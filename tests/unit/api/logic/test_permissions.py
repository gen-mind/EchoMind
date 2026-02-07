"""
Unit tests for PermissionChecker.

Tests RBAC permission checking for connectors, documents, and team access.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.logic.permissions import (
    ROLE_ADMIN,
    ROLE_ALLOWED,
    SCOPE_GROUP,
    SCOPE_ORG,
    SCOPE_TEAM,
    SCOPE_USER,
    AccessResult,
    PermissionChecker,
)


class TestAccessResult:
    """Tests for AccessResult dataclass."""

    def test_access_result_allowed_is_truthy(self):
        """Test that allowed=True AccessResult is truthy."""
        result = AccessResult(allowed=True, reason="test")
        assert bool(result) is True

    def test_access_result_denied_is_falsy(self):
        """Test that allowed=False AccessResult is falsy."""
        result = AccessResult(allowed=False, reason="denied")
        assert bool(result) is False

    def test_access_result_stores_reason(self):
        """Test that AccessResult stores the reason."""
        result = AccessResult(allowed=True, reason="admin")
        assert result.reason == "admin"


class TestPermissionCheckerRoles:
    """Tests for role-checking helper methods."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def checker(self, mock_db):
        """Create a PermissionChecker instance."""
        return PermissionChecker(mock_db)

    @pytest.fixture
    def allowed_user(self):
        """Create a user with echomind-allowed role."""
        user = MagicMock()
        user.id = 1
        user.roles = [ROLE_ALLOWED]
        return user

    @pytest.fixture
    def admin_user(self):
        """Create a user with echomind-admins role."""
        user = MagicMock()
        user.id = 2
        user.roles = [ROLE_ALLOWED, ROLE_ADMIN]
        return user

    @pytest.fixture
    def no_role_user(self):
        """Create a user with no roles."""
        user = MagicMock()
        user.id = 4
        user.roles = []
        return user

    # =========================================================================
    # is_allowed tests
    # =========================================================================

    def test_is_allowed_with_allowed_role(self, checker, allowed_user):
        """Test is_allowed returns True for users with echomind-allowed."""
        assert checker.is_allowed(allowed_user) is True

    def test_is_allowed_with_admin_role(self, checker, admin_user):
        """Test is_allowed returns True for users with echomind-admins."""
        assert checker.is_allowed(admin_user) is True

    def test_is_allowed_with_no_role(self, checker, no_role_user):
        """Test is_allowed returns False for users with no roles."""
        assert checker.is_allowed(no_role_user) is False

    # =========================================================================
    # is_admin tests
    # =========================================================================

    def test_is_admin_with_allowed_role(self, checker, allowed_user):
        """Test is_admin returns False for regular allowed users."""
        assert checker.is_admin(allowed_user) is False

    def test_is_admin_with_admin_role(self, checker, admin_user):
        """Test is_admin returns True for users with echomind-admins."""
        assert checker.is_admin(admin_user) is True

    def test_is_admin_with_no_role(self, checker, no_role_user):
        """Test is_admin returns False for users with no roles."""
        assert checker.is_admin(no_role_user) is False


class TestPermissionCheckerTeams:
    """Tests for team-related helper methods."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def checker(self, mock_db):
        """Create a PermissionChecker instance."""
        return PermissionChecker(mock_db)

    # =========================================================================
    # get_user_team_ids tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_user_team_ids_returns_team_list(self, checker, mock_db):
        """Test getting user's team IDs."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[1, 2, 3])
            mp.setattr(
                "api.logic.permissions.team_crud", mock_crud
            )

            result = await checker.get_user_team_ids(42)

            assert result == [1, 2, 3]
            mock_crud.get_team_ids_for_user.assert_called_once_with(mock_db, 42)

    @pytest.mark.asyncio
    async def test_get_user_team_ids_caches_result(self, checker, mock_db):
        """Test that team IDs are cached."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[1, 2])
            mp.setattr(
                "api.logic.permissions.team_crud", mock_crud
            )

            # Call twice
            result1 = await checker.get_user_team_ids(42)
            result2 = await checker.get_user_team_ids(42)

            assert result1 == result2
            # Should only call DB once
            assert mock_crud.get_team_ids_for_user.call_count == 1

    @pytest.mark.asyncio
    async def test_get_user_team_ids_empty_list(self, checker, mock_db):
        """Test getting team IDs for user with no teams."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[])
            mp.setattr(
                "api.logic.permissions.team_crud", mock_crud
            )

            result = await checker.get_user_team_ids(42)

            assert result == []

    # =========================================================================
    # is_team_member tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_is_team_member_true(self, checker, mock_db):
        """Test is_team_member returns True when user is member."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[1, 2, 3])
            mp.setattr(
                "api.logic.permissions.team_crud", mock_crud
            )

            result = await checker.is_team_member(42, 2)

            assert result is True

    @pytest.mark.asyncio
    async def test_is_team_member_false(self, checker, mock_db):
        """Test is_team_member returns False when user is not member."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[1, 2, 3])
            mp.setattr(
                "api.logic.permissions.team_crud", mock_crud
            )

            result = await checker.is_team_member(42, 99)

            assert result is False

    # =========================================================================
    # is_team_lead tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_is_team_lead_as_leader(self, checker, mock_db):
        """Test is_team_lead returns True for team leader."""
        mock_team = MagicMock()
        mock_team.leader_id = 42

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_team
        mock_db.execute.return_value = mock_result

        result = await checker.is_team_lead(42, 1)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_team_lead_as_lead_role(self, checker, mock_db):
        """Test is_team_lead returns True for user with lead role."""
        mock_team = MagicMock()
        mock_team.leader_id = 999  # Different user is leader

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_team
        mock_db.execute.return_value = mock_result

        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.is_lead = AsyncMock(return_value=True)
            mp.setattr(
                "api.logic.permissions.team_crud", mock_crud
            )

            result = await checker.is_team_lead(42, 1)

            assert result is True

    @pytest.mark.asyncio
    async def test_is_team_lead_regular_member(self, checker, mock_db):
        """Test is_team_lead returns False for regular member."""
        mock_team = MagicMock()
        mock_team.leader_id = 999

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_team
        mock_db.execute.return_value = mock_result

        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.is_lead = AsyncMock(return_value=False)
            mp.setattr(
                "api.logic.permissions.team_crud", mock_crud
            )

            result = await checker.is_team_lead(42, 1)

            assert result is False

    @pytest.mark.asyncio
    async def test_is_team_lead_team_not_found(self, checker, mock_db):
        """Test is_team_lead returns False when team doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await checker.is_team_lead(42, 999)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_team_lead_caches_result(self, checker, mock_db):
        """Test that is_team_lead caches results."""
        mock_team = MagicMock()
        mock_team.leader_id = 42

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_team
        mock_db.execute.return_value = mock_result

        # Call twice
        result1 = await checker.is_team_lead(42, 1)
        result2 = await checker.is_team_lead(42, 1)

        assert result1 == result2
        # Should only query DB once
        assert mock_db.execute.call_count == 1


class TestPermissionCheckerConnectorView:
    """Tests for can_view_connector method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def checker(self, mock_db):
        """Create a PermissionChecker instance."""
        return PermissionChecker(mock_db)

    @pytest.fixture
    def admin_user(self):
        """Create an admin user."""
        user = MagicMock()
        user.id = 2
        user.roles = [ROLE_ALLOWED, ROLE_ADMIN]
        return user

    @pytest.fixture
    def allowed_user(self):
        """Create a regular allowed user."""
        user = MagicMock()
        user.id = 3
        user.roles = [ROLE_ALLOWED]
        return user

    @pytest.fixture
    def user_connector(self, allowed_user):
        """Create a user-scoped connector."""
        connector = MagicMock()
        connector.id = 1
        connector.user_id = allowed_user.id
        connector.scope = SCOPE_USER
        connector.team_id = None
        return connector

    @pytest.fixture
    def team_connector(self):
        """Create a team-scoped connector."""
        connector = MagicMock()
        connector.id = 2
        connector.user_id = 99  # Different user
        connector.scope = SCOPE_TEAM
        connector.team_id = 10
        return connector

    @pytest.fixture
    def org_connector(self):
        """Create an org-scoped connector."""
        connector = MagicMock()
        connector.id = 3
        connector.user_id = 99
        connector.scope = SCOPE_ORG
        connector.team_id = None
        return connector

    # =========================================================================
    # Admin access
    # =========================================================================

    @pytest.mark.asyncio
    async def test_admin_can_view_any_connector(
        self, checker, admin_user, user_connector
    ):
        """Test admin can view any connector."""
        result = await checker.can_view_connector(admin_user, user_connector)

        assert result.allowed is True
        assert result.reason == "admin"

    # =========================================================================
    # User scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_owner_can_view_user_connector(
        self, checker, allowed_user, user_connector
    ):
        """Test owner can view their user-scoped connector."""
        result = await checker.can_view_connector(allowed_user, user_connector)

        assert result.allowed is True
        assert result.reason == "owner"

    @pytest.mark.asyncio
    async def test_non_owner_non_admin_cannot_view_user_connector(
        self, checker, user_connector
    ):
        """Test non-owner non-admin cannot view user-scoped connector."""
        other_user = MagicMock()
        other_user.id = 999
        other_user.roles = [ROLE_ALLOWED]
        result = await checker.can_view_connector(other_user, user_connector)

        assert result.allowed is False
        assert "not owner" in result.reason

    # =========================================================================
    # Team scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_team_member_can_view_team_connector(
        self, checker, allowed_user, team_connector, mock_db
    ):
        """Test team member can view team-scoped connector."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[10, 20])
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.can_view_connector(allowed_user, team_connector)

            assert result.allowed is True
            assert result.reason == "team member"

    @pytest.mark.asyncio
    async def test_non_member_cannot_view_team_connector(
        self, checker, allowed_user, team_connector, mock_db
    ):
        """Test non-member cannot view team-scoped connector."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[1, 2])  # Not team 10
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.can_view_connector(allowed_user, team_connector)

            assert result.allowed is False
            assert "not a member" in result.reason

    @pytest.mark.asyncio
    async def test_group_scope_treated_as_team(
        self, checker, allowed_user, team_connector, mock_db
    ):
        """Test legacy 'group' scope is treated same as 'team'."""
        team_connector.scope = SCOPE_GROUP

        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[10])
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.can_view_connector(allowed_user, team_connector)

            assert result.allowed is True

    # =========================================================================
    # Org scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_allowed_user_can_view_org_connector(
        self, checker, allowed_user, org_connector
    ):
        """Test any allowed user can view org-scoped connector."""
        result = await checker.can_view_connector(allowed_user, org_connector)

        assert result.allowed is True
        assert "org scope" in result.reason

    @pytest.mark.asyncio
    async def test_no_role_user_cannot_view_org_connector(
        self, checker, org_connector
    ):
        """Test user without roles cannot view org-scoped connector."""
        user = MagicMock()
        user.id = 99
        user.roles = []

        result = await checker.can_view_connector(user, org_connector)

        assert result.allowed is False
        assert "not an allowed user" in result.reason


class TestPermissionCheckerConnectorEdit:
    """Tests for can_edit_connector method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def checker(self, mock_db):
        """Create a PermissionChecker instance."""
        return PermissionChecker(mock_db)

    @pytest.fixture
    def admin_user(self):
        """Create an admin user."""
        user = MagicMock()
        user.id = 2
        user.roles = [ROLE_ALLOWED, ROLE_ADMIN]
        return user

    @pytest.fixture
    def allowed_user(self):
        """Create a regular allowed user."""
        user = MagicMock()
        user.id = 3
        user.roles = [ROLE_ALLOWED]
        return user

    @pytest.fixture
    def user_connector(self, allowed_user):
        """Create a user-scoped connector."""
        connector = MagicMock()
        connector.id = 1
        connector.user_id = allowed_user.id
        connector.scope = SCOPE_USER
        connector.team_id = None
        return connector

    @pytest.fixture
    def team_connector(self):
        """Create a team-scoped connector."""
        connector = MagicMock()
        connector.id = 2
        connector.user_id = 99
        connector.scope = SCOPE_TEAM
        connector.team_id = 10
        return connector

    @pytest.fixture
    def org_connector(self):
        """Create an org-scoped connector."""
        connector = MagicMock()
        connector.id = 3
        connector.user_id = 99
        connector.scope = SCOPE_ORG
        connector.team_id = None
        return connector

    # =========================================================================
    # Admin access
    # =========================================================================

    @pytest.mark.asyncio
    async def test_admin_can_edit_any_connector(
        self, checker, admin_user, org_connector
    ):
        """Test admin can edit any connector."""
        result = await checker.can_edit_connector(admin_user, org_connector)

        assert result.allowed is True
        assert result.reason == "admin"

    # =========================================================================
    # User scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_owner_can_edit_user_connector(
        self, checker, allowed_user, user_connector
    ):
        """Test owner can edit their user-scoped connector."""
        result = await checker.can_edit_connector(allowed_user, user_connector)

        assert result.allowed is True
        assert result.reason == "owner"

    @pytest.mark.asyncio
    async def test_non_owner_non_admin_cannot_edit_user_connector(
        self, checker, user_connector
    ):
        """Test non-owner non-admin cannot edit user-scoped connector."""
        other_user = MagicMock()
        other_user.id = 999
        other_user.roles = [ROLE_ALLOWED]
        result = await checker.can_edit_connector(other_user, user_connector)

        assert result.allowed is False

    # =========================================================================
    # Team scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_team_lead_can_edit_team_connector(
        self, checker, allowed_user, team_connector, mock_db
    ):
        """Test team lead can edit team-scoped connector."""
        # Mock is_team_lead to return True
        mock_team = MagicMock()
        mock_team.leader_id = allowed_user.id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_team
        mock_db.execute.return_value = mock_result

        result = await checker.can_edit_connector(allowed_user, team_connector)

        assert result.allowed is True
        assert "team lead" in result.reason

    @pytest.mark.asyncio
    async def test_admin_can_edit_team_connector(
        self, checker, admin_user, team_connector, mock_db
    ):
        """Test admin can edit team-scoped connector (early return as admin)."""
        result = await checker.can_edit_connector(admin_user, team_connector)

        assert result.allowed is True
        assert result.reason == "admin"

    @pytest.mark.asyncio
    async def test_regular_member_cannot_edit_team_connector(
        self, checker, allowed_user, team_connector, mock_db
    ):
        """Test regular team member cannot edit team-scoped connector."""
        mock_team = MagicMock()
        mock_team.leader_id = 999

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_team
        mock_db.execute.return_value = mock_result

        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.is_lead = AsyncMock(return_value=False)
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[10])
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.can_edit_connector(allowed_user, team_connector)

            assert result.allowed is False
            assert "not a lead" in result.reason

    # =========================================================================
    # Org scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_allowed_user_cannot_edit_org_connector_without_admin(
        self, checker, org_connector
    ):
        """Test non-admin cannot edit org-scoped connector."""
        user = MagicMock()
        user.id = 99
        user.roles = [ROLE_ALLOWED]
        result = await checker.can_edit_connector(user, org_connector)

        assert result.allowed is False
        assert "admin" in result.reason

    @pytest.mark.asyncio
    async def test_allowed_user_cannot_edit_org_connector(
        self, checker, allowed_user, org_connector
    ):
        """Test regular user cannot edit org-scoped connector."""
        result = await checker.can_edit_connector(allowed_user, org_connector)

        assert result.allowed is False


class TestPermissionCheckerConnectorCreate:
    """Tests for can_create_connector method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def checker(self, mock_db):
        """Create a PermissionChecker instance."""
        return PermissionChecker(mock_db)

    @pytest.fixture
    def admin_user(self):
        """Create an admin user."""
        user = MagicMock()
        user.id = 2
        user.roles = [ROLE_ALLOWED, ROLE_ADMIN]
        return user

    @pytest.fixture
    def allowed_user(self):
        """Create a regular allowed user."""
        user = MagicMock()
        user.id = 3
        user.roles = [ROLE_ALLOWED]
        return user

    # =========================================================================
    # User scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_allowed_user_can_create_user_connector(
        self, checker, allowed_user
    ):
        """Test any allowed user can create user-scoped connector."""
        result = await checker.can_create_connector(allowed_user, SCOPE_USER)

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_no_role_cannot_create_user_connector(self, checker):
        """Test user without roles cannot create connector."""
        user = MagicMock()
        user.id = 99
        user.roles = []

        result = await checker.can_create_connector(user, SCOPE_USER)

        assert result.allowed is False

    # =========================================================================
    # Team scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_admin_team_member_can_create_team_connector(
        self, checker, admin_user, mock_db
    ):
        """Test admin who is team member can create team-scoped connector."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[10, 20])
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.can_create_connector(admin_user, SCOPE_TEAM, team_id=10)

            assert result.allowed is True
            assert "admin and team member" in result.reason

    @pytest.mark.asyncio
    async def test_admin_non_member_cannot_create_team_connector(
        self, checker, admin_user, mock_db
    ):
        """Test admin who is not team member cannot create team-scoped connector."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[1, 2])  # Not team 10
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.can_create_connector(admin_user, SCOPE_TEAM, team_id=10)

            assert result.allowed is False
            assert "must be a member" in result.reason

    @pytest.mark.asyncio
    async def test_non_admin_cannot_create_team_connector(
        self, checker, allowed_user
    ):
        """Test non-admin cannot create team-scoped connector."""
        result = await checker.can_create_connector(allowed_user, SCOPE_TEAM, team_id=10)

        assert result.allowed is False
        assert "admin role required" in result.reason

    @pytest.mark.asyncio
    async def test_team_scope_requires_team_id(self, checker, admin_user):
        """Test team scope requires team_id parameter."""
        result = await checker.can_create_connector(admin_user, SCOPE_TEAM)

        assert result.allowed is False
        assert "team_id required" in result.reason

    # =========================================================================
    # Org scope
    # =========================================================================

    @pytest.mark.asyncio
    async def test_admin_can_create_org_connector(
        self, checker, admin_user
    ):
        """Test admin can create org-scoped connector."""
        result = await checker.can_create_connector(admin_user, SCOPE_ORG)

        assert result.allowed is True
        assert result.reason == "admin"

    @pytest.mark.asyncio
    async def test_allowed_user_cannot_create_org_connector(
        self, checker, allowed_user
    ):
        """Test non-admin cannot create org-scoped connector."""
        result = await checker.can_create_connector(allowed_user, SCOPE_ORG)

        assert result.allowed is False
        assert "admin required" in result.reason


class TestPermissionCheckerConnectorDelete:
    """Tests for can_delete_connector method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def checker(self, mock_db):
        """Create a PermissionChecker instance."""
        return PermissionChecker(mock_db)

    @pytest.mark.asyncio
    async def test_delete_uses_edit_permissions(self, checker):
        """Test can_delete_connector uses same rules as can_edit_connector."""
        user = MagicMock()
        user.id = 1
        user.roles = [ROLE_ALLOWED]

        connector = MagicMock()
        connector.user_id = 1
        connector.scope = SCOPE_USER

        # Owner can edit, so owner can delete
        result = await checker.can_delete_connector(user, connector)

        assert result.allowed is True


class TestPermissionCheckerDocuments:
    """Tests for document permission methods."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def checker(self, mock_db):
        """Create a PermissionChecker instance."""
        return PermissionChecker(mock_db)

    @pytest.fixture
    def allowed_user(self):
        """Create a regular allowed user."""
        user = MagicMock()
        user.id = 1
        user.roles = [ROLE_ALLOWED]
        return user

    @pytest.fixture
    def user_connector(self, allowed_user):
        """Create a user-scoped connector."""
        connector = MagicMock()
        connector.user_id = allowed_user.id
        connector.scope = SCOPE_USER
        return connector

    @pytest.mark.asyncio
    async def test_can_view_document_inherits_from_connector(
        self, checker, allowed_user, user_connector
    ):
        """Test document view permission inherits from connector."""
        result = await checker.can_view_document(allowed_user, user_connector)

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_can_edit_document_inherits_from_connector(
        self, checker, allowed_user, user_connector
    ):
        """Test document edit permission inherits from connector."""
        result = await checker.can_edit_document(allowed_user, user_connector)

        assert result.allowed is True


class TestPermissionCheckerQueryHelpers:
    """Tests for query helper methods."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def checker(self, mock_db):
        """Create a PermissionChecker instance."""
        return PermissionChecker(mock_db)

    @pytest.fixture
    def allowed_user(self):
        """Create a regular allowed user."""
        user = MagicMock()
        user.id = 1
        user.roles = [ROLE_ALLOWED]
        return user

    @pytest.fixture
    def admin_user(self):
        """Create an admin user."""
        user = MagicMock()
        user.id = 2
        user.roles = [ROLE_ALLOWED, ROLE_ADMIN]
        return user

    # =========================================================================
    # get_search_collections tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_search_collections_includes_user_collection(
        self, checker, allowed_user, mock_db
    ):
        """Test search collections include user's personal collection."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[])
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.get_search_collections(allowed_user)

            assert f"user_{allowed_user.id}" in result

    @pytest.mark.asyncio
    async def test_get_search_collections_includes_team_collections(
        self, checker, allowed_user, mock_db
    ):
        """Test search collections include team collections."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[10, 20])
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.get_search_collections(allowed_user)

            assert "team_10" in result
            assert "team_20" in result

    @pytest.mark.asyncio
    async def test_get_search_collections_includes_org_collection(
        self, checker, allowed_user, mock_db
    ):
        """Test search collections include org collection."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[])
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            result = await checker.get_search_collections(allowed_user)

            assert "org_default" in result

    # =========================================================================
    # get_accessible_connector_ids tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_admin_gets_all_connectors(
        self, checker, admin_user, mock_db
    ):
        """Test admin can access all connectors."""
        mock_result = MagicMock()
        mock_result.all.return_value = [(1,), (2,), (3,)]
        mock_db.execute.return_value = mock_result

        result = await checker.get_accessible_connector_ids(admin_user)

        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_regular_user_gets_filtered_connectors(
        self, checker, allowed_user, mock_db
    ):
        """Test regular user gets filtered connector list."""
        with pytest.MonkeyPatch.context() as mp:
            mock_crud = MagicMock()
            mock_crud.get_team_ids_for_user = AsyncMock(return_value=[10])
            mp.setattr("api.logic.permissions.team_crud", mock_crud)

            mock_result = MagicMock()
            mock_result.all.return_value = [(1,), (5,)]
            mock_db.execute.return_value = mock_result

            result = await checker.get_accessible_connector_ids(allowed_user)

            assert result == [1, 5]

    # =========================================================================
    # get_connector_query_filters tests
    # =========================================================================

    def test_get_connector_query_filters_returns_filters(
        self, checker, allowed_user
    ):
        """Test get_connector_query_filters returns filter list."""
        team_ids = [10, 20]

        result = checker.get_connector_query_filters(allowed_user, team_ids)

        assert len(result) == 1  # Single OR clause
