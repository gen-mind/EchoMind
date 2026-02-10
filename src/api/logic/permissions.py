"""
Permission checking utilities for RBAC enforcement.

This module provides centralized permission checking for all resources.
It implements the RBAC rules defined in docs/rbac.md.

Usage:
    from api.logic.permissions import PermissionChecker

    checker = PermissionChecker(db)
    if await checker.can_view_connector(user, connector):
        # User has access
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud import team_crud
from echomind_lib.db.models import Connector as ConnectorORM
from echomind_lib.db.models import Team as TeamORM

if TYPE_CHECKING:
    from echomind_lib.helpers.auth import TokenUser

logger = logging.getLogger(__name__)

# RBAC role names (Authentik groups)
ROLE_ALLOWED = "echomind-allowed"
ROLE_ADMIN = "echomind-admins"

# Connector scopes
SCOPE_USER = "user"
SCOPE_TEAM = "team"
SCOPE_GROUP = "group"  # Legacy alias for team
SCOPE_ORG = "org"


@dataclass
class AccessResult:
    """Result of an access check with reason."""

    allowed: bool
    reason: str

    def __bool__(self) -> bool:
        """Allow using AccessResult in boolean context."""
        return self.allowed


class PermissionChecker:
    """
    RBAC permission checking utilities.

    Provides methods to check user permissions for various resources
    based on their roles and team memberships.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize PermissionChecker.

        Args:
            db: Database session for querying team memberships.
        """
        self.db = db
        self._team_ids_cache: dict[int, list[int]] = {}
        self._team_lead_cache: dict[tuple[int, int], bool] = {}

    # =========================================================================
    # Role Helpers
    # =========================================================================

    def is_allowed(self, user: "TokenUser") -> bool:
        """
        Check if user has at least 'allowed' role.

        Args:
            user: The authenticated user.

        Returns:
            True if user has echomind-allowed or higher role.
        """
        return ROLE_ALLOWED in user.groups or ROLE_ADMIN in user.groups

    def is_admin(self, user: "TokenUser") -> bool:
        """
        Check if user has admin privileges.

        Args:
            user: The authenticated user.

        Returns:
            True if user has echomind-admins role.
        """
        return ROLE_ADMIN in user.groups

    # =========================================================================
    # Team Helpers
    # =========================================================================

    async def get_user_team_ids(self, user_id: int) -> list[int]:
        """
        Get list of team IDs a user belongs to.

        Results are cached per user for the lifetime of the checker instance.

        Args:
            user_id: User ID.

        Returns:
            List of team IDs.
        """
        if user_id in self._team_ids_cache:
            return self._team_ids_cache[user_id]

        team_ids = await team_crud.get_team_ids_for_user(self.db, user_id)
        self._team_ids_cache[user_id] = team_ids
        return team_ids

    async def is_team_member(self, user_id: int, team_id: int) -> bool:
        """
        Check if user is a member of a team.

        Args:
            user_id: User ID.
            team_id: Team ID.

        Returns:
            True if user is a member.
        """
        team_ids = await self.get_user_team_ids(user_id)
        return team_id in team_ids

    async def is_team_lead(self, user_id: int, team_id: int) -> bool:
        """
        Check if user is a lead of a team.

        Results are cached for the lifetime of the checker instance.

        Args:
            user_id: User ID.
            team_id: Team ID.

        Returns:
            True if user is a lead or the team leader.
        """
        cache_key = (user_id, team_id)
        if cache_key in self._team_lead_cache:
            return self._team_lead_cache[cache_key]

        # Check if user is team leader or has lead role
        result = await self.db.execute(
            select(TeamORM).where(TeamORM.id == team_id)
        )
        team = result.scalar_one_or_none()

        if not team:
            self._team_lead_cache[cache_key] = False
            return False

        # Team leader has full access
        if team.leader_id == user_id:
            self._team_lead_cache[cache_key] = True
            return True

        # Check if user has lead role in team
        is_lead = await team_crud.is_lead(self.db, team_id, user_id)
        self._team_lead_cache[cache_key] = is_lead
        return is_lead

    # =========================================================================
    # Connector Permissions
    # =========================================================================

    async def can_view_connector(
        self,
        user: "TokenUser",
        connector: ConnectorORM,
    ) -> AccessResult:
        """
        Check if user can view a connector.

        Rules:
        - Admin: Can view all connectors
        - User scope: Owner only
        - Team scope: Team members
        - Org scope: All allowed users

        Args:
            user: The authenticated user.
            connector: The connector to check.

        Returns:
            AccessResult with allowed status and reason.
        """
        # Admins can view everything
        if self.is_admin(user):
            return AccessResult(True, "admin")

        # Check by scope
        scope = connector.scope or SCOPE_USER

        if scope == SCOPE_USER:
            # User scope - owner only
            if connector.user_id == user.id:
                return AccessResult(True, "owner")
            return AccessResult(False, "not owner of user-scoped connector")

        if scope in (SCOPE_TEAM, SCOPE_GROUP):
            # Team scope - must be member
            if connector.team_id:
                if await self.is_team_member(user.id, connector.team_id):
                    return AccessResult(True, "team member")
                return AccessResult(False, "not a member of connector's team")
            # Fallback: check if user is owner (legacy data)
            if connector.user_id == user.id:
                return AccessResult(True, "owner (legacy team connector)")
            return AccessResult(False, "team connector without team_id")

        if scope == SCOPE_ORG:
            # Org scope - all allowed users can view
            if self.is_allowed(user):
                return AccessResult(True, "org scope visible to all")
            return AccessResult(False, "not an allowed user")

        # Unknown scope - deny
        return AccessResult(False, f"unknown scope: {scope}")

    async def can_edit_connector(
        self,
        user: "TokenUser",
        connector: ConnectorORM,
    ) -> AccessResult:
        """
        Check if user can edit a connector.

        Rules:
        - Admin: Can edit all connectors
        - User scope: Owner only
        - Team scope: Team leads and admins who are members
        - Org scope: Admin only

        Args:
            user: The authenticated user.
            connector: The connector to check.

        Returns:
            AccessResult with allowed status and reason.
        """
        # Admins can edit everything
        if self.is_admin(user):
            return AccessResult(True, "admin")

        scope = connector.scope or SCOPE_USER

        if scope == SCOPE_USER:
            # User scope - owner only
            if connector.user_id == user.id:
                return AccessResult(True, "owner")
            return AccessResult(False, "not owner of user-scoped connector")

        if scope in (SCOPE_TEAM, SCOPE_GROUP):
            # Team scope - team lead or admin who is member
            if connector.team_id:
                # Check if user is team lead
                if await self.is_team_lead(user.id, connector.team_id):
                    return AccessResult(True, "team lead")

                # Admins who are team members can also edit
                if self.is_admin(user):
                    if await self.is_team_member(user.id, connector.team_id):
                        return AccessResult(True, "admin team member")

                return AccessResult(False, "not a lead of connector's team")

            # Fallback for legacy data without team_id
            if connector.user_id == user.id:
                return AccessResult(True, "owner (legacy team connector)")
            return AccessResult(False, "team connector without team_id")

        if scope == SCOPE_ORG:
            # Org scope - admin only (already checked above)
            return AccessResult(False, "org connectors require admin")

        return AccessResult(False, f"unknown scope: {scope}")

    async def can_create_connector(
        self,
        user: "TokenUser",
        scope: str,
        team_id: int | None = None,
    ) -> AccessResult:
        """
        Check if user can create a connector with given scope.

        Rules:
        - User scope: All allowed users
        - Team scope: Admins who are team members
        - Org scope: Admin only

        Args:
            user: The authenticated user.
            scope: The desired connector scope.
            team_id: Team ID for team-scoped connectors.

        Returns:
            AccessResult with allowed status and reason.
        """
        if scope == SCOPE_USER:
            # Anyone can create personal connectors
            if self.is_allowed(user):
                return AccessResult(True, "allowed users can create personal connectors")
            return AccessResult(False, "not an allowed user")

        if scope in (SCOPE_TEAM, SCOPE_GROUP):
            # Must be admin and team member
            if not self.is_admin(user):
                return AccessResult(False, "admin role required for team connectors")

            if not team_id:
                return AccessResult(False, "team_id required for team scope")

            if await self.is_team_member(user.id, team_id):
                return AccessResult(True, "admin and team member")
            return AccessResult(False, "must be a member of the team")

        if scope == SCOPE_ORG:
            if self.is_admin(user):
                return AccessResult(True, "admin")
            return AccessResult(False, "admin required for org connectors")

        return AccessResult(False, f"unknown scope: {scope}")

    async def can_delete_connector(
        self,
        user: "TokenUser",
        connector: ConnectorORM,
    ) -> AccessResult:
        """
        Check if user can delete a connector.

        Same rules as can_edit_connector.

        Args:
            user: The authenticated user.
            connector: The connector to check.

        Returns:
            AccessResult with allowed status and reason.
        """
        return await self.can_edit_connector(user, connector)

    # =========================================================================
    # Document Permissions (Inherit from Connector)
    # =========================================================================

    async def can_view_document(
        self,
        user: "TokenUser",
        connector: ConnectorORM,
    ) -> AccessResult:
        """
        Check if user can view documents from a connector.

        Documents inherit permissions from their connector.

        Args:
            user: The authenticated user.
            connector: The document's parent connector.

        Returns:
            AccessResult with allowed status and reason.
        """
        return await self.can_view_connector(user, connector)

    async def can_edit_document(
        self,
        user: "TokenUser",
        connector: ConnectorORM,
    ) -> AccessResult:
        """
        Check if user can upload/delete documents for a connector.

        Documents inherit permissions from their connector.

        Args:
            user: The authenticated user.
            connector: The document's parent connector.

        Returns:
            AccessResult with allowed status and reason.
        """
        return await self.can_edit_connector(user, connector)

    # =========================================================================
    # Query Helpers
    # =========================================================================

    async def get_accessible_connector_ids(
        self,
        user: "TokenUser",
    ) -> list[int]:
        """
        Get IDs of all connectors accessible to user.

        Args:
            user: The authenticated user.

        Returns:
            List of connector IDs user can view.
        """
        # Admins can see all
        if self.is_admin(user):
            result = await self.db.execute(
                select(ConnectorORM.id).where(ConnectorORM.deleted_date.is_(None))
            )
            return [r[0] for r in result.all()]

        # Get user's team IDs
        team_ids = await self.get_user_team_ids(user.id)

        # Build query for accessible connectors:
        # 1. User's own connectors (any scope)
        # 2. Team connectors for teams user belongs to
        # 3. Org connectors (visible to all)
        result = await self.db.execute(
            select(ConnectorORM.id)
            .where(ConnectorORM.deleted_date.is_(None))
            .where(
                (ConnectorORM.user_id == user.id)
                | (
                    (ConnectorORM.scope.in_([SCOPE_TEAM, SCOPE_GROUP]))
                    & (ConnectorORM.team_id.in_(team_ids))
                )
                | (ConnectorORM.scope == SCOPE_ORG)
            )
        )
        return [r[0] for r in result.all()]

    async def get_accessible_team_ids(
        self,
        user: "TokenUser",
    ) -> list[int]:
        """
        Get team IDs accessible to user.

        Admins can see all teams, regular users only their own.

        Args:
            user: The authenticated user.

        Returns:
            List of team IDs.
        """
        if self.is_admin(user):
            result = await self.db.execute(
                select(TeamORM.id).where(TeamORM.deleted_date.is_(None))
            )
            return [r[0] for r in result.all()]

        return await self.get_user_team_ids(user.id)

    async def get_search_collections(
        self,
        user: "TokenUser",
    ) -> list[str]:
        """
        Get Qdrant collection names for document search.

        Args:
            user: The authenticated user.

        Returns:
            List of collection names to search.
        """
        collections = []

        # User's personal collection
        collections.append(f"user_{user.id}")

        # Team collections
        team_ids = await self.get_user_team_ids(user.id)
        for team_id in team_ids:
            collections.append(f"team_{team_id}")

        # Org collection (everyone can search)
        collections.append("org_default")

        return collections

    def get_connector_query_filters(
        self,
        user: "TokenUser",
        team_ids: list[int],
    ) -> list:
        """
        Get SQLAlchemy filter clauses for connector queries.

        Args:
            user: The authenticated user.
            team_ids: User's team IDs (precomputed for efficiency).

        Returns:
            List of SQLAlchemy filter conditions (OR'd together).
        """
        from sqlalchemy import or_

        filters = [
            # User's own connectors
            ConnectorORM.user_id == user.id,
            # Team connectors for user's teams
            (
                (ConnectorORM.scope.in_([SCOPE_TEAM, SCOPE_GROUP]))
                & (ConnectorORM.team_id.in_(team_ids))
            ),
            # Org connectors
            ConnectorORM.scope == SCOPE_ORG,
        ]

        return [or_(*filters)]


def create_permission_checker(db: AsyncSession) -> PermissionChecker:
    """
    Factory function to create a PermissionChecker.

    Args:
        db: Database session.

    Returns:
        PermissionChecker instance.
    """
    return PermissionChecker(db)
