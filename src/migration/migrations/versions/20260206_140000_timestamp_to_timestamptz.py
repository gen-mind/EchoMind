"""Convert all TIMESTAMP columns to TIMESTAMPTZ.

Revision ID: 20260206_140000
Revises: 20260206_130000
Create Date: 2026-02-06 14:00:00.000000

Converts all timestamp columns from TIMESTAMP (timezone-naive) to
TIMESTAMPTZ (timezone-aware) using explicit ``AT TIME ZONE 'UTC'``
so that existing naive values are correctly treated as UTC regardless
of the session's TimeZone setting.

This fixes the asyncpg strict type checking that rejects
timezone-aware Python datetimes for naive DB columns.

References:
    - https://www.postgresql.org/docs/current/datatype-datetime.html
    - https://wiki.postgresql.org/wiki/Don't_Do_This#Don.27t_use_timestamp_.28without_time_zone.29
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
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
    """Convert all TIMESTAMP columns to TIMESTAMPTZ.

    Uses ``AT TIME ZONE 'UTC'`` so PostgreSQL treats existing naive
    values as UTC, regardless of the session's ``TimeZone`` setting.
    Without this, PostgreSQL would interpret naive values as local time.
    """
    for table, columns in _TIMESTAMP_COLUMNS:
        for col in columns:
            op.execute(
                text(
                    f'ALTER TABLE "{table}" '
                    f'ALTER COLUMN "{col}" '
                    f"TYPE TIMESTAMPTZ "
                    f"USING \"{col}\" AT TIME ZONE 'UTC'"
                )
            )


def downgrade() -> None:
    """Revert TIMESTAMPTZ columns back to TIMESTAMP."""
    for table, columns in _TIMESTAMP_COLUMNS:
        for col in columns:
            op.execute(
                text(
                    f'ALTER TABLE "{table}" '
                    f'ALTER COLUMN "{col}" '
                    f"TYPE TIMESTAMP WITHOUT TIME ZONE "
                    f"USING \"{col}\" AT TIME ZONE 'UTC'"
                )
            )
