"""
Tests for ProjectorWorker NATS subscriber.

Covers message handling, connection management, retries, and health probes.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from nats.aio.msg import Msg

from projector.logic.exceptions import ProjectorError, EmptyCollectionError


@pytest.fixture
def mock_msg():
    """
    Create a mock NATS message.

    Returns:
        MagicMock: Mock NATS Msg instance
    """
    msg = MagicMock(spec=Msg)
    msg.ack = AsyncMock()
    msg.nak = AsyncMock()
    return msg


@pytest.fixture
def mock_projector_service():
    """
    Create a mock ProjectorService.

    Returns:
        MagicMock: Mock ProjectorService instance
    """
    service = MagicMock()
    service.generate_visualization = AsyncMock(
        return_value={
            "viz_id": "viz-test123",
            "log_dir": "/logs/viz-test123",
            "num_points": 100,
            "vector_dimension": 768,
        }
    )
    service.qdrant._client.get_collections = MagicMock(
        return_value=MagicMock(collections=[])
    )
    return service


@pytest.fixture
def mock_jetstream_subscriber():
    """
    Create a mock JetStreamSubscriber.

    Returns:
        MagicMock: Mock JetStreamSubscriber instance
    """
    subscriber = MagicMock()
    subscriber.init = AsyncMock()
    subscriber.subscribe = AsyncMock()
    subscriber.close = AsyncMock()
    return subscriber


@pytest.fixture
def mock_readiness_probe():
    """
    Create a mock ReadinessProbe.

    Returns:
        MagicMock: Mock ReadinessProbe instance
    """
    probe = MagicMock()
    probe.set_ready = MagicMock()
    probe.start_server = MagicMock()
    return probe


@pytest.fixture
def worker(mock_projector_service, monkeypatch):
    """
    Create a ProjectorWorker instance with mocked dependencies.

    Args:
        mock_projector_service: Mocked ProjectorService
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        ProjectorWorker: Worker instance for testing
    """
    # Mock ProjectorService constructor
    monkeypatch.setattr(
        "projector.main.ProjectorService",
        lambda *args, **kwargs: mock_projector_service
    )

    from projector.main import ProjectorWorker
    worker = ProjectorWorker()
    return worker


class TestProjectorWorkerHandleMessage:
    """Tests for _handle_message method."""

    @pytest.mark.asyncio
    async def test_handle_message_success(
        self,
        worker,
        mock_msg: MagicMock,
    ) -> None:
        """
        Test successful message processing.

        Verifies:
        - Parses protobuf message
        - Calls service.generate_visualization
        - Acknowledges message
        """
        from echomind_lib.models.internal.projector_pb2 import ProjectorGenerateRequest

        # Create protobuf message
        proto_msg = ProjectorGenerateRequest(
            viz_id="viz-test123",
            collection_name="user_42",
            search_query="test query",
            limit=5000,
        )
        mock_msg.data = proto_msg.SerializeToString()

        # Set worker as ready
        worker._nats_connected = True
        worker._qdrant_connected = True

        await worker._handle_message(mock_msg)

        # Verify service called
        worker.service.generate_visualization.assert_called_once_with(
            collection_name="user_42",
            search_query="test query",
            limit=5000,
        )

        # Verify message acknowledged
        mock_msg.ack.assert_called_once()
        mock_msg.nak.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_service_not_ready(
        self,
        worker,
        mock_msg: MagicMock,
    ) -> None:
        """
        Test message handling when service not ready.

        Verifies:
        - Skips processing
        - Naks message
        - Does not call service
        """
        # Set worker as not ready
        worker._nats_connected = False
        worker._qdrant_connected = False

        await worker._handle_message(mock_msg)

        # Verify message nacked
        mock_msg.nak.assert_called_once()
        mock_msg.ack.assert_not_called()

        # Verify service not called
        worker.service.generate_visualization.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_empty_collection(
        self,
        worker,
        mock_msg: MagicMock,
    ) -> None:
        """
        Test handling of EmptyCollectionError.

        Verifies:
        - Acknowledges message (not a failure)
        - Logs warning
        """
        from echomind_lib.models.internal.projector_pb2 import ProjectorGenerateRequest

        # Create protobuf message
        proto_msg = ProjectorGenerateRequest(
            viz_id="viz-test123",
            collection_name="empty_collection",
            limit=1000,
        )
        mock_msg.data = proto_msg.SerializeToString()

        # Set worker as ready
        worker._nats_connected = True
        worker._qdrant_connected = True

        # Mock service to raise EmptyCollectionError
        worker.service.generate_visualization.side_effect = EmptyCollectionError(
            "Collection is empty"
        )

        await worker._handle_message(mock_msg)

        # Verify message acknowledged (empty is not an error)
        mock_msg.ack.assert_called_once()
        mock_msg.nak.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_projector_error(
        self,
        worker,
        mock_msg: MagicMock,
    ) -> None:
        """
        Test handling of ProjectorError.

        Verifies:
        - Naks message (retryable error)
        - Does not ack
        """
        from echomind_lib.models.internal.projector_pb2 import ProjectorGenerateRequest

        # Create protobuf message
        proto_msg = ProjectorGenerateRequest(
            viz_id="viz-test123",
            collection_name="user_42",
            limit=1000,
        )
        mock_msg.data = proto_msg.SerializeToString()

        # Set worker as ready
        worker._nats_connected = True
        worker._qdrant_connected = True

        # Mock service to raise ProjectorError
        worker.service.generate_visualization.side_effect = ProjectorError(
            "Failed to generate checkpoint"
        )

        await worker._handle_message(mock_msg)

        # Verify message nacked
        mock_msg.nak.assert_called_once()
        mock_msg.ack.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_generic_exception(
        self,
        worker,
        mock_msg: MagicMock,
    ) -> None:
        """
        Test handling of unexpected exception.

        Verifies:
        - Naks message
        - Logs exception
        """
        from echomind_lib.models.internal.projector_pb2 import ProjectorGenerateRequest

        # Create protobuf message
        proto_msg = ProjectorGenerateRequest(
            viz_id="viz-test123",
            collection_name="user_42",
            limit=1000,
        )
        mock_msg.data = proto_msg.SerializeToString()

        # Set worker as ready
        worker._nats_connected = True
        worker._qdrant_connected = True

        # Mock service to raise generic exception
        worker.service.generate_visualization.side_effect = RuntimeError(
            "Unexpected error"
        )

        await worker._handle_message(mock_msg)

        # Verify message nacked
        mock_msg.nak.assert_called_once()
        mock_msg.ack.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_no_search_query(
        self,
        worker,
        mock_msg: MagicMock,
    ) -> None:
        """
        Test message handling without search query.

        Verifies:
        - Optional field handled correctly
        - search_query passed as None
        """
        from echomind_lib.models.internal.projector_pb2 import ProjectorGenerateRequest

        # Create protobuf message WITHOUT search_query
        proto_msg = ProjectorGenerateRequest(
            viz_id="viz-test123",
            collection_name="user_42",
            limit=1000,
        )
        mock_msg.data = proto_msg.SerializeToString()

        # Set worker as ready
        worker._nats_connected = True
        worker._qdrant_connected = True

        await worker._handle_message(mock_msg)

        # Verify service called with None for search_query
        worker.service.generate_visualization.assert_called_once_with(
            collection_name="user_42",
            search_query=None,
            limit=1000,
        )


class TestProjectorWorkerConnectionManagement:
    """Tests for connection initialization and retry logic."""

    @pytest.mark.asyncio
    async def test_init_nats_success(
        self,
        worker,
        mock_jetstream_subscriber: MagicMock,
        monkeypatch,
    ) -> None:
        """
        Test successful NATS initialization.

        Verifies:
        - Creates subscriber
        - Subscribes to subject
        - Sets connection flag
        - Updates readiness
        """
        # Mock JetStreamSubscriber constructor
        monkeypatch.setattr(
            "projector.main.JetStreamSubscriber",
            lambda *args, **kwargs: mock_jetstream_subscriber
        )

        await worker._init_nats()

        # Verify subscriber initialized
        mock_jetstream_subscriber.init.assert_called_once()

        # Verify subscribed
        mock_jetstream_subscriber.subscribe.assert_called_once_with(
            stream=worker.stream_name,
            consumer=worker.consumer_name,
            subject=worker.subject,
            handler=worker._handle_message,
        )

        # Verify connection flag set
        assert worker._nats_connected is True

    @pytest.mark.asyncio
    async def test_init_nats_failure(
        self,
        worker,
        mock_jetstream_subscriber: MagicMock,
        monkeypatch,
    ) -> None:
        """
        Test NATS initialization failure.

        Verifies:
        - Logs warning
        - Spawns retry task
        - Connection flag remains False
        """
        # Mock JetStreamSubscriber to raise exception
        mock_jetstream_subscriber.init.side_effect = Exception("Connection failed")

        monkeypatch.setattr(
            "projector.main.JetStreamSubscriber",
            lambda *args, **kwargs: mock_jetstream_subscriber
        )

        await worker._init_nats()

        # Verify connection flag not set
        assert worker._nats_connected is False

        # Verify retry task spawned
        assert len(worker._retry_tasks) == 1

    @pytest.mark.asyncio
    async def test_retry_nats_connection_eventually_succeeds(
        self,
        worker,
        mock_jetstream_subscriber: MagicMock,
        monkeypatch,
    ) -> None:
        """
        Test NATS retry eventually succeeds.

        Verifies:
        - Retry loop runs
        - Connection flag gets set when successful
        - Loop exits after success
        """
        # Mock JetStreamSubscriber
        monkeypatch.setattr(
            "projector.main.JetStreamSubscriber",
            lambda *args, **kwargs: mock_jetstream_subscriber
        )

        # Track number of retry attempts
        retry_count = 0

        original_sleep = asyncio.sleep

        async def mock_sleep(seconds):
            """Mock sleep that counts retries and shortcuts the wait."""
            nonlocal retry_count
            retry_count += 1
            # Only wait very briefly instead of 30 seconds
            if seconds > 1:
                await original_sleep(0.001)
            else:
                await original_sleep(seconds)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            # Start retry task
            retry_task = asyncio.create_task(worker._retry_nats_connection())

            # Wait for task to complete (should happen quickly with mocked sleep)
            await asyncio.wait_for(retry_task, timeout=1.0)

            # Verify connection established
            assert worker._nats_connected is True
            # Verify at least one retry attempt was made
            assert retry_count >= 1

    @pytest.mark.asyncio
    async def test_init_qdrant_success(
        self,
        worker,
    ) -> None:
        """
        Test successful Qdrant initialization.

        Verifies:
        - Checks collections
        - Sets connection flag
        - Updates readiness
        """
        await worker._init_qdrant()

        # Verify collections checked
        worker.service.qdrant._client.get_collections.assert_called_once()

        # Verify connection flag set
        assert worker._qdrant_connected is True

    @pytest.mark.asyncio
    async def test_init_qdrant_failure(
        self,
        worker,
    ) -> None:
        """
        Test Qdrant initialization failure.

        Verifies:
        - Logs warning
        - Spawns retry task
        - Connection flag remains False
        """
        # Mock get_collections to raise exception
        worker.service.qdrant._client.get_collections.side_effect = Exception(
            "Connection failed"
        )

        await worker._init_qdrant()

        # Verify connection flag not set
        assert worker._qdrant_connected is False

        # Verify retry task spawned
        assert len(worker._retry_tasks) == 1

    @pytest.mark.asyncio
    async def test_retry_qdrant_connection_eventually_succeeds(
        self,
        worker,
    ) -> None:
        """
        Test Qdrant retry eventually succeeds.

        Verifies:
        - Retry loop runs
        - Connection flag gets set when successful
        - Loop exits after success
        """
        # Track number of retry attempts
        retry_count = 0

        original_sleep = asyncio.sleep

        async def mock_sleep(seconds):
            """Mock sleep that counts retries and shortcuts the wait."""
            nonlocal retry_count
            retry_count += 1
            # Only wait very briefly instead of 30 seconds
            if seconds > 1:
                await original_sleep(0.001)
            else:
                await original_sleep(seconds)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            # Start retry task
            retry_task = asyncio.create_task(worker._retry_qdrant_connection())

            # Wait for task to complete (should happen quickly with mocked sleep)
            await asyncio.wait_for(retry_task, timeout=1.0)

            # Verify connection established
            assert worker._qdrant_connected is True
            # Verify at least one retry attempt was made
            assert retry_count >= 1


class TestProjectorWorkerReadiness:
    """Tests for readiness checking and health probe updates."""

    def test_is_ready_both_connected(self, worker) -> None:
        """
        Test readiness when both services connected.

        Verifies:
        - Returns True when both NATS and Qdrant connected
        """
        worker._nats_connected = True
        worker._qdrant_connected = True

        assert worker._is_ready() is True

    def test_is_ready_nats_not_connected(self, worker) -> None:
        """
        Test readiness when NATS not connected.

        Verifies:
        - Returns False
        """
        worker._nats_connected = False
        worker._qdrant_connected = True

        assert worker._is_ready() is False

    def test_is_ready_qdrant_not_connected(self, worker) -> None:
        """
        Test readiness when Qdrant not connected.

        Verifies:
        - Returns False
        """
        worker._nats_connected = True
        worker._qdrant_connected = False

        assert worker._is_ready() is False

    def test_is_ready_neither_connected(self, worker) -> None:
        """
        Test readiness when neither service connected.

        Verifies:
        - Returns False
        """
        worker._nats_connected = False
        worker._qdrant_connected = False

        assert worker._is_ready() is False

    def test_update_readiness(
        self,
        worker,
        mock_readiness_probe: MagicMock,
    ) -> None:
        """
        Test readiness probe update.

        Verifies:
        - Calls set_ready on health server
        - Passes correct readiness status
        """
        worker.health_server = mock_readiness_probe
        worker._nats_connected = True
        worker._qdrant_connected = True

        worker._update_readiness()

        # Verify set_ready called with True
        mock_readiness_probe.set_ready.assert_called_once_with(True)

    def test_update_readiness_no_health_server(self, worker) -> None:
        """
        Test update_readiness when health server not initialized.

        Verifies:
        - Does not crash
        """
        worker.health_server = None
        worker._nats_connected = True
        worker._qdrant_connected = True

        # Should not raise
        worker._update_readiness()


class TestProjectorWorkerCleanup:
    """Tests for resource cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_cancels_retry_tasks(
        self,
        worker,
    ) -> None:
        """
        Test cleanup cancels retry tasks.

        Verifies:
        - All retry tasks cancelled
        """
        # Create mock retry tasks
        task1 = MagicMock()
        task2 = MagicMock()
        worker._retry_tasks = [task1, task2]

        await worker.cleanup()

        # Verify both tasks cancelled
        task1.cancel.assert_called_once()
        task2.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_closes_subscriber(
        self,
        worker,
        mock_jetstream_subscriber: MagicMock,
    ) -> None:
        """
        Test cleanup closes NATS subscriber.

        Verifies:
        - Subscriber close() called
        """
        worker.subscriber = mock_jetstream_subscriber

        await worker.cleanup()

        # Verify subscriber closed
        mock_jetstream_subscriber.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_no_subscriber(
        self,
        worker,
    ) -> None:
        """
        Test cleanup when no subscriber initialized.

        Verifies:
        - Does not crash
        """
        worker.subscriber = None

        # Should not raise
        await worker.cleanup()
