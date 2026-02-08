"""
Unit tests for ensure_langfuse_database() in migration service.

Tests the ENABLE_LANGFUSE gate, database creation, already-exists path,
and error handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from migration.main import ensure_langfuse_database


class TestEnsureLangfuseDatabase:
    """Tests for ensure_langfuse_database()."""

    def test_creates_database_when_not_exists(self) -> None:
        """Creates langfuse database when it does not exist."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("migration.main.create_engine", return_value=mock_engine) as mock_ce:
            ensure_langfuse_database("postgresql://user:pass@host:5432/echomind")

            # Should connect to postgres maintenance DB
            mock_ce.assert_called_once_with(
                "postgresql://user:pass@host:5432/postgres",
                isolation_level="AUTOCOMMIT",
            )

            # Should execute SELECT check + CREATE DATABASE
            assert mock_conn.execute.call_count == 2
            mock_engine.dispose.assert_called_once()

    def test_skips_when_database_already_exists(self) -> None:
        """Does not create database when it already exists."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("migration.main.create_engine", return_value=mock_engine):
            ensure_langfuse_database("postgresql://user:pass@host:5432/echomind")

            # Should only execute SELECT check, not CREATE
            assert mock_conn.execute.call_count == 1
            mock_engine.dispose.assert_called_once()

    def test_handles_connection_error_gracefully(self) -> None:
        """Logs warning and continues when connection fails."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection refused")

        with patch("migration.main.create_engine", return_value=mock_engine):
            # Should not raise
            ensure_langfuse_database("postgresql://user:pass@host:5432/echomind")
            mock_engine.dispose.assert_called_once()

    def test_constructs_postgres_url_correctly(self) -> None:
        """Derives postgres maintenance DB URL from the given database URL."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("test")

        with patch("migration.main.create_engine", return_value=mock_engine) as mock_ce:
            ensure_langfuse_database("postgresql://admin:secret@db.host:5432/mydb")
            mock_ce.assert_called_once_with(
                "postgresql://admin:secret@db.host:5432/postgres",
                isolation_level="AUTOCOMMIT",
            )

    def test_disposes_engine_on_success(self) -> None:
        """Engine is always disposed even on success path."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("migration.main.create_engine", return_value=mock_engine):
            ensure_langfuse_database("postgresql://user:pass@host:5432/echomind")
            mock_engine.dispose.assert_called_once()


class TestEnsureLangfuseGate:
    """Tests for the ENABLE_LANGFUSE env var gate in main()."""

    @patch("migration.main.verify_schema")
    @patch("migration.main.run_migrations")
    @patch("migration.main.log_available_migrations")
    @patch("migration.main.get_current_revision", return_value="abc123")
    @patch("migration.main.wait_for_db", return_value=True)
    @patch("migration.main.get_database_url", return_value="postgresql://u:p@h:5432/db")
    @patch("migration.main.ensure_langfuse_database")
    def test_calls_ensure_when_enabled(
        self,
        mock_ensure: MagicMock,
        mock_url: MagicMock,
        mock_wait: MagicMock,
        mock_rev: MagicMock,
        mock_log: MagicMock,
        mock_run: MagicMock,
        mock_verify: MagicMock,
    ) -> None:
        """Calls ensure_langfuse_database when ENABLE_LANGFUSE=true."""
        from migration.main import main

        with patch.dict("os.environ", {"ENABLE_LANGFUSE": "true"}):
            main()

        mock_ensure.assert_called_once_with("postgresql://u:p@h:5432/db")

    @patch("migration.main.verify_schema")
    @patch("migration.main.run_migrations")
    @patch("migration.main.log_available_migrations")
    @patch("migration.main.get_current_revision", return_value="abc123")
    @patch("migration.main.wait_for_db", return_value=True)
    @patch("migration.main.get_database_url", return_value="postgresql://u:p@h:5432/db")
    @patch("migration.main.ensure_langfuse_database")
    def test_skips_ensure_when_disabled(
        self,
        mock_ensure: MagicMock,
        mock_url: MagicMock,
        mock_wait: MagicMock,
        mock_rev: MagicMock,
        mock_log: MagicMock,
        mock_run: MagicMock,
        mock_verify: MagicMock,
    ) -> None:
        """Does not call ensure_langfuse_database when ENABLE_LANGFUSE=false."""
        from migration.main import main

        with patch.dict("os.environ", {"ENABLE_LANGFUSE": "false"}):
            main()

        mock_ensure.assert_not_called()

    @patch("migration.main.verify_schema")
    @patch("migration.main.run_migrations")
    @patch("migration.main.log_available_migrations")
    @patch("migration.main.get_current_revision", return_value="abc123")
    @patch("migration.main.wait_for_db", return_value=True)
    @patch("migration.main.get_database_url", return_value="postgresql://u:p@h:5432/db")
    @patch("migration.main.ensure_langfuse_database")
    def test_skips_ensure_when_not_set(
        self,
        mock_ensure: MagicMock,
        mock_url: MagicMock,
        mock_wait: MagicMock,
        mock_rev: MagicMock,
        mock_log: MagicMock,
        mock_run: MagicMock,
        mock_verify: MagicMock,
    ) -> None:
        """Does not call ensure_langfuse_database when ENABLE_LANGFUSE not set."""
        from migration.main import main

        with patch.dict("os.environ", {}, clear=False):
            # Remove ENABLE_LANGFUSE if present
            import os

            os.environ.pop("ENABLE_LANGFUSE", None)
            main()

        mock_ensure.assert_not_called()
