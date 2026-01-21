"""User management endpoints."""

from fastapi import APIRouter

from api.dependencies import AdminUser, CurrentUser, DbSession
from api.logic.user_service import UserService
from echomind_lib.models.public import (
    ListUsersResponse,
    UpdateUserRequest,
    User,
)

router = APIRouter()


@router.get("/me", response_model=User)
async def get_current_user_profile(user: CurrentUser, db: DbSession) -> User:
    """Get the current user's profile."""
    service = UserService(db)
    return await service.get_user_by_id(user.id)


@router.put("/me", response_model=User)
async def update_current_user_profile(
    updates: UpdateUserRequest,
    user: CurrentUser,
    db: DbSession,
) -> User:
    """Update the current user's profile."""
    service = UserService(db)
    return await service.update_user(user.id, updates, user.id)


@router.get("", response_model=ListUsersResponse)
async def list_users(
    admin: AdminUser,
    db: DbSession,
    page: int = 1,
    limit: int = 20,
    is_active: bool | None = None,
) -> ListUsersResponse:
    """List all users (admin only)."""
    service = UserService(db)
    return await service.list_users(page, limit, is_active)


@router.get("/{user_id}", response_model=User)
async def get_user_by_id(user_id: int, admin: AdminUser, db: DbSession) -> User:
    """Get a user by ID (admin only)."""
    service = UserService(db)
    return await service.get_user_by_id(user_id)
