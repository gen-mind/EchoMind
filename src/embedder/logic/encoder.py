"""
SentenceTransformer encoder with model caching.

Provides thread-safe model loading and batch encoding for text embeddings.
Supports NVIDIA Nemotron embedding models with trust_remote_code.
"""

import logging
import threading
from typing import ClassVar

import torch
from sentence_transformers import SentenceTransformer

from echomind_lib.helpers.device_checker import get_device
from embedder.logic.exceptions import EncodingError, ModelNotFoundError

logger = logging.getLogger(__name__)

# NVIDIA models that require trust_remote_code and have special encode methods
NVIDIA_EMBED_MODELS = [
    "nvidia/llama-nemotron-embed-1b-v2",
    "nvidia/llama-3.2-nv-embedqa-1b-v2",
    "nvidia/llama-nemotron-embed-vl-1b-v2",
    "nvidia/llama-embed-nemotron-8b",
]


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

                # Check if this is an NVIDIA model requiring special handling
                is_nvidia_model = any(
                    model_name.startswith(prefix) or model_name == prefix
                    for prefix in NVIDIA_EMBED_MODELS
                )

                if is_nvidia_model:
                    # NVIDIA models require trust_remote_code and work best with bfloat16
                    logger.info("🚀 Loading NVIDIA model with trust_remote_code=True")
                    model = SentenceTransformer(
                        model_name,
                        device=device,
                        trust_remote_code=True,
                        model_kwargs={"torch_dtype": torch.bfloat16},
                    )
                else:
                    # Standard sentence-transformers model
                    model = SentenceTransformer(model_name, device=device)

                cls._model_cache[model_name] = model
                logger.info("🧠 Model loaded: %s (dim=%d)", model_name, model.get_sentence_embedding_dimension())
                return model
            except Exception as e:
                logger.error("❌ Failed to load model %s: %s", model_name, e)
                raise ModelNotFoundError(model_name) from e

    @classmethod
    def _is_nvidia_model(cls, model_name: str) -> bool:
        """Check if the model is an NVIDIA model with special encoding methods."""
        return any(
            model_name.startswith(prefix) or model_name == prefix
            for prefix in NVIDIA_EMBED_MODELS
        )

    @classmethod
    def encode(
        cls,
        texts: list[str],
        model_name: str,
        batch_size: int = 32,
        normalize: bool = True,
        encode_type: str = "document",
    ) -> list[list[float]]:
        """
        Encode texts to embedding vectors.

        Args:
            texts: List of texts to encode.
            model_name: SentenceTransformer model name.
            batch_size: Batch size for encoding.
            normalize: Normalize vectors to unit length.
            encode_type: Type of encoding - "document" or "query".
                         NVIDIA models use different methods for each.

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
            # Check if this is an NVIDIA model with special encode methods
            if cls._is_nvidia_model(model_name):
                # NVIDIA models have encode_query and encode_document methods
                if encode_type == "query" and hasattr(model, "encode_query"):
                    logger.debug("🔍 Using encode_query for NVIDIA model")
                    embeddings = model.encode_query(texts)
                elif hasattr(model, "encode_document"):
                    logger.debug("📄 Using encode_document for NVIDIA model")
                    embeddings = model.encode_document(texts)
                else:
                    # Fallback to standard encode
                    embeddings = model.encode(
                        texts,
                        batch_size=batch_size,
                        normalize_embeddings=normalize,
                        show_progress_bar=False,
                    )
            else:
                # Standard sentence-transformers encoding
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
    def encode_query(
        cls,
        texts: list[str],
        model_name: str,
    ) -> list[list[float]]:
        """
        Encode query texts for search.

        For NVIDIA models, uses the specialized encode_query method.
        For other models, uses standard encoding.

        Args:
            texts: List of query texts to encode.
            model_name: SentenceTransformer model name.

        Returns:
            List of embedding vectors as float lists.
        """
        return cls.encode(texts, model_name, encode_type="query")

    @classmethod
    def encode_document(
        cls,
        texts: list[str],
        model_name: str,
    ) -> list[list[float]]:
        """
        Encode document texts for indexing.

        For NVIDIA models, uses the specialized encode_document method.
        For other models, uses standard encoding.

        Args:
            texts: List of document texts to encode.
            model_name: SentenceTransformer model name.

        Returns:
            List of embedding vectors as float lists.
        """
        return cls.encode(texts, model_name, encode_type="document")

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
