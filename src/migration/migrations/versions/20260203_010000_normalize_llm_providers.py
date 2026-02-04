"""Normalize LLM provider values.

Revision ID: 003_normalize_llm_providers
Revises: 002_add_teams
Create Date: 2026-02-03 01:00:00.000000

Migrates legacy provider values to new canonical names:
- tgi, vllm, openai, ollama, LLM_PROVIDER_* -> openai-compatible
- anthropic, LLM_PROVIDER_ANTHROPIC -> anthropic
- anthropic-token, LLM_PROVIDER_ANTHROPIC_TOKEN -> anthropic-token
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_normalize_llm_providers"
down_revision: Union[str, None] = "002_add_teams"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Normalize LLM provider values to canonical names."""

    # Migrate legacy OpenAI-compatible providers
    op.execute("""
        UPDATE llms
        SET provider = 'openai-compatible'
        WHERE LOWER(provider) IN (
            'tgi', 'vllm', 'openai', 'ollama',
            'llm_provider_tgi', 'llm_provider_vllm',
            'llm_provider_openai', 'llm_provider_ollama',
            'llm_provider_openai_compatible', 'openai_compatible'
        )
    """)

    # Migrate Anthropic API provider
    op.execute("""
        UPDATE llms
        SET provider = 'anthropic'
        WHERE LOWER(provider) IN (
            'llm_provider_anthropic'
        )
        AND LOWER(provider) != 'anthropic'
    """)

    # Migrate Anthropic Token (Claude CLI) provider
    op.execute("""
        UPDATE llms
        SET provider = 'anthropic-token'
        WHERE LOWER(provider) IN (
            'anthropic_token', 'llm_provider_anthropic_token'
        )
        AND LOWER(provider) != 'anthropic-token'
    """)


def downgrade() -> None:
    """Revert to legacy enum names (best effort - may not match original values)."""

    op.execute("""
        UPDATE llms
        SET provider = 'LLM_PROVIDER_OPENAI'
        WHERE provider = 'openai-compatible'
    """)

    op.execute("""
        UPDATE llms
        SET provider = 'LLM_PROVIDER_ANTHROPIC'
        WHERE provider = 'anthropic'
    """)

    op.execute("""
        UPDATE llms
        SET provider = 'LLM_PROVIDER_ANTHROPIC_TOKEN'
        WHERE provider = 'anthropic-token'
    """)
