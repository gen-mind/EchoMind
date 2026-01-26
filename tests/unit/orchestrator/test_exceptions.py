"""Unit tests for orchestrator exceptions."""

import pytest

from orchestrator.logic.exceptions import (
    OrchestratorError,
    ConnectorNotFoundError,
    SyncTriggerError,
    DatabaseConnectionError,
    NatsConnectionError,
)


class TestOrchestratorError:
    """Tests for OrchestratorError base class."""

    def test_message_stored(self) -> None:
        """Test that message is stored on exception."""
        error = OrchestratorError("Test error message")
        assert error.message == "Test error message"

    def test_str_representation(self) -> None:
        """Test string representation of exception."""
        error = OrchestratorError("Test error")
        assert str(error) == "Test error"

    def test_is_exception(self) -> None:
        """Test that it is a proper Exception subclass."""
        error = OrchestratorError("Test")
        assert isinstance(error, Exception)


class TestConnectorNotFoundError:
    """Tests for ConnectorNotFoundError."""

    def test_connector_id_stored(self) -> None:
        """Test that connector_id is stored."""
        error = ConnectorNotFoundError(123)
        assert error.connector_id == 123

    def test_message_format(self) -> None:
        """Test error message format."""
        error = ConnectorNotFoundError(456)
        assert "456" in error.message
        assert "not found" in error.message.lower()

    def test_inherits_from_orchestrator_error(self) -> None:
        """Test inheritance from OrchestratorError."""
        error = ConnectorNotFoundError(1)
        assert isinstance(error, OrchestratorError)


class TestSyncTriggerError:
    """Tests for SyncTriggerError."""

    def test_connector_id_and_reason_stored(self) -> None:
        """Test that connector_id and reason are stored."""
        error = SyncTriggerError(123, "Connection timeout")
        assert error.connector_id == 123
        assert error.reason == "Connection timeout"

    def test_message_format(self) -> None:
        """Test error message format."""
        error = SyncTriggerError(456, "NATS unavailable")
        assert "456" in error.message
        assert "NATS unavailable" in error.message

    def test_inherits_from_orchestrator_error(self) -> None:
        """Test inheritance from OrchestratorError."""
        error = SyncTriggerError(1, "reason")
        assert isinstance(error, OrchestratorError)


class TestDatabaseConnectionError:
    """Tests for DatabaseConnectionError."""

    def test_reason_stored(self) -> None:
        """Test that reason is stored."""
        error = DatabaseConnectionError("Connection refused")
        assert error.reason == "Connection refused"

    def test_message_format(self) -> None:
        """Test error message format."""
        error = DatabaseConnectionError("Timeout")
        assert "Database connection failed" in error.message
        assert "Timeout" in error.message

    def test_inherits_from_orchestrator_error(self) -> None:
        """Test inheritance from OrchestratorError."""
        error = DatabaseConnectionError("test")
        assert isinstance(error, OrchestratorError)


class TestNatsConnectionError:
    """Tests for NatsConnectionError."""

    def test_reason_stored(self) -> None:
        """Test that reason is stored."""
        error = NatsConnectionError("Server unreachable")
        assert error.reason == "Server unreachable"

    def test_message_format(self) -> None:
        """Test error message format."""
        error = NatsConnectionError("Auth failed")
        assert "NATS connection failed" in error.message
        assert "Auth failed" in error.message

    def test_inherits_from_orchestrator_error(self) -> None:
        """Test inheritance from OrchestratorError."""
        error = NatsConnectionError("test")
        assert isinstance(error, OrchestratorError)


class TestExceptionRaising:
    """Tests for exception raising behavior."""

    def test_can_catch_specific_error(self) -> None:
        """Test that specific errors can be caught."""
        with pytest.raises(ConnectorNotFoundError):
            raise ConnectorNotFoundError(1)

    def test_can_catch_base_error(self) -> None:
        """Test that all errors can be caught via base class."""
        with pytest.raises(OrchestratorError):
            raise SyncTriggerError(1, "test")

        with pytest.raises(OrchestratorError):
            raise ConnectorNotFoundError(1)

        with pytest.raises(OrchestratorError):
            raise DatabaseConnectionError("test")

        with pytest.raises(OrchestratorError):
            raise NatsConnectionError("test")
