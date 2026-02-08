"""ChatMessage, ChatMessageFeedback, and ChatMessageDocument ORM models."""

from typing import TYPE_CHECKING, Any

from echomind_lib.db.models.base import (
    JSONB,
    TIMESTAMP,
    Base,
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Mapped,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    datetime,
    mapped_column,
    relationship,
    utcnow,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.chat_session import ChatSession
    from echomind_lib.db.models.document import Document


class ChatMessage(Base):
    """Individual messages within chat sessions."""
    
    __tablename__ = "chat_messages"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_message_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chat_messages.id"))
    rephrased_query: Mapped[str | None] = mapped_column(Text)
    retrieval_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    
    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    parent_message: Mapped["ChatMessage | None"] = relationship(remote_side=[id])
    feedbacks: Mapped[list["ChatMessageFeedback"]] = relationship(back_populates="message", cascade="all, delete-orphan")
    message_documents: Mapped[list["ChatMessageDocument"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class ChatMessageFeedback(Base):
    """User feedback on assistant messages."""
    
    __tablename__ = "chat_message_feedbacks"
    __table_args__ = (
        UniqueConstraint("chat_message_id", "user_id", name="uq_feedback_message_user"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    is_positive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback_text: Mapped[str | None] = mapped_column(Text)
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    
    message: Mapped[ChatMessage] = relationship(back_populates="feedbacks")


class ChatMessageDocument(Base):
    """Documents cited in chat messages."""
    
    __tablename__ = "chat_message_documents"
    __table_args__ = (
        UniqueConstraint("chat_message_id", "document_id", "chunk_id", name="uq_message_document_chunk"),
    )
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[str | None] = mapped_column(Text)
    relevance_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    
    message: Mapped[ChatMessage] = relationship(back_populates="message_documents")
    document: Mapped["Document"] = relationship(back_populates="message_documents")
