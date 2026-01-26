"""
Alembic migration environment configuration.

This module configures Alembic to work with EchoMind's SQLAlchemy models.
It imports all models from echomind_lib to ensure they are registered
with Base.metadata before migrations run.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

# Add src directory to path for echomind_lib imports
# Path: alembic/ -> migration/ -> src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Import Base and all models to register them with metadata
# This import is critical - it ensures all models are loaded
from echomind_lib.db.connection import Base

# Import all models explicitly to register them with Base.metadata
# Without this, Alembic won't see the tables
from echomind_lib.db.models import (  # noqa: F401
    AgentMemory,
    Assistant,
    ChatMessage,
    ChatMessageDocument,
    ChatMessageFeedback,
    ChatSession,
    Connector,
    Document,
    EmbeddingModel,
    LLM,
    User,
)

# Alembic Config object
config = context.config

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata

# Override sqlalchemy.url with environment variable if present
database_url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
if database_url:
    # Convert asyncpg URL to psycopg2 for sync Alembic operations
    if "asyncpg" in database_url:
        database_url = database_url.replace("postgresql+asyncpg", "postgresql")
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This generates SQL scripts without connecting to the database.
    Useful for reviewing migrations before applying them.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates a connection to the database and runs migrations
    within a transaction.
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detect column type changes
            compare_server_default=True,  # Detect default value changes
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
