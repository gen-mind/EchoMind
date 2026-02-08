"""Unit tests for Connector Service configuration."""

import os
from unittest.mock import patch

import pytest

from connector.config import ConnectorSettings, get_settings, reset_settings


class TestConnectorSettings:
    """Tests for ConnectorSettings."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Reset settings after each test."""
        reset_settings()

    def test_default_values(self) -> None:
        """Test default configuration values."""
        settings = ConnectorSettings()

        assert settings.enabled is True
        assert settings.max_concurrent_downloads == 5
        assert settings.max_file_size_bytes == 100 * 1024 * 1024
        assert settings.google_export_max_size_bytes == 10 * 1024 * 1024
        assert settings.health_port == 8080
        assert settings.minio_bucket == "echomind-documents"
        assert settings.max_retries == 3
        assert settings.retry_base_delay == 1.0
        assert settings.log_level == "INFO"

    def test_database_url_default(self) -> None:
        """Test default database URL."""
        settings = ConnectorSettings()

        assert "postgresql+asyncpg" in settings.database_url
        assert "echomind" in settings.database_url

    def test_nats_defaults(self) -> None:
        """Test NATS default configuration."""
        settings = ConnectorSettings()

        assert settings.nats_url == "nats://localhost:4222"
        assert settings.nats_stream_name == "ECHOMIND"
        assert settings.nats_consumer_name == "connector-consumer"
        assert settings.nats_user is None
        assert settings.nats_password is None

    def test_minio_defaults(self) -> None:
        """Test MinIO default configuration."""
        settings = ConnectorSettings()

        assert settings.minio_endpoint == "localhost:9000"
        assert settings.minio_access_key == "minioadmin"
        assert settings.minio_secret_key == "minioadmin"
        assert settings.minio_secure is False

    def test_google_credentials_optional(self) -> None:
        """Test Google credentials are optional."""
        settings = ConnectorSettings()

        assert settings.google_service_account_json is None
        assert settings.google_client_id is None
        assert settings.google_client_secret is None

    def test_ms_graph_credentials_optional(self) -> None:
        """Test Microsoft Graph credentials are optional."""
        settings = ConnectorSettings()

        assert settings.ms_graph_client_id is None
        assert settings.ms_graph_client_secret is None
        assert settings.ms_graph_tenant_id is None

    def test_env_prefix(self) -> None:
        """Test environment variable prefix."""
        with patch.dict(os.environ, {"CONNECTOR_ENABLED": "false"}):
            settings = ConnectorSettings()
            assert settings.enabled is False

    def test_custom_max_file_size(self) -> None:
        """Test custom max file size from environment."""
        with patch.dict(os.environ, {"CONNECTOR_MAX_FILE_SIZE_BYTES": "50000000"}):
            settings = ConnectorSettings()
            assert settings.max_file_size_bytes == 50_000_000

    def test_custom_retry_settings(self) -> None:
        """Test custom retry settings from environment."""
        with patch.dict(
            os.environ,
            {
                "CONNECTOR_MAX_RETRIES": "5",
                "CONNECTOR_RETRY_BASE_DELAY": "2.5",
            },
        ):
            settings = ConnectorSettings()
            assert settings.max_retries == 5
            assert settings.retry_base_delay == 2.5


class TestGetSettings:
    """Tests for get_settings function."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Reset settings after each test."""
        reset_settings()

    def test_returns_settings(self) -> None:
        """Test get_settings returns ConnectorSettings instance."""
        settings = get_settings()

        assert isinstance(settings, ConnectorSettings)

    def test_caches_settings(self) -> None:
        """Test settings are cached after first call."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reset_clears_cache(self) -> None:
        """Test reset_settings clears the cache."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()

        assert settings1 is not settings2
