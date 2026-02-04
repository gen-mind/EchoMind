"""
Embedder gRPC client for query embedding.

Handles text embedding via async gRPC calls to the Embedder service.
Used by ChatService for query vectorization during retrieval.
"""

import logging

import grpc

from echomind_lib.models.internal.embedding_pb2 import EmbedRequest
from echomind_lib.models.internal.embedding_pb2_grpc import EmbedServiceStub

from api.logic.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class EmbedderClient:
    """
    Async gRPC client for Embedder service.

    Provides query embedding for semantic search.

    Attributes:
        host: Embedder service hostname.
        port: Embedder gRPC port.
        timeout: gRPC call timeout in seconds.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize Embedder client.

        Args:
            host: Embedder service hostname.
            port: Embedder gRPC port.
            timeout: gRPC call timeout in seconds.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._channel: grpc.aio.Channel | None = None
        self._stub: EmbedServiceStub | None = None

    async def _ensure_connected(self) -> None:
        """
        Ensure gRPC channel is connected.

        Creates channel and stub if not already connected.
        """
        if self._channel is None:
            target = f"{self._host}:{self._port}"
            self._channel = grpc.aio.insecure_channel(
                target,
                options=[
                    ("grpc.max_send_message_length", 10 * 1024 * 1024),
                    ("grpc.max_receive_message_length", 10 * 1024 * 1024),
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 10000),
                ],
            )
            self._stub = EmbedServiceStub(self._channel)
            logger.info("🔗 Connected to Embedder at %s:%d", self._host, self._port)

    async def embed_query(self, query: str) -> list[float]:
        """
        Embed a search query.

        Args:
            query: The search query text.

        Returns:
            Embedding vector as list of floats.

        Raises:
            ServiceUnavailableError: If Embedder service is unavailable.
        """
        await self._ensure_connected()

        try:
            request = EmbedRequest(texts=[query])
            response = await self._stub.Embed(
                request,
                timeout=self._timeout,
            )

            if not response.embeddings:
                logger.error("❌ Embedder returned empty response")
                raise ServiceUnavailableError("Embedder")

            vector = list(response.embeddings[0].vector)
            logger.debug("🎯 Embedded query (%d dims)", len(vector))
            return vector

        except grpc.aio.AioRpcError as e:
            logger.error("❌ Embedder gRPC error: %s", e.details())
            raise ServiceUnavailableError("Embedder") from e

    async def close(self) -> None:
        """Close gRPC channel."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("🔗 Embedder client closed")

    async def health_check(self) -> bool:
        """
        Check if Embedder service is available.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            await self._ensure_connected()
            # Simple connectivity check
            return self._channel is not None
        except Exception:
            return False


# Global client instance
_embedder_client: EmbedderClient | None = None


def get_embedder_client() -> EmbedderClient:
    """Get the global Embedder client instance."""
    if _embedder_client is None:
        raise RuntimeError("Embedder client not initialized. Call init_embedder_client() first.")
    return _embedder_client


async def init_embedder_client(
    host: str,
    port: int,
    timeout: float = 30.0,
) -> EmbedderClient:
    """
    Initialize the global Embedder client.

    Args:
        host: Embedder gRPC host.
        port: Embedder gRPC port.
        timeout: Call timeout in seconds.

    Returns:
        Initialized EmbedderClient.
    """
    global _embedder_client
    _embedder_client = EmbedderClient(host=host, port=port, timeout=timeout)
    return _embedder_client


async def close_embedder_client() -> None:
    """Close the global Embedder client."""
    global _embedder_client
    if _embedder_client is not None:
        await _embedder_client.close()
        _embedder_client = None
