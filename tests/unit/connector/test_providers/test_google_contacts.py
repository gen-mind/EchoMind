"""Unit tests for Google Contacts provider."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from connector.logic.checkpoint import GoogleContactsCheckpoint
from connector.logic.exceptions import (
    AuthenticationError,
    DownloadError,
    RateLimitError,
)
from connector.logic.providers.base import FileMetadata
from connector.logic.providers.google_contacts import GoogleContactsProvider


class TestGoogleContactsProvider:
    """Tests for GoogleContactsProvider."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GoogleContactsProvider:
        """Create a provider with mock client."""
        return GoogleContactsProvider(http_client=mock_client)

    def test_provider_name(self, provider: GoogleContactsProvider) -> None:
        """Test provider name is google_contacts."""
        assert provider.provider_name == "google_contacts"

    def test_create_checkpoint(self, provider: GoogleContactsProvider) -> None:
        """Test creating a new checkpoint."""
        checkpoint = provider.create_checkpoint()
        assert isinstance(checkpoint, GoogleContactsCheckpoint)
        assert checkpoint.sync_token is None
        assert checkpoint.page_token is None


class TestContactsAuthentication:
    """Tests for Contacts authentication."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GoogleContactsProvider:
        """Create a provider with mock client."""
        return GoogleContactsProvider(http_client=mock_client)

    @pytest.mark.asyncio
    async def test_authenticate_success(
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test successful authentication."""
        config = {"access_token": "valid_token"}
        await provider.authenticate(config)
        assert provider._auth.access_token == "valid_token"

    @pytest.mark.asyncio
    async def test_authenticate_missing_token(
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test authentication fails without access_token."""
        with pytest.raises(AuthenticationError):
            await provider.authenticate({})

    @pytest.mark.asyncio
    async def test_check_connection_success(
        self, provider: GoogleContactsProvider, mock_client: AsyncMock
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
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test connection check without token."""
        result = await provider.check_connection()
        assert result is False


class TestContactsGetChanges:
    """Tests for Contacts get_changes."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GoogleContactsProvider:
        """Create provider with mock client and auth."""
        p = GoogleContactsProvider(http_client=mock_client)
        p._auth._access_token = "test_token"
        return p

    @pytest.mark.asyncio
    async def test_initial_sync(
        self, provider: GoogleContactsProvider, mock_client: AsyncMock
    ) -> None:
        """Test initial sync lists contacts."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "connections": [
                {
                    "resourceName": "people/c123",
                    "names": [{"displayName": "Alice"}],
                    "metadata": {},
                    "etag": "etag1",
                },
                {
                    "resourceName": "people/c456",
                    "names": [{"displayName": "Bob"}],
                    "metadata": {},
                    "etag": "etag2",
                },
            ],
            "nextSyncToken": "sync_tok_1",
        }
        mock_client.get.return_value = response

        checkpoint = GoogleContactsCheckpoint()
        changes = []
        async for change in provider.get_changes({}, checkpoint):
            changes.append(change)

        assert len(changes) == 2
        assert changes[0].source_id == "people/c123"
        assert changes[0].file is not None
        assert changes[0].file.name == "alice.md"
        assert checkpoint.sync_token == "sync_tok_1"

    @pytest.mark.asyncio
    async def test_deleted_contact(
        self, provider: GoogleContactsProvider, mock_client: AsyncMock
    ) -> None:
        """Test deleted contact yields delete change."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "connections": [
                {
                    "resourceName": "people/c789",
                    "metadata": {"deleted": True},
                },
            ],
            "nextSyncToken": "sync_tok_2",
        }
        mock_client.get.return_value = response

        checkpoint = GoogleContactsCheckpoint(sync_token="old_token")
        changes = []
        async for change in provider.get_changes({}, checkpoint):
            changes.append(change)

        assert len(changes) == 1
        assert changes[0].action == "delete"
        assert changes[0].source_id == "people/c789"

    @pytest.mark.asyncio
    async def test_sync_token_expired(
        self, provider: GoogleContactsProvider, mock_client: AsyncMock
    ) -> None:
        """Test 410 GONE triggers full resync."""
        # First call returns 410 (expired syncToken)
        gone_response = MagicMock()
        gone_response.status_code = 410
        gone_response.text = "Sync token expired"

        # Second call (full resync) returns contacts
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "connections": [
                {
                    "resourceName": "people/c123",
                    "names": [{"displayName": "Alice"}],
                    "metadata": {},
                },
            ],
            "nextSyncToken": "new_sync_tok",
        }

        mock_client.get.side_effect = [gone_response, success_response]

        checkpoint = GoogleContactsCheckpoint(sync_token="expired_token")
        changes = []
        async for change in provider.get_changes({}, checkpoint):
            changes.append(change)

        assert len(changes) == 1
        assert checkpoint.sync_token == "new_sync_tok"


class TestContactsDownloadFile:
    """Tests for Contacts download_file."""

    @pytest.fixture
    def provider(self) -> GoogleContactsProvider:
        """Create provider."""
        return GoogleContactsProvider(
            http_client=AsyncMock(spec=httpx.AsyncClient)
        )

    @pytest.mark.asyncio
    async def test_download_file_success(
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test successful contact conversion."""
        person_data = {
            "names": [{"displayName": "Alice Johnson"}],
            "emailAddresses": [{"value": "alice@test.com"}],
            "phoneNumbers": [{"value": "+1-555-123"}],
        }

        file = FileMetadata(
            source_id="people/c123",
            name="alice-johnson.md",
            mime_type="text/markdown",
            extra={"person_data": person_data},
        )

        downloaded = await provider.download_file(
            file, {"user_email": "user@test.com"}
        )

        assert downloaded.source_id == "people/c123"
        assert downloaded.mime_type == "text/markdown"
        assert b"Alice Johnson" in downloaded.content
        assert b"alice@test.com" in downloaded.content

    @pytest.mark.asyncio
    async def test_download_file_no_person_data(
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test download_file fails without person data."""
        file = FileMetadata(
            source_id="people/c123",
            name="test.md",
            mime_type="text/markdown",
        )

        with pytest.raises(DownloadError):
            await provider.download_file(file, {})


class TestContactsGetFilePermissions:
    """Tests for Contacts permissions."""

    @pytest.fixture
    def provider(self) -> GoogleContactsProvider:
        """Create provider."""
        return GoogleContactsProvider(
            http_client=AsyncMock(spec=httpx.AsyncClient)
        )

    @pytest.mark.asyncio
    async def test_permissions_with_email(
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test permissions return user email."""
        file = FileMetadata(source_id="p/c1", name="c1", mime_type="text/markdown")
        access = await provider.get_file_permissions(
            file, {"user_email": "user@test.com"}
        )
        assert "user@test.com" in access.external_user_emails

    @pytest.mark.asyncio
    async def test_permissions_without_email(
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test permissions without email returns empty."""
        file = FileMetadata(source_id="p/c1", name="c1", mime_type="text/markdown")
        access = await provider.get_file_permissions(file, {})
        assert len(access.external_user_emails) == 0


class TestContactsStreamToStorage:
    """Tests for Contacts stream_to_storage."""

    @pytest.fixture
    def provider(self) -> GoogleContactsProvider:
        """Create provider."""
        return GoogleContactsProvider(
            http_client=AsyncMock(spec=httpx.AsyncClient)
        )

    @pytest.mark.asyncio
    async def test_stream_to_storage_success(
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test streaming contact to MinIO storage."""
        person_data = {
            "names": [{"displayName": "Alice"}],
            "emailAddresses": [{"value": "alice@test.com"}],
        }

        mock_minio = AsyncMock()
        mock_minio.upload_file.return_value = "etag123"

        file = FileMetadata(
            source_id="people/c123",
            name="alice.md",
            mime_type="text/markdown",
            extra={"person_data": person_data},
        )

        result = await provider.stream_to_storage(
            file, {}, mock_minio, "bucket", "key/alice.md"
        )

        assert result.storage_path == "minio:bucket:key/alice.md"
        assert result.etag == "etag123"
        mock_minio.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_to_storage_no_person_data(
        self, provider: GoogleContactsProvider
    ) -> None:
        """Test stream_to_storage fails without person data."""
        file = FileMetadata(
            source_id="people/c123",
            name="test.md",
            mime_type="text/markdown",
        )

        with pytest.raises(DownloadError):
            await provider.stream_to_storage(
                file, {}, AsyncMock(), "bucket", "key"
            )


class TestContactsClose:
    """Tests for provider cleanup."""

    @pytest.mark.asyncio
    async def test_close_owned_client(self) -> None:
        """Test close when client is owned."""
        provider = GoogleContactsProvider()
        provider._client = AsyncMock()
        provider._owns_client = True
        await provider.close()
        provider._client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_external_client(self) -> None:
        """Test close when client is external."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        provider = GoogleContactsProvider(http_client=mock_client)
        await provider.close()
        mock_client.aclose.assert_not_called()
