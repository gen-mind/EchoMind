"""
Assistant CRUD operations.
"""

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase, SoftDeleteMixin
from echomind_lib.db.models import Assistant


class AssistantCRUD(SoftDeleteMixin[Assistant], CRUDBase[Assistant]):
    """
    CRUD operations for Assistant model.

    Assistants support soft delete via deleted_date field.
    """

    def __init__(self):
        """Initialize AssistantCRUD."""
        super().__init__(Assistant)

    async def get_visible(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Assistant]:
        """
        Get visible assistants ordered by priority.

        Args:
            session: Database session.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of visible assistants.
        """
        result = await session.execute(
            select(Assistant)
            .where(Assistant.deleted_date.is_(None))
            .where(Assistant.is_visible.is_(True))
            .order_by(Assistant.display_priority, Assistant.name)
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_default(
        self,
        session: AsyncSession,
    ) -> Assistant | None:
        """
        Get the default assistant.

        Args:
            session: Database session.

        Returns:
            Default assistant or None.
        """
        result = await session.execute(
            select(Assistant)
            .where(Assistant.deleted_date.is_(None))
            .where(Assistant.is_default.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_llm_id(
        self,
        session: AsyncSession,
        llm_id: int,
    ) -> Sequence[Assistant]:
        """
        Get assistants using a specific LLM.

        Args:
            session: Database session.
            llm_id: LLM ID.

        Returns:
            List of assistants using the LLM.
        """
        result = await session.execute(
            select(Assistant)
            .where(Assistant.deleted_date.is_(None))
            .where(Assistant.llm_id == llm_id)
        )
        return result.scalars().all()

    async def set_default(
        self,
        session: AsyncSession,
        assistant_id: int,
        user_id: int | None = None,
    ) -> Assistant | None:
        """
        Set an assistant as default, clearing others.

        Args:
            session: Database session.
            assistant_id: Assistant to set as default.
            user_id: User making the change.

        Returns:
            Updated assistant or None if not found.
        """
        # Clear existing default
        result = await session.execute(
            select(Assistant)
            .where(Assistant.deleted_date.is_(None))
            .where(Assistant.is_default.is_(True))
        )
        for assistant in result.scalars().all():
            assistant.is_default = False

        # Set new default
        assistant = await self.get_by_id_active(session, assistant_id)
        if assistant:
            assistant.is_default = True
            if user_id:
                assistant.user_id_last_update = user_id
            await session.flush()
            return assistant
        return None


assistant_crud = AssistantCRUD()
