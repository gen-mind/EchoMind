"""Team and TeamMember ORM models."""

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
    utcnow,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.connector import Connector
    from echomind_lib.db.models.user import User


class Team(Base):
    """Teams for grouping users and their resources (connectors, documents)."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    leader_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    creation_date: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, default=utcnow
    )
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    deleted_date: Mapped[datetime | None] = mapped_column(TIMESTAMP)

    # Relationships
    leader: Mapped["User | None"] = relationship(
        "User", foreign_keys=[leader_id], lazy="selectin"
    )
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], lazy="selectin"
    )
    members: Mapped[list["TeamMember"]] = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan", lazy="selectin"
    )
    connectors: Mapped[list["Connector"]] = relationship(
        "Connector", back_populates="team", foreign_keys="Connector.team_id"
    )


class TeamMember(Base):
    """Team membership with role (member or lead)."""

    __tablename__ = "team_members"

    team_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, default=utcnow
    )
    added_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="members")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    adder: Mapped["User"] = relationship("User", foreign_keys=[added_by], lazy="selectin")
