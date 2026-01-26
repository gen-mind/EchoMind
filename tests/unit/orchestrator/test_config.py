"""Unit tests for orchestrator configuration."""

import os
from unittest import mock

import pytest

from orchestrator.config import OrchestratorSettings, get_settings


class TestOrchestratorSettings:
    """Tests for OrchestratorSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = OrchestratorSettings()

        assert settings.enabled is True
        assert settings.check_interval_seconds == 60
        assert settings.max_concurrent_syncs == 5
        assert settings.health_port == 8080
        assert "postgresql" in settings.database_url
        assert settings.database_echo is False
        assert settings.nats_url == "nats://localhost:4222"
        assert settings.nats_user is None
        assert settings.nats_password is None
        assert settings.nats_connect_timeout == 5.0
        assert settings.default_refresh_web_minutes == 10080
        assert settings.default_refresh_drive_minutes == 10080
        assert settings.default_refresh_chat_minutes == 1440
        assert settings.log_level == "INFO"

    def test_env_override(self) -> None:
        """Test that environment variables override defaults."""
        env = {
            "ORCHESTRATOR_ENABLED": "false",
            "ORCHESTRATOR_CHECK_INTERVAL_SECONDS": "120",
            "ORCHESTRATOR_MAX_CONCURRENT_SYNCS": "10",
            "ORCHESTRATOR_HEALTH_PORT": "9090",
            "ORCHESTRATOR_DATABASE_URL": "postgresql+asyncpg://user:pass@host:5432/db",
            "ORCHESTRATOR_NATS_URL": "nats://nats:4222",
            "ORCHESTRATOR_NATS_USER": "testuser",
            "ORCHESTRATOR_NATS_PASSWORD": "testpass",
            "ORCHESTRATOR_LOG_LEVEL": "DEBUG",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            settings = OrchestratorSettings()

        assert settings.enabled is False
        assert settings.check_interval_seconds == 120
        assert settings.max_concurrent_syncs == 10
        assert settings.health_port == 9090
        assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/db"
        assert settings.nats_url == "nats://nats:4222"
        assert settings.nats_user == "testuser"
        assert settings.nats_password == "testpass"
        assert settings.log_level == "DEBUG"

    def test_get_settings_returns_instance(self) -> None:
        """Test that get_settings returns an OrchestratorSettings instance."""
        # Reset cached settings
        import orchestrator.config
        orchestrator.config._settings = None

        settings = get_settings()
        assert isinstance(settings, OrchestratorSettings)


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_invalid_interval_type(self) -> None:
        """Test that invalid interval values raise errors."""
        env = {"ORCHESTRATOR_CHECK_INTERVAL_SECONDS": "not_a_number"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception):
                OrchestratorSettings()

    def test_zero_interval_rejected(self) -> None:
        """Test that zero interval is rejected."""
        env = {"ORCHESTRATOR_CHECK_INTERVAL_SECONDS": "0"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception):
                OrchestratorSettings()

    def test_negative_interval_rejected(self) -> None:
        """Test that negative interval is rejected."""
        env = {"ORCHESTRATOR_CHECK_INTERVAL_SECONDS": "-1"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception):
                OrchestratorSettings()

    def test_extra_env_vars_ignored(self) -> None:
        """Test that extra environment variables are ignored."""
        env = {
            "ORCHESTRATOR_UNKNOWN_SETTING": "value",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            settings = OrchestratorSettings()
            assert not hasattr(settings, "unknown_setting")
