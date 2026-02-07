"""User ORM model."""

from typing import TYPE_CHECKING

from echomind_lib.db.models.base import (
    ARRAY,
    JSONB,
    TIMESTAMP,
    Base,
    Boolean,
    ForeignKey,
    Integer,
    Mapped,
    String,
    Text,
    datetime,
    mapped_column,
    relationship,
    utcnow,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.agent_memory import AgentMemory
    from echomind_lib.db.models.chat_session import ChatSession
    from echomind_lib.db.models.connector import Connector
    from echomind_lib.db.models.google_credential import GoogleCredential


class User(Base):
    """User accounts synced from Authentik OIDC."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    external_id: Mapped[str | None] = mapped_column(Text)
    roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    groups: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    last_login: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    
    connectors: Mapped[list["Connector"]] = relationship(back_populates="user", foreign_keys="Connector.user_id")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", foreign_keys="ChatSession.user_id")
    agent_memories: Mapped[list["AgentMemory"]] = relationship(back_populates="user", foreign_keys="AgentMemory.user_id")
    google_credential: Mapped["GoogleCredential | None"] = relationship(back_populates="user", uselist=False)
