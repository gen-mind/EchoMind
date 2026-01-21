"""ChatSession ORM model."""

from typing import TYPE_CHECKING

from echomind_lib.db.models.base import (
    TIMESTAMP,
    Base,
    ForeignKey,
    Integer,
    Mapped,
    SmallInteger,
    String,
    Text,
    datetime,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.assistant import Assistant
    from echomind_lib.db.models.chat_message import ChatMessage
    from echomind_lib.db.models.user import User


class ChatSession(Base):
    """Chat sessions between users and assistants."""
    
    __tablename__ = "chat_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    assistant_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("assistants.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="New Chat")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="chat")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    last_message_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    deleted_date: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    
    user: Mapped["User"] = relationship(back_populates="chat_sessions")
    assistant: Mapped["Assistant"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
