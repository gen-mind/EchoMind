"""
User CRUD operations.
"""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase
from echomind_lib.db.models import User


class UserCRUD(CRUDBase[User]):
    """
    CRUD operations for User model.

    Users are synced from Authentik OIDC, so create/update
    operations are typically done during login flow.
    """

    def __init__(self):
        """Initialize UserCRUD."""
        super().__init__(User)

    async def get_by_email(
        self,
        session: AsyncSession,
        email: str,
    ) -> User | None:
        """
        Get user by email address.

        Args:
            session: Database session.
            email: User email.

        Returns:
            User or None if not found.
        """
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(
        self,
        session: AsyncSession,
        user_name: str,
    ) -> User | None:
        """
        Get user by username.

        Args:
            session: Database session.
            user_name: Username.

        Returns:
            User or None if not found.
        """
        result = await session.execute(
            select(User).where(User.user_name == user_name)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(
        self,
        session: AsyncSession,
        external_id: str,
    ) -> User | None:
        """
        Get user by external ID (from OIDC provider).

        Args:
            session: Database session.
            external_id: External ID from identity provider.

        Returns:
            User or None if not found.
        """
        result = await session.execute(
            select(User).where(User.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_active_users(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[User]:
        """
        Get active users with pagination.

        Args:
            session: Database session.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of active users.
        """
        result = await session.execute(
            select(User)
            .where(User.is_active.is_(True))
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def update_last_login(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> User | None:
        """
        Update user's last login timestamp.

        Args:
            session: Database session.
            user_id: User ID.

        Returns:
            Updated user or None if not found.
        """
        user = await self.get_by_id(session, user_id)
        if user:
            user.last_login = datetime.now(timezone.utc)
            await session.flush()
            return user
        return None

    async def upsert_from_oidc(
        self,
        session: AsyncSession,
        *,
        external_id: str,
        user_name: str,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
        roles: list[str] | None = None,
        groups: list[str] | None = None,
    ) -> User:
        """
        Create or update user from OIDC token data.

        Args:
            session: Database session.
            external_id: External ID from OIDC provider.
            user_name: Username.
            email: Email address.
            first_name: First name.
            last_name: Last name.
            roles: User roles.
            groups: User groups.

        Returns:
            Created or updated user.
        """
        user = await self.get_by_external_id(session, external_id)

        if user:
            user.user_name = user_name
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.roles = roles or []
            user.groups = groups or []
            user.last_login = datetime.now(timezone.utc)
            user.last_update = datetime.now(timezone.utc)
            await session.flush()
        else:
            user = User(
                external_id=external_id,
                user_name=user_name,
                email=email,
                first_name=first_name,
                last_name=last_name,
                roles=roles or [],
                groups=groups or [],
                last_login=datetime.now(timezone.utc),
            )
            session.add(user)
            await session.flush()
            await session.refresh(user)

        return user


user_crud = UserCRUD()
