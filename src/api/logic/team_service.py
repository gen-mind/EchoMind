"""
Team business logic service.

Handles all team-related business operations, keeping routes thin.
Supports RBAC where:
- echomind-allowed: Can view teams they belong to
- echomind-admins: Full access to all teams
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.logic.exceptions import DuplicateError, ForbiddenError, NotFoundError
from echomind_lib.db.crud import team_crud
from echomind_lib.db.models import Team as TeamORM
from echomind_lib.db.models import TeamMember as TeamMemberORM
from echomind_lib.db.models import User as UserORM
from echomind_lib.models.public import (
    GetTeamResponse,
    ListTeamsResponse,
    ListUserTeamsResponse,
    Team,
    TeamMemberRole,
    TeamMemberWithUser,
)

# RBAC role names
ROLE_ALLOWED = "echomind-allowed"
ROLE_ADMIN = "echomind-admins"


def _role_str_to_enum(role: str) -> TeamMemberRole:
    """
    Convert database role string to TeamMemberRole enum.

    Args:
        role: Role string from database ("member" or "lead").

    Returns:
        TeamMemberRole enum value.
    """
    if role == "lead":
        return TeamMemberRole.TEAM_MEMBER_ROLE_LEAD
    return TeamMemberRole.TEAM_MEMBER_ROLE_MEMBER


def _role_enum_to_str(role: TeamMemberRole) -> str:
    """
    Convert TeamMemberRole enum to database role string.

    Args:
        role: TeamMemberRole enum value.

    Returns:
        Role string for database ("member" or "lead").
    """
    if role == TeamMemberRole.TEAM_MEMBER_ROLE_LEAD:
        return "lead"
    return "member"


def _team_orm_to_model(team: TeamORM, member_count: int | None = None) -> Team:
    """
    Convert Team ORM to Pydantic model.

    Args:
        team: Team ORM instance.
        member_count: Optional member count (if computed separately).

    Returns:
        Team Pydantic model.
    """
    return Team(
        id=team.id,
        name=team.name,
        description=team.description or "",
        leader_id=team.leader_id,
        created_by=team.created_by,
        member_count=member_count or len(team.members) if team.members else 0,
        creation_date=team.creation_date,
        last_update=team.last_update,
    )


def _member_orm_to_model(member: TeamMemberORM) -> TeamMemberWithUser:
    """
    Convert TeamMember ORM to TeamMemberWithUser Pydantic model.

    Args:
        member: TeamMember ORM instance with user relationship loaded.

    Returns:
        TeamMemberWithUser Pydantic model.
    """
    user = member.user
    return TeamMemberWithUser(
        user_id=user.id,
        user_name=user.user_name,
        email=user.email,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        role=_role_str_to_enum(member.role),
        added_at=member.added_at,
    )


class TeamService:
    """Service for team-related business logic."""

    def __init__(self, db: AsyncSession):
        """
        Initialize TeamService.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db

    def _is_admin(self, user_roles: list[str]) -> bool:
        """
        Check if user has admin privileges.

        Args:
            user_roles: List of user's roles.

        Returns:
            True if user is admin.
        """
        return ROLE_ADMIN in user_roles

    async def _check_team_access(
        self,
        team_id: int,
        user_id: int,
        user_roles: list[str],
        *,
        require_lead: bool = False,
    ) -> TeamORM:
        """
        Check if user has access to a team.

        Args:
            team_id: Team ID to check access for.
            user_id: User ID requesting access.
            user_roles: User's roles for RBAC.
            require_lead: If True, requires lead role or admin privileges.

        Returns:
            Team ORM if access granted.

        Raises:
            NotFoundError: If team doesn't exist.
            ForbiddenError: If access denied.
        """
        team = await team_crud.get_by_id(self.db, team_id)
        if not team or team.deleted_date:
            raise NotFoundError("Team", team_id)

        # Admins have full access
        if self._is_admin(user_roles):
            if require_lead:
                # Admins need to be lead to modify
                is_lead = await team_crud.is_lead(self.db, team_id, user_id)
                if not is_lead and team.leader_id != user_id:
                    raise ForbiddenError("Team lead role required")
            return team

        # Regular users must be team members
        is_member = await team_crud.is_member(self.db, team_id, user_id)
        if not is_member:
            raise ForbiddenError("Not a member of this team")

        if require_lead:
            is_lead = await team_crud.is_lead(self.db, team_id, user_id)
            if not is_lead and team.leader_id != user_id:
                raise ForbiddenError("Team lead role required")

        return team

    async def list_teams(
        self,
        user_id: int,
        user_roles: list[str],
        page: int = 1,
        limit: int = 20,
        include_member_count: bool = False,
    ) -> ListTeamsResponse:
        """
        List teams accessible to the user.

        Admins see all teams, regular users see their teams only.

        Args:
            user_id: Requesting user's ID.
            user_roles: User's roles for RBAC.
            page: Page number (1-indexed).
            limit: Items per page.
            include_member_count: Whether to include member counts.

        Returns:
            ListTeamsResponse with paginated teams.
        """
        offset = (page - 1) * limit

        if self._is_admin(user_roles):
            # Admins see all non-deleted teams
            query = (
                select(TeamORM)
                .where(TeamORM.deleted_date.is_(None))
                .order_by(TeamORM.name)
                .offset(offset)
                .limit(limit)
            )
            result = await self.db.execute(query)
            db_teams = result.scalars().all()
        else:
            # Regular users see only their teams
            db_teams = await team_crud.get_by_user(
                self.db, user_id, offset=offset, limit=limit
            )

        teams = []
        for team in db_teams:
            member_count = None
            if include_member_count:
                member_count = await team_crud.count_members(self.db, team.id)
            teams.append(_team_orm_to_model(team, member_count))

        return ListTeamsResponse(teams=teams)

    async def get_my_teams(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 20,
    ) -> ListUserTeamsResponse:
        """
        Get teams the current user belongs to.

        Args:
            user_id: User's ID.
            page: Page number (1-indexed).
            limit: Items per page.

        Returns:
            ListUserTeamsResponse with user's teams.
        """
        offset = (page - 1) * limit
        db_teams = await team_crud.get_by_user(
            self.db, user_id, offset=offset, limit=limit
        )

        teams = []
        for team in db_teams:
            member_count = await team_crud.count_members(self.db, team.id)
            teams.append(_team_orm_to_model(team, member_count))

        return ListUserTeamsResponse(teams=teams)

    async def get_team(
        self,
        team_id: int,
        user_id: int,
        user_roles: list[str],
    ) -> GetTeamResponse:
        """
        Get team details with members.

        Args:
            team_id: Team ID.
            user_id: Requesting user's ID.
            user_roles: User's roles for RBAC.

        Returns:
            GetTeamResponse with team and members.

        Raises:
            NotFoundError: If team doesn't exist.
            ForbiddenError: If user lacks access.
        """
        team = await self._check_team_access(team_id, user_id, user_roles)
        members = await team_crud.get_members(self.db, team_id)
        member_count = len(members)

        team_model = _team_orm_to_model(team, member_count)
        member_models = [_member_orm_to_model(m) for m in members]

        return GetTeamResponse(team=team_model, members=member_models)

    async def create_team(
        self,
        name: str,
        description: str,
        leader_id: int | None,
        created_by_user_id: int,
        user_roles: list[str],
    ) -> Team:
        """
        Create a new team.

        Only admins can create teams.

        Args:
            name: Team name (unique).
            description: Team description.
            leader_id: Optional leader user ID.
            created_by_user_id: ID of user creating the team.
            user_roles: User's roles for RBAC.

        Returns:
            Created Team model.

        Raises:
            ForbiddenError: If user lacks admin privileges.
            DuplicateError: If team name already exists.
        """
        if not self._is_admin(user_roles):
            raise ForbiddenError("Admin role required to create teams")

        # Check for duplicate name
        existing = await team_crud.get_by_name(self.db, name)
        if existing:
            raise DuplicateError("Team", "name")

        # Verify leader exists if specified
        if leader_id:
            leader_result = await self.db.execute(
                select(UserORM).where(UserORM.id == leader_id)
            )
            if not leader_result.scalar_one_or_none():
                raise NotFoundError("User", leader_id)

        team = await team_crud.create_with_founder(
            self.db,
            name=name,
            description=description,
            created_by=created_by_user_id,
            leader_id=leader_id,
        )

        member_count = await team_crud.count_members(self.db, team.id)
        return _team_orm_to_model(team, member_count)

    async def update_team(
        self,
        team_id: int,
        name: str | None,
        description: str | None,
        leader_id: int | None,
        updated_by_user_id: int,
        user_roles: list[str],
    ) -> Team:
        """
        Update a team.

        Requires team lead role or admin privileges.

        Args:
            team_id: Team ID to update.
            name: New team name (optional).
            description: New description (optional).
            leader_id: New leader ID (optional).
            updated_by_user_id: ID of user making the update.
            user_roles: User's roles for RBAC.

        Returns:
            Updated Team model.

        Raises:
            NotFoundError: If team doesn't exist.
            ForbiddenError: If user lacks required role.
            DuplicateError: If new name already exists.
        """
        team = await self._check_team_access(
            team_id, updated_by_user_id, user_roles, require_lead=True
        )

        if name and name != team.name:
            existing = await team_crud.get_by_name(self.db, name)
            if existing and existing.id != team_id:
                raise DuplicateError("Team", "name")
            team.name = name

        if description is not None:
            team.description = description

        if leader_id is not None:
            # Verify new leader exists
            leader_result = await self.db.execute(
                select(UserORM).where(UserORM.id == leader_id)
            )
            if not leader_result.scalar_one_or_none():
                raise NotFoundError("User", leader_id)
            team.leader_id = leader_id

        team.last_update = datetime.now(timezone.utc)
        team.user_id_last_update = updated_by_user_id

        await self.db.flush()
        await self.db.refresh(team)

        member_count = await team_crud.count_members(self.db, team.id)
        return _team_orm_to_model(team, member_count)

    async def delete_team(
        self,
        team_id: int,
        deleted_by_user_id: int,
        user_roles: list[str],
    ) -> None:
        """
        Soft delete a team.

        Only admins or the team leader can delete teams.

        Args:
            team_id: Team ID to delete.
            deleted_by_user_id: ID of user deleting the team.
            user_roles: User's roles for RBAC.

        Raises:
            NotFoundError: If team doesn't exist.
            ForbiddenError: If user lacks required role.
        """
        team = await self._check_team_access(
            team_id, deleted_by_user_id, user_roles, require_lead=True
        )

        team.deleted_date = datetime.now(timezone.utc)
        team.user_id_last_update = deleted_by_user_id

    async def add_member(
        self,
        team_id: int,
        user_id: int,
        role: TeamMemberRole,
        added_by_user_id: int,
        user_roles: list[str],
    ) -> TeamMemberWithUser:
        """
        Add a member to a team.

        Requires team lead role or admin privileges.

        Args:
            team_id: Team ID.
            user_id: User ID to add.
            role: Member role (MEMBER or LEAD).
            added_by_user_id: ID of user adding the member.
            user_roles: User's roles for RBAC.

        Returns:
            TeamMemberWithUser with added member details.

        Raises:
            NotFoundError: If team or user doesn't exist.
            ForbiddenError: If user lacks required role.
            DuplicateError: If user is already a member.
        """
        await self._check_team_access(
            team_id, added_by_user_id, user_roles, require_lead=True
        )

        # Verify user to add exists
        user_result = await self.db.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        user_to_add = user_result.scalar_one_or_none()
        if not user_to_add:
            raise NotFoundError("User", user_id)

        # Check if already a member
        existing = await team_crud.get_member(self.db, team_id, user_id)
        if existing:
            raise DuplicateError("TeamMember", "user_id")

        role_str = _role_enum_to_str(role)
        member = await team_crud.add_member(
            self.db,
            team_id=team_id,
            user_id=user_id,
            role=role_str,
            added_by=added_by_user_id,
        )

        # Reload with user relationship
        await self.db.refresh(member, ["user"])
        return _member_orm_to_model(member)

    async def remove_member(
        self,
        team_id: int,
        user_id: int,
        removed_by_user_id: int,
        user_roles: list[str],
    ) -> None:
        """
        Remove a member from a team.

        Requires team lead role or admin privileges.
        Cannot remove the team leader.

        Args:
            team_id: Team ID.
            user_id: User ID to remove.
            removed_by_user_id: ID of user removing the member.
            user_roles: User's roles for RBAC.

        Raises:
            NotFoundError: If team or membership doesn't exist.
            ForbiddenError: If user lacks required role or trying to remove leader.
        """
        team = await self._check_team_access(
            team_id, removed_by_user_id, user_roles, require_lead=True
        )

        # Cannot remove the team leader
        if team.leader_id == user_id:
            raise ForbiddenError("Cannot remove the team leader")

        removed = await team_crud.remove_member(self.db, team_id, user_id)
        if not removed:
            raise NotFoundError("TeamMember", f"team_id={team_id}, user_id={user_id}")

    async def update_member_role(
        self,
        team_id: int,
        user_id: int,
        role: TeamMemberRole,
        updated_by_user_id: int,
        user_roles: list[str],
    ) -> TeamMemberWithUser:
        """
        Update a member's role.

        Requires team lead role or admin privileges.

        Args:
            team_id: Team ID.
            user_id: User ID whose role to update.
            role: New role.
            updated_by_user_id: ID of user making the update.
            user_roles: User's roles for RBAC.

        Returns:
            Updated TeamMemberWithUser.

        Raises:
            NotFoundError: If team or membership doesn't exist.
            ForbiddenError: If user lacks required role.
        """
        await self._check_team_access(
            team_id, updated_by_user_id, user_roles, require_lead=True
        )

        role_str = _role_enum_to_str(role)
        member = await team_crud.update_member_role(
            self.db, team_id, user_id, role_str
        )

        if not member:
            raise NotFoundError("TeamMember", f"team_id={team_id}, user_id={user_id}")

        # Reload with user relationship
        await self.db.refresh(member, ["user"])
        return _member_orm_to_model(member)
