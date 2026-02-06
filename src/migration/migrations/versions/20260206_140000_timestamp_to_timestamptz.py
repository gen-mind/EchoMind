"""Convert all TIMESTAMP columns to TIMESTAMPTZ.

Revision ID: 20260206_140000
Revises: 20260206_130000
Create Date: 2026-02-06 14:00:00.000000

Converts all timestamp columns from TIMESTAMP (timezone-naive) to
TIMESTAMPTZ (timezone-aware). PostgreSQL interprets existing naive values
as UTC during the conversion, which is correct since all timestamps in
the application are stored in UTC.

This fixes the asyncpg 0.31+ strict type checking that rejects
timezone-aware Python datetimes for naive DB columns.

See: https://www.postgresql.org/docs/current/datatype-datetime.html
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "20260206_140000"
down_revision: Union[str, None] = "20260206_130000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All tables and their timestamp columns to convert
_TIMESTAMP_COLUMNS: list[tuple[str, list[str]]] = [
    ("users", ["creation_date", "last_update", "last_login"]),
    ("llms", ["creation_date", "last_update", "deleted_date"]),
    ("embedding_models", ["creation_date", "last_update", "deleted_date"]),
    ("assistants", ["creation_date", "last_update", "deleted_date"]),
    ("connectors", ["last_sync_at", "creation_date", "last_update", "deleted_date"]),
    ("documents", ["creation_date", "last_update"]),
    ("chat_sessions", ["creation_date", "last_update", "last_message_at", "deleted_date"]),
    ("chat_messages", ["creation_date", "last_update"]),
    ("chat_message_feedbacks", ["creation_date", "last_update"]),
    ("chat_message_documents", ["creation_date", "last_update"]),
    ("agent_memories", ["last_accessed_at", "creation_date", "last_update", "expires_at"]),
    ("teams", ["creation_date", "last_update", "deleted_date"]),
    ("team_members", ["added_at"]),
]


def upgrade() -> None:
    """Convert all TIMESTAMP columns to TIMESTAMPTZ."""
    for table, columns in _TIMESTAMP_COLUMNS:
        for col in columns:
            op.alter_column(
                table,
                col,
                type_=TIMESTAMP(timezone=True),
                existing_type=TIMESTAMP(timezone=False),
                existing_nullable=True,
            )


def downgrade() -> None:
    """Revert TIMESTAMPTZ columns back to TIMESTAMP."""
    for table, columns in _TIMESTAMP_COLUMNS:
        for col in columns:
            op.alter_column(
                table,
                col,
                type_=TIMESTAMP(timezone=False),
                existing_type=TIMESTAMP(timezone=True),
                existing_nullable=True,
            )
