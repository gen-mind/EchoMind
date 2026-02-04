"""
EchoMind Embedder Service Entry Point.

gRPC server that provides text embedding using SentenceTransformers.

Usage:
    python main.py

Environment Variables:
    EMBEDDER_GRPC_PORT: gRPC server port (default: 50051)
    EMBEDDER_HEALTH_PORT: Health check port (default: 8080)
    EMBEDDER_MODEL_NAME: Default model name
    EMBEDDER_MODEL_CACHE_LIMIT: Max models in cache (default: 1)
    EMBEDDER_PREFER_GPU: Use GPU if available (default: true)
    EMBEDDER_LOG_LEVEL: Logging level (default: INFO)
"""

import logging
import os
import sys
import threading
import time
from concurrent import futures
from types import ModuleType

import grpc

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from echomind_lib.helpers.device_checker import DeviceChecker
from echomind_lib.helpers.readiness_probe import HealthServer
from echomind_lib.models.internal.embedding_pb2 import (
    DimensionResponse,
    EmbedResponse,
    Embedding,
)
from echomind_lib.models.internal.embedding_pb2_grpc import (
    EmbedServiceServicer,
    add_EmbedServiceServicer_to_server,
)

from embedder.config import get_settings
from embedder.logic.encoder import SentenceEncoder
from embedder.logic.exceptions import EncoderError, ModelNotFoundError

# Configure logging
logging.basicConfig(
    level=os.getenv("EMBEDDER_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("echomind-embedder")


class EmbedServicer(EmbedServiceServicer):
    """
    gRPC servicer for embedding operations.

    Implements the EmbedService defined in embedding.proto.
    """

    def __init__(self, default_model: str, batch_size: int = 32):
        """
        Initialize the servicer.

        Args:
            default_model: Default model name for embeddings.
            batch_size: Default batch size for encoding.
        """
        self._default_model = default_model
        self._batch_size = batch_size

    def Embed(self, request, context) -> EmbedResponse:
        """
        Generate embeddings for input texts.

        Args:
            request: EmbedRequest with texts to embed.
            context: gRPC context.

        Returns:
            EmbedResponse with embedding vectors.
        """
        start_time = time.time()
        texts_count = len(request.texts)

        try:
            if not request.texts:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "texts cannot be empty",
                )

            logger.info("📨 Embed request: %d texts", texts_count)

            # Encode texts
            vectors = SentenceEncoder.encode(
                texts=list(request.texts),
                model_name=self._default_model,
                batch_size=self._batch_size,
            )

            # Build response
            embeddings = [
                Embedding(vector=vec, dimension=len(vec))
                for vec in vectors
            ]

            logger.info("🎯 Embedded %d texts", texts_count)
            return EmbedResponse(embeddings=embeddings)

        except ModelNotFoundError as e:
            logger.error("❌ Model not found: %s", e.model_name)
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Model not found: {e.model_name}",
            )
        except EncoderError as e:
            logger.error("❌ Encoding error: %s", e)
            context.abort(
                grpc.StatusCode.INTERNAL,
                str(e),
            )
        except grpc.RpcError:
            raise
        except Exception as e:
            logger.exception("❌ Unexpected error")
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Internal error: {str(e)}",
            )
        finally:
            elapsed = time.time() - start_time
            logger.info("⏰ Embed request completed in %.2fs", elapsed)

    def GetDimension(self, request, context) -> DimensionResponse:
        """
        Get the embedding dimension for the current model.

        Args:
            request: DimensionRequest (empty).
            context: gRPC context.

        Returns:
            DimensionResponse with dimension and model ID.
        """
        try:
            dimension = SentenceEncoder.get_dimension(self._default_model)
            return DimensionResponse(
                dimension=dimension,
                model_id=self._default_model,
            )
        except ModelNotFoundError as e:
            logger.error("❌ Model not found: %s", e.model_name)
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Model not found: {e.model_name}",
            )
        except Exception as e:
            logger.exception("❌ Unexpected error getting dimension")
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Internal error: {str(e)}",
            )


def serve() -> None:
    """
    Start the gRPC server.

    Initializes the encoder, starts health probe, and serves requests.
    """
    settings = get_settings()

    logger.info("🚀 EchoMind Embedder Service starting...")
    logger.info("📋 Configuration:")
    logger.info("   gRPC port: %d", settings.grpc_port)
    logger.info("   Health port: %d", settings.health_port)
    logger.info("   Model: %s", settings.model_name)
    logger.info("   Cache limit: %d", settings.model_cache_limit)
    logger.info("   Batch size: %d", settings.batch_size)

    # Check device
    checker = DeviceChecker(prefer_gpu=settings.prefer_gpu)
    device = checker.get_best_device()
    logger.info("🖥️ Device: %s (%s)", device.device_type.value, device.device_name)

    # Configure encoder
    SentenceEncoder.set_cache_limit(settings.model_cache_limit)
    SentenceEncoder.set_device(checker.get_torch_device())

    # Pre-load default model
    logger.info("🧠 Pre-loading model: %s", settings.model_name)
    try:
        dim = SentenceEncoder.get_dimension(settings.model_name)
        logger.info("🧠 Model loaded, dimension: %d", dim)
    except Exception as e:
        logger.error("❌ Failed to load model: %s", e)
        sys.exit(1)

    # Start health server
    health_server = HealthServer(port=settings.health_port)
    health_thread = threading.Thread(target=health_server.start, daemon=True)
    health_thread.start()
    health_server.set_ready(True)
    logger.info("💓 Health server started on port %d", settings.health_port)

    # Create gRPC server
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=settings.grpc_max_workers),
        options=[
            ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
            ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
        ],
    )

    # Add servicer
    servicer = EmbedServicer(
        default_model=settings.model_name,
        batch_size=settings.batch_size,
    )
    add_EmbedServiceServicer_to_server(servicer, server)

    # Start server
    server.add_insecure_port(f"0.0.0.0:{settings.grpc_port}")
    server.start()
    logger.info("👂 gRPC server listening on port %d", settings.grpc_port)

    # Wait for termination
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        server.stop(grace=5)
        SentenceEncoder.clear_cache()
        logger.info("👋 Goodbye!")


if __name__ == "__main__":
    serve()
