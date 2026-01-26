"""
ChatSession CRUD operations.
"""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase, SoftDeleteMixin
from echomind_lib.db.models import ChatSession


class ChatSessionCRUD(SoftDeleteMixin[ChatSession], CRUDBase[ChatSession]):
    """
    CRUD operations for ChatSession model.

    Chat sessions support soft delete via deleted_date field.
    """

    def __init__(self):
        """Initialize ChatSessionCRUD."""
        super().__init__(ChatSession)

    async def get_by_user(
        self,
        session: AsyncSession,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ChatSession]:
        """
        Get chat sessions for a user.

        Args:
            session: Database session.
            user_id: User ID.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of chat sessions ordered by last activity.
        """
        result = await session.execute(
            select(ChatSession)
            .where(ChatSession.deleted_date.is_(None))
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.last_message_at.desc().nullsfirst())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_user_and_assistant(
        self,
        session: AsyncSession,
        user_id: int,
        assistant_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ChatSession]:
        """
        Get chat sessions for a user with specific assistant.

        Args:
            session: Database session.
            user_id: User ID.
            assistant_id: Assistant ID.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of chat sessions.
        """
        result = await session.execute(
            select(ChatSession)
            .where(ChatSession.deleted_date.is_(None))
            .where(ChatSession.user_id == user_id)
            .where(ChatSession.assistant_id == assistant_id)
            .order_by(ChatSession.last_message_at.desc().nullsfirst())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_by_user(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> int:
        """
        Count active chat sessions for a user.

        Args:
            session: Database session.
            user_id: User ID.

        Returns:
            Session count.
        """
        result = await session.execute(
            select(func.count(ChatSession.id))
            .where(ChatSession.deleted_date.is_(None))
            .where(ChatSession.user_id == user_id)
        )
        return result.scalar_one()

    async def update_title(
        self,
        session: AsyncSession,
        chat_session_id: int,
        title: str,
        user_id: int | None = None,
    ) -> ChatSession | None:
        """
        Update chat session title.

        Args:
            session: Database session.
            chat_session_id: Chat session ID.
            title: New title.
            user_id: User making the change.

        Returns:
            Updated session or None.
        """
        chat_session = await self.get_by_id_active(session, chat_session_id)
        if chat_session:
            chat_session.title = title
            chat_session.last_update = datetime.now(timezone.utc)
            if user_id:
                chat_session.user_id_last_update = user_id
            await session.flush()
            return chat_session
        return None

    async def increment_message_count(
        self,
        session: AsyncSession,
        chat_session_id: int,
    ) -> ChatSession | None:
        """
        Increment message count and update last_message_at.

        Args:
            session: Database session.
            chat_session_id: Chat session ID.

        Returns:
            Updated session or None.
        """
        chat_session = await self.get_by_id_active(session, chat_session_id)
        if chat_session:
            chat_session.message_count += 1
            chat_session.last_message_at = datetime.now(timezone.utc)
            chat_session.last_update = datetime.now(timezone.utc)
            await session.flush()
            return chat_session
        return None


chat_session_crud = ChatSessionCRUD()
