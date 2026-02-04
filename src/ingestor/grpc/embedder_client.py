"""
gRPC client for Embedder service.

Handles text embeddings via async gRPC calls.
"""

import logging
from typing import Any

import grpc

from echomind_lib.models.internal.embedding_pb2 import (
    DimensionRequest,
    EmbedRequest,
)
from echomind_lib.models.internal.embedding_pb2_grpc import EmbedServiceStub

from ingestor.logic.exceptions import EmbeddingError, GrpcError

logger = logging.getLogger("echomind-ingestor.embedder_client")


class EmbedderClient:
    """
    Async gRPC client for Embedder service.

    Handles:
    - Text chunk embedding
    - Connection management
    - Error handling with retry guidance

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
        self._dimension: int | None = None

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
                    ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
                    ("grpc.max_receive_message_length", 100 * 1024 * 1024),
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 10000),
                    ("grpc.keepalive_permit_without_calls", True),
                ],
            )
            self._stub = EmbedServiceStub(self._channel)
            logger.info("🔗 Connected to Embedder at %s:%d", self._host, self._port)

    async def get_dimension(self) -> int:
        """
        Get embedding vector dimension from embedder service.

        Returns:
            Vector dimension (e.g., 1024 for NV-Embed-v2).

        Raises:
            GrpcError: If gRPC call fails.
        """
        if self._dimension is not None:
            return self._dimension

        await self._ensure_connected()

        try:
            request = DimensionRequest()
            response = await self._stub.GetDimension(
                request,
                timeout=self._timeout,
            )
            self._dimension = response.dimension
            logger.info(
                "📐 Embedder dimension: %d (model: %s)",
                response.dimension,
                response.model_id,
            )
            return response.dimension

        except grpc.aio.AioRpcError as e:
            raise GrpcError(
                service="embedder",
                reason=str(e.details()),
                code=e.code().name,
            ) from e

    async def embed_texts(
        self,
        texts: list[str],
        document_id: int | None = None,
    ) -> list[list[float]]:
        """
        Embed text chunks via Embedder service.

        Args:
            texts: List of text chunks to embed.
            document_id: Optional document ID for error context.

        Returns:
            List of embedding vectors.

        Raises:
            EmbeddingError: If embedding fails.
            GrpcError: If gRPC communication fails.
        """
        await self._ensure_connected()

        if not texts:
            return []

        try:
            request = EmbedRequest(texts=texts)

            response = await self._stub.Embed(
                request,
                timeout=self._timeout,
            )

            # Extract vectors from response
            vectors = [
                list(embedding.vector)
                for embedding in response.embeddings
            ]

            logger.info(
                "🎯 Embedded %d texts for document %s",
                len(vectors),
                document_id or "N/A",
            )

            return vectors

        except grpc.aio.AioRpcError as e:
            logger.error(
                "❌ gRPC error embedding texts for document %s: %s",
                document_id,
                e.details(),
            )
            raise GrpcError(
                service="embedder",
                reason=str(e.details()),
                code=e.code().name,
            ) from e
        except Exception as e:
            logger.exception(
                "❌ Embedding failed for document %s: %s",
                document_id,
                e,
            )
            raise EmbeddingError(str(e), document_id=document_id) from e

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        document_id: int | None = None,
    ) -> list[list[float]]:
        """
        Embed texts in batches to avoid memory issues.

        Args:
            texts: List of text chunks to embed.
            batch_size: Number of texts per batch.
            document_id: Optional document ID for error context.

        Returns:
            List of embedding vectors.

        Raises:
            EmbeddingError: If embedding fails.
            GrpcError: If gRPC communication fails.
        """
        if not texts:
            return []

        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(texts) + batch_size - 1) // batch_size

            logger.debug(
                "🔄 Embedding batch %d/%d (%d texts) for document %s",
                batch_num,
                total_batches,
                len(batch),
                document_id or "N/A",
            )

            vectors = await self.embed_texts(batch, document_id)
            all_vectors.extend(vectors)

        return all_vectors

    async def close(self) -> None:
        """
        Close gRPC channel.

        Should be called when done with client.
        """
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("🔗 Embedder client closed")

    async def health_check(self) -> dict[str, Any]:
        """
        Check embedder service health.

        Returns:
            Dictionary with health status and dimension.

        Raises:
            GrpcError: If service is unavailable.
        """
        try:
            dimension = await self.get_dimension()
            return {
                "status": "healthy",
                "dimension": dimension,
                "host": self._host,
                "port": self._port,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "host": self._host,
                "port": self._port,
            }
