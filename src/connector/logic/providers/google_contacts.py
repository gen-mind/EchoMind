"""
Google Contacts provider for fetching contacts as markdown documents.

Supports:
- OAuth2 authentication (shared Google credentials)
- People API v1 syncToken-based incremental sync
- 410 GONE handling (syncToken expires after 7 days)
- Checkpoint-based resumable sync
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from connector.logic.checkpoint import (
    ConnectorCheckpoint,
    GoogleContactsCheckpoint,
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
    contact_to_markdown,
    handle_rate_limit,
    slugify,
)
from connector.logic.providers.google_utils.rate_limiter import MAX_RATE_LIMIT_RETRIES
from echomind_lib.db.minio import MinIOClient

logger = logging.getLogger("echomind-connector.google_contacts")

PEOPLE_API = "https://people.googleapis.com/v1"

# Person fields to request from People API
PERSON_FIELDS = (
    "names,emailAddresses,phoneNumbers,organizations,"
    "addresses,birthdays,biographies,photos"
)

# Contacts per page
CONTACTS_PAGE_SIZE = 1000

# Maximum contacts to process per sync cycle
MAX_CONTACTS_PER_SYNC = 50000


class GoogleContactsProvider(BaseProvider):
    """
    Provider for Google Contacts.

    Fetches contacts via Google People API and converts them to
    markdown documents. Uses syncToken for efficient incremental sync.
    On 410 GONE (token expires after 7 days), performs full resync.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize Google Contacts provider.

        Args:
            http_client: Optional HTTP client (for testing).
        """
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._owns_client = http_client is None
        self._auth = GoogleAuthHelper(self._client)

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "google_contacts"

    async def authenticate(self, config: dict[str, Any]) -> None:
        """
        Authenticate with People API via shared Google credentials.

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
        Verify the People API connection.

        Returns:
            True if connected and authenticated, False otherwise.
        """
        if not self._auth.access_token:
            return False

        try:
            response = await self._client.get(
                f"{PEOPLE_API}/people/me",
                params={"personFields": "names"},
                headers=self._auth.auth_headers(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"🔌 Contacts connection check failed: {e}")
            return False

    async def get_changes(
        self,
        config: dict[str, Any],
        checkpoint: ConnectorCheckpoint,
    ) -> AsyncIterator[FileChange]:
        """
        Detect changes using People API syncToken.

        On first sync, lists all contacts. On subsequent syncs, uses
        syncToken for incremental changes. On 410 GONE, clears
        syncToken and does full resync.

        Args:
            config: Provider configuration.
            checkpoint: GoogleContactsCheckpoint with sync state.

        Yields:
            FileChange for each changed contact.
        """
        if not isinstance(checkpoint, GoogleContactsCheckpoint):
            checkpoint = GoogleContactsCheckpoint()

        contacts_processed = 0
        page_token = checkpoint.page_token

        while True:
            if contacts_processed >= MAX_CONTACTS_PER_SYNC:
                checkpoint.has_more = True
                return

            params: dict[str, Any] = {
                "personFields": PERSON_FIELDS,
                "pageSize": CONTACTS_PAGE_SIZE,
            }

            if checkpoint.sync_token and not page_token:
                # Incremental sync
                params["syncToken"] = checkpoint.sync_token
                params["requestSyncToken"] = "true"
            else:
                # Full sync
                params["requestSyncToken"] = "true"

            if page_token:
                params["pageToken"] = page_token

            try:
                response = await self._api_get(
                    f"{PEOPLE_API}/people/me/connections",
                    params=params,
                )
            except DownloadError as e:
                if "410" in str(e):
                    # syncToken expired (7-day limit) — full resync
                    logger.warning(
                        "⚠️ [google_contacts] syncToken expired, "
                        "performing full resync"
                    )
                    checkpoint.sync_token = None
                    checkpoint.page_token = None
                    async for change in self.get_changes(config, checkpoint):
                        yield change
                    return
                raise

            data = response.json()

            for person in data.get("connections", []):
                resource_name = person.get("resourceName", "")
                metadata = person.get("metadata", {})

                # Check if contact was deleted (in sync responses)
                if metadata.get("deleted"):
                    yield FileChange(
                        source_id=resource_name,
                        action="delete",
                        file=None,
                    )
                else:
                    names = person.get("names", [])
                    display_name = (
                        names[0].get("displayName", "Unknown")
                        if names
                        else "Unknown"
                    )

                    yield FileChange(
                        source_id=resource_name,
                        action="update",
                        file=FileMetadata(
                            source_id=resource_name,
                            name=f"{slugify(display_name)}.md",
                            mime_type="text/markdown",
                            content_hash=person.get("etag"),
                            extra={"person_data": person},
                        ),
                    )
                contacts_processed += 1

            page_token = data.get("nextPageToken")
            checkpoint.page_token = page_token

            if not page_token:
                # Save syncToken for next incremental sync
                new_sync_token = data.get("nextSyncToken")
                if new_sync_token:
                    checkpoint.sync_token = new_sync_token
                checkpoint.page_token = None
                break

    async def download_file(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> DownloadedFile:
        """
        Convert a contact to markdown.

        The person data is passed via file.extra['person_data'] from
        get_changes(), so no additional API call is needed.

        Args:
            file: FileMetadata with person data in extra.
            config: Provider configuration.

        Returns:
            DownloadedFile with markdown content.

        Raises:
            DownloadError: If person data is missing.
        """
        person_data = file.extra.get("person_data")
        if not person_data:
            raise DownloadError(
                self.provider_name,
                file.source_id,
                "No person data in FileMetadata.extra",
            )

        markdown = contact_to_markdown(person_data)
        content = markdown.encode("utf-8")

        email = config.get("user_email", "")
        external_access = ExternalAccess.for_users({email}) if email else ExternalAccess.empty()

        return DownloadedFile(
            source_id=file.source_id,
            name=file.name,
            content=content,
            mime_type="text/markdown",
            content_hash=hashlib.md5(content).hexdigest(),
            modified_at=datetime.now(timezone.utc),
            external_access=external_access,
            original_url=f"https://contacts.google.com/person/{file.source_id.split('/')[-1]}",
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
        Convert contact to markdown and upload to MinIO.

        Args:
            file: FileMetadata with person data in extra.
            config: Provider configuration.
            minio_client: MinIO client for storage.
            bucket: Target MinIO bucket.
            object_key: Object key in MinIO.

        Returns:
            StreamResult with storage path.

        Raises:
            DownloadError: If conversion or upload fails.
        """
        person_data = file.extra.get("person_data")
        if not person_data:
            raise DownloadError(
                self.provider_name,
                file.source_id,
                "No person data in FileMetadata.extra",
            )

        markdown = contact_to_markdown(person_data)
        content = markdown.encode("utf-8")

        result = await minio_client.upload_file(
            bucket_name=bucket,
            object_name=object_key,
            data=content,
            content_type="text/markdown",
        )

        logger.info(
            f"📦 Stored contact {file.source_id} ({len(content)} bytes)"
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
        Return permissions for a contact.

        Contacts are private to the owner.

        Args:
            file: File metadata.
            config: Provider configuration with 'user_email'.

        Returns:
            ExternalAccess restricted to the contact owner.
        """
        email = config.get("user_email", "")
        if email:
            return ExternalAccess.for_users({email})
        return ExternalAccess.empty()

    async def sync(
        self,
        config: dict[str, Any],
        checkpoint: ConnectorCheckpoint,
    ) -> AsyncIterator[DownloadedFile | DeletedFile]:
        """
        Perform full or incremental contacts sync.

        Args:
            config: Provider configuration.
            checkpoint: GoogleContactsCheckpoint for resumption.

        Yields:
            DownloadedFile or DeletedFile for each change.
        """
        if not isinstance(checkpoint, GoogleContactsCheckpoint):
            checkpoint = GoogleContactsCheckpoint()

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
                        f"❌ Failed to process contact {change.source_id}: {e}"
                    )
                    checkpoint.error_count += 1

        checkpoint.has_more = False

    def create_checkpoint(self) -> GoogleContactsCheckpoint:
        """
        Create a new Google Contacts checkpoint.

        Returns:
            Fresh GoogleContactsCheckpoint instance.
        """
        return GoogleContactsCheckpoint()

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
        Make a GET request to the People API with rate limit handling.

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
                f"People API error {response.status_code}: {response.text}",
            )

        raise RateLimitError(self.provider_name)
