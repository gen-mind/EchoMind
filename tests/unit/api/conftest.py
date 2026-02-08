"""
Shared fixtures for API unit tests.

Provides mock database sessions, authenticated users, and test clients.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass
class MockTokenUser:
    """Mock TokenUser for testing."""

    id: int = 1
    email: str = "test@example.com"
    user_name: str = "testuser"
    first_name: str | None = "Test"
    last_name: str | None = "User"
    roles: list[str] | None = None
    groups: list[str] | None = None
    external_id: str | None = "ext-123"

    def __post_init__(self):
        if self.roles is None:
            self.roles = ["user"]
        if self.groups is None:
            self.groups = ["default"]


@pytest.fixture
def mock_user() -> MockTokenUser:
    """Create a mock authenticated user."""
    return MockTokenUser()


@pytest.fixture
def mock_admin_user() -> MockTokenUser:
    """Create a mock admin user."""
    return MockTokenUser(
        id=2,
        email="admin@example.com",
        user_name="admin",
        roles=["user", "admin"],
    )


class MockAsyncSession:
    """
    Mock async database session.

    Tracks operations for verification in tests.
    """

    def __init__(self):
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushed: bool = False
        self.committed: bool = False
        self._execute_results: dict[str, Any] = {}
        self._scalars_result: list[Any] = []

    def add(self, obj: Any) -> None:
        """Track added objects."""
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        """Track deleted objects."""
        self.deleted.append(obj)

    async def flush(self) -> None:
        """Mark as flushed."""
        self.flushed = True

    async def commit(self) -> None:
        """Mark as committed."""
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        """Mock refresh - set ID if not present."""
        if hasattr(obj, "id") and obj.id is None:
            obj.id = 1
        if hasattr(obj, "creation_date") and obj.creation_date is None:
            obj.creation_date = datetime.now(timezone.utc)

    async def execute(self, query: Any) -> "MockResult":
        """Return mock query result."""
        return MockResult(self._scalars_result)

    def set_scalars_result(self, result: list[Any]) -> None:
        """Set the result for scalars().all()."""
        self._scalars_result = result


class MockResult:
    """Mock SQLAlchemy result."""

    def __init__(self, data: list[Any]):
        self._data = data

    def scalars(self) -> "MockScalars":
        """Return scalars wrapper."""
        return MockScalars(self._data)

    def scalar_one_or_none(self) -> Any | None:
        """Return first result or None."""
        return self._data[0] if self._data else None

    def all(self) -> list[Any]:
        """Return all results."""
        return self._data


class MockScalars:
    """Mock scalars wrapper."""

    def __init__(self, data: list[Any]):
        self._data = data

    def all(self) -> list[Any]:
        """Return all results."""
        return self._data

    def first(self) -> Any | None:
        """Return first result."""
        return self._data[0] if self._data else None


@pytest.fixture
def mock_db_session() -> MockAsyncSession:
    """Create a mock database session."""
    return MockAsyncSession()


@pytest.fixture
def app() -> FastAPI:
    """
    Create a FastAPI app for testing.

    This creates a minimal app with overridden dependencies.
    """
    from api.main import create_app

    return create_app()


@pytest.fixture
def client(app: FastAPI, mock_db_session: MockAsyncSession, mock_user: MockTokenUser) -> TestClient:
    """
    Create a test client with mocked dependencies.

    Args:
        app: The FastAPI application.
        mock_db_session: Mock database session.
        mock_user: Mock authenticated user.

    Returns:
        TestClient: Configured test client.
    """
    from api.dependencies import get_current_user, get_db_session

    async def override_get_db() -> AsyncGenerator[MockAsyncSession, None]:
        yield mock_db_session

    async def override_get_user() -> MockTokenUser:
        return mock_user

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_user

    return TestClient(app)


@pytest.fixture
def unauthenticated_client(app: FastAPI, mock_db_session: MockAsyncSession) -> TestClient:
    """
    Create a test client without authentication override.

    Args:
        app: The FastAPI application.
        mock_db_session: Mock database session.

    Returns:
        TestClient: Test client that will fail auth.
    """
    from api.dependencies import get_db_session

    async def override_get_db() -> AsyncGenerator[MockAsyncSession, None]:
        yield mock_db_session

    app.dependency_overrides[get_db_session] = override_get_db

    return TestClient(app)
