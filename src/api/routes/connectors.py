"""Connector management endpoints with RBAC enforcement."""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, status
from pydantic import BaseModel

from api.converters import orm_to_connector
from api.dependencies import CurrentUser, DbSession, NatsPublisher
from api.logic.connector_service import ConnectorService
from echomind_lib.models.public import (
    Connector,
    ConnectorScope,
    CreateConnectorRequest,
    ListConnectorsResponse,
    UpdateConnectorRequest,
)

router = APIRouter()


def _scope_to_db_string(scope: "ConnectorScope | None") -> str | None:
    """
    Convert ConnectorScope enum to database string.

    Args:
        scope: The ConnectorScope enum value.

    Returns:
        Canonical scope string (user, team, org) or None.
    """
    if scope is None:
        return None

    mapping = {
        ConnectorScope.CONNECTOR_SCOPE_USER: "user",
        ConnectorScope.CONNECTOR_SCOPE_GROUP: "team",  # GROUP is legacy name for TEAM
        ConnectorScope.CONNECTOR_SCOPE_ORG: "org",
    }
    return mapping.get(scope)  # Returns None for UNSPECIFIED


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
    List connectors accessible to the current user.

    Access rules:
    - User sees own connectors
    - User sees team connectors for teams they belong to
    - User sees org connectors
    - Superadmins see all connectors

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
    service = ConnectorService(db)
    db_connectors = await service.list_connectors(
        user=user,
        page=page,
        limit=limit,
        connector_type=connector_type,
        connector_status=connector_status,
    )

    connectors = [orm_to_connector(c) for c in db_connectors]
    return ListConnectorsResponse(connectors=connectors)


@router.post("", response_model=Connector, status_code=status.HTTP_201_CREATED)
async def create_connector(
    data: CreateConnectorRequest,
    user: CurrentUser,
    db: DbSession,
    nats: NatsPublisher,
) -> Connector:
    """
    Create a new connector and trigger initial sync.

    Access rules:
    - User scope: All allowed users
    - Team scope: Admins who are team members
    - Org scope: Superadmins only

    Args:
        data: The connector creation data.
        user: The authenticated user.
        db: Database session.
        nats: NATS publisher for sync messages.

    Returns:
        Connector: The created connector.

    Raises:
        HTTPException: 403 if user lacks permission for the scope.
    """
    service = ConnectorService(db, nats)

    # Extract team_id from config if present (for team scope)
    team_id = None
    if data.config and "team_id" in data.config:
        team_id = data.config.get("team_id")

    connector = await service.create_connector(
        name=data.name,
        connector_type=data.type.name if data.type else "unspecified",
        user=user,
        config=data.config,
        refresh_freq_minutes=data.refresh_freq_minutes,
        scope=_scope_to_db_string(data.scope),
        scope_id=data.scope_id,
        team_id=team_id,
        trigger_sync=True,
    )

    return orm_to_connector(connector)


@router.get("/{connector_id}", response_model=Connector)
async def get_connector(
    connector_id: int,
    user: CurrentUser,
    db: DbSession,
) -> Connector:
    """
    Get a connector by ID.

    Access rules:
    - User scope: Owner only
    - Team scope: Team members
    - Org scope: All allowed users
    - Superadmins: All connectors

    Args:
        connector_id: The ID of the connector to retrieve.
        user: The authenticated user.
        db: Database session.

    Returns:
        Connector: The requested connector.

    Raises:
        HTTPException: 404 if connector not found.
        HTTPException: 403 if user lacks permission.
    """
    service = ConnectorService(db)
    connector = await service.get_connector(connector_id, user)
    return orm_to_connector(connector)


@router.put("/{connector_id}", response_model=Connector)
async def update_connector(
    connector_id: int,
    data: UpdateConnectorRequest,
    user: CurrentUser,
    db: DbSession,
) -> Connector:
    """
    Update a connector.

    Access rules:
    - User scope: Owner only
    - Team scope: Team leads or admin team members
    - Org scope: Superadmins only

    Args:
        connector_id: The ID of the connector to update.
        data: The fields to update.
        user: The authenticated user.
        db: Database session.

    Returns:
        Connector: The updated connector.

    Raises:
        HTTPException: 404 if connector not found.
        HTTPException: 403 if user lacks permission.
    """
    service = ConnectorService(db)

    # Extract team_id from config if present
    team_id = None
    if data.config and "team_id" in data.config:
        team_id = data.config.get("team_id")

    connector = await service.update_connector(
        connector_id=connector_id,
        user=user,
        name=data.name,
        config=data.config,
        refresh_freq_minutes=data.refresh_freq_minutes,
        scope=_scope_to_db_string(data.scope),
        scope_id=data.scope_id,
        team_id=team_id,
    )
    return orm_to_connector(connector)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: int,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Delete a connector (soft delete).

    Access rules:
    - User scope: Owner only
    - Team scope: Team leads or admin team members
    - Org scope: Superadmins only

    Args:
        connector_id: The ID of the connector to delete.
        user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if connector not found.
        HTTPException: 403 if user lacks permission.
    """
    service = ConnectorService(db)
    await service.delete_connector(connector_id, user)


@router.post("/{connector_id}/sync", response_model=TriggerSyncResponse)
async def trigger_sync(
    connector_id: int,
    user: CurrentUser,
    db: DbSession,
    nats: NatsPublisher,
) -> TriggerSyncResponse:
    """
    Trigger a manual sync for a connector.

    Requires edit access to the connector.

    Args:
        connector_id: The ID of the connector to sync.
        user: The authenticated user.
        db: Database session.
        nats: NATS publisher for sync messages.

    Returns:
        TriggerSyncResponse: Success status and message.

    Raises:
        HTTPException: 404 if connector not found.
        HTTPException: 403 if user lacks permission.
    """
    service = ConnectorService(db, nats)
    success, message = await service.trigger_sync(connector_id, user)
    return TriggerSyncResponse(success=success, message=message)


@router.get("/{connector_id}/status", response_model=ConnectorStatusResponse)
async def get_connector_status(
    connector_id: int,
    user: CurrentUser,
    db: DbSession,
) -> ConnectorStatusResponse:
    """
    Get the sync status of a connector.

    Requires view access to the connector.

    Args:
        connector_id: The ID of the connector.
        user: The authenticated user.
        db: Database session.

    Returns:
        ConnectorStatusResponse: Status information.

    Raises:
        HTTPException: 404 if connector not found.
        HTTPException: 403 if user lacks permission.
    """
    service = ConnectorService(db)
    status_info = await service.get_connector_status(connector_id, user)
    return ConnectorStatusResponse(**status_info)
