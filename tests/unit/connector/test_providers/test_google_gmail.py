"""Unit tests for Gmail provider."""

import base64
import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from connector.logic.checkpoint import GmailCheckpoint
from connector.logic.exceptions import (
    AuthenticationError,
    DownloadError,
    RateLimitError,
)
from connector.logic.providers.base import FileMetadata
from connector.logic.providers.google_gmail import GmailProvider


class TestGmailProvider:
    """Tests for GmailProvider."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GmailProvider:
        """Create a provider with mock client."""
        return GmailProvider(http_client=mock_client)

    def test_provider_name(self, provider: GmailProvider) -> None:
        """Test provider name is gmail."""
        assert provider.provider_name == "gmail"

    def test_create_checkpoint(self, provider: GmailProvider) -> None:
        """Test creating a new checkpoint."""
        checkpoint = provider.create_checkpoint()
        assert isinstance(checkpoint, GmailCheckpoint)
        assert checkpoint.history_id is None
        assert checkpoint.page_token is None


class TestGmailAuthentication:
    """Tests for Gmail authentication."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GmailProvider:
        """Create a provider with mock client."""
        return GmailProvider(http_client=mock_client)

    @pytest.mark.asyncio
    async def test_authenticate_success(
        self, provider: GmailProvider
    ) -> None:
        """Test successful authentication."""
        config = {"access_token": "valid_token"}
        await provider.authenticate(config)
        assert provider._auth.access_token == "valid_token"

    @pytest.mark.asyncio
    async def test_authenticate_missing_token(
        self, provider: GmailProvider
    ) -> None:
        """Test authentication fails without access_token."""
        with pytest.raises(AuthenticationError):
            await provider.authenticate({})

    @pytest.mark.asyncio
    async def test_check_connection_success(
        self, provider: GmailProvider, mock_client: AsyncMock
    ) -> None:
        """Test connection check success."""
        provider._auth._access_token = "valid_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response

        result = await provider.check_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_check_connection_no_token(
        self, provider: GmailProvider
    ) -> None:
        """Test connection check without token."""
        result = await provider.check_connection()
        assert result is False


class TestGmailDownloadFile:
    """Tests for Gmail download_file."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GmailProvider:
        """Create provider with mock client and auth."""
        p = GmailProvider(http_client=mock_client)
        p._auth._access_token = "test_token"
        return p

    @pytest.mark.asyncio
    async def test_download_file_success(
        self, provider: GmailProvider, mock_client: AsyncMock
    ) -> None:
        """Test successful thread download and conversion."""
        body_b64 = base64.urlsafe_b64encode(b"Hello World").decode()
        thread_data = {
            "id": "thread123",
            "messages": [
                {
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [
                            {"name": "Subject", "value": "Test Email"},
                            {"name": "From", "value": "alice@test.com"},
                        ],
                        "body": {"data": body_b64},
                    }
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = thread_data
        mock_client.get.return_value = mock_response

        file = FileMetadata(
            source_id="thread123",
            name="thread123",
            mime_type="text/markdown",
        )
        config = {"user_email": "user@test.com"}

        downloaded = await provider.download_file(file, config)

        assert downloaded.source_id == "thread123"
        assert downloaded.mime_type == "text/markdown"
        assert b"Test Email" in downloaded.content
        assert b"Hello World" in downloaded.content
        assert downloaded.name.endswith(".md")

    @pytest.mark.asyncio
    async def test_download_file_rate_limited(
        self, provider: GmailProvider, mock_client: AsyncMock
    ) -> None:
        """Test rate limit during thread fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "1"}
        mock_response.text = ""
        mock_client.get.return_value = mock_response

        file = FileMetadata(
            source_id="thread123",
            name="thread123",
            mime_type="text/markdown",
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RateLimitError):
                await provider.download_file(file, {})


class TestGmailGetChanges:
    """Tests for Gmail get_changes (initial and incremental)."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GmailProvider:
        """Create provider with mock client and auth."""
        p = GmailProvider(http_client=mock_client)
        p._auth._access_token = "test_token"
        return p

    @pytest.mark.asyncio
    async def test_initial_sync_lists_threads(
        self, provider: GmailProvider, mock_client: AsyncMock
    ) -> None:
        """Test initial sync lists all threads."""
        # Profile response (for historyId)
        profile_response = MagicMock()
        profile_response.status_code = 200
        profile_response.json.return_value = {
            "emailAddress": "user@test.com",
            "historyId": "12345",
        }

        # Thread list response
        threads_response = MagicMock()
        threads_response.status_code = 200
        threads_response.json.return_value = {
            "threads": [
                {"id": "thread1", "snippet": "Hello"},
                {"id": "thread2", "snippet": "World"},
            ],
        }

        mock_client.get.side_effect = [profile_response, threads_response]

        checkpoint = GmailCheckpoint()
        changes = []
        async for change in provider.get_changes({}, checkpoint):
            changes.append(change)

        assert len(changes) == 2
        assert changes[0].source_id == "thread1"
        assert changes[1].source_id == "thread2"
        assert checkpoint.history_id == "12345"

    @pytest.mark.asyncio
    async def test_incremental_sync_uses_history(
        self, provider: GmailProvider, mock_client: AsyncMock
    ) -> None:
        """Test incremental sync uses history API."""
        history_response = MagicMock()
        history_response.status_code = 200
        history_response.json.return_value = {
            "history": [
                {
                    "messagesAdded": [
                        {"message": {"threadId": "thread_new"}},
                    ],
                },
            ],
            "historyId": "12346",
        }

        mock_client.get.return_value = history_response

        checkpoint = GmailCheckpoint(history_id="12345")
        changes = []
        async for change in provider.get_changes({}, checkpoint):
            changes.append(change)

        assert len(changes) == 1
        assert changes[0].source_id == "thread_new"
        assert changes[0].action == "update"
        assert checkpoint.history_id == "12346"


class TestGmailGetFilePermissions:
    """Tests for Gmail permissions."""

    @pytest.fixture
    def provider(self) -> GmailProvider:
        """Create provider."""
        return GmailProvider(http_client=AsyncMock(spec=httpx.AsyncClient))

    @pytest.mark.asyncio
    async def test_permissions_with_email(self, provider: GmailProvider) -> None:
        """Test permissions return user email."""
        file = FileMetadata(source_id="t1", name="t1", mime_type="text/markdown")
        access = await provider.get_file_permissions(file, {"user_email": "user@test.com"})
        assert "user@test.com" in access.external_user_emails

    @pytest.mark.asyncio
    async def test_permissions_without_email(self, provider: GmailProvider) -> None:
        """Test permissions without email returns empty."""
        file = FileMetadata(source_id="t1", name="t1", mime_type="text/markdown")
        access = await provider.get_file_permissions(file, {})
        assert len(access.external_user_emails) == 0


class TestGmailStreamToStorage:
    """Tests for Gmail stream_to_storage."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GmailProvider:
        """Create provider with mock client and auth."""
        p = GmailProvider(http_client=mock_client)
        p._auth._access_token = "test_token"
        return p

    @pytest.mark.asyncio
    async def test_stream_to_storage_success(
        self, provider: GmailProvider, mock_client: AsyncMock
    ) -> None:
        """Test streaming thread to MinIO storage."""
        body_b64 = base64.urlsafe_b64encode(b"Email content").decode()
        thread_data = {
            "id": "thread1",
            "messages": [
                {
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [{"name": "Subject", "value": "Test"}],
                        "body": {"data": body_b64},
                    }
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = thread_data
        mock_client.get.return_value = mock_response

        mock_minio = AsyncMock()
        mock_minio.upload_file.return_value = "etag123"

        file = FileMetadata(source_id="thread1", name="test.md", mime_type="text/markdown")

        result = await provider.stream_to_storage(
            file, {}, mock_minio, "bucket", "key/thread1.md"
        )

        assert result.storage_path == "minio:bucket:key/thread1.md"
        assert result.etag == "etag123"
        assert result.size > 0
        mock_minio.upload_file.assert_called_once()


class TestGmailClose:
    """Tests for provider cleanup."""

    @pytest.mark.asyncio
    async def test_close_owned_client(self) -> None:
        """Test close when client is owned."""
        provider = GmailProvider()
        provider._client = AsyncMock()
        provider._owns_client = True
        await provider.close()
        provider._client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_external_client(self) -> None:
        """Test close when client is external."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        provider = GmailProvider(http_client=mock_client)
        await provider.close()
        mock_client.aclose.assert_not_called()
