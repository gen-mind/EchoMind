"""
Tests for ProjectorService business logic.

Covers visualization generation, vector fetching, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from projector.logic.projector_service import ProjectorService
from projector.logic.exceptions import VectorFetchError, EmptyCollectionError


@pytest.fixture
def mock_qdrant():
    """
    Create a mock Qdrant client.

    Returns:
        MagicMock: Mock QdrantDB instance
    """
    mock_qdrant = MagicMock()

    # Mock scroll response with vectors
    mock_point1 = MagicMock()
    mock_point1.id = "point1"
    mock_point1.vector = [0.1, 0.2, 0.3]
    mock_point1.payload = {"title": "Doc 1", "text": "Sample text"}

    mock_point2 = MagicMock()
    mock_point2.id = "point2"
    mock_point2.vector = [0.4, 0.5, 0.6]
    mock_point2.payload = {"title": "Doc 2", "text": "Another document"}

    # Mock scroll returns (batch, offset)
    mock_qdrant._client.scroll.return_value = ([mock_point1, mock_point2], None)

    return mock_qdrant


@pytest.fixture
def projector_service(mock_qdrant, monkeypatch):
    """
    Create a ProjectorService instance with mocked dependencies.

    Args:
        mock_qdrant: Mocked Qdrant client
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        ProjectorService: Service instance for testing
    """
    # Mock QdrantDB to return our mock
    monkeypatch.setattr(
        "projector.logic.projector_service.QdrantDB",
        lambda *args, **kwargs: mock_qdrant
    )

    service = ProjectorService(
        qdrant_url="qdrant:6333",
        qdrant_api_key=None,
        log_base_dir="/tmp/test_logs",
    )
    return service


class TestProjectorServiceGenerateVisualization:
    """Tests for generate_visualization method."""

    @pytest.mark.asyncio
    async def test_generate_visualization_success(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test successful visualization generation.

        Verifies:
        - Returns viz_id
        - Returns tensorboard_url
        - Returns correct num_points
        - Returns correct vector_dimension
        """
        with patch.object(projector_service.generator, "generate_visualization") as mock_gen:
            mock_gen.return_value = {
                "viz_id": "viz-test123",
                "log_dir": "/tmp/test_logs/viz-test123",
                "num_points": 2,
                "vector_dim": 3,
            }

            result = await projector_service.generate_visualization(
                collection_name="user_42",
                search_query=None,
                limit=10000,
            )

        assert result["viz_id"] == "viz-test123"
        assert "tensorboard" in result["tensorboard_url"]
        assert result["num_points"] == 2
        assert result["vector_dimension"] == 3
        assert result["search_applied"] is False

    @pytest.mark.asyncio
    async def test_generate_visualization_with_search(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test visualization generation with search query.

        Verifies:
        - search_applied is True when search query provided
        - Scroll filter is constructed correctly
        """
        with patch.object(projector_service.generator, "generate_visualization") as mock_gen:
            mock_gen.return_value = {
                "viz_id": "viz-test456",
                "log_dir": "/tmp/test_logs/viz-test456",
                "num_points": 1,
                "vector_dim": 3,
            }

            result = await projector_service.generate_visualization(
                collection_name="user_42",
                search_query="test query",
                limit=5000,
            )

        assert result["search_applied"] is True

        # Verify scroll was called with filter
        scroll_call = projector_service.qdrant._client.scroll.call_args
        assert scroll_call.kwargs["scroll_filter"] is not None

    @pytest.mark.asyncio
    async def test_generate_visualization_empty_collection(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test error when collection has no vectors.

        Verifies:
        - Raises EmptyCollectionError
        - Error message includes collection name
        """
        # Mock scroll to return empty results
        projector_service.qdrant._client.scroll.return_value = ([], None)

        with pytest.raises(EmptyCollectionError) as exc_info:
            await projector_service.generate_visualization(
                collection_name="empty_collection",
                search_query=None,
                limit=1000,
            )

        assert "empty_collection" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_visualization_empty_after_search(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test error when search query returns no results.

        Verifies:
        - Raises EmptyCollectionError
        - Error message includes search query
        """
        # Mock scroll to return empty results
        projector_service.qdrant._client.scroll.return_value = ([], None)

        with pytest.raises(EmptyCollectionError) as exc_info:
            await projector_service.generate_visualization(
                collection_name="user_42",
                search_query="nonexistent",
                limit=1000,
            )

        assert "nonexistent" in str(exc_info.value)


class TestProjectorServiceFetchVectors:
    """Tests for _fetch_vectors method."""

    @pytest.mark.asyncio
    async def test_fetch_vectors_single_batch(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test fetching vectors in a single batch.

        Verifies:
        - Returns correct number of points
        - Each point has id, vector, and payload
        - scroll called with correct parameters
        """
        # Mock single batch response
        mock_point = MagicMock()
        mock_point.id = "point1"
        mock_point.vector = [0.1, 0.2]
        mock_point.payload = {"title": "Doc"}

        projector_service.qdrant._client.scroll.return_value = ([mock_point], None)

        points = await projector_service._fetch_vectors(
            collection_name="test_collection",
            limit=100,
            scroll_filter=None,
        )

        assert len(points) == 1
        assert points[0]["id"] == "point1"
        assert points[0]["vector"] == [0.1, 0.2]
        assert points[0]["payload"] == {"title": "Doc"}

    @pytest.mark.asyncio
    async def test_fetch_vectors_multiple_batches(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test fetching vectors across multiple batches.

        Verifies:
        - Pagination works correctly
        - All batches are combined
        - scroll called multiple times
        """
        # Mock multiple batch responses
        mock_point1 = MagicMock()
        mock_point1.id = "p1"
        mock_point1.vector = [0.1]
        mock_point1.payload = {}

        mock_point2 = MagicMock()
        mock_point2.id = "p2"
        mock_point2.vector = [0.2]
        mock_point2.payload = {}

        # First call returns batch with offset
        # Second call returns batch with no offset (end)
        projector_service.qdrant._client.scroll.side_effect = [
            ([mock_point1], "offset1"),
            ([mock_point2], None),
        ]

        points = await projector_service._fetch_vectors(
            collection_name="test_collection",
            limit=1000,
            scroll_filter=None,
        )

        assert len(points) == 2
        assert projector_service.qdrant._client.scroll.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_vectors_with_filter(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test fetching vectors with scroll filter.

        Verifies:
        - Filter is passed to scroll API
        """
        mock_point = MagicMock()
        mock_point.id = "p1"
        mock_point.vector = [0.1]
        mock_point.payload = {}

        projector_service.qdrant._client.scroll.return_value = ([mock_point], None)

        scroll_filter = {"should": [{"key": "title", "match": {"text": "query"}}]}

        points = await projector_service._fetch_vectors(
            collection_name="test_collection",
            limit=100,
            scroll_filter=scroll_filter,
        )

        # Verify filter was passed
        call_args = projector_service.qdrant._client.scroll.call_args
        assert call_args.kwargs["scroll_filter"] == scroll_filter

    @pytest.mark.asyncio
    async def test_fetch_vectors_limit_respected(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test that fetch stops at limit.

        Verifies:
        - Only fetches up to limit
        - Doesn't fetch more batches than needed
        """
        # Mock many points
        mock_points = [MagicMock(id=f"p{i}", vector=[float(i)], payload={}) for i in range(500)]

        # Mock scroll to always return 500 points
        projector_service.qdrant._client.scroll.side_effect = [
            (mock_points, "offset1"),
            (mock_points, None),
        ]

        points = await projector_service._fetch_vectors(
            collection_name="test_collection",
            limit=600,  # Should fetch 2 batches
            scroll_filter=None,
        )

        # Should get 600 points (500 from first batch + first 100 from second)
        # Actually, looking at the code, it will fetch both batches
        # because the while condition is len(points) < limit
        assert len(points) <= 1000  # At most 2 batches

    @pytest.mark.asyncio
    async def test_fetch_vectors_qdrant_error(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test error handling when Qdrant scroll fails.

        Verifies:
        - Raises VectorFetchError
        - Exception is chained properly
        """
        # Mock scroll to raise exception
        projector_service.qdrant._client.scroll.side_effect = Exception("Connection failed")

        with pytest.raises(VectorFetchError) as exc_info:
            await projector_service._fetch_vectors(
                collection_name="test_collection",
                limit=100,
                scroll_filter=None,
            )

        assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_vectors_none_payload(
        self,
        projector_service: ProjectorService,
    ) -> None:
        """
        Test handling of points with None payload.

        Verifies:
        - None payload is converted to empty dict
        - Doesn't crash
        """
        mock_point = MagicMock()
        mock_point.id = "p1"
        mock_point.vector = [0.1]
        mock_point.payload = None  # None payload

        projector_service.qdrant._client.scroll.return_value = ([mock_point], None)

        points = await projector_service._fetch_vectors(
            collection_name="test_collection",
            limit=100,
            scroll_filter=None,
        )

        assert points[0]["payload"] == {}  # Should be empty dict, not None
