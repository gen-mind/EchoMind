"""LLM ORM model."""

from typing import TYPE_CHECKING

from echomind_lib.db.models.base import (
    TIMESTAMP,
    Base,
    Boolean,
    ForeignKey,
    Integer,
    Mapped,
    Numeric,
    SmallInteger,
    String,
    datetime,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.assistant import Assistant


class LLM(Base):
    """LLM provider configurations."""
    
    __tablename__ = "llms"
    
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str | None] = mapped_column(String)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), default=0.7)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    deleted_date: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    
    assistants: Mapped[list["Assistant"]] = relationship(back_populates="llm")
