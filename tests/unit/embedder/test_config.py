"""
Unit tests for the Embedder Service configuration.

Tests cover:
- Settings loading from environment variables
- Default values
"""

import os
import sys
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from embedder.config import EmbedderSettings, get_settings


class TestEmbedderSettings:
    """Tests for EmbedderSettings class."""

    def test_default_grpc_port(self) -> None:
        """Should use default gRPC port of 50051."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.grpc_port == 50051

    def test_custom_grpc_port(self) -> None:
        """Should load custom gRPC port from environment."""
        with patch.dict(os.environ, {"EMBEDDER_GRPC_PORT": "50052"}, clear=True):
            settings = EmbedderSettings()
            assert settings.grpc_port == 50052

    def test_default_health_port(self) -> None:
        """Should use default health port of 8080."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.health_port == 8080

    def test_default_model_name(self) -> None:
        """Should use default model name."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert "paraphrase-multilingual" in settings.model_name

    def test_custom_model_name(self) -> None:
        """Should load custom model name from environment."""
        with patch.dict(
            os.environ,
            {"EMBEDDER_MODEL_NAME": "sentence-transformers/all-MiniLM-L6-v2"},
            clear=True,
        ):
            settings = EmbedderSettings()
            assert settings.model_name == "sentence-transformers/all-MiniLM-L6-v2"

    def test_default_cache_limit(self) -> None:
        """Should use default cache limit of 1."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.model_cache_limit == 1

    def test_custom_cache_limit(self) -> None:
        """Should load custom cache limit from environment."""
        with patch.dict(
            os.environ,
            {"EMBEDDER_MODEL_CACHE_LIMIT": "3"},
            clear=True,
        ):
            settings = EmbedderSettings()
            assert settings.model_cache_limit == 3

    def test_default_batch_size(self) -> None:
        """Should use default batch size of 32."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.batch_size == 32

    def test_default_prefer_gpu(self) -> None:
        """Should prefer GPU by default."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.prefer_gpu is True

    def test_disable_gpu_preference(self) -> None:
        """Should allow disabling GPU preference."""
        with patch.dict(os.environ, {"EMBEDDER_PREFER_GPU": "false"}, clear=True):
            settings = EmbedderSettings()
            assert settings.prefer_gpu is False

    def test_default_log_level(self) -> None:
        """Should use default log level of INFO."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.log_level == "INFO"

    def test_default_max_workers(self) -> None:
        """Should use default max workers of 10."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.grpc_max_workers == 10

    def test_default_qdrant_host(self) -> None:
        """Should use default Qdrant host of localhost."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.qdrant_host == "localhost"

    def test_custom_qdrant_host(self) -> None:
        """Should load custom Qdrant host from environment."""
        with patch.dict(os.environ, {"EMBEDDER_QDRANT_HOST": "qdrant"}, clear=True):
            settings = EmbedderSettings()
            assert settings.qdrant_host == "qdrant"

    def test_default_qdrant_port(self) -> None:
        """Should use default Qdrant port of 6333."""
        with patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()
            assert settings.qdrant_port == 6333

    def test_custom_qdrant_port(self) -> None:
        """Should load custom Qdrant port from environment."""
        with patch.dict(os.environ, {"EMBEDDER_QDRANT_PORT": "6334"}, clear=True):
            settings = EmbedderSettings()
            assert settings.qdrant_port == 6334


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_embedder_settings(self) -> None:
        """Should return an EmbedderSettings instance."""
        with patch.dict(os.environ, {}, clear=True):
            settings = get_settings()
            assert isinstance(settings, EmbedderSettings)
