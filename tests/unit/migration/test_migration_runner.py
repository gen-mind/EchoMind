"""
Unit tests for the Migration Service runner.

Tests cover:
- Database connection waiting logic
- Migration execution
- Error handling
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from migration.main import (
    get_database_url,
    wait_for_db,
)


class TestGetDatabaseUrl:
    """Tests for get_database_url function."""

    def test_returns_migration_database_url_when_set(self) -> None:
        """Should return MIGRATION_DATABASE_URL when set."""
        with patch.dict(
            os.environ,
            {"MIGRATION_DATABASE_URL": "postgresql://test:test@localhost/test"},
            clear=True,
        ):
            result = get_database_url()
            assert result == "postgresql://test:test@localhost/test"

    def test_returns_database_url_as_fallback(self) -> None:
        """Should return DATABASE_URL when MIGRATION_DATABASE_URL not set."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://fallback:fallback@localhost/fallback"},
            clear=True,
        ):
            result = get_database_url()
            assert result == "postgresql://fallback:fallback@localhost/fallback"

    def test_converts_asyncpg_to_psycopg2(self) -> None:
        """Should convert asyncpg URL to psycopg2 format."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db"},
            clear=True,
        ):
            result = get_database_url()
            assert result == "postgresql://user:pass@localhost/db"
            assert "asyncpg" not in result

    def test_exits_when_no_url_set(self) -> None:
        """Should exit with code 1 when no database URL is set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                get_database_url()
            assert exc_info.value.code == 1


class TestWaitForDb:
    """Tests for wait_for_db function."""

    def test_returns_true_when_db_ready(self) -> None:
        """Should return True when database connection succeeds."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("migration.main.create_engine", return_value=mock_engine):
            result = wait_for_db("postgresql://test@localhost/test", retries=1, delay=0)

        assert result is True
        mock_conn.execute.assert_called_once()

    def test_returns_false_after_max_retries(self) -> None:
        """Should return False after exhausting all retries."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("", "", "")

        with patch("migration.main.create_engine", return_value=mock_engine):
            with patch("time.sleep"):  # Skip actual sleep
                result = wait_for_db(
                    "postgresql://test@localhost/test", retries=2, delay=0
                )

        assert result is False

    def test_retries_on_operational_error(self) -> None:
        """Should retry when OperationalError is raised."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()

        # Fail twice, then succeed
        call_count = 0

        def connect_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("", "", "Connection refused")
            context = MagicMock()
            context.__enter__ = MagicMock(return_value=mock_conn)
            context.__exit__ = MagicMock(return_value=False)
            return context

        mock_engine.connect.side_effect = connect_side_effect

        with patch("migration.main.create_engine", return_value=mock_engine):
            with patch("time.sleep"):  # Skip actual sleep
                result = wait_for_db(
                    "postgresql://test@localhost/test", retries=5, delay=0
                )

        assert result is True
        assert call_count == 3

    def test_disposes_engine_on_success(self) -> None:
        """Should dispose engine after successful connection."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("migration.main.create_engine", return_value=mock_engine):
            wait_for_db("postgresql://test@localhost/test", retries=1, delay=0)

        mock_engine.dispose.assert_called_once()

    def test_disposes_engine_on_failure(self) -> None:
        """Should dispose engine after failed retries."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("", "", "")

        with patch("migration.main.create_engine", return_value=mock_engine):
            with patch("time.sleep"):
                wait_for_db("postgresql://test@localhost/test", retries=1, delay=0)

        mock_engine.dispose.assert_called_once()
