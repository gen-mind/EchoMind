"""AgentMemory ORM model."""

from typing import TYPE_CHECKING

from echomind_lib.db.models.base import (
    TIMESTAMP,
    Base,
    ForeignKey,
    Integer,
    Mapped,
    Numeric,
    String,
    Text,
    datetime,
    mapped_column,
    relationship,
    utcnow,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.user import User


class AgentMemory(Base):
    """Long-term agent memory for personalization."""
    
    __tablename__ = "agent_memories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[str | None] = mapped_column(Text)
    importance_score: Mapped[float] = mapped_column(Numeric(3, 2), default=0.5)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    source_session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("chat_sessions.id"))
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    
    user: Mapped["User"] = relationship(back_populates="agent_memories", foreign_keys=[user_id])
