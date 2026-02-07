"""
File upload endpoints using pre-signed URLs.

Provides a three-step upload flow:
1. POST /upload/initiate - Get pre-signed URL for direct upload to MinIO
2. POST /upload/complete - Finalize upload after file is in MinIO
3. POST /upload/abort - Cancel upload and clean up
"""

from pydantic import BaseModel, Field

from fastapi import APIRouter

from api.converters import orm_to_document
from api.dependencies import CurrentUser, DbSession, MinioClient, NatsPublisher
from api.logic.upload_service import UploadService
from echomind_lib.models.public import Document

router = APIRouter()


class InitiateUploadRequest(BaseModel):
    """Request to initiate a file upload."""

    filename: str = Field(
        ...,
        description="Name of the file to upload",
        min_length=1,
        max_length=255,
    )
    content_type: str = Field(
        ...,
        description="MIME type of the file",
        min_length=1,
        max_length=100,
    )
    size: int = Field(
        ...,
        description="File size in bytes",
        gt=0,
    )


class InitiateUploadResponse(BaseModel):
    """Response from initiating an upload."""

    document_id: int = Field(..., description="ID of the created document record")
    upload_url: str = Field(..., description="Pre-signed PUT URL for uploading")
    expires_in: int = Field(..., description="URL validity in seconds")
    storage_path: str = Field(..., description="MinIO object path")


class CompleteUploadRequest(BaseModel):
    """Request to complete a file upload."""

    document_id: int = Field(..., description="ID of the document to complete")


class AbortUploadRequest(BaseModel):
    """Request to abort a file upload."""

    document_id: int = Field(..., description="ID of the document to abort")


class AbortUploadResponse(BaseModel):
    """Response from aborting an upload."""

    success: bool = Field(..., description="Whether the abort was successful")


@router.post("/initiate", response_model=InitiateUploadResponse)
async def initiate_upload(
    request: InitiateUploadRequest,
    user: CurrentUser,
    db: DbSession,
    minio: MinioClient,
) -> InitiateUploadResponse:
    """
    Initiate a file upload.

    Creates a document record and returns a pre-signed URL for direct upload
    to MinIO. The URL is valid for 1 hour.

    After initiating, the client should:
    1. PUT the file directly to the upload_url
    2. Call POST /upload/complete to finalize

    Args:
        request: Upload initiation parameters.
        user: The authenticated user.
        db: Database session.
        minio: MinIO client for file storage.

    Returns:
        InitiateUploadResponse with document ID and upload URL.

    Raises:
        HTTPException 422: If file type or size is invalid.
        HTTPException 503: If MinIO is unavailable.
    """
    service = UploadService(db, minio=minio)
    result = await service.initiate_upload(
        filename=request.filename,
        content_type=request.content_type,
        size=request.size,
        user=user,
    )

    return InitiateUploadResponse(
        document_id=result.document_id,
        upload_url=result.upload_url,
        expires_in=result.expires_in,
        storage_path=result.storage_path,
    )


@router.post("/complete", response_model=Document)
async def complete_upload(
    request: CompleteUploadRequest,
    user: CurrentUser,
    db: DbSession,
    minio: MinioClient,
    nats: NatsPublisher,
) -> Document:
    """
    Complete a file upload.

    Verifies the file exists in MinIO, updates the document status to "pending",
    and publishes a document.process event for processing.

    Args:
        request: Upload completion parameters.
        user: The authenticated user.
        db: Database session.
        minio: MinIO client for file storage.
        nats: NATS publisher for document processing events.

    Returns:
        Document: The completed document.

    Raises:
        HTTPException 404: If document not found or not owned by user.
        HTTPException 422: If document not in "uploading" status or file not in MinIO.
        HTTPException 503: If MinIO is unavailable.
    """
    service = UploadService(db, minio=minio, nats=nats)
    document = await service.complete_upload(
        document_id=request.document_id,
        user=user,
    )

    return orm_to_document(document)


@router.post("/abort", response_model=AbortUploadResponse)
async def abort_upload(
    request: AbortUploadRequest,
    user: CurrentUser,
    db: DbSession,
    minio: MinioClient,
) -> AbortUploadResponse:
    """
    Abort a file upload.

    Deletes the MinIO object (if uploaded) and the document record.
    Only documents in "uploading" status can be aborted.

    Args:
        request: Upload abort parameters.
        user: The authenticated user.
        db: Database session.
        minio: MinIO client for file storage.

    Returns:
        AbortUploadResponse indicating success.

    Raises:
        HTTPException 404: If document not found or not owned by user.
        HTTPException 422: If document not in "uploading" status.
        HTTPException 503: If MinIO is unavailable.
    """
    service = UploadService(db, minio=minio)
    success = await service.abort_upload(
        document_id=request.document_id,
        user=user,
    )

    return AbortUploadResponse(success=success)
