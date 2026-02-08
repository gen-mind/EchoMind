"""
FastAPI dependency injection.

Provides dependencies for database sessions, authentication, and services.
"""

import logging
from typing import Annotated, AsyncGenerator

logger = logging.getLogger(__name__)

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.connection import get_db_manager
from echomind_lib.db.models import User as UserORM
from echomind_lib.db.nats_publisher import JetStreamPublisher, get_nats_publisher
from echomind_lib.helpers.auth import (
    TokenUser,
    extract_bearer_token,
    get_jwt_validator,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.
    
    Usage:
        @app.get("/items")
        async def get_items(db: DbSession):
            ...
    """
    db = get_db_manager()
    async with db.session() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> TokenUser:
    """
    Get the current authenticated user from JWT token.

    Validates the JWT and looks up the user in the local database.
    User must have called POST /api/v1/auth/session first to sync from Authentik.

    Usage:
        @app.get("/me")
        async def get_me(user: CurrentUser):
            return user
    """
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
        logger.info(f"🔒 Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up user in database by external_id (Authentik sub)
    result = await db.execute(
        select(UserORM).where(UserORM.external_id == token_user.external_id)
    )
    db_user = result.scalar_one_or_none()

    if db_user is None:
        # User not synced yet - they need to call POST /api/v1/auth/session first
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not synced. Call POST /api/v1/auth/session first.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return TokenUser with the database user ID and roles from JWT
    return TokenUser(
        id=db_user.id,
        email=db_user.email,
        user_name=db_user.user_name,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        roles=token_user.roles,  # Use roles from JWT (always current)
        groups=token_user.groups,  # Use groups from JWT (always current)
        external_id=db_user.external_id,
    )


CurrentUser = Annotated[TokenUser, Depends(get_current_user)]


async def get_current_user_optional(
    authorization: Annotated[str | None, Header()] = None,
) -> TokenUser | None:
    """
    Get the current user if authenticated, None otherwise.
    
    Usage:
        @app.get("/public")
        async def public_endpoint(user: OptionalUser):
            if user:
                # authenticated
            else:
                # anonymous
    """
    token = extract_bearer_token(authorization)
    if not token:
        return None
    
    try:
        validator = get_jwt_validator()
        return validator.validate_token(token)
    except Exception:
        return None


OptionalUser = Annotated[TokenUser | None, Depends(get_current_user_optional)]


async def get_verified_user_optional(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> TokenUser | None:
    """
    Get the current verified user if authenticated, None otherwise.

    Unlike OptionalUser, this also verifies the user exists in the database.

    Usage:
        @app.get("/public")
        async def public_endpoint(user: OptionalVerifiedUser):
            if user:
                # authenticated and verified
            else:
                # anonymous
    """
    token = extract_bearer_token(authorization)
    if not token:
        return None

    try:
        validator = get_jwt_validator()
        token_user = validator.validate_token(token)
    except Exception:
        return None

    # Look up user in database by external_id (Authentik sub)
    result = await db.execute(
        select(UserORM).where(UserORM.external_id == token_user.external_id)
    )
    db_user = result.scalar_one_or_none()

    if db_user is None:
        return None

    # Return TokenUser with the database user ID and roles from JWT
    return TokenUser(
        id=db_user.id,
        email=db_user.email,
        user_name=db_user.user_name,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        roles=token_user.roles,
        groups=token_user.groups,
        external_id=db_user.external_id,
    )


OptionalVerifiedUser = Annotated[TokenUser | None, Depends(get_verified_user_optional)]


def require_role(role: str):
    """
    Dependency factory to require a specific role.
    
    Usage:
        @app.get("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_only():
            ...
    """
    async def check_role(user: CurrentUser) -> TokenUser:
        if role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required",
            )
        return user
    
    return check_role


def require_any_role(*roles: str):
    """
    Dependency factory to require any of the specified roles.
    
    Usage:
        @app.get("/staff", dependencies=[Depends(require_any_role("admin", "moderator"))])
        async def staff_only():
            ...
    """
    async def check_roles(user: CurrentUser) -> TokenUser:
        if not any(r in user.roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {roles} required",
            )
        return user
    
    return check_roles


AdminUser = Annotated[TokenUser, Depends(require_role("admin"))]


def get_nats() -> JetStreamPublisher | None:
    """
    Get the NATS publisher if available.

    Returns None if NATS is not initialized (graceful degradation).

    Usage:
        @app.post("/connectors")
        async def create_connector(nats: NatsPublisher):
            if nats:
                await nats.publish(...)
    """
    try:
        return get_nats_publisher()
    except RuntimeError:
        # NATS not initialized - return None for graceful degradation
        return None


NatsPublisher = Annotated[JetStreamPublisher | None, Depends(get_nats)]


def get_minio_client() -> "MinIOClient | None":
    """
    Get the MinIO client if available.

    Returns None if MinIO is not initialized (graceful degradation).

    Usage:
        @app.post("/upload")
        async def upload(minio: MinioClient):
            if minio:
                await minio.upload_file(...)
    """
    from echomind_lib.db.minio import MinIOClient, get_minio

    try:
        return get_minio()
    except RuntimeError:
        # MinIO not initialized - return None for graceful degradation
        return None


MinioClient = Annotated["MinIOClient | None", Depends(get_minio_client)]


def get_qdrant_client() -> "QdrantDB | None":
    """
    Get the Qdrant client if available.

    Returns None if Qdrant is not initialized (graceful degradation).

    Usage:
        @app.post("/documents/search")
        async def search(qdrant: QdrantClient):
            if qdrant:
                await qdrant.search(...)
    """
    from echomind_lib.db.qdrant import QdrantDB, get_qdrant

    try:
        return get_qdrant()
    except RuntimeError:
        # Qdrant not initialized - return None for graceful degradation
        return None


QdrantClient = Annotated["QdrantDB | None", Depends(get_qdrant_client)]
