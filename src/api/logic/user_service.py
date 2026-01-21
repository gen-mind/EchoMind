"""
User business logic service.

Handles all user-related business operations, keeping routes thin.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.logic.exceptions import NotFoundError
from echomind_lib.db.models import User as UserORM
from echomind_lib.models.public import (
    ListUsersResponse,
    UpdateUserRequest,
    User,
)


class UserService:
    """Service for user-related business logic."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_id(self, user_id: int) -> User:
        """
        Get a user by ID.
        
        Args:
            user_id: The ID of the user to retrieve.
            
        Returns:
            User: The user data.
            
        Raises:
            NotFoundError: If user not found.
        """
        result = await self.db.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            raise NotFoundError("User", user_id)
        
        return User.model_validate(db_user, from_attributes=True)
    
    async def update_user(
        self,
        user_id: int,
        updates: UpdateUserRequest,
        updated_by_user_id: int,
    ) -> User:
        """
        Update a user's profile.
        
        Args:
            user_id: The ID of the user to update.
            updates: The fields to update.
            updated_by_user_id: The ID of the user performing the update.
            
        Returns:
            User: The updated user data.
            
        Raises:
            NotFoundError: If user not found.
        """
        result = await self.db.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            raise NotFoundError("User", user_id)
        
        if updates.first_name:
            db_user.first_name = updates.first_name
        if updates.last_name:
            db_user.last_name = updates.last_name
        if updates.preferences is not None:
            prefs = db_user.preferences.copy() if db_user.preferences else {}
            if updates.preferences.default_assistant_id:
                prefs["default_assistant_id"] = updates.preferences.default_assistant_id
            if updates.preferences.theme:
                prefs["theme"] = updates.preferences.theme
            db_user.preferences = prefs
        
        db_user.user_id_last_update = updated_by_user_id
        
        return User.model_validate(db_user, from_attributes=True)
    
    async def list_users(
        self,
        page: int = 1,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> ListUsersResponse:
        """
        List users with pagination.
        
        Args:
            page: Page number (1-indexed).
            limit: Number of items per page.
            is_active: Optional filter by active status.
            
        Returns:
            ListUsersResponse: Paginated list of users.
        """
        query = select(UserORM)
        
        if is_active is not None:
            query = query.where(UserORM.is_active == is_active)
        
        # Count total
        count_query = select(UserORM.id)
        if is_active is not None:
            count_query = count_query.where(UserORM.is_active == is_active)
        count_result = await self.db.execute(count_query)
        total = len(count_result.all())
        
        # Paginate
        query = query.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(query)
        db_users = result.scalars().all()
        
        users = [User.model_validate(u, from_attributes=True) for u in db_users]
        
        return ListUsersResponse(users=users)
