"""Add google_credentials table and link to connectors.

Revision ID: 20260207_010000
Revises: 20260206_140000
Create Date: 2026-02-07 01:00:00.000000

Creates a shared google_credentials table for storing OAuth2 tokens
that are shared across all Google connectors (Drive, Gmail, Calendar,
Contacts) for a given user. Also adds google_credential_id FK to
the connectors table.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260207_010000"
down_revision = "20260206_140000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add google_credentials table and FK on connectors."""
    # Create google_credentials table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS google_credentials (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            token_expires_at TIMESTAMPTZ,
            granted_scopes TEXT[] NOT NULL DEFAULT '{}',
            client_id TEXT NOT NULL,
            client_secret TEXT NOT NULL,
            creation_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_update TIMESTAMPTZ,
            UNIQUE(user_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_google_credentials_user_id
        ON google_credentials(user_id)
        """
    )

    # Add google_credential_id FK to connectors
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'connectors'
                AND column_name = 'google_credential_id'
            ) THEN
                ALTER TABLE connectors
                ADD COLUMN google_credential_id INTEGER
                REFERENCES google_credentials(id) ON DELETE SET NULL;
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    """Remove google_credential_id FK and google_credentials table."""
    op.execute(
        """
        ALTER TABLE connectors DROP COLUMN IF EXISTS google_credential_id
        """
    )
    op.execute("DROP TABLE IF EXISTS google_credentials")
