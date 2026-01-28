"""
SentenceTransformer encoder with model caching.

Provides thread-safe model loading and batch encoding for text embeddings.
"""

import logging
import threading
from typing import ClassVar

from sentence_transformers import SentenceTransformer

from echomind_lib.helpers.device_checker import get_device
from embedder.logic.exceptions import EncodingError, ModelNotFoundError

logger = logging.getLogger(__name__)


class SentenceEncoder:
    """
    Thread-safe SentenceTransformer encoder with LRU model caching.

    Usage:
        # Configure cache limit (optional)
        SentenceEncoder.set_cache_limit(2)

        # Encode texts
        vectors = SentenceEncoder.encode(
            texts=["Hello world", "How are you?"],
            model_name="nvidia/llama-nemotron-embed-1b-v2"
        )

        # Get model dimension
        dim = SentenceEncoder.get_dimension("nvidia/llama-nemotron-embed-1b-v2")
    """

    _cache_limit: ClassVar[int] = 1
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _model_cache: ClassVar[dict[str, SentenceTransformer]] = {}
    _device: ClassVar[str | None] = None

    @classmethod
    def set_cache_limit(cls, limit: int) -> None:
        """
        Set the maximum number of models to cache.

        Args:
            limit: Maximum models in cache (minimum 1).
        """
        with cls._lock:
            cls._cache_limit = max(1, limit)
            logger.info("📦 Model cache limit set to %d", cls._cache_limit)

    @classmethod
    def set_device(cls, device: str | None = None) -> None:
        """
        Set the device for model inference.

        Args:
            device: Device string (cuda:0, mps, cpu) or None for auto-detect.
        """
        with cls._lock:
            cls._device = device or get_device()
            logger.info("🖥️ Device set to: %s", cls._device)

    @classmethod
    def _get_device(cls) -> str:
        """Get the device, auto-detecting if not set."""
        if cls._device is None:
            cls._device = get_device()
        return cls._device

    @classmethod
    def _get_model(cls, model_name: str) -> SentenceTransformer:
        """
        Get or load a model from cache.

        Thread-safe with LRU eviction when cache is full.

        Args:
            model_name: HuggingFace model name or path.

        Returns:
            Loaded SentenceTransformer model.

        Raises:
            ModelNotFoundError: If model cannot be loaded.
        """
        with cls._lock:
            # Return cached model if available
            if model_name in cls._model_cache:
                logger.debug("📦 Cache hit for model: %s", model_name)
                return cls._model_cache[model_name]

            # Evict oldest model if cache is full
            if len(cls._model_cache) >= cls._cache_limit:
                oldest = next(iter(cls._model_cache))
                del cls._model_cache[oldest]
                logger.info("🗑️ Evicted model from cache: %s", oldest)

            # Load new model
            try:
                device = cls._get_device()
                logger.info("📥 Loading model: %s on %s", model_name, device)
                model = SentenceTransformer(model_name, device=device)
                cls._model_cache[model_name] = model
                logger.info("✅ Model loaded: %s (dim=%d)", model_name, model.get_sentence_embedding_dimension())
                return model
            except Exception as e:
                logger.error("❌ Failed to load model %s: %s", model_name, e)
                raise ModelNotFoundError(model_name) from e

    @classmethod
    def encode(
        cls,
        texts: list[str],
        model_name: str,
        batch_size: int = 32,
        normalize: bool = True,
    ) -> list[list[float]]:
        """
        Encode texts to embedding vectors.

        Args:
            texts: List of texts to encode.
            model_name: SentenceTransformer model name.
            batch_size: Batch size for encoding.
            normalize: Normalize vectors to unit length.

        Returns:
            List of embedding vectors as float lists.

        Raises:
            ModelNotFoundError: If model cannot be loaded.
            EncodingError: If encoding fails.
        """
        if not texts:
            return []

        model = cls._get_model(model_name)

        try:
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=False,
            )
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error("❌ Encoding failed: %s", e)
            raise EncodingError(str(e), len(texts)) from e

    @classmethod
    def get_dimension(cls, model_name: str) -> int:
        """
        Get the embedding dimension for a model.

        Args:
            model_name: SentenceTransformer model name.

        Returns:
            Embedding vector dimension.

        Raises:
            ModelNotFoundError: If model cannot be loaded.
        """
        model = cls._get_model(model_name)
        return model.get_sentence_embedding_dimension()

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached models."""
        with cls._lock:
            cls._model_cache.clear()
            logger.info("🗑️ Model cache cleared")

    @classmethod
    def get_cached_models(cls) -> list[str]:
        """Get list of currently cached model names."""
        with cls._lock:
            return list(cls._model_cache.keys())
