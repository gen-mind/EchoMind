"""
Orchestrator Service business logic.

Handles connector sync scheduling and NATS message publishing.
This is protocol-agnostic business logic that can be used by any entry point.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.connector import connector_crud
from echomind_lib.db.models import Connector
from echomind_lib.db.nats_publisher import JetStreamPublisher

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
    "teams": "connector.sync.teams",
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
        logger.info("📊 Triggered %d syncs", triggered)
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
                logger.error("❌ %s", e.message)
            except Exception as e:
                logger.exception(
                    "❌ Unexpected error triggering sync for connector %d: %s",
                    connector.id,
                    e,
                )

        logger.info("✅ Triggered %d sync(s)", triggered)
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

        # Build message payload
        payload = self._build_sync_payload(connector, chunking_session)

        # Get NATS subject for connector type
        subject = CONNECTOR_SUBJECTS.get(connector.type)
        if not subject:
            raise SyncTriggerError(connector.id, f"Unknown connector type: {connector.type}")

        # Publish to NATS (fire-and-forget)
        try:
            await self._publisher.publish(
                subject=subject,
                payload=json.dumps(payload).encode("utf-8"),
            )
        except Exception as e:
            raise SyncTriggerError(connector.id, f"NATS publish failed: {e}") from e

        logger.info(
            "📤 Triggered sync for connector %d (%s) - session: %s",
            connector.id,
            connector.type,
            chunking_session,
        )

        return chunking_session

    def _build_sync_payload(
        self,
        connector: Connector,
        chunking_session: str,
    ) -> dict[str, Any]:
        """
        Build the sync request payload.

        Args:
            connector: Connector to sync.
            chunking_session: UUID for this sync session.

        Returns:
            Dict payload for NATS message.
        """
        return {
            "connector_id": connector.id,
            "type": connector.type,
            "user_id": connector.user_id,
            "scope": connector.scope,
            "scope_id": connector.scope_id,
            "config": connector.config,
            "state": connector.state,
            "chunking_session": chunking_session,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }

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
