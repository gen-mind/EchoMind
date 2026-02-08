"""Assistant ORM model."""

from typing import TYPE_CHECKING

from echomind_lib.db.models.base import (
    JSONB,
    TIMESTAMP,
    Base,
    Boolean,
    ForeignKey,
    Integer,
    Mapped,
    SmallInteger,
    String,
    Text,
    datetime,
    mapped_column,
    relationship,
    utcnow,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.chat_session import ChatSession
    from echomind_lib.db.models.llm import LLM


class Assistant(Base):
    """AI assistant configurations with custom prompts."""
    
    __tablename__ = "assistants"
    
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    llm_id: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("llms.id"))
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    task_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    starter_messages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_priority: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    deleted_date: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    
    llm: Mapped["LLM | None"] = relationship(back_populates="assistants")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="assistant")
