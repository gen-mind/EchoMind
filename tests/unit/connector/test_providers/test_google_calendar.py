"""Unit tests for Google Calendar provider."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from connector.logic.checkpoint import GoogleCalendarCheckpoint
from connector.logic.exceptions import (
    AuthenticationError,
    DownloadError,
    RateLimitError,
)
from connector.logic.providers.base import FileMetadata
from connector.logic.providers.google_calendar import GoogleCalendarProvider


class TestGoogleCalendarProvider:
    """Tests for GoogleCalendarProvider."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GoogleCalendarProvider:
        """Create a provider with mock client."""
        return GoogleCalendarProvider(http_client=mock_client)

    def test_provider_name(self, provider: GoogleCalendarProvider) -> None:
        """Test provider name is google_calendar."""
        assert provider.provider_name == "google_calendar"

    def test_create_checkpoint(self, provider: GoogleCalendarProvider) -> None:
        """Test creating a new checkpoint."""
        checkpoint = provider.create_checkpoint()
        assert isinstance(checkpoint, GoogleCalendarCheckpoint)
        assert checkpoint.sync_tokens == {}
        assert checkpoint.calendar_ids is None
        assert checkpoint.current_calendar_idx == 0


class TestCalendarAuthentication:
    """Tests for Calendar authentication."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GoogleCalendarProvider:
        """Create a provider with mock client."""
        return GoogleCalendarProvider(http_client=mock_client)

    @pytest.mark.asyncio
    async def test_authenticate_success(
        self, provider: GoogleCalendarProvider
    ) -> None:
        """Test successful authentication."""
        config = {"access_token": "valid_token"}
        await provider.authenticate(config)
        assert provider._auth.access_token == "valid_token"

    @pytest.mark.asyncio
    async def test_authenticate_missing_token(
        self, provider: GoogleCalendarProvider
    ) -> None:
        """Test authentication fails without access_token."""
        with pytest.raises(AuthenticationError):
            await provider.authenticate({})

    @pytest.mark.asyncio
    async def test_check_connection_success(
        self, provider: GoogleCalendarProvider, mock_client: AsyncMock
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
        self, provider: GoogleCalendarProvider
    ) -> None:
        """Test connection check without token."""
        result = await provider.check_connection()
        assert result is False


class TestCalendarGetChanges:
    """Tests for Calendar get_changes."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def provider(self, mock_client: AsyncMock) -> GoogleCalendarProvider:
        """Create provider with mock client and auth."""
        p = GoogleCalendarProvider(http_client=mock_client)
        p._auth._access_token = "test_token"
        return p

    @pytest.mark.asyncio
    async def test_initial_sync(
        self, provider: GoogleCalendarProvider, mock_client: AsyncMock
    ) -> None:
        """Test initial sync discovers calendars and lists events."""
        # Calendar list response
        cal_list = MagicMock()
        cal_list.status_code = 200
        cal_list.json.return_value = {
            "items": [{"id": "primary"}],
        }

        # Events list response
        events = MagicMock()
        events.status_code = 200
        events.json.return_value = {
            "items": [
                {
                    "id": "event1",
                    "summary": "Meeting",
                    "start": {"dateTime": "2026-02-07T09:00:00Z"},
                    "status": "confirmed",
                    "etag": "etag1",
                },
            ],
            "nextSyncToken": "sync_token_1",
        }

        mock_client.get.side_effect = [cal_list, events]

        checkpoint = GoogleCalendarCheckpoint()
        changes = []
        async for change in provider.get_changes({}, checkpoint):
            changes.append(change)

        assert len(changes) == 1
        assert "event1" in changes[0].source_id
        assert changes[0].file is not None
        # Per-calendar syncToken stored in sync_tokens dict
        assert checkpoint.calendar_ids == ["primary"]
        assert checkpoint.sync_tokens == {"primary": "sync_token_1"}
        assert checkpoint.current_calendar_idx == 1

    @pytest.mark.asyncio
    async def test_cancelled_event_yields_delete(
        self, provider: GoogleCalendarProvider, mock_client: AsyncMock
    ) -> None:
        """Test cancelled events yield delete changes."""
        cal_list = MagicMock()
        cal_list.status_code = 200
        cal_list.json.return_value = {"items": [{"id": "primary"}]}

        events = MagicMock()
        events.status_code = 200
        events.json.return_value = {
            "items": [
                {"id": "event1", "status": "cancelled"},
            ],
            "nextSyncToken": "sync_token_2",
        }

        mock_client.get.side_effect = [cal_list, events]

        checkpoint = GoogleCalendarCheckpoint()
        changes = []
        async for change in provider.get_changes({}, checkpoint):
            changes.append(change)

        assert len(changes) == 1
        assert changes[0].action == "delete"


class TestCalendarDownloadFile:
    """Tests for Calendar download_file."""

    @pytest.fixture
    def provider(self) -> GoogleCalendarProvider:
        """Create provider."""
        return GoogleCalendarProvider(http_client=AsyncMock(spec=httpx.AsyncClient))

    @pytest.mark.asyncio
    async def test_download_file_success(self, provider: GoogleCalendarProvider) -> None:
        """Test successful event conversion."""
        event_data = {
            "summary": "Team Meeting",
            "start": {"dateTime": "2026-02-07T09:00:00Z"},
            "end": {"dateTime": "2026-02-07T10:00:00Z"},
            "organizer": {"email": "org@test.com"},
            "attendees": [{"email": "bob@test.com"}],
            "htmlLink": "https://calendar.google.com/event/123",
        }

        file = FileMetadata(
            source_id="gcal_primary_event1",
            name="team-meeting_2026-02-07.md",
            mime_type="text/markdown",
            extra={"event_data": event_data, "calendar_id": "primary"},
        )

        downloaded = await provider.download_file(file, {"user_email": "user@test.com"})

        assert downloaded.source_id == "gcal_primary_event1"
        assert downloaded.mime_type == "text/markdown"
        assert b"Team Meeting" in downloaded.content
        assert "bob@test.com" in downloaded.external_access.external_user_emails
        assert "user@test.com" in downloaded.external_access.external_user_emails

    @pytest.mark.asyncio
    async def test_download_file_no_event_data(
        self, provider: GoogleCalendarProvider
    ) -> None:
        """Test download_file fails without event data."""
        file = FileMetadata(
            source_id="gcal_primary_event1",
            name="test.md",
            mime_type="text/markdown",
        )

        with pytest.raises(DownloadError):
            await provider.download_file(file, {})


class TestCalendarGetFilePermissions:
    """Tests for Calendar permissions."""

    @pytest.fixture
    def provider(self) -> GoogleCalendarProvider:
        """Create provider."""
        return GoogleCalendarProvider(http_client=AsyncMock(spec=httpx.AsyncClient))

    @pytest.mark.asyncio
    async def test_permissions_with_attendees(
        self, provider: GoogleCalendarProvider
    ) -> None:
        """Test permissions include attendees."""
        file = FileMetadata(
            source_id="gcal_p_e1",
            name="test.md",
            mime_type="text/markdown",
            extra={
                "event_data": {
                    "attendees": [
                        {"email": "bob@test.com"},
                        {"email": "carol@test.com"},
                    ]
                }
            },
        )
        access = await provider.get_file_permissions(
            file, {"user_email": "alice@test.com"}
        )
        assert "alice@test.com" in access.external_user_emails
        assert "bob@test.com" in access.external_user_emails
        assert "carol@test.com" in access.external_user_emails


class TestCalendarStreamToStorage:
    """Tests for Calendar stream_to_storage."""

    @pytest.fixture
    def provider(self) -> GoogleCalendarProvider:
        """Create provider."""
        return GoogleCalendarProvider(http_client=AsyncMock(spec=httpx.AsyncClient))

    @pytest.mark.asyncio
    async def test_stream_to_storage_success(
        self, provider: GoogleCalendarProvider
    ) -> None:
        """Test streaming event to MinIO storage."""
        event_data = {
            "summary": "Test Event",
            "start": {"dateTime": "2026-02-07T09:00:00Z"},
        }

        mock_minio = AsyncMock()
        mock_minio.upload_file.return_value = "etag123"

        file = FileMetadata(
            source_id="gcal_p_e1",
            name="test.md",
            mime_type="text/markdown",
            extra={"event_data": event_data},
        )

        result = await provider.stream_to_storage(
            file, {}, mock_minio, "bucket", "key/event.md"
        )

        assert result.storage_path == "minio:bucket:key/event.md"
        assert result.etag == "etag123"
        mock_minio.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_to_storage_no_event_data(
        self, provider: GoogleCalendarProvider
    ) -> None:
        """Test stream_to_storage fails without event data."""
        file = FileMetadata(
            source_id="gcal_p_e1",
            name="test.md",
            mime_type="text/markdown",
        )

        with pytest.raises(DownloadError):
            await provider.stream_to_storage(
                file, {}, AsyncMock(), "bucket", "key"
            )


class TestCalendarClose:
    """Tests for provider cleanup."""

    @pytest.mark.asyncio
    async def test_close_owned_client(self) -> None:
        """Test close when client is owned."""
        provider = GoogleCalendarProvider()
        provider._client = AsyncMock()
        provider._owns_client = True
        await provider.close()
        provider._client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_external_client(self) -> None:
        """Test close when client is external."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        provider = GoogleCalendarProvider(http_client=mock_client)
        await provider.close()
        mock_client.aclose.assert_not_called()
