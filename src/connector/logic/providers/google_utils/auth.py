"""Shared Google OAuth2 authentication helper for all Google providers."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from connector.logic.exceptions import AuthenticationError

logger = logging.getLogger("echomind-connector.google_auth")

# Google token endpoint
TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleAuthHelper:
    """Shared Google OAuth2 token management.

    Handles token loading, refresh, and header generation for all
    Google providers. Extracted from GoogleDriveProvider to share
    across Gmail, Calendar, and Contacts providers.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """Initialize auth helper.

        Args:
            http_client: httpx client for token refresh requests.
        """
        self._client = http_client
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def access_token(self) -> str | None:
        """Current access token."""
        return self._access_token

    @property
    def token_expires_at(self) -> datetime | None:
        """Token expiration timestamp."""
        return self._token_expires_at

    async def authenticate(self, config: dict[str, Any]) -> None:
        """Load tokens from config and refresh if expired.

        Args:
            config: Must contain 'access_token'. Optionally contains
                'refresh_token', 'client_id', 'client_secret',
                'token_expires_at'.

        Raises:
            AuthenticationError: If no access_token in config.
        """
        if "access_token" not in config:
            raise AuthenticationError(
                "google", "Missing access_token in config"
            )

        self._access_token = config["access_token"]

        if "token_expires_at" in config and config["token_expires_at"]:
            self._token_expires_at = datetime.fromisoformat(
                config["token_expires_at"]
            )

        # Refresh if expired
        if self._is_expired():
            await self.refresh_token(config)

    def _is_expired(self) -> bool:
        """Check if the current token is expired or about to expire.

        Returns:
            True if token is expired or will expire within 60 seconds.
        """
        if not self._token_expires_at:
            return False
        return self._token_expires_at <= datetime.now(timezone.utc) + timedelta(
            seconds=60
        )

    async def refresh_token(self, config: dict[str, Any]) -> None:
        """Refresh the OAuth2 access token.

        Args:
            config: Must contain 'refresh_token', 'client_id', 'client_secret'.

        Raises:
            AuthenticationError: If refresh fails or required fields missing.
        """
        refresh_token = config.get("refresh_token")
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")

        if not all([refresh_token, client_id, client_secret]):
            raise AuthenticationError(
                "google",
                "Missing refresh_token, client_id, or client_secret for token refresh",
            )

        response = await self._client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

        if response.status_code != 200:
            raise AuthenticationError(
                "google",
                f"Token refresh failed: {response.text}",
            )

        data = response.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=expires_in
        )

        logger.info("🔄 Refreshed Google access token")

    async def ensure_valid_token(self, config: dict[str, Any]) -> str:
        """Return a valid access token, refreshing if needed.

        Args:
            config: Config dict with refresh credentials.

        Returns:
            Valid access token string.

        Raises:
            AuthenticationError: If token is None or refresh fails.
        """
        if self._is_expired():
            await self.refresh_token(config)

        if not self._access_token:
            raise AuthenticationError("google", "No access token available")

        return self._access_token

    def auth_headers(self) -> dict[str, str]:
        """Return Authorization: Bearer header dict.

        Returns:
            Dict with Authorization header.

        Raises:
            AuthenticationError: If no access token is set.
        """
        if not self._access_token:
            raise AuthenticationError("google", "Not authenticated")
        return {"Authorization": f"Bearer {self._access_token}"}

    @staticmethod
    def has_scope(scope: str, granted_scopes: list[str]) -> bool:
        """Check if a specific scope was granted.

        Args:
            scope: The scope URI to check.
            granted_scopes: List of granted scope URIs.

        Returns:
            True if scope is in granted_scopes.
        """
        return scope in granted_scopes
