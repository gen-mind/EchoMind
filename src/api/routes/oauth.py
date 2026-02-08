"""
OAuth/OIDC Authentication Endpoints.

Handles OAuth login flow for the WebUI frontend.
"""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from api.config import get_settings
from api.dependencies import DbSession
from echomind_lib.db.models import User as UserORM

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory state storage for OAuth (use Redis in production)
_oauth_states: dict[str, str] = {}


@router.get("/oidc/login")
async def oauth_oidc_login(request: Request) -> RedirectResponse:
    """
    Initiate OIDC login flow.

    Redirects to the OAuth provider's authorization endpoint.

    Args:
        request: The HTTP request.

    Returns:
        Redirect to OAuth authorization URL.

    Raises:
        HTTPException: If OAuth is not configured.
    """
    settings = get_settings()

    if not settings.oauth_client_id or not settings.oauth_authorize_url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OAuth/OIDC is not configured",
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "pending"

    # Build authorization URL
    params = {
        "client_id": settings.oauth_client_id,
        "response_type": "code",
        "scope": settings.oauth_scope,
        "redirect_uri": settings.oauth_redirect_uri,
        "state": state,
    }

    auth_url = f"{settings.oauth_authorize_url}?{urlencode(params)}"
    logger.info("🔐 Redirecting to OAuth provider: %s", settings.oauth_authorize_url)

    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/oidc/callback")
async def oauth_oidc_callback(
    request: Request,
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """
    Handle OIDC callback after user authenticates.

    Exchanges authorization code for tokens, creates/updates user,
    and redirects to the frontend with the token.

    Args:
        request: The HTTP request.
        db: Database session.
        code: Authorization code from OAuth provider.
        state: State parameter for CSRF validation.
        error: Error from OAuth provider (if any).

    Returns:
        Redirect to frontend with token.

    Raises:
        HTTPException: If OAuth flow fails.
    """
    settings = get_settings()

    # Check for errors from OAuth provider
    if error:
        logger.error("❌ OAuth error: %s", error)
        return RedirectResponse(
            url=f"/auth?error={error}",
            status_code=status.HTTP_302_FOUND,
        )

    # Validate state
    if not state or state not in _oauth_states:
        logger.error("❌ Invalid OAuth state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    # Clean up state
    del _oauth_states[state]

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    if not settings.oauth_token_url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OAuth token URL not configured",
        )

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                settings.oauth_token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.oauth_client_id,
                    "client_secret": settings.oauth_client_secret,
                    "code": code,
                    "redirect_uri": settings.oauth_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_response.status_code != 200:
                logger.error("❌ Token exchange failed: %s", token_response.text)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to exchange authorization code",
                )

            tokens = token_response.json()
            access_token = tokens.get("access_token")
            id_token = tokens.get("id_token")

            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No access token received",
                )

            # Get user info
            if settings.oauth_userinfo_url:
                userinfo_response = await client.get(
                    settings.oauth_userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if userinfo_response.status_code == 200:
                    userinfo = userinfo_response.json()
                    logger.info("✅ OAuth user: %s", userinfo.get("email", "unknown"))

                    # Create or update user in database
                    external_id = userinfo.get("sub")
                    email = userinfo.get("email", "")
                    name = userinfo.get("name", "")
                    given_name = userinfo.get("given_name", "")
                    family_name = userinfo.get("family_name", "")
                    preferred_username = userinfo.get(
                        "preferred_username", email.split("@")[0] if email else ""
                    )

                    result = await db.execute(
                        select(UserORM).where(UserORM.external_id == external_id)
                    )
                    db_user = result.scalar_one_or_none()

                    if db_user is None:
                        # Create new user
                        db_user = UserORM(
                            user_name=preferred_username,
                            email=email,
                            first_name=given_name or name,
                            last_name=family_name or "",
                            external_id=external_id,
                            roles=[],
                            groups=[],
                        )
                        db.add(db_user)
                        await db.flush()
                        logger.info("✅ Created new user: %s", email)
                    else:
                        # Update existing user
                        db_user.email = email
                        db_user.first_name = given_name or name
                        db_user.last_name = family_name or ""
                        await db.flush()
                        logger.info("✅ Updated user: %s", email)

            # Redirect to frontend with token
            # Use id_token if available (contains user claims), else access_token
            token_to_use = id_token or access_token

            # Determine redirect URL - use frontend URL if configured
            frontend_url = settings.oauth_frontend_url or "/"
            redirect_url = f"{frontend_url}/auth" if frontend_url != "/" else "/"

            # Create response with redirect to frontend
            response = RedirectResponse(
                url=redirect_url,
                status_code=status.HTTP_302_FOUND,
            )

            # Set token as cookie for frontend to read
            # Use configured domain for cross-subdomain sharing
            cookie_kwargs = {
                "key": "token",
                "value": token_to_use,
                "httponly": False,  # Frontend JavaScript needs to read it
                "secure": True,
                "samesite": "lax",
                "max_age": 86400 * 7,  # 7 days
                "path": "/",
            }

            # Add domain if configured (e.g., ".demo.echomind.ch" for subdomain sharing)
            if settings.oauth_cookie_domain:
                cookie_kwargs["domain"] = settings.oauth_cookie_domain

            response.set_cookie(**cookie_kwargs)
            logger.info("🍪 Set token cookie, redirecting to %s", redirect_url)

            return response

    except httpx.RequestError as e:
        logger.exception("❌ OAuth request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OAuth request failed: {str(e)}",
        ) from e
