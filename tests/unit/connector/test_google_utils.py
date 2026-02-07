"""Unit tests for shared Google utilities."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from connector.logic.exceptions import (
    AuthenticationError,
    DownloadError,
    RateLimitError,
)
from connector.logic.providers.google_utils.auth import GoogleAuthHelper
from connector.logic.providers.google_utils.markdown import (
    calendar_event_to_markdown,
    contact_to_markdown,
    gmail_thread_to_markdown,
)
from connector.logic.providers.google_utils.pagination import (
    google_paginate,
)
from connector.logic.providers.google_utils.rate_limiter import (
    DEFAULT_RETRY_SECONDS,
    RETRY_BUFFER_SECONDS,
    _parse_retry_timestamp,
    handle_rate_limit,
)
from echomind_lib.google.scopes import (
    GOOGLE_SCOPES,
    all_scopes,
    scopes_for_service,
    service_has_scopes,
    services_authorized,
)


# =========================================================================
# GoogleAuthHelper tests
# =========================================================================


class TestGoogleAuthHelper:
    """Tests for GoogleAuthHelper."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def auth(self, mock_client: AsyncMock) -> GoogleAuthHelper:
        """Create auth helper with mock client."""
        return GoogleAuthHelper(mock_client)

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth: GoogleAuthHelper) -> None:
        """Test successful authentication."""
        config = {"access_token": "test_token"}
        await auth.authenticate(config)
        assert auth.access_token == "test_token"

    @pytest.mark.asyncio
    async def test_authenticate_missing_token(self, auth: GoogleAuthHelper) -> None:
        """Test authentication fails without access_token."""
        with pytest.raises(AuthenticationError):
            await auth.authenticate({})

    @pytest.mark.asyncio
    async def test_authenticate_with_expiry(self, auth: GoogleAuthHelper) -> None:
        """Test authentication with token expiry."""
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        config = {"access_token": "test_token", "token_expires_at": future}
        await auth.authenticate(config)
        assert auth.access_token == "test_token"
        assert auth.token_expires_at is not None

    @pytest.mark.asyncio
    async def test_authenticate_expired_token_refreshes(
        self, auth: GoogleAuthHelper, mock_client: AsyncMock
    ) -> None:
        """Test that expired token triggers refresh."""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_token",
            "expires_in": 3600,
        }
        mock_client.post.return_value = mock_response

        config = {
            "access_token": "expired_token",
            "token_expires_at": past,
            "refresh_token": "refresh_tok",
            "client_id": "client_id",
            "client_secret": "client_secret",
        }
        await auth.authenticate(config)
        assert auth.access_token == "refreshed_token"

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self, auth: GoogleAuthHelper, mock_client: AsyncMock
    ) -> None:
        """Test token refresh."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
        }
        mock_client.post.return_value = mock_response

        config = {
            "refresh_token": "refresh",
            "client_id": "cid",
            "client_secret": "csecret",
        }
        await auth.refresh_token(config)

        assert auth.access_token == "new_token"
        assert auth.token_expires_at is not None

    @pytest.mark.asyncio
    async def test_refresh_token_failure(
        self, auth: GoogleAuthHelper, mock_client: AsyncMock
    ) -> None:
        """Test token refresh failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "invalid_grant"
        mock_client.post.return_value = mock_response

        config = {
            "refresh_token": "bad_refresh",
            "client_id": "cid",
            "client_secret": "csecret",
        }
        with pytest.raises(AuthenticationError):
            await auth.refresh_token(config)

    @pytest.mark.asyncio
    async def test_refresh_token_missing_credentials(
        self, auth: GoogleAuthHelper
    ) -> None:
        """Test refresh fails without credentials."""
        with pytest.raises(AuthenticationError):
            await auth.refresh_token({})

    @pytest.mark.asyncio
    async def test_ensure_valid_token_not_expired(
        self, auth: GoogleAuthHelper
    ) -> None:
        """Test ensure_valid_token returns existing token when not expired."""
        auth._access_token = "valid_token"
        auth._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token = await auth.ensure_valid_token({})
        assert token == "valid_token"

    @pytest.mark.asyncio
    async def test_ensure_valid_token_no_token(
        self, auth: GoogleAuthHelper
    ) -> None:
        """Test ensure_valid_token raises when no token."""
        with pytest.raises(AuthenticationError):
            await auth.ensure_valid_token({})

    def test_auth_headers(self, auth: GoogleAuthHelper) -> None:
        """Test auth headers generation."""
        auth._access_token = "test_token"
        headers = auth.auth_headers()
        assert headers == {"Authorization": "Bearer test_token"}

    def test_auth_headers_no_token(self, auth: GoogleAuthHelper) -> None:
        """Test auth headers raises without token."""
        with pytest.raises(AuthenticationError):
            auth.auth_headers()

    def test_has_scope(self) -> None:
        """Test scope checking."""
        assert GoogleAuthHelper.has_scope(
            "https://www.googleapis.com/auth/gmail.readonly",
            ["https://www.googleapis.com/auth/gmail.readonly"],
        )
        assert not GoogleAuthHelper.has_scope(
            "https://www.googleapis.com/auth/gmail.readonly",
            ["https://www.googleapis.com/auth/drive.readonly"],
        )


# =========================================================================
# Scope tests
# =========================================================================


class TestScopes:
    """Tests for Google scope definitions."""

    def test_all_services_present(self) -> None:
        """Test all expected services have scopes."""
        assert "drive" in GOOGLE_SCOPES
        assert "gmail" in GOOGLE_SCOPES
        assert "calendar" in GOOGLE_SCOPES
        assert "contacts" in GOOGLE_SCOPES

    def test_scopes_for_service_drive(self) -> None:
        """Test drive scopes."""
        scopes = scopes_for_service("drive")
        assert len(scopes) == 2
        assert "https://www.googleapis.com/auth/drive.readonly" in scopes

    def test_scopes_for_service_gmail(self) -> None:
        """Test gmail scopes."""
        scopes = scopes_for_service("gmail")
        assert "https://www.googleapis.com/auth/gmail.readonly" in scopes

    def test_scopes_for_service_calendar(self) -> None:
        """Test calendar scopes."""
        scopes = scopes_for_service("calendar")
        assert "https://www.googleapis.com/auth/calendar.readonly" in scopes

    def test_scopes_for_service_contacts(self) -> None:
        """Test contacts scopes."""
        scopes = scopes_for_service("contacts")
        assert "https://www.googleapis.com/auth/contacts.readonly" in scopes

    def test_scopes_for_unknown_service(self) -> None:
        """Test unknown service raises."""
        with pytest.raises(ValueError, match="Unknown Google service"):
            scopes_for_service("unknown")

    def test_all_scopes(self) -> None:
        """Test all_scopes combines all services."""
        scopes = all_scopes()
        assert len(scopes) >= 5
        assert "https://www.googleapis.com/auth/gmail.readonly" in scopes
        assert "https://www.googleapis.com/auth/drive.readonly" in scopes


class TestServiceHasScopes:
    """Tests for service_has_scopes helper."""

    def test_drive_has_all_scopes(self) -> None:
        """Test drive is authorized when all drive scopes granted."""
        granted = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]
        assert service_has_scopes("drive", granted) is True

    def test_drive_missing_one_scope(self) -> None:
        """Test drive is not authorized when one scope is missing."""
        granted = ["https://www.googleapis.com/auth/drive.readonly"]
        assert service_has_scopes("drive", granted) is False

    def test_gmail_authorized(self) -> None:
        """Test gmail is authorized with correct scope."""
        granted = ["https://www.googleapis.com/auth/gmail.readonly"]
        assert service_has_scopes("gmail", granted) is True

    def test_empty_granted_scopes(self) -> None:
        """Test no scopes granted returns False."""
        assert service_has_scopes("drive", []) is False

    def test_extra_scopes_dont_interfere(self) -> None:
        """Test that extra scopes don't affect authorization check."""
        granted = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/some.other.scope",
        ]
        assert service_has_scopes("gmail", granted) is True

    def test_unknown_service_raises(self) -> None:
        """Test unknown service raises ValueError."""
        with pytest.raises(ValueError, match="Unknown Google service"):
            service_has_scopes("unknown", [])


class TestServicesAuthorized:
    """Tests for services_authorized helper."""

    def test_no_scopes_all_false(self) -> None:
        """Test empty scopes returns all services as False."""
        result = services_authorized([])
        assert result == {
            "drive": False,
            "gmail": False,
            "calendar": False,
            "contacts": False,
        }

    def test_all_scopes_all_true(self) -> None:
        """Test all scopes returns all services as True."""
        granted = all_scopes()
        result = services_authorized(granted)
        assert all(result.values())

    def test_partial_authorization(self) -> None:
        """Test with only some services authorized."""
        granted = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
        ]
        result = services_authorized(granted)
        assert result["gmail"] is True
        assert result["calendar"] is True
        assert result["drive"] is False
        assert result["contacts"] is False

    def test_all_four_services_present(self) -> None:
        """Test result dict has all four service keys."""
        result = services_authorized([])
        assert set(result.keys()) == {"drive", "gmail", "calendar", "contacts"}


# =========================================================================
# Rate limiter tests
# =========================================================================


class TestRateLimiter:
    """Tests for rate limit handling."""

    @pytest.mark.asyncio
    async def test_handle_rate_limit_with_retry_after(self) -> None:
        """Test rate limit with Retry-After header."""
        response = MagicMock(spec=httpx.Response)
        response.headers = {"Retry-After": "5"}
        response.text = ""

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await handle_rate_limit(response, "test_provider")
            mock_sleep.assert_called_once_with(5 + RETRY_BUFFER_SECONDS)

    @pytest.mark.asyncio
    async def test_handle_rate_limit_with_timestamp(self) -> None:
        """Test rate limit with timestamp in body."""
        future = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        response = MagicMock(spec=httpx.Response)
        response.headers = {}
        response.text = f"Retry after {future}"

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await handle_rate_limit(response, "test_provider")
            called_time = mock_sleep.call_args[0][0]
            # Should sleep roughly 30 seconds + buffer
            assert 25 <= called_time <= 40

    @pytest.mark.asyncio
    async def test_handle_rate_limit_default_sleep(self) -> None:
        """Test rate limit with no Retry-After header or timestamp."""
        response = MagicMock(spec=httpx.Response)
        response.headers = {}
        response.text = "rate limited"

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await handle_rate_limit(response, "test_provider")
            mock_sleep.assert_called_once_with(
                DEFAULT_RETRY_SECONDS + RETRY_BUFFER_SECONDS
            )

    def test_parse_retry_timestamp_valid(self) -> None:
        """Test parsing a valid timestamp."""
        future = (datetime.now(timezone.utc) + timedelta(seconds=60)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        result = _parse_retry_timestamp(f"Retry after {future}")
        assert 55 <= result <= 65

    def test_parse_retry_timestamp_past(self) -> None:
        """Test parsing a past timestamp returns 0."""
        past = (datetime.now(timezone.utc) - timedelta(seconds=60)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        result = _parse_retry_timestamp(f"Retry after {past}")
        assert result == 0

    def test_parse_retry_timestamp_no_match(self) -> None:
        """Test default return when no timestamp found."""
        result = _parse_retry_timestamp("some error text")
        assert result == DEFAULT_RETRY_SECONDS


# =========================================================================
# Pagination tests
# =========================================================================


class TestPagination:
    """Tests for Google API pagination."""

    @pytest.mark.asyncio
    async def test_single_page(self) -> None:
        """Test pagination with a single page."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{"id": "1"}, {"id": "2"}],
        }
        mock_client.get.return_value = mock_response

        items = []
        async for item in google_paginate(
            client=mock_client,
            url="https://api.example.com/items",
            headers={"Authorization": "Bearer token"},
            params={},
            items_key="items",
            provider="test",
        ):
            items.append(item)

        assert len(items) == 2
        assert items[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_multi_page(self) -> None:
        """Test pagination with multiple pages."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = {
            "items": [{"id": "1"}],
            "nextPageToken": "page2",
        }

        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = {
            "items": [{"id": "2"}],
        }

        mock_client.get.side_effect = [page1, page2]

        items = []
        async for item in google_paginate(
            client=mock_client,
            url="https://api.example.com/items",
            headers={"Authorization": "Bearer token"},
            params={},
            items_key="items",
            provider="test",
        ):
            items.append(item)

        assert len(items) == 2
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_max_pages(self) -> None:
        """Test max_pages limit."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "items": [{"id": "1"}],
            "nextPageToken": "more",
        }
        mock_client.get.return_value = response

        items = []
        async for item in google_paginate(
            client=mock_client,
            url="https://api.example.com/items",
            headers={},
            params={},
            items_key="items",
            provider="test",
            max_pages=1,
        ):
            items.append(item)

        assert len(items) == 1
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self) -> None:
        """Test rate limit handling during pagination."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "1"}
        rate_limited.text = ""

        success = MagicMock()
        success.status_code = 200
        success.json.return_value = {"items": [{"id": "1"}]}

        mock_client.get.side_effect = [rate_limited, success]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            items = []
            async for item in google_paginate(
                client=mock_client,
                url="https://api.example.com/items",
                headers={},
                params={},
                items_key="items",
                provider="test",
            ):
                items.append(item)

            assert len(items) == 1

    @pytest.mark.asyncio
    async def test_non_200_error(self) -> None:
        """Test non-200/non-429 response raises DownloadError."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        error_response = MagicMock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        mock_client.get.return_value = error_response

        with pytest.raises(DownloadError):
            async for _ in google_paginate(
                client=mock_client,
                url="https://api.example.com/items",
                headers={},
                params={},
                items_key="items",
                provider="test",
            ):
                pass

    @pytest.mark.asyncio
    async def test_empty_page(self) -> None:
        """Test pagination with empty items list."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"items": []}
        mock_client.get.return_value = response

        items = []
        async for item in google_paginate(
            client=mock_client,
            url="https://api.example.com/items",
            headers={},
            params={},
            items_key="items",
            provider="test",
        ):
            items.append(item)

        assert len(items) == 0


# =========================================================================
# Markdown conversion tests
# =========================================================================


class TestGmailThreadToMarkdown:
    """Tests for gmail_thread_to_markdown."""

    def test_basic_thread(self) -> None:
        """Test basic thread conversion."""
        thread = {
            "id": "thread1",
            "messages": [
                {
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [
                            {"name": "Subject", "value": "Test Subject"},
                            {"name": "From", "value": "alice@example.com"},
                            {"name": "To", "value": "bob@example.com"},
                            {"name": "Date", "value": "Mon, 7 Feb 2026 10:00:00 +0000"},
                        ],
                        "body": {
                            "data": "SGVsbG8gV29ybGQ=",  # "Hello World" base64url
                        },
                    }
                }
            ],
        }

        md = gmail_thread_to_markdown(thread)

        assert "# Test Subject" in md
        assert "**From:** alice@example.com" in md
        assert "**To:** bob@example.com" in md
        assert "Hello World" in md

    def test_empty_thread(self) -> None:
        """Test empty thread returns empty string."""
        assert gmail_thread_to_markdown({"messages": []}) == ""
        assert gmail_thread_to_markdown({}) == ""

    def test_no_subject(self) -> None:
        """Test thread without subject."""
        thread = {
            "messages": [
                {
                    "payload": {
                        "mimeType": "text/plain",
                        "headers": [
                            {"name": "From", "value": "test@test.com"},
                        ],
                        "body": {"data": "dGVzdA=="},
                    }
                }
            ]
        }
        md = gmail_thread_to_markdown(thread)
        assert "# (No Subject)" in md


class TestCalendarEventToMarkdown:
    """Tests for calendar_event_to_markdown."""

    def test_basic_event(self) -> None:
        """Test basic event conversion."""
        event = {
            "summary": "Team Meeting",
            "start": {"dateTime": "2026-02-07T09:00:00+00:00"},
            "end": {"dateTime": "2026-02-07T10:00:00+00:00"},
            "location": "Room A",
            "organizer": {"email": "alice@example.com"},
            "attendees": [
                {"email": "bob@example.com", "responseStatus": "accepted"},
            ],
            "description": "Weekly standup",
            "status": "confirmed",
        }

        md = calendar_event_to_markdown(event)

        assert "# Team Meeting" in md
        assert "**Where:** Room A" in md
        assert "**Organizer:** alice@example.com" in md
        assert "bob@example.com (accepted)" in md
        assert "Weekly standup" in md

    def test_all_day_event(self) -> None:
        """Test all-day event."""
        event = {
            "summary": "Holiday",
            "start": {"date": "2026-02-07"},
            "end": {"date": "2026-02-08"},
        }

        md = calendar_event_to_markdown(event)

        assert "# Holiday" in md
        assert "2026-02-07" in md

    def test_event_with_hangout_link(self) -> None:
        """Test event with Google Meet link."""
        event = {
            "summary": "Remote Meeting",
            "start": {"dateTime": "2026-02-07T09:00:00+00:00"},
            "end": {"dateTime": "2026-02-07T10:00:00+00:00"},
            "hangoutLink": "https://meet.google.com/abc-def",
        }

        md = calendar_event_to_markdown(event)

        assert "https://meet.google.com/abc-def" in md

    def test_no_title(self) -> None:
        """Test event without title."""
        event = {"start": {"dateTime": "2026-02-07T09:00:00+00:00"}}
        md = calendar_event_to_markdown(event)
        assert "# (No Title)" in md


class TestContactToMarkdown:
    """Tests for contact_to_markdown."""

    def test_basic_contact(self) -> None:
        """Test basic contact conversion."""
        person = {
            "names": [{"displayName": "Alice Johnson"}],
            "emailAddresses": [
                {"value": "alice@example.com", "type": "work"},
            ],
            "phoneNumbers": [
                {"value": "+1-555-123", "type": "mobile"},
            ],
            "organizations": [
                {"name": "Acme Corp", "title": "Engineer"},
            ],
        }

        md = contact_to_markdown(person)

        assert "# Alice Johnson" in md
        assert "alice@example.com (work)" in md
        assert "+1-555-123 (mobile)" in md
        assert "Acme Corp" in md
        assert "Engineer" in md

    def test_contact_with_birthday(self) -> None:
        """Test contact with birthday."""
        person = {
            "names": [{"displayName": "Bob"}],
            "birthdays": [{"date": {"month": 3, "day": 15}}],
        }

        md = contact_to_markdown(person)

        assert "# Bob" in md
        assert "**Birthday:** March 15" in md

    def test_contact_with_biography(self) -> None:
        """Test contact with notes."""
        person = {
            "names": [{"displayName": "Carol"}],
            "biographies": [{"value": "Met at conference"}],
        }

        md = contact_to_markdown(person)

        assert "Met at conference" in md

    def test_unknown_name(self) -> None:
        """Test contact without name."""
        person = {"emailAddresses": [{"value": "unknown@test.com"}]}
        md = contact_to_markdown(person)
        assert "# Unknown" in md

    def test_contact_with_address(self) -> None:
        """Test contact with address."""
        person = {
            "names": [{"displayName": "Dave"}],
            "addresses": [
                {"formattedValue": "123 Main St", "type": "home"},
            ],
        }

        md = contact_to_markdown(person)

        assert "**Address (home):** 123 Main St" in md
