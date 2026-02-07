"""Connector ORM model."""

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
    SmallInteger,
    String,
    Text,
    datetime,
    mapped_column,
    relationship,
    utcnow,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.document import Document
    from echomind_lib.db.models.google_credential import GoogleCredential
    from echomind_lib.db.models.team import Team
    from echomind_lib.db.models.user import User


class Connector(Base):
    """Data source connectors (Teams, Google Drive, etc.)."""
    
    __tablename__ = "connectors"
    
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    refresh_freq_minutes: Mapped[int | None] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    scope_id: Mapped[str | None] = mapped_column(Text)
    team_id: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("teams.id"))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    status_message: Mapped[str | None] = mapped_column(Text)
    last_sync_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    docs_analyzed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    deleted_date: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    google_credential_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("google_credentials.id", ondelete="SET NULL")
    )

    user: Mapped["User"] = relationship(back_populates="connectors", foreign_keys=[user_id])
    team: Mapped["Team | None"] = relationship(back_populates="connectors", foreign_keys=[team_id])
    documents: Mapped[list["Document"]] = relationship(back_populates="connector")
    google_credential: Mapped["GoogleCredential | None"] = relationship()
