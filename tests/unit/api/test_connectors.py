"""Unit tests for connector management endpoints."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass
class MockConnector:
    """Mock connector ORM object for testing.

    Uses string values matching how ORM stores enum fields.
    The API converter handles string -> enum conversion.
    """

    id: int = 1
    name: str = "Test Connector"
    type: str = "google_drive"
    config: dict[str, Any] = field(default_factory=lambda: {"folder_id": "root"})
    state: dict[str, Any] = field(default_factory=dict)
    refresh_freq_minutes: int | None = 60
    user_id: int = 1
    scope: str = "user"
    scope_id: str | None = None
    status: str = "active"
    status_message: str | None = None
    last_sync_at: datetime | None = None
    docs_analyzed: int = 0
    creation_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_update: datetime | None = None
    user_id_last_update: int | None = None
    deleted_date: datetime | None = None


@dataclass
class MockTokenUser:
    """Mock authenticated user."""

    id: int = 1
    email: str = "test@example.com"
    user_name: str = "testuser"
    first_name: str = "Test"
    last_name: str = "User"
    roles: list[str] = field(default_factory=lambda: ["user"])
    groups: list[str] = field(default_factory=lambda: ["default"])
    external_id: str = "ext-123"


class MockResult:
    """Mock SQLAlchemy query result."""

    def __init__(self, data: list[Any]):
        self._data = data

    def scalars(self) -> "MockResult":
        return self

    def all(self) -> list[Any]:
        return self._data

    def scalar_one_or_none(self) -> Any | None:
        return self._data[0] if self._data else None

    def scalar(self) -> Any | None:
        """Return a single scalar value (e.g., count query result)."""
        if not self._data:
            return None
        # For count queries, return the first value
        first = self._data[0]
        if isinstance(first, tuple):
            return len(self._data)  # Number of rows
        return first


class MockDbSession:
    """Mock async database session."""

    def __init__(self):
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self._query_results: dict[str, list[Any]] = {
            "list": [],
            "count": [],
            "single": [],
            "documents": [],
        }

    def set_list_results(self, results: list[Any]) -> None:
        self._query_results["list"] = results

    def set_count_results(self, count: int) -> None:
        self._query_results["count"] = [(i,) for i in range(count)]

    def set_single_result(self, result: Any | None) -> None:
        self._query_results["single"] = [result] if result else []

    def set_document_results(self, results: list[Any]) -> None:
        self._query_results["documents"] = results

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        if hasattr(obj, "id") and obj.id is None:
            obj.id = 1
        if hasattr(obj, "creation_date") and obj.creation_date is None:
            obj.creation_date = datetime.now(timezone.utc)

    async def execute(self, query: Any) -> MockResult:
        query_str = str(query).lower()

        # Document pending count
        if "documents" in query_str and "pending" in query_str:
            return MockResult(self._query_results["documents"])

        # Count query - only selecting ID
        if "connectors.id" in query_str and "connectors.name" not in query_str:
            return MockResult(self._query_results["count"])

        # List query with pagination
        if "limit" in query_str or "offset" in query_str:
            return MockResult(self._query_results["list"])

        # Single item query by ID
        if "connectors.id =" in query_str or "connectors.id==" in query_str:
            return MockResult(self._query_results["single"])

        return MockResult(self._query_results["list"])


class TestConnectorEndpoints:
    """Tests for connector CRUD endpoints."""

    @pytest.fixture
    def mock_user(self) -> MockTokenUser:
        return MockTokenUser()

    @pytest.fixture
    def mock_db(self) -> MockDbSession:
        return MockDbSession()

    @pytest.fixture
    def mock_nats(self):
        """Create mock NATS publisher."""
        from unittest.mock import AsyncMock

        nats = AsyncMock()
        nats.publish = AsyncMock()
        return nats

    @pytest.fixture
    def client(
        self,
        mock_db: MockDbSession,
        mock_user: MockTokenUser,
        mock_nats,
    ) -> TestClient:
        """Create test client with mocked dependencies."""
        from api.dependencies import get_current_user, get_db_session, get_nats
        from api.routes.connectors import router

        app = FastAPI()
        app.include_router(router, prefix="/connectors")

        async def override_db() -> AsyncGenerator[MockDbSession, None]:
            yield mock_db

        async def override_user() -> MockTokenUser:
            return mock_user

        def override_nats():
            return mock_nats

        app.dependency_overrides[get_db_session] = override_db
        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_nats] = override_nats

        return TestClient(app)

    def test_list_connectors_empty(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing connectors when user has none."""
        mock_db.set_list_results([])
        mock_db.set_count_results(0)

        response = client.get("/connectors")

        assert response.status_code == 200
        data = response.json()
        assert data["connectors"] == []

    def test_list_connectors_with_results(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing connectors returns user's connectors."""
        connector = MockConnector(user_id=1)
        mock_db.set_list_results([connector])
        mock_db.set_count_results(1)

        response = client.get("/connectors")

        assert response.status_code == 200
        data = response.json()
        assert len(data["connectors"]) == 1
        assert data["connectors"][0]["name"] == "Test Connector"

    def test_list_connectors_type_filter(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing connectors with type filter."""
        connector = MockConnector(type="google_drive")
        mock_db.set_list_results([connector])
        mock_db.set_count_results(1)

        response = client.get("/connectors?connector_type=google_drive")

        assert response.status_code == 200

    def test_list_connectors_status_filter(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing connectors with status filter."""
        connector = MockConnector(status="active")
        mock_db.set_list_results([connector])
        mock_db.set_count_results(1)

        response = client.get("/connectors?connector_status=active")

        assert response.status_code == 200

    def test_get_connector_success(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test getting a single connector by ID."""
        connector = MockConnector(id=1, user_id=1)
        mock_db.set_single_result(connector)

        response = client.get("/connectors/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Test Connector"

    def test_get_connector_not_found(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test getting a non-existent connector returns 404."""
        mock_db.set_single_result(None)

        response = client.get("/connectors/999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Connector not found"

    def test_get_connector_other_user(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test getting another user's connector returns 404."""
        mock_db.set_single_result(None)

        response = client.get("/connectors/1")

        assert response.status_code == 404

    def test_create_connector_success(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test creating a new connector."""
        response = client.post(
            "/connectors",
            json={
                "name": "New Connector",
                "type": 2,  # CONNECTOR_TYPE_GOOGLE_DRIVE
                "config": {"folder_id": "abc123"},
                "refresh_freq_minutes": 30,
                "scope": 1,  # CONNECTOR_SCOPE_USER
            },
        )

        assert response.status_code == 201
        assert len(mock_db.added) == 1
        assert mock_db.added[0].name == "New Connector"

    def test_create_connector_minimal(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test creating connector with minimal fields."""
        response = client.post(
            "/connectors",
            json={
                "name": "Minimal",
                "type": 2,  # CONNECTOR_TYPE_GOOGLE_DRIVE
            },
        )

        assert response.status_code == 201

    def test_update_connector_success(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test updating an existing connector."""
        connector = MockConnector(id=1, user_id=1)
        mock_db.set_single_result(connector)

        response = client.put(
            "/connectors/1",
            json={"name": "Updated Connector"},
        )

        assert response.status_code == 200
        assert connector.name == "Updated Connector"

    def test_update_connector_not_found(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test updating a non-existent connector returns 404."""
        mock_db.set_single_result(None)

        response = client.put(
            "/connectors/999",
            json={"name": "Updated"},
        )

        assert response.status_code == 404

    def test_update_connector_config(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test updating connector config."""
        connector = MockConnector(id=1, config={"old": "value"})
        mock_db.set_single_result(connector)

        response = client.put(
            "/connectors/1",
            json={"config": {"new": "value"}},
        )

        assert response.status_code == 200
        assert connector.config == {"new": "value"}

    def test_delete_connector_success(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test soft deleting a connector."""
        connector = MockConnector(id=1, user_id=1, deleted_date=None)
        mock_db.set_single_result(connector)

        response = client.delete("/connectors/1")

        assert response.status_code == 204
        assert connector.deleted_date is not None

    def test_delete_connector_not_found(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test deleting a non-existent connector returns 404."""
        mock_db.set_single_result(None)

        response = client.delete("/connectors/999")

        assert response.status_code == 404

    def test_trigger_sync_success(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test triggering a sync for a connector."""
        connector = MockConnector(id=1, user_id=1, status="active")
        mock_db.set_single_result(connector)

        response = client.post("/connectors/1/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Sync triggered"
        assert connector.status == "pending"

    def test_trigger_sync_already_syncing(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test triggering sync when already syncing."""
        connector = MockConnector(id=1, user_id=1, status="syncing")
        mock_db.set_single_result(connector)

        response = client.post("/connectors/1/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "Sync already in progress"

    def test_trigger_sync_not_found(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test triggering sync for non-existent connector."""
        mock_db.set_single_result(None)

        response = client.post("/connectors/999/sync")

        assert response.status_code == 404

    def test_get_connector_status_success(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test getting connector status."""
        connector = MockConnector(
            id=1,
            user_id=1,
            status="active",
            docs_analyzed=100,
            last_sync_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        mock_db.set_single_result(connector)
        mock_db.set_document_results([5])  # 5 pending docs (scalar value)

        response = client.get("/connectors/1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["docs_analyzed"] == 100

    def test_get_connector_status_not_found(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test getting status for non-existent connector."""
        mock_db.set_single_result(None)

        response = client.get("/connectors/999/status")

        assert response.status_code == 404
