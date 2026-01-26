"""Unit tests for orchestrator service logic."""

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.logic.orchestrator_service import (
    CONNECTOR_SUBJECTS,
    OrchestratorService,
)
from orchestrator.logic.exceptions import (
    ConnectorNotFoundError,
    SyncTriggerError,
)


def create_mock_connector(
    id: int = 1,
    type: str = "web",
    user_id: int = 1,
    scope: str = "user",
    scope_id: str | None = None,
    config: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    status: str = "active",
    status_message: str | None = None,
) -> MagicMock:
    """Create a mock connector for testing."""
    connector = MagicMock()
    connector.id = id
    connector.type = type
    connector.user_id = user_id
    connector.scope = scope
    connector.scope_id = scope_id
    connector.config = config or {"url": "https://example.com"}
    connector.state = state or {}
    connector.status = status
    connector.status_message = status_message
    return connector


class TestConnectorSubjects:
    """Tests for NATS subject mapping."""

    def test_web_subject(self) -> None:
        """Test web connector subject mapping."""
        assert CONNECTOR_SUBJECTS["web"] == "connector.sync.web"

    def test_file_subject(self) -> None:
        """Test file connector subject mapping."""
        assert CONNECTOR_SUBJECTS["file"] == "connector.sync.file"

    def test_onedrive_subject(self) -> None:
        """Test OneDrive connector subject mapping."""
        assert CONNECTOR_SUBJECTS["onedrive"] == "connector.sync.onedrive"

    def test_google_drive_subject(self) -> None:
        """Test Google Drive connector subject mapping."""
        assert CONNECTOR_SUBJECTS["google_drive"] == "connector.sync.google_drive"

    def test_teams_subject(self) -> None:
        """Test Teams connector subject mapping."""
        assert CONNECTOR_SUBJECTS["teams"] == "connector.sync.teams"


class TestOrchestratorService:
    """Tests for OrchestratorService class."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        """Create mock NATS publisher."""
        publisher = AsyncMock()
        publisher.publish = AsyncMock()
        return publisher

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_publisher: AsyncMock,
    ) -> OrchestratorService:
        """Create orchestrator service with mocks."""
        return OrchestratorService(mock_session, mock_publisher)

    @pytest.mark.asyncio
    async def test_check_and_trigger_syncs_no_connectors(
        self,
        service: OrchestratorService,
    ) -> None:
        """Test sync check with no connectors due."""
        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.get_due_for_sync = AsyncMock(return_value=[])

            triggered = await service.check_and_trigger_syncs()

            assert triggered == 0
            mock_crud.get_due_for_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_and_trigger_syncs_with_connectors(
        self,
        service: OrchestratorService,
        mock_publisher: AsyncMock,
    ) -> None:
        """Test sync check triggers syncs for due connectors."""
        connectors = [
            create_mock_connector(id=1, type="web"),
            create_mock_connector(id=2, type="onedrive"),
        ]

        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.get_due_for_sync = AsyncMock(return_value=connectors)
            mock_crud.update_status = AsyncMock(return_value=connectors[0])

            triggered = await service.check_and_trigger_syncs()

            assert triggered == 2
            assert mock_publisher.publish.call_count == 2

    @pytest.mark.asyncio
    async def test_check_and_trigger_syncs_handles_errors(
        self,
        service: OrchestratorService,
    ) -> None:
        """Test sync check handles errors gracefully."""
        connector = create_mock_connector(id=1, type="web")

        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.get_due_for_sync = AsyncMock(return_value=[connector])
            mock_crud.update_status = AsyncMock(return_value=None)  # Simulate failure

            triggered = await service.check_and_trigger_syncs()

            assert triggered == 0

    @pytest.mark.asyncio
    async def test_trigger_sync_publishes_message(
        self,
        service: OrchestratorService,
        mock_publisher: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test that trigger sync publishes NATS message."""
        connector = create_mock_connector(id=1, type="web")

        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.update_status = AsyncMock(return_value=connector)

            await service._trigger_sync(connector)

            mock_publisher.publish.assert_called_once()
            call_args = mock_publisher.publish.call_args
            assert call_args.kwargs["subject"] == "connector.sync.web"

    @pytest.mark.asyncio
    async def test_trigger_sync_unknown_type_raises(
        self,
        service: OrchestratorService,
    ) -> None:
        """Test that unknown connector type raises error."""
        connector = create_mock_connector(id=1, type="unknown_type")

        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.update_status = AsyncMock(return_value=connector)

            with pytest.raises(SyncTriggerError) as exc_info:
                await service._trigger_sync(connector)

            assert "Unknown connector type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_trigger_sync_nats_failure_raises(
        self,
        service: OrchestratorService,
        mock_publisher: AsyncMock,
    ) -> None:
        """Test that NATS publish failure raises error."""
        connector = create_mock_connector(id=1, type="web")
        mock_publisher.publish.side_effect = Exception("NATS error")

        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.update_status = AsyncMock(return_value=connector)

            with pytest.raises(SyncTriggerError) as exc_info:
                await service._trigger_sync(connector)

            assert "NATS publish failed" in str(exc_info.value)

    def test_build_sync_payload(
        self,
        service: OrchestratorService,
    ) -> None:
        """Test sync payload building."""
        connector = create_mock_connector(
            id=1,
            type="web",
            user_id=10,
            scope="user",
            scope_id=None,
            config={"url": "https://example.com"},
            state={"etag": "abc123"},
        )
        session_id = "test-session-123"

        payload = service._build_sync_payload(connector, session_id)

        assert payload["connector_id"] == 1
        assert payload["type"] == "web"
        assert payload["user_id"] == 10
        assert payload["scope"] == "user"
        assert payload["scope_id"] is None
        assert payload["config"] == {"url": "https://example.com"}
        assert payload["state"] == {"etag": "abc123"}
        assert payload["chunking_session"] == session_id
        assert "triggered_at" in payload

    @pytest.mark.asyncio
    async def test_trigger_manual_sync_not_found(
        self,
        service: OrchestratorService,
    ) -> None:
        """Test manual sync with non-existent connector."""
        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.get_by_id_active = AsyncMock(return_value=None)

            with pytest.raises(ConnectorNotFoundError) as exc_info:
                await service.trigger_manual_sync(999)

            assert exc_info.value.connector_id == 999

    @pytest.mark.asyncio
    async def test_trigger_manual_sync_already_pending(
        self,
        service: OrchestratorService,
    ) -> None:
        """Test manual sync on already pending connector."""
        connector = create_mock_connector(id=1, status="pending")

        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.get_by_id_active = AsyncMock(return_value=connector)

            with pytest.raises(SyncTriggerError) as exc_info:
                await service.trigger_manual_sync(1)

            assert "already pending" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_trigger_manual_sync_disabled(
        self,
        service: OrchestratorService,
    ) -> None:
        """Test manual sync on disabled connector."""
        connector = create_mock_connector(id=1, status="disabled")

        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.get_by_id_active = AsyncMock(return_value=connector)

            with pytest.raises(SyncTriggerError) as exc_info:
                await service.trigger_manual_sync(1)

            assert "disabled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_sync_stats(
        self,
        service: OrchestratorService,
    ) -> None:
        """Test sync statistics retrieval."""
        with patch(
            "orchestrator.logic.orchestrator_service.connector_crud"
        ) as mock_crud:
            mock_crud.get_by_status = AsyncMock(
                side_effect=lambda s, status: [MagicMock()] * (1 if status == "active" else 0)
            )
            mock_crud.get_due_for_sync = AsyncMock(return_value=[MagicMock()])

            stats = await service.get_sync_stats()

            assert stats["active"] == 1
            assert stats["pending"] == 0
            assert stats["due_for_sync"] == 1
