"""GoogleCredential ORM model for shared Google OAuth2 tokens."""

from typing import TYPE_CHECKING

from echomind_lib.db.models.base import (
    ARRAY,
    TIMESTAMP,
    Base,
    ForeignKey,
    Integer,
    Mapped,
    Text,
    datetime,
    mapped_column,
    relationship,
    utcnow,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.user import User


class GoogleCredential(Base):
    """Shared Google OAuth2 credentials for all Google connectors per user.

    One row per user. All Google connectors (Drive, Gmail, Calendar, Contacts)
    for the same user share these tokens. Tokens are refreshed in-place.
    """

    __tablename__ = "google_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    granted_scopes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    client_secret: Mapped[str] = mapped_column(Text, nullable=False)
    creation_date: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, default=utcnow
    )
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)

    user: Mapped["User"] = relationship(back_populates="google_credential")
