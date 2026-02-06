"""Seed default LLM for Open WebUI.

Revision ID: 20260206_010000
Revises: 20260203_010000
Create Date: 2026-02-06 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = "20260206_010000"
down_revision = "20260203_010000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Seed a default LLM for the WebUI to use."""
    # Insert default LLMs
    op.execute(
        sa.text("""
            INSERT INTO llms (name, provider, model_id, endpoint, api_key, max_tokens, temperature, is_default, is_active, creation_date)
            VALUES
                ('GPT-4o', 'openai', 'gpt-4o', 'https://api.openai.com/v1', NULL, 4096, 0.7, true, true, NOW()),
                ('GPT-4o Mini', 'openai', 'gpt-4o-mini', 'https://api.openai.com/v1', NULL, 4096, 0.7, false, true, NOW()),
                ('Claude 3.5 Sonnet', 'anthropic', 'claude-3-5-sonnet-20241022', 'https://api.anthropic.com/v1', NULL, 4096, 0.7, false, true, NOW())
            ON CONFLICT (id) DO NOTHING
        """)
    )


def downgrade() -> None:
    """Remove seeded LLMs."""
    op.execute(
        sa.text("""
            DELETE FROM llms
            WHERE model_id IN ('gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet-20241022')
        """)
    )
