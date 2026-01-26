"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from echomind_lib.db.models import User as UserORM
from echomind_lib.helpers.auth import (
    extract_bearer_token,
    get_jwt_validator,
)
from echomind_lib.models.public import User

router = APIRouter()


class SessionResponse(BaseModel):
    """Response from session sync."""
    user: User
    message: str


@router.post("/session", response_model=SessionResponse)
async def create_session(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """
    Sync user from Authentik to local database on login.

    This endpoint should be called once after OIDC login completes.
    It creates the user in the local database if they don't exist,
    or updates their info if they do.

    Returns:
        SessionResponse: The synced user info.
    """
    # Validate JWT token
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        validator = get_jwt_validator()
        token_user = validator.validate_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up user by external_id (Authentik sub)
    result = await db.execute(
        select(UserORM).where(UserORM.external_id == token_user.external_id)
    )
    db_user = result.scalar_one_or_none()

    if db_user is None:
        # Create user on first login
        db_user = UserORM(
            user_name=token_user.user_name,
            email=token_user.email,
            first_name=token_user.first_name,
            last_name=token_user.last_name,
            external_id=token_user.external_id,
            roles=token_user.roles,
            groups=token_user.groups,
        )
        db.add(db_user)
        await db.flush()
        await db.refresh(db_user)
        message = "User created"
    else:
        # Update user info from token (sync on login)
        db_user.user_name = token_user.user_name
        db_user.email = token_user.email
        db_user.first_name = token_user.first_name
        db_user.last_name = token_user.last_name
        db_user.roles = token_user.roles
        db_user.groups = token_user.groups
        await db.flush()
        message = "User synced"

    # Return User model
    user = User.model_validate(db_user, from_attributes=True)
    return SessionResponse(user=user, message=message)


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session() -> None:
    """
    Logout endpoint (for future session management).

    Currently just a placeholder - actual logout is handled by OIDC.
    """
    # Stub: Session invalidation handled by OIDC provider (Authentik)
    pass
