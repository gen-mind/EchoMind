"""
EchoMind Ingestor Service - Main Entry Point.

NATS JetStream consumer for document ingestion using nv_ingest_api.
Replaces deprecated semantic, voice, and vision services.
"""

import asyncio
import logging
import os
import signal
import sys
import threading
from typing import Any

# Add parent to path for echomind_lib imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nats.aio.msg import Msg

from echomind_lib.db.connection import close_db, get_db_manager, init_db
from echomind_lib.db.minio import close_minio, get_minio, init_minio
from echomind_lib.db.nats_subscriber import (
    JetStreamSubscriber,
    close_nats_subscriber,
    get_nats_subscriber,
    init_nats_subscriber,
)
from echomind_lib.db.qdrant import close_qdrant, get_qdrant, init_qdrant
from echomind_lib.helpers.readiness_probe import HealthServer
from echomind_lib.models.internal.orchestrator_model import DocumentProcessRequest
from echomind_lib.models.internal.orchestrator_pb2 import (
    DocumentProcessRequest as DocumentProcessRequestProto,
)
from echomind_lib.models.public.connector_model import ConnectorScope

from ingestor.config import get_settings, IngestorSettings
from ingestor.logic.exceptions import IngestorError
from ingestor.logic.ingestor_service import IngestorService
from ingestor.middleware.error_handler import handle_ingestor_error

# Configure logging
logging.basicConfig(
    level=os.getenv("INGESTOR_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("echomind-ingestor")


class IngestorApp:
    """
    Main Ingestor application managing service lifecycle.

    Handles:
    - Database connection management
    - NATS subscription lifecycle
    - MinIO client initialization
    - Qdrant client initialization
    - Health server for Kubernetes probes
    - Graceful shutdown with signal handlers
    - Background retry for failed connections
    """

    def __init__(self) -> None:
        """Initialize the Ingestor application."""
        self._settings = get_settings()
        self._subscriber: JetStreamSubscriber | None = None
        self._health_server: HealthServer | None = None
        self._running = False
        self._retry_tasks: list[asyncio.Task[None]] = []

        # Connection status flags
        self._db_connected = False
        self._minio_connected = False
        self._qdrant_connected = False
        self._nats_connected = False

    async def start(self) -> None:
        """
        Start the Ingestor service.

        Initializes all connections with graceful degradation.
        Service starts even if some connections fail, with background retry.
        """
        logger.info("🛠️ Starting EchoMind Ingestor Service...")
        logger.info("📋 Configuration:")
        logger.info("   Enabled: %s", self._settings.enabled)
        logger.info("   Health port: %d", self._settings.health_port)
        logger.info("   Database: %s", self._mask_url(self._settings.database_url))
        logger.info("   NATS: %s", self._settings.nats_url)
        logger.info("   MinIO: %s", self._settings.minio_endpoint)
        logger.info(
            "   Embedder: %s:%d",
            self._settings.embedder_host,
            self._settings.embedder_port,
        )
        logger.info("   Extract method: %s", self._settings.extract_method)
        logger.info("   Chunk size: %d tokens", self._settings.chunk_size)
        logger.info("   Tokenizer: %s", self._settings.tokenizer)

        if not self._settings.enabled:
            logger.warning("⚠️ Ingestor is disabled via configuration")
            return

        # Start health server FIRST - service must respond to health checks
        self._health_server = HealthServer(port=self._settings.health_port)
        health_thread = threading.Thread(
            target=self._health_server.start,
            daemon=True,
        )
        health_thread.start()
        logger.info("💓 Health server started on port %d", self._settings.health_port)

        # Initialize services with graceful degradation
        # Each service failure spawns a background retry task

        # Initialize database
        logger.info("🔌 Connecting to database...")
        try:
            await init_db(
                self._settings.database_url,
                echo=self._settings.database_echo,
            )
            self._db_connected = True
            logger.info("🗄️ Database connected")
        except Exception as e:
            logger.warning("⚠️ Database connection failed: %s", e)
            logger.info("🔄 Will retry database connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_db_connection())
            )

        # Initialize MinIO
        logger.info("🔌 Connecting to MinIO...")
        try:
            await init_minio(
                endpoint=self._settings.minio_endpoint,
                access_key=self._settings.minio_access_key,
                secret_key=self._settings.minio_secret_key,
                secure=self._settings.minio_secure,
            )
            self._minio_connected = True
            logger.info("📦 MinIO connected")
        except Exception as e:
            logger.warning("⚠️ MinIO connection failed: %s", e)
            logger.info("🔄 Will retry MinIO connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_minio_connection())
            )

        # Initialize Qdrant
        logger.info("🔌 Connecting to Qdrant...")
        try:
            await init_qdrant(
                host=self._settings.qdrant_host,
                port=self._settings.qdrant_port,
                api_key=self._settings.qdrant_api_key or None,
            )
            self._qdrant_connected = True
            logger.info("🔍 Qdrant connected")
        except Exception as e:
            logger.warning("⚠️ Qdrant connection failed: %s", e)
            logger.info("🔄 Will retry Qdrant connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_qdrant_connection())
            )

        # Initialize NATS subscriber
        logger.info("🔌 Connecting to NATS...")
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
            self._nats_connected = True
            logger.info("📥 NATS subscriber connected")

            # Setup subscriptions only if NATS connected
            await self._setup_subscriptions()
        except Exception as e:
            logger.warning("⚠️ NATS connection failed: %s", e)
            logger.info("🔄 Will retry NATS connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_nats_connection())
            )

        # Update readiness based on connection status
        self._update_readiness()
        self._running = True

        if self._is_ready():
            logger.info("🚀 Ingestor ready and listening")
        else:
            logger.warning("⚠️ Ingestor started but waiting for connections...")

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
                logger.warning("⚠️ Database reconnection attempt failed: %s", e)

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
                )
                self._minio_connected = True
                logger.info("📦 MinIO reconnected")
                self._update_readiness()
            except Exception as e:
                logger.warning("⚠️ MinIO reconnection attempt failed: %s", e)

    async def _retry_qdrant_connection(self) -> None:
        """Background task to retry Qdrant connection."""
        while not self._qdrant_connected:
            await asyncio.sleep(30)
            try:
                await init_qdrant(
                    host=self._settings.qdrant_host,
                    port=self._settings.qdrant_port,
                    api_key=self._settings.qdrant_api_key or None,
                )
                self._qdrant_connected = True
                logger.info("🔍 Qdrant reconnected")
                self._update_readiness()
            except Exception as e:
                logger.warning("⚠️ Qdrant reconnection attempt failed: %s", e)

    async def _retry_nats_connection(self) -> None:
        """Background task to retry NATS connection."""
        while not self._nats_connected:
            await asyncio.sleep(30)
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
                self._nats_connected = True
                logger.info("📥 NATS subscriber reconnected")
                await self._setup_subscriptions()
                self._update_readiness()
            except Exception as e:
                logger.warning("⚠️ NATS reconnection attempt failed: %s", e)

    def _is_ready(self) -> bool:
        """Check if all required services are connected."""
        return (
            self._db_connected
            and self._minio_connected
            and self._qdrant_connected
            and self._nats_connected
        )

    def _update_readiness(self) -> None:
        """Update health server readiness based on connection status."""
        if self._health_server:
            ready = self._is_ready()
            self._health_server.set_ready(ready)
            if ready:
                logger.info("🚀 All services connected - marking as ready")

    async def _setup_subscriptions(self) -> None:
        """
        Setup NATS JetStream subscriptions.

        Subscribes to:
        - document.process: Process uploaded documents
        """
        if not self._subscriber:
            return

        subject = "document.process"
        consumer_name = f"{self._settings.nats_consumer_name}-{subject.replace('.', '-')}"

        await self._subscriber.subscribe(
            stream=self._settings.nats_stream_name,
            consumer=consumer_name,
            subject=subject,
            handler=self._handle_message,
        )
        logger.info("📥 Subscribed to %s", subject)

    async def _handle_message(self, msg: Msg) -> None:
        """
        Handle incoming NATS message.

        Args:
            msg: NATS message with protobuf payload.
        """
        # Check if all services are ready before processing
        if not self._is_ready():
            logger.warning("⚠️ Message received but services not ready, will NAK")
            await msg.nak()
            return

        start_time = asyncio.get_event_loop().time()
        document_id: int | None = None

        try:
            # Parse protobuf message
            proto_request = DocumentProcessRequestProto()
            proto_request.ParseFromString(msg.data)

            # Convert to Pydantic model for easier handling
            request = DocumentProcessRequest.from_protobuf(proto_request)
            document_id = request.document_id

            logger.info(
                "📥 Processing document %d (path: %s)",
                document_id,
                request.minio_path,
            )

            # Get database session and clients
            db = get_db_manager()
            minio = get_minio()
            qdrant = get_qdrant()

            async with db.session() as session:
                # Create service instance
                service = IngestorService(
                    db_session=session,
                    minio_client=minio,
                    qdrant_client=qdrant,
                    settings=self._settings,
                )

                try:
                    # Map scope enum to string
                    scope_map = {
                        ConnectorScope.CONNECTOR_SCOPE_USER: "user",
                        ConnectorScope.CONNECTOR_SCOPE_GROUP: "group",
                        ConnectorScope.CONNECTOR_SCOPE_ORG: "org",
                    }
                    scope = scope_map.get(request.scope, "user")

                    # Process document
                    result = await service.process_document(
                        document_id=request.document_id,
                        connector_id=request.connector_id,
                        user_id=request.user_id,
                        minio_path=request.minio_path,
                        chunking_session=request.chunking_session,
                        scope=scope,
                        scope_id=request.scope_id or None,
                        team_id=request.team_id if request.team_id else None,
                    )

                    # ACK message on success
                    await msg.ack()
                    logger.info(
                        "✅ Document %d processed: %d chunks",
                        document_id,
                        result.get("chunk_count", 0),
                    )

                finally:
                    await service.close()

        except IngestorError as e:
            error_info = await handle_ingestor_error(e)
            logger.error(
                "❌ Ingestor error for document %s: %s",
                document_id,
                e.message,
            )

            if error_info["should_retry"]:
                await msg.nak()  # NATS will redeliver
            else:
                await msg.term()  # Terminal failure, don't retry

        except Exception as e:
            logger.exception(
                "💀 Unexpected error processing document %s: %s",
                document_id,
                e,
            )
            await msg.nak()  # Allow retry for unexpected errors

        finally:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info("⏰ Elapsed: %.2fs", elapsed)

    async def stop(self) -> None:
        """
        Stop the Ingestor service gracefully.

        Closes all connections in reverse order of initialization.
        """
        logger.info("🛑 Ingestor shutting down...")
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
            await close_qdrant()
            logger.info("🔍 Qdrant disconnected")
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

        logger.info("👋 Ingestor stopped")

    def _mask_url(self, url: str) -> str:
        """
        Mask password in URL for safe logging.

        Args:
            url: Connection URL that may contain password.

        Returns:
            URL with password masked as ***.
        """
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
    """
    Main entry point for the Ingestor service.

    Sets up signal handlers and manages application lifecycle.
    """
    app = IngestorApp()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        """Handle shutdown signals."""
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
        logger.exception("💀 Fatal error: %s", e)

    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
