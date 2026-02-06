"""
Upload service for handling file uploads via pre-signed URLs.

This service manages the three-step upload process:
1. initiate_upload - Create document record, generate pre-signed PUT URL
2. complete_upload - Verify file exists in MinIO, publish processing event
3. abort_upload - Clean up if upload is cancelled
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.config import get_settings
from api.logic.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from echomind_lib.db.crud import connector_crud
from echomind_lib.db.minio import MinIOClient, get_minio
from echomind_lib.db.models import Connector as ConnectorORM
from echomind_lib.db.models import Document as DocumentORM
from echomind_lib.db.nats_publisher import JetStreamPublisher

if TYPE_CHECKING:
    from echomind_lib.helpers.auth import TokenUser

logger = logging.getLogger(__name__)

# Allowed file types for upload
# NOTE: Audio/video types intentionally excluded - see UNSUPPORTED_MEDIA_TYPES below
ALLOWED_CONTENT_TYPES: set[str] = {
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Text
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    # Images (processed via OCR/captioning)
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

# Unsupported media types - explicitly rejected with clear error message
# These require Voice/Vision services that are not yet implemented:
# - Audio requires Riva NIM for speech-to-text (not deployed)
# - Video requires frame extraction + BLIP captioning (not implemented)
# Accepting these would result in documents with zero searchable content.
UNSUPPORTED_MEDIA_TYPES: set[str] = {
    # Audio - requires Voice service (Riva NIM)
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/ogg",
    "audio/webm",
    "audio/x-wav",
    "audio/wave",
    # Video - requires Vision service (not implemented)
    "video/mp4",
    "video/webm",
    "video/ogg",
    "video/x-msvideo",
    "video/x-matroska",
    "video/quicktime",
}

# Maximum file size (5GB)
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024


class InitiateUploadResult:
    """Result of initiating an upload."""

    def __init__(
        self,
        document_id: int,
        upload_url: str,
        expires_in: int,
        storage_path: str,
    ):
        """
        Initialize result.

        Args:
            document_id: ID of the created document record.
            upload_url: Pre-signed PUT URL for uploading.
            expires_in: URL validity in seconds.
            storage_path: MinIO object path.
        """
        self.document_id = document_id
        self.upload_url = upload_url
        self.expires_in = expires_in
        self.storage_path = storage_path


class UploadService:
    """
    Service for handling document uploads via pre-signed URLs.

    The upload flow is:
    1. Client calls initiate_upload with filename, content_type, size
    2. Service creates document record (status: "uploading")
    3. Service generates pre-signed PUT URL for MinIO
    4. Client uploads file directly to MinIO using the URL
    5. Client calls complete_upload to finalize
    6. Service verifies file exists, updates status, publishes NATS event
    """

    def __init__(
        self,
        db: AsyncSession,
        minio: MinIOClient | None = None,
        nats: JetStreamPublisher | None = None,
    ):
        """
        Initialize upload service.

        Args:
            db: Database session.
            minio: MinIO client (uses global if not provided).
            nats: NATS publisher (optional, for document processing).
        """
        self.db = db
        self._minio = minio
        self._nats = nats
        self._settings = get_settings()

    @property
    def minio(self) -> MinIOClient:
        """Get MinIO client."""
        if self._minio:
            return self._minio
        return get_minio()

    async def initiate_upload(
        self,
        filename: str,
        content_type: str,
        size: int,
        user: "TokenUser",
    ) -> InitiateUploadResult:
        """
        Initiate a file upload.

        Creates a document record and generates a pre-signed URL for direct upload.

        Args:
            filename: Name of the file to upload.
            content_type: MIME type of the file.
            size: File size in bytes.
            user: The authenticated user.

        Returns:
            InitiateUploadResult with document ID and upload URL.

        Raises:
            ValidationError: If file type or size is invalid.
            ServiceUnavailableError: If MinIO is unavailable.
        """
        # Validate content type
        normalized_type = content_type.lower()
        if normalized_type in UNSUPPORTED_MEDIA_TYPES:
            raise ValidationError(
                f"Audio and video files are not yet supported. "
                f"Please upload documents (PDF, Word, Excel, PowerPoint), "
                f"text files, or images instead."
            )
        if normalized_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(
                f"File type '{content_type}' is not allowed. "
                f"Supported types: documents, images, and text files."
            )

        # Validate file size
        if size > MAX_FILE_SIZE:
            raise ValidationError(
                f"File size {size} bytes exceeds maximum allowed "
                f"size of {MAX_FILE_SIZE} bytes (5GB)."
            )

        if size <= 0:
            raise ValidationError("File size must be greater than 0.")

        # Get or create user's system FILE connector
        connector = await connector_crud.get_or_create_upload_connector(
            self.db, user.id
        )

        # Generate unique source ID and object path
        source_id = f"upload_{uuid.uuid4().hex}"
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        object_name = f"{connector.id}/{source_id}/{safe_filename}"

        # Create document record with "uploading" status
        document = DocumentORM(
            connector_id=connector.id,
            source_id=source_id,
            url=object_name,  # MinIO path
            title=filename,
            content_type=content_type,
            status="uploading",
            creation_date=datetime.now(timezone.utc),
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        logger.info(f"📤 Initiated upload for user {user.id}: {filename} ({size} bytes)")

        # Generate pre-signed URL
        try:
            expires_in = 3600  # 1 hour
            upload_url = await self.minio.presigned_put_url(
                bucket_name=self._settings.minio_bucket,
                object_name=object_name,
                expires=expires_in,
            )
        except Exception as e:
            # Rollback document creation
            await self.db.delete(document)
            await self.db.commit()
            logger.error(f"❌ Failed to generate pre-signed URL: {e}")
            raise ServiceUnavailableError("MinIO") from e

        return InitiateUploadResult(
            document_id=document.id,
            upload_url=upload_url,
            expires_in=expires_in,
            storage_path=object_name,
        )

    async def complete_upload(
        self,
        document_id: int,
        user: "TokenUser",
    ) -> DocumentORM:
        """
        Complete a file upload.

        Verifies the file exists in MinIO and publishes a processing event.

        Args:
            document_id: ID of the document to complete.
            user: The authenticated user.

        Returns:
            The updated document.

        Raises:
            NotFoundError: If document not found.
            ValidationError: If document is not in "uploading" status
                or file not found in MinIO.
        """
        # Get document with connector
        result = await self.db.execute(
            select(DocumentORM)
            .options(selectinload(DocumentORM.connector))
            .where(DocumentORM.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError("Document", document_id)

        # Verify ownership (document's connector must belong to user)
        if document.connector.user_id != user.id:
            raise NotFoundError("Document", document_id)

        # Verify status
        if document.status != "uploading":
            raise ValidationError(
                f"Document is in '{document.status}' status, expected 'uploading'."
            )

        # Verify file exists in MinIO
        object_name = document.url
        try:
            file_exists = await self.minio.file_exists(
                self._settings.minio_bucket, object_name
            )
        except Exception as e:
            logger.error(f"❌ Failed to check file in MinIO: {e}")
            raise ServiceUnavailableError("MinIO") from e

        if not file_exists:
            raise ValidationError(
                "File not found in storage. Please upload the file first."
            )

        # Get file info for signature
        try:
            file_info = await self.minio.get_file_info(
                self._settings.minio_bucket, object_name
            )
            document.signature = file_info.get("etag", "")
        except Exception as e:
            logger.warning(f"⚠️ Could not get file info: {e}")

        # Update document status
        document.status = "pending"
        document.last_update = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(document)

        logger.info(f"✅ Completed upload for document {document.id}: {document.title}")

        # Publish document.process event
        await self._publish_document_process(document, document.connector)

        return document

    async def abort_upload(
        self,
        document_id: int,
        user: "TokenUser",
    ) -> bool:
        """
        Abort an upload and clean up resources.

        Deletes the MinIO object (if exists) and the document record.

        Args:
            document_id: ID of the document to abort.
            user: The authenticated user.

        Returns:
            True if abort was successful.

        Raises:
            NotFoundError: If document not found.
            ValidationError: If document is not in "uploading" status.
        """
        # Get document with connector
        result = await self.db.execute(
            select(DocumentORM)
            .options(selectinload(DocumentORM.connector))
            .where(DocumentORM.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError("Document", document_id)

        # Verify ownership
        if document.connector.user_id != user.id:
            raise NotFoundError("Document", document_id)

        # Only allow aborting uploads in "uploading" status
        if document.status != "uploading":
            raise ValidationError(
                f"Cannot abort document in '{document.status}' status."
            )

        # Try to delete from MinIO (ignore errors, file may not exist yet)
        object_name = document.url
        try:
            if await self.minio.file_exists(
                self._settings.minio_bucket, object_name
            ):
                await self.minio.delete_file(
                    self._settings.minio_bucket, object_name
                )
                logger.info(f"🗑️ Deleted MinIO object: {object_name}")
        except Exception as e:
            logger.warning(f"⚠️ Could not delete MinIO object: {e}")

        # Delete document record
        await self.db.delete(document)
        await self.db.commit()

        logger.info(f"🚫 Aborted upload for document {document_id} by user {user.id}")

        return True

    async def _publish_document_process(
        self,
        document: DocumentORM,
        connector: ConnectorORM,
    ) -> None:
        """
        Publish document.process event to NATS.

        Args:
            document: Document to process.
            connector: The document's connector.
        """
        if not self._nats:
            logger.warning(
                "⚠️ NATS not available, skipping document.process publish"
            )
            return

        # Import protobuf message
        from echomind_lib.models.internal.orchestrator_pb2 import (  # type: ignore[import-untyped]
            DocumentProcessRequest,
        )
        from echomind_lib.models.public.connector_pb2 import (  # type: ignore[import-untyped]
            ConnectorScope,
        )

        # Map scope to enum
        scope_map = {
            "user": ConnectorScope.CONNECTOR_SCOPE_USER,
            "team": ConnectorScope.CONNECTOR_SCOPE_GROUP,  # team uses GROUP enum
            "group": ConnectorScope.CONNECTOR_SCOPE_GROUP,
            "org": ConnectorScope.CONNECTOR_SCOPE_ORG,
        }
        scope_enum = scope_map.get(
            connector.scope or "user",
            ConnectorScope.CONNECTOR_SCOPE_USER,
        )

        message = DocumentProcessRequest(
            document_id=document.id,
            connector_id=document.connector_id,
            user_id=connector.user_id,
            minio_path=document.url,  # Just the object path, bucket is in ingestor settings
            chunking_session="",  # No session for uploads
            scope=scope_enum,
            scope_id=connector.scope_id or "",
        )

        # Set team_id for team-scoped connectors
        if connector.team_id is not None:
            message.team_id = connector.team_id

        try:
            await self._nats.publish(
                subject="document.process",
                payload=message.SerializeToString(),
            )
            logger.info(f"📤 Published document.process for document {document.id}")
        except Exception as e:
            logger.error(f"❌ Failed to publish document.process for document {document.id}: {e}")
