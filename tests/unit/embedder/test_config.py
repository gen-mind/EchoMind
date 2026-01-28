"""Unit tests for embedder configuration."""

import os
from unittest import mock

import pytest

from embedder.config import EmbedderSettings, get_settings


class TestEmbedderSettings:
    """Tests for EmbedderSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = EmbedderSettings()

        assert settings.grpc_port == 50051
        assert settings.grpc_max_workers == 10
        assert settings.health_port == 8080
        assert settings.model_name == "nvidia/llama-nemotron-embed-1b-v2"
        assert settings.model_cache_limit == 1
        assert settings.batch_size == 32
        assert settings.prefer_gpu is True
        assert settings.qdrant_host == "localhost"
        assert settings.qdrant_port == 6333
        assert settings.log_level == "INFO"

    def test_env_override(self) -> None:
        """Test that environment variables override defaults."""
        env = {
            "EMBEDDER_GRPC_PORT": "50052",
            "EMBEDDER_MODEL_NAME": "custom-model",
            "EMBEDDER_BATCH_SIZE": "64",
            "EMBEDDER_PREFER_GPU": "false",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            settings = EmbedderSettings()

        assert settings.grpc_port == 50052
        assert settings.model_name == "custom-model"
        assert settings.batch_size == 64
        assert settings.prefer_gpu is False

    def test_get_settings_returns_instance(self) -> None:
        """Test that get_settings returns an EmbedderSettings instance."""
        settings = get_settings()
        assert isinstance(settings, EmbedderSettings)


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_invalid_port_type(self) -> None:
        """Test that invalid port values raise errors."""
        env = {"EMBEDDER_GRPC_PORT": "not_a_number"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception):  # Pydantic validation error
                EmbedderSettings()

    def test_extra_env_vars_ignored(self) -> None:
        """Test that extra environment variables are ignored."""
        env = {
            "EMBEDDER_UNKNOWN_SETTING": "value",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            # Should not raise
            settings = EmbedderSettings()
            assert not hasattr(settings, "unknown_setting")
