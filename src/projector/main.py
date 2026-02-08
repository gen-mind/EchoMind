"""Projector worker service - NATS subscriber for TensorBoard visualization generation."""

import asyncio
import logging
import os
import sys
import threading
from typing import Any

from nats.aio.msg import Msg

from echomind_lib.db.nats_subscriber import JetStreamSubscriber
from echomind_lib.helpers.readiness_probe import ReadinessProbe
from echomind_lib.models.internal.projector_pb2 import ProjectorGenerateRequest
from projector.logic.projector_service import ProjectorService
from projector.logic.exceptions import ProjectorError, EmptyCollectionError


# Configure logging
logging.basicConfig(
    level=os.getenv("PROJECTOR_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ProjectorWorker:
    """NATS subscriber worker for TensorBoard visualization generation."""

    def __init__(self):
        """Initialize the projector worker."""
        self.nats_url = os.getenv("PROJECTOR_NATS_URL", "nats://nats:4222")
        self.stream_name = os.getenv("PROJECTOR_STREAM_NAME", "projector-stream")
        self.consumer_name = os.getenv("PROJECTOR_CONSUMER_NAME", "projector-worker")
        self.subject = os.getenv("PROJECTOR_SUBJECT", "projector.generate")

        self.qdrant_url = os.getenv("PROJECTOR_QDRANT_URL", "http://qdrant:6333")
        self.qdrant_api_key = os.getenv("PROJECTOR_QDRANT_API_KEY")
        self.log_base_dir = os.getenv("PROJECTOR_LOG_DIR", "/logs")

        self.service = ProjectorService(
            qdrant_url=self.qdrant_url,
            qdrant_api_key=self.qdrant_api_key,
            log_base_dir=self.log_base_dir,
        )

        self.subscriber: JetStreamSubscriber | None = None
        self.health_server: ReadinessProbe | None = None

        # Connection status flags
        self._nats_connected = False
        self._qdrant_connected = False
        self._retry_tasks: list[asyncio.Task] = []

    def _is_ready(self) -> bool:
        """Check if service is ready to process messages."""
        return self._nats_connected and self._qdrant_connected

    def _update_readiness(self) -> None:
        """Update health server readiness status."""
        if self.health_server:
            self.health_server.set_ready(self._is_ready())

    async def _handle_message(self, msg: Msg) -> None:
        """
        Handle incoming NATS message.

        Args:
            msg: NATS message containing ProjectorGenerateRequest protobuf
        """
        start_time = asyncio.get_event_loop().time()

        # Skip if not ready
        if not self._is_ready():
            logger.warning("⚠️ Service not ready, skipping message")
            await msg.nak()
            return

        try:
            # Parse protobuf message
            data = ProjectorGenerateRequest()
            data.ParseFromString(msg.data)

            viz_id = data.viz_id
            collection_name = data.collection_name
            search_query = data.search_query if data.HasField("search_query") else None
            limit = data.limit or 10000

            logger.info(f"📨 Received request: viz_id={viz_id}, collection={collection_name}")

            # Generate visualization
            result = await self.service.generate_visualization(
                collection_name=collection_name,
                search_query=search_query,
                limit=limit,
            )

            await msg.ack()
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(
                f"✅ Visualization generated: {result['viz_id']} "
                f"({result['num_points']} points, {result['vector_dimension']}D) "
                f"in {elapsed:.2f}s"
            )

        except EmptyCollectionError as e:
            logger.warning(f"⚠️ {str(e)}")
            await msg.ack()  # Ack empty results (not a failure)

        except ProjectorError as e:
            logger.error(f"❌ Projector error: {str(e)}")
            await msg.nak()

        except Exception as e:
            logger.exception(f"❌ Unexpected error processing message")
            await msg.nak()

    async def _init_nats(self) -> None:
        """Initialize NATS connection and subscription."""
        try:
            self.subscriber = JetStreamSubscriber(servers=[self.nats_url])
            await self.subscriber.init()

            await self.subscriber.subscribe(
                stream=self.stream_name,
                consumer=self.consumer_name,
                subject=self.subject,
                handler=self._handle_message,
            )

            self._nats_connected = True
            logger.info(f"✅ NATS connected: {self.nats_url} (subject: {self.subject})")
            self._update_readiness()

        except Exception as e:
            logger.warning(f"⚠️ NATS connection failed: {str(e)}")
            logger.info("🔄 Will retry NATS connection in background...")
            self._retry_tasks.append(asyncio.create_task(self._retry_nats_connection()))

    async def _retry_nats_connection(self) -> None:
        """Retry NATS connection every 30 seconds."""
        while not self._nats_connected:
            await asyncio.sleep(30)
            try:
                self.subscriber = JetStreamSubscriber(servers=[self.nats_url])
                await self.subscriber.init()

                await self.subscriber.subscribe(
                    stream=self.stream_name,
                    consumer=self.consumer_name,
                    subject=self.subject,
                    handler=self._handle_message,
                )

                self._nats_connected = True
                logger.info(f"✅ NATS reconnected: {self.nats_url}")
                self._update_readiness()

            except Exception as e:
                logger.warning(f"⚠️ NATS reconnection attempt failed: {str(e)}")

    async def _init_qdrant(self) -> None:
        """Initialize Qdrant connection check."""
        try:
            # Test Qdrant connection
            collections = self.service.qdrant._client.get_collections()
            self._qdrant_connected = True
            logger.info(f"✅ Qdrant connected: {self.qdrant_url} ({len(collections.collections)} collections)")
            self._update_readiness()

        except Exception as e:
            logger.warning(f"⚠️ Qdrant connection failed: {str(e)}")
            logger.info("🔄 Will retry Qdrant connection in background...")
            self._retry_tasks.append(asyncio.create_task(self._retry_qdrant_connection()))

    async def _retry_qdrant_connection(self) -> None:
        """Retry Qdrant connection every 30 seconds."""
        while not self._qdrant_connected:
            await asyncio.sleep(30)
            try:
                collections = self.service.qdrant._client.get_collections()
                self._qdrant_connected = True
                logger.info(f"✅ Qdrant reconnected: {self.qdrant_url}")
                self._update_readiness()

            except Exception as e:
                logger.warning(f"⚠️ Qdrant reconnection attempt failed: {str(e)}")

    async def start(self) -> None:
        """Start the projector worker."""
        logger.info("🚀 Starting Projector Worker...")

        # Start health server
        self.health_server = ReadinessProbe(port=8080)
        threading.Thread(target=self.health_server.start_server, daemon=True).start()
        logger.info("🏥 Health server started on :8080")

        # Initialize connections (non-blocking)
        await self._init_nats()
        await self._init_qdrant()

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("⏹️ Shutting down...")
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Cleanup resources."""
        # Cancel retry tasks
        for task in self._retry_tasks:
            task.cancel()

        # Close NATS
        if self.subscriber:
            await self.subscriber.close()

        logger.info("👋 Projector worker stopped")


async def main() -> None:
    """Main entry point."""
    worker = ProjectorWorker()
    await worker.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("💀 Fatal error")
        sys.exit(1)
