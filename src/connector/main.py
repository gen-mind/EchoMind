"""
EchoMind Connector Service Entry Point.

NATS subscriber that fetches files from external sources (Google Drive, OneDrive)
and uploads them to MinIO for processing.

Usage:
    python main.py

Environment Variables:
    CONNECTOR_ENABLED: Enable connector service (default: true)
    CONNECTOR_HEALTH_PORT: Health check port (default: 8080)
    CONNECTOR_DATABASE_URL: PostgreSQL connection URL
    CONNECTOR_NATS_URL: NATS server URL
    CONNECTOR_MINIO_ENDPOINT: MinIO endpoint
    CONNECTOR_LOG_LEVEL: Logging level (default: INFO)
"""

import asyncio
import logging
import os
import signal
import sys
import threading
from typing import Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from echomind_lib.constants import MinioBuckets
from echomind_lib.db.connection import close_db, get_db_manager, init_db
from echomind_lib.db.minio import close_minio, get_minio, init_minio
from echomind_lib.db.nats_publisher import (
    close_nats_publisher,
    get_nats_publisher,
    init_nats_publisher,
)
from echomind_lib.db.nats_subscriber import (
    JetStreamSubscriber,
    close_nats_subscriber,
    init_nats_subscriber,
)
from echomind_lib.helpers.readiness_probe import HealthServer

from echomind_lib.helpers.langfuse_helper import init_langfuse, shutdown_langfuse, create_trace

from connector.config import get_settings
from connector.logic.connector_service import ConnectorService

# Configure logging
logging.basicConfig(
    level=os.getenv("CONNECTOR_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("echomind-connector")


class ConnectorApp:
    """
    Main connector application.

    Manages lifecycle of NATS subscriber, database, and MinIO connections.
    Uses graceful degradation - service starts even if some connections fail,
    with background retry for failed connections.
    """

    def __init__(self) -> None:
        """Initialize connector application."""
        self._settings = get_settings()
        self._subscriber: JetStreamSubscriber | None = None
        self._health_server: HealthServer | None = None
        self._running = False
        self._retry_tasks: list[asyncio.Task[None]] = []

        # Connection status flags
        self._db_connected = False
        self._minio_connected = False
        self._nats_pub_connected = False
        self._nats_sub_connected = False

    async def start(self) -> None:
        """
        Start the connector service.

        Initializes all connections with graceful degradation.
        Service starts even if some connections fail, with background retry.
        """
        logger.info("🛠️ Starting EchoMind Connector Service...")
        logger.info("📋 Configuration:")
        logger.info(f"   Enabled: {self._settings.enabled}")
        logger.info(f"   Health port: {self._settings.health_port}")
        logger.info(f"   Database: {self._mask_url(self._settings.database_url)}")
        logger.info(f"   NATS: {self._settings.nats_url}")
        logger.info(f"   MinIO: {self._settings.minio_endpoint}")

        if not self._settings.enabled:
            logger.warning("⚠️ Connector is disabled via configuration")
            return

        # Start health server FIRST - service must respond to health checks
        self._health_server = HealthServer(port=self._settings.health_port)
        health_thread = threading.Thread(
            target=self._health_server.start,
            daemon=True,
        )
        health_thread.start()
        logger.info(f"💓 Health server started on port {self._settings.health_port}")

        # Initialize services with graceful degradation
        # Each service failure spawns a background retry task

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

        # Initialize MinIO
        logger.info("🛠️ Connecting to MinIO...")
        try:
            await init_minio(
                endpoint=self._settings.minio_endpoint,
                access_key=self._settings.minio_access_key,
                secret_key=self._settings.minio_secret_key,
                secure=self._settings.minio_secure,
                ensure_buckets=MinioBuckets.all(),
            )
            self._minio_connected = True
            logger.info(f"📦 MinIO connected (buckets: {MinioBuckets.all()})")
        except Exception as e:
            logger.warning(f"⚠️ MinIO connection failed: {e}")
            logger.info("🔄 Will retry MinIO connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_minio_connection())
            )

        # Initialize NATS publisher
        logger.info("🛠️ Connecting to NATS (publisher)...")
        try:
            await init_nats_publisher(
                servers=[self._settings.nats_url],
                user=self._settings.nats_user if self._settings.nats_user else None,
                password=(
                    self._settings.nats_password
                    if self._settings.nats_password
                    else None
                ),
            )
            self._nats_pub_connected = True
            logger.info("📡 NATS publisher connected")
        except Exception as e:
            logger.warning(f"⚠️ NATS publisher connection failed: {e}")
            logger.info("🔄 Will retry NATS publisher connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_nats_pub_connection())
            )

        # Initialize NATS subscriber
        logger.info("🛠️ Connecting to NATS (subscriber)...")
        try:
            self._subscriber = await init_nats_subscriber(
                servers=[self._settings.nats_url],
                user=self._settings.nats_user if self._settings.nats_user else None,
                password=(
                    self._settings.nats_password
                    if self._settings.nats_password
                    else None
                ),
            )
            self._nats_sub_connected = True
            logger.info("📥 NATS subscriber connected")

            # Setup subscriptions only if NATS connected
            await self._setup_subscriptions()
        except Exception as e:
            logger.warning(f"⚠️ NATS subscriber connection failed: {e}")
            logger.info("🔄 Will retry NATS subscriber connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_nats_sub_connection())
            )

        # Initialize Langfuse (LLM observability)
        init_langfuse()

        # Update readiness based on connection status
        self._update_readiness()
        self._running = True

        if self._is_ready():
            logger.info("🚀 Connector ready and listening")
        else:
            logger.warning("⚠️ Connector started but waiting for connections...")

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

    async def _retry_minio_connection(self) -> None:
        """Background task to retry MinIO connection."""
        while not self._minio_connected:
            await asyncio.sleep(30)
            try:
                await init_minio(
                    endpoint=self._settings.minio_endpoint,
                    access_key=self._settings.minio_access_key,
                    secret_key=self._settings.minio_secret_key,
                    secure=self._settings.minio_secure,
                    ensure_buckets=MinioBuckets.all(),
                )
                self._minio_connected = True
                logger.info(f"📦 MinIO reconnected (buckets: {MinioBuckets.all()})")
                self._update_readiness()
            except Exception as e:
                logger.warning(f"⚠️ MinIO reconnection attempt failed: {e}")

    async def _retry_nats_pub_connection(self) -> None:
        """Background task to retry NATS publisher connection."""
        while not self._nats_pub_connected:
            await asyncio.sleep(30)
            try:
                await init_nats_publisher(
                    servers=[self._settings.nats_url],
                    user=(
                        self._settings.nats_user
                        if self._settings.nats_user
                        else None
                    ),
                    password=(
                        self._settings.nats_password
                        if self._settings.nats_password
                        else None
                    ),
                )
                self._nats_pub_connected = True
                logger.info("📡 NATS publisher reconnected")
                self._update_readiness()
            except Exception as e:
                logger.warning(f"⚠️ NATS publisher reconnection attempt failed: {e}")

    async def _retry_nats_sub_connection(self) -> None:
        """Background task to retry NATS subscriber connection."""
        while not self._nats_sub_connected:
            await asyncio.sleep(30)
            try:
                self._subscriber = await init_nats_subscriber(
                    servers=[self._settings.nats_url],
                    user=(
                        self._settings.nats_user
                        if self._settings.nats_user
                        else None
                    ),
                    password=(
                        self._settings.nats_password
                        if self._settings.nats_password
                        else None
                    ),
                )
                self._nats_sub_connected = True
                logger.info("📥 NATS subscriber reconnected")
                await self._setup_subscriptions()
                self._update_readiness()
            except Exception as e:
                logger.warning(f"⚠️ NATS subscriber reconnection attempt failed: {e}")

    def _is_ready(self) -> bool:
        """Check if all required services are connected."""
        return (
            self._db_connected
            and self._minio_connected
            and self._nats_pub_connected
            and self._nats_sub_connected
        )

    def _update_readiness(self) -> None:
        """Update health server readiness based on connection status."""
        if self._health_server:
            ready = self._is_ready()
            self._health_server.set_ready(ready)
            if ready:
                logger.info("🚀 All services connected - marking as ready")

    async def _setup_subscriptions(self) -> None:
        """Set up NATS subscriptions for connector sync events."""
        if not self._subscriber:
            return

        subjects = [
            "connector.sync.google_drive",
            "connector.sync.gmail",
            "connector.sync.google_calendar",
            "connector.sync.google_contacts",
            "connector.sync.onedrive",
        ]

        for subject in subjects:
            await self._subscriber.subscribe(
                stream=self._settings.nats_stream_name,
                consumer=f"{self._settings.nats_consumer_name}-{subject.split('.')[-1]}",
                subject=subject,
                handler=self._handle_sync_message,
            )
            logger.info(f"📥 Subscribed to {subject}")

    async def _handle_sync_message(self, msg: Any) -> None:
        """
        Handle incoming sync message from NATS.

        Args:
            msg: NATS message with ConnectorSyncRequest payload.
        """
        # Check if all services are ready before processing
        if not self._is_ready():
            logger.warning("⚠️ Message received but services not ready, will NAK")
            await msg.nak()
            return

        start_time = asyncio.get_event_loop().time()

        try:
            # Parse message
            # Generated protobuf lacks type stubs
            from echomind_lib.models.internal.orchestrator_pb2 import (  # type: ignore[import-untyped]
                ConnectorSyncRequest,
            )

            request = ConnectorSyncRequest()
            request.ParseFromString(msg.data)

            connector_id = request.connector_id
            logger.info(f"🔄 Received sync request for connector {connector_id}")

            # Create Langfuse trace for this sync operation
            trace = create_trace(
                name="connector-sync",
                metadata={
                    "connector_id": connector_id,
                    "chunking_session": request.chunking_session,
                },
                tags=["connector", "sync"],
            )

            # Process sync
            db = get_db_manager()
            minio = get_minio()
            publisher = get_nats_publisher()

            async with db.session() as session:
                service = ConnectorService(
                    db_session=session,
                    minio_client=minio,
                    nats_publisher=publisher,
                    minio_bucket=self._settings.minio_bucket,
                )

                try:
                    docs_processed = await service.sync_connector(
                        connector_id=connector_id,
                        chunking_session=request.chunking_session,
                    )
                    trace.update(
                        output={"documents_processed": docs_processed},
                    )
                    logger.info(
                        f"✅ Sync completed for connector {connector_id}: {docs_processed} documents"
                    )
                    await msg.ack()
                finally:
                    await service.close()

        except Exception as e:
            logger.exception(f"❌ Sync message handling failed: {e}")
            await msg.nak()

        finally:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"⏰ Message processing time: {elapsed:.2f}s")

    async def stop(self) -> None:
        """
        Stop the connector service gracefully.

        Shuts down subscriber, closes database and MinIO connections.
        """
        logger.info("🛑 Connector shutting down...")
        self._running = False

        if self._health_server:
            self._health_server.set_ready(False)

        # Cancel all retry tasks
        for task in self._retry_tasks:
            task.cancel()

        # Close connections (ignore errors for cleanup)
        try:
            await close_nats_subscriber()
            logger.info("📥 NATS subscriber disconnected")
        except Exception:
            pass

        try:
            await close_nats_publisher()
            logger.info("📡 NATS publisher disconnected")
        except Exception:
            pass

        try:
            close_minio()
            logger.info("📦 MinIO disconnected")
        except Exception:
            pass

        try:
            await close_db()
            logger.info("🗄️ Database disconnected")
        except Exception:
            pass

        try:
            shutdown_langfuse()
        except Exception:
            pass

        logger.info("👋 Connector stopped")

    def _mask_url(self, url: str) -> str:
        """Mask password in connection URL for logging."""
        if "@" in url and ":" in url.split("@")[0]:
            parts = url.split("@")
            user_pass = parts[0].split("://")
            if len(user_pass) > 1:
                credentials = user_pass[1]
                if ":" in credentials:
                    user = credentials.split(":")[0]
                    return f"{user_pass[0]}://{user}:***@{parts[1]}"
        return url


async def main() -> None:
    """Main entry point."""
    app = ConnectorApp()

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("⚠️ Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await app.start()
        await stop_event.wait()

    except KeyboardInterrupt:
        logger.info("⚠️ Received keyboard interrupt")

    except Exception as e:
        logger.exception(f"💀 Fatal error: {e}")

    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
