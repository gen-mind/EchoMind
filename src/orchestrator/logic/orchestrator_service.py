"""
Orchestrator Service business logic.

Handles connector sync scheduling and NATS message publishing.
This is protocol-agnostic business logic that can be used by any entry point.
"""

import logging
import uuid

from google.protobuf import struct_pb2
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.connector import connector_crud
from echomind_lib.db.models import Connector
from echomind_lib.db.nats_publisher import JetStreamPublisher
from echomind_lib.models.internal import orchestrator_pb2
from echomind_lib.models.public import connector_pb2

from orchestrator.logic.exceptions import (
    ConnectorNotFoundError,
    SyncTriggerError,
)

logger = logging.getLogger(__name__)


# NATS subject mapping by connector type
CONNECTOR_SUBJECTS: dict[str, str] = {
    "web": "connector.sync.web",
    "file": "connector.sync.file",
    "onedrive": "connector.sync.onedrive",
    "google_drive": "connector.sync.google_drive",
    "gmail": "connector.sync.gmail",
    "google_calendar": "connector.sync.google_calendar",
    "google_contacts": "connector.sync.google_contacts",
    "teams": "connector.sync.teams",
}

# Connector type string to proto enum mapping
CONNECTOR_TYPE_MAP: dict[str, int] = {
    "web": connector_pb2.ConnectorType.CONNECTOR_TYPE_WEB,
    "file": connector_pb2.ConnectorType.CONNECTOR_TYPE_FILE,
    "onedrive": connector_pb2.ConnectorType.CONNECTOR_TYPE_ONEDRIVE,
    "google_drive": connector_pb2.ConnectorType.CONNECTOR_TYPE_GOOGLE_DRIVE,
    "gmail": connector_pb2.ConnectorType.CONNECTOR_TYPE_GMAIL,
    "google_calendar": connector_pb2.ConnectorType.CONNECTOR_TYPE_GOOGLE_CALENDAR,
    "google_contacts": connector_pb2.ConnectorType.CONNECTOR_TYPE_GOOGLE_CONTACTS,
    "teams": connector_pb2.ConnectorType.CONNECTOR_TYPE_TEAMS,
}

# Connector scope string to proto enum mapping
# Note: "team" maps to GROUP (proto doesn't have TEAM enum)
CONNECTOR_SCOPE_MAP: dict[str, int] = {
    "user": connector_pb2.ConnectorScope.CONNECTOR_SCOPE_USER,
    "team": connector_pb2.ConnectorScope.CONNECTOR_SCOPE_GROUP,  # team uses GROUP
    "group": connector_pb2.ConnectorScope.CONNECTOR_SCOPE_GROUP,
    "org": connector_pb2.ConnectorScope.CONNECTOR_SCOPE_ORG,
}


class OrchestratorService:
    """
    Core orchestrator business logic.

    Responsibilities:
    - Query connectors due for sync
    - Update connector status to pending
    - Publish sync messages to NATS

    Usage:
        service = OrchestratorService(db_session, nats_publisher)
        triggered = await service.check_and_trigger_syncs()
        logger.info(f"📊 Triggered {triggered} syncs")
    """

    def __init__(
        self,
        session: AsyncSession,
        publisher: JetStreamPublisher,
    ):
        """
        Initialize orchestrator service.

        Args:
            session: Database session for queries.
            publisher: NATS JetStream publisher for messages.
        """
        self._session = session
        self._publisher = publisher

    async def check_and_trigger_syncs(self) -> int:
        """
        Check for connectors due for sync and trigger them.

        This is the main job that runs on the configured interval.
        For each connector due for sync:
        1. Update status to pending
        2. Publish NATS message

        Returns:
            Number of syncs triggered.

        Raises:
            SyncTriggerError: If NATS publish fails.
        """
        logger.info("🔍 Checking connectors for sync...")

        # Get connectors due for sync
        connectors = await connector_crud.get_due_for_sync(self._session)

        if not connectors:
            logger.debug("📭 No connectors due for sync")
            return 0

        triggered = 0
        for connector in connectors:
            try:
                await self._trigger_sync(connector)
                triggered += 1
            except SyncTriggerError as e:
                logger.error(f"❌ {e.message}")
            except Exception as e:
                logger.exception(
                    f"❌ Unexpected error triggering sync for connector {connector.id}: {e}"
                )

        logger.info(f"📤 Triggered {triggered} sync(s)")
        return triggered

    async def _trigger_sync(self, connector: Connector) -> str:
        """
        Trigger a sync for a single connector.

        Args:
            connector: Connector to sync.

        Returns:
            Chunking session ID for tracking.

        Raises:
            SyncTriggerError: If update or publish fails.
        """
        # Generate unique session ID for this sync
        chunking_session = str(uuid.uuid4())

        # Update status to pending
        updated = await connector_crud.update_status(
            self._session,
            connector.id,
            status="pending",
            status_message=f"Queued for sync (session: {chunking_session})",
        )
        if not updated:
            raise SyncTriggerError(connector.id, "Failed to update status")

        await self._session.commit()

        # Get NATS subject for connector type
        subject = CONNECTOR_SUBJECTS.get(connector.type)
        if not subject:
            raise SyncTriggerError(connector.id, f"Unknown connector type: {connector.type}")

        # Build protobuf message
        request = self._build_sync_request(connector, chunking_session)

        # Publish to NATS (fire-and-forget)
        try:
            await self._publisher.publish(
                subject=subject,
                payload=request.SerializeToString(),
            )
        except Exception as e:
            raise SyncTriggerError(connector.id, f"NATS publish failed: {e}") from e

        logger.info(
            f"📤 Triggered sync for connector {connector.id} ({connector.type}) - session: {chunking_session}"
        )

        return chunking_session

    def _build_sync_request(
        self,
        connector: Connector,
        chunking_session: str,
    ) -> orchestrator_pb2.ConnectorSyncRequest:
        """
        Build the sync request protobuf message.

        Args:
            connector: Connector to sync.
            chunking_session: UUID for this sync session.

        Returns:
            ConnectorSyncRequest protobuf message.

        Raises:
            SyncTriggerError: If connector type is not in the mapping.
        """
        request = orchestrator_pb2.ConnectorSyncRequest()
        request.connector_id = connector.id
        request.user_id = connector.user_id
        request.chunking_session = chunking_session

        # Set connector type enum using explicit mapping
        connector_type = connector.type.lower() if connector.type else None
        if connector_type not in CONNECTOR_TYPE_MAP:
            raise SyncTriggerError(
                connector.id,
                f"Unknown connector type: {connector.type}",
            )
        request.type = CONNECTOR_TYPE_MAP[connector_type]

        # Set scope enum using explicit mapping
        # Note: "team" correctly maps to CONNECTOR_SCOPE_GROUP
        connector_scope = connector.scope.lower() if connector.scope else "user"
        request.scope = CONNECTOR_SCOPE_MAP.get(
            connector_scope,
            connector_pb2.ConnectorScope.CONNECTOR_SCOPE_USER,
        )

        # Set scope_id if present
        if connector.scope_id:
            request.scope_id = connector.scope_id

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

        logger.debug(
            f"🔧 Built sync request: connector_id={connector.id}, type={connector_type}, scope={connector_scope}, session={chunking_session}"
        )

        return request

    async def trigger_manual_sync(self, connector_id: int) -> str:
        """
        Manually trigger a sync for a specific connector.

        This bypasses the normal scheduling and immediately queues the connector.

        Args:
            connector_id: ID of the connector to sync.

        Returns:
            Chunking session ID for tracking.

        Raises:
            ConnectorNotFoundError: If connector doesn't exist.
            SyncTriggerError: If connector is already syncing or trigger fails.
        """
        connector = await connector_crud.get_by_id_active(self._session, connector_id)
        if not connector:
            raise ConnectorNotFoundError(connector_id)

        # Check if already processing
        if connector.status in ("pending", "syncing"):
            raise SyncTriggerError(
                connector_id,
                f"Connector is already {connector.status}",
            )

        # Check if disabled
        if connector.status == "disabled":
            raise SyncTriggerError(connector_id, "Connector is disabled")

        return await self._trigger_sync(connector)

    async def get_sync_stats(self) -> dict[str, int]:
        """
        Get current sync statistics.

        Returns:
            Dict with counts by status.
        """
        stats = {
            "pending": 0,
            "syncing": 0,
            "active": 0,
            "error": 0,
            "disabled": 0,
            "due_for_sync": 0,
        }

        for status in ["pending", "syncing", "active", "error", "disabled"]:
            connectors = await connector_crud.get_by_status(self._session, status)
            stats[status] = len(connectors)

        due = await connector_crud.get_due_for_sync(self._session)
        stats["due_for_sync"] = len(due)

        return stats
