"""
Tests for TensorBoard Projector API routes.

Covers all endpoints, error cases, and authentication requirements with Option B design:
- Explicit team_id/org_id parameters
- Team membership validation via database
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from echomind_lib.helpers.auth import TokenUser


@pytest.fixture
def admin_user() -> TokenUser:
    """
    Create a mock admin user for testing.

    Returns:
        TokenUser: Admin user with all required attributes
    """
    return TokenUser(
        id=42,
        email="admin@test.com",
        user_name="admin",
        first_name="Admin",
        last_name="User",
        roles=["admin"],
        groups=["admins"],
        external_id="auth0|123",
    )


@pytest.fixture
def regular_user() -> TokenUser:
    """
    Create a mock regular (non-admin) user for testing.

    Returns:
        TokenUser: Regular user without admin role
    """
    return TokenUser(
        id=99,
        email="user@test.com",
        user_name="user",
        first_name="Regular",
        last_name="User",
        roles=["user"],
        groups=["users"],
        external_id="auth0|456",
    )


@pytest.fixture
def mock_db_session():
    """
    Create a mock database session.

    Returns:
        AsyncMock: Mock AsyncSession
    """
    mock_db = AsyncMock()

    # Mock team membership query result (user IS a member)
    mock_result = MagicMock()  # NOT AsyncMock - scalar_one_or_none() is synchronous
    mock_team_member = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_team_member
    mock_db.execute.return_value = mock_result

    return mock_db


@pytest.fixture
def mock_db_session_not_member():
    """
    Create a mock database session where user is NOT a team member.

    Returns:
        AsyncMock: Mock AsyncSession
    """
    mock_db = AsyncMock()

    # Mock team membership query result (user is NOT a member)
    mock_result = MagicMock()  # NOT AsyncMock - scalar_one_or_none() is synchronous
    mock_result.scalar_one_or_none.return_value = None  # Not a member
    mock_db.execute.return_value = mock_result

    return mock_db


@pytest.fixture
def mock_qdrant_client():
    """
    Create a mock Qdrant client with collections.

    Returns:
        MagicMock: Mock QdrantDB instance
    """
    mock_client = MagicMock()

    # Create a dynamic mock that returns collections for any request
    def mock_get_collections():
        """Mock get_collections to return a flexible set of collections."""
        mock_collections = MagicMock()
        # Return a list of common collection names
        # Note: In real usage, this would return all collections
        # For tests, we mock it to always find the requested collection
        mock_collection = MagicMock()
        mock_collection.name = "ANY"  # Will be checked with 'any()' which is flexible
        mock_collections.collections = []

        # Add collections dynamically based on common patterns
        for collection_name in ["user_42", "team_10", "team_99", "org_1", "org_5"]:
            coll = MagicMock()
            coll.name = collection_name
            mock_collections.collections.append(coll)

        return mock_collections

    mock_client._client.get_collections = mock_get_collections

    # Mock get_collection response for stats
    mock_collection_info = MagicMock()
    mock_collection_info.points_count = 1000
    mock_client._client.get_collection.return_value = mock_collection_info

    return mock_client


@pytest.fixture
def mock_nats_publisher():
    """
    Create a mock NATS publisher.

    Returns:
        AsyncMock: Mock JetStreamPublisher instance
    """
    mock_pub = AsyncMock()
    mock_pub.publish = AsyncMock()
    return mock_pub


class TestProjectorGenerateEndpoint:
    """Tests for POST /api/v1/projector/generate endpoint."""

    @pytest.mark.asyncio
    async def test_generate_visualization_success_user_scope(
        self,
        admin_user: TokenUser,
        mock_db_session: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_nats_publisher: AsyncMock,
    ) -> None:
        """
        Test successful visualization generation for user scope.

        Verifies:
        - Returns correct viz_id format
        - Returns correct collection_name
        - Returns correct tensorboard_url
        - Publishes NATS message with correct protobuf data
        """
        from api.routes.projector import generate_visualization, ProjectorGenerateRequest

        request = ProjectorGenerateRequest(
            scope="user",
            search_query=None,
            limit=5000,
        )

        with patch("api.routes.projector.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "a" * 32  # Mock UUID

            response = await generate_visualization(
                request=request,
                user=admin_user,
                db=mock_db_session,
                qdrant=mock_qdrant_client,
                nats=mock_nats_publisher,
            )

        # Verify response
        assert response.viz_id == "viz-" + "a" * 16
        assert response.collection_name == "user_42"
        assert response.status == "processing"
        assert "tensorboard" in response.tensorboard_url
        assert response.viz_id in response.tensorboard_url

        # Verify NATS publish was called
        assert mock_nats_publisher.publish.called
        call_args = mock_nats_publisher.publish.call_args
        assert call_args.kwargs["subject"] == "projector.generate"

        # Verify protobuf message
        proto_data = call_args.kwargs["data"]
        assert isinstance(proto_data, bytes)

        from echomind_lib.models.internal.projector_pb2 import ProjectorGenerateRequest as ProtoRequest
        proto_msg = ProtoRequest()
        proto_msg.ParseFromString(proto_data)
        assert proto_msg.viz_id == "viz-" + "a" * 16
        assert proto_msg.collection_name == "user_42"
        assert proto_msg.limit == 5000

    @pytest.mark.asyncio
    async def test_generate_visualization_team_scope_success(
        self,
        admin_user: TokenUser,
        mock_db_session: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_nats_publisher: AsyncMock,
    ) -> None:
        """
        Test successful visualization generation for team scope.

        Verifies:
        - Validates team membership
        - Uses correct team collection name
        """
        from api.routes.projector import generate_visualization, ProjectorGenerateRequest

        request = ProjectorGenerateRequest(
            scope="team",
            team_id=10,
            limit=2000,
        )

        response = await generate_visualization(
            request=request,
            user=admin_user,
            db=mock_db_session,
            qdrant=mock_qdrant_client,
            nats=mock_nats_publisher,
        )

        assert response.collection_name == "team_10"

        # Verify team membership was checked
        assert mock_db_session.execute.called

    @pytest.mark.asyncio
    async def test_generate_visualization_team_scope_not_member(
        self,
        admin_user: TokenUser,
        mock_db_session_not_member: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_nats_publisher: AsyncMock,
    ) -> None:
        """
        Test error when user is not a member of requested team.

        Verifies:
        - Returns 403 Forbidden
        - Error message mentions team membership
        """
        from api.routes.projector import generate_visualization, ProjectorGenerateRequest

        request = ProjectorGenerateRequest(
            scope="team",
            team_id=99,  # Team user is not a member of
            limit=1000,
        )

        with pytest.raises(HTTPException) as exc_info:
            await generate_visualization(
                request=request,
                user=admin_user,
                db=mock_db_session_not_member,
                qdrant=mock_qdrant_client,
                nats=mock_nats_publisher,
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "member" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_generate_visualization_team_scope_missing_team_id(
        self,
        admin_user: TokenUser,
        mock_db_session: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_nats_publisher: AsyncMock,
    ) -> None:
        """
        Test error when team_id not provided for team scope.

        Verifies:
        - Returns 400 Bad Request
        - Error message mentions team_id requirement
        """
        from api.routes.projector import generate_visualization, ProjectorGenerateRequest

        request = ProjectorGenerateRequest(
            scope="team",
            # team_id=None (not provided)
            limit=1000,
        )

        with pytest.raises(HTTPException) as exc_info:
            await generate_visualization(
                request=request,
                user=admin_user,
                db=mock_db_session,
                qdrant=mock_qdrant_client,
                nats=mock_nats_publisher,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "team_id" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_generate_visualization_org_scope(
        self,
        admin_user: TokenUser,
        mock_db_session: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_nats_publisher: AsyncMock,
    ) -> None:
        """
        Test successful visualization generation for org scope.

        Verifies:
        - Uses provided org_id
        - Defaults to org_1 if not provided
        """
        from api.routes.projector import generate_visualization, ProjectorGenerateRequest

        # Test with explicit org_id
        request = ProjectorGenerateRequest(scope="org", org_id=5, limit=1000)

        response = await generate_visualization(
            request=request,
            user=admin_user,
            db=mock_db_session,
            qdrant=mock_qdrant_client,
            nats=mock_nats_publisher,
        )

        assert response.collection_name == "org_5"

    @pytest.mark.asyncio
    async def test_generate_visualization_org_scope_default(
        self,
        admin_user: TokenUser,
        mock_db_session: AsyncMock,
        mock_qdrant_client: MagicMock,
        mock_nats_publisher: AsyncMock,
    ) -> None:
        """
        Test org scope defaults to org_1 when org_id not provided.

        Verifies:
        - Defaults to org_1
        """
        from api.routes.projector import generate_visualization, ProjectorGenerateRequest

        request = ProjectorGenerateRequest(scope="org", limit=1000)

        response = await generate_visualization(
            request=request,
            user=admin_user,
            db=mock_db_session,
            qdrant=mock_qdrant_client,
            nats=mock_nats_publisher,
        )

        assert response.collection_name == "org_1"

    @pytest.mark.asyncio
    async def test_generate_visualization_qdrant_unavailable(
        self,
        admin_user: TokenUser,
        mock_db_session: AsyncMock,
        mock_nats_publisher: AsyncMock,
    ) -> None:
        """Test error when Qdrant is unavailable."""
        from api.routes.projector import generate_visualization, ProjectorGenerateRequest

        request = ProjectorGenerateRequest(scope="user", limit=1000)

        with pytest.raises(HTTPException) as exc_info:
            await generate_visualization(
                request=request,
                user=admin_user,
                db=mock_db_session,
                qdrant=None,
                nats=mock_nats_publisher,
            )

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_generate_visualization_nats_unavailable(
        self,
        admin_user: TokenUser,
        mock_db_session: AsyncMock,
        mock_qdrant_client: MagicMock,
    ) -> None:
        """Test error when NATS is unavailable."""
        from api.routes.projector import generate_visualization, ProjectorGenerateRequest

        request = ProjectorGenerateRequest(scope="user", limit=1000)

        with pytest.raises(HTTPException) as exc_info:
            await generate_visualization(
                request=request,
                user=admin_user,
                db=mock_db_session,
                qdrant=mock_qdrant_client,
                nats=None,
            )

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestProjectorStatsEndpoint:
    """Tests for GET /api/v1/projector/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_collection_stats_success(
        self,
        admin_user: TokenUser,
        mock_qdrant_client: MagicMock,
    ) -> None:
        """
        Test successful retrieval of collection statistics.

        Verifies:
        - Returns user collection stats
        - Returns all team collections user is a member of
        - Returns org collection stats
        """
        from api.routes.projector import get_collection_stats

        # Mock database to return user's teams
        mock_db = AsyncMock()
        mock_result = MagicMock()  # NOT AsyncMock - result.all() is synchronous

        # Create mock team data
        mock_team_member1 = MagicMock()
        mock_team1 = MagicMock()
        mock_team1.id = 10
        mock_team1.name = "Engineering"

        mock_team_member2 = MagicMock()
        mock_team2 = MagicMock()
        mock_team2.id = 20
        mock_team2.name = "Marketing"

        mock_result.all.return_value = [
            (mock_team_member1, mock_team1),
            (mock_team_member2, mock_team2),
        ]
        mock_db.execute.return_value = mock_result

        response = await get_collection_stats(
            user=admin_user,
            db=mock_db,
            qdrant=mock_qdrant_client,
        )

        assert response.user_collection == "user_42"
        assert response.user_vectors == 1000
        assert len(response.teams) == 2
        assert response.teams[0].team_id == 10
        assert response.teams[0].team_name == "Engineering"
        assert response.teams[1].team_id == 20
        assert response.org_collection == "org_1"

    @pytest.mark.asyncio
    async def test_get_collection_stats_no_teams(
        self,
        admin_user: TokenUser,
        mock_qdrant_client: MagicMock,
    ) -> None:
        """
        Test stats when user is not a member of any teams.

        Verifies:
        - Returns empty teams list
        - Doesn't crash
        """
        from api.routes.projector import get_collection_stats

        # Mock database to return no teams
        mock_db = AsyncMock()
        mock_result = MagicMock()  # NOT AsyncMock - result.all() is synchronous
        mock_result.all.return_value = []  # No teams
        mock_db.execute.return_value = mock_result

        response = await get_collection_stats(
            user=admin_user,
            db=mock_db,
            qdrant=mock_qdrant_client,
        )

        assert len(response.teams) == 0

    @pytest.mark.asyncio
    async def test_get_collection_stats_qdrant_unavailable(
        self,
        admin_user: TokenUser,
    ) -> None:
        """Test error when Qdrant is unavailable."""
        from api.routes.projector import get_collection_stats

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_collection_stats(
                user=admin_user,
                db=mock_db,
                qdrant=None,
            )

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestProjectorRequestValidation:
    """Tests for Pydantic request model validation."""

    def test_projector_request_valid_scopes(self) -> None:
        """Test all valid scopes."""
        from api.routes.projector import ProjectorGenerateRequest

        for scope in ["user", "team", "org"]:
            request = ProjectorGenerateRequest(scope=scope, limit=5000)
            assert request.scope == scope

    def test_projector_request_invalid_scope(self) -> None:
        """Test invalid scope raises validation error."""
        from api.routes.projector import ProjectorGenerateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProjectorGenerateRequest(scope="invalid", limit=5000)

    def test_projector_request_team_id_optional(self) -> None:
        """Test team_id is optional."""
        from api.routes.projector import ProjectorGenerateRequest

        request = ProjectorGenerateRequest(scope="team")
        assert request.team_id is None

    def test_projector_request_org_id_optional(self) -> None:
        """Test org_id is optional."""
        from api.routes.projector import ProjectorGenerateRequest

        request = ProjectorGenerateRequest(scope="org")
        assert request.org_id is None

    def test_projector_request_limit_validation(self) -> None:
        """Test limit must be between 100 and 20000."""
        from api.routes.projector import ProjectorGenerateRequest
        from pydantic import ValidationError

        # Too low
        with pytest.raises(ValidationError):
            ProjectorGenerateRequest(scope="user", limit=50)

        # Too high
        with pytest.raises(ValidationError):
            ProjectorGenerateRequest(scope="user", limit=25000)

        # Valid
        request = ProjectorGenerateRequest(scope="user", limit=5000)
        assert request.limit == 5000
