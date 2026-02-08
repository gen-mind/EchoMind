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

        Raises:
            INVALID_ARGUMENT: If texts list is empty or contains invalid strings.
        """
        start_time = time.time()
        texts_count = len(request.texts)

        try:
            # Validate texts list is not empty
            if not request.texts:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "texts cannot be empty",
                )

            # Validate each text string
            MIN_TEXT_LENGTH = 50
            for idx, text in enumerate(request.texts):
                # Check for empty strings
                if not text:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        f"Text at index {idx} is empty",
                    )

                # Check for whitespace-only strings
                if not text.strip():
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        f"Text at index {idx} contains only whitespace",
                    )

                # Check minimum length
                if len(text.strip()) < MIN_TEXT_LENGTH:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        f"Text at index {idx} is too short ({len(text.strip())} chars, minimum {MIN_TEXT_LENGTH})",
                    )

            logger.info(f"📨 Embed request: {texts_count} texts")

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

            logger.info(f"🎯 Embedded {texts_count} texts")
            return EmbedResponse(embeddings=embeddings)

        except ModelNotFoundError as e:
            logger.error(f"❌ Model not found: {e.model_name}")
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Model not found: {e.model_name}",
            )
        except EncoderError as e:
            logger.error(f"❌ Encoding error: {e}")
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
            logger.info(f"⏰ Embed request completed in {elapsed:.2f}s")

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
            logger.error(f"❌ Model not found: {e.model_name}")
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
    logger.info(f"   gRPC port: {settings.grpc_port}")
    logger.info(f"   Health port: {settings.health_port}")
    logger.info(f"   Model: {settings.model_name}")
    logger.info(f"   Cache limit: {settings.model_cache_limit}")
    logger.info(f"   Batch size: {settings.batch_size}")

    # Check device
    checker = DeviceChecker(prefer_gpu=settings.prefer_gpu)
    device = checker.get_best_device()
    logger.info(f"🖥️ Device: {device.device_type.value} ({device.device_name})")

    # Configure encoder
    SentenceEncoder.set_cache_limit(settings.model_cache_limit)
    SentenceEncoder.set_device(checker.get_torch_device())

    # Start health server (must start before model loading for K8s liveness)
    health_server = HealthServer(port=settings.health_port)
    health_thread = threading.Thread(target=health_server.start, daemon=True)
    health_thread.start()
    logger.info(f"💓 Health server started on port {settings.health_port}")

    # Pre-load default model with retry
    max_retries = 5
    retry_delay = 30
    logger.info(f"🧠 Pre-loading model: {settings.model_name}")
    for attempt in range(1, max_retries + 1):
        try:
            dim = SentenceEncoder.get_dimension(settings.model_name)
            logger.info(f"🧠 Model loaded, dimension: {dim}")
            health_server.set_ready(True)
            break
        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"⚠️ Model load attempt {attempt}/{max_retries} failed: {e}"
                )
                logger.info(f"🔄 Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.error(
                    f"❌ Model load failed after {max_retries} attempts: {e}"
                )
                sys.exit(1)

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
    logger.info(f"👂 gRPC server listening on port {settings.grpc_port}")

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
