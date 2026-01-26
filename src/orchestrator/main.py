"""
EchoMind Orchestrator Service Entry Point.

Lightweight scheduler that triggers connector syncs via NATS.
Uses APScheduler for job scheduling.

Usage:
    python main.py

Environment Variables:
    ORCHESTRATOR_ENABLED: Enable scheduling (default: true)
    ORCHESTRATOR_CHECK_INTERVAL_SECONDS: Sync check interval (default: 60)
    ORCHESTRATOR_HEALTH_PORT: Health check port (default: 8080)
    ORCHESTRATOR_DATABASE_URL: PostgreSQL connection URL
    ORCHESTRATOR_NATS_URL: NATS server URL
    ORCHESTRATOR_LOG_LEVEL: Logging level (default: INFO)
"""

import asyncio
import logging
import os
import signal
import sys
import threading

# APScheduler doesn't provide type stubs
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-not-found]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-not-found]

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from echomind_lib.db.connection import init_db, close_db, get_db_manager
from echomind_lib.db.nats_publisher import (
    init_nats_publisher,
    close_nats_publisher,
    get_nats_publisher,
)
from echomind_lib.helpers.readiness_probe import HealthServer

from orchestrator.config import get_settings
from orchestrator.logic.orchestrator_service import OrchestratorService

# Configure logging
logging.basicConfig(
    level=os.getenv("ORCHESTRATOR_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("echomind-orchestrator")


class Orchestrator:
    """
    Main orchestrator application.

    Manages lifecycle of scheduler, database, and NATS connections.
    """

    def __init__(self):
        """Initialize orchestrator."""
        self._settings = get_settings()
        self._scheduler: AsyncIOScheduler | None = None
        self._health_server: HealthServer | None = None
        self._running = False

    async def start(self) -> None:
        """
        Start the orchestrator service.

        Initializes:
        - Database connection
        - NATS publisher
        - APScheduler
        - Health check server
        """
        logger.info("🚀 EchoMind Orchestrator Service starting...")
        logger.info("📋 Configuration:")
        logger.info("   Enabled: %s", self._settings.enabled)
        logger.info("   Check interval: %d seconds", self._settings.check_interval_seconds)
        logger.info("   Health port: %d", self._settings.health_port)
        logger.info("   Database: %s", self._mask_url(self._settings.database_url))
        logger.info("   NATS: %s", self._settings.nats_url)

        if not self._settings.enabled:
            logger.warning("⚠️ Orchestrator is disabled via configuration")
            return

        # Initialize database
        logger.info("🔌 Connecting to database...")
        try:
            await init_db(
                self._settings.database_url,
                echo=self._settings.database_echo,
            )
            logger.info("✅ Database connected")
        except Exception as e:
            logger.error("❌ Database connection failed: %s", e)
            raise

        # Initialize NATS publisher
        logger.info("🔌 Connecting to NATS...")
        try:
            await init_nats_publisher(
                servers=[self._settings.nats_url],
                user=self._settings.nats_user,
                password=self._settings.nats_password,
                timeout=self._settings.nats_connect_timeout,
            )
            logger.info("✅ NATS connected")
        except Exception as e:
            logger.error("❌ NATS connection failed: %s", e)
            await close_db()
            raise

        # Start health server
        self._health_server = HealthServer(port=self._settings.health_port)
        health_thread = threading.Thread(target=self._health_server.start, daemon=True)
        health_thread.start()
        logger.info("💓 Health server started on port %d", self._settings.health_port)

        # Initialize scheduler
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._sync_check_job,
            trigger=IntervalTrigger(seconds=self._settings.check_interval_seconds),
            id="connector_sync_check",
            name="Connector Sync Check",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(
            "🕐 Scheduler started (interval: %d seconds)",
            self._settings.check_interval_seconds,
        )

        # Mark as ready
        self._health_server.set_ready(True)
        self._running = True
        logger.info("✅ Orchestrator ready")

    async def stop(self) -> None:
        """
        Stop the orchestrator service gracefully.

        Shuts down scheduler, closes database and NATS connections.
        """
        logger.info("🛑 Orchestrator shutting down...")
        self._running = False

        # Mark as not ready
        if self._health_server:
            self._health_server.set_ready(False)

        # Stop scheduler
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("🕐 Scheduler stopped")

        # Close NATS
        await close_nats_publisher()
        logger.info("📡 NATS disconnected")

        # Close database
        await close_db()
        logger.info("🔌 Database disconnected")

        logger.info("👋 Orchestrator stopped")

    async def _sync_check_job(self) -> None:
        """
        Job that checks for connectors due for sync.

        Called by APScheduler on the configured interval.
        """
        if not self._running:
            return

        try:
            db = get_db_manager()
            publisher = get_nats_publisher()

            async with db.session() as session:
                service = OrchestratorService(session, publisher)
                triggered = await service.check_and_trigger_syncs()

                if triggered > 0:
                    logger.info("📊 Sync check complete: %d triggered", triggered)

        except Exception as e:
            logger.exception("❌ Sync check job failed: %s", e)

    def _mask_url(self, url: str) -> str:
        """Mask password in connection URL for logging."""
        if "@" in url and ":" in url.split("@")[0]:
            parts = url.split("@")
            user_pass = parts[0].split(":")
            if len(user_pass) > 2:
                return f"{user_pass[0]}:{user_pass[1]}:***@{parts[1]}"
        return url


async def main() -> None:
    """Main entry point."""
    orchestrator = Orchestrator()

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await orchestrator.start()

        # Wait for stop signal
        await stop_event.wait()

    except KeyboardInterrupt:
        logger.info("🛑 Received keyboard interrupt")
    except Exception as e:
        logger.exception("💀 Fatal error: %s", e)
        sys.exit(1)
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
