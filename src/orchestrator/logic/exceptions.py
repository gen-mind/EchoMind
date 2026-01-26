"""
Domain exceptions for the Orchestrator Service.

These exceptions represent business logic errors that can occur
during orchestration operations.
"""


class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""

    def __init__(self, message: str):
        """
        Initialize orchestrator error.

        Args:
            message: Error description.
        """
        self.message = message
        super().__init__(message)


class ConnectorNotFoundError(OrchestratorError):
    """Raised when a connector is not found."""

    def __init__(self, connector_id: int):
        """
        Initialize connector not found error.

        Args:
            connector_id: ID of the connector that was not found.
        """
        self.connector_id = connector_id
        super().__init__(f"Connector not found: {connector_id}")


class SyncTriggerError(OrchestratorError):
    """Raised when a sync trigger fails."""

    def __init__(self, connector_id: int, reason: str):
        """
        Initialize sync trigger error.

        Args:
            connector_id: ID of the connector.
            reason: Reason for the failure.
        """
        self.connector_id = connector_id
        self.reason = reason
        super().__init__(f"Failed to trigger sync for connector {connector_id}: {reason}")


class DatabaseConnectionError(OrchestratorError):
    """Raised when database connection fails."""

    def __init__(self, reason: str):
        """
        Initialize database connection error.

        Args:
            reason: Reason for the connection failure.
        """
        self.reason = reason
        super().__init__(f"Database connection failed: {reason}")


class NatsConnectionError(OrchestratorError):
    """Raised when NATS connection fails."""

    def __init__(self, reason: str):
        """
        Initialize NATS connection error.

        Args:
            reason: Reason for the connection failure.
        """
        self.reason = reason
        super().__init__(f"NATS connection failed: {reason}")
