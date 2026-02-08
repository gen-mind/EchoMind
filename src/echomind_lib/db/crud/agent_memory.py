"""
AgentMemory CRUD operations.
"""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase
from echomind_lib.db.models import AgentMemory


class AgentMemoryCRUD(CRUDBase[AgentMemory]):
    """
    CRUD operations for AgentMemory model.

    Memories have optional expiration via expires_at field.
    """

    def __init__(self):
        """Initialize AgentMemoryCRUD."""
        super().__init__(AgentMemory)

    async def get_by_user(
        self,
        session: AsyncSession,
        user_id: int,
        *,
        memory_type: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[AgentMemory]:
        """
        Get memories for a user.

        Args:
            session: Database session.
            user_id: User ID.
            memory_type: Optional filter by type (episodic, semantic, procedural).
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of memories ordered by importance.
        """
        query = (
            select(AgentMemory)
            .where(AgentMemory.user_id == user_id)
        )
        if memory_type:
            query = query.where(AgentMemory.memory_type == memory_type)
        query = (
            query
            .order_by(AgentMemory.importance_score.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(query)
        return result.scalars().all()

    async def get_active_by_user(
        self,
        session: AsyncSession,
        user_id: int,
        *,
        memory_type: str | None = None,
        limit: int = 100,
    ) -> Sequence[AgentMemory]:
        """
        Get non-expired memories for a user.

        Args:
            session: Database session.
            user_id: User ID.
            memory_type: Optional filter by type.
            limit: Maximum number to return.

        Returns:
            List of active memories.
        """
        now = datetime.now(timezone.utc)
        query = (
            select(AgentMemory)
            .where(AgentMemory.user_id == user_id)
            .where(
                (AgentMemory.expires_at.is_(None)) |
                (AgentMemory.expires_at > now)
            )
        )
        if memory_type:
            query = query.where(AgentMemory.memory_type == memory_type)
        query = (
            query
            .order_by(AgentMemory.importance_score.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        return result.scalars().all()

    async def get_by_session(
        self,
        session: AsyncSession,
        source_session_id: int,
    ) -> Sequence[AgentMemory]:
        """
        Get memories created from a specific chat session.

        Args:
            session: Database session.
            source_session_id: Source chat session ID.

        Returns:
            List of memories.
        """
        result = await session.execute(
            select(AgentMemory)
            .where(AgentMemory.source_session_id == source_session_id)
        )
        return result.scalars().all()

    async def count_by_user(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> int:
        """
        Count memories for a user.

        Args:
            session: Database session.
            user_id: User ID.

        Returns:
            Memory count.
        """
        result = await session.execute(
            select(func.count(AgentMemory.id))
            .where(AgentMemory.user_id == user_id)
        )
        return result.scalar_one()

    async def increment_access(
        self,
        session: AsyncSession,
        memory_id: int,
    ) -> AgentMemory | None:
        """
        Increment access count and update last_accessed_at.

        Args:
            session: Database session.
            memory_id: Memory ID.

        Returns:
            Updated memory or None.
        """
        memory = await self.get_by_id(session, memory_id)
        if memory:
            memory.access_count += 1
            memory.last_accessed_at = datetime.now(timezone.utc)
            await session.flush()
            return memory
        return None

    async def update_importance(
        self,
        session: AsyncSession,
        memory_id: int,
        importance_score: float,
    ) -> AgentMemory | None:
        """
        Update memory importance score.

        Args:
            session: Database session.
            memory_id: Memory ID.
            importance_score: New importance score (0.0 - 1.0).

        Returns:
            Updated memory or None.
        """
        memory = await self.get_by_id(session, memory_id)
        if memory:
            memory.importance_score = max(0.0, min(1.0, importance_score))
            memory.last_update = datetime.now(timezone.utc)
            await session.flush()
            return memory
        return None

    async def delete_expired(
        self,
        session: AsyncSession,
        user_id: int | None = None,
    ) -> int:
        """
        Delete expired memories.

        Args:
            session: Database session.
            user_id: Optional filter by user.

        Returns:
            Number of memories deleted.
        """
        now = datetime.now(timezone.utc)
        query = (
            select(AgentMemory)
            .where(AgentMemory.expires_at.isnot(None))
            .where(AgentMemory.expires_at <= now)
        )
        if user_id:
            query = query.where(AgentMemory.user_id == user_id)
        result = await session.execute(query)
        memories = result.scalars().all()
        count = len(memories)
        for m in memories:
            await session.delete(m)
        await session.flush()
        return count

    async def delete_by_user(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> int:
        """
        Delete all memories for a user.

        Args:
            session: Database session.
            user_id: User ID.

        Returns:
            Number of memories deleted.
        """
        result = await session.execute(
            select(AgentMemory)
            .where(AgentMemory.user_id == user_id)
        )
        memories = result.scalars().all()
        count = len(memories)
        for m in memories:
            await session.delete(m)
        await session.flush()
        return count


agent_memory_crud = AgentMemoryCRUD()
