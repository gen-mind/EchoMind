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
            logger.info("🗄️ Database is ready")
            engine.dispose()
            return True
        except OperationalError as e:
            logger.warning(
                f"⏳ Waiting for database (attempt {attempt + 1}/{retries}): {str(e)[:100]}"
            )
            time.sleep(delay)
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to database: {e}")
            time.sleep(delay)

    logger.error(f"❌ Database not ready after {retries} retries")
    engine.dispose()
    return False


def _get_alembic_config(database_url: str) -> Config:
    """
    Create Alembic config with correct paths.

    Args:
        database_url: PostgreSQL connection URL.

    Returns:
        Configured Alembic Config object.

    Raises:
        SystemExit: If alembic.ini not found.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    alembic_ini = os.path.join(script_dir, "alembic.ini")

    if not os.path.exists(alembic_ini):
        logger.error(f"❌ alembic.ini not found at {alembic_ini}")
        sys.exit(1)

    alembic_cfg = Config(alembic_ini)
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option(
        "script_location", os.path.join(script_dir, "migrations")
    )
    return alembic_cfg


def log_available_migrations(database_url: str) -> None:
    """
    Log all available migration files and which are pending.

    Args:
        database_url: PostgreSQL connection URL.
    """
    try:
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext

        alembic_cfg = _get_alembic_config(database_url)
        script = ScriptDirectory.from_config(alembic_cfg)

        engine = create_engine(database_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
        engine.dispose()

        # List all revisions in order
        revisions = list(script.walk_revisions())
        revisions.reverse()  # oldest first

        # Build set of applied revisions by walking back from current
        applied: set[str] = set()
        if current_rev:
            check = script.get_revision(current_rev)
            while check is not None:
                applied.add(check.revision)
                down = check.down_revision
                check = script.get_revision(down) if down else None

        logger.info(f"📋 Found {len(revisions)} migration(s) in chain:")
        for rev in revisions:
            is_applied = rev.revision in applied
            marker = "✅" if is_applied else "⏳"
            label = "applied" if is_applied else "PENDING"
            desc = rev.doc.split("\n")[0][:60] if rev.doc else "no description"
            logger.info(f"  {marker} {rev.revision} - {desc} [{label}]")

    except Exception as e:
        logger.warning(f"⚠️ Could not list migrations: {e}")


def run_migrations(database_url: str) -> None:
    """
    Run Alembic migrations to latest revision.

    Args:
        database_url: PostgreSQL connection URL.

    Raises:
        SystemExit: If migrations fail.
    """
    try:
        alembic_cfg = _get_alembic_config(database_url)

        logger.info("🚀 Running migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("🏁 Migrations completed")

    except Exception as e:
        logger.exception(f"❌ Migration failed: {e}")
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
        from alembic.runtime.migration import MigrationContext

        engine = create_engine(database_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
        engine.dispose()
        return current_rev

    except Exception as e:
        logger.warning(f"⚠️ Could not get current revision: {e}")
        return None


def verify_schema(database_url: str) -> None:
    """
    Verify critical schema objects exist after migration.

    Catches cases where alembic_version was stamped but DDL was not applied.
    Fails hard so broken deployments don't silently start with missing schema.

    Args:
        database_url: PostgreSQL connection URL.

    Raises:
        SystemExit: If required schema objects are missing.
    """
    # Table -> list of required columns
    required_schema: dict[str, list[str]] = {
        "users": ["id", "email"],
        "connectors": ["id", "team_id"],
        "teams": ["id", "name"],
        "team_members": ["team_id", "user_id"],
        "llms": ["id", "provider", "model_id"],
        "documents": ["id", "connector_id"],
        "chat_sessions": ["id", "user_id"],
    }

    engine = create_engine(database_url)
    errors: list[str] = []

    try:
        with engine.connect() as conn:
            for table, columns in required_schema.items():
                # Check table exists
                result = conn.execute(
                    text(
                        "SELECT EXISTS ("
                        "  SELECT 1 FROM information_schema.tables "
                        "  WHERE table_schema = 'public' AND table_name = :name"
                        ")"
                    ),
                    {"name": table},
                )
                if not result.scalar():
                    errors.append(f"Table '{table}' does not exist")
                    continue

                # Check required columns
                for col in columns:
                    result = conn.execute(
                        text(
                            "SELECT EXISTS ("
                            "  SELECT 1 FROM information_schema.columns "
                            "  WHERE table_schema = 'public' "
                            "    AND table_name = :table AND column_name = :col"
                            ")"
                        ),
                        {"table": table, "col": col},
                    )
                    if not result.scalar():
                        errors.append(
                            f"Column '{table}.{col}' does not exist"
                        )
    finally:
        engine.dispose()

    if errors:
        for err in errors:
            logger.error(f"❌ Schema verification failed: {err}")
        logger.error(
            "💀 Database schema is out of sync with alembic_version. "
            "Migrations were stamped but DDL was not applied."
        )
        sys.exit(1)

    logger.info("✅ Schema verification passed")


def main() -> None:
    """
    Main entry point for migration service.

    Waits for database, then runs all pending migrations.
    """
    logger.info("🛠️ EchoMind Migration Service starting...")

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
        logger.info(f"📍 Current DB revision: {current_rev}")
    else:
        logger.info("📍 No migrations applied yet (fresh database)")

    # Show all migrations and their status
    log_available_migrations(database_url)

    # Run migrations
    run_migrations(database_url)

    # Log post-migration state
    new_rev = get_current_revision(database_url)
    if new_rev != current_rev:
        logger.info(f"📍 Upgraded: {current_rev} → {new_rev}")
    else:
        logger.info(f"📍 Already at latest revision: {new_rev}")

    # Verify critical schema objects exist after migration
    verify_schema(database_url)

    logger.info("🎉 Migration service completed")


if __name__ == "__main__":
    main()
