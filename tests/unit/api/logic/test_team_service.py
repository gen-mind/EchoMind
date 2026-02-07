"""
Unit tests for TeamService.

Tests team CRUD operations and RBAC enforcement.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.logic.exceptions import DuplicateError, ForbiddenError, NotFoundError
from api.logic.team_service import (
    ROLE_ADMIN,
    ROLE_ALLOWED,
    TeamService,
    _role_enum_to_str,
    _role_str_to_enum,
)
from echomind_lib.models.public import TeamMemberRole


class TestRoleConversions:
    """Tests for role conversion helpers."""

    def test_role_str_to_enum_member(self) -> None:
        """Test converting 'member' string to enum."""
        result = _role_str_to_enum("member")
        assert result == TeamMemberRole.TEAM_MEMBER_ROLE_MEMBER

    def test_role_str_to_enum_lead(self) -> None:
        """Test converting 'lead' string to enum."""
        result = _role_str_to_enum("lead")
        assert result == TeamMemberRole.TEAM_MEMBER_ROLE_LEAD

    def test_role_str_to_enum_unknown(self) -> None:
        """Test converting unknown string defaults to member."""
        result = _role_str_to_enum("unknown")
        assert result == TeamMemberRole.TEAM_MEMBER_ROLE_MEMBER

    def test_role_enum_to_str_member(self) -> None:
        """Test converting member enum to string."""
        result = _role_enum_to_str(TeamMemberRole.TEAM_MEMBER_ROLE_MEMBER)
        assert result == "member"

    def test_role_enum_to_str_lead(self) -> None:
        """Test converting lead enum to string."""
        result = _role_enum_to_str(TeamMemberRole.TEAM_MEMBER_ROLE_LEAD)
        assert result == "lead"

    def test_role_enum_to_str_unspecified(self) -> None:
        """Test converting unspecified enum defaults to member."""
        result = _role_enum_to_str(TeamMemberRole.TEAM_MEMBER_ROLE_UNSPECIFIED)
        assert result == "member"


class TestTeamService:
    """Tests for TeamService CRUD operations."""

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
    def mock_team(self):
        """Create a mock team ORM object."""
        team = MagicMock()
        team.id = 1
        team.name = "Test Team"
        team.description = "A test team"
        team.leader_id = 10
        team.created_by = 10
        team.creation_date = datetime.now(timezone.utc)
        team.last_update = None
        team.deleted_date = None
        team.members = []
        return team

    @pytest.fixture
    def mock_user(self):
        """Create a mock user ORM object."""
        user = MagicMock()
        user.id = 20
        user.user_name = "testuser"
        user.email = "test@example.com"
        user.first_name = "Test"
        user.last_name = "User"
        return user

    @pytest.fixture
    def mock_team_member(self, mock_user):
        """Create a mock team member ORM object."""
        member = MagicMock()
        member.team_id = 1
        member.user_id = mock_user.id
        member.role = "member"
        member.added_at = datetime.now(timezone.utc)
        member.added_by = 10
        member.user = mock_user
        return member

    @pytest.fixture
    def service(self, mock_db):
        """Create a TeamService with mocked database."""
        return TeamService(mock_db)

    # =========================================================================
    # RBAC helper tests
    # =========================================================================

    def test_is_admin_with_admin_role(self, service) -> None:
        """Test admin detection with admin role."""
        assert service._is_admin([ROLE_ADMIN])
        assert service._is_admin([ROLE_ALLOWED, ROLE_ADMIN])

    def test_is_admin_without_admin_role(self, service) -> None:
        """Test admin detection without admin role."""
        assert not service._is_admin([ROLE_ALLOWED])
        assert not service._is_admin([])

    # =========================================================================
    # _check_team_access tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_check_team_access_admin_full_access(self, service, mock_team) -> None:
        """Test admins have full access without require_lead."""
        with patch.object(service, "db") as mock_db:
            with patch("api.logic.team_service.team_crud") as mock_crud:
                mock_crud.get_by_id = AsyncMock(return_value=mock_team)

                result = await service._check_team_access(
                    1, 99, [ROLE_ADMIN], require_lead=False
                )

                assert result == mock_team

    @pytest.mark.asyncio
    async def test_check_team_access_not_found(self, service) -> None:
        """Test access check raises NotFoundError for missing team."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(NotFoundError):
                await service._check_team_access(999, 1, [ROLE_ALLOWED])

    @pytest.mark.asyncio
    async def test_check_team_access_deleted_team(self, service, mock_team) -> None:
        """Test access check raises NotFoundError for deleted team."""
        mock_team.deleted_date = datetime.now(timezone.utc)

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)

            with pytest.raises(NotFoundError):
                await service._check_team_access(1, 1, [ROLE_ALLOWED])

    @pytest.mark.asyncio
    async def test_check_team_access_non_member(self, service, mock_team) -> None:
        """Test access check raises ForbiddenError for non-members."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=False)

            with pytest.raises(ForbiddenError):
                await service._check_team_access(1, 99, [ROLE_ALLOWED])

    @pytest.mark.asyncio
    async def test_check_team_access_member_require_lead(
        self, service, mock_team
    ) -> None:
        """Test member without lead role fails require_lead check."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=False)

            with pytest.raises(ForbiddenError):
                await service._check_team_access(
                    1, 20, [ROLE_ALLOWED], require_lead=True
                )

    @pytest.mark.asyncio
    async def test_check_team_access_leader_require_lead(
        self, service, mock_team
    ) -> None:
        """Test team leader passes require_lead check."""
        mock_team.leader_id = 20  # User is the leader

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=False)

            result = await service._check_team_access(
                1, 20, [ROLE_ALLOWED], require_lead=True
            )

            assert result == mock_team

    # =========================================================================
    # list_teams tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_teams_admin_sees_all(self, service, mock_db, mock_team) -> None:
        """Test admins can see all teams."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_team]
        mock_db.execute.return_value = mock_result

        result = await service.list_teams(
            user_id=1,
            user_roles=[ROLE_ADMIN],
            page=1,
            limit=20,
        )

        assert len(result.teams) == 1
        assert result.teams[0].name == "Test Team"

    @pytest.mark.asyncio
    async def test_list_teams_user_sees_own(self, service, mock_team) -> None:
        """Test regular users only see their teams."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_user = AsyncMock(return_value=[mock_team])
            mock_crud.count_members = AsyncMock(return_value=5)

            result = await service.list_teams(
                user_id=20,
                user_roles=[ROLE_ALLOWED],
                page=1,
                limit=20,
                include_member_count=True,
            )

            assert len(result.teams) == 1
            # When include_member_count=True, member_count comes from count_members
            mock_crud.count_members.assert_called_once()
            mock_crud.get_by_user.assert_called_once()

    # =========================================================================
    # get_my_teams tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_my_teams(self, service, mock_team) -> None:
        """Test getting user's own teams."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_user = AsyncMock(return_value=[mock_team])
            mock_crud.count_members = AsyncMock(return_value=3)

            result = await service.get_my_teams(user_id=20, page=1, limit=20)

            assert len(result.teams) == 1
            mock_crud.get_by_user.assert_called_with(
                service.db, 20, offset=0, limit=20
            )

    # =========================================================================
    # get_team tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_team_success(
        self, service, mock_team, mock_team_member
    ) -> None:
        """Test getting a team with members."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.get_members = AsyncMock(return_value=[mock_team_member])

            result = await service.get_team(1, 20, [ROLE_ALLOWED])

            assert result.team.name == "Test Team"
            assert len(result.members) == 1
            assert result.members[0].user_name == "testuser"

    # =========================================================================
    # create_team tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_team_success(self, service, mock_db, mock_team) -> None:
        """Test creating a team successfully."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_name = AsyncMock(return_value=None)
            mock_crud.create_with_founder = AsyncMock(return_value=mock_team)
            mock_crud.count_members = AsyncMock(return_value=1)

            result = await service.create_team(
                name="New Team",
                description="A new team",
                leader_id=None,
                created_by_user_id=10,
                user_roles=[ROLE_ADMIN],
            )

            assert result.name == "Test Team"
            mock_crud.create_with_founder.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_team_forbidden_for_regular_user(self, service) -> None:
        """Test creating team forbidden for non-admin users."""
        with pytest.raises(ForbiddenError):
            await service.create_team(
                name="New Team",
                description="A new team",
                leader_id=None,
                created_by_user_id=20,
                user_roles=[ROLE_ALLOWED],
            )

    @pytest.mark.asyncio
    async def test_create_team_duplicate_name(self, service, mock_team) -> None:
        """Test creating team with duplicate name fails."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_name = AsyncMock(return_value=mock_team)

            with pytest.raises(DuplicateError):
                await service.create_team(
                    name="Test Team",  # Already exists
                    description="A new team",
                    leader_id=None,
                    created_by_user_id=10,
                    user_roles=[ROLE_ADMIN],
                )

    @pytest.mark.asyncio
    async def test_create_team_with_leader(self, service, mock_db, mock_team, mock_user) -> None:
        """Test creating team with specified leader."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_name = AsyncMock(return_value=None)
            mock_crud.create_with_founder = AsyncMock(return_value=mock_team)
            mock_crud.count_members = AsyncMock(return_value=2)

            result = await service.create_team(
                name="New Team",
                description="A new team",
                leader_id=mock_user.id,
                created_by_user_id=10,
                user_roles=[ROLE_ADMIN],
            )

            mock_crud.create_with_founder.assert_called_once()
            call_kwargs = mock_crud.create_with_founder.call_args[1]
            assert call_kwargs["leader_id"] == mock_user.id

    @pytest.mark.asyncio
    async def test_create_team_invalid_leader(self, service, mock_db) -> None:
        """Test creating team with non-existent leader fails."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_name = AsyncMock(return_value=None)

            with pytest.raises(NotFoundError):
                await service.create_team(
                    name="New Team",
                    description="A new team",
                    leader_id=999,  # Non-existent user
                    created_by_user_id=10,
                    user_roles=[ROLE_ADMIN],
                )

    # =========================================================================
    # update_team tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_update_team_success(self, service, mock_db, mock_team) -> None:
        """Test updating a team successfully."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)
            mock_crud.get_by_name = AsyncMock(return_value=None)
            mock_crud.count_members = AsyncMock(return_value=3)

            result = await service.update_team(
                team_id=1,
                name="Updated Name",
                description="Updated description",
                leader_id=None,
                updated_by_user_id=10,
                user_roles=[ROLE_ADMIN],
            )

            assert mock_team.name == "Updated Name"
            assert mock_team.description == "Updated description"

    @pytest.mark.asyncio
    async def test_update_team_duplicate_name(self, service, mock_team) -> None:
        """Test updating team to duplicate name fails."""
        other_team = MagicMock()
        other_team.id = 2
        other_team.name = "Other Team"

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)
            mock_crud.get_by_name = AsyncMock(return_value=other_team)

            with pytest.raises(DuplicateError):
                await service.update_team(
                    team_id=1,
                    name="Other Team",  # Name of different team
                    description=None,
                    leader_id=None,
                    updated_by_user_id=10,
                    user_roles=[ROLE_ADMIN],
                )

    # =========================================================================
    # delete_team tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_team_success(self, service, mock_team) -> None:
        """Test soft deleting a team."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)

            await service.delete_team(1, 10, [ROLE_ADMIN])

            assert mock_team.deleted_date is not None
            assert mock_team.user_id_last_update == 10

    # =========================================================================
    # add_member tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_add_member_success(
        self, service, mock_db, mock_team, mock_user, mock_team_member
    ) -> None:
        """Test adding a member to a team."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)
            mock_crud.get_member = AsyncMock(return_value=None)  # Not already member
            mock_crud.add_member = AsyncMock(return_value=mock_team_member)

            result = await service.add_member(
                team_id=1,
                user_id=mock_user.id,
                role=TeamMemberRole.TEAM_MEMBER_ROLE_MEMBER,
                added_by_user_id=10,
                user_roles=[ROLE_ADMIN],
            )

            assert result.user_id == mock_user.id
            mock_crud.add_member.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_member_already_exists(
        self, service, mock_db, mock_team, mock_user, mock_team_member
    ) -> None:
        """Test adding existing member fails."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)
            mock_crud.get_member = AsyncMock(return_value=mock_team_member)  # Already member

            with pytest.raises(DuplicateError):
                await service.add_member(
                    team_id=1,
                    user_id=mock_user.id,
                    role=TeamMemberRole.TEAM_MEMBER_ROLE_MEMBER,
                    added_by_user_id=10,
                    user_roles=[ROLE_ADMIN],
                )

    @pytest.mark.asyncio
    async def test_add_member_user_not_found(self, service, mock_db, mock_team) -> None:
        """Test adding non-existent user fails."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)

            with pytest.raises(NotFoundError):
                await service.add_member(
                    team_id=1,
                    user_id=999,  # Non-existent user
                    role=TeamMemberRole.TEAM_MEMBER_ROLE_MEMBER,
                    added_by_user_id=10,
                    user_roles=[ROLE_ADMIN],
                )

    # =========================================================================
    # remove_member tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_remove_member_success(self, service, mock_team) -> None:
        """Test removing a member from a team."""
        mock_team.leader_id = 10  # Different from user being removed

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)
            mock_crud.remove_member = AsyncMock(return_value=True)

            await service.remove_member(
                team_id=1,
                user_id=20,
                removed_by_user_id=10,
                user_roles=[ROLE_ADMIN],
            )

            mock_crud.remove_member.assert_called_once_with(service.db, 1, 20)

    @pytest.mark.asyncio
    async def test_remove_member_cannot_remove_leader(
        self, service, mock_team
    ) -> None:
        """Test cannot remove team leader."""
        mock_team.leader_id = 20  # Trying to remove the leader

        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)

            with pytest.raises(ForbiddenError):
                await service.remove_member(
                    team_id=1,
                    user_id=20,  # The leader
                    removed_by_user_id=10,
                    user_roles=[ROLE_ADMIN],
                )

    @pytest.mark.asyncio
    async def test_remove_member_not_found(self, service, mock_team) -> None:
        """Test removing non-existent member fails."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)
            mock_crud.remove_member = AsyncMock(return_value=False)

            with pytest.raises(NotFoundError):
                await service.remove_member(
                    team_id=1,
                    user_id=999,  # Not a member
                    removed_by_user_id=10,
                    user_roles=[ROLE_ADMIN],
                )

    # =========================================================================
    # update_member_role tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_update_member_role_success(
        self, service, mock_team, mock_team_member
    ) -> None:
        """Test updating a member's role."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)
            mock_crud.update_member_role = AsyncMock(return_value=mock_team_member)

            result = await service.update_member_role(
                team_id=1,
                user_id=20,
                role=TeamMemberRole.TEAM_MEMBER_ROLE_LEAD,
                updated_by_user_id=10,
                user_roles=[ROLE_ADMIN],
            )

            assert result.user_id == 20
            mock_crud.update_member_role.assert_called_once_with(
                service.db, 1, 20, "lead"
            )

    @pytest.mark.asyncio
    async def test_update_member_role_not_found(self, service, mock_team) -> None:
        """Test updating role for non-existent member fails."""
        with patch("api.logic.team_service.team_crud") as mock_crud:
            mock_crud.get_by_id = AsyncMock(return_value=mock_team)
            mock_crud.is_member = AsyncMock(return_value=True)
            mock_crud.is_lead = AsyncMock(return_value=True)
            mock_crud.update_member_role = AsyncMock(return_value=None)

            with pytest.raises(NotFoundError):
                await service.update_member_role(
                    team_id=1,
                    user_id=999,
                    role=TeamMemberRole.TEAM_MEMBER_ROLE_LEAD,
                    updated_by_user_id=10,
                    user_roles=[ROLE_ADMIN],
                )
