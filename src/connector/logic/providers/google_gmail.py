"""
Gmail provider for fetching email threads as markdown documents.

Supports:
- OAuth2 authentication (shared Google credentials)
- History API for incremental sync
- Thread-based retrieval (each thread → one markdown document)
- Checkpoint-based resumable sync
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from connector.logic.checkpoint import ConnectorCheckpoint, GmailCheckpoint
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
    gmail_thread_to_markdown,
    handle_rate_limit,
    slugify,
)
from connector.logic.providers.google_utils.rate_limiter import MAX_RATE_LIMIT_RETRIES
from echomind_lib.db.minio import MinIOClient

logger = logging.getLogger("echomind-connector.gmail")

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"

# Default page size for thread listing
THREADS_PAGE_SIZE = 100

# Maximum threads to process per sync cycle
MAX_THREADS_PER_SYNC = 5000


class GmailProvider(BaseProvider):
    """
    Provider for Gmail email threads.

    Fetches email threads via Gmail API and converts them to markdown
    documents for storage and embedding. Uses historyId for efficient
    incremental sync.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize Gmail provider.

        Args:
            http_client: Optional HTTP client (for testing).
        """
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._owns_client = http_client is None
        self._auth = GoogleAuthHelper(self._client)

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "gmail"

    async def authenticate(self, config: dict[str, Any]) -> None:
        """
        Authenticate with Gmail API via shared Google credentials.

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
        Verify the Gmail API connection.

        Returns:
            True if connected and authenticated, False otherwise.
        """
        if not self._auth.access_token:
            return False

        try:
            response = await self._client.get(
                f"{GMAIL_API}/users/me/profile",
                headers=self._auth.auth_headers(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"🔌 Gmail connection check failed: {e}")
            return False

    async def get_changes(
        self,
        config: dict[str, Any],
        checkpoint: ConnectorCheckpoint,
    ) -> AsyncIterator[FileChange]:
        """
        Detect changes using Gmail History API.

        On first sync, lists all threads. On subsequent syncs, uses
        history.list with historyId for incremental changes.

        Args:
            config: Provider configuration.
            checkpoint: GmailCheckpoint with history_id state.

        Yields:
            FileChange for each changed thread.
        """
        if not isinstance(checkpoint, GmailCheckpoint):
            checkpoint = GmailCheckpoint()

        if checkpoint.history_id:
            # Incremental sync via history.list
            async for change in self._get_history_changes(config, checkpoint):
                yield change
        else:
            # First sync - list all threads
            async for change in self._list_all_threads(config, checkpoint):
                yield change

    async def _list_all_threads(
        self,
        config: dict[str, Any],
        checkpoint: GmailCheckpoint,
    ) -> AsyncIterator[FileChange]:
        """
        List all threads for initial sync.

        Args:
            config: Provider configuration.
            checkpoint: GmailCheckpoint for page token resumption.

        Yields:
            FileChange for each thread.
        """
        # Get current historyId for future incremental syncs
        profile = await self._get_profile()
        checkpoint.history_id = str(profile.get("historyId", ""))

        page_token = checkpoint.page_token
        threads_processed = 0

        while True:
            if threads_processed >= MAX_THREADS_PER_SYNC:
                checkpoint.has_more = True
                return

            params: dict[str, Any] = {
                "maxResults": THREADS_PAGE_SIZE,
                "includeSpamTrash": "false",
            }
            if page_token:
                params["pageToken"] = page_token

            response = await self._api_get(
                f"{GMAIL_API}/users/me/threads",
                params=params,
            )

            data = response.json()

            for thread_stub in data.get("threads", []):
                thread_id = thread_stub["id"]
                snippet = thread_stub.get("snippet", "")

                yield FileChange(
                    source_id=thread_id,
                    action="create",
                    file=FileMetadata(
                        source_id=thread_id,
                        name=slugify(snippet[:80]) or thread_id,
                        mime_type="text/markdown",
                        content_hash=thread_stub.get("historyId"),
                    ),
                )
                threads_processed += 1

            page_token = data.get("nextPageToken")
            checkpoint.page_token = page_token

            if not page_token:
                checkpoint.page_token = None
                break

    async def _get_history_changes(
        self,
        config: dict[str, Any],
        checkpoint: GmailCheckpoint,
    ) -> AsyncIterator[FileChange]:
        """
        Get changes since last sync via Gmail History API.

        Args:
            config: Provider configuration.
            checkpoint: GmailCheckpoint with history_id.

        Yields:
            FileChange for each changed thread.
        """
        changed_thread_ids: set[str] = set()
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {
                "startHistoryId": checkpoint.history_id,
                "historyTypes": "messageAdded,messageDeleted,labelAdded,labelRemoved",
                "maxResults": 500,
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                response = await self._api_get(
                    f"{GMAIL_API}/users/me/history",
                    params=params,
                )
            except DownloadError as e:
                # 404 means historyId is too old — need full resync
                if "404" in str(e):
                    logger.warning(
                        "⚠️ [gmail] historyId expired, forcing full resync"
                    )
                    checkpoint.history_id = None
                    checkpoint.page_token = None
                    async for change in self._list_all_threads(config, checkpoint):
                        yield change
                    return
                raise

            data = response.json()

            # Collect changed thread IDs
            for history in data.get("history", []):
                for msg_added in history.get("messagesAdded", []):
                    tid = msg_added.get("message", {}).get("threadId")
                    if tid:
                        changed_thread_ids.add(tid)
                for msg_deleted in history.get("messagesDeleted", []):
                    tid = msg_deleted.get("message", {}).get("threadId")
                    if tid:
                        changed_thread_ids.add(tid)
                for label_added in history.get("labelsAdded", []):
                    tid = label_added.get("message", {}).get("threadId")
                    if tid:
                        changed_thread_ids.add(tid)
                for label_removed in history.get("labelsRemoved", []):
                    tid = label_removed.get("message", {}).get("threadId")
                    if tid:
                        changed_thread_ids.add(tid)

            # Update historyId
            new_history_id = data.get("historyId")
            if new_history_id:
                checkpoint.history_id = str(new_history_id)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        # Yield changes for each affected thread
        for thread_id in changed_thread_ids:
            yield FileChange(
                source_id=thread_id,
                action="update",
                file=FileMetadata(
                    source_id=thread_id,
                    name=thread_id,
                    mime_type="text/markdown",
                ),
            )

    async def download_file(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> DownloadedFile:
        """
        Fetch a Gmail thread and convert to markdown.

        Args:
            file: FileMetadata with source_id = thread ID.
            config: Provider configuration.

        Returns:
            DownloadedFile with markdown content.

        Raises:
            DownloadError: If thread fetch fails.
        """
        thread_data = await self._get_thread(file.source_id)
        markdown = gmail_thread_to_markdown(thread_data)
        content = markdown.encode("utf-8")

        # Extract subject for filename
        messages = thread_data.get("messages", [])
        subject = ""
        if messages:
            headers = messages[0].get("payload", {}).get("headers", [])
            for h in headers:
                if h.get("name", "").lower() == "subject":
                    subject = h.get("value", "")
                    break

        name = f"{slugify(subject) or file.source_id}.md"

        # Get user email for permissions
        email = config.get("user_email", "")
        external_access = ExternalAccess.for_users({email}) if email else ExternalAccess.empty()

        return DownloadedFile(
            source_id=file.source_id,
            name=name,
            content=content,
            mime_type="text/markdown",
            content_hash=hashlib.md5(content).hexdigest(),
            modified_at=datetime.now(timezone.utc),
            external_access=external_access,
            original_url=f"https://mail.google.com/mail/u/0/#inbox/{file.source_id}",
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
        Fetch thread, convert to markdown, and upload to MinIO.

        Args:
            file: FileMetadata with source_id = thread ID.
            config: Provider configuration.
            minio_client: MinIO client for storage.
            bucket: Target MinIO bucket.
            object_key: Object key in MinIO.

        Returns:
            StreamResult with storage path and metadata.

        Raises:
            DownloadError: If thread fetch or upload fails.
        """
        thread_data = await self._get_thread(file.source_id)
        markdown = gmail_thread_to_markdown(thread_data)
        content = markdown.encode("utf-8")

        result = await minio_client.upload_file(
            bucket_name=bucket,
            object_name=object_key,
            data=content,
            content_type="text/markdown",
        )

        logger.info(
            f"📦 Stored Gmail thread {file.source_id} ({len(content)} bytes)"
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
        Return permissions for a Gmail thread.

        Gmail emails are private to the mailbox owner.

        Args:
            file: File metadata.
            config: Provider configuration with 'user_email'.

        Returns:
            ExternalAccess restricted to the mailbox owner.
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
        Perform full or incremental Gmail sync.

        Args:
            config: Provider configuration.
            checkpoint: GmailCheckpoint for resumption.

        Yields:
            DownloadedFile for each changed thread.
        """
        if not isinstance(checkpoint, GmailCheckpoint):
            checkpoint = GmailCheckpoint()

        checkpoint.last_sync_start = datetime.now(timezone.utc)

        if not self._auth.access_token:
            await self.authenticate(config)

        async for change in self.get_changes(config, checkpoint):
            if change.action == "delete":
                yield DeletedFile(source_id=change.source_id)
            elif change.file:
                if not checkpoint.mark_thread_retrieved(change.source_id):
                    continue

                try:
                    downloaded = await self.download_file(change.file, config)
                    yield downloaded
                except DownloadError as e:
                    logger.error(f"❌ Failed to download thread {change.source_id}: {e}")
                    checkpoint.error_count += 1

        checkpoint.has_more = False

    def create_checkpoint(self) -> GmailCheckpoint:
        """
        Create a new Gmail checkpoint.

        Returns:
            Fresh GmailCheckpoint instance.
        """
        return GmailCheckpoint()

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_profile(self) -> dict[str, Any]:
        """
        Get the Gmail profile (email, historyId).

        Returns:
            Gmail profile dict.

        Raises:
            DownloadError: If profile fetch fails.
        """
        response = await self._api_get(
            f"{GMAIL_API}/users/me/profile",
            params={},
        )
        return response.json()

    async def _get_thread(self, thread_id: str) -> dict[str, Any]:
        """
        Get a full thread with messages expanded.

        Args:
            thread_id: Gmail thread ID.

        Returns:
            Thread dict with messages.

        Raises:
            DownloadError: If thread fetch fails.
        """
        response = await self._api_get(
            f"{GMAIL_API}/users/me/threads/{thread_id}",
            params={"format": "full"},
        )
        return response.json()

    async def _api_get(
        self,
        url: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        """
        Make a GET request to the Gmail API with rate limit handling.

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
                f"Gmail API error {response.status_code}: {response.text}",
            )

        raise RateLimitError(self.provider_name)
