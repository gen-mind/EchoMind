"""
Unit tests for the Migration Service configuration.

Tests cover:
- Settings loading from environment variables
- Default values
- URL conversion
"""

import os
import sys
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from migration.config import MigrationSettings, get_settings


class TestMigrationSettings:
    """Tests for MigrationSettings class."""

    def test_loads_database_url_from_env(self) -> None:
        """Should load database_url from environment."""
        with patch.dict(
            os.environ,
            {"MIGRATION_DATABASE_URL": "postgresql://user:pass@localhost/db"},
            clear=True,
        ):
            settings = MigrationSettings()
            assert settings.database_url == "postgresql://user:pass@localhost/db"

    def test_default_retry_count(self) -> None:
        """Should use default retry_count of 5."""
        with patch.dict(
            os.environ,
            {"MIGRATION_DATABASE_URL": "postgresql://localhost/db"},
            clear=True,
        ):
            settings = MigrationSettings()
            assert settings.retry_count == 5

    def test_custom_retry_count(self) -> None:
        """Should allow custom retry_count from environment."""
        with patch.dict(
            os.environ,
            {
                "MIGRATION_DATABASE_URL": "postgresql://localhost/db",
                "MIGRATION_RETRY_COUNT": "10",
            },
            clear=True,
        ):
            settings = MigrationSettings()
            assert settings.retry_count == 10

    def test_default_retry_delay(self) -> None:
        """Should use default retry_delay of 5 seconds."""
        with patch.dict(
            os.environ,
            {"MIGRATION_DATABASE_URL": "postgresql://localhost/db"},
            clear=True,
        ):
            settings = MigrationSettings()
            assert settings.retry_delay == 5

    def test_custom_retry_delay(self) -> None:
        """Should allow custom retry_delay from environment."""
        with patch.dict(
            os.environ,
            {
                "MIGRATION_DATABASE_URL": "postgresql://localhost/db",
                "MIGRATION_RETRY_DELAY": "15",
            },
            clear=True,
        ):
            settings = MigrationSettings()
            assert settings.retry_delay == 15

    def test_default_log_level(self) -> None:
        """Should use default log_level of INFO."""
        with patch.dict(
            os.environ,
            {"MIGRATION_DATABASE_URL": "postgresql://localhost/db"},
            clear=True,
        ):
            settings = MigrationSettings()
            assert settings.log_level == "INFO"

    def test_custom_log_level(self) -> None:
        """Should allow custom log_level from environment."""
        with patch.dict(
            os.environ,
            {
                "MIGRATION_DATABASE_URL": "postgresql://localhost/db",
                "MIGRATION_LOG_LEVEL": "DEBUG",
            },
            clear=True,
        ):
            settings = MigrationSettings()
            assert settings.log_level == "DEBUG"

    def test_raises_when_database_url_missing(self) -> None:
        """Should raise validation error when database_url is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception):  # ValidationError
                MigrationSettings()


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_migration_settings(self) -> None:
        """Should return a MigrationSettings instance."""
        with patch.dict(
            os.environ,
            {"MIGRATION_DATABASE_URL": "postgresql://localhost/db"},
            clear=True,
        ):
            settings = get_settings()
            assert isinstance(settings, MigrationSettings)
