"""Unit tests for document management endpoints."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass
class MockConnector:
    """Mock connector ORM object for testing.

    Used when document service needs to access connector details.
    """

    id: int = 1
    name: str = "Test Connector"
    type: str = "google_drive"
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    refresh_freq_minutes: int | None = 60
    user_id: int = 1
    scope: str = "user"
    scope_id: str | None = None
    team_id: int | None = None
    status: str = "active"
    status_message: str | None = None
    last_sync_at: datetime | None = None
    docs_analyzed: int = 0
    creation_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_update: datetime | None = None
    user_id_last_update: int | None = None
    deleted_date: datetime | None = None


@dataclass
class MockDocument:
    """Mock document ORM object for testing."""

    id: int = 1
    parent_id: int | None = None
    connector_id: int = 1
    source_id: str = "source-123"
    url: str | None = "https://example.com/doc"
    original_url: str | None = None
    title: str | None = "Test Document"
    content_type: str | None = "application/pdf"
    signature: str | None = "sha256:abc123"
    chunking_session: str | None = None
    status: str = "completed"
    status_message: str | None = None
    chunk_count: int = 10
    creation_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_update: datetime | None = None
    user_id_last_update: int | None = None
    # Connector relationship - loaded via selectinload
    connector: "MockConnector | None" = None

    def __post_init__(self):
        """Auto-create connector if not provided."""
        if self.connector is None:
            self.connector = MockConnector(id=self.connector_id, user_id=1)


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


class MockDbSession:
    """Mock async database session."""

    def __init__(self):
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self._query_results: dict[str, list[Any]] = {
            "connector_ids": [],  # For select(ConnectorORM.id) - returns tuples
            "connector_objects": [],  # For select(ConnectorORM) - returns full objects
            "documents": [],
            "count": [],
            "single": [],
            "team_ids": [],  # For team queries
        }
        self._call_count = 0

    def set_connector_ids(self, ids: list[int]) -> None:
        """Set connector ID results for ID-only queries."""
        self._query_results["connector_ids"] = [(i,) for i in ids]

    def set_connector_objects(self, connectors: list[Any]) -> None:
        """Set connector object results for full object queries."""
        self._query_results["connector_objects"] = connectors

    def set_connector_results(self, results: list[Any]) -> None:
        """Legacy method - sets both IDs and objects from tuples or objects.

        If results are tuples (id, scope, scope_id), extract IDs.
        If results are objects, use them directly.
        """
        if not results:
            self._query_results["connector_ids"] = []
            self._query_results["connector_objects"] = []
            return

        # Check if first item is a tuple
        if isinstance(results[0], tuple):
            # Legacy format: (id, scope, scope_id) - convert to proper mocks
            self._query_results["connector_ids"] = [(r[0],) for r in results]
            # Create mock connector objects from tuples
            mock_connectors = []
            for r in results:
                mock_connectors.append(MockConnector(
                    id=r[0],
                    scope=r[1] if len(r) > 1 else "user",
                    scope_id=r[2] if len(r) > 2 else None,
                ))
            self._query_results["connector_objects"] = mock_connectors
        else:
            # Already proper objects
            self._query_results["connector_ids"] = [(c.id,) for c in results]
            self._query_results["connector_objects"] = results

    def set_document_results(self, results: list[Any]) -> None:
        self._query_results["documents"] = results

    def set_count_results(self, count: int) -> None:
        self._query_results["count"] = [(i,) for i in range(count)]

    def set_single_result(self, result: Any | None) -> None:
        self._query_results["single"] = [result] if result else []

    def set_team_ids(self, ids: list[int]) -> None:
        """Set team ID results for team membership queries."""
        self._query_results["team_ids"] = [(i,) for i in ids]

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass

    async def execute(self, query: Any) -> MockResult:
        self._call_count += 1
        query_str = str(query).lower()

        # Team ID queries (for permissions)
        if "teams" in query_str and "team_members" in query_str:
            return MockResult(self._query_results["team_ids"])

        # Full connector object query (for getting connector details)
        # Pattern: select(ConnectorORM).where(ConnectorORM.id == X)
        if "connectors" in query_str and "connectors.id =" in query_str and "documents" not in query_str:
            # Single connector by ID - return from objects list
            return MockResult(self._query_results["connector_objects"])

        # Connector ID-only queries (for listing accessible connectors)
        # Pattern: select(ConnectorORM.id)
        if "connectors.id" in query_str and "connectors.name" not in query_str and "documents" not in query_str:
            return MockResult(self._query_results["connector_ids"])

        # Single document query by ID (with or without joins)
        # Pattern: select(DocumentORM).where(DocumentORM.id == X)
        if "documents" in query_str and "documents.id =" in query_str:
            return MockResult(self._query_results["single"])

        # Count query for documents (only selecting ID, not other fields)
        if "documents.id" in query_str and "documents.title" not in query_str and "documents.id =" not in query_str:
            return MockResult(self._query_results["count"])

        # List documents query
        if "documents" in query_str:
            return MockResult(self._query_results["documents"])

        return MockResult([])


class TestDocumentEndpoints:
    """Tests for document endpoints."""

    @pytest.fixture
    def mock_user(self) -> MockTokenUser:
        return MockTokenUser()

    @pytest.fixture
    def mock_db(self) -> MockDbSession:
        return MockDbSession()

    @pytest.fixture
    def client(
        self,
        mock_db: MockDbSession,
        mock_user: MockTokenUser,
    ) -> TestClient:
        """Create test client with mocked dependencies."""
        from api.dependencies import get_current_user, get_db_session
        from api.middleware.error_handler import setup_error_handlers
        from api.routes.documents import router

        app = FastAPI()
        setup_error_handlers(app)  # Enable error handlers for proper HTTP responses
        app.include_router(router, prefix="/documents")

        async def override_db() -> AsyncGenerator[MockDbSession, None]:
            yield mock_db

        async def override_user() -> MockTokenUser:
            return mock_user

        app.dependency_overrides[get_db_session] = override_db
        app.dependency_overrides[get_current_user] = override_user

        return TestClient(app, raise_server_exceptions=False)

    def test_list_documents_no_connectors(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing documents when user has no connectors."""
        mock_db.set_connector_results([])

        response = client.get("/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []

    def test_list_documents_empty(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing documents when connectors have no documents."""
        mock_db.set_connector_results([(1,)])
        mock_db.set_document_results([])
        mock_db.set_count_results(0)

        response = client.get("/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []

    def test_list_documents_with_results(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing documents returns correct data."""
        mock_db.set_connector_results([(1,)])
        document = MockDocument(id=1, connector_id=1)
        mock_db.set_document_results([document])
        mock_db.set_count_results(1)

        response = client.get("/documents")

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["title"] == "Test Document"

    def test_list_documents_connector_filter(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing documents filtered by connector."""
        mock_db.set_connector_results([(1,)])
        document = MockDocument(id=1, connector_id=1)
        mock_db.set_document_results([document])
        mock_db.set_count_results(1)

        response = client.get("/documents?connector_id=1")

        assert response.status_code == 200

    def test_list_documents_status_filter(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing documents filtered by status."""
        mock_db.set_connector_results([(1,)])
        document = MockDocument(id=1, status="pending")
        mock_db.set_document_results([document])
        mock_db.set_count_results(1)

        response = client.get("/documents?doc_status=pending")

        assert response.status_code == 200

    def test_list_documents_pagination(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test listing documents with pagination."""
        mock_db.set_connector_results([(1,)])
        documents = [MockDocument(id=i) for i in range(1, 6)]
        mock_db.set_document_results(documents)
        mock_db.set_count_results(5)

        response = client.get("/documents?page=1&limit=2")

        assert response.status_code == 200

    def test_get_document_success(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test getting a single document by ID."""
        document = MockDocument(id=1, connector_id=1)
        mock_db.set_single_result(document)

        response = client.get("/documents/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Test Document"

    def test_get_document_not_found(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test getting a non-existent document returns 404."""
        mock_db.set_single_result(None)

        response = client.get("/documents/999")

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"
        assert "not found" in data["error"]["message"].lower()

    def test_get_document_other_user(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test getting another user's document returns 404."""
        mock_db.set_single_result(None)

        response = client.get("/documents/1")

        assert response.status_code == 404

    def test_delete_document_success(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test deleting a document."""
        document = MockDocument(id=1, connector_id=1)
        mock_db.set_single_result(document)

        response = client.delete("/documents/1")

        assert response.status_code == 204
        assert document in mock_db.deleted

    def test_delete_document_not_found(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test deleting a non-existent document returns 404."""
        mock_db.set_single_result(None)

        response = client.delete("/documents/999")

        assert response.status_code == 404

    def test_search_documents_no_connectors(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test searching documents when user has no connectors."""
        mock_db.set_connector_results([])

        response = client.get("/documents/search?query=test")

        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []

    def test_search_documents_empty_results(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test searching documents with no matches."""
        mock_db.set_connector_results([(1, "user", None)])

        response = client.get("/documents/search?query=nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []

    def test_search_documents_with_connector_filter(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test searching documents with connector filter."""
        mock_db.set_connector_results([(1, "user", None)])

        response = client.get("/documents/search?query=test&connector_id=1")

        assert response.status_code == 200

    def test_search_documents_limit_parameter(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test searching documents with limit parameter."""
        mock_db.set_connector_results([(1, "user", None)])

        response = client.get("/documents/search?query=test&limit=5")

        assert response.status_code == 200

    def test_search_documents_min_score_parameter(
        self,
        client: TestClient,
        mock_db: MockDbSession,
    ) -> None:
        """Test searching documents with min_score parameter."""
        mock_db.set_connector_results([(1, "user", None)])

        response = client.get("/documents/search?query=test&min_score=0.7")

        assert response.status_code == 200
