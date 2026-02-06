"""
ChatMessage, ChatMessageFeedback, and ChatMessageDocument CRUD operations.
"""

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase
from echomind_lib.db.models import ChatMessage, ChatMessageDocument, ChatMessageFeedback


class ChatMessageCRUD(CRUDBase[ChatMessage]):
    """
    CRUD operations for ChatMessage model.

    Messages are cascade deleted with their session.
    """

    def __init__(self):
        """Initialize ChatMessageCRUD."""
        super().__init__(ChatMessage)

    async def get_by_session(
        self,
        session: AsyncSession,
        chat_session_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ChatMessage]:
        """
        Get messages for a chat session.

        Args:
            session: Database session.
            chat_session_id: Chat session ID.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of messages ordered by creation date.
        """
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .order_by(ChatMessage.creation_date)
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_recent_by_session(
        self,
        session: AsyncSession,
        chat_session_id: int,
        limit: int = 10,
    ) -> Sequence[ChatMessage]:
        """
        Get most recent messages for a chat session.

        Args:
            session: Database session.
            chat_session_id: Chat session ID.
            limit: Number of messages to return.

        Returns:
            List of most recent messages (oldest first).
        """
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .order_by(ChatMessage.creation_date.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # Return oldest first
        return messages

    async def count_by_session(
        self,
        session: AsyncSession,
        chat_session_id: int,
    ) -> int:
        """
        Count messages in a chat session.

        Args:
            session: Database session.
            chat_session_id: Chat session ID.

        Returns:
            Message count.
        """
        result = await session.execute(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.chat_session_id == chat_session_id)
        )
        return result.scalar_one()

    async def create_user_message(
        self,
        session: AsyncSession,
        chat_session_id: int,
        content: str,
        parent_message_id: int | None = None,
    ) -> ChatMessage:
        """
        Create a user message.

        Args:
            session: Database session.
            chat_session_id: Chat session ID.
            content: Message content.
            parent_message_id: Optional parent message ID.

        Returns:
            Created message.
        """
        message = ChatMessage(
            chat_session_id=chat_session_id,
            role="user",
            content=content,
            parent_message_id=parent_message_id,
        )
        session.add(message)
        await session.flush()
        await session.refresh(message)
        return message

    async def create_assistant_message(
        self,
        session: AsyncSession,
        chat_session_id: int,
        content: str,
        token_count: int = 0,
        parent_message_id: int | None = None,
        rephrased_query: str | None = None,
        retrieval_context: dict[str, Any] | None = None,
        tool_calls: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ChatMessage:
        """
        Create an assistant message.

        Args:
            session: Database session.
            chat_session_id: Chat session ID.
            content: Message content.
            token_count: Number of tokens used.
            parent_message_id: Optional parent message ID.
            rephrased_query: Query after rephrasing.
            retrieval_context: Retrieved context metadata.
            tool_calls: Tool calls made.
            error: Error message if any.

        Returns:
            Created message.
        """
        message = ChatMessage(
            chat_session_id=chat_session_id,
            role="assistant",
            content=content,
            token_count=token_count,
            parent_message_id=parent_message_id,
            rephrased_query=rephrased_query,
            retrieval_context=retrieval_context,
            tool_calls=tool_calls,
            error=error,
        )
        session.add(message)
        await session.flush()
        await session.refresh(message)
        return message


class ChatMessageFeedbackCRUD(CRUDBase[ChatMessageFeedback]):
    """
    CRUD operations for ChatMessageFeedback model.
    """

    def __init__(self):
        """Initialize ChatMessageFeedbackCRUD."""
        super().__init__(ChatMessageFeedback)

    async def get_by_message(
        self,
        session: AsyncSession,
        chat_message_id: int,
    ) -> Sequence[ChatMessageFeedback]:
        """
        Get feedback for a message.

        Args:
            session: Database session.
            chat_message_id: Chat message ID.

        Returns:
            List of feedback entries.
        """
        result = await session.execute(
            select(ChatMessageFeedback)
            .where(ChatMessageFeedback.chat_message_id == chat_message_id)
        )
        return result.scalars().all()

    async def get_by_user_and_message(
        self,
        session: AsyncSession,
        user_id: int,
        chat_message_id: int,
    ) -> ChatMessageFeedback | None:
        """
        Get feedback from specific user on specific message.

        Args:
            session: Database session.
            user_id: User ID.
            chat_message_id: Chat message ID.

        Returns:
            Feedback or None.
        """
        result = await session.execute(
            select(ChatMessageFeedback)
            .where(ChatMessageFeedback.user_id == user_id)
            .where(ChatMessageFeedback.chat_message_id == chat_message_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        session: AsyncSession,
        user_id: int,
        chat_message_id: int,
        is_positive: bool,
        feedback_text: str | None = None,
    ) -> ChatMessageFeedback:
        """
        Create or update feedback.

        Args:
            session: Database session.
            user_id: User ID.
            chat_message_id: Chat message ID.
            is_positive: Whether feedback is positive.
            feedback_text: Optional text feedback.

        Returns:
            Created or updated feedback.
        """
        existing = await self.get_by_user_and_message(session, user_id, chat_message_id)
        if existing:
            existing.is_positive = is_positive
            existing.feedback_text = feedback_text
            existing.last_update = datetime.now(timezone.utc)
            existing.user_id_last_update = user_id
            await session.flush()
            return existing
        else:
            feedback = ChatMessageFeedback(
                user_id=user_id,
                chat_message_id=chat_message_id,
                is_positive=is_positive,
                feedback_text=feedback_text,
            )
            session.add(feedback)
            await session.flush()
            await session.refresh(feedback)
            return feedback


class ChatMessageDocumentCRUD(CRUDBase[ChatMessageDocument]):
    """
    CRUD operations for ChatMessageDocument model.

    Links messages to cited documents.
    """

    def __init__(self):
        """Initialize ChatMessageDocumentCRUD."""
        super().__init__(ChatMessageDocument)

    async def get_by_message(
        self,
        session: AsyncSession,
        chat_message_id: int,
    ) -> Sequence[ChatMessageDocument]:
        """
        Get document citations for a message.

        Args:
            session: Database session.
            chat_message_id: Chat message ID.

        Returns:
            List of message-document links.
        """
        result = await session.execute(
            select(ChatMessageDocument)
            .where(ChatMessageDocument.chat_message_id == chat_message_id)
            .order_by(ChatMessageDocument.relevance_score.desc().nullsfirst())
        )
        return result.scalars().all()

    async def add_citation(
        self,
        session: AsyncSession,
        chat_message_id: int,
        document_id: int,
        chunk_id: str | None = None,
        relevance_score: float | None = None,
    ) -> ChatMessageDocument:
        """
        Add a document citation to a message.

        Args:
            session: Database session.
            chat_message_id: Chat message ID.
            document_id: Document ID.
            chunk_id: Optional chunk ID.
            relevance_score: Optional relevance score.

        Returns:
            Created citation link.
        """
        citation = ChatMessageDocument(
            chat_message_id=chat_message_id,
            document_id=document_id,
            chunk_id=chunk_id,
            relevance_score=relevance_score,
        )
        session.add(citation)
        await session.flush()
        await session.refresh(citation)
        return citation

    async def add_citations_batch(
        self,
        session: AsyncSession,
        chat_message_id: int,
        citations: list[dict],
    ) -> list[ChatMessageDocument]:
        """
        Add multiple document citations to a message.

        Args:
            session: Database session.
            chat_message_id: Chat message ID.
            citations: List of dicts with document_id, chunk_id, relevance_score.

        Returns:
            List of created citation links.
        """
        results = []
        for c in citations:
            citation = ChatMessageDocument(
                chat_message_id=chat_message_id,
                document_id=c["document_id"],
                chunk_id=c.get("chunk_id"),
                relevance_score=c.get("relevance_score"),
            )
            session.add(citation)
            results.append(citation)
        await session.flush()
        for r in results:
            await session.refresh(r)
        return results


chat_message_crud = ChatMessageCRUD()
chat_message_feedback_crud = ChatMessageFeedbackCRUD()
chat_message_document_crud = ChatMessageDocumentCRUD()
