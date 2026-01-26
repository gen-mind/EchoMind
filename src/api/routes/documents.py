"""Document management endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.converters import orm_to_document
from api.dependencies import CurrentUser, DbSession
from echomind_lib.db.models import Connector as ConnectorORM
from echomind_lib.db.models import Document as DocumentORM
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
    page: int = 1,
    limit: int = 20,
    connector_id: int | None = None,
    doc_status: str | None = None,
) -> ListDocumentsResponse:
    """
    List documents for the current user's connectors.

    Args:
        user: The authenticated user.
        db: Database session.
        page: Page number for pagination.
        limit: Number of items per page.
        connector_id: Optional filter by connector.
        doc_status: Optional filter by document status.

    Returns:
        ListDocumentsResponse: Paginated list of documents.
    """
    # Get user's connector IDs
    connector_query = select(ConnectorORM.id).where(
        ConnectorORM.user_id == user.id,
        ConnectorORM.deleted_date.is_(None),
    )
    if connector_id:
        connector_query = connector_query.where(ConnectorORM.id == connector_id)
    
    connector_result = await db.execute(connector_query)
    connector_ids = [c[0] for c in connector_result.all()]
    
    if not connector_ids:
        return ListDocumentsResponse(documents=[])
    
    # Query documents
    query = select(DocumentORM).where(DocumentORM.connector_id.in_(connector_ids))
    
    if doc_status:
        query = query.where(DocumentORM.status == doc_status)
    
    query = query.order_by(DocumentORM.creation_date.desc())
    
    # Count total
    count_query = select(DocumentORM.id).where(DocumentORM.connector_id.in_(connector_ids))
    if doc_status:
        count_query = count_query.where(DocumentORM.status == doc_status)
    # Paginate
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    db_documents = result.scalars().all()
    
    documents = [orm_to_document(d) for d in db_documents]
    
    return ListDocumentsResponse(documents=documents)


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents(
    user: CurrentUser,
    db: DbSession,
    query: str,
    connector_id: int | None = None,
    limit: int = 10,
    min_score: float = 0.5,
) -> DocumentSearchResponse:
    """
    Search documents using vector similarity.

    Args:
        user: The authenticated user.
        db: Database session.
        query: The search query string.
        connector_id: Optional filter by connector.
        limit: Maximum number of results (max 50).
        min_score: Minimum relevance score threshold.

    Returns:
        DocumentSearchResponse: List of matching documents with scores.
    """
    # Get user's connector IDs
    connector_query = select(ConnectorORM.id, ConnectorORM.scope, ConnectorORM.scope_id).where(
        ConnectorORM.user_id == user.id,
        ConnectorORM.deleted_date.is_(None),
    )
    if connector_id:
        connector_query = connector_query.where(ConnectorORM.id == connector_id)
    
    connector_result = await db.execute(connector_query)
    connectors = connector_result.all()
    
    if not connectors:
        return DocumentSearchResponse(results=[])
    
    # Stub: Vector search requires Embedder + Qdrant integration (Phase 2)
    # Production implementation:
    # 1. Embed the query using the active embedding model
    # 2. Search Qdrant collections based on connector scopes
    # 3. Return ranked results
    
    return DocumentSearchResponse(results=[])


@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: int,
    user: CurrentUser,
    db: DbSession,
) -> Document:
    """
    Get a document by ID.

    Args:
        document_id: The ID of the document to retrieve.
        user: The authenticated user.
        db: Database session.

    Returns:
        Document: The requested document.

    Raises:
        HTTPException: 404 if document not found or user doesn't own it.
    """
    # Verify user owns the connector
    result = await db.execute(
        select(DocumentORM)
        .join(ConnectorORM, DocumentORM.connector_id == ConnectorORM.id)
        .where(DocumentORM.id == document_id)
        .where(ConnectorORM.user_id == user.id)
        .where(ConnectorORM.deleted_date.is_(None))
    )
    db_document = result.scalar_one_or_none()
    
    if not db_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return orm_to_document(db_document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Delete a document and its chunks from the vector store.

    Args:
        document_id: The ID of the document to delete.
        user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if document not found or user doesn't own it.
    """
    # Verify user owns the connector
    result = await db.execute(
        select(DocumentORM)
        .join(ConnectorORM, DocumentORM.connector_id == ConnectorORM.id)
        .where(DocumentORM.id == document_id)
        .where(ConnectorORM.user_id == user.id)
        .where(ConnectorORM.deleted_date.is_(None))
    )
    db_document = result.scalar_one_or_none()
    
    if not db_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Stub: Qdrant chunk deletion requires vector DB integration (Phase 2)
    # Stub: MinIO file deletion requires storage integration (Phase 2)
    
    # Delete from database
    await db.delete(db_document)
