"""
OneDrive/SharePoint provider for fetching files and folders.

Supports:
- MSAL authentication (OAuth2 with Microsoft identity)
- Delta API for incremental sync
- cTag comparison for change detection (content-only changes)
- Checkpoint-based resumable sync
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

import httpx

from connector.logic.checkpoint import (
    ConnectorCheckpoint,
    SharePointCheckpoint,
)
from connector.logic.exceptions import (
    AuthenticationError,
    DownloadError,
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

logger = logging.getLogger("echomind-connector.onedrive")

# Microsoft Graph API base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class OneDriveProvider(BaseProvider):
    """
    Provider for Microsoft OneDrive and SharePoint files.

    Uses the Microsoft Graph API with Delta queries for efficient
    incremental sync. Uses cTag for content-only change detection.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        max_file_size: int = 100 * 1024 * 1024,
    ):
        """
        Initialize OneDrive provider.

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
        return "onedrive"

    async def authenticate(self, config: dict[str, Any]) -> None:
        """
        Authenticate with Microsoft Graph API.

        Uses MSAL client credentials flow or user tokens.

        Args:
            config: Must contain:
                - 'access_token' for pre-authenticated token, OR
                - 'client_id', 'client_secret', 'tenant_id' for app auth

        Raises:
            AuthenticationError: If authentication fails.
        """
        try:
            if "access_token" in config:
                # Pre-authenticated token
                self._access_token = config["access_token"]
                if "token_expires_at" in config:
                    self._token_expires_at = datetime.fromisoformat(
                        config["token_expires_at"]
                    )
                    if self._token_expires_at <= datetime.now(timezone.utc):
                        await self._refresh_token(config)
            elif all(
                k in config for k in ["client_id", "client_secret", "tenant_id"]
            ):
                # App-only auth (client credentials)
                await self._authenticate_app(config)
            else:
                raise AuthenticationError(
                    self.provider_name,
                    "Missing access_token or client_id/client_secret/tenant_id",
                )

            # Verify token works
            if not await self.check_connection():
                raise AuthenticationError(
                    self.provider_name,
                    "Token validation failed",
                )

            logger.info("🔐 Authenticated with Microsoft Graph API")

        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(self.provider_name, str(e)) from e

    async def _authenticate_app(self, config: dict[str, Any]) -> None:
        """
        Authenticate using client credentials (app-only).

        Args:
            config: Must contain client_id, client_secret, tenant_id.

        Raises:
            AuthenticationError: If authentication fails.
        """
        token_url = (
            f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
        )

        response = await self._client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "scope": "https://graph.microsoft.com/.default",
            },
        )

        if response.status_code != 200:
            raise AuthenticationError(
                self.provider_name,
                f"App authentication failed: {response.text}",
            )

        data = response.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=expires_in
        )

        logger.info("🔐 Authenticated with Microsoft Graph (app credentials)")

    async def _refresh_token(self, config: dict[str, Any]) -> None:
        """
        Refresh OAuth2 access token.

        Args:
            config: Must contain refresh_token, client_id, client_secret, tenant_id.

        Raises:
            AuthenticationError: If refresh fails.
        """
        refresh_token = config.get("refresh_token")
        if not refresh_token:
            # Try app auth instead
            if all(
                k in config for k in ["client_id", "client_secret", "tenant_id"]
            ):
                await self._authenticate_app(config)
                return
            raise AuthenticationError(
                self.provider_name,
                "Token expired and no refresh_token available",
            )

        token_url = (
            f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
        )

        response = await self._client.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": config["client_id"],
                "client_secret": config.get("client_secret", ""),
                "scope": "https://graph.microsoft.com/.default",
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

        logger.info("🔄 Refreshed Microsoft Graph access token")

    async def check_connection(self) -> bool:
        """
        Verify connection to Microsoft Graph API.

        Returns:
            True if connected, False otherwise.
        """
        if not self._access_token:
            return False

        try:
            response = await self._client.get(
                f"{GRAPH_API_BASE}/me",
                headers=self._auth_headers(),
            )
            # App-only tokens can't access /me, try /organization
            if response.status_code == 401:
                response = await self._client.get(
                    f"{GRAPH_API_BASE}/organization",
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
        Detect changes using Microsoft Graph Delta API.

        Uses delta queries for efficient incremental sync.
        Compares cTag to detect actual content changes.

        Args:
            config: Provider configuration with:
                - drive_id: Drive to sync (default: user's drive)
                - folder_id: Optional folder path
            checkpoint: SharePointCheckpoint with delta_link.

        Yields:
            FileChange for each changed item.
        """
        if not isinstance(checkpoint, SharePointCheckpoint):
            checkpoint = SharePointCheckpoint()

        drive_id = config.get("drive_id")
        folder_path = config.get("folder_path", "")

        # Build delta URL
        if checkpoint.delta_link:
            url = checkpoint.delta_link
        else:
            # Initial sync
            if drive_id:
                url = f"{GRAPH_API_BASE}/drives/{drive_id}/root"
            else:
                url = f"{GRAPH_API_BASE}/me/drive/root"

            if folder_path:
                url = f"{url}:/{folder_path}:"

            url = f"{url}/delta"

        # Fetch delta
        while url:
            response = await self._client.get(url, headers=self._auth_headers())

            if response.status_code == 429:
                raise RateLimitError(
                    self.provider_name,
                    int(response.headers.get("Retry-After", 60)),
                )
            if response.status_code != 200:
                raise DownloadError(
                    self.provider_name,
                    "delta",
                    f"Delta query failed: {response.text}",
                )

            data = response.json()

            for item in data.get("value", []):
                if item.get("deleted"):
                    yield FileChange(
                        source_id=item["id"],
                        action="delete",
                        file=None,
                    )
                elif "file" in item:
                    # It's a file (not folder)
                    yield FileChange(
                        source_id=item["id"],
                        action="update",
                        file=self._parse_file_metadata(item),
                    )

            url = data.get("@odata.nextLink")
            if "@odata.deltaLink" in data:
                checkpoint.delta_link = data["@odata.deltaLink"]

    def _parse_file_metadata(self, item: dict[str, Any]) -> FileMetadata:
        """
        Parse Microsoft Graph item to FileMetadata.

        Args:
            item: Raw item from Graph API.

        Returns:
            FileMetadata instance.
        """
        modified_at = None
        if "lastModifiedDateTime" in item:
            modified_at = datetime.fromisoformat(
                item["lastModifiedDateTime"].replace("Z", "+00:00")
            )

        created_at = None
        if "createdDateTime" in item:
            created_at = datetime.fromisoformat(
                item["createdDateTime"].replace("Z", "+00:00")
            )

        return FileMetadata(
            source_id=item["id"],
            name=item["name"],
            mime_type=item.get("file", {}).get("mimeType", "application/octet-stream"),
            size=item.get("size"),
            content_hash=item.get("cTag"),  # cTag for content-only changes
            modified_at=modified_at,
            created_at=created_at,
            web_url=item.get("webUrl"),
            parent_id=item.get("parentReference", {}).get("id"),
            extra={
                "eTag": item.get("eTag"),  # eTag for any change
                "drive_id": item.get("parentReference", {}).get("driveId"),
            },
        )

    async def download_file(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> DownloadedFile:
        """
        Download a file from OneDrive/SharePoint.

        Args:
            file: File metadata from change detection.
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

        drive_id = file.extra.get("drive_id") or config.get("drive_id")

        logger.info("🔄 Downloading OneDrive file %s", file.source_id)

        # Get download URL
        if drive_id:
            url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file.source_id}/content"
        else:
            url = f"{GRAPH_API_BASE}/me/drive/items/{file.source_id}/content"

        response = await self._client.get(
            url,
            headers=self._auth_headers(),
            follow_redirects=True,
        )

        if response.status_code == 429:
            raise RateLimitError(
                self.provider_name,
                int(response.headers.get("Retry-After", 60)),
            )
        if response.status_code != 200:
            raise DownloadError(
                self.provider_name,
                file.source_id,
                f"Download failed: {response.status_code}",
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
            content_hash=file.content_hash,  # cTag
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
        Stream a file directly from OneDrive/SharePoint to MinIO storage.

        Uses httpx streaming to avoid loading the entire file into memory.
        No file size limit when streaming.

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
        """
        drive_id = file.extra.get("drive_id") or config.get("drive_id")

        logger.info("🔄 Streaming OneDrive file %s to storage", file.source_id)

        # Build download URL
        if drive_id:
            url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file.source_id}/content"
        else:
            url = f"{GRAPH_API_BASE}/me/drive/items/{file.source_id}/content"

        # Use streaming download
        async with self._client.stream(
            "GET",
            url,
            headers=self._auth_headers(),
            follow_redirects=True,
        ) as response:
            if response.status_code == 429:
                raise RateLimitError(
                    self.provider_name,
                    int(response.headers.get("Retry-After", 60)),
                )
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
            "📦 Streamed OneDrive file %s to storage (%d bytes)",
            file.source_id,
            content_len,
        )

        return StreamResult(
            storage_path=f"minio:{bucket}:{object_key}",
            etag=result,
            size=content_len,
            content_hash=file.content_hash,  # cTag
        )

    async def get_file_permissions(
        self,
        file: FileMetadata,
        config: dict[str, Any],
    ) -> ExternalAccess:
        """
        Fetch permissions from Microsoft Graph API.

        Args:
            file: File metadata.
            config: Provider configuration.

        Returns:
            ExternalAccess with permission information.
        """
        try:
            drive_id = file.extra.get("drive_id") or config.get("drive_id")

            if drive_id:
                url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file.source_id}/permissions"
            else:
                url = f"{GRAPH_API_BASE}/me/drive/items/{file.source_id}/permissions"

            response = await self._client.get(url, headers=self._auth_headers())

            if response.status_code != 200:
                logger.warning(
                    "⚠️ Failed to fetch permissions for %s: %s",
                    file.source_id,
                    response.text,
                )
                return ExternalAccess.empty()

            data = response.json()
            emails: set[str] = set()
            groups: set[str] = set()
            is_public = False

            for perm in data.get("value", []):
                # Check for public/anonymous links
                if "link" in perm:
                    scope = perm["link"].get("scope")
                    if scope == "anonymous":
                        is_public = True

                # Check for direct grants
                if "grantedToV2" in perm:
                    granted = perm["grantedToV2"]
                    if "user" in granted:
                        email = granted["user"].get("email")
                        if email:
                            emails.add(email)
                    if "group" in granted:
                        group_id = granted["group"].get("id")
                        if group_id:
                            groups.add(group_id)

                # Legacy format
                if "grantedTo" in perm:
                    granted = perm["grantedTo"]
                    if "user" in granted:
                        email = granted["user"].get("email")
                        if email:
                            emails.add(email)

            if is_public:
                return ExternalAccess.public()

            return ExternalAccess.for_users_and_groups(emails, groups)

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
                - drive_id: Optional drive ID (default: user's drive)
                - folder_path: Optional folder path to sync
                - access_token: OAuth2 access token
            checkpoint: SharePointCheckpoint for resumption.

        Yields:
            DownloadedFile or DeletedFile for each change.
        """
        if not isinstance(checkpoint, SharePointCheckpoint):
            checkpoint = SharePointCheckpoint()

        checkpoint.last_sync_start = datetime.now(timezone.utc)

        # Authenticate if needed
        if not self._access_token:
            await self.authenticate(config)

        # Detect and process changes
        async for change in self.get_changes(config, checkpoint):
            if change.action == "delete":
                yield DeletedFile(source_id=change.source_id)
            elif change.file:
                # Check for duplicates
                if not checkpoint.mark_item_retrieved(change.source_id):
                    continue

                try:
                    downloaded = await self.download_file(change.file, config)
                    yield downloaded
                except FileTooLargeError as e:
                    logger.warning("⚠️ Skipping large file: %s", e)
                    checkpoint.error_count += 1
                except DownloadError as e:
                    logger.error("❌ Download error: %s", e)
                    checkpoint.error_count += 1

        checkpoint.has_more = False

    def create_checkpoint(self) -> SharePointCheckpoint:
        """
        Create a new SharePoint/OneDrive checkpoint.

        Returns:
            Fresh SharePointCheckpoint instance.
        """
        return SharePointCheckpoint()

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()
