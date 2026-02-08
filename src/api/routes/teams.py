"""Team management endpoints."""

from fastapi import APIRouter, status

from api.dependencies import CurrentUser, DbSession
from api.logic.team_service import TeamService
from echomind_lib.models.public import (
    AddTeamMemberRequest,
    CreateTeamRequest,
    GetTeamResponse,
    ListTeamsResponse,
    ListUserTeamsResponse,
    RemoveTeamMemberRequest,
    Team,
    TeamMemberWithUser,
    UpdateTeamMemberRoleRequest,
    UpdateTeamRequest,
)

router = APIRouter()


@router.get("", response_model=ListTeamsResponse)
async def list_teams(
    user: CurrentUser,
    db: DbSession,
    page: int = 1,
    limit: int = 20,
    include_member_count: bool = False,
) -> ListTeamsResponse:
    """
    List teams accessible to the current user.

    Admins see all teams, regular users see only teams they belong to.

    Args:
        user: The authenticated user.
        db: Database session.
        page: Page number for pagination (1-indexed).
        limit: Number of items per page.
        include_member_count: Whether to include member counts.

    Returns:
        ListTeamsResponse: Paginated list of teams.
    """
    service = TeamService(db)
    return await service.list_teams(
        user_id=user.id,
        user_roles=user.roles,
        page=page,
        limit=limit,
        include_member_count=include_member_count,
    )


@router.get("/me", response_model=ListUserTeamsResponse)
async def get_my_teams(
    user: CurrentUser,
    db: DbSession,
    page: int = 1,
    limit: int = 20,
) -> ListUserTeamsResponse:
    """
    Get teams the current user belongs to.

    Args:
        user: The authenticated user.
        db: Database session.
        page: Page number for pagination (1-indexed).
        limit: Number of items per page.

    Returns:
        ListUserTeamsResponse: User's teams with pagination.
    """
    service = TeamService(db)
    return await service.get_my_teams(
        user_id=user.id,
        page=page,
        limit=limit,
    )


@router.post("", response_model=Team, status_code=status.HTTP_201_CREATED)
async def create_team(
    data: CreateTeamRequest,
    user: CurrentUser,
    db: DbSession,
) -> Team:
    """
    Create a new team.

    Requires admin role.

    Args:
        data: The team creation data.
        user: The authenticated user.
        db: Database session.

    Returns:
        Team: The created team.

    Raises:
        HTTPException: 403 if user lacks admin role.
        HTTPException: 409 if team name already exists.
    """
    service = TeamService(db)
    return await service.create_team(
        name=data.name or "",
        description=data.description or "",
        leader_id=data.leader_id if data.leader_id else None,
        created_by_user_id=user.id,
        user_roles=user.roles,
    )


@router.get("/{team_id}", response_model=GetTeamResponse)
async def get_team(
    team_id: int,
    user: CurrentUser,
    db: DbSession,
) -> GetTeamResponse:
    """
    Get a team by ID with its members.

    Args:
        team_id: The ID of the team to retrieve.
        user: The authenticated user.
        db: Database session.

    Returns:
        GetTeamResponse: Team details with members.

    Raises:
        HTTPException: 404 if team not found.
        HTTPException: 403 if user lacks access.
    """
    service = TeamService(db)
    return await service.get_team(
        team_id=team_id,
        user_id=user.id,
        user_roles=user.roles,
    )


@router.put("/{team_id}", response_model=Team)
async def update_team(
    team_id: int,
    data: UpdateTeamRequest,
    user: CurrentUser,
    db: DbSession,
) -> Team:
    """
    Update a team.

    Requires team lead role or admin privileges.

    Args:
        team_id: The ID of the team to update.
        data: The fields to update.
        user: The authenticated user.
        db: Database session.

    Returns:
        Team: The updated team.

    Raises:
        HTTPException: 404 if team not found.
        HTTPException: 403 if user lacks required role.
        HTTPException: 409 if new name already exists.
    """
    service = TeamService(db)
    return await service.update_team(
        team_id=team_id,
        name=data.name if data.name else None,
        description=data.description if data.description else None,
        leader_id=data.leader_id if data.leader_id else None,
        updated_by_user_id=user.id,
        user_roles=user.roles,
    )


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: int,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Delete a team (soft delete).

    Requires team lead role or admin privileges.

    Args:
        team_id: The ID of the team to delete.
        user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if team not found.
        HTTPException: 403 if user lacks required role.
    """
    service = TeamService(db)
    await service.delete_team(
        team_id=team_id,
        deleted_by_user_id=user.id,
        user_roles=user.roles,
    )


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberWithUser,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_member(
    team_id: int,
    data: AddTeamMemberRequest,
    user: CurrentUser,
    db: DbSession,
) -> TeamMemberWithUser:
    """
    Add a member to a team.

    Requires team lead role or admin privileges.

    Args:
        team_id: The ID of the team.
        data: The member to add.
        user: The authenticated user.
        db: Database session.

    Returns:
        TeamMemberWithUser: The added member details.

    Raises:
        HTTPException: 404 if team or user not found.
        HTTPException: 403 if user lacks required role.
        HTTPException: 409 if user is already a member.
    """
    service = TeamService(db)
    return await service.add_member(
        team_id=team_id,
        user_id=data.user_id or 0,
        role=data.role,
        added_by_user_id=user.id,
        user_roles=user.roles,
    )


@router.delete(
    "/{team_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_team_member(
    team_id: int,
    member_user_id: int,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Remove a member from a team.

    Requires team lead role or admin privileges.
    Cannot remove the team leader.

    Args:
        team_id: The ID of the team.
        member_user_id: The ID of the user to remove.
        user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if team or membership not found.
        HTTPException: 403 if user lacks required role or trying to remove leader.
    """
    service = TeamService(db)
    await service.remove_member(
        team_id=team_id,
        user_id=member_user_id,
        removed_by_user_id=user.id,
        user_roles=user.roles,
    )


@router.put(
    "/{team_id}/members/{member_user_id}/role",
    response_model=TeamMemberWithUser,
)
async def update_team_member_role(
    team_id: int,
    member_user_id: int,
    data: UpdateTeamMemberRoleRequest,
    user: CurrentUser,
    db: DbSession,
) -> TeamMemberWithUser:
    """
    Update a team member's role.

    Requires team lead role or admin privileges.

    Args:
        team_id: The ID of the team.
        member_user_id: The ID of the user whose role to update.
        data: The role update data.
        user: The authenticated user.
        db: Database session.

    Returns:
        TeamMemberWithUser: The updated member details.

    Raises:
        HTTPException: 404 if team or membership not found.
        HTTPException: 403 if user lacks required role.
    """
    service = TeamService(db)
    return await service.update_member_role(
        team_id=team_id,
        user_id=member_user_id,
        role=data.role,
        updated_by_user_id=user.id,
        user_roles=user.roles,
    )
