"""
Google Calendar provider for fetching events as markdown documents.

Supports:
- OAuth2 authentication (shared Google credentials)
- syncToken-based incremental sync
- 410 GONE handling (automatic full resync)
- Multi-calendar support
- Checkpoint-based resumable sync
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

import httpx

from connector.logic.checkpoint import (
    ConnectorCheckpoint,
    GoogleCalendarCheckpoint,
)
from connector.logic.exceptions import (
    AuthenticationError,
    DownloadError,
    RateLimitError,
)
from connector.logic.permissions import ExternalAccess
from connector.logic.providers.base import (
    BaseProvider,
    DeletedFile,
    DownloadedFile,
    FileChange,
    FileMetadata,
    StreamResult,
)
from connector.logic.providers.google_utils import (
    GoogleAuthHelper,
    calendar_event_to_markdown,
    handle_rate_limit,
    slugify,
)
from connector.logic.providers.google_utils.rate_limiter import MAX_RATE_LIMIT_RETRIES
from echomind_lib.db.minio import MinIOClient

logger = logging.getLogger("echomind-connector.google_calendar")

CALENDAR_API = "https://www.googleapis.com/calendar/v3"

# Default time range for initial sync
DEFAULT_PAST_DAYS = 90

# Events per page
EVENTS_PAGE_SIZE = 250

# Maximum events to process per sync cycle
MAX_EVENTS_PER_SYNC = 10000


class GoogleCalendarProvider(BaseProvider):
    """
    Provider for Google Calendar events.

    Fetches calendar events via Calendar API and converts them to
    markdown documents. Uses syncToken for efficient incremental sync.
    On 410 GONE, performs a full resync.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize Google Calendar provider.

        Args:
            http_client: Optional HTTP client (for testing).
        """
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._owns_client = http_client is None
        self._auth = GoogleAuthHelper(self._client)

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "google_calendar"

    async def authenticate(self, config: dict[str, Any]) -> None:
        """
        Authenticate with Google Calendar API via shared credentials.

        Args:
            config: Must contain 'access_token'. Optionally contains
                'refresh_token', 'client_id', 'client_secret',
                'token_expires_at'.

        Raises:
            AuthenticationError: If authentication fails.
        """
        await self._auth.authenticate(config)

    async def check_connection(self) -> bool:
        """
        Verify the Calendar API connection.

        Returns:
            True if connected and authenticated, False otherwise.
        """
        if not self._auth.access_token:
            return False

        try:
            response = await self._client.get(
                f"{CALENDAR_API}/users/me/calendarList",
                params={"maxResults": 1},
                headers=self._auth.auth_headers(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"🔌 Calendar connection check failed: {e}")
            return False

    async def get_changes(
        self,
        config: dict[str, Any],
        checkpoint: ConnectorCheckpoint,
    ) -> AsyncIterator[FileChange]:
        """
        Detect changes using Calendar API syncToken.

        On first sync, fetches events from the last 90 days + all future.
        On subsequent syncs, uses syncToken for incremental changes.
        On 410 GONE, clears syncToken and does full resync.

        Args:
            config: Provider configuration.
            checkpoint: GoogleCalendarCheckpoint with sync state.

        Yields:
            FileChange for each changed event.
        """
        if not isinstance(checkpoint, GoogleCalendarCheckpoint):
            checkpoint = GoogleCalendarCheckpoint()

        # Reset calendar index at the start of each sync cycle
        checkpoint.current_calendar_idx = 0

        # Discover calendars (refresh list each cycle)
        checkpoint.calendar_ids = await self._list_calendar_ids()

        # Process each calendar
        while checkpoint.current_calendar_idx < len(checkpoint.calendar_ids):
            calendar_id = checkpoint.calendar_ids[checkpoint.current_calendar_idx]

            async for change in self._sync_calendar(
                calendar_id, config, checkpoint
            ):
                yield change

            checkpoint.current_calendar_idx += 1
            checkpoint.page_token = None

    async def _list_calendar_ids(self) -> list[str]:
        """
        List all calendar IDs the user has access to.

        Returns:
            List of calendar ID strings.

        Raises:
            DownloadError: If calendar list fetch fails.
        """
        calendar_ids: list[str] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"maxResults": 250}
            if page_token:
                params["pageToken"] = page_token

            response = await self._api_get(
                f"{CALENDAR_API}/users/me/calendarList",
                params=params,
            )

            data = response.json()
            for cal in data.get("items", []):
                calendar_ids.append(cal["id"])

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"📅 [google_calendar] Found {len(calendar_ids)} calendars")
        return calendar_ids

    async def _sync_calendar(
        self,
        calendar_id: str,
        config: dict[str, Any],
        checkpoint: GoogleCalendarCheckpoint,
    ) -> AsyncIterator[FileChange]:
        """
        Sync events from a single calendar.

        Args:
            calendar_id: Google Calendar ID.
            config: Provider configuration.
            checkpoint: Checkpoint with syncToken state.

        Yields:
            FileChange for each changed event.
        """
        events_processed = 0
        page_token = checkpoint.page_token

        # Load per-calendar syncToken
        cal_sync_token = checkpoint.sync_tokens.get(calendar_id)

        while True:
            if events_processed >= MAX_EVENTS_PER_SYNC:
                checkpoint.has_more = True
                return

            params: dict[str, Any] = {
                "maxResults": EVENTS_PAGE_SIZE,
                "singleEvents": "true",
                "orderBy": "startTime",
            }

            if cal_sync_token and not page_token:
                # Incremental sync
                params["syncToken"] = cal_sync_token
                # Remove orderBy — not allowed with syncToken
                del params["singleEvents"]
                del params["orderBy"]
            elif not page_token:
                # Initial sync — set time range
                past_days = config.get("past_days", DEFAULT_PAST_DAYS)
                time_min = datetime.now(timezone.utc) - timedelta(days=past_days)
                params["timeMin"] = time_min.isoformat()

            if page_token:
                params["pageToken"] = page_token

            try:
                response = await self._api_get(
                    f"{CALENDAR_API}/calendars/{calendar_id}/events",
                    params=params,
                )
            except DownloadError as e:
                if "410" in str(e):
                    # syncToken expired — full resync for this calendar
                    logger.warning(
                        f"⚠️ [google_calendar] syncToken expired for {calendar_id}, "
                        "performing full resync"
                    )
                    checkpoint.sync_tokens.pop(calendar_id, None)
                    checkpoint.page_token = None
                    async for change in self._sync_calendar(
                        calendar_id, config, checkpoint
                    ):
                        yield change
                    return
                raise

            data = response.json()

            for event in data.get("items", []):
                event_id = event.get("id", "")
                status = event.get("status", "")

                if status == "cancelled":
                    yield FileChange(
                        source_id=f"gcal_{calendar_id}_{event_id}",
                        action="delete",
                        file=None,
                    )
                else:
                    summary = event.get("summary", "Untitled Event")
                    start = event.get("start", {})
                    event_date = start.get("date") or start.get("dateTime", "")[:10]

                    yield FileChange(
                        source_id=f"gcal_{calendar_id}_{event_id}",
                        action="update",
                        file=FileMetadata(
                            source_id=f"gcal_{calendar_id}_{event_id}",
                            name=f"{slugify(summary)}_{event_date}.md",
                            mime_type="text/markdown",
                            content_hash=event.get("etag"),
                            extra={"event_data": event, "calendar_id": calendar_id},
                        ),
                    )
                events_processed += 1

            page_token = data.get("nextPageToken")
            checkpoint.page_token = page_token

            if not page_token:
                # Save per-calendar syncToken for next incremental sync
                new_sync_token = data.get("nextSyncToken")
                if new_sync_token:
                    checkpoint.sync_tokens[calendar_id] = new_sync_token
                checkpoint.page_token = None
                break

    async def download_file(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> DownloadedFile:
        """
        Convert a calendar event to markdown.

        The event data is passed via file.extra['event_data'] from
        get_changes(), so no additional API call is needed.

        Args:
            file: FileMetadata with event data in extra.
            config: Provider configuration.

        Returns:
            DownloadedFile with markdown content.

        Raises:
            DownloadError: If event data is missing.
        """
        event_data = file.extra.get("event_data")
        if not event_data:
            raise DownloadError(
                self.provider_name,
                file.source_id,
                "No event data in FileMetadata.extra",
            )

        markdown = calendar_event_to_markdown(event_data)
        content = markdown.encode("utf-8")

        email = config.get("user_email", "")
        external_access = ExternalAccess.for_users({email}) if email else ExternalAccess.empty()

        # Add attendee emails to permissions
        attendees = event_data.get("attendees", [])
        attendee_emails = {
            att["email"] for att in attendees if "email" in att
        }
        if email:
            attendee_emails.add(email)
        if attendee_emails:
            external_access = ExternalAccess.for_users(attendee_emails)

        html_link = event_data.get("htmlLink", "")

        return DownloadedFile(
            source_id=file.source_id,
            name=file.name,
            content=content,
            mime_type="text/markdown",
            content_hash=hashlib.md5(content).hexdigest(),
            modified_at=datetime.now(timezone.utc),
            external_access=external_access,
            original_url=html_link,
        )

    async def stream_to_storage(
        self,
        file: FileMetadata,
        config: dict[str, Any],
        minio_client: MinIOClient,
        bucket: str,
        object_key: str,
    ) -> StreamResult:
        """
        Convert event to markdown and upload to MinIO.

        Args:
            file: FileMetadata with event data in extra.
            config: Provider configuration.
            minio_client: MinIO client for storage.
            bucket: Target MinIO bucket.
            object_key: Object key in MinIO.

        Returns:
            StreamResult with storage path.

        Raises:
            DownloadError: If conversion or upload fails.
        """
        event_data = file.extra.get("event_data")
        if not event_data:
            raise DownloadError(
                self.provider_name,
                file.source_id,
                "No event data in FileMetadata.extra",
            )

        markdown = calendar_event_to_markdown(event_data)
        content = markdown.encode("utf-8")

        result = await minio_client.upload_file(
            bucket_name=bucket,
            object_name=object_key,
            data=content,
            content_type="text/markdown",
        )

        logger.info(
            f"📦 Stored calendar event {file.source_id} ({len(content)} bytes)"
        )

        return StreamResult(
            storage_path=f"minio:{bucket}:{object_key}",
            etag=result,
            size=len(content),
            content_hash=hashlib.md5(content).hexdigest(),
        )

    async def get_file_permissions(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> ExternalAccess:
        """
        Return permissions for a calendar event.

        Calendar events are visible to the owner and all attendees.

        Args:
            file: File metadata with event data in extra.
            config: Provider configuration with 'user_email'.

        Returns:
            ExternalAccess with owner and attendee emails.
        """
        emails: set[str] = set()

        email = config.get("user_email", "")
        if email:
            emails.add(email)

        event_data = file.extra.get("event_data", {})
        for att in event_data.get("attendees", []):
            att_email = att.get("email")
            if att_email:
                emails.add(att_email)

        return ExternalAccess.for_users(emails) if emails else ExternalAccess.empty()

    async def sync(
        self,
        config: dict[str, Any],
        checkpoint: ConnectorCheckpoint,
    ) -> AsyncIterator[DownloadedFile | DeletedFile]:
        """
        Perform full or incremental calendar sync.

        Args:
            config: Provider configuration.
            checkpoint: GoogleCalendarCheckpoint for resumption.

        Yields:
            DownloadedFile or DeletedFile for each change.
        """
        if not isinstance(checkpoint, GoogleCalendarCheckpoint):
            checkpoint = GoogleCalendarCheckpoint()

        checkpoint.last_sync_start = datetime.now(timezone.utc)

        if not self._auth.access_token:
            await self.authenticate(config)

        async for change in self.get_changes(config, checkpoint):
            if change.action == "delete":
                yield DeletedFile(source_id=change.source_id)
            elif change.file:
                try:
                    downloaded = await self.download_file(change.file, config)
                    yield downloaded
                except DownloadError as e:
                    logger.error(
                        f"❌ Failed to process event {change.source_id}: {e}"
                    )
                    checkpoint.error_count += 1

        checkpoint.has_more = False

    def create_checkpoint(self) -> GoogleCalendarCheckpoint:
        """
        Create a new Google Calendar checkpoint.

        Returns:
            Fresh GoogleCalendarCheckpoint instance.
        """
        return GoogleCalendarCheckpoint()

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _api_get(
        self,
        url: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        """
        Make a GET request to the Calendar API with rate limit handling.

        Args:
            url: Full API URL.
            params: Query parameters.

        Returns:
            Successful httpx.Response.

        Raises:
            RateLimitError: If rate limit retries exhausted.
            DownloadError: If non-200/non-429 response.
        """
        for attempt in range(MAX_RATE_LIMIT_RETRIES):
            response = await self._client.get(
                url,
                headers=self._auth.auth_headers(),
                params=params,
            )

            if response.status_code == 200:
                return response

            if response.status_code == 429:
                if attempt >= MAX_RATE_LIMIT_RETRIES - 1:
                    raise RateLimitError(self.provider_name)
                await handle_rate_limit(response, self.provider_name)
                continue

            raise DownloadError(
                self.provider_name,
                url,
                f"Calendar API error {response.status_code}: {response.text}",
            )

        raise RateLimitError(self.provider_name)
