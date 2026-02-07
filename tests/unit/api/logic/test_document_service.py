"""
Unit tests for DocumentService.

Tests document CRUD operations with RBAC enforcement.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.logic.document_service import DocumentService
from api.logic.exceptions import ForbiddenError, NotFoundError
from api.logic.permissions import AccessResult


class TestDocumentService:
    """Tests for DocumentService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.delete = AsyncMock()
        return db

    @pytest.fixture
    def mock_user(self):
        """Create a mock user with allowed role."""
        user = MagicMock()
        user.id = 42
        user.roles = ["echomind-allowed"]
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin user."""
        user = MagicMock()
        user.id = 100
        user.roles = ["echomind-allowed", "echomind-admins"]
        return user

    @pytest.fixture
    def mock_connector(self, mock_user):
        """Create a mock connector ORM object."""
        connector = MagicMock()
        connector.id = 1
        connector.user_id = mock_user.id
        connector.scope = "user"
        connector.team_id = None
        connector.deleted_date = None
        return connector

    @pytest.fixture
    def mock_document(self, mock_connector):
        """Create a mock document ORM object."""
        document = MagicMock()
        document.id = 10
        document.connector_id = mock_connector.id
        document.connector = mock_connector
        document.status = "analyzed"
        document.title = "Test Document"
        return document

    @pytest.fixture
    def service(self, mock_db):
        """Create a DocumentService with mocked dependencies."""
        return DocumentService(mock_db)

    # =========================================================================
    # get_document tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_document_success(self, service, mock_db, mock_document, mock_user):
        """Test getting an existing document with permission."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        # Mock permission check
        with patch.object(
            service.permissions,
            "can_view_document",
            return_value=AccessResult(True, "owner"),
        ):
            result = await service.get_document(10, mock_user)

        assert result == mock_document
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, service, mock_db, mock_user):
        """Test getting a non-existent document raises NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_document(999, mock_user)

        assert "Document" in str(exc_info.value)
        assert "999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_document_forbidden(self, service, mock_db, mock_document, mock_user):
        """Test getting a document without permission raises ForbiddenError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_view_document",
            return_value=AccessResult(False, "not owner"),
        ):
            with pytest.raises(ForbiddenError) as exc_info:
                await service.get_document(10, mock_user)

        assert "not owner" in str(exc_info.value)

    # =========================================================================
    # list_documents tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_documents_success(self, service, mock_db, mock_document, mock_user):
        """Test listing documents with accessible connectors."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1, 2, 3],
        ):
            result = await service.list_documents(mock_user, page=1, limit=20)

        assert len(result) == 1
        assert result[0] == mock_document

    @pytest.mark.asyncio
    async def test_list_documents_no_accessible_connectors(
        self, service, mock_db, mock_user
    ):
        """Test listing documents when user has no accessible connectors."""
        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[],
        ):
            result = await service.list_documents(mock_user, page=1, limit=20)

        assert result == []
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_connector(
        self, service, mock_db, mock_document, mock_user
    ):
        """Test listing documents filtered by specific connector."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1, 2, 3],
        ):
            result = await service.list_documents(
                mock_user, page=1, limit=20, connector_id=1
            )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_documents_inaccessible_connector(
        self, service, mock_db, mock_user
    ):
        """Test listing documents from inaccessible connector returns empty."""
        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1, 2, 3],
        ):
            result = await service.list_documents(
                mock_user, page=1, limit=20, connector_id=999
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_status(
        self, service, mock_db, mock_document, mock_user
    ):
        """Test listing documents filtered by status."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1],
        ):
            result = await service.list_documents(
                mock_user, page=1, limit=20, doc_status="analyzed"
            )

        assert len(result) == 1

    # =========================================================================
    # delete_document tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_document_success(
        self, service, mock_db, mock_document, mock_user
    ):
        """Test deleting a document with permission."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "owner"),
        ):
            await service.delete_document(10, mock_user)

        mock_db.delete.assert_called_once_with(mock_document)

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, service, mock_db, mock_user):
        """Test deleting non-existent document raises NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.delete_document(999, mock_user)

    @pytest.mark.asyncio
    async def test_delete_document_forbidden(
        self, service, mock_db, mock_document, mock_user
    ):
        """Test deleting document without permission raises ForbiddenError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(False, "not a lead"),
        ):
            with pytest.raises(ForbiddenError):
                await service.delete_document(10, mock_user)

        mock_db.delete.assert_not_called()

    # =========================================================================
    # search_documents tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_search_documents_gets_collections(self, service, mock_db, mock_user):
        """Test search gets accessible collections."""
        with patch.object(
            service.permissions,
            "get_search_collections",
            return_value=["user_42", "team_1", "org_default"],
        ):
            result = await service.search_documents(mock_user, "test query")

        # Returns empty since Qdrant not implemented
        assert result == []

    @pytest.mark.asyncio
    async def test_search_documents_no_collections(self, service, mock_db, mock_user):
        """Test search with no accessible collections returns empty."""
        with patch.object(
            service.permissions,
            "get_search_collections",
            return_value=[],
        ):
            result = await service.search_documents(mock_user, "test query")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_documents_filter_by_connector(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test search filtered to specific connector."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "get_search_collections",
            return_value=["user_42"],
        ), patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1],
        ):
            result = await service.search_documents(
                mock_user, "test query", connector_id=1
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_search_documents_inaccessible_connector(
        self, service, mock_db, mock_user
    ):
        """Test search with inaccessible connector returns empty."""
        with patch.object(
            service.permissions,
            "get_search_collections",
            return_value=["user_42"],
        ), patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1, 2],
        ):
            result = await service.search_documents(
                mock_user, "test query", connector_id=999
            )

        assert result == []

    # =========================================================================
    # count_documents tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_count_documents_success(self, service, mock_db, mock_user):
        """Test counting documents."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1, 2, 3],
        ):
            result = await service.count_documents(mock_user)

        assert result == 42

    @pytest.mark.asyncio
    async def test_count_documents_no_connectors(self, service, mock_db, mock_user):
        """Test counting documents with no accessible connectors."""
        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[],
        ):
            result = await service.count_documents(mock_user)

        assert result == 0

    @pytest.mark.asyncio
    async def test_count_documents_filter_by_connector(
        self, service, mock_db, mock_user
    ):
        """Test counting documents filtered by connector."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1, 2, 3],
        ):
            result = await service.count_documents(mock_user, connector_id=1)

        assert result == 10

    @pytest.mark.asyncio
    async def test_count_documents_inaccessible_connector(
        self, service, mock_db, mock_user
    ):
        """Test counting documents from inaccessible connector."""
        with patch.object(
            service.permissions,
            "get_accessible_connector_ids",
            return_value=[1, 2, 3],
        ):
            result = await service.count_documents(mock_user, connector_id=999)

        assert result == 0

    # =========================================================================
    # _get_collection_for_connector tests
    # =========================================================================

    def test_get_collection_for_user_scope(self, service, mock_connector):
        """Test collection name for user-scoped connector."""
        mock_connector.scope = "user"
        mock_connector.user_id = 42

        result = service._get_collection_for_connector(mock_connector, 42)

        assert result == "user_42"

    def test_get_collection_for_team_scope(self, service, mock_connector):
        """Test collection name for team-scoped connector."""
        mock_connector.scope = "team"
        mock_connector.team_id = 10

        result = service._get_collection_for_connector(mock_connector, 42)

        assert result == "team_10"

    def test_get_collection_for_group_scope_legacy(self, service, mock_connector):
        """Test collection name for legacy group-scoped connector."""
        mock_connector.scope = "group"
        mock_connector.team_id = 10

        result = service._get_collection_for_connector(mock_connector, 42)

        assert result == "team_10"

    def test_get_collection_for_org_scope(self, service, mock_connector):
        """Test collection name for org-scoped connector."""
        mock_connector.scope = "org"

        result = service._get_collection_for_connector(mock_connector, 42)

        assert result == "org_default"

    def test_get_collection_for_team_without_team_id(self, service, mock_connector):
        """Test collection name for team connector without team_id (legacy)."""
        mock_connector.scope = "team"
        mock_connector.team_id = None
        mock_connector.user_id = 99

        result = service._get_collection_for_connector(mock_connector, 42)

        # Falls back to user collection
        assert result == "user_99"

    def test_get_collection_for_none_scope(self, service, mock_connector):
        """Test collection name when scope is None."""
        mock_connector.scope = None
        mock_connector.user_id = 42

        result = service._get_collection_for_connector(mock_connector, 42)

        assert result == "user_42"


class TestDocumentServiceRBAC:
    """RBAC integration tests for DocumentService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.delete = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create a DocumentService."""
        return DocumentService(mock_db)

    @pytest.mark.asyncio
    async def test_team_member_can_view_team_document(self, service, mock_db):
        """Test team member can view document from team connector."""
        user = MagicMock()
        user.id = 1
        user.roles = ["echomind-allowed"]

        connector = MagicMock()
        connector.id = 1
        connector.user_id = 99  # Different user
        connector.scope = "team"
        connector.team_id = 10

        document = MagicMock()
        document.id = 100
        document.connector = connector

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = document
        mock_db.execute.return_value = mock_result

        # Mock team membership
        with patch.object(
            service.permissions,
            "can_view_document",
            return_value=AccessResult(True, "team member"),
        ):
            result = await service.get_document(100, user)

        assert result == document

    @pytest.mark.asyncio
    async def test_admin_can_view_any_document(self, service, mock_db):
        """Test admin can view any document."""
        user = MagicMock()
        user.id = 1
        user.roles = ["echomind-allowed", "echomind-admins"]

        connector = MagicMock()
        connector.id = 1
        connector.user_id = 99
        connector.scope = "user"

        document = MagicMock()
        document.id = 100
        document.connector = connector

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = document
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_view_document",
            return_value=AccessResult(True, "admin"),
        ):
            result = await service.get_document(100, user)

        assert result == document

    @pytest.mark.asyncio
    async def test_allowed_user_can_view_org_document(self, service, mock_db):
        """Test any allowed user can view document from org connector."""
        user = MagicMock()
        user.id = 1
        user.roles = ["echomind-allowed"]

        connector = MagicMock()
        connector.id = 1
        connector.user_id = 99
        connector.scope = "org"

        document = MagicMock()
        document.id = 100
        document.connector = connector

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = document
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_view_document",
            return_value=AccessResult(True, "org scope"),
        ):
            result = await service.get_document(100, user)

        assert result == document


class TestDocumentDeletionCascade:
    """Tests for full document deletion cascade (Qdrant + MinIO + DB)."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.delete = AsyncMock()
        return db

    @pytest.fixture
    def mock_qdrant(self):
        """Create a mock Qdrant client."""
        qdrant = AsyncMock()
        qdrant.delete_by_filter = AsyncMock()
        return qdrant

    @pytest.fixture
    def mock_minio(self):
        """Create a mock MinIO client."""
        minio = AsyncMock()
        minio.file_exists = AsyncMock(return_value=True)
        minio.delete_file = AsyncMock()
        return minio

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = MagicMock()
        user.id = 42
        user.roles = ["echomind-allowed"]
        return user

    @pytest.fixture
    def mock_connector(self, mock_user):
        """Create a mock connector."""
        connector = MagicMock()
        connector.id = 1
        connector.user_id = mock_user.id
        connector.scope = "user"
        connector.team_id = None
        connector.deleted_date = None
        return connector

    @pytest.fixture
    def mock_document(self, mock_connector):
        """Create a mock document with MinIO path."""
        document = MagicMock()
        document.id = 10
        document.connector_id = mock_connector.id
        document.connector = mock_connector
        document.url = "1/upload_abc123/test.pdf"  # MinIO object path
        document.status = "analyzed"
        document.title = "Test Document"
        return document

    @pytest.fixture
    def service(self, mock_db, mock_qdrant, mock_minio):
        """Create DocumentService with all dependencies."""
        return DocumentService(mock_db, qdrant=mock_qdrant, minio=mock_minio)

    @pytest.mark.asyncio
    async def test_delete_document_full_cascade(
        self, service, mock_db, mock_qdrant, mock_minio, mock_document, mock_user
    ):
        """Test delete_document performs full cascade: Qdrant + MinIO + DB."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "owner"),
        ):
            await service.delete_document(10, mock_user)

        # Verify Qdrant deletion was called
        mock_qdrant.delete_by_filter.assert_called_once()
        call_kwargs = mock_qdrant.delete_by_filter.call_args.kwargs
        assert call_kwargs["collection_name"] == "user_42"
        assert call_kwargs["filter_"]["must"][0]["match"]["value"] == 10

        # Verify MinIO deletion was called
        mock_minio.file_exists.assert_called_once()
        mock_minio.delete_file.assert_called_once_with(
            "echomind-documents", "1/upload_abc123/test.pdf"
        )

        # Verify DB deletion was called
        mock_db.delete.assert_called_once_with(mock_document)

    @pytest.mark.asyncio
    async def test_delete_document_team_collection(
        self, mock_db, mock_qdrant, mock_minio, mock_user
    ):
        """Test deletion uses correct collection for team-scoped documents."""
        connector = MagicMock()
        connector.id = 1
        connector.user_id = 99  # Different user
        connector.scope = "team"
        connector.team_id = 5

        document = MagicMock()
        document.id = 10
        document.connector = connector
        document.url = "1/upload_abc/test.pdf"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = document
        mock_db.execute.return_value = mock_result

        service = DocumentService(mock_db, qdrant=mock_qdrant, minio=mock_minio)

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "team lead"),
        ):
            await service.delete_document(10, mock_user)

        # Should use team_5 collection
        call_kwargs = mock_qdrant.delete_by_filter.call_args.kwargs
        assert call_kwargs["collection_name"] == "team_5"

    @pytest.mark.asyncio
    async def test_delete_document_qdrant_failure_continues(
        self, service, mock_db, mock_qdrant, mock_minio, mock_document, mock_user
    ):
        """Test that Qdrant failure doesn't block DB deletion."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        # Qdrant fails
        mock_qdrant.delete_by_filter.side_effect = Exception("Qdrant connection failed")

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "owner"),
        ):
            # Should not raise
            await service.delete_document(10, mock_user)

        # DB deletion should still happen
        mock_db.delete.assert_called_once_with(mock_document)

    @pytest.mark.asyncio
    async def test_delete_document_minio_failure_continues(
        self, service, mock_db, mock_qdrant, mock_minio, mock_document, mock_user
    ):
        """Test that MinIO failure doesn't block DB deletion."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        # MinIO fails
        mock_minio.delete_file.side_effect = Exception("MinIO connection failed")

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "owner"),
        ):
            # Should not raise
            await service.delete_document(10, mock_user)

        # DB deletion should still happen
        mock_db.delete.assert_called_once_with(mock_document)

    @pytest.mark.asyncio
    async def test_delete_document_file_not_in_minio(
        self, service, mock_db, mock_qdrant, mock_minio, mock_document, mock_user
    ):
        """Test deletion works when file already deleted from MinIO."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        # File doesn't exist
        mock_minio.file_exists.return_value = False

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "owner"),
        ):
            await service.delete_document(10, mock_user)

        # Should not attempt deletion
        mock_minio.delete_file.assert_not_called()
        # But DB deletion should still happen
        mock_db.delete.assert_called_once_with(mock_document)

    @pytest.mark.asyncio
    async def test_delete_document_without_qdrant_client(
        self, mock_db, mock_minio, mock_document, mock_user
    ):
        """Test deletion works without Qdrant client (graceful degradation)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        # No Qdrant client
        service = DocumentService(mock_db, qdrant=None, minio=mock_minio)

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "owner"),
        ):
            await service.delete_document(10, mock_user)

        # MinIO and DB should still work
        mock_minio.delete_file.assert_called_once()
        mock_db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_without_minio_client(
        self, mock_db, mock_qdrant, mock_document, mock_user
    ):
        """Test deletion works without MinIO client (graceful degradation)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        # No MinIO client
        service = DocumentService(mock_db, qdrant=mock_qdrant, minio=None)

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "owner"),
        ):
            await service.delete_document(10, mock_user)

        # Qdrant and DB should still work
        mock_qdrant.delete_by_filter.assert_called_once()
        mock_db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_no_url(
        self, service, mock_db, mock_qdrant, mock_minio, mock_user, mock_connector
    ):
        """Test deletion works when document has no URL (web connector)."""
        document = MagicMock()
        document.id = 10
        document.connector = mock_connector
        document.url = None  # No file, e.g., web content

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = document
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "owner"),
        ):
            await service.delete_document(10, mock_user)

        # MinIO should be skipped (no URL)
        mock_minio.file_exists.assert_not_called()
        mock_minio.delete_file.assert_not_called()
        # Qdrant and DB should still work
        mock_qdrant.delete_by_filter.assert_called_once()
        mock_db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_org_collection(
        self, mock_db, mock_qdrant, mock_minio, mock_user
    ):
        """Test deletion uses org_default collection for org-scoped documents."""
        connector = MagicMock()
        connector.id = 1
        connector.scope = "org"
        connector.team_id = None

        document = MagicMock()
        document.id = 10
        document.connector = connector
        document.url = "1/upload_abc/test.pdf"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = document
        mock_db.execute.return_value = mock_result

        service = DocumentService(mock_db, qdrant=mock_qdrant, minio=mock_minio)

        with patch.object(
            service.permissions,
            "can_edit_document",
            return_value=AccessResult(True, "admin"),
        ):
            await service.delete_document(10, mock_user)

        # Should use org_default collection
        call_kwargs = mock_qdrant.delete_by_filter.call_args.kwargs
        assert call_kwargs["collection_name"] == "org_default"
