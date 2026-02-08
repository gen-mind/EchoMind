"""Repair: ensure teams schema exists.

Revision ID: 20260206_130000
Revises: 20260206_010000
Create Date: 2026-02-06 13:00:00.000000

Idempotent migration that ensures all objects from 002_add_teams exist.
Handles the case where alembic_version was stamped past 002_add_teams
without actually running its DDL (e.g. via `alembic stamp head`).

Safe to run on both fresh databases (no-op) and broken ones (repair).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260206_130000"
down_revision: Union[str, None] = "20260206_010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """
    Check if a table exists in the database.

    Args:
        table_name: Name of the table to check.

    Returns:
        True if the table exists.
    """
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_schema = 'public' AND table_name = :name"
            ")"
        ),
        {"name": table_name},
    )
    return result.scalar()


def _column_exists(table_name: str, column_name: str) -> bool:
    """
    Check if a column exists on a table.

    Args:
        table_name: Name of the table.
        column_name: Name of the column to check.

    Returns:
        True if the column exists.
    """
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.columns "
            "  WHERE table_schema = 'public' "
            "    AND table_name = :table AND column_name = :col"
            ")"
        ),
        {"table": table_name, "col": column_name},
    )
    return result.scalar()


def _index_exists(index_name: str) -> bool:
    """
    Check if an index exists.

    Args:
        index_name: Name of the index.

    Returns:
        True if the index exists.
    """
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM pg_indexes "
            "  WHERE indexname = :name"
            ")"
        ),
        {"name": index_name},
    )
    return result.scalar()


def _constraint_exists(constraint_name: str) -> bool:
    """
    Check if a constraint exists.

    Args:
        constraint_name: Name of the constraint.

    Returns:
        True if the constraint exists.
    """
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.table_constraints "
            "  WHERE constraint_name = :name"
            ")"
        ),
        {"name": constraint_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Ensure teams, team_members tables and connectors.team_id exist."""
    # ============================================
    # TEAMS TABLE
    # ============================================
    if not _table_exists("teams"):
        op.create_table(
            "teams",
            sa.Column("id", sa.SmallInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("leader_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column(
                "creation_date",
                postgresql.TIMESTAMP(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("last_update", postgresql.TIMESTAMP(), nullable=True),
            sa.Column("user_id_last_update", sa.Integer(), nullable=True),
            sa.Column("deleted_date", postgresql.TIMESTAMP(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
            sa.ForeignKeyConstraint(["leader_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["user_id_last_update"], ["users.id"]),
        )

    if not _index_exists("ix_teams_name"):
        op.create_index("ix_teams_name", "teams", ["name"])
    if not _index_exists("ix_teams_leader_id"):
        op.create_index("ix_teams_leader_id", "teams", ["leader_id"])
    if not _index_exists("ix_teams_deleted_date"):
        op.create_index("ix_teams_deleted_date", "teams", ["deleted_date"])

    # ============================================
    # TEAM_MEMBERS TABLE
    # ============================================
    if not _table_exists("team_members"):
        op.create_table(
            "team_members",
            sa.Column("team_id", sa.SmallInteger(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "role", sa.String(20), nullable=False, server_default="'member'"
            ),
            sa.Column(
                "added_at",
                postgresql.TIMESTAMP(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("added_by", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("team_id", "user_id"),
            sa.ForeignKeyConstraint(
                ["team_id"], ["teams.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["added_by"], ["users.id"]),
        )

    if not _index_exists("ix_team_members_user_id"):
        op.create_index("ix_team_members_user_id", "team_members", ["user_id"])
    if not _index_exists("ix_team_members_role"):
        op.create_index("ix_team_members_role", "team_members", ["role"])

    # ============================================
    # ADD team_id TO CONNECTORS (if missing)
    # ============================================
    if not _column_exists("connectors", "team_id"):
        op.add_column(
            "connectors",
            sa.Column("team_id", sa.SmallInteger(), nullable=True),
        )

    if not _constraint_exists("fk_connectors_team_id"):
        op.create_foreign_key(
            "fk_connectors_team_id",
            "connectors",
            "teams",
            ["team_id"],
            ["id"],
        )

    if not _index_exists("ix_connectors_team_id"):
        op.create_index("ix_connectors_team_id", "connectors", ["team_id"])


def downgrade() -> None:
    """No-op downgrade - original 002_add_teams handles teardown."""
    pass
