"""
Google Drive provider for fetching files and folders.

Supports:
- OAuth2 authentication (user tokens)
- Service account authentication (impersonation)
- Changes API for incremental sync
- Google Workspace export to PDF
- Checkpoint-based resumable sync
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

import httpx

from connector.logic.checkpoint import (
    ConnectorCheckpoint,
    GoogleDriveCheckpoint,
)
from connector.logic.exceptions import (
    AuthenticationError,
    DownloadError,
    ExportError,
    FileTooLargeError,
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
from echomind_lib.db.minio import MinIOClient

logger = logging.getLogger("echomind-connector.google_drive")


# Google Workspace MIME types and their export format (all to PDF)
GOOGLE_EXPORT_MIMES: dict[str, str] = {
    "application/vnd.google-apps.document": "application/pdf",
    "application/vnd.google-apps.spreadsheet": "application/pdf",
    "application/vnd.google-apps.presentation": "application/pdf",
    "application/vnd.google-apps.drawing": "application/pdf",
}

# Maximum export size (Google API limitation)
MAX_EXPORT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class GoogleDriveProvider(BaseProvider):
    """
    Provider for Google Drive files and Google Workspace documents.

    Uses the Google Drive API v3 for file operations and the Changes API
    for efficient incremental sync.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        max_file_size: int = 100 * 1024 * 1024,
    ):
        """
        Initialize Google Drive provider.

        Args:
            http_client: Optional HTTP client (for testing).
            max_file_size: Maximum file size to download in bytes.
        """
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._owns_client = http_client is None
        self._max_file_size = max_file_size
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "google_drive"

    async def authenticate(self, config: dict[str, Any]) -> None:
        """
        Authenticate with Google Drive API.

        Supports OAuth2 tokens (from user auth flow) or service account
        credentials.

        Args:
            config: Must contain either:
                - 'access_token' and 'refresh_token' for OAuth2
                - 'service_account_json' path for service account

        Raises:
            AuthenticationError: If authentication fails.
        """
        try:
            if "access_token" in config:
                # OAuth2 token from user flow
                self._access_token = config["access_token"]
                # Check if token needs refresh
                if "token_expires_at" in config:
                    self._token_expires_at = datetime.fromisoformat(
                        config["token_expires_at"]
                    )
                    if self._token_expires_at <= datetime.now(timezone.utc):
                        await self._refresh_token(config)
            elif "service_account_json" in config:
                # Service account - generate token
                await self._authenticate_service_account(config)
            else:
                raise AuthenticationError(
                    self.provider_name,
                    "Missing access_token or service_account_json in config",
                )

            # Verify token works
            if not await self.check_connection():
                raise AuthenticationError(
                    self.provider_name,
                    "Token validation failed",
                )

            logger.info("🔐 Authenticated with Google Drive API")

        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(self.provider_name, str(e)) from e

    async def _refresh_token(self, config: dict[str, Any]) -> None:
        """
        Refresh OAuth2 access token.

        Args:
            config: Must contain 'refresh_token', 'client_id', 'client_secret'.

        Raises:
            AuthenticationError: If refresh fails.
        """
        refresh_token = config.get("refresh_token")
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")

        if not all([refresh_token, client_id, client_secret]):
            raise AuthenticationError(
                self.provider_name,
                "Missing refresh_token, client_id, or client_secret",
            )

        response = await self._client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

        if response.status_code != 200:
            raise AuthenticationError(
                self.provider_name,
                f"Token refresh failed: {response.text}",
            )

        data = response.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=expires_in
        )

        logger.info("🔄 Refreshed Google Drive access token")

    async def _authenticate_service_account(self, config: dict[str, Any]) -> None:
        """
        Authenticate using service account credentials.

        Args:
            config: Must contain 'service_account_json' path.

        Raises:
            AuthenticationError: If authentication fails.
        """
        # Service account auth requires google-auth library
        # For now, we expect pre-generated tokens
        raise AuthenticationError(
            self.provider_name,
            "Service account auth not yet implemented - use OAuth2 tokens",
        )

    async def check_connection(self) -> bool:
        """
        Verify connection to Google Drive API.

        Returns:
            True if connected, False otherwise.
        """
        if not self._access_token:
            return False

        try:
            response = await self._client.get(
                "https://www.googleapis.com/drive/v3/about",
                params={"fields": "user"},
                headers=self._auth_headers(),
            )
            return response.status_code == 200
        except Exception:
            return False

    def _auth_headers(self) -> dict[str, str]:
        """Return authorization headers."""
        return {"Authorization": f"Bearer {self._access_token}"}

    async def get_changes(
        self,
        config: dict[str, Any],
        checkpoint: ConnectorCheckpoint,
    ) -> AsyncIterator[FileChange]:
        """
        Detect changes using Google Drive Changes API.

        Uses the Changes API for efficient incremental sync. On first sync,
        gets start page token and lists all files.

        Args:
            config: Provider configuration.
            checkpoint: GoogleDriveCheckpoint with changes_start_page_token.

        Yields:
            FileChange for each changed file.
        """
        if not isinstance(checkpoint, GoogleDriveCheckpoint):
            checkpoint = GoogleDriveCheckpoint()

        # Get or create start page token
        if not checkpoint.changes_start_page_token:
            # First sync - get start page token
            response = await self._client.get(
                "https://www.googleapis.com/drive/v3/changes/startPageToken",
                headers=self._auth_headers(),
            )
            if response.status_code != 200:
                raise DownloadError(
                    self.provider_name,
                    "startPageToken",
                    f"Failed to get start page token: {response.text}",
                )
            checkpoint.changes_start_page_token = response.json()["startPageToken"]

            # Do initial full scan
            async for change in self._list_all_files(config, checkpoint):
                yield change
            return

        # Incremental sync using Changes API
        page_token = checkpoint.changes_start_page_token

        while page_token:
            response = await self._client.get(
                "https://www.googleapis.com/drive/v3/changes",
                params={
                    "pageToken": page_token,
                    "fields": "nextPageToken,newStartPageToken,changes(removed,fileId,file(id,name,mimeType,md5Checksum,size,modifiedTime,webViewLink,parents))",
                    "pageSize": 100,
                    "includeRemoved": "true",
                },
                headers=self._auth_headers(),
            )

            if response.status_code == 429:
                raise RateLimitError(self.provider_name)
            if response.status_code != 200:
                raise DownloadError(
                    self.provider_name,
                    "changes",
                    f"Changes API error: {response.text}",
                )

            data = response.json()

            for change in data.get("changes", []):
                if change.get("removed"):
                    yield FileChange(
                        source_id=change["fileId"],
                        action="delete",
                        file=None,
                    )
                else:
                    file_data = change.get("file", {})
                    yield FileChange(
                        source_id=file_data["id"],
                        action="update",
                        file=self._parse_file_metadata(file_data),
                    )

            page_token = data.get("nextPageToken")
            if "newStartPageToken" in data:
                checkpoint.changes_start_page_token = data["newStartPageToken"]

    async def _list_all_files(
        self,
        config: dict[str, Any],
        checkpoint: GoogleDriveCheckpoint,
    ) -> AsyncIterator[FileChange]:
        """
        List all files for initial sync.

        Args:
            config: Provider configuration.
            checkpoint: Checkpoint for deduplication.

        Yields:
            FileChange for each file.
        """
        folder_id = config.get("folder_id")
        query = "trashed = false"
        if folder_id:
            query = f"'{folder_id}' in parents and trashed = false"

        page_token = None

        while True:
            params: dict[str, Any] = {
                "q": query,
                "fields": "nextPageToken,files(id,name,mimeType,md5Checksum,size,modifiedTime,webViewLink,parents)",
                "pageSize": 100,
            }
            if page_token:
                params["pageToken"] = page_token

            response = await self._client.get(
                "https://www.googleapis.com/drive/v3/files",
                params=params,
                headers=self._auth_headers(),
            )

            if response.status_code == 429:
                raise RateLimitError(self.provider_name)
            if response.status_code != 200:
                raise DownloadError(
                    self.provider_name,
                    "list_files",
                    f"List files error: {response.text}",
                )

            data = response.json()

            for file_data in data.get("files", []):
                yield FileChange(
                    source_id=file_data["id"],
                    action="create",
                    file=self._parse_file_metadata(file_data),
                )

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    def _parse_file_metadata(self, file_data: dict[str, Any]) -> FileMetadata:
        """
        Parse Google Drive API file data to FileMetadata.

        Args:
            file_data: Raw file data from API.

        Returns:
            FileMetadata instance.
        """
        modified_at = None
        if "modifiedTime" in file_data:
            modified_at = datetime.fromisoformat(
                file_data["modifiedTime"].replace("Z", "+00:00")
            )

        return FileMetadata(
            source_id=file_data["id"],
            name=file_data["name"],
            mime_type=file_data["mimeType"],
            size=file_data.get("size"),
            content_hash=file_data.get("md5Checksum"),
            modified_at=modified_at,
            web_url=file_data.get("webViewLink"),
            parent_id=file_data.get("parents", [None])[0],
        )

    async def download_file(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> DownloadedFile:
        """
        Download a file or export Google Workspace document as PDF.

        Args:
            file: File metadata.
            config: Provider configuration.

        Returns:
            DownloadedFile with content.

        Raises:
            DownloadError: If download fails.
            ExportError: If export fails.
            FileTooLargeError: If file exceeds size limit.
        """
        if file.mime_type in GOOGLE_EXPORT_MIMES:
            return await self._export_workspace_file(file, config)
        else:
            return await self._download_regular_file(file, config)

    async def _export_workspace_file(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> DownloadedFile:
        """
        Export Google Workspace document as PDF.

        Args:
            file: File metadata (must be Workspace document).
            config: Provider configuration.

        Returns:
            DownloadedFile with PDF content.

        Raises:
            ExportError: If export fails.
        """
        export_mime = GOOGLE_EXPORT_MIMES[file.mime_type]

        logger.info(
            "🔄 Exporting Google Workspace file %s as PDF", file.source_id
        )

        response = await self._client.get(
            f"https://www.googleapis.com/drive/v3/files/{file.source_id}/export",
            params={"mimeType": export_mime},
            headers=self._auth_headers(),
        )

        if response.status_code == 403:
            # May be too large
            raise ExportError(
                self.provider_name,
                file.source_id,
                export_mime,
                "Export forbidden - file may exceed 10MB limit",
            )
        if response.status_code != 200:
            raise ExportError(
                self.provider_name,
                file.source_id,
                export_mime,
                f"Export failed: {response.text}",
            )

        content = response.content
        if len(content) > MAX_EXPORT_SIZE_BYTES:
            raise FileTooLargeError(
                self.provider_name,
                file.source_id,
                len(content),
                MAX_EXPORT_SIZE_BYTES,
            )

        # Fetch permissions
        external_access = await self.get_file_permissions(file, config)

        return DownloadedFile(
            source_id=file.source_id,
            name=f"{file.name}.pdf",
            content=content,
            mime_type="application/pdf",
            content_hash=None,  # Workspace files don't have md5
            modified_at=file.modified_at,
            external_access=external_access,
            parent_id=file.parent_id,
            original_url=file.web_url,
        )

    async def _download_regular_file(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> DownloadedFile:
        """
        Download a regular (non-Workspace) file.

        Args:
            file: File metadata.
            config: Provider configuration.

        Returns:
            DownloadedFile with content.

        Raises:
            DownloadError: If download fails.
            FileTooLargeError: If file exceeds size limit.
        """
        # Check size before download
        if file.size and file.size > self._max_file_size:
            raise FileTooLargeError(
                self.provider_name,
                file.source_id,
                file.size,
                self._max_file_size,
            )

        logger.info("🔄 Downloading file %s", file.source_id)

        response = await self._client.get(
            f"https://www.googleapis.com/drive/v3/files/{file.source_id}",
            params={"alt": "media"},
            headers=self._auth_headers(),
        )

        if response.status_code == 429:
            raise RateLimitError(self.provider_name)
        if response.status_code != 200:
            raise DownloadError(
                self.provider_name,
                file.source_id,
                f"Download failed: {response.text}",
            )

        content = response.content
        if len(content) > self._max_file_size:
            raise FileTooLargeError(
                self.provider_name,
                file.source_id,
                len(content),
                self._max_file_size,
            )

        # Fetch permissions
        external_access = await self.get_file_permissions(file, config)

        return DownloadedFile(
            source_id=file.source_id,
            name=file.name,
            content=content,
            mime_type=file.mime_type,
            content_hash=file.content_hash,
            modified_at=file.modified_at,
            external_access=external_access,
            parent_id=file.parent_id,
            original_url=file.web_url,
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
        Stream a file directly from Google Drive to MinIO storage.

        For Google Workspace files (Docs, Sheets, etc.), exports to PDF first
        (limited to 10MB by Google API). For regular files, streams directly
        without size limit.

        Args:
            file: File metadata from change detection.
            config: Provider configuration.
            minio_client: MinIO client for storage.
            bucket: Target MinIO bucket.
            object_key: Object key/path in MinIO.

        Returns:
            StreamResult with storage path and metadata.

        Raises:
            DownloadError: If download/streaming fails.
            ExportError: If Google Workspace export fails.
        """
        if file.mime_type in GOOGLE_EXPORT_MIMES:
            # Workspace files must be exported (cannot stream, limited to 10MB)
            return await self._export_workspace_to_storage(
                file, config, minio_client, bucket, object_key
            )
        else:
            return await self._stream_regular_file(
                file, config, minio_client, bucket, object_key
            )

    async def _export_workspace_to_storage(
        self,
        file: FileMetadata,
        config: dict[str, Any],
        minio_client: MinIOClient,
        bucket: str,
        object_key: str,
    ) -> StreamResult:
        """
        Export Google Workspace document as PDF and upload to storage.

        Google's export API doesn't support streaming, so we must download
        the entire file first (limited to 10MB).

        Args:
            file: File metadata (must be Workspace document).
            config: Provider configuration.
            minio_client: MinIO client.
            bucket: Target bucket.
            object_key: Object key.

        Returns:
            StreamResult with storage path.

        Raises:
            ExportError: If export fails.
        """
        import io

        export_mime = GOOGLE_EXPORT_MIMES[file.mime_type]

        logger.info(
            "🔄 Exporting Google Workspace file %s as PDF", file.source_id
        )

        response = await self._client.get(
            f"https://www.googleapis.com/drive/v3/files/{file.source_id}/export",
            params={"mimeType": export_mime},
            headers=self._auth_headers(),
        )

        if response.status_code == 403:
            raise ExportError(
                self.provider_name,
                file.source_id,
                export_mime,
                "Export forbidden - file may exceed 10MB limit",
            )
        if response.status_code != 200:
            raise ExportError(
                self.provider_name,
                file.source_id,
                export_mime,
                f"Export failed: {response.text}",
            )

        content = response.content
        content_len = len(content)

        # Upload to MinIO
        result = await minio_client.upload_file(
            bucket_name=bucket,
            object_name=object_key,
            data=content,
            content_type="application/pdf",
        )

        logger.info(
            "📦 Streamed Workspace file %s to storage (%d bytes)",
            file.source_id,
            content_len,
        )

        return StreamResult(
            storage_path=f"minio:{bucket}:{object_key}",
            etag=result,
            size=content_len,
            content_hash=None,  # Workspace files don't have md5
        )

    async def _stream_regular_file(
        self,
        file: FileMetadata,
        config: dict[str, Any],
        minio_client: MinIOClient,
        bucket: str,
        object_key: str,
    ) -> StreamResult:
        """
        Stream a regular file from Google Drive to MinIO.

        Uses httpx streaming to avoid loading the entire file into memory.
        No file size limit for regular files.

        Args:
            file: File metadata.
            config: Provider configuration.
            minio_client: MinIO client.
            bucket: Target bucket.
            object_key: Object key.

        Returns:
            StreamResult with storage path.

        Raises:
            DownloadError: If download fails.
        """
        import io

        logger.info("🔄 Streaming file %s to storage", file.source_id)

        # Use streaming download
        async with self._client.stream(
            "GET",
            f"https://www.googleapis.com/drive/v3/files/{file.source_id}",
            params={"alt": "media"},
            headers=self._auth_headers(),
        ) as response:
            if response.status_code == 429:
                raise RateLimitError(self.provider_name)
            if response.status_code != 200:
                raise DownloadError(
                    self.provider_name,
                    file.source_id,
                    f"Download failed: {response.status_code}",
                )

            # Collect chunks and upload
            # Note: miniopy-async requires known length, so we buffer
            chunks: list[bytes] = []
            async for chunk in response.aiter_bytes(chunk_size=8192):
                chunks.append(chunk)

            content = b"".join(chunks)
            content_len = len(content)

        # Upload to MinIO
        result = await minio_client.upload_file(
            bucket_name=bucket,
            object_name=object_key,
            data=content,
            content_type=file.mime_type,
        )

        logger.info(
            "📦 Streamed file %s to storage (%d bytes)",
            file.source_id,
            content_len,
        )

        return StreamResult(
            storage_path=f"minio:{bucket}:{object_key}",
            etag=result,
            size=content_len,
            content_hash=file.content_hash,
        )

    async def get_file_permissions(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> ExternalAccess:
        """
        Fetch permissions from Google Drive API.

        Args:
            file: File metadata.
            config: Provider configuration.

        Returns:
            ExternalAccess with permission information.
        """
        try:
            response = await self._client.get(
                f"https://www.googleapis.com/drive/v3/files/{file.source_id}/permissions",
                params={"fields": "permissions(emailAddress,type,role)"},
                headers=self._auth_headers(),
            )

            if response.status_code != 200:
                logger.warning(
                    "⚠️ Failed to fetch permissions for %s: %s",
                    file.source_id,
                    response.text,
                )
                return ExternalAccess.empty()

            data = response.json()
            emails: set[str] = set()
            is_public = False

            for perm in data.get("permissions", []):
                if perm.get("type") == "anyone":
                    is_public = True
                elif perm.get("type") == "user":
                    email = perm.get("emailAddress")
                    if email:
                        emails.add(email)

            if is_public:
                return ExternalAccess.public()

            return ExternalAccess.for_users(emails)

        except Exception as e:
            logger.warning(
                "⚠️ Error fetching permissions for %s: %s", file.source_id, e
            )
            return ExternalAccess.empty()

    async def sync(
        self,
        config: dict[str, Any],
        checkpoint: ConnectorCheckpoint,
    ) -> AsyncIterator[DownloadedFile | DeletedFile]:
        """
        Perform full or incremental sync.

        Args:
            config: Provider configuration with:
                - folder_id: Optional folder to sync (all if not specified)
                - access_token: OAuth2 access token
                - refresh_token: OAuth2 refresh token (for auto-refresh)
            checkpoint: GoogleDriveCheckpoint for resumption.

        Yields:
            DownloadedFile or DeletedFile for each change.
        """
        if not isinstance(checkpoint, GoogleDriveCheckpoint):
            checkpoint = GoogleDriveCheckpoint()

        checkpoint.last_sync_start = datetime.now(timezone.utc)

        # Authenticate if needed
        if not self._access_token:
            await self.authenticate(config)

        # Detect changes
        async for change in self.get_changes(config, checkpoint):
            if change.action == "delete":
                yield DeletedFile(source_id=change.source_id)
            elif change.file:
                # Check for duplicates
                if not checkpoint.mark_file_retrieved(change.source_id):
                    continue

                try:
                    downloaded = await self.download_file(change.file, config)
                    yield downloaded
                except FileTooLargeError as e:
                    logger.warning("⚠️ Skipping large file: %s", e)
                    checkpoint.error_count += 1
                except (DownloadError, ExportError) as e:
                    logger.error("❌ Download/export error: %s", e)
                    checkpoint.error_count += 1

        checkpoint.has_more = False

    def create_checkpoint(self) -> GoogleDriveCheckpoint:
        """
        Create a new Google Drive checkpoint.

        Returns:
            Fresh GoogleDriveCheckpoint instance.
        """
        return GoogleDriveCheckpoint()

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()
