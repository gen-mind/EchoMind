"""
LLM CRUD operations.
"""

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase, SoftDeleteMixin
from echomind_lib.db.models import LLM


class LLMCRUD(SoftDeleteMixin[LLM], CRUDBase[LLM]):
    """
    CRUD operations for LLM model.

    LLMs support soft delete via deleted_date field.
    """

    def __init__(self):
        """Initialize LLMCRUD."""
        super().__init__(LLM)

    async def get_active_llms(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[LLM]:
        """
        Get active LLMs (not deleted and is_active=True).

        Args:
            session: Database session.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of active LLMs.
        """
        result = await session.execute(
            select(LLM)
            .where(LLM.deleted_date.is_(None))
            .where(LLM.is_active.is_(True))
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_default(
        self,
        session: AsyncSession,
    ) -> LLM | None:
        """
        Get the default LLM.

        Args:
            session: Database session.

        Returns:
            Default LLM or None.
        """
        result = await session.execute(
            select(LLM)
            .where(LLM.deleted_date.is_(None))
            .where(LLM.is_default.is_(True))
            .where(LLM.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_provider(
        self,
        session: AsyncSession,
        provider: str,
    ) -> Sequence[LLM]:
        """
        Get LLMs by provider type.

        Args:
            session: Database session.
            provider: Provider name (openai, anthropic, tgi, vllm, ollama).

        Returns:
            List of LLMs with that provider.
        """
        result = await session.execute(
            select(LLM)
            .where(LLM.deleted_date.is_(None))
            .where(LLM.provider == provider)
        )
        return result.scalars().all()

    async def set_default(
        self,
        session: AsyncSession,
        llm_id: int,
        user_id: int | None = None,
    ) -> LLM | None:
        """
        Set an LLM as default, clearing others.

        Args:
            session: Database session.
            llm_id: LLM to set as default.
            user_id: User making the change.

        Returns:
            Updated LLM or None if not found.
        """
        # Clear existing default
        result = await session.execute(
            select(LLM)
            .where(LLM.deleted_date.is_(None))
            .where(LLM.is_default.is_(True))
        )
        for llm in result.scalars().all():
            llm.is_default = False

        # Set new default
        llm = await self.get_by_id_active(session, llm_id)
        if llm:
            llm.is_default = True
            if user_id:
                llm.user_id_last_update = user_id
            await session.flush()
            return llm
        return None


llm_crud = LLMCRUD()
