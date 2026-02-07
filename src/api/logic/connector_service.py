"""
Connector business logic service.

Handles connector CRUD operations, RBAC enforcement, and NATS sync message publishing.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from google.protobuf import struct_pb2
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.logic.exceptions import ForbiddenError, NotFoundError
from api.logic.permissions import (
    SCOPE_GROUP,
    SCOPE_ORG,
    SCOPE_TEAM,
    SCOPE_USER,
    PermissionChecker,
)
from echomind_lib.db.crud import team_crud
from echomind_lib.db.models import Connector as ConnectorORM
from echomind_lib.db.models import Document as DocumentORM
from echomind_lib.db.nats_publisher import JetStreamPublisher
from echomind_lib.models.internal.orchestrator_pb2 import ConnectorSyncRequest
from echomind_lib.models.public import connector_pb2

if TYPE_CHECKING:
    from echomind_lib.helpers.auth import TokenUser

logger = logging.getLogger(__name__)


class ConnectorService:
    """Service for connector-related business logic with RBAC enforcement."""

    def __init__(
        self,
        db: AsyncSession,
        nats_publisher: JetStreamPublisher | None = None,
    ):
        """
        Initialize connector service.

        Args:
            db: Database session.
            nats_publisher: Optional NATS publisher for sync messages.
        """
        self.db = db
        self.nats = nats_publisher
        self.permissions = PermissionChecker(db)

    async def get_connector(
        self,
        connector_id: int,
        user: "TokenUser",
    ) -> ConnectorORM:
        """
        Get a connector by ID with permission check.

        Args:
            connector_id: The connector ID.
            user: The authenticated user.

        Returns:
            ConnectorORM: The connector.

        Raises:
            NotFoundError: If connector not found.
            ForbiddenError: If user lacks permission.
        """
        result = await self.db.execute(
            select(ConnectorORM)
            .where(ConnectorORM.id == connector_id)
            .where(ConnectorORM.deleted_date.is_(None))
        )
        connector = result.scalar_one_or_none()

        if not connector:
            raise NotFoundError("Connector", connector_id)

        # Check permission
        access = await self.permissions.can_view_connector(user, connector)
        if not access:
            logger.warning(
                "🚫 User %d denied access to connector %d: %s",
                user.id,
                connector_id,
                access.reason,
            )
            raise ForbiddenError(f"Cannot access connector: {access.reason}")

        return connector

    async def list_connectors(
        self,
        user: "TokenUser",
        page: int = 1,
        limit: int = 20,
        connector_type: str | None = None,
        connector_status: str | None = None,
    ) -> list[ConnectorORM]:
        """
        List connectors accessible to the user.

        Args:
            user: The authenticated user.
            page: Page number (1-indexed).
            limit: Items per page.
            connector_type: Optional filter by type.
            connector_status: Optional filter by status.

        Returns:
            List of accessible connectors.
        """
        # Get user's team IDs for filtering
        team_ids = await self.permissions.get_user_team_ids(user.id)

        # Build base query with RBAC filters
        if self.permissions.is_admin(user):
            # Admins see all
            query = select(ConnectorORM).where(ConnectorORM.deleted_date.is_(None))
        else:
            # Regular users see: own + team + org connectors
            query = (
                select(ConnectorORM)
                .where(ConnectorORM.deleted_date.is_(None))
                .where(
                    or_(
                        ConnectorORM.user_id == user.id,
                        (
                            (ConnectorORM.scope.in_([SCOPE_TEAM, SCOPE_GROUP]))
                            & (ConnectorORM.team_id.in_(team_ids))
                        ),
                        ConnectorORM.scope == SCOPE_ORG,
                    )
                )
            )

        # Apply additional filters
        if connector_type:
            query = query.where(ConnectorORM.type == connector_type)
        if connector_status:
            query = query.where(ConnectorORM.status == connector_status)

        # Order and paginate
        query = query.order_by(ConnectorORM.name)
        query = query.offset((page - 1) * limit).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_connector(
        self,
        name: str,
        connector_type: str,
        user: "TokenUser",
        config: dict | None = None,
        refresh_freq_minutes: int | None = None,
        scope: str | None = None,
        scope_id: str | None = None,
        team_id: int | None = None,
        trigger_sync: bool = True,
    ) -> ConnectorORM:
        """
        Create a new connector with RBAC check.

        Args:
            name: Connector name.
            connector_type: Type (google_drive, onedrive, etc.).
            user: The authenticated user.
            config: Connector configuration.
            refresh_freq_minutes: Sync frequency.
            scope: Connector scope (user, team, org).
            scope_id: Scope ID (deprecated, use team_id).
            team_id: Team ID for team scope.
            trigger_sync: Whether to publish NATS sync message.

        Returns:
            ConnectorORM: The created connector.

        Raises:
            ForbiddenError: If user lacks permission for the scope.
        """
        # Default to user scope
        actual_scope = scope or SCOPE_USER

        # Check permission to create with this scope
        access = await self.permissions.can_create_connector(
            user, actual_scope, team_id
        )
        if not access:
            logger.warning(
                "🚫 User %d denied creating %s connector: %s",
                user.id,
                actual_scope,
                access.reason,
            )
            raise ForbiddenError(f"Cannot create connector: {access.reason}")

        connector = ConnectorORM(
            name=name,
            type=connector_type,
            config=config or {},
            state={},
            refresh_freq_minutes=refresh_freq_minutes,
            user_id=user.id,
            scope=actual_scope,
            scope_id=scope_id or "",
            team_id=team_id,
            status="pending",
            user_id_last_update=user.id,
        )

        self.db.add(connector)
        await self.db.flush()
        await self.db.refresh(connector)

        logger.info(
            "📝 Created connector %d (%s, scope=%s) for user %d",
            connector.id,
            connector.type,
            actual_scope,
            user.id,
        )

        # Trigger initial sync if requested
        if trigger_sync and self.nats:
            await self._publish_sync_message(connector)

        return connector

    async def update_connector(
        self,
        connector_id: int,
        user: "TokenUser",
        name: str | None = None,
        config: dict | None = None,
        refresh_freq_minutes: int | None = None,
        scope: str | None = None,
        scope_id: str | None = None,
        team_id: int | None = None,
    ) -> ConnectorORM:
        """
        Update a connector with RBAC check.

        Args:
            connector_id: The connector ID.
            user: The authenticated user.
            name: New name.
            config: New configuration.
            refresh_freq_minutes: New sync frequency.
            scope: New scope.
            scope_id: New scope ID.
            team_id: New team ID.

        Returns:
            ConnectorORM: The updated connector.

        Raises:
            NotFoundError: If connector not found.
            ForbiddenError: If user lacks permission.
        """
        # Get connector (without permission check yet)
        result = await self.db.execute(
            select(ConnectorORM)
            .where(ConnectorORM.id == connector_id)
            .where(ConnectorORM.deleted_date.is_(None))
        )
        connector = result.scalar_one_or_none()

        if not connector:
            raise NotFoundError("Connector", connector_id)

        # Check edit permission
        access = await self.permissions.can_edit_connector(user, connector)
        if not access:
            logger.warning(
                "🚫 User %d denied editing connector %d: %s",
                user.id,
                connector_id,
                access.reason,
            )
            raise ForbiddenError(f"Cannot edit connector: {access.reason}")

        # If changing scope, check permission for new scope
        if scope and scope != connector.scope:
            new_team_id = team_id if team_id else connector.team_id
            new_access = await self.permissions.can_create_connector(
                user, scope, new_team_id
            )
            if not new_access:
                raise ForbiddenError(f"Cannot change scope: {new_access.reason}")

        # Apply updates
        if name:
            connector.name = name
        if config:
            connector.config = config
        if refresh_freq_minutes is not None:
            connector.refresh_freq_minutes = refresh_freq_minutes
        if scope:
            connector.scope = scope
        if scope_id is not None:
            connector.scope_id = scope_id
        if team_id is not None:
            connector.team_id = team_id

        connector.last_update = datetime.now(timezone.utc)
        connector.user_id_last_update = user.id

        logger.info(f"🔄 Updated connector {connector_id} by user {user.id}")

        return connector

    async def delete_connector(
        self,
        connector_id: int,
        user: "TokenUser",
    ) -> None:
        """
        Soft delete a connector with RBAC check.

        Args:
            connector_id: The connector ID.
            user: The authenticated user.

        Raises:
            NotFoundError: If connector not found.
            ForbiddenError: If user lacks permission.
        """
        # Get connector
        result = await self.db.execute(
            select(ConnectorORM)
            .where(ConnectorORM.id == connector_id)
            .where(ConnectorORM.deleted_date.is_(None))
        )
        connector = result.scalar_one_or_none()

        if not connector:
            raise NotFoundError("Connector", connector_id)

        # Check delete permission
        access = await self.permissions.can_delete_connector(user, connector)
        if not access:
            logger.warning(
                "🚫 User %d denied deleting connector %d: %s",
                user.id,
                connector_id,
                access.reason,
            )
            raise ForbiddenError(f"Cannot delete connector: {access.reason}")

        connector.deleted_date = datetime.now(timezone.utc)
        connector.user_id_last_update = user.id

        logger.info(f"🗑️ Deleted connector {connector_id} by user {user.id}")

    async def trigger_sync(
        self,
        connector_id: int,
        user: "TokenUser",
    ) -> tuple[bool, str]:
        """
        Trigger a manual sync for a connector with RBAC check.

        Args:
            connector_id: The connector ID.
            user: The authenticated user.

        Returns:
            Tuple of (success, message).

        Raises:
            NotFoundError: If connector not found.
            ForbiddenError: If user lacks permission.
        """
        # Get connector
        result = await self.db.execute(
            select(ConnectorORM)
            .where(ConnectorORM.id == connector_id)
            .where(ConnectorORM.deleted_date.is_(None))
        )
        connector = result.scalar_one_or_none()

        if not connector:
            raise NotFoundError("Connector", connector_id)

        # Check edit permission (sync requires edit access)
        access = await self.permissions.can_edit_connector(user, connector)
        if not access:
            logger.warning(
                "🚫 User %d denied syncing connector %d: %s",
                user.id,
                connector_id,
                access.reason,
            )
            raise ForbiddenError(f"Cannot trigger sync: {access.reason}")

        if connector.status == "syncing":
            return False, "Sync already in progress"

        if not self.nats:
            logger.warning("⚠️ NATS publisher not available, cannot trigger sync")
            return False, "NATS not available"

        # Update status to pending
        connector.status = "pending"
        connector.user_id_last_update = user.id

        # Publish sync message
        await self._publish_sync_message(connector)

        return True, "Sync triggered"

    async def get_connector_status(
        self,
        connector_id: int,
        user: "TokenUser",
    ) -> dict:
        """
        Get detailed status for a connector with RBAC check.

        Args:
            connector_id: The connector ID.
            user: The authenticated user.

        Returns:
            Dict with status information.

        Raises:
            NotFoundError: If connector not found.
            ForbiddenError: If user lacks permission.
        """
        connector = await self.get_connector(connector_id, user)

        # Count pending documents
        pending_result = await self.db.execute(
            select(func.count(DocumentORM.id))
            .where(DocumentORM.connector_id == connector_id)
            .where(DocumentORM.status == "pending")
        )
        docs_pending = pending_result.scalar() or 0

        return {
            "status": connector.status,
            "status_message": connector.status_message,
            "last_sync_at": connector.last_sync_at,
            "docs_analyzed": connector.docs_analyzed,
            "docs_pending": docs_pending,
        }

    async def _publish_sync_message(self, connector: ConnectorORM) -> None:
        """
        Publish a sync message to NATS.

        Args:
            connector: The connector to sync.
        """
        if not self.nats:
            logger.warning("⚠️ NATS publisher not available")
            return

        # Generate chunking session ID
        chunking_session = str(uuid.uuid4())

        # Build protobuf message
        request = ConnectorSyncRequest()
        request.connector_id = connector.id
        request.user_id = connector.user_id
        request.chunking_session = chunking_session

        # Set connector type enum
        type_name = (
            f"CONNECTOR_TYPE_{connector.type.upper()}"
            if connector.type
            else "CONNECTOR_TYPE_UNSPECIFIED"
        )
        type_value = getattr(
            connector_pb2.ConnectorType,
            type_name,
            connector_pb2.ConnectorType.CONNECTOR_TYPE_UNSPECIFIED,
        )
        request.type = type_value

        # Set scope enum
        scope_name = (
            f"CONNECTOR_SCOPE_{connector.scope.upper()}"
            if connector.scope
            else "CONNECTOR_SCOPE_USER"
        )
        scope_value = getattr(
            connector_pb2.ConnectorScope,
            scope_name,
            connector_pb2.ConnectorScope.CONNECTOR_SCOPE_USER,
        )
        request.scope = scope_value

        if connector.scope_id:
            request.scope_id = connector.scope_id

        # Note: team_id is stored in DB but not in proto
        # For team-scoped connectors, the scope_id could contain team info
        # or the team_id can be looked up from connector_id on the receiving end

        # Convert config dict to protobuf Struct
        if connector.config:
            config_struct = struct_pb2.Struct()
            config_struct.update(connector.config)
            request.config.CopyFrom(config_struct)

        # Convert state dict to protobuf Struct
        if connector.state:
            state_struct = struct_pb2.Struct()
            state_struct.update(connector.state)
            request.state.CopyFrom(state_struct)

        # Determine NATS subject based on connector type
        subject = f"connector.sync.{connector.type}"

        # Publish message
        await self.nats.publish(subject, request.SerializeToString())

        logger.info(
            "📤 Published sync message for connector %d to %s (session: %s)",
            connector.id,
            subject,
            chunking_session,
        )
