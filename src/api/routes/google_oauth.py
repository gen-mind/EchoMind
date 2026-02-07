"""
Google OAuth2 endpoints for Google Workspace integration.

Handles per-service incremental OAuth with popup mode support.
Each Google service (Drive, Gmail, Calendar, Contacts) can be
authorized individually. Scopes accumulate across services via
Google's include_granted_scopes mechanism.

Tokens are stored in the google_credentials table (one row per user,
shared across all Google connectors).
"""

from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from api.config import get_settings
from api.dependencies import CurrentUser, DbSession
from echomind_lib.db.models import GoogleCredential
from echomind_lib.google import scopes_for_service, services_authorized

logger = logging.getLogger(__name__)

router = APIRouter()

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# Valid Google services
GoogleService = Literal["drive", "gmail", "calendar", "contacts"]
OAuthMode = Literal["popup", "redirect"]

# In-memory state storage (use Redis in production)
# Stores (user_id, service, mode, created_at)
_STATE_TTL_SECONDS = 600  # 10 minutes
_google_oauth_states: dict[str, tuple[int, str, str, float]] = {}

# HTML page returned to popup after successful OAuth
_POPUP_SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head><title>Authorization Complete</title></head>
<body>
<p>Authorization successful. This window will close automatically.</p>
<script>
  if (window.opener) {{
    window.opener.postMessage({{
      type: 'google-oauth-success',
      service: '{service}'
    }}, '*');
  }}
  window.close();
</script>
</body>
</html>"""

_POPUP_ERROR_HTML = """<!DOCTYPE html>
<html>
<head><title>Authorization Failed</title></head>
<body>
<p>Authorization failed: {error}</p>
<script>
  if (window.opener) {{
    window.opener.postMessage({{
      type: 'google-oauth-error',
      error: '{error}'
    }}, '*');
  }}
  setTimeout(function() {{ window.close(); }}, 3000);
</script>
</body>
</html>"""


class GoogleAuthStatusResponse(BaseModel):
    """Response model for Google auth status."""

    connected: bool
    granted_scopes: list[str]
    email: str | None = None
    services: dict[str, bool] = {}


class GoogleAuthUrlResponse(BaseModel):
    """Response model for Google auth URL."""

    url: str


@router.get("/auth/url", response_model=GoogleAuthUrlResponse)
async def google_auth_url(
    user: CurrentUser,
    db: DbSession,
    service: GoogleService = Query(
        ..., description="Google service to authorize (drive, gmail, calendar, contacts)"
    ),
    mode: OAuthMode = Query(
        "redirect", description="OAuth flow mode (popup or redirect)"
    ),
) -> GoogleAuthUrlResponse:
    """
    Generate Google OAuth2 authorization URL for a specific service.

    Requests only the scopes needed for the specified service.
    Uses include_granted_scopes=true for incremental authorization,
    so previously granted scopes are preserved.

    Args:
        user: Authenticated user from JWT.
        db: Database session.
        service: Google service to authorize.
        mode: OAuth flow mode (popup or redirect).

    Returns:
        GoogleAuthUrlResponse with the authorization URL.

    Raises:
        HTTPException: If Google OAuth is not configured.
    """
    settings = get_settings()

    if not settings.google_client_id or not settings.google_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )

    _cleanup_expired_states()
    state = secrets.token_urlsafe(32)
    _google_oauth_states[state] = (user.id, service, mode, time.monotonic())

    # Check if user already has credentials to determine prompt type
    result = await db.execute(
        select(GoogleCredential).where(GoogleCredential.user_id == user.id)
    )
    existing_credential = result.scalar_one_or_none()

    # Use consent only for first-time auth; otherwise select_account
    # avoids re-consent for already-granted scopes
    prompt = "consent" if not existing_credential else "select_account"

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes_for_service(service)),
        "access_type": "offline",
        "prompt": prompt,
        "include_granted_scopes": "true",
        "state": state,
    }

    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    logger.info(
        f"🔐 Generated Google OAuth URL for user {user.id}, "
        f"service={service}, mode={mode}"
    )

    return GoogleAuthUrlResponse(url=url)


@router.get("/auth/callback", response_model=None)
async def google_auth_callback(
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    scope: str | None = None,
) -> RedirectResponse | HTMLResponse:
    """
    Handle Google OAuth2 callback.

    Exchanges authorization code for tokens, merges granted scopes
    with any existing scopes, and either redirects (redirect mode)
    or returns HTML that posts a message to the opener (popup mode).

    Args:
        db: Database session.
        code: Authorization code from Google.
        state: State parameter for CSRF validation.
        error: Error from Google (if any).
        scope: Granted scopes from Google.

    Returns:
        RedirectResponse (redirect mode) or HTMLResponse (popup mode).

    Raises:
        HTTPException: If OAuth flow fails.
    """
    settings = get_settings()

    # Determine mode from state (default to redirect if state is missing)
    state_service = "drive"
    state_mode: str = "redirect"

    if state and state in _google_oauth_states:
        _, state_service, state_mode, _ = _google_oauth_states[state]

    if error:
        logger.error(f"❌ Google OAuth error: {error}")
        if state_mode == "popup":
            return HTMLResponse(
                content=_POPUP_ERROR_HTML.format(error=error),
                status_code=200,
            )
        frontend_url = settings.oauth_frontend_url or ""
        return RedirectResponse(
            url=f"{frontend_url}/connectors/google?error={error}",
            status_code=status.HTTP_302_FOUND,
        )

    if not state or state not in _google_oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    user_id, state_service, state_mode, _created_at = _google_oauth_states.pop(state)

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "redirect_uri": settings.google_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_response.status_code != 200:
                logger.error(
                    f"❌ Google token exchange failed: {token_response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to exchange Google authorization code",
                )

            tokens = token_response.json()

    except httpx.RequestError as e:
        logger.exception("❌ Google OAuth request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google OAuth request failed: {e}",
        ) from e

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access token received from Google",
        )

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token received from Google. "
            "Re-authorize with prompt=consent.",
        )

    # Parse granted scopes from token response
    granted_scopes_str = tokens.get("scope", scope or "")
    new_scopes = granted_scopes_str.split() if granted_scopes_str else []

    # Calculate token expiry
    expires_in = tokens.get("expires_in", 3600)
    token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Upsert google_credentials for user with scope merging
    result = await db.execute(
        select(GoogleCredential).where(GoogleCredential.user_id == user_id)
    )
    credential = result.scalar_one_or_none()

    if credential:
        # Merge scopes: union of existing + newly granted
        existing_scopes = set(credential.granted_scopes or [])
        merged_scopes = sorted(existing_scopes | set(new_scopes))

        credential.access_token = access_token
        credential.refresh_token = refresh_token
        credential.token_expires_at = token_expires_at
        credential.granted_scopes = merged_scopes
        credential.client_id = settings.google_client_id
        credential.client_secret = settings.google_client_secret
        credential.last_update = datetime.now(timezone.utc)
        logger.info(
            f"🔄 Updated Google credentials for user {user_id}, "
            f"service={state_service}, scopes={len(merged_scopes)}"
        )
    else:
        credential = GoogleCredential(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            granted_scopes=sorted(new_scopes),
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        db.add(credential)
        logger.info(
            f"✅ Created Google credentials for user {user_id}, "
            f"service={state_service}"
        )

    await db.commit()

    # Return response based on mode
    if state_mode == "popup":
        return HTMLResponse(
            content=_POPUP_SUCCESS_HTML.format(service=state_service),
            status_code=200,
        )

    # Redirect mode (backwards compatible)
    frontend_url = settings.oauth_frontend_url or ""
    return RedirectResponse(
        url=f"{frontend_url}/connectors/google/setup",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/auth/status", response_model=GoogleAuthStatusResponse)
async def google_auth_status(
    user: CurrentUser,
    db: DbSession,
) -> GoogleAuthStatusResponse:
    """
    Check Google connection status for the current user.

    Returns connection status, granted scopes, and per-service
    authorization status.

    Args:
        user: Authenticated user from JWT.
        db: Database session.

    Returns:
        GoogleAuthStatusResponse with connection status, granted scopes,
        and per-service authorization status.
    """
    result = await db.execute(
        select(GoogleCredential).where(GoogleCredential.user_id == user.id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        return GoogleAuthStatusResponse(
            connected=False,
            granted_scopes=[],
            services=services_authorized([]),
        )

    return GoogleAuthStatusResponse(
        connected=True,
        granted_scopes=credential.granted_scopes,
        services=services_authorized(credential.granted_scopes),
    )


@router.delete("/auth", status_code=status.HTTP_204_NO_CONTENT)
async def google_auth_revoke(
    user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Revoke Google tokens and delete credentials.

    Args:
        user: Authenticated user from JWT.
        db: Database session.

    Raises:
        HTTPException: If user has no Google credentials.
    """
    result = await db.execute(
        select(GoogleCredential).where(GoogleCredential.user_id == user.id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Google credentials found",
        )

    # Revoke token at Google
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                GOOGLE_REVOKE_URL,
                params={"token": credential.access_token},
            )
            logger.info(f"🔓 Revoked Google token for user {user.id}")
    except httpx.RequestError:
        logger.warning(
            f"⚠️ Failed to revoke Google token for user {user.id} (continuing with deletion)"
        )

    # Delete from database
    await db.delete(credential)
    await db.commit()
    logger.info(f"🗑️ Deleted Google credentials for user {user.id}")


def _cleanup_expired_states() -> None:
    """Remove expired OAuth state entries to prevent memory leaks.

    Called before creating a new state. Removes entries older than
    _STATE_TTL_SECONDS.
    """
    now = time.monotonic()
    expired = [
        key
        for key, (_uid, _service, _mode, created_at) in _google_oauth_states.items()
        if now - created_at > _STATE_TTL_SECONDS
    ]
    for key in expired:
        _google_oauth_states.pop(key, None)
