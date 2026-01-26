"""
EmbeddingModel CRUD operations.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase, SoftDeleteMixin
from echomind_lib.db.models import EmbeddingModel


class EmbeddingModelCRUD(SoftDeleteMixin[EmbeddingModel], CRUDBase[EmbeddingModel]):
    """
    CRUD operations for EmbeddingModel.

    EmbeddingModels are cluster-wide configurations.
    Only one can be active at a time.
    """

    def __init__(self):
        """Initialize EmbeddingModelCRUD."""
        super().__init__(EmbeddingModel)

    async def get_active(
        self,
        session: AsyncSession,
    ) -> EmbeddingModel | None:
        """
        Get the currently active embedding model.

        Args:
            session: Database session.

        Returns:
            Active embedding model or None.
        """
        result = await session.execute(
            select(EmbeddingModel)
            .where(EmbeddingModel.deleted_date.is_(None))
            .where(EmbeddingModel.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_model_id(
        self,
        session: AsyncSession,
        model_id: str,
    ) -> EmbeddingModel | None:
        """
        Get embedding model by model_id string.

        Args:
            session: Database session.
            model_id: Model identifier string.

        Returns:
            Embedding model or None.
        """
        result = await session.execute(
            select(EmbeddingModel)
            .where(EmbeddingModel.deleted_date.is_(None))
            .where(EmbeddingModel.model_id == model_id)
        )
        return result.scalar_one_or_none()

    async def set_active(
        self,
        session: AsyncSession,
        embedding_model_id: int,
        user_id: int | None = None,
    ) -> EmbeddingModel | None:
        """
        Set an embedding model as active, deactivating others.

        Args:
            session: Database session.
            embedding_model_id: Model to activate.
            user_id: User making the change.

        Returns:
            Activated model or None if not found.
        """
        # Deactivate all
        result = await session.execute(
            select(EmbeddingModel)
            .where(EmbeddingModel.deleted_date.is_(None))
            .where(EmbeddingModel.is_active.is_(True))
        )
        for model in result.scalars().all():
            model.is_active = False

        # Activate selected
        model = await self.get_by_id_active(session, embedding_model_id)
        if model:
            model.is_active = True
            if user_id:
                model.user_id_last_update = user_id
            await session.flush()
            return model
        return None


embedding_model_crud = EmbeddingModelCRUD()
