"""
Unit tests for ConnectorService.

Tests connector CRUD operations with RBAC enforcement and NATS sync message publishing.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.logic.connector_service import ConnectorService
from api.logic.exceptions import ForbiddenError, NotFoundError
from api.logic.permissions import AccessResult


class TestConnectorService:
    """Tests for ConnectorService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_nats(self):
        """Create a mock NATS publisher."""
        nats = AsyncMock()
        nats.publish = AsyncMock()
        return nats

    @pytest.fixture
    def mock_user(self):
        """Create a mock TokenUser."""
        user = MagicMock()
        user.id = 42
        user.roles = ["echomind-allowed"]
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin TokenUser."""
        user = MagicMock()
        user.id = 100
        user.roles = ["echomind-allowed", "echomind-admins"]
        return user

    @pytest.fixture
    def mock_connector(self, mock_user):
        """Create a mock connector ORM object."""
        connector = MagicMock()
        connector.id = 1
        connector.name = "Test Connector"
        connector.type = "google_drive"
        connector.user_id = mock_user.id
        connector.scope = "user"
        connector.scope_id = ""
        connector.team_id = None
        connector.config = {"folder_id": "abc123"}
        connector.state = {}
        connector.status = "active"
        connector.status_message = None
        connector.last_sync_at = None
        connector.docs_analyzed = 0
        connector.refresh_freq_minutes = 60
        connector.deleted_date = None
        return connector

    @pytest.fixture
    def service(self, mock_db, mock_nats):
        """Create a ConnectorService with mocked dependencies."""
        return ConnectorService(mock_db, mock_nats)

    @pytest.fixture
    def service_no_nats(self, mock_db):
        """Create a ConnectorService without NATS."""
        return ConnectorService(mock_db, None)

    # =========================================================================
    # get_connector tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_connector_success(self, service, mock_db, mock_connector, mock_user):
        """Test getting an existing connector with permission."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_view_connector",
            return_value=AccessResult(True, "owner"),
        ):
            result = await service.get_connector(1, mock_user)

        assert result == mock_connector
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_connector_not_found(self, service, mock_db, mock_user):
        """Test getting a non-existent connector raises NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_connector(999, mock_user)

        assert "Connector" in str(exc_info.value)
        assert "999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_connector_forbidden(self, service, mock_db, mock_connector, mock_user):
        """Test getting a connector without permission raises ForbiddenError."""
        # Different user's connector
        mock_connector.user_id = 999
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_view_connector",
            return_value=AccessResult(False, "not owner"),
        ):
            with pytest.raises(ForbiddenError):
                await service.get_connector(1, mock_user)

    # =========================================================================
    # list_connectors tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_connectors_regular_user(self, service, mock_db, mock_connector, mock_user):
        """Test listing connectors for regular user."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_connector]
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "get_user_team_ids",
            return_value=[1, 2],
        ), patch.object(
            service.permissions,
            "is_admin",
            return_value=False,
        ):
            result = await service.list_connectors(mock_user)

        assert len(result) == 1
        assert result[0] == mock_connector

    @pytest.mark.asyncio
    async def test_list_connectors_admin_sees_all(
        self, service, mock_db, mock_connector, mock_admin_user
    ):
        """Test admin can list all connectors."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_connector]
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "is_admin",
            return_value=True,
        ):
            result = await service.list_connectors(mock_admin_user)

        assert len(result) == 1

    # =========================================================================
    # create_connector tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_connector_user_scope_success(
        self, service, mock_db, mock_nats, mock_user
    ):
        """Test creating a user-scoped connector successfully."""

        def set_connector_id(connector):
            connector.id = 1
            connector.type = "google_drive"
            connector.user_id = mock_user.id
            connector.scope = "user"
            connector.scope_id = ""
            connector.config = {}
            connector.state = {}

        mock_db.refresh.side_effect = set_connector_id

        with patch.object(
            service.permissions,
            "can_create_connector",
            return_value=AccessResult(True, "allowed user"),
        ):
            result = await service.create_connector(
                name="New Connector",
                connector_type="google_drive",
                user=mock_user,
                config={"folder_id": "abc"},
                trigger_sync=True,
            )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()
        mock_nats.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_connector_team_scope_requires_admin(
        self, service, mock_db, mock_user
    ):
        """Test creating team-scoped connector requires admin."""
        with patch.object(
            service.permissions,
            "can_create_connector",
            return_value=AccessResult(False, "admin role required"),
        ):
            with pytest.raises(ForbiddenError) as exc_info:
                await service.create_connector(
                    name="Team Connector",
                    connector_type="google_drive",
                    user=mock_user,
                    scope="team",
                    team_id=10,
                )

        assert "admin" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_connector_org_scope_requires_admin(
        self, service, mock_db, mock_user
    ):
        """Test creating org-scoped connector requires admin."""
        with patch.object(
            service.permissions,
            "can_create_connector",
            return_value=AccessResult(False, "admin required"),
        ):
            with pytest.raises(ForbiddenError) as exc_info:
                await service.create_connector(
                    name="Org Connector",
                    connector_type="google_drive",
                    user=mock_user,
                    scope="org",
                )

        assert "admin" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_connector_without_sync(
        self, service, mock_db, mock_nats, mock_user
    ):
        """Test creating a connector without triggering sync."""

        def set_connector_id(connector):
            connector.id = 1
            connector.type = "google_drive"
            connector.user_id = mock_user.id
            connector.scope = None
            connector.scope_id = ""
            connector.config = {}
            connector.state = {}

        mock_db.refresh.side_effect = set_connector_id

        with patch.object(
            service.permissions,
            "can_create_connector",
            return_value=AccessResult(True, "allowed user"),
        ):
            await service.create_connector(
                name="New Connector",
                connector_type="google_drive",
                user=mock_user,
                trigger_sync=False,
            )

        mock_db.add.assert_called_once()
        mock_nats.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_connector_no_nats_available(
        self, service_no_nats, mock_db, mock_user
    ):
        """Test creating a connector when NATS is not available."""

        def set_connector_id(connector):
            connector.id = 1
            connector.type = "onedrive"
            connector.user_id = mock_user.id
            connector.scope = None
            connector.scope_id = ""
            connector.config = {}
            connector.state = {}

        mock_db.refresh.side_effect = set_connector_id

        with patch.object(
            service_no_nats.permissions,
            "can_create_connector",
            return_value=AccessResult(True, "allowed user"),
        ):
            result = await service_no_nats.create_connector(
                name="New Connector",
                connector_type="onedrive",
                user=mock_user,
                trigger_sync=True,
            )

        mock_db.add.assert_called_once()

    # =========================================================================
    # update_connector tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_update_connector_success(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test updating a connector with permission."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_connector",
            return_value=AccessResult(True, "owner"),
        ):
            result = await service.update_connector(
                connector_id=1,
                user=mock_user,
                name="Updated Name",
                config={"new": "config"},
            )

        assert result.name == "Updated Name"
        assert result.config == {"new": "config"}

    @pytest.mark.asyncio
    async def test_update_connector_not_found(self, service, mock_db, mock_user):
        """Test updating non-existent connector raises NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.update_connector(
                connector_id=999,
                user=mock_user,
                name="New Name",
            )

    @pytest.mark.asyncio
    async def test_update_connector_forbidden(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test updating connector without permission raises ForbiddenError."""
        mock_connector.user_id = 999
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_connector",
            return_value=AccessResult(False, "not owner"),
        ):
            with pytest.raises(ForbiddenError):
                await service.update_connector(
                    connector_id=1,
                    user=mock_user,
                    name="New Name",
                )

    @pytest.mark.asyncio
    async def test_update_connector_partial(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test partial update only changes specified fields."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        original_config = mock_connector.config.copy()

        with patch.object(
            service.permissions,
            "can_edit_connector",
            return_value=AccessResult(True, "owner"),
        ):
            result = await service.update_connector(
                connector_id=1,
                user=mock_user,
                name="New Name Only",
            )

        assert result.name == "New Name Only"
        assert result.config == original_config

    @pytest.mark.asyncio
    async def test_update_connector_scope_change_requires_permission(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test changing connector scope requires permission for new scope."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_connector",
            return_value=AccessResult(True, "owner"),
        ), patch.object(
            service.permissions,
            "can_create_connector",
            return_value=AccessResult(False, "admin required for team scope"),
        ):
            with pytest.raises(ForbiddenError):
                await service.update_connector(
                    connector_id=1,
                    user=mock_user,
                    scope="team",
                    team_id=10,
                )

    # =========================================================================
    # delete_connector tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_connector_success(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test soft deleting a connector."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_delete_connector",
            return_value=AccessResult(True, "owner"),
        ):
            await service.delete_connector(1, mock_user)

        assert mock_connector.deleted_date is not None
        assert isinstance(mock_connector.deleted_date, datetime)

    @pytest.mark.asyncio
    async def test_delete_connector_not_found(self, service, mock_db, mock_user):
        """Test deleting non-existent connector raises NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.delete_connector(999, mock_user)

    @pytest.mark.asyncio
    async def test_delete_connector_forbidden(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test deleting connector without permission raises ForbiddenError."""
        mock_connector.user_id = 999
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_delete_connector",
            return_value=AccessResult(False, "not owner"),
        ):
            with pytest.raises(ForbiddenError):
                await service.delete_connector(1, mock_user)

    # =========================================================================
    # trigger_sync tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_trigger_sync_success(
        self, service, mock_db, mock_nats, mock_connector, mock_user
    ):
        """Test triggering a sync successfully."""
        mock_connector.status = "active"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_connector",
            return_value=AccessResult(True, "owner"),
        ):
            success, message = await service.trigger_sync(1, mock_user)

        assert success is True
        assert message == "Sync triggered"
        assert mock_connector.status == "pending"
        mock_nats.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_sync_already_syncing(
        self, service, mock_db, mock_nats, mock_connector, mock_user
    ):
        """Test triggering sync when already syncing returns failure."""
        mock_connector.status = "syncing"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_connector",
            return_value=AccessResult(True, "owner"),
        ):
            success, message = await service.trigger_sync(1, mock_user)

        assert success is False
        assert "already in progress" in message
        mock_nats.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_sync_no_nats(
        self, service_no_nats, mock_db, mock_connector, mock_user
    ):
        """Test triggering sync when NATS is not available."""
        mock_connector.status = "active"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service_no_nats.permissions,
            "can_edit_connector",
            return_value=AccessResult(True, "owner"),
        ):
            success, message = await service_no_nats.trigger_sync(1, mock_user)

        assert success is False
        assert "NATS not available" in message

    @pytest.mark.asyncio
    async def test_trigger_sync_not_found(self, service, mock_db, mock_user):
        """Test triggering sync for non-existent connector raises NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await service.trigger_sync(999, mock_user)

    @pytest.mark.asyncio
    async def test_trigger_sync_forbidden(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test triggering sync without edit permission raises ForbiddenError."""
        mock_connector.status = "active"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_connector",
            return_value=AccessResult(False, "not team lead"),
        ):
            with pytest.raises(ForbiddenError):
                await service.trigger_sync(1, mock_user)

    # =========================================================================
    # get_connector_status tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_connector_status_success(
        self, service, mock_db, mock_connector, mock_user
    ):
        """Test getting connector status."""
        mock_connector.status = "active"
        mock_connector.status_message = "Last sync successful"
        mock_connector.last_sync_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_connector.docs_analyzed = 100

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_connector

        mock_result2 = MagicMock()
        mock_result2.scalar.return_value = 5

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        with patch.object(
            service.permissions,
            "can_view_connector",
            return_value=AccessResult(True, "owner"),
        ):
            result = await service.get_connector_status(1, mock_user)

        assert result["status"] == "active"
        assert result["status_message"] == "Last sync successful"
        assert result["docs_analyzed"] == 100
        assert result["docs_pending"] == 5

    # =========================================================================
    # _publish_sync_message tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_publish_sync_message_content(
        self, service, mock_db, mock_nats, mock_connector
    ):
        """Test that sync message contains correct data."""
        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")

            await service._publish_sync_message(mock_connector)

        mock_nats.publish.assert_called_once()
        call_args = mock_nats.publish.call_args

        subject = call_args[0][0]
        assert subject == "connector.sync.google_drive"

        payload = call_args[0][1]
        assert isinstance(payload, bytes)

    @pytest.mark.asyncio
    async def test_publish_sync_message_different_types(self, service, mock_nats):
        """Test sync message subject varies by connector type."""
        for connector_type, expected_subject in [
            ("google_drive", "connector.sync.google_drive"),
            ("onedrive", "connector.sync.onedrive"),
            ("teams", "connector.sync.teams"),
        ]:
            mock_nats.reset_mock()

            connector = MagicMock()
            connector.id = 1
            connector.type = connector_type
            connector.user_id = 42
            connector.scope = "user"
            connector.scope_id = ""
            connector.team_id = None
            connector.config = {}
            connector.state = {}

            await service._publish_sync_message(connector)

            call_args = mock_nats.publish.call_args
            assert call_args[0][0] == expected_subject


class TestConnectorServiceRBAC:
    """RBAC-specific tests for ConnectorService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_nats(self):
        """Create a mock NATS publisher."""
        nats = AsyncMock()
        nats.publish = AsyncMock()
        return nats

    @pytest.fixture
    def service(self, mock_db, mock_nats):
        """Create a ConnectorService."""
        return ConnectorService(mock_db, mock_nats)

    @pytest.mark.asyncio
    async def test_team_member_can_view_team_connector(self, service, mock_db):
        """Test team member can view team-scoped connector."""
        user = MagicMock()
        user.id = 1
        user.roles = ["echomind-allowed"]

        connector = MagicMock()
        connector.id = 1
        connector.user_id = 99
        connector.scope = "team"
        connector.team_id = 10
        connector.deleted_date = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_view_connector",
            return_value=AccessResult(True, "team member"),
        ):
            result = await service.get_connector(1, user)

        assert result == connector

    @pytest.mark.asyncio
    async def test_admin_can_view_any_connector(self, service, mock_db):
        """Test admin can view any connector."""
        user = MagicMock()
        user.id = 1
        user.roles = ["echomind-allowed", "echomind-admins"]

        connector = MagicMock()
        connector.id = 1
        connector.user_id = 99
        connector.scope = "user"
        connector.deleted_date = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_view_connector",
            return_value=AccessResult(True, "admin"),
        ):
            result = await service.get_connector(1, user)

        assert result == connector

    @pytest.mark.asyncio
    async def test_admin_can_create_team_connector_as_member(
        self, service, mock_db, mock_nats
    ):
        """Test admin who is team member can create team connector."""
        user = MagicMock()
        user.id = 100
        user.roles = ["echomind-allowed", "echomind-admins"]

        def set_connector_id(connector):
            connector.id = 1
            connector.type = "google_drive"
            connector.user_id = user.id
            connector.scope = "team"
            connector.scope_id = ""
            connector.team_id = 10
            connector.config = {}
            connector.state = {}

        mock_db.refresh.side_effect = set_connector_id

        with patch.object(
            service.permissions,
            "can_create_connector",
            return_value=AccessResult(True, "admin and team member"),
        ):
            result = await service.create_connector(
                name="Team Connector",
                connector_type="google_drive",
                user=user,
                scope="team",
                team_id=10,
            )

        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_team_lead_can_edit_team_connector(self, service, mock_db):
        """Test team lead can edit team-scoped connector."""
        user = MagicMock()
        user.id = 50
        user.roles = ["echomind-allowed"]

        connector = MagicMock()
        connector.id = 1
        connector.name = "Original"
        connector.user_id = 99
        connector.scope = "team"
        connector.team_id = 10
        connector.deleted_date = None
        connector.last_update = None
        connector.user_id_last_update = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = connector
        mock_db.execute.return_value = mock_result

        with patch.object(
            service.permissions,
            "can_edit_connector",
            return_value=AccessResult(True, "team lead"),
        ):
            result = await service.update_connector(
                connector_id=1,
                user=user,
                name="Updated by Lead",
            )

        assert result.name == "Updated by Lead"
