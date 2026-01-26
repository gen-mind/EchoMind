"""
Unit tests for the SentenceEncoder.

Tests cover:
- Model caching behavior
- Encoding functionality
- Dimension retrieval
- Error handling
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from embedder.logic.encoder import SentenceEncoder
from embedder.logic.exceptions import EncodingError, ModelNotFoundError


class TestSentenceEncoder:
    """Tests for SentenceEncoder class."""

    @pytest.fixture(autouse=True)
    def reset_encoder(self) -> None:
        """Reset encoder state before each test."""
        SentenceEncoder.clear_cache()
        SentenceEncoder._cache_limit = 1
        SentenceEncoder._device = None

    def test_set_cache_limit(self) -> None:
        """Should set cache limit with minimum of 1."""
        SentenceEncoder.set_cache_limit(5)
        assert SentenceEncoder._cache_limit == 5

        SentenceEncoder.set_cache_limit(0)
        assert SentenceEncoder._cache_limit == 1  # Minimum 1

        SentenceEncoder.set_cache_limit(-1)
        assert SentenceEncoder._cache_limit == 1  # Minimum 1

    def test_set_device(self) -> None:
        """Should set device string."""
        SentenceEncoder.set_device("cuda:0")
        assert SentenceEncoder._device == "cuda:0"

        SentenceEncoder.set_device("cpu")
        assert SentenceEncoder._device == "cpu"

    def test_encode_empty_list_returns_empty(self) -> None:
        """Should return empty list for empty input."""
        result = SentenceEncoder.encode(texts=[], model_name="test-model")
        assert result == []

    def test_encode_calls_model_encode(self) -> None:
        """Should call model.encode with correct parameters."""
        mock_model = MagicMock()
        mock_model.encode.return_value = [
            MagicMock(tolist=lambda: [0.1, 0.2, 0.3]),
            MagicMock(tolist=lambda: [0.4, 0.5, 0.6]),
        ]
        mock_model.get_sentence_embedding_dimension.return_value = 3

        with patch.object(SentenceEncoder, "_get_model", return_value=mock_model):
            result = SentenceEncoder.encode(
                texts=["hello", "world"],
                model_name="test-model",
                batch_size=16,
                normalize=True,
            )

        mock_model.encode.assert_called_once_with(
            ["hello", "world"],
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        assert len(result) == 2

    def test_encode_raises_model_not_found_error(self) -> None:
        """Should raise ModelNotFoundError when model loading fails."""
        with patch(
            "embedder.logic.encoder.SentenceTransformer",
            side_effect=Exception("Model not found"),
        ):
            with patch.object(SentenceEncoder, "_get_device", return_value="cpu"):
                with pytest.raises(ModelNotFoundError) as exc_info:
                    SentenceEncoder.encode(
                        texts=["hello"],
                        model_name="nonexistent-model",
                    )

        assert "nonexistent-model" in str(exc_info.value)

    def test_encode_raises_encoding_error(self) -> None:
        """Should raise EncodingError when encoding fails."""
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("GPU OOM")
        mock_model.get_sentence_embedding_dimension.return_value = 768

        with patch.object(SentenceEncoder, "_get_model", return_value=mock_model):
            with pytest.raises(EncodingError) as exc_info:
                SentenceEncoder.encode(
                    texts=["hello", "world"],
                    model_name="test-model",
                )

        assert exc_info.value.texts_count == 2
        assert "GPU OOM" in str(exc_info.value)

    def test_get_dimension_returns_correct_value(self) -> None:
        """Should return model embedding dimension."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768

        with patch.object(SentenceEncoder, "_get_model", return_value=mock_model):
            dim = SentenceEncoder.get_dimension("test-model")

        assert dim == 768

    def test_model_caching(self) -> None:
        """Should cache models and evict oldest when limit reached."""
        mock_model_1 = MagicMock()
        mock_model_1.get_sentence_embedding_dimension.return_value = 384
        mock_model_2 = MagicMock()
        mock_model_2.get_sentence_embedding_dimension.return_value = 768

        SentenceEncoder.set_cache_limit(1)

        with patch(
            "embedder.logic.encoder.SentenceTransformer",
            side_effect=[mock_model_1, mock_model_2],
        ):
            with patch.object(SentenceEncoder, "_get_device", return_value="cpu"):
                # Load first model
                SentenceEncoder.get_dimension("model-1")
                assert "model-1" in SentenceEncoder.get_cached_models()

                # Load second model (should evict first)
                SentenceEncoder.get_dimension("model-2")
                assert "model-2" in SentenceEncoder.get_cached_models()
                assert "model-1" not in SentenceEncoder.get_cached_models()

    def test_clear_cache(self) -> None:
        """Should clear all cached models."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768

        with patch(
            "embedder.logic.encoder.SentenceTransformer",
            return_value=mock_model,
        ):
            with patch.object(SentenceEncoder, "_get_device", return_value="cpu"):
                SentenceEncoder.get_dimension("test-model")
                assert len(SentenceEncoder.get_cached_models()) == 1

                SentenceEncoder.clear_cache()
                assert len(SentenceEncoder.get_cached_models()) == 0

    def test_get_cached_models(self) -> None:
        """Should return list of cached model names."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768

        SentenceEncoder.set_cache_limit(2)

        with patch(
            "embedder.logic.encoder.SentenceTransformer",
            return_value=mock_model,
        ):
            with patch.object(SentenceEncoder, "_get_device", return_value="cpu"):
                SentenceEncoder.get_dimension("model-a")
                SentenceEncoder.get_dimension("model-b")

                cached = SentenceEncoder.get_cached_models()
                assert "model-a" in cached
                assert "model-b" in cached
