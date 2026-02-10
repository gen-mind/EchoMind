"""Normalize connector types to lowercase strings.

Revision ID: 20260210_033000
Revises: 20260206_140000
Create Date: 2026-02-10 03:30:00

CRITICAL: The database should store connector types as lowercase strings
(e.g., "google_drive"), NOT as protobuf enum names (e.g., "CONNECTOR_TYPE_GOOGLE_DRIVE").

This migration fixes existing connectors that were created with the bug where
data.type.name was used instead of proper enum-to-string conversion.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260210_033000'
down_revision = '20260206_140000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Normalize connector types from enum names to lowercase strings.

    Maps:
      CONNECTOR_TYPE_GOOGLE_DRIVE -> google_drive
      CONNECTOR_TYPE_GMAIL -> gmail
      CONNECTOR_TYPE_GOOGLE_CALENDAR -> google_calendar
      CONNECTOR_TYPE_GOOGLE_CONTACTS -> google_contacts
      CONNECTOR_TYPE_TEAMS -> teams
      CONNECTOR_TYPE_ONEDRIVE -> onedrive
      CONNECTOR_TYPE_WEB -> web
      CONNECTOR_TYPE_FILE -> file
      CONNECTOR_TYPE_UNSPECIFIED -> unspecified
    """
    # Update connector types using CASE statement for safety
    op.execute("""
        UPDATE connectors
        SET type = CASE
            WHEN type = 'CONNECTOR_TYPE_GOOGLE_DRIVE' THEN 'google_drive'
            WHEN type = 'CONNECTOR_TYPE_GMAIL' THEN 'gmail'
            WHEN type = 'CONNECTOR_TYPE_GOOGLE_CALENDAR' THEN 'google_calendar'
            WHEN type = 'CONNECTOR_TYPE_GOOGLE_CONTACTS' THEN 'google_contacts'
            WHEN type = 'CONNECTOR_TYPE_TEAMS' THEN 'teams'
            WHEN type = 'CONNECTOR_TYPE_ONEDRIVE' THEN 'onedrive'
            WHEN type = 'CONNECTOR_TYPE_WEB' THEN 'web'
            WHEN type = 'CONNECTOR_TYPE_FILE' THEN 'file'
            WHEN type = 'CONNECTOR_TYPE_UNSPECIFIED' THEN 'unspecified'
            ELSE type  -- Keep existing value if already normalized
        END
        WHERE type LIKE 'CONNECTOR_TYPE_%';
    """)


def downgrade() -> None:
    """
    Revert connector types from lowercase strings to enum names.

    WARNING: This is lossy - connectors with already-normalized types
    cannot be reverted accurately.
    """
    op.execute("""
        UPDATE connectors
        SET type = CASE
            WHEN type = 'google_drive' THEN 'CONNECTOR_TYPE_GOOGLE_DRIVE'
            WHEN type = 'gmail' THEN 'CONNECTOR_TYPE_GMAIL'
            WHEN type = 'google_calendar' THEN 'CONNECTOR_TYPE_GOOGLE_CALENDAR'
            WHEN type = 'google_contacts' THEN 'CONNECTOR_TYPE_GOOGLE_CONTACTS'
            WHEN type = 'teams' THEN 'CONNECTOR_TYPE_TEAMS'
            WHEN type = 'onedrive' THEN 'CONNECTOR_TYPE_ONEDRIVE'
            WHEN type = 'web' THEN 'CONNECTOR_TYPE_WEB'
            WHEN type = 'file' THEN 'CONNECTOR_TYPE_FILE'
            WHEN type = 'unspecified' THEN 'CONNECTOR_TYPE_UNSPECIFIED'
            ELSE type  -- Keep existing value if not recognized
        END
        WHERE type NOT LIKE 'CONNECTOR_TYPE_%';
    """)
