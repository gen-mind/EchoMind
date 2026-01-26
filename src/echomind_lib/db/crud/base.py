"""
Base CRUD class with common database operations.

All model-specific CRUD classes inherit from this base.
"""

from datetime import datetime
from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.connection import Base

ModelT = TypeVar("ModelT", bound=Base)


class CRUDBase(Generic[ModelT]):
    """
    Base class for CRUD operations.

    Provides common database operations for all models.
    Model-specific CRUD classes should inherit from this.

    Args:
        model: The SQLAlchemy model class.
    """

    def __init__(self, model: type[ModelT]):
        """
        Initialize CRUD with model class.

        Args:
            model: SQLAlchemy model class.
        """
        self.model = model

    async def get_by_id(
        self,
        session: AsyncSession,
        id: int | str,
    ) -> ModelT | None:
        """
        Get a single record by ID.

        Args:
            session: Database session.
            id: Record ID.

        Returns:
            Model instance or None if not found.
        """
        result = await session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelT]:
        """
        Get multiple records with pagination.

        Args:
            session: Database session.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of model instances.
        """
        result = await session.execute(
            select(self.model).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def count(self, session: AsyncSession) -> int:
        """
        Count total records.

        Args:
            session: Database session.

        Returns:
            Total count.
        """
        result = await session.execute(
            select(func.count(self.model.id))
        )
        return result.scalar_one()

    async def create(
        self,
        session: AsyncSession,
        *,
        obj_in: dict[str, Any],
    ) -> ModelT:
        """
        Create a new record.

        Args:
            session: Database session.
            obj_in: Dictionary of field values.

        Returns:
            Created model instance.
        """
        db_obj = self.model(**obj_in)
        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        session: AsyncSession,
        *,
        db_obj: ModelT,
        obj_in: dict[str, Any],
    ) -> ModelT:
        """
        Update an existing record.

        Args:
            session: Database session.
            db_obj: Existing model instance.
            obj_in: Dictionary of fields to update.

        Returns:
            Updated model instance.
        """
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def delete(
        self,
        session: AsyncSession,
        *,
        id: int | str,
    ) -> bool:
        """
        Hard delete a record.

        Args:
            session: Database session.
            id: Record ID.

        Returns:
            True if deleted, False if not found.
        """
        db_obj = await self.get_by_id(session, id)
        if db_obj:
            await session.delete(db_obj)
            await session.flush()
            return True
        return False


class SoftDeleteMixin(Generic[ModelT]):
    """
    Mixin for models that support soft delete.

    Requires model to have 'deleted_date' column.
    """

    model: type[ModelT]

    async def get_by_id_active(
        self,
        session: AsyncSession,
        id: int | str,
    ) -> ModelT | None:
        """
        Get a single active (not deleted) record by ID.

        Args:
            session: Database session.
            id: Record ID.

        Returns:
            Model instance or None if not found or deleted.
        """
        result = await session.execute(
            select(self.model)
            .where(self.model.id == id)
            .where(self.model.deleted_date.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_multi_active(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelT]:
        """
        Get multiple active (not deleted) records with pagination.

        Args:
            session: Database session.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of model instances.
        """
        result = await session.execute(
            select(self.model)
            .where(self.model.deleted_date.is_(None))
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_active(self, session: AsyncSession) -> int:
        """
        Count active (not deleted) records.

        Args:
            session: Database session.

        Returns:
            Total count of active records.
        """
        result = await session.execute(
            select(func.count(self.model.id))
            .where(self.model.deleted_date.is_(None))
        )
        return result.scalar_one()

    async def soft_delete(
        self,
        session: AsyncSession,
        *,
        id: int | str,
        user_id: int | None = None,
    ) -> bool:
        """
        Soft delete a record by setting deleted_date.

        Args:
            session: Database session.
            id: Record ID.
            user_id: ID of user performing deletion.

        Returns:
            True if deleted, False if not found or already deleted.
        """
        db_obj = await self.get_by_id_active(session, id)
        if db_obj:
            db_obj.deleted_date = datetime.utcnow()
            if hasattr(db_obj, "user_id_last_update") and user_id:
                db_obj.user_id_last_update = user_id
            await session.flush()
            return True
        return False
