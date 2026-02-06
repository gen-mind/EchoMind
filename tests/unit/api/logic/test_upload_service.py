"""
Unit tests for UploadService.

Tests the file upload flow via pre-signed URLs.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.logic.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from api.logic.upload_service import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
    UNSUPPORTED_MEDIA_TYPES,
    UploadService,
)


class TestUploadServiceInitiate:
    """Tests for UploadService.initiate_upload."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.delete = AsyncMock()
        return db

    @pytest.fixture
    def mock_minio(self):
        """Create a mock MinIO client."""
        minio = MagicMock()
        minio.presigned_put_url = AsyncMock(
            return_value="https://minio.example.com/bucket/path?signature=abc123"
        )
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
        connector.scope_id = None
        return connector

    @pytest.fixture
    def service(self, mock_db, mock_minio):
        """Create UploadService with mocked dependencies."""
        return UploadService(mock_db, minio=mock_minio)

    @pytest.mark.asyncio
    async def test_initiate_upload_success(
        self, service, mock_db, mock_minio, mock_user, mock_connector
    ):
        """Test successful upload initiation."""
        with patch(
            "api.logic.upload_service.connector_crud.get_or_create_upload_connector",
            return_value=mock_connector,
        ):
            # Mock document refresh to set the ID
            async def set_doc_id(doc):
                doc.id = 100

            mock_db.refresh = AsyncMock(side_effect=set_doc_id)

            result = await service.initiate_upload(
                filename="test.pdf",
                content_type="application/pdf",
                size=1024,
                user=mock_user,
            )

        assert result.document_id == 100
        assert result.upload_url.startswith("https://")
        assert result.expires_in == 3600
        assert "test.pdf" in result.storage_path

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_minio.presigned_put_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_upload_invalid_content_type(
        self, service, mock_user
    ):
        """Test that invalid content type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="test.exe",
                content_type="application/x-executable",
                size=1024,
                user=mock_user,
            )

        assert "not allowed" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_initiate_upload_file_too_large(
        self, service, mock_user
    ):
        """Test that file size exceeding limit raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="huge.pdf",
                content_type="application/pdf",
                size=MAX_FILE_SIZE + 1,
                user=mock_user,
            )

        assert "exceeds maximum" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_initiate_upload_zero_size(
        self, service, mock_user
    ):
        """Test that zero file size raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="empty.pdf",
                content_type="application/pdf",
                size=0,
                user=mock_user,
            )

        assert "greater than 0" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_initiate_upload_minio_failure(
        self, service, mock_db, mock_minio, mock_user, mock_connector
    ):
        """Test that MinIO failure raises ServiceUnavailableError."""
        mock_minio.presigned_put_url = AsyncMock(
            side_effect=Exception("MinIO connection failed")
        )

        with patch(
            "api.logic.upload_service.connector_crud.get_or_create_upload_connector",
            return_value=mock_connector,
        ):
            async def set_doc_id(doc):
                doc.id = 100

            mock_db.refresh = AsyncMock(side_effect=set_doc_id)

            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.initiate_upload(
                    filename="test.pdf",
                    content_type="application/pdf",
                    size=1024,
                    user=mock_user,
                )

        assert "MinIO" in str(exc_info.value.message)
        # Verify cleanup - document should be deleted
        mock_db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_upload_sanitizes_filename(
        self, service, mock_db, mock_minio, mock_user, mock_connector
    ):
        """Test that dangerous characters in filename are sanitized."""
        with patch(
            "api.logic.upload_service.connector_crud.get_or_create_upload_connector",
            return_value=mock_connector,
        ):
            async def set_doc_id(doc):
                doc.id = 100

            mock_db.refresh = AsyncMock(side_effect=set_doc_id)

            result = await service.initiate_upload(
                filename="path/to/../dangerous\\file.pdf",
                content_type="application/pdf",
                size=1024,
                user=mock_user,
            )

        # Path separators should be replaced with underscores
        assert "/" not in result.storage_path.split("/")[-1]
        assert "\\" not in result.storage_path.split("/")[-1]

    @pytest.mark.asyncio
    async def test_initiate_upload_all_allowed_types(self, service, mock_user):
        """Test that all allowed content types are accepted."""
        for content_type in ALLOWED_CONTENT_TYPES:
            try:
                # Will fail at connector lookup, but validates content type passes
                with patch(
                    "api.logic.upload_service.connector_crud.get_or_create_upload_connector",
                    side_effect=Exception("Expected"),
                ):
                    await service.initiate_upload(
                        filename="test.file",
                        content_type=content_type,
                        size=1024,
                        user=mock_user,
                    )
            except Exception as e:
                # Only ValidationError for content type is a failure
                if isinstance(e, ValidationError) and "not allowed" in str(e):
                    pytest.fail(f"Content type {content_type} should be allowed")


class TestUnsupportedMediaTypes:
    """Tests for audio/video content type rejection."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_minio(self):
        """Create a mock MinIO client."""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = MagicMock()
        user.id = 42
        user.roles = ["echomind-allowed"]
        return user

    @pytest.fixture
    def service(self, mock_db, mock_minio):
        """Create UploadService with mocked dependencies."""
        return UploadService(mock_db, minio=mock_minio)

    @pytest.mark.asyncio
    async def test_audio_mpeg_rejected(self, service, mock_user):
        """Test that MP3 files are rejected with clear message."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="podcast.mp3",
                content_type="audio/mpeg",
                size=1024,
                user=mock_user,
            )

        assert "Audio and video files are not yet supported" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_audio_wav_rejected(self, service, mock_user):
        """Test that WAV files are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="recording.wav",
                content_type="audio/wav",
                size=1024,
                user=mock_user,
            )

        assert "not yet supported" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_audio_ogg_rejected(self, service, mock_user):
        """Test that OGG audio files are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="voice.ogg",
                content_type="audio/ogg",
                size=1024,
                user=mock_user,
            )

        assert "not yet supported" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_video_mp4_rejected(self, service, mock_user):
        """Test that MP4 video files are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="video.mp4",
                content_type="video/mp4",
                size=1024,
                user=mock_user,
            )

        assert "Audio and video files are not yet supported" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_video_webm_rejected(self, service, mock_user):
        """Test that WebM video files are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="video.webm",
                content_type="video/webm",
                size=1024,
                user=mock_user,
            )

        assert "not yet supported" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_all_unsupported_media_types_rejected(self, service, mock_user):
        """Test that ALL unsupported media types are rejected."""
        for content_type in UNSUPPORTED_MEDIA_TYPES:
            with pytest.raises(ValidationError) as exc_info:
                await service.initiate_upload(
                    filename="media.file",
                    content_type=content_type,
                    size=1024,
                    user=mock_user,
                )

            assert "not yet supported" in str(exc_info.value.message), \
                f"Expected 'not yet supported' in error for {content_type}"

    @pytest.mark.asyncio
    async def test_unsupported_media_error_message_is_helpful(self, service, mock_user):
        """Test that error message suggests alternatives."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="song.mp3",
                content_type="audio/mpeg",
                size=1024,
                user=mock_user,
            )

        message = str(exc_info.value.message)
        # Should suggest what IS supported
        assert "documents" in message.lower() or "PDF" in message
        assert "images" in message.lower()

    @pytest.mark.asyncio
    async def test_case_insensitive_media_type_rejection(self, service, mock_user):
        """Test that media type rejection is case-insensitive."""
        with pytest.raises(ValidationError) as exc_info:
            await service.initiate_upload(
                filename="video.mp4",
                content_type="VIDEO/MP4",  # uppercase
                size=1024,
                user=mock_user,
            )

        assert "not yet supported" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_audio_no_intersection_with_allowed(self, service, mock_user):
        """Verify no audio types are in ALLOWED_CONTENT_TYPES."""
        audio_types = {t for t in UNSUPPORTED_MEDIA_TYPES if t.startswith("audio/")}
        assert not audio_types.intersection(ALLOWED_CONTENT_TYPES), \
            "Audio types should not be in ALLOWED_CONTENT_TYPES"

    @pytest.mark.asyncio
    async def test_video_no_intersection_with_allowed(self, service, mock_user):
        """Verify no video types are in ALLOWED_CONTENT_TYPES."""
        video_types = {t for t in UNSUPPORTED_MEDIA_TYPES if t.startswith("video/")}
        assert not video_types.intersection(ALLOWED_CONTENT_TYPES), \
            "Video types should not be in ALLOWED_CONTENT_TYPES"

    def test_unsupported_media_types_constant_not_empty(self):
        """Verify UNSUPPORTED_MEDIA_TYPES is populated."""
        assert len(UNSUPPORTED_MEDIA_TYPES) > 0
        assert any(t.startswith("audio/") for t in UNSUPPORTED_MEDIA_TYPES)
        assert any(t.startswith("video/") for t in UNSUPPORTED_MEDIA_TYPES)


class TestUploadServiceComplete:
    """Tests for UploadService.complete_upload."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_minio(self):
        """Create a mock MinIO client."""
        minio = MagicMock()
        minio.file_exists = AsyncMock(return_value=True)
        minio.get_file_info = AsyncMock(return_value={"etag": "abc123", "size": 1024})
        return minio

    @pytest.fixture
    def mock_nats(self):
        """Create a mock NATS publisher."""
        nats = MagicMock()
        nats.publish = AsyncMock()
        return nats

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
        connector.scope_id = None
        return connector

    @pytest.fixture
    def mock_document(self, mock_connector):
        """Create a mock document in uploading status."""
        document = MagicMock()
        document.id = 100
        document.connector_id = mock_connector.id
        document.connector = mock_connector
        document.url = "1/upload_abc123/test.pdf"
        document.title = "test.pdf"
        document.status = "uploading"
        return document

    @pytest.fixture
    def service(self, mock_db, mock_minio, mock_nats):
        """Create UploadService with mocked dependencies."""
        return UploadService(mock_db, minio=mock_minio, nats=mock_nats)

    @pytest.mark.asyncio
    async def test_complete_upload_success(
        self, service, mock_db, mock_minio, mock_nats, mock_user, mock_document
    ):
        """Test successful upload completion."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        result = await service.complete_upload(100, mock_user)

        assert result == mock_document
        assert mock_document.status == "pending"
        mock_db.commit.assert_called()
        mock_minio.file_exists.assert_called_once()
        mock_nats.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_upload_not_found(
        self, service, mock_db, mock_user
    ):
        """Test completing non-existent document raises NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.complete_upload(999, mock_user)

    @pytest.mark.asyncio
    async def test_complete_upload_wrong_owner(
        self, service, mock_db, mock_user, mock_document, mock_connector
    ):
        """Test completing document owned by another user raises NotFoundError."""
        mock_connector.user_id = 999  # Different user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.complete_upload(100, mock_user)

    @pytest.mark.asyncio
    async def test_complete_upload_wrong_status(
        self, service, mock_db, mock_user, mock_document
    ):
        """Test completing document not in uploading status raises ValidationError."""
        mock_document.status = "pending"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValidationError) as exc_info:
            await service.complete_upload(100, mock_user)

        assert "uploading" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_complete_upload_file_not_in_minio(
        self, service, mock_db, mock_minio, mock_user, mock_document
    ):
        """Test completing when file not in MinIO raises ValidationError."""
        mock_minio.file_exists = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValidationError) as exc_info:
            await service.complete_upload(100, mock_user)

        assert "not found in storage" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_complete_upload_minio_failure(
        self, service, mock_db, mock_minio, mock_user, mock_document
    ):
        """Test MinIO failure during completion raises ServiceUnavailableError."""
        mock_minio.file_exists = AsyncMock(side_effect=Exception("MinIO down"))
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with pytest.raises(ServiceUnavailableError):
            await service.complete_upload(100, mock_user)

    @pytest.mark.asyncio
    async def test_complete_upload_without_nats(
        self, mock_db, mock_minio, mock_user, mock_document
    ):
        """Test completion works without NATS (graceful degradation)."""
        service = UploadService(mock_db, minio=mock_minio, nats=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        result = await service.complete_upload(100, mock_user)

        assert result == mock_document
        assert mock_document.status == "pending"


class TestUploadServiceAbort:
    """Tests for UploadService.abort_upload."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.delete = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_minio(self):
        """Create a mock MinIO client."""
        minio = MagicMock()
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
        return connector

    @pytest.fixture
    def mock_document(self, mock_connector):
        """Create a mock document in uploading status."""
        document = MagicMock()
        document.id = 100
        document.connector_id = mock_connector.id
        document.connector = mock_connector
        document.url = "1/upload_abc123/test.pdf"
        document.status = "uploading"
        return document

    @pytest.fixture
    def service(self, mock_db, mock_minio):
        """Create UploadService with mocked dependencies."""
        return UploadService(mock_db, minio=mock_minio)

    @pytest.mark.asyncio
    async def test_abort_upload_success(
        self, service, mock_db, mock_minio, mock_user, mock_document
    ):
        """Test successful upload abort."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        result = await service.abort_upload(100, mock_user)

        assert result is True
        mock_minio.delete_file.assert_called_once()
        mock_db.delete.assert_called_once_with(mock_document)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_abort_upload_file_not_in_minio(
        self, service, mock_db, mock_minio, mock_user, mock_document
    ):
        """Test abort succeeds even if file not in MinIO."""
        mock_minio.file_exists = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        result = await service.abort_upload(100, mock_user)

        assert result is True
        mock_minio.delete_file.assert_not_called()
        mock_db.delete.assert_called_once_with(mock_document)

    @pytest.mark.asyncio
    async def test_abort_upload_not_found(
        self, service, mock_db, mock_user
    ):
        """Test aborting non-existent document raises NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.abort_upload(999, mock_user)

    @pytest.mark.asyncio
    async def test_abort_upload_wrong_owner(
        self, service, mock_db, mock_user, mock_document, mock_connector
    ):
        """Test aborting document owned by another user raises NotFoundError."""
        mock_connector.user_id = 999
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.abort_upload(100, mock_user)

    @pytest.mark.asyncio
    async def test_abort_upload_wrong_status(
        self, service, mock_db, mock_user, mock_document
    ):
        """Test aborting document not in uploading status raises ValidationError."""
        mock_document.status = "pending"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValidationError) as exc_info:
            await service.abort_upload(100, mock_user)

        assert "Cannot abort" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_abort_upload_minio_failure_continues(
        self, service, mock_db, mock_minio, mock_user, mock_document
    ):
        """Test abort continues even if MinIO delete fails."""
        mock_minio.file_exists = AsyncMock(return_value=True)
        mock_minio.delete_file = AsyncMock(side_effect=Exception("MinIO error"))
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        # Should not raise - MinIO failures are logged and ignored
        result = await service.abort_upload(100, mock_user)

        assert result is True
        mock_db.delete.assert_called_once_with(mock_document)


class TestUploadServiceIntegration:
    """Integration-style tests for the full upload flow."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.delete = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_minio(self):
        """Create a mock MinIO client."""
        minio = MagicMock()
        minio.presigned_put_url = AsyncMock(return_value="https://minio/upload")
        minio.file_exists = AsyncMock(return_value=True)
        minio.get_file_info = AsyncMock(return_value={"etag": "abc"})
        minio.delete_file = AsyncMock()
        return minio

    @pytest.fixture
    def mock_nats(self):
        """Create a mock NATS publisher."""
        nats = MagicMock()
        nats.publish = AsyncMock()
        return nats

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
        connector.scope_id = None
        return connector

    @pytest.mark.asyncio
    async def test_full_upload_flow(
        self, mock_db, mock_minio, mock_nats, mock_user, mock_connector
    ):
        """Test complete initiate -> complete flow."""
        service = UploadService(mock_db, minio=mock_minio, nats=mock_nats)

        # Step 1: Initiate
        with patch(
            "api.logic.upload_service.connector_crud.get_or_create_upload_connector",
            return_value=mock_connector,
        ):
            created_doc = MagicMock()
            created_doc.id = 100
            created_doc.status = "uploading"
            created_doc.url = "1/upload_abc/test.pdf"
            created_doc.connector = mock_connector
            created_doc.connector_id = mock_connector.id

            async def set_doc_id(doc):
                doc.id = 100

            mock_db.refresh = AsyncMock(side_effect=set_doc_id)

            initiate_result = await service.initiate_upload(
                filename="test.pdf",
                content_type="application/pdf",
                size=1024,
                user=mock_user,
            )

        assert initiate_result.document_id == 100
        assert initiate_result.upload_url == "https://minio/upload"

        # Step 2: Complete
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = created_doc
        mock_db.execute.return_value = mock_result
        mock_db.refresh = AsyncMock()

        complete_result = await service.complete_upload(100, mock_user)

        assert complete_result.status == "pending"
        mock_nats.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_abort_flow(
        self, mock_db, mock_minio, mock_user, mock_connector
    ):
        """Test initiate -> abort flow."""
        service = UploadService(mock_db, minio=mock_minio)

        # Step 1: Initiate
        with patch(
            "api.logic.upload_service.connector_crud.get_or_create_upload_connector",
            return_value=mock_connector,
        ):
            async def set_doc_id(doc):
                doc.id = 100

            mock_db.refresh = AsyncMock(side_effect=set_doc_id)

            initiate_result = await service.initiate_upload(
                filename="test.pdf",
                content_type="application/pdf",
                size=1024,
                user=mock_user,
            )

        # Step 2: Abort
        doc = MagicMock()
        doc.id = 100
        doc.status = "uploading"
        doc.url = "1/upload_abc/test.pdf"
        doc.connector = mock_connector

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute.return_value = mock_result

        abort_result = await service.abort_upload(100, mock_user)

        assert abort_result is True
        mock_db.delete.assert_called()


class TestPresignedUrlRewrite:
    """Tests for _rewrite_presigned_url method."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_minio(self) -> MagicMock:
        """Create a mock MinIO client."""
        return MagicMock()

    def test_rewrites_internal_to_public_endpoint(
        self, mock_db: AsyncMock, mock_minio: MagicMock,
    ) -> None:
        """Test that internal Docker endpoint is replaced with public URL."""
        service = UploadService(mock_db, minio=mock_minio)
        service._settings = MagicMock()
        service._settings.minio_endpoint = "minio:9000"
        service._settings.minio_secure = False
        service._settings.minio_public_endpoint = "https://s3.demo.echomind.ch"

        internal_url = (
            "http://minio:9000/echomind-documents/1/upload_abc/test.pdf"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=abc123"
        )

        result = service._rewrite_presigned_url(internal_url)

        assert result.startswith("https://s3.demo.echomind.ch/echomind-documents/")
        assert "X-Amz-Signature=abc123" in result
        assert "minio:9000" not in result

    def test_no_rewrite_when_public_endpoint_not_set(
        self, mock_db: AsyncMock, mock_minio: MagicMock,
    ) -> None:
        """Test that URL is returned unchanged when no public endpoint configured."""
        service = UploadService(mock_db, minio=mock_minio)
        service._settings = MagicMock()
        service._settings.minio_public_endpoint = None

        internal_url = "http://minio:9000/bucket/path?signature=abc"

        result = service._rewrite_presigned_url(internal_url)

        assert result == internal_url

    def test_adds_https_scheme_if_missing(
        self, mock_db: AsyncMock, mock_minio: MagicMock,
    ) -> None:
        """Test that https:// is added to public endpoint if no scheme specified."""
        service = UploadService(mock_db, minio=mock_minio)
        service._settings = MagicMock()
        service._settings.minio_endpoint = "minio:9000"
        service._settings.minio_secure = False
        service._settings.minio_public_endpoint = "s3.demo.echomind.ch"

        internal_url = "http://minio:9000/bucket/path?signature=abc"

        result = service._rewrite_presigned_url(internal_url)

        assert result.startswith("https://s3.demo.echomind.ch/bucket/path")

    def test_preserves_query_params(
        self, mock_db: AsyncMock, mock_minio: MagicMock,
    ) -> None:
        """Test that query parameters (signature, etc.) are preserved."""
        service = UploadService(mock_db, minio=mock_minio)
        service._settings = MagicMock()
        service._settings.minio_endpoint = "minio:9000"
        service._settings.minio_secure = False
        service._settings.minio_public_endpoint = "https://s3.example.com"

        query = "X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=key&X-Amz-Signature=sig"
        internal_url = f"http://minio:9000/bucket/path?{query}"

        result = service._rewrite_presigned_url(internal_url)

        assert query in result

    def test_handles_secure_internal_endpoint(
        self, mock_db: AsyncMock, mock_minio: MagicMock,
    ) -> None:
        """Test rewrite when internal MinIO uses HTTPS."""
        service = UploadService(mock_db, minio=mock_minio)
        service._settings = MagicMock()
        service._settings.minio_endpoint = "minio:9000"
        service._settings.minio_secure = True
        service._settings.minio_public_endpoint = "https://s3.example.com"

        internal_url = "https://minio:9000/bucket/path?sig=abc"

        result = service._rewrite_presigned_url(internal_url)

        assert result == "https://s3.example.com/bucket/path?sig=abc"
