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
    Implements graceful degradation: retries failed connections in background.
    """

    def __init__(self):
        """Initialize orchestrator."""
        self._settings = get_settings()
        self._scheduler: AsyncIOScheduler | None = None
        self._health_server: HealthServer | None = None
        self._running = False
        self._db_connected = False
        self._nats_connected = False
        self._retry_tasks: list[asyncio.Task] = []

    def _is_ready(self) -> bool:
        """Check if all required connections are established."""
        return self._db_connected and self._nats_connected

    def _update_readiness(self) -> None:
        """Update health server readiness based on connection state."""
        if self._health_server:
            self._health_server.set_ready(self._is_ready())

    async def start(self) -> None:
        """
        Start the orchestrator service.

        Initializes:
        - Health check server (always starts first)
        - Database connection (retries on failure)
        - NATS publisher (retries on failure)
        - APScheduler (starts immediately, jobs skip if not ready)
        """
        logger.info("🚀 EchoMind Orchestrator Service starting...")
        logger.info("📋 Configuration:")
        logger.info(f"   ⚙️ Enabled: {self._settings.enabled}")
        logger.info(f"   ⏱️ Check interval: {self._settings.check_interval_seconds} seconds")
        logger.info(f"   🔌 Health port: {self._settings.health_port}")
        logger.info(f"   🗄️ Database: {self._mask_url(self._settings.database_url)}")
        logger.info(f"   📡 NATS: {self._settings.nats_url}")

        if not self._settings.enabled:
            logger.warning("⚠️ Orchestrator is disabled via configuration")
            return

        # Start health server first (Kubernetes needs it)
        self._health_server = HealthServer(port=self._settings.health_port)
        health_thread = threading.Thread(target=self._health_server.start, daemon=True)
        health_thread.start()
        logger.info(f"💓 Health server started on port {self._settings.health_port}")

        # Initialize database
        logger.info("🛠️ Connecting to database...")
        try:
            await init_db(
                self._settings.database_url,
                echo=self._settings.database_echo,
            )
            self._db_connected = True
            logger.info("🗄️ Database connected")
        except Exception as e:
            logger.warning(f"⚠️ Database connection failed: {e}")
            logger.info("🔄 Will retry database connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_db_connection())
            )

        # Initialize NATS publisher
        logger.info("🛠️ Connecting to NATS...")
        try:
            await self._init_nats()
            self._nats_connected = True
            logger.info("📡 NATS publisher connected")
        except Exception as e:
            logger.warning(f"⚠️ NATS connection failed: {e}")
            logger.info("🔄 Will retry NATS connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_nats_connection())
            )

        # Initialize scheduler (starts immediately — jobs check _is_ready())
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
            f"🕐 Scheduler started (interval: {self._settings.check_interval_seconds} seconds)"
        )

        # Update readiness
        self._update_readiness()
        self._running = True

        if self._is_ready():
            logger.info("🚀 Orchestrator ready")
        else:
            logger.warning("⚠️ Orchestrator started with degraded connectivity, retrying...")

    async def _init_nats(self) -> None:
        """
        Initialize NATS publisher and create JetStream streams.

        Raises:
            Exception: If NATS connection fails.
        """
        publisher = await init_nats_publisher(
            servers=[self._settings.nats_url],
            user=self._settings.nats_user,
            password=self._settings.nats_password,
            timeout=self._settings.nats_connect_timeout,
        )

        # Create JetStream stream if it doesn't exist
        try:
            await publisher.create_stream(
                name=self._settings.nats_stream_name,
                subjects=[
                    "connector.sync.*",
                    "document.process",
                ],
            )
            logger.info(
                f"✅ NATS stream '{self._settings.nats_stream_name}' ready"
            )
        except Exception as e:
            if "already in use" not in str(e).lower():
                logger.warning(f"⚠️ Stream creation warning: {e}")

        # Create DLQ advisory stream for Guardian service
        try:
            await publisher.create_stream(
                name=self._settings.nats_dlq_stream_name,
                subjects=[
                    f"$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.{self._settings.nats_stream_name}.>",
                    f"$JS.EVENT.ADVISORY.CONSUMER.MSG_TERMINATED.{self._settings.nats_stream_name}.>",
                ],
            )
            logger.info(
                f"✅ NATS DLQ stream '{self._settings.nats_dlq_stream_name}' ready"
            )
        except Exception as e:
            if "already in use" not in str(e).lower():
                logger.warning(f"⚠️ DLQ stream creation warning: {e}")

    async def _retry_db_connection(self) -> None:
        """Background task to retry database connection."""
        while not self._db_connected:
            await asyncio.sleep(30)
            try:
                await init_db(
                    self._settings.database_url,
                    echo=self._settings.database_echo,
                )
                self._db_connected = True
                logger.info("🗄️ Database reconnected")
                self._update_readiness()
            except Exception as e:
                logger.warning(f"⚠️ Database reconnection attempt failed: {e}")

    async def _retry_nats_connection(self) -> None:
        """Background task to retry NATS connection."""
        while not self._nats_connected:
            await asyncio.sleep(30)
            try:
                await self._init_nats()
                self._nats_connected = True
                logger.info("📡 NATS reconnected")
                self._update_readiness()
            except Exception as e:
                logger.warning(f"⚠️ NATS reconnection attempt failed: {e}")

    async def stop(self) -> None:
        """
        Stop the orchestrator service gracefully.

        Cancels retry tasks, shuts down scheduler, closes connections.
        """
        logger.info("🛑 Orchestrator shutting down...")
        self._running = False

        # Mark as not ready
        if self._health_server:
            self._health_server.set_ready(False)

        # Cancel retry tasks
        for task in self._retry_tasks:
            task.cancel()

        # Stop scheduler
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("🕐 Scheduler stopped")

        # Close NATS
        await close_nats_publisher()
        logger.info("📡 NATS disconnected")

        # Close database
        await close_db()
        logger.info("🗄️ Database disconnected")

        logger.info("👋 Orchestrator stopped")

    async def _sync_check_job(self) -> None:
        """
        Job that checks for connectors due for sync.

        Called by APScheduler on the configured interval.
        Skips execution if not all connections are ready.
        """
        if not self._running or not self._is_ready():
            return

        try:
            db = get_db_manager()
            publisher = get_nats_publisher()

            async with db.session() as session:
                service = OrchestratorService(session, publisher)
                triggered = await service.check_and_trigger_syncs()

                if triggered > 0:
                    logger.info(f"📊 Sync check complete: {triggered} triggered")

        except Exception as e:
            logger.exception(f"❌ Sync check job failed: {e}")

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
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
