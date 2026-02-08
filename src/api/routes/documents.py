"""Document management endpoints with RBAC enforcement."""

from fastapi import APIRouter, status
from pydantic import BaseModel

from api.converters import orm_to_document
from api.dependencies import CurrentUser, DbSession, MinioClient, QdrantClient
from api.logic.document_service import DocumentService
from echomind_lib.models.public import (
    Document,
    ListDocumentsResponse,
)

router = APIRouter()


class DocumentSearchResult(BaseModel):
    """Search result with relevance score."""

    document: Document
    chunk_id: str
    chunk_content: str
    score: float


class DocumentSearchResponse(BaseModel):
    """Response model for document search."""

    results: list[DocumentSearchResult]


@router.get("", response_model=ListDocumentsResponse)
async def list_documents(
    user: CurrentUser,
    db: DbSession,
    qdrant: QdrantClient,
    minio: MinioClient,
    page: int = 1,
    limit: int = 20,
    connector_id: int | None = None,
    doc_status: str | None = None,
) -> ListDocumentsResponse:
    """
    List documents accessible to the current user.

    Access rules:
    - User sees documents from own connectors
    - User sees documents from team connectors for teams they belong to
    - User sees documents from org connectors
    - Superadmins see all documents

    Args:
        user: The authenticated user.
        db: Database session.
        qdrant: Qdrant client for vector operations.
        minio: MinIO client for file operations.
        page: Page number for pagination.
        limit: Number of items per page.
        connector_id: Optional filter by connector.
        doc_status: Optional filter by document status.

    Returns:
        ListDocumentsResponse: Paginated list of documents.
    """
    service = DocumentService(db, qdrant=qdrant, minio=minio)
    db_documents = await service.list_documents(
        user=user,
        page=page,
        limit=limit,
        connector_id=connector_id,
        doc_status=doc_status,
    )

    documents = [orm_to_document(d) for d in db_documents]
    return ListDocumentsResponse(documents=documents)


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents(
    user: CurrentUser,
    db: DbSession,
    qdrant: QdrantClient,
    minio: MinioClient,
    query: str,
    connector_id: int | None = None,
    limit: int = 10,
    min_score: float = 0.5,
) -> DocumentSearchResponse:
    """
    Search documents using vector similarity.

    Searches across all collections accessible to the user:
    - Personal collection (user_{user_id})
    - Team collections (team_{team_id}) for user's teams
    - Organization collection (org_default)

    Args:
        user: The authenticated user.
        db: Database session.
        qdrant: Qdrant client for vector operations.
        minio: MinIO client for file operations.
        query: The search query string.
        connector_id: Optional filter by connector.
        limit: Maximum number of results (max 50).
        min_score: Minimum relevance score threshold.

    Returns:
        DocumentSearchResponse: List of matching documents with scores.
    """
    service = DocumentService(db, qdrant=qdrant, minio=minio)
    results = await service.search_documents(
        user=user,
        query_text=query,
        connector_id=connector_id,
        limit=min(limit, 50),
        min_score=min_score,
    )

    # Transform results to response model
    search_results = [
        DocumentSearchResult(
            document=orm_to_document(r["document"]),
            chunk_id=r["chunk_id"],
            chunk_content=r["chunk_content"],
            score=r["score"],
        )
        for r in results
    ]

    return DocumentSearchResponse(results=search_results)


@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: int,
    user: CurrentUser,
    db: DbSession,
    qdrant: QdrantClient,
    minio: MinioClient,
) -> Document:
    """
    Get a document by ID.

    Access rules:
    - Document inherits permissions from its connector
    - User scope: Owner only
    - Team scope: Team members
    - Org scope: All allowed users
    - Superadmins: All documents

    Args:
        document_id: The ID of the document to retrieve.
        user: The authenticated user.
        db: Database session.
        qdrant: Qdrant client for vector operations.
        minio: MinIO client for file operations.

    Returns:
        Document: The requested document.

    Raises:
        HTTPException: 404 if document not found.
        HTTPException: 403 if user lacks permission.
    """
    service = DocumentService(db, qdrant=qdrant, minio=minio)
    document = await service.get_document(document_id, user)
    return orm_to_document(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    user: CurrentUser,
    db: DbSession,
    qdrant: QdrantClient,
    minio: MinioClient,
) -> None:
    """
    Delete a document and its chunks from the vector store.

    Access rules:
    - Document inherits permissions from its connector
    - User scope: Owner only
    - Team scope: Team leads or admin team members
    - Org scope: Superadmins only

    Args:
        document_id: The ID of the document to delete.
        user: The authenticated user.
        db: Database session.
        qdrant: Qdrant client for vector operations.
        minio: MinIO client for file operations.

    Raises:
        HTTPException: 404 if document not found.
        HTTPException: 403 if user lacks permission.
        HTTPException: 503 if storage services unavailable.
    """
    service = DocumentService(db, qdrant=qdrant, minio=minio)
    await service.delete_document(document_id, user)
