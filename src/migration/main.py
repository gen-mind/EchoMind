"""
EchoMind Migration Service Entry Point.

This service runs Alembic migrations on startup. It is designed to run
as a Kubernetes init container or standalone batch job.

Usage:
    python main.py

Environment Variables:
    MIGRATION_DATABASE_URL: PostgreSQL connection URL
    MIGRATION_RETRY_COUNT: Number of retries if DB not ready (default: 5)
    MIGRATION_RETRY_DELAY: Seconds between retries (default: 5)
    MIGRATION_LOG_LEVEL: Logging level (default: INFO)
"""

import logging
import os
import sys
import time

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Configure logging
logging.basicConfig(
    level=os.getenv("MIGRATION_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("echomind-migration")


def get_database_url() -> str:
    """
    Get database URL from environment.

    Returns:
        PostgreSQL connection URL.

    Raises:
        SystemExit: If DATABASE_URL is not set.
    """
    database_url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")

    if not database_url:
        logger.error("❌ DATABASE_URL or MIGRATION_DATABASE_URL not set")
        sys.exit(1)

    # Convert asyncpg URL to psycopg2 for sync Alembic operations
    if "asyncpg" in database_url:
        database_url = database_url.replace("postgresql+asyncpg", "postgresql")

    return database_url


def wait_for_db(database_url: str, retries: int = 5, delay: int = 5) -> bool:
    """
    Wait for database to be ready.

    Args:
        database_url: PostgreSQL connection URL.
        retries: Number of retry attempts.
        delay: Seconds between retries.

    Returns:
        True if database is ready, False otherwise.
    """
    engine = create_engine(database_url)

    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Database is ready")
            engine.dispose()
            return True
        except OperationalError as e:
            logger.warning(
                "⏳ Waiting for database (attempt %d/%d): %s",
                attempt + 1,
                retries,
                str(e)[:100],
            )
            time.sleep(delay)
        except Exception as e:
            logger.error("❌ Unexpected error connecting to database: %s", e)
            time.sleep(delay)

    logger.error("❌ Database not ready after %d retries", retries)
    engine.dispose()
    return False


def run_migrations(database_url: str) -> None:
    """
    Run Alembic migrations to latest revision.

    Args:
        database_url: PostgreSQL connection URL.

    Raises:
        SystemExit: If migrations fail.
    """
    try:
        # Get path to alembic.ini relative to this file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini = os.path.join(script_dir, "alembic.ini")

        if not os.path.exists(alembic_ini):
            logger.error("❌ alembic.ini not found at %s", alembic_ini)
            sys.exit(1)

        # Create Alembic config
        alembic_cfg = Config(alembic_ini)
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

        # Set script location relative to alembic.ini
        alembic_cfg.set_main_option(
            "script_location", os.path.join(script_dir, "migrations")
        )

        logger.info("🚀 Running migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Migrations completed successfully")

    except Exception as e:
        logger.exception("❌ Migration failed: %s", e)
        sys.exit(1)


def get_current_revision(database_url: str) -> str | None:
    """
    Get current database revision.

    Args:
        database_url: PostgreSQL connection URL.

    Returns:
        Current revision ID or None if no migrations applied.
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini = os.path.join(script_dir, "alembic.ini")

        alembic_cfg = Config(alembic_ini)
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        alembic_cfg.set_main_option(
            "script_location", os.path.join(script_dir, "migrations")
        )

        # Get current revision using Alembic's script directory
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext

        script = ScriptDirectory.from_config(alembic_cfg)
        engine = create_engine(database_url)

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

        engine.dispose()
        return current_rev

    except Exception as e:
        logger.warning("Could not get current revision: %s", e)
        return None


def main() -> None:
    """
    Main entry point for migration service.

    Waits for database, then runs all pending migrations.
    """
    logger.info("🔄 EchoMind Migration Service starting...")

    # Get configuration
    database_url = get_database_url()
    retry_count = int(os.getenv("MIGRATION_RETRY_COUNT", "5"))
    retry_delay = int(os.getenv("MIGRATION_RETRY_DELAY", "5"))

    # Wait for database
    if not wait_for_db(database_url, retries=retry_count, delay=retry_delay):
        sys.exit(1)

    # Log current state
    current_rev = get_current_revision(database_url)
    if current_rev:
        logger.info("📍 Current revision: %s", current_rev)
    else:
        logger.info("📍 No migrations applied yet (fresh database)")

    # Run migrations
    run_migrations(database_url)

    logger.info("🎉 Migration service completed")


if __name__ == "__main__":
    main()
