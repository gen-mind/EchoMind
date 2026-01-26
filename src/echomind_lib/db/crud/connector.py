"""
Connector CRUD operations.
"""

from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase, SoftDeleteMixin
from echomind_lib.db.models import Connector


class ConnectorCRUD(SoftDeleteMixin[Connector], CRUDBase[Connector]):
    """
    CRUD operations for Connector model.

    Connectors are data sources (Teams, Drive, etc.) with sync state.
    """

    def __init__(self):
        """Initialize ConnectorCRUD."""
        super().__init__(Connector)

    async def get_by_user(
        self,
        session: AsyncSession,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Connector]:
        """
        Get connectors owned by a user.

        Args:
            session: Database session.
            user_id: Owner user ID.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of user's connectors.
        """
        result = await session.execute(
            select(Connector)
            .where(Connector.deleted_date.is_(None))
            .where(Connector.user_id == user_id)
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_type(
        self,
        session: AsyncSession,
        connector_type: str,
    ) -> Sequence[Connector]:
        """
        Get connectors by type.

        Args:
            session: Database session.
            connector_type: Type (teams, onedrive, google_drive, web, file).

        Returns:
            List of connectors of that type.
        """
        result = await session.execute(
            select(Connector)
            .where(Connector.deleted_date.is_(None))
            .where(Connector.type == connector_type)
        )
        return result.scalars().all()

    async def get_by_status(
        self,
        session: AsyncSession,
        status: str,
    ) -> Sequence[Connector]:
        """
        Get connectors by status.

        Args:
            session: Database session.
            status: Status (pending, syncing, active, error, disabled).

        Returns:
            List of connectors with that status.
        """
        result = await session.execute(
            select(Connector)
            .where(Connector.deleted_date.is_(None))
            .where(Connector.status == status)
        )
        return result.scalars().all()

    async def get_due_for_sync(
        self,
        session: AsyncSession,
    ) -> Sequence[Connector]:
        """
        Get connectors due for sync.

        Finds connectors where:
        - status is 'active' or 'error'
        - has refresh_freq_minutes set
        - last_sync_at + refresh_freq <= now

        Args:
            session: Database session.

        Returns:
            List of connectors needing sync.
        """
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Connector)
            .where(Connector.deleted_date.is_(None))
            .where(Connector.status.in_(["active", "error"]))
            .where(Connector.refresh_freq_minutes.isnot(None))
        )
        connectors = result.scalars().all()

        # Filter by time (SQLAlchemy interval math is DB-specific)
        due = []
        for c in connectors:
            if c.last_sync_at is None:
                due.append(c)
            else:
                next_sync = c.last_sync_at + timedelta(minutes=c.refresh_freq_minutes)
                # Handle timezone-naive timestamps from DB
                if next_sync.tzinfo is None:
                    next_sync = next_sync.replace(tzinfo=timezone.utc)
                if next_sync <= now:
                    due.append(c)
        return due

    async def update_status(
        self,
        session: AsyncSession,
        connector_id: int,
        status: str,
        status_message: str | None = None,
    ) -> Connector | None:
        """
        Update connector status.

        Args:
            session: Database session.
            connector_id: Connector ID.
            status: New status.
            status_message: Optional status message.

        Returns:
            Updated connector or None.
        """
        connector = await self.get_by_id_active(session, connector_id)
        if connector:
            connector.status = status
            connector.status_message = status_message
            connector.last_update = datetime.now(timezone.utc)
            await session.flush()
            return connector
        return None

    async def update_sync_completed(
        self,
        session: AsyncSession,
        connector_id: int,
        docs_analyzed: int,
        state: dict | None = None,
    ) -> Connector | None:
        """
        Update connector after successful sync.

        Args:
            session: Database session.
            connector_id: Connector ID.
            docs_analyzed: Number of documents analyzed.
            state: Updated state dict (delta tokens, etc.).

        Returns:
            Updated connector or None.
        """
        connector = await self.get_by_id_active(session, connector_id)
        if connector:
            connector.status = "active"
            connector.status_message = None
            connector.last_sync_at = datetime.now(timezone.utc)
            connector.docs_analyzed = docs_analyzed
            connector.last_update = datetime.now(timezone.utc)
            if state is not None:
                connector.state = state
            await session.flush()
            return connector
        return None


connector_crud = ConnectorCRUD()
