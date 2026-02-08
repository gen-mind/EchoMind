"""Projector service business logic."""

import logging
import os
from typing import Any

from echomind_lib.db.qdrant import QdrantDB
from .checkpoint_generator import CheckpointGenerator
from .exceptions import VectorFetchError, EmptyCollectionError


logger = logging.getLogger(__name__)


class ProjectorService:
    """Service for generating TensorBoard visualizations from Qdrant collections."""

    def __init__(
        self,
        qdrant_url: str,
        qdrant_api_key: str | None = None,
        log_base_dir: str = "/logs",
    ):
        """
        Initialize projector service.

        Args:
            qdrant_url: Qdrant server URL
            qdrant_api_key: Optional Qdrant API key
            log_base_dir: Base directory for TensorBoard logs
        """
        self.qdrant = QdrantDB(qdrant_url, qdrant_api_key)
        self.generator = CheckpointGenerator(log_base_dir)
        self.tensorboard_domain = os.getenv("TENSORBOARD_DOMAIN", "tensorboard.echomind.local")

    async def generate_visualization(
        self,
        collection_name: str,
        search_query: str | None = None,
        limit: int = 10000,
    ) -> dict[str, Any]:
        """
        Generate TensorBoard visualization for a Qdrant collection.

        Args:
            collection_name: Qdrant collection name
            search_query: Optional search query to filter vectors
            limit: Max vectors to visualize (default 10k)

        Returns:
            Dict with viz_id, tensorboard_url, num_points, vector_dimension, search_applied

        Raises:
            VectorFetchError: If fetching vectors from Qdrant fails
            EmptyCollectionError: If no vectors found
        """
        logger.info(
            f"🔍 Generating visualization for collection '{collection_name}' "
            f"(search: {search_query or 'none'}, limit: {limit})"
        )

        # Build scroll filter if search query provided
        scroll_filter = None
        if search_query:
            # Qdrant full-text search on payload fields
            scroll_filter = {
                "should": [
                    {"key": "title", "match": {"text": search_query}},
                    {"key": "text", "match": {"text": search_query}},
                ]
            }
            logger.info(f"🔎 Applying search filter: {search_query}")

        # Fetch vectors from Qdrant
        points = await self._fetch_vectors(
            collection_name=collection_name,
            limit=limit,
            scroll_filter=scroll_filter,
        )

        if not points:
            error_msg = f"No vectors found in {collection_name}"
            if search_query:
                error_msg += f" matching '{search_query}'"
            logger.error(f"❌ {error_msg}")
            raise EmptyCollectionError(error_msg)

        logger.info(f"📦 Fetched {len(points)} vectors from {collection_name}")

        # Generate TensorFlow checkpoint
        result = self.generator.generate_visualization(
            points=points,
            collection_name=collection_name,
        )

        # Construct TensorBoard URL
        tensorboard_url = (
            f"https://{self.tensorboard_domain}/"
            f"#projector&run={result['viz_id']}"
        )

        logger.info(f"✅ Visualization generated: {tensorboard_url}")

        return {
            "viz_id": result["viz_id"],
            "tensorboard_url": tensorboard_url,
            "collection_name": collection_name,
            "num_points": result["num_points"],
            "vector_dimension": result["vector_dim"],
            "search_applied": bool(search_query),
        }

    async def _fetch_vectors(
        self,
        collection_name: str,
        limit: int,
        scroll_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch vectors from Qdrant using scroll API.

        Args:
            collection_name: Qdrant collection name
            limit: Max vectors to fetch
            scroll_filter: Optional Qdrant filter

        Returns:
            List of points with 'vector' and 'payload' keys

        Raises:
            VectorFetchError: If fetch fails
        """
        points = []
        offset = None

        try:
            while len(points) < limit:
                batch, offset = self.qdrant._client.scroll(
                    collection_name=collection_name,
                    limit=min(500, limit - len(points)),  # Batch size
                    offset=offset,
                    scroll_filter=scroll_filter,
                    with_payload=True,
                    with_vectors=True,  # CRITICAL: Must fetch vectors
                )

                if not batch:
                    break

                # Convert to dict format
                for point in batch:
                    points.append({
                        "id": point.id,
                        "vector": point.vector,
                        "payload": point.payload or {},
                    })

                if offset is None:
                    break

                logger.info(f"📊 Fetched {len(points)}/{limit} vectors...")

        except Exception as e:
            logger.exception(f"❌ Failed to fetch vectors from {collection_name}")
            raise VectorFetchError(
                f"Failed to fetch vectors from {collection_name}: {str(e)}"
            ) from e

        return points
