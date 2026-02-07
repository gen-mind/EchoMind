"""Unit tests for IngestorService."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from ingestor.config import IngestorSettings, reset_settings
from ingestor.logic.ingestor_service import IngestorService
from ingestor.logic.exceptions import (
    DatabaseError,
    DocumentNotFoundError,
    EmbeddingError,
    FileNotFoundInStorageError,
    MinioError,
    OwnershipMismatchError,
)


class TestIngestorService:
    """Tests for IngestorService class."""

    def setup_method(self) -> None:
        """Create service instance with mocks for each test."""
        reset_settings()
        self.settings = IngestorSettings()

        # Mock dependencies
        self.mock_db_session = AsyncMock()
        self.mock_minio = AsyncMock()
        self.mock_qdrant = AsyncMock()

        self.service = IngestorService(
            db_session=self.mock_db_session,
            minio_client=self.mock_minio,
            qdrant_client=self.mock_qdrant,
            settings=self.settings,
        )

    def teardown_method(self) -> None:
        """Reset after tests."""
        reset_settings()

    # ==========================================
    # Initialization tests
    # ==========================================

    def test_init_stores_dependencies(self) -> None:
        """Test service stores all dependencies."""
        assert self.service._db is self.mock_db_session
        assert self.service._minio is self.mock_minio
        assert self.service._qdrant is self.mock_qdrant
        assert self.service._settings is self.settings

    def test_init_creates_processor(self) -> None:
        """Test service creates DocumentProcessor."""
        assert self.service._processor is not None

    def test_init_creates_embedder_client(self) -> None:
        """Test service creates EmbedderClient."""
        assert self.service._embedder is not None
        assert self.service._embedder._host == self.settings.embedder_host
        assert self.service._embedder._port == self.settings.embedder_port

    # ==========================================
    # Collection name building tests
    # ==========================================

    def test_build_collection_name_user_scope(self) -> None:
        """Test collection name for user scope."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="user",
            scope_id=None,
        )

        assert result == "user_123"

    def test_build_collection_name_user_scope_ignores_team_id(self) -> None:
        """Test user scope ignores team_id parameter."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="user",
            scope_id=None,
            team_id=999,  # Should be ignored
        )

        assert result == "user_123"

    def test_build_collection_name_team_scope_with_team_id(self) -> None:
        """Test team scope uses team_id for collection name."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="team",
            scope_id="legacy-scope",  # Should be ignored when team_id present
            team_id=456,
        )

        assert result == "team_456"

    def test_build_collection_name_group_scope_with_team_id(self) -> None:
        """Test group scope uses team_id (same as team scope)."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="group",
            scope_id="legacy-scope",  # Should be ignored when team_id present
            team_id=789,
        )

        assert result == "team_789"

    def test_build_collection_name_team_scope_fallback_to_scope_id(self) -> None:
        """Test team scope falls back to scope_id when team_id not provided."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="team",
            scope_id="legacy-team-id",
            team_id=None,
        )

        assert result == "team_legacy-team-id"

    def test_build_collection_name_group_scope_fallback_to_scope_id(self) -> None:
        """Test group scope falls back to scope_id when team_id not provided."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="group",
            scope_id="legacy-group-id",
            team_id=None,
        )

        assert result == "team_legacy-group-id"

    def test_build_collection_name_team_scope_fallback_to_user(self) -> None:
        """Test team scope falls back to user when neither team_id nor scope_id."""
        result = self.service._build_collection_name(
            user_id=789,
            scope="team",
            scope_id=None,
            team_id=None,
        )

        assert result == "user_789"

    def test_build_collection_name_group_scope_fallback_to_user(self) -> None:
        """Test group scope without team_id or scope_id falls back to user."""
        result = self.service._build_collection_name(
            user_id=789,
            scope="group",
            scope_id=None,
            team_id=None,
        )

        assert result == "user_789"

    def test_build_collection_name_org_scope_with_scope_id(self) -> None:
        """Test org scope uses scope_id for collection name."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="org",
            scope_id="my-org",
        )

        assert result == "org_my-org"

    def test_build_collection_name_org_scope_without_scope_id(self) -> None:
        """Test org scope defaults to org_default without scope_id."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="org",
            scope_id=None,
        )

        assert result == "org_default"

    def test_build_collection_name_org_scope_ignores_team_id(self) -> None:
        """Test org scope ignores team_id parameter."""
        result = self.service._build_collection_name(
            user_id=123,
            scope="org",
            scope_id="my-org",
            team_id=999,  # Should be ignored for org scope
        )

        assert result == "org_my-org"

    def test_build_collection_name_unknown_scope_defaults_to_user(self) -> None:
        """Test unknown scope defaults to user collection."""
        result = self.service._build_collection_name(
            user_id=456,
            scope="unknown",
            scope_id=None,
        )

        assert result == "user_456"

    def test_build_collection_name_empty_scope_defaults_to_user(self) -> None:
        """Test empty scope defaults to user collection."""
        result = self.service._build_collection_name(
            user_id=456,
            scope="",
            scope_id=None,
        )

        assert result == "user_456"

    # ==========================================
    # Point ID generation tests
    # ==========================================

    def test_generate_point_id_returns_uuid(self) -> None:
        """Test _generate_point_id returns valid UUID string."""
        result = self.service._generate_point_id(
            document_id=1,
            chunk_index=0,
            session="test-session",
        )

        # Should be valid UUID format
        uuid.UUID(result)

    def test_generate_point_id_is_deterministic(self) -> None:
        """Test _generate_point_id is deterministic for same input."""
        id1 = self.service._generate_point_id(1, 0, "session")
        id2 = self.service._generate_point_id(1, 0, "session")

        assert id1 == id2

    def test_generate_point_id_different_for_different_input(self) -> None:
        """Test _generate_point_id differs for different input."""
        id1 = self.service._generate_point_id(1, 0, "session")
        id2 = self.service._generate_point_id(1, 1, "session")
        id3 = self.service._generate_point_id(2, 0, "session")

        assert id1 != id2
        assert id1 != id3
        assert id2 != id3

    # ==========================================
    # Document retrieval tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_get_document_returns_document(self) -> None:
        """Test _get_document returns document from database."""
        mock_document = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        result = await self.service._get_document(123)

        assert result is mock_document
        self.mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document_returns_none_when_not_found(self) -> None:
        """Test _get_document returns None when document not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db_session.execute.return_value = mock_result

        result = await self.service._get_document(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_document_raises_database_error(self) -> None:
        """Test _get_document raises DatabaseError on failure."""
        self.mock_db_session.execute.side_effect = Exception("connection lost")

        with pytest.raises(DatabaseError) as exc_info:
            await self.service._get_document(1)

        assert exc_info.value.operation == "select"

    # ==========================================
    # Status update tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_update_status_updates_database(self) -> None:
        """Test _update_status updates document in database."""
        await self.service._update_status(123, "completed")

        self.mock_db_session.execute.assert_called_once()
        self.mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_with_chunk_count(self) -> None:
        """Test _update_status with chunk_count."""
        await self.service._update_status(123, "completed", chunk_count=50)

        # Verify execute was called with values including chunk_count
        self.mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_with_error_message(self) -> None:
        """Test _update_status with error_message."""
        await self.service._update_status(123, "error", error_message="Failed")

        self.mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_raises_database_error(self) -> None:
        """Test _update_status raises DatabaseError on failure."""
        self.mock_db_session.execute.side_effect = Exception("update failed")

        with pytest.raises(DatabaseError) as exc_info:
            await self.service._update_status(1, "processing")

        assert exc_info.value.operation == "update"

    # ==========================================
    # File download tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_download_file_returns_bytes(self) -> None:
        """Test _download_file returns file content."""
        self.mock_minio.download_file.return_value = b"file content"

        result = await self.service._download_file("path/to/file.pdf")

        assert result == b"file content"
        self.mock_minio.download_file.assert_called_once_with(
            bucket_name=self.settings.minio_bucket,
            object_name="path/to/file.pdf",
        )

    @pytest.mark.asyncio
    async def test_download_file_raises_file_not_found(self) -> None:
        """Test _download_file raises FileNotFoundInStorageError."""
        self.mock_minio.download_file.return_value = None

        with pytest.raises(FileNotFoundInStorageError) as exc_info:
            await self.service._download_file("missing.pdf")

        assert exc_info.value.file_path == "missing.pdf"

    @pytest.mark.asyncio
    async def test_download_file_raises_minio_error(self) -> None:
        """Test _download_file raises MinioError on other failures."""
        self.mock_minio.download_file.side_effect = Exception("connection refused")

        with pytest.raises(MinioError) as exc_info:
            await self.service._download_file("file.pdf")

        assert exc_info.value.operation == "download"

    @pytest.mark.asyncio
    async def test_download_file_handles_no_such_key(self) -> None:
        """Test _download_file raises FileNotFoundInStorageError for NoSuchKey."""
        self.mock_minio.download_file.side_effect = Exception("NoSuchKey: file not found")

        with pytest.raises(FileNotFoundInStorageError):
            await self.service._download_file("missing.pdf")

    # ==========================================
    # Collection management tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_ensure_collection_creates_if_not_exists(self) -> None:
        """Test _ensure_collection creates collection when needed."""
        self.mock_qdrant.create_collection.return_value = True

        await self.service._ensure_collection("test_collection", 1024)

        self.mock_qdrant.create_collection.assert_called_once_with(
            collection_name="test_collection",
            vector_size=1024,
        )

    @pytest.mark.asyncio
    async def test_ensure_collection_handles_existing(self) -> None:
        """Test _ensure_collection handles existing collection."""
        self.mock_qdrant.create_collection.return_value = False

        # Should not raise
        await self.service._ensure_collection("existing_collection", 768)

    @pytest.mark.asyncio
    async def test_ensure_collection_handles_error(self) -> None:
        """Test _ensure_collection handles creation error gracefully."""
        self.mock_qdrant.create_collection.side_effect = Exception("already exists")

        # Should not raise
        await self.service._ensure_collection("collection", 512)

    # ==========================================
    # Embed and store tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_embed_and_store_empty_texts(self) -> None:
        """Test _embed_and_store returns 0 for empty texts."""
        result = await self.service._embed_and_store(
            texts=[],
            document_id=1,
            collection_name="test",
            chunking_session="session",
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_embed_and_store_calls_embedder(self) -> None:
        """Test _embed_and_store calls embedder service."""
        with patch.object(
            self.service._embedder,
            "embed_batch",
            return_value=[[0.1, 0.2], [0.3, 0.4]],
        ):
            result = await self.service._embed_and_store(
                texts=["chunk1", "chunk2"],
                document_id=123,
                collection_name="user_1",
                chunking_session="session-123",
            )

            assert result == 2
            self.service._embedder.embed_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_and_store_upserts_to_qdrant(self) -> None:
        """Test _embed_and_store upserts vectors to Qdrant."""
        with patch.object(
            self.service._embedder,
            "embed_batch",
            return_value=[[0.1], [0.2]],
        ):
            await self.service._embed_and_store(
                texts=["a", "b"],
                document_id=1,
                collection_name="collection",
                chunking_session="session",
            )

            self.mock_qdrant.upsert.assert_called_once()
            call_kwargs = self.mock_qdrant.upsert.call_args[1]
            assert call_kwargs["collection_name"] == "collection"
            assert len(call_kwargs["vectors"]) == 2
            assert len(call_kwargs["payloads"]) == 2
            assert len(call_kwargs["ids"]) == 2

    @pytest.mark.asyncio
    async def test_embed_and_store_payload_structure(self) -> None:
        """Test _embed_and_store creates correct payload structure."""
        with patch.object(
            self.service._embedder,
            "embed_batch",
            return_value=[[0.1]],
        ):
            await self.service._embed_and_store(
                texts=["test content"],
                document_id=123,
                collection_name="collection",
                chunking_session="session-id",
                content_type="text",
            )

            call_kwargs = self.mock_qdrant.upsert.call_args[1]
            payload = call_kwargs["payloads"][0]

            assert payload["document_id"] == 123
            assert payload["chunk_index"] == 0
            assert payload["chunking_session"] == "session-id"
            assert payload["content_type"] == "text"
            assert "text" in payload  # Truncated text for preview

    @pytest.mark.asyncio
    async def test_embed_and_store_raises_on_vector_count_mismatch(self) -> None:
        """Test _embed_and_store raises EmbeddingError when vector count != text count.

        If the embedder returns fewer vectors than texts (e.g., partial failure),
        continuing would corrupt Qdrant with misaligned vectors/payloads.
        """
        with patch.object(
            self.service._embedder,
            "embed_batch",
            return_value=[[0.1]],  # Only 1 vector for 3 texts
        ):
            with pytest.raises(EmbeddingError) as exc_info:
                await self.service._embed_and_store(
                    texts=["chunk1", "chunk2", "chunk3"],
                    document_id=99,
                    collection_name="test",
                    chunking_session="session",
                )

            assert "mismatch" in exc_info.value.message.lower()
            assert exc_info.value.document_id == 99

            # Verify Qdrant was NOT called (data integrity protection)
            self.mock_qdrant.upsert.assert_not_called()

    # ==========================================
    # Delete vectors tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_delete_document_vectors_calls_qdrant(self) -> None:
        """Test delete_document_vectors calls Qdrant delete."""
        await self.service.delete_document_vectors(
            document_id=123,
            collection_name="user_1",
        )

        self.mock_qdrant.delete_by_filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_vectors_handles_error(self) -> None:
        """Test delete_document_vectors handles errors gracefully."""
        self.mock_qdrant.delete_by_filter.side_effect = Exception("delete failed")

        # Should not raise, just log warning
        await self.service.delete_document_vectors(
            document_id=1,
            collection_name="collection",
        )

    # ==========================================
    # Process document tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_process_document_not_found_raises(self) -> None:
        """Test process_document raises DocumentNotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db_session.execute.return_value = mock_result

        with pytest.raises(DocumentNotFoundError):
            await self.service.process_document(
                document_id=999,
                connector_id=1,
                user_id=1,
                minio_path="path/to/file.pdf",
                chunking_session="session",
                scope="user",
            )

    def _create_mock_document(
        self,
        connector_id: int,
        user_id: int,
        content_type: str = "application/pdf",
        document_id: int = 1,
    ) -> MagicMock:
        """Helper to create a mock document with connector for ownership verification."""
        mock_connector = MagicMock()
        mock_connector.user_id = user_id

        mock_document = MagicMock()
        mock_document.id = document_id
        mock_document.connector_id = connector_id
        mock_document.connector = mock_connector
        mock_document.content_type = content_type
        return mock_document

    @pytest.mark.asyncio
    async def test_process_document_full_pipeline(self) -> None:
        """Test process_document runs full pipeline."""
        # Mock document lookup with connector for ownership verification
        mock_document = self._create_mock_document(
            connector_id=1, user_id=456, content_type="application/pdf"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        # Mock file download
        self.mock_minio.download_file.return_value = b"PDF content"

        # Mock processing
        with patch.object(
            self.service._processor,
            "process",
            return_value=(["chunk1", "chunk2"], []),
        ):
            # Mock embedder
            with patch.object(
                self.service._embedder,
                "get_dimension",
                return_value=1024,
            ):
                with patch.object(
                    self.service._embedder,
                    "embed_batch",
                    return_value=[[0.1], [0.2]],
                ):
                    # Mock Qdrant
                    self.mock_qdrant.create_collection.return_value = True

                    result = await self.service.process_document(
                        document_id=123,
                        connector_id=1,
                        user_id=456,
                        minio_path="docs/file.pdf",
                        chunking_session="session-123",
                        scope="user",
                    )

                    assert result["document_id"] == 123
                    assert result["chunk_count"] == 2
                    assert result["collection_name"] == "user_456"

    @pytest.mark.asyncio
    async def test_process_document_with_team_scope(self) -> None:
        """Test process_document routes team-scoped docs to team collection."""
        # Mock document lookup with connector for ownership verification
        mock_document = self._create_mock_document(
            connector_id=1, user_id=456, content_type="application/pdf"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        # Mock file download
        self.mock_minio.download_file.return_value = b"PDF content"

        # Mock processing
        with patch.object(
            self.service._processor,
            "process",
            return_value=(["chunk1"], []),
        ):
            with patch.object(
                self.service._embedder,
                "get_dimension",
                return_value=1024,
            ):
                with patch.object(
                    self.service._embedder,
                    "embed_batch",
                    return_value=[[0.1]],
                ):
                    self.mock_qdrant.create_collection.return_value = True

                    result = await self.service.process_document(
                        document_id=123,
                        connector_id=1,
                        user_id=456,
                        minio_path="docs/file.pdf",
                        chunking_session="session-123",
                        scope="team",
                        scope_id="legacy-id",  # Should be ignored
                        team_id=789,
                    )

                    assert result["document_id"] == 123
                    assert result["chunk_count"] == 1
                    assert result["collection_name"] == "team_789"

    @pytest.mark.asyncio
    async def test_process_document_with_group_scope(self) -> None:
        """Test process_document routes group-scoped docs to team collection."""
        # Mock document lookup with connector for ownership verification
        mock_document = self._create_mock_document(
            connector_id=2, user_id=10, content_type="text/plain"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        # Mock file download
        self.mock_minio.download_file.return_value = b"text content"

        # Mock processing
        with patch.object(
            self.service._processor,
            "process",
            return_value=(["chunk"], []),
        ):
            with patch.object(
                self.service._embedder,
                "get_dimension",
                return_value=768,
            ):
                with patch.object(
                    self.service._embedder,
                    "embed_batch",
                    return_value=[[0.5]],
                ):
                    self.mock_qdrant.create_collection.return_value = True

                    result = await self.service.process_document(
                        document_id=100,
                        connector_id=2,
                        user_id=10,
                        minio_path="docs/doc.txt",
                        chunking_session="session",
                        scope="group",  # Group scope maps to team
                        team_id=55,
                    )

                    assert result["collection_name"] == "team_55"

    @pytest.mark.asyncio
    async def test_process_document_with_org_scope(self) -> None:
        """Test process_document routes org-scoped docs to org collection."""
        # Mock document lookup with connector for ownership verification
        mock_document = self._create_mock_document(
            connector_id=3, user_id=30, content_type="application/pdf"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        # Mock file download
        self.mock_minio.download_file.return_value = b"PDF"

        # Mock processing
        with patch.object(
            self.service._processor,
            "process",
            return_value=(["chunk"], []),
        ):
            with patch.object(
                self.service._embedder,
                "get_dimension",
                return_value=1024,
            ):
                with patch.object(
                    self.service._embedder,
                    "embed_batch",
                    return_value=[[0.1]],
                ):
                    self.mock_qdrant.create_collection.return_value = True

                    result = await self.service.process_document(
                        document_id=200,
                        connector_id=3,
                        user_id=30,
                        minio_path="docs/org-doc.pdf",
                        chunking_session="org-session",
                        scope="org",
                        scope_id="acme-corp",
                        team_id=None,  # Org scope ignores team_id
                    )

                    assert result["collection_name"] == "org_acme-corp"

    @pytest.mark.asyncio
    async def test_process_document_empty_content(self) -> None:
        """Test process_document raises exception when extraction produces no content."""
        from ingestor.logic.exceptions import NoExtractableContentError

        # Mock document lookup with connector for ownership verification
        mock_document = self._create_mock_document(
            connector_id=1, user_id=1, content_type="text/plain"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        # Mock file download
        self.mock_minio.download_file.return_value = b""

        # Mock processing - returns empty (no chunks, no structured images)
        with patch.object(
            self.service._processor,
            "process",
            return_value=([], []),
        ):
            # Should raise NoExtractableContentError instead of returning success
            with pytest.raises(NoExtractableContentError) as exc_info:
                await self.service.process_document(
                    document_id=1,
                    connector_id=1,
                    user_id=1,
                    minio_path="empty.txt",
                    chunking_session="session",
                    scope="user",
                )

            # Verify exception details
            assert exc_info.value.document_id == 1
            assert "No extractable content" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_document_updates_status_on_error(self) -> None:
        """Test process_document updates status to error on failure."""
        # Mock document lookup with connector for ownership verification
        mock_document = self._create_mock_document(
            connector_id=1, user_id=1, content_type="application/pdf", document_id=123
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        # Mock file download to fail
        self.mock_minio.download_file.side_effect = Exception("download failed")

        with pytest.raises(Exception):
            await self.service.process_document(
                document_id=123,
                connector_id=1,
                user_id=1,
                minio_path="file.pdf",
                chunking_session="session",
                scope="user",
            )

        # Should have: 1) document lookup, 2) status update to processing
        # Since download fails, status update to error happens in exception handler
        assert self.mock_db_session.execute.call_count >= 1

    # ==========================================
    # Ownership verification tests (SECURITY)
    # ==========================================

    def test_verify_ownership_passes_when_matching(self) -> None:
        """Test _verify_ownership passes when claims match."""
        mock_connector = MagicMock()
        mock_connector.user_id = 42

        mock_document = MagicMock()
        mock_document.id = 10
        mock_document.connector_id = 1
        mock_document.connector = mock_connector

        # Should not raise
        self.service._verify_ownership(mock_document, claimed_connector_id=1, claimed_user_id=42)

    def test_verify_ownership_raises_on_connector_mismatch(self) -> None:
        """Test _verify_ownership raises when connector_id doesn't match."""
        mock_connector = MagicMock()
        mock_connector.user_id = 42

        mock_document = MagicMock()
        mock_document.id = 10
        mock_document.connector_id = 1  # Actual connector
        mock_document.connector = mock_connector

        with pytest.raises(OwnershipMismatchError) as exc_info:
            self.service._verify_ownership(
                mock_document,
                claimed_connector_id=999,  # Claimed different connector
                claimed_user_id=42,
            )

        assert exc_info.value.document_id == 10
        assert exc_info.value.expected_connector_id == 999
        assert exc_info.value.actual_connector_id == 1

    def test_verify_ownership_raises_on_user_mismatch(self) -> None:
        """Test _verify_ownership raises when user_id doesn't match connector owner."""
        mock_connector = MagicMock()
        mock_connector.user_id = 42  # Actual owner

        mock_document = MagicMock()
        mock_document.id = 10
        mock_document.connector_id = 1
        mock_document.connector = mock_connector

        with pytest.raises(OwnershipMismatchError) as exc_info:
            self.service._verify_ownership(
                mock_document,
                claimed_connector_id=1,
                claimed_user_id=999,  # Claimed different user
            )

        assert exc_info.value.document_id == 10
        assert exc_info.value.expected_user_id == 999
        assert exc_info.value.actual_user_id == 42

    def test_verify_ownership_error_message_includes_security_alert(self) -> None:
        """Test OwnershipMismatchError message includes SECURITY label."""
        mock_connector = MagicMock()
        mock_connector.user_id = 1

        mock_document = MagicMock()
        mock_document.id = 10
        mock_document.connector_id = 1
        mock_document.connector = mock_connector

        with pytest.raises(OwnershipMismatchError) as exc_info:
            self.service._verify_ownership(mock_document, claimed_connector_id=999, claimed_user_id=1)

        assert "SECURITY" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_process_document_verifies_ownership(self) -> None:
        """Test process_document verifies ownership before processing."""
        # Mock document with connector
        mock_connector = MagicMock()
        mock_connector.user_id = 42

        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.connector_id = 1
        mock_document.connector = mock_connector
        mock_document.content_type = "text/plain"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        # Try to process with WRONG connector_id
        with pytest.raises(OwnershipMismatchError):
            await self.service.process_document(
                document_id=1,
                connector_id=999,  # Wrong connector
                user_id=42,
                minio_path="file.txt",
                chunking_session="session",
                scope="user",
            )

    @pytest.mark.asyncio
    async def test_process_document_verifies_user_ownership(self) -> None:
        """Test process_document verifies user_id matches connector owner."""
        # Mock document with connector
        mock_connector = MagicMock()
        mock_connector.user_id = 42  # Actual owner

        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.connector_id = 1
        mock_document.connector = mock_connector
        mock_document.content_type = "text/plain"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        self.mock_db_session.execute.return_value = mock_result

        # Try to process with WRONG user_id
        with pytest.raises(OwnershipMismatchError):
            await self.service.process_document(
                document_id=1,
                connector_id=1,
                user_id=999,  # Wrong user - attack vector!
                minio_path="file.txt",
                chunking_session="session",
                scope="user",
            )

    # ==========================================
    # Close tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_close_closes_embedder(self) -> None:
        """Test close() closes embedder client."""
        with patch.object(self.service._embedder, "close") as mock_close:
            await self.service.close()

            mock_close.assert_called_once()

    # ==========================================
    # Empty content handling tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_process_document_raises_on_empty_content(self) -> None:
        """Test process_document raises NoExtractableContentError when no chunks extracted."""
        from ingestor.logic.exceptions import NoExtractableContentError

        # Mock document
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.connector_id = 1
        mock_document.connector.user_id = 42
        mock_document.content_type = "application/pdf"

        with patch.object(
            self.service, "_get_document", return_value=mock_document
        ), patch.object(
            self.service, "_download_file", return_value=b"fake file bytes"
        ), patch.object(
            self.service._processor, "process", return_value=([], [])  # No chunks!
        ), patch.object(
            self.service, "_update_status"
        ) as mock_update:
            with pytest.raises(NoExtractableContentError) as exc_info:
                await self.service.process_document(
                    document_id=1,
                    connector_id=1,
                    user_id=42,
                    minio_path="empty.pdf",
                    chunking_session="session",
                    scope="user",
                )

            # Should raise with document ID and MIME type
            assert exc_info.value.document_id == 1
            assert exc_info.value.mime_type == "application/pdf"
            assert "No extractable content" in str(exc_info.value)

            # Should have updated status to "error" via exception handling
            # (The exception is caught by the outer try/except in process_document)

    @pytest.mark.asyncio
    async def test_process_document_empty_chunks_updates_error_status(self) -> None:
        """Test that empty content results in error status via exception path."""
        from ingestor.logic.exceptions import NoExtractableContentError

        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.connector_id = 1
        mock_document.connector.user_id = 42
        mock_document.content_type = "text/plain"

        with patch.object(
            self.service, "_get_document", return_value=mock_document
        ), patch.object(
            self.service, "_download_file", return_value=b""
        ), patch.object(
            self.service._processor, "process", return_value=([], [])
        ), patch.object(
            self.service, "_update_status"
        ) as mock_update:
            with pytest.raises(NoExtractableContentError):
                await self.service.process_document(
                    document_id=1,
                    connector_id=1,
                    user_id=42,
                    minio_path="empty.txt",
                    chunking_session="session",
                    scope="user",
                )

            # Exception should be raised before any success status update
            # The outer exception handler will call _update_status with "error"
