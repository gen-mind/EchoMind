"""Unit tests for Google OAuth2 endpoints."""

import time
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.google_oauth import (
    _cleanup_expired_states,
    _google_oauth_states,
    _STATE_TTL_SECONDS,
    router,
)


@pytest.fixture
def _mock_user() -> MagicMock:
    """Create a mock authenticated user with id=1."""
    user = MagicMock()
    user.id = 1
    user.email = "test@example.com"
    return user


@pytest.fixture
def _mock_db() -> MagicMock:
    """Create a mock async DB session."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def client(_mock_user: MagicMock, _mock_db: MagicMock) -> TestClient:
    """Create a test client with the Google OAuth router and mocked deps."""
    from api.dependencies import get_current_user, get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/google")

    async def override_user() -> MagicMock:
        return _mock_user

    async def override_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db_session] = override_db

    return TestClient(app)


def _mock_settings(**overrides: object) -> MagicMock:
    """Create mock settings with sensible defaults.

    Args:
        **overrides: Fields to override on the mock settings.

    Returns:
        MagicMock configured as Settings instance.
    """
    settings = MagicMock()
    settings.google_client_id = overrides.get("google_client_id", "test-client-id")
    settings.google_client_secret = overrides.get("google_client_secret", "test-secret")
    settings.google_redirect_uri = overrides.get(
        "google_redirect_uri", "https://example.com/callback"
    )
    settings.oauth_frontend_url = overrides.get(
        "oauth_frontend_url", "https://app.example.com"
    )
    return settings


def _mock_no_credential(mock_db: MagicMock) -> None:
    """Configure mock DB to return no existing credential.

    Args:
        mock_db: Mock database session.
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)


def _mock_existing_credential(
    mock_db: MagicMock,
    granted_scopes: list[str] | None = None,
    access_token: str = "existing_token",
) -> MagicMock:
    """Configure mock DB to return an existing credential.

    Args:
        mock_db: Mock database session.
        granted_scopes: Scopes already granted.
        access_token: Token value.

    Returns:
        The mock credential object.
    """
    credential = MagicMock()
    credential.granted_scopes = granted_scopes or []
    credential.access_token = access_token
    credential.refresh_token = "existing_refresh"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = credential
    mock_db.execute = AsyncMock(return_value=mock_result)
    return credential


def _mock_token_exchange(
    mock_client_cls: MagicMock,
    access_token: str = "test_access_token",
    refresh_token: str | None = "test_refresh_token",
    scope: str = "https://www.googleapis.com/auth/gmail.readonly",
    status_code: int = 200,
    text: str = "",
) -> None:
    """Configure mock httpx client for token exchange.

    Args:
        mock_client_cls: The mocked httpx.AsyncClient class.
        access_token: Token to return.
        refresh_token: Refresh token to return.
        scope: Scope string to return.
        status_code: HTTP status code.
        text: Response text (for errors).
    """
    mock_token_response = MagicMock()
    mock_token_response.status_code = status_code
    mock_token_response.text = text

    response_data: dict[str, object] = {
        "access_token": access_token,
        "expires_in": 3600,
        "scope": scope,
    }
    if refresh_token:
        response_data["refresh_token"] = refresh_token
    mock_token_response.json.return_value = response_data

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_token_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client


class TestGoogleAuthUrl:
    """Tests for GET /auth/url endpoint."""

    def test_generates_url_with_service_scopes(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test URL generation includes only scopes for the requested service."""
        _mock_no_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get("/google/auth/url?service=gmail")

        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "accounts.google.com" in data["url"]
        assert "gmail.readonly" in data["url"]
        # Should NOT include drive scopes
        assert "drive.readonly" not in data["url"]

    def test_generates_url_with_drive_scopes(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test URL generation with drive service includes drive scopes."""
        _mock_no_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get("/google/auth/url?service=drive")

        assert response.status_code == 200
        data = response.json()
        assert "drive.readonly" in data["url"]

    def test_generates_url_with_calendar_scopes(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test URL generation with calendar service."""
        _mock_no_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get("/google/auth/url?service=calendar")

        assert response.status_code == 200
        assert "calendar.readonly" in response.json()["url"]

    def test_generates_url_with_contacts_scopes(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test URL generation with contacts service."""
        _mock_no_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get("/google/auth/url?service=contacts")

        assert response.status_code == 200
        assert "contacts.readonly" in response.json()["url"]

    def test_requires_service_param(self, client: TestClient) -> None:
        """Test that service parameter is required."""
        response = client.get("/google/auth/url")
        assert response.status_code == 422  # Validation error

    def test_rejects_invalid_service(self, client: TestClient) -> None:
        """Test that invalid service is rejected."""
        response = client.get("/google/auth/url?service=invalid")
        assert response.status_code == 422

    def test_consent_prompt_for_new_user(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test prompt=consent when user has no existing credential."""
        _mock_no_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get("/google/auth/url?service=drive")

        assert "prompt=consent" in response.json()["url"]

    def test_select_account_prompt_for_existing_user(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test prompt=select_account when user has existing credential."""
        _mock_existing_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get("/google/auth/url?service=gmail")

        assert "prompt=select_account" in response.json()["url"]

    def test_returns_501_when_not_configured(self, client: TestClient) -> None:
        """Test 501 when Google OAuth is not configured."""
        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings(
                google_client_id=None, google_redirect_uri=None
            )

            response = client.get("/google/auth/url?service=drive")

        assert response.status_code == 501

    def test_state_stored_with_service_and_mode(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test that state stores user_id, service, mode, and timestamp."""
        _google_oauth_states.clear()
        _mock_no_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            client.get("/google/auth/url?service=gmail&mode=popup")

        assert len(_google_oauth_states) == 1
        state_key = next(iter(_google_oauth_states))
        user_id, service, mode, created_at = _google_oauth_states[state_key]
        assert user_id == 1
        assert service == "gmail"
        assert mode == "popup"
        assert isinstance(created_at, float)

        _google_oauth_states.clear()

    def test_default_mode_is_redirect(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test default mode is redirect when not specified."""
        _google_oauth_states.clear()
        _mock_no_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            client.get("/google/auth/url?service=drive")

        state_key = next(iter(_google_oauth_states))
        _, _, mode, _ = _google_oauth_states[state_key]
        assert mode == "redirect"

        _google_oauth_states.clear()

    def test_include_granted_scopes_in_url(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test that include_granted_scopes=true is in URL."""
        _mock_no_credential(_mock_db)

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get("/google/auth/url?service=drive")

        assert "include_granted_scopes=true" in response.json()["url"]


class TestGoogleAuthCallback:
    """Tests for GET /auth/callback endpoint."""

    def test_callback_with_error_redirects(self, client: TestClient) -> None:
        """Test callback with error parameter redirects to frontend."""
        # State with redirect mode
        _google_oauth_states["err_state"] = (1, "drive", "redirect", time.monotonic())

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get(
                "/google/auth/callback",
                params={"error": "access_denied", "state": "err_state"},
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "error=access_denied" in response.headers["location"]
        _google_oauth_states.clear()

    def test_callback_with_error_popup_returns_html(self, client: TestClient) -> None:
        """Test callback with error in popup mode returns HTML."""
        _google_oauth_states["popup_err"] = (1, "gmail", "popup", time.monotonic())

        with patch("api.routes.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value = _mock_settings()

            response = client.get(
                "/google/auth/callback",
                params={"error": "access_denied", "state": "popup_err"},
            )

        assert response.status_code == 200
        assert "google-oauth-error" in response.text
        assert "access_denied" in response.text
        _google_oauth_states.clear()

    def test_callback_invalid_state_returns_400(self, client: TestClient) -> None:
        """Test callback with invalid state returns 400."""
        response = client.get(
            "/google/auth/callback",
            params={"code": "auth_code", "state": "invalid_state"},
        )

        assert response.status_code == 400

    def test_callback_missing_state_returns_400(self, client: TestClient) -> None:
        """Test callback without state returns 400."""
        response = client.get(
            "/google/auth/callback",
            params={"code": "auth_code"},
        )

        assert response.status_code == 400

    def test_callback_missing_code_returns_400(self, client: TestClient) -> None:
        """Test callback without code returns 400."""
        _google_oauth_states["test_state"] = (1, "drive", "redirect", time.monotonic())

        response = client.get(
            "/google/auth/callback",
            params={"state": "test_state"},
        )

        assert response.status_code == 400
        _google_oauth_states.clear()

    def test_callback_success_redirect_mode(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test successful callback in redirect mode creates credentials and redirects."""
        _google_oauth_states["valid_state"] = (1, "gmail", "redirect", time.monotonic())
        _mock_no_credential(_mock_db)

        with (
            patch("api.routes.google_oauth.get_settings") as mock_settings,
            patch("api.routes.google_oauth.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.return_value = _mock_settings()
            _mock_token_exchange(mock_client_cls)

            response = client.get(
                "/google/auth/callback",
                params={"code": "auth_code", "state": "valid_state"},
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "/connectors/google/setup" in response.headers["location"]
        assert "valid_state" not in _google_oauth_states
        assert _mock_db.add.called

        _google_oauth_states.clear()

    def test_callback_success_popup_mode(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test successful callback in popup mode returns HTML with postMessage."""
        _google_oauth_states["popup_state"] = (1, "gmail", "popup", time.monotonic())
        _mock_no_credential(_mock_db)

        with (
            patch("api.routes.google_oauth.get_settings") as mock_settings,
            patch("api.routes.google_oauth.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.return_value = _mock_settings()
            _mock_token_exchange(mock_client_cls)

            response = client.get(
                "/google/auth/callback",
                params={"code": "auth_code", "state": "popup_state"},
            )

        assert response.status_code == 200
        assert "google-oauth-success" in response.text
        assert "gmail" in response.text
        assert "window.opener.postMessage" in response.text
        assert _mock_db.add.called

        _google_oauth_states.clear()

    def test_callback_scope_merging(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test that new scopes are merged with existing scopes."""
        _google_oauth_states["merge_state"] = (1, "gmail", "redirect", time.monotonic())

        existing_scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]
        credential = _mock_existing_credential(
            _mock_db, granted_scopes=existing_scopes
        )

        new_scope = "https://www.googleapis.com/auth/gmail.readonly"

        with (
            patch("api.routes.google_oauth.get_settings") as mock_settings,
            patch("api.routes.google_oauth.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.return_value = _mock_settings()
            _mock_token_exchange(mock_client_cls, scope=new_scope)

            response = client.get(
                "/google/auth/callback",
                params={"code": "auth_code", "state": "merge_state"},
                follow_redirects=False,
            )

        assert response.status_code == 302
        # Credential should have merged scopes (drive + gmail)
        merged = credential.granted_scopes
        assert new_scope in merged
        assert "https://www.googleapis.com/auth/drive.readonly" in merged
        assert "https://www.googleapis.com/auth/drive.metadata.readonly" in merged
        assert len(merged) == 3

        _google_oauth_states.clear()

    def test_callback_token_exchange_failure_returns_401(
        self, client: TestClient
    ) -> None:
        """Test callback returns 401 when token exchange fails."""
        _google_oauth_states["fail_state"] = (1, "drive", "redirect", time.monotonic())

        with (
            patch("api.routes.google_oauth.get_settings") as mock_settings,
            patch("api.routes.google_oauth.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.return_value = _mock_settings()
            _mock_token_exchange(mock_client_cls, status_code=400, text="invalid_grant")

            response = client.get(
                "/google/auth/callback",
                params={"code": "bad_code", "state": "fail_state"},
            )

        assert response.status_code == 401
        _google_oauth_states.clear()

    def test_callback_no_refresh_token_returns_401(
        self, client: TestClient
    ) -> None:
        """Test callback returns 401 when no refresh token received."""
        _google_oauth_states["no_refresh_state"] = (
            1, "drive", "redirect", time.monotonic()
        )

        with (
            patch("api.routes.google_oauth.get_settings") as mock_settings,
            patch("api.routes.google_oauth.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_settings.return_value = _mock_settings()
            _mock_token_exchange(mock_client_cls, refresh_token=None)

            response = client.get(
                "/google/auth/callback",
                params={"code": "auth_code", "state": "no_refresh_state"},
            )

        assert response.status_code == 401
        assert "refresh token" in response.json()["detail"].lower()
        _google_oauth_states.clear()


class TestGoogleAuthStatus:
    """Tests for GET /auth/status endpoint."""

    def test_status_not_connected(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test status when user has no Google credentials."""
        _mock_no_credential(_mock_db)

        response = client.get("/google/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["granted_scopes"] == []
        assert data["services"]["drive"] is False
        assert data["services"]["gmail"] is False
        assert data["services"]["calendar"] is False
        assert data["services"]["contacts"] is False

    def test_status_connected_with_drive(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test status when user has Drive scopes granted."""
        _mock_existing_credential(
            _mock_db,
            granted_scopes=[
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/drive.metadata.readonly",
            ],
        )

        response = client.get("/google/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["services"]["drive"] is True
        assert data["services"]["gmail"] is False
        assert data["services"]["calendar"] is False
        assert data["services"]["contacts"] is False

    def test_status_connected_with_multiple_services(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test status with multiple services authorized."""
        _mock_existing_credential(
            _mock_db,
            granted_scopes=[
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/drive.metadata.readonly",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/calendar.readonly",
            ],
        )

        response = client.get("/google/auth/status")

        data = response.json()
        assert data["services"]["drive"] is True
        assert data["services"]["gmail"] is True
        assert data["services"]["calendar"] is True
        assert data["services"]["contacts"] is False


class TestGoogleAuthRevoke:
    """Tests for DELETE /auth endpoint."""

    def test_revoke_no_credentials_returns_404(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test revoke when user has no credentials."""
        _mock_no_credential(_mock_db)

        response = client.delete("/google/auth")

        assert response.status_code == 404

    def test_revoke_success(
        self, client: TestClient, _mock_db: MagicMock
    ) -> None:
        """Test successful revoke deletes credentials."""
        mock_credential = _mock_existing_credential(_mock_db)

        with patch("api.routes.google_oauth.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = MagicMock(status_code=200)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            response = client.delete("/google/auth")

        assert response.status_code == 204
        _mock_db.delete.assert_called_once_with(mock_credential)
        _mock_db.commit.assert_called()


class TestCleanupExpiredStates:
    """Tests for TTL-based state cleanup."""

    def test_cleanup_removes_expired_states(self) -> None:
        """Test expired states are removed."""
        _google_oauth_states.clear()

        _google_oauth_states["expired"] = (
            1,
            "drive",
            "redirect",
            time.monotonic() - _STATE_TTL_SECONDS - 10,
        )
        _google_oauth_states["valid"] = (2, "gmail", "popup", time.monotonic())

        _cleanup_expired_states()

        assert "expired" not in _google_oauth_states
        assert "valid" in _google_oauth_states

        _google_oauth_states.clear()

    def test_cleanup_noop_when_empty(self) -> None:
        """Test cleanup does nothing on empty dict."""
        _google_oauth_states.clear()

        _cleanup_expired_states()

        assert len(_google_oauth_states) == 0

    def test_cleanup_keeps_valid_states(self) -> None:
        """Test cleanup preserves non-expired states."""
        _google_oauth_states.clear()

        _google_oauth_states["fresh1"] = (1, "drive", "redirect", time.monotonic())
        _google_oauth_states["fresh2"] = (2, "gmail", "popup", time.monotonic())

        _cleanup_expired_states()

        assert len(_google_oauth_states) == 2

        _google_oauth_states.clear()
