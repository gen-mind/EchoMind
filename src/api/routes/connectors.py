"""Connector management endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.converters import orm_to_connector
from api.dependencies import CurrentUser, DbSession
from echomind_lib.db.models import Connector as ConnectorORM
from echomind_lib.db.models import Document as DocumentORM
from echomind_lib.models.public import (
    Connector,
    CreateConnectorRequest,
    ListConnectorsResponse,
    UpdateConnectorRequest,
)

router = APIRouter()


class TriggerSyncResponse(BaseModel):
    """Response model for triggering a sync."""
    success: bool
    message: str


class ConnectorStatusResponse(BaseModel):
    """Response model for connector status."""
    status: str
    status_message: str | None
    last_sync_at: datetime | None
    docs_analyzed: int
    docs_pending: int


@router.get("", response_model=ListConnectorsResponse)
async def list_connectors(
    user: CurrentUser,
    db: DbSession,
    page: int = 1,
    limit: int = 20,
    connector_type: str | None = None,
    connector_status: str | None = None,
) -> ListConnectorsResponse:
    """
    List all connectors for the current user.

    Args:
        user: The authenticated user.
        db: Database session.
        page: Page number for pagination.
        limit: Number of items per page.
        connector_type: Optional filter by connector type.
        connector_status: Optional filter by status.

    Returns:
        ListConnectorsResponse: Paginated list of connectors.
    """
    query = select(ConnectorORM).where(
        ConnectorORM.user_id == user.id,
        ConnectorORM.deleted_date.is_(None),
    )
    
    if connector_type:
        query = query.where(ConnectorORM.type == connector_type)
    if connector_status:
        query = query.where(ConnectorORM.status == connector_status)
    
    query = query.order_by(ConnectorORM.name)
    
    # Count total
    count_query = select(ConnectorORM.id).where(
        ConnectorORM.user_id == user.id,
        ConnectorORM.deleted_date.is_(None),
    )
    if connector_type:
        count_query = count_query.where(ConnectorORM.type == connector_type)
    if connector_status:
        count_query = count_query.where(ConnectorORM.status == connector_status)
    # Paginate
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    db_connectors = result.scalars().all()
    
    connectors = [orm_to_connector(c) for c in db_connectors]
    
    return ListConnectorsResponse(connectors=connectors)


@router.post("", response_model=Connector, status_code=status.HTTP_201_CREATED)
async def create_connector(
    data: CreateConnectorRequest,
    user: CurrentUser,
    db: DbSession,
) -> Connector:
    """
    Create a new connector.

    Args:
        data: The connector creation data.
        user: The authenticated user.
        db: Database session.

    Returns:
        Connector: The created connector.
    """
    connector = ConnectorORM(
        name=data.name,
        type=data.type.name if data.type else None,
        config=data.config or {},
        state={},
        refresh_freq_minutes=data.refresh_freq_minutes,
        user_id=user.id,
        scope=data.scope.name if data.scope else None,
        scope_id=data.scope_id or "",
        status="pending",
        user_id_last_update=user.id,
    )
    
    db.add(connector)
    await db.flush()
    await db.refresh(connector)
    
    return orm_to_connector(connector)


@router.get("/{connector_id}", response_model=Connector)
async def get_connector(
    connector_id: int,
    user: CurrentUser,
    db: DbSession,
) -> Connector:
    """
    Get a connector by ID.

    Args:
        connector_id: The ID of the connector to retrieve.
        user: The authenticated user.
        db: Database session.

    Returns:
        Connector: The requested connector.

    Raises:
        HTTPException: 404 if connector not found.
    """
    result = await db.execute(
        select(ConnectorORM)
        .where(ConnectorORM.id == connector_id)
        .where(ConnectorORM.user_id == user.id)
        .where(ConnectorORM.deleted_date.is_(None))
    )
    db_connector = result.scalar_one_or_none()
    
    if not db_connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    
    return orm_to_connector(db_connector)


@router.put("/{connector_id}", response_model=Connector)
async def update_connector(
    connector_id: int,
    data: UpdateConnectorRequest,
    user: CurrentUser,
    db: DbSession,
) -> Connector:
    """
    Update a connector.

    Args:
        connector_id: The ID of the connector to update.
        data: The fields to update.
        user: The authenticated user.
        db: Database session.

    Returns:
        Connector: The updated connector.

    Raises:
        HTTPException: 404 if connector not found.
    """
    result = await db.execute(
        select(ConnectorORM)
        .where(ConnectorORM.id == connector_id)
        .where(ConnectorORM.user_id == user.id)
        .where(ConnectorORM.deleted_date.is_(None))
    )
    db_connector = result.scalar_one_or_none()
    
    if not db_connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    
    if data.name:
        db_connector.name = data.name
    if data.config:
        db_connector.config = data.config
    if data.refresh_freq_minutes:
        db_connector.refresh_freq_minutes = data.refresh_freq_minutes
    if data.scope:
        db_connector.scope = data.scope.name if hasattr(data.scope, 'name') else str(data.scope)
    if data.scope_id:
        db_connector.scope_id = data.scope_id
    
    db_connector.user_id_last_update = user.id
    
    return orm_to_connector(db_connector)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: int,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Delete a connector (soft delete).

    Args:
        connector_id: The ID of the connector to delete.
        user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if connector not found.
    """
    result = await db.execute(
        select(ConnectorORM)
        .where(ConnectorORM.id == connector_id)
        .where(ConnectorORM.user_id == user.id)
        .where(ConnectorORM.deleted_date.is_(None))
    )
    db_connector = result.scalar_one_or_none()
    
    if not db_connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    
    db_connector.deleted_date = datetime.now(timezone.utc)
    db_connector.user_id_last_update = user.id


@router.post("/{connector_id}/sync", response_model=TriggerSyncResponse)
async def trigger_sync(
    connector_id: int,
    user: CurrentUser,
    db: DbSession,
) -> TriggerSyncResponse:
    """
    Trigger a manual sync for a connector.

    Args:
        connector_id: The ID of the connector to sync.
        user: The authenticated user.
        db: Database session.

    Returns:
        TriggerSyncResponse: Success status and message.

    Raises:
        HTTPException: 404 if connector not found.
    """
    result = await db.execute(
        select(ConnectorORM)
        .where(ConnectorORM.id == connector_id)
        .where(ConnectorORM.user_id == user.id)
        .where(ConnectorORM.deleted_date.is_(None))
    )
    db_connector = result.scalar_one_or_none()
    
    if not db_connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    
    if db_connector.status == "syncing":
        return TriggerSyncResponse(
            success=False,
            message="Sync already in progress",
        )
    
    # Update status to pending
    db_connector.status = "pending"
    db_connector.user_id_last_update = user.id
    
    # Stub: NATS publish requires Orchestrator service (Phase 2)
    
    return TriggerSyncResponse(
        success=True,
        message="Sync triggered",
    )


@router.get("/{connector_id}/status", response_model=ConnectorStatusResponse)
async def get_connector_status(
    connector_id: int,
    user: CurrentUser,
    db: DbSession,
) -> ConnectorStatusResponse:
    """
    Get the sync status of a connector.

    Args:
        connector_id: The ID of the connector.
        user: The authenticated user.
        db: Database session.

    Returns:
        ConnectorStatusResponse: Status information.

    Raises:
        HTTPException: 404 if connector not found.
    """
    result = await db.execute(
        select(ConnectorORM)
        .where(ConnectorORM.id == connector_id)
        .where(ConnectorORM.user_id == user.id)
        .where(ConnectorORM.deleted_date.is_(None))
    )
    db_connector = result.scalar_one_or_none()
    
    if not db_connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    
    # Count pending documents
    pending_result = await db.execute(
        select(DocumentORM.id)
        .where(DocumentORM.connector_id == connector_id)
        .where(DocumentORM.status == "pending")
    )
    docs_pending = len(pending_result.all())
    
    return ConnectorStatusResponse(
        status=db_connector.status,
        status_message=db_connector.status_message,
        last_sync_at=db_connector.last_sync_at,
        docs_analyzed=db_connector.docs_analyzed,
        docs_pending=docs_pending,
    )
