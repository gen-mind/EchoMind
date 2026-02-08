"""TensorBoard Projector visualization endpoints (Admin-only)."""

import logging
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import AdminUser, DbSession, NatsPublisher, QdrantClient
from echomind_lib.helpers.auth import TokenUser
from echomind_lib.models.internal.projector_pb2 import ProjectorGenerateRequest as ProtoProjectorRequest

logger = logging.getLogger(__name__)
router = APIRouter()


class ProjectorGenerateRequest(BaseModel):
    """Request to generate TensorBoard visualization."""

    scope: str = Field(
        ...,
        description="Collection scope: 'user', 'team', or 'org'",
        pattern="^(user|team|org)$",
    )
    team_id: int | None = Field(
        None,
        description="Team ID (required when scope='team')",
        gt=0,
    )
    org_id: int | None = Field(
        None,
        description="Organization ID (required when scope='org', defaults to 1 if not provided)",
        gt=0,
    )
    search_query: str | None = Field(
        None,
        description="Optional search query to filter vectors",
    )
    limit: int = Field(
        default=10000,
        ge=100,
        le=20000,
        description="Max vectors to visualize (100-20k, default 10k)",
    )


class ProjectorGenerateResponse(BaseModel):
    """Response after requesting visualization generation."""

    viz_id: str = Field(..., description="Unique visualization ID")
    collection_name: str = Field(..., description="Qdrant collection name")
    status: str = Field(..., description="Processing status")
    tensorboard_url: str = Field(..., description="TensorBoard Projector URL")
    message: str = Field(..., description="Human-readable message")


class TeamCollectionStats(BaseModel):
    """Statistics for a single team collection."""

    team_id: int
    team_name: str
    collection_name: str
    vector_count: int


class CollectionStatsResponse(BaseModel):
    """Statistics for user/team/org collections."""

    user_collection: str
    user_vectors: int
    teams: list[TeamCollectionStats]
    org_collection: str
    org_vectors: int


@router.post("/generate", response_model=ProjectorGenerateResponse)
async def generate_visualization(
    request: ProjectorGenerateRequest,
    user: AdminUser,
    db: DbSession,
    qdrant: QdrantClient,
    nats: NatsPublisher,
) -> ProjectorGenerateResponse:
    """
    Generate TensorBoard Projector visualization (Admin-only).

    Publishes a NATS message to the projector worker, which:
    1. Fetches vectors from the specified Qdrant collection
    2. Generates TensorFlow checkpoint files
    3. Makes the visualization available via TensorBoard

    Access Control:
    - Admin users only
    - User scope: Admin's own user collection
    - Team scope: Admin's current team collection
    - Org scope: Admin's organization collection

    Args:
        request: Visualization parameters
        user: Authenticated admin user
        db: Database session
        qdrant: Qdrant client
        nats: NATS publisher

    Returns:
        ProjectorGenerateResponse: Visualization ID and TensorBoard URL

    Raises:
        HTTPException: 400 if user not assigned to team/org for team/org scope
        HTTPException: 503 if Qdrant or NATS unavailable
    """
    # Check service availability
    if qdrant is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant vector database is not available",
        )

    if nats is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NATS message queue is not available",
        )

    # Determine collection name based on scope
    if request.scope == "user":
        collection_name = f"user_{user.id}"

    elif request.scope == "team":
        # Require team_id parameter
        if not request.team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="team_id parameter required when scope='team'",
            )

        # Verify user is a member of the requested team
        from sqlalchemy import select
        from echomind_lib.db.models import TeamMember

        result = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == request.team_id,
                TeamMember.user_id == user.id,
            )
        )
        team_member = result.scalar_one_or_none()

        if not team_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User is not a member of team {request.team_id}",
            )

        collection_name = f"team_{request.team_id}"

    elif request.scope == "org":
        # Use provided org_id or default to 1
        org_id = request.org_id or 1
        # NOTE: No org membership validation for now - all users can access default org
        # TODO: Add Organization model and membership validation
        collection_name = f"org_{org_id}"

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope: {request.scope}",
        )

    # Check if collection exists
    try:
        collections = qdrant._client.get_collections()
        collection_exists = any(c.name == collection_name for c in collections.collections)

        if not collection_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' does not exist",
            )

    except HTTPException:
        # Re-raise HTTP exceptions (like 404 above)
        raise
    except Exception as e:
        # Only catch actual Qdrant connection errors
        logger.exception(f"❌ Failed to check Qdrant collections")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to Qdrant: {str(e)}",
        ) from e

    # Generate unique viz ID
    viz_id = f"viz-{uuid4().hex[:16]}"

    # Create protobuf message
    proto_request = ProtoProjectorRequest(
        viz_id=viz_id,
        collection_name=collection_name,
        limit=request.limit,
    )

    # Set optional fields if provided
    if request.search_query:
        proto_request.search_query = request.search_query
    if request.team_id:
        proto_request.team_id = request.team_id
    if request.org_id:
        proto_request.org_id = request.org_id

    try:
        await nats.publish(
            subject="projector.generate",
            data=proto_request.SerializeToString(),
        )
        logger.info(
            f"📨 Published projector request: viz_id={viz_id}, "
            f"collection={collection_name}, search={request.search_query or 'none'}"
        )

    except Exception as e:
        logger.exception(f"❌ Failed to publish NATS message")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue visualization request: {str(e)}",
        ) from e

    # Construct TensorBoard URL (visualization will be available once worker processes it)
    tensorboard_domain = os.getenv("TENSORBOARD_DOMAIN", "tensorboard.echomind.local")
    tensorboard_url = f"https://{tensorboard_domain}/#projector&run={viz_id}"

    return ProjectorGenerateResponse(
        viz_id=viz_id,
        collection_name=collection_name,
        status="processing",
        tensorboard_url=tensorboard_url,
        message=(
            f"Visualization queued for processing. "
            f"Visit the URL in 30-60 seconds to view your {request.limit} vectors."
        ),
    )


@router.get("/stats", response_model=CollectionStatsResponse)
async def get_collection_stats(
    user: AdminUser,
    db: DbSession,
    qdrant: QdrantClient,
) -> CollectionStatsResponse:
    """
    Get vector counts for user/team/org collections (Admin-only).

    Returns the collection names and vector counts for:
    - User collection (user_{user_id})
    - All team collections the user is a member of
    - Organization collection (org_1)

    If a collection doesn't exist, the count will be 0.

    Args:
        user: Authenticated admin user
        db: Database session
        qdrant: Qdrant client

    Returns:
        CollectionStatsResponse: Collection names and vector counts

    Raises:
        HTTPException: 503 if Qdrant unavailable
    """
    if qdrant is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant vector database is not available",
        )

    # Get user's teams
    from sqlalchemy import select
    from echomind_lib.db.models import TeamMember, Team

    result = await db.execute(
        select(TeamMember, Team)
        .join(Team, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == user.id)
    )
    user_teams = result.all()  # This is NOT a coroutine - it's a method on Result

    # Initialize stats
    user_collection = f"user_{user.id}"
    org_collection = "org_1"
    team_stats: list[TeamCollectionStats] = []

    # Get collection counts from Qdrant
    try:
        collections = qdrant._client.get_collections()
        collection_map = {c.name: c for c in collections.collections}

        # User collection count
        user_vectors = 0
        if user_collection in collection_map:
            info = qdrant._client.get_collection(user_collection)
            user_vectors = info.points_count

        # Team collections counts
        for team_member, team in user_teams:
            team_collection = f"team_{team.id}"
            vector_count = 0

            if team_collection in collection_map:
                info = qdrant._client.get_collection(team_collection)
                vector_count = info.points_count

            team_stats.append(
                TeamCollectionStats(
                    team_id=team.id,
                    team_name=team.name,
                    collection_name=team_collection,
                    vector_count=vector_count,
                )
            )

        # Org collection count
        org_vectors = 0
        if org_collection in collection_map:
            info = qdrant._client.get_collection(org_collection)
            org_vectors = info.points_count

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Only catch actual Qdrant connection errors
        logger.exception(f"❌ Failed to get Qdrant collection stats")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get collection statistics: {str(e)}",
        ) from e

    return CollectionStatsResponse(
        user_collection=user_collection,
        user_vectors=user_vectors,
        teams=team_stats,
        org_collection=org_collection,
        org_vectors=org_vectors,
    )
