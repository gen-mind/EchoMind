"""Unit tests for Orchestrator main module retry/resilience pattern."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.main import Orchestrator


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock orchestrator settings."""
    settings = MagicMock()
    settings.enabled = True
    settings.check_interval_seconds = 60
    settings.health_port = 8080
    settings.database_url = "postgresql+asyncpg://user:pass@localhost:5432/echomind"
    settings.database_echo = False
    settings.nats_url = "nats://localhost:4222"
    settings.nats_user = None
    settings.nats_password = None
    settings.nats_connect_timeout = 5.0
    settings.nats_stream_name = "ECHOMIND"
    settings.nats_dlq_stream_name = "ECHOMIND_DLQ"
    return settings


@pytest.fixture
def orchestrator(mock_settings: MagicMock) -> Orchestrator:
    """Create Orchestrator instance with mocked settings."""
    with patch("orchestrator.main.get_settings", return_value=mock_settings):
        return Orchestrator()


class TestOrchestratorInit:
    """Tests for Orchestrator initialization state."""

    def test_initial_state_not_connected(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that connection flags start as False."""
        assert orchestrator._db_connected is False
        assert orchestrator._nats_connected is False

    def test_initial_state_not_running(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that running flag starts as False."""
        assert orchestrator._running is False

    def test_initial_state_no_retry_tasks(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that retry tasks list starts empty."""
        assert orchestrator._retry_tasks == []

    def test_initial_state_no_scheduler(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that scheduler starts as None."""
        assert orchestrator._scheduler is None

    def test_initial_state_no_health_server(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that health server starts as None."""
        assert orchestrator._health_server is None


class TestIsReady:
    """Tests for _is_ready() method."""

    def test_not_ready_when_nothing_connected(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test not ready when no connections established."""
        assert orchestrator._is_ready() is False

    def test_not_ready_when_only_db_connected(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test not ready when only database is connected."""
        orchestrator._db_connected = True
        assert orchestrator._is_ready() is False

    def test_not_ready_when_only_nats_connected(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test not ready when only NATS is connected."""
        orchestrator._nats_connected = True
        assert orchestrator._is_ready() is False

    def test_ready_when_all_connected(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test ready when both DB and NATS are connected."""
        orchestrator._db_connected = True
        orchestrator._nats_connected = True
        assert orchestrator._is_ready() is True


class TestUpdateReadiness:
    """Tests for _update_readiness() method."""

    def test_updates_health_server_ready(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that readiness is propagated to health server."""
        mock_health = MagicMock()
        orchestrator._health_server = mock_health
        orchestrator._db_connected = True
        orchestrator._nats_connected = True

        orchestrator._update_readiness()

        mock_health.set_ready.assert_called_once_with(True)

    def test_updates_health_server_not_ready(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that not-ready is propagated to health server."""
        mock_health = MagicMock()
        orchestrator._health_server = mock_health
        orchestrator._db_connected = False
        orchestrator._nats_connected = True

        orchestrator._update_readiness()

        mock_health.set_ready.assert_called_once_with(False)

    def test_no_crash_when_health_server_is_none(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test no crash when health server not yet initialized."""
        orchestrator._health_server = None
        orchestrator._update_readiness()  # Should not raise


class TestStartResilience:
    """Tests for start() method resilience pattern."""

    @pytest.mark.asyncio
    async def test_start_disabled_returns_early(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Test that disabled orchestrator returns early without connecting."""
        mock_settings.enabled = False

        with patch("orchestrator.main.get_settings", return_value=mock_settings):
            orch = Orchestrator()

        with patch("orchestrator.main.init_db") as mock_init_db:
            await orch.start()

            mock_init_db.assert_not_called()
            assert orch._running is False

    @pytest.mark.asyncio
    async def test_start_db_failure_spawns_retry(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that DB failure spawns background retry task, not crash."""
        with (
            patch("orchestrator.main.init_db", side_effect=ConnectionError("DB down")),
            patch.object(orchestrator, "_init_nats", new_callable=AsyncMock),
            patch("orchestrator.main.HealthServer") as mock_hs_cls,
            patch("orchestrator.main.AsyncIOScheduler") as mock_sched_cls,
            patch("orchestrator.main.threading"),
        ):
            mock_hs_cls.return_value = MagicMock()
            mock_sched_cls.return_value = MagicMock()

            await orchestrator.start()

            assert orchestrator._db_connected is False
            assert orchestrator._nats_connected is True
            assert len(orchestrator._retry_tasks) == 1
            assert orchestrator._running is True

            # Cleanup
            for task in orchestrator._retry_tasks:
                task.cancel()

    @pytest.mark.asyncio
    async def test_start_nats_failure_spawns_retry(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that NATS failure spawns background retry task, not crash."""
        with (
            patch("orchestrator.main.init_db", new_callable=AsyncMock),
            patch.object(
                orchestrator,
                "_init_nats",
                new_callable=AsyncMock,
                side_effect=ConnectionError("NATS down"),
            ),
            patch("orchestrator.main.HealthServer") as mock_hs_cls,
            patch("orchestrator.main.AsyncIOScheduler") as mock_sched_cls,
            patch("orchestrator.main.threading"),
        ):
            mock_hs_cls.return_value = MagicMock()
            mock_sched_cls.return_value = MagicMock()

            await orchestrator.start()

            assert orchestrator._db_connected is True
            assert orchestrator._nats_connected is False
            assert len(orchestrator._retry_tasks) == 1
            assert orchestrator._running is True

            for task in orchestrator._retry_tasks:
                task.cancel()

    @pytest.mark.asyncio
    async def test_start_both_failures_spawns_two_retry_tasks(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that both DB and NATS failures spawn two retry tasks."""
        with (
            patch("orchestrator.main.init_db", side_effect=ConnectionError("DB down")),
            patch.object(
                orchestrator,
                "_init_nats",
                new_callable=AsyncMock,
                side_effect=ConnectionError("NATS down"),
            ),
            patch("orchestrator.main.HealthServer") as mock_hs_cls,
            patch("orchestrator.main.AsyncIOScheduler") as mock_sched_cls,
            patch("orchestrator.main.threading"),
        ):
            mock_hs_cls.return_value = MagicMock()
            mock_sched_cls.return_value = MagicMock()

            await orchestrator.start()

            assert orchestrator._db_connected is False
            assert orchestrator._nats_connected is False
            assert len(orchestrator._retry_tasks) == 2
            assert orchestrator._running is True

            for task in orchestrator._retry_tasks:
                task.cancel()

    @pytest.mark.asyncio
    async def test_start_all_success_no_retry_tasks(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that successful startup creates no retry tasks."""
        with (
            patch("orchestrator.main.init_db", new_callable=AsyncMock),
            patch.object(orchestrator, "_init_nats", new_callable=AsyncMock),
            patch("orchestrator.main.HealthServer") as mock_hs_cls,
            patch("orchestrator.main.AsyncIOScheduler") as mock_sched_cls,
            patch("orchestrator.main.threading"),
        ):
            mock_hs_cls.return_value = MagicMock()
            mock_sched_cls.return_value = MagicMock()

            await orchestrator.start()

            assert orchestrator._db_connected is True
            assert orchestrator._nats_connected is True
            assert len(orchestrator._retry_tasks) == 0
            assert orchestrator._running is True
            assert orchestrator._is_ready() is True

    @pytest.mark.asyncio
    async def test_start_health_server_starts_first(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that health server is started before connection attempts."""
        call_order: list[str] = []

        async def track_init_db(*args: object, **kwargs: object) -> None:
            call_order.append("init_db")

        async def track_init_nats() -> None:
            call_order.append("init_nats")

        with (
            patch("orchestrator.main.init_db", side_effect=track_init_db),
            patch.object(orchestrator, "_init_nats", side_effect=track_init_nats),
            patch("orchestrator.main.HealthServer") as mock_hs_cls,
            patch("orchestrator.main.AsyncIOScheduler") as mock_sched_cls,
            patch("orchestrator.main.threading") as mock_threading,
        ):
            mock_hs_cls.return_value = MagicMock()
            mock_sched_cls.return_value = MagicMock()

            # Track Thread start call
            mock_thread = MagicMock()
            mock_threading.Thread.return_value = mock_thread

            def track_health_start() -> None:
                call_order.append("health_start")

            mock_thread.start = track_health_start

            await orchestrator.start()

            assert call_order.index("health_start") < call_order.index("init_db")
            assert call_order.index("health_start") < call_order.index("init_nats")

    @pytest.mark.asyncio
    async def test_start_scheduler_starts_regardless_of_connection_state(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that scheduler starts even when connections fail."""
        with (
            patch("orchestrator.main.init_db", side_effect=ConnectionError("DB down")),
            patch.object(
                orchestrator,
                "_init_nats",
                new_callable=AsyncMock,
                side_effect=ConnectionError("NATS down"),
            ),
            patch("orchestrator.main.HealthServer") as mock_hs_cls,
            patch("orchestrator.main.AsyncIOScheduler") as mock_sched_cls,
            patch("orchestrator.main.threading"),
        ):
            mock_hs_cls.return_value = MagicMock()
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler

            await orchestrator.start()

            mock_scheduler.start.assert_called_once()

            for task in orchestrator._retry_tasks:
                task.cancel()


class TestRetryDbConnection:
    """Tests for _retry_db_connection() background task."""

    @pytest.mark.asyncio
    async def test_retry_db_succeeds_on_second_attempt(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that DB retry succeeds and sets connected flag."""
        orchestrator._health_server = MagicMock()
        orchestrator._nats_connected = True  # Other connection already up
        call_count = 0

        async def mock_init_db(*args: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Still down")

        with (
            patch("orchestrator.main.init_db", side_effect=mock_init_db),
            patch("orchestrator.main.asyncio.sleep", new_callable=AsyncMock),
        ):
            # Run retry — will fail once, then succeed
            await orchestrator._retry_db_connection()

            assert orchestrator._db_connected is True
            assert call_count == 2
            orchestrator._health_server.set_ready.assert_called_with(True)

    @pytest.mark.asyncio
    async def test_retry_db_updates_readiness(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that successful DB retry updates readiness probe."""
        mock_health = MagicMock()
        orchestrator._health_server = mock_health
        orchestrator._nats_connected = True

        with (
            patch("orchestrator.main.init_db", new_callable=AsyncMock),
            patch("orchestrator.main.asyncio.sleep", new_callable=AsyncMock),
        ):
            await orchestrator._retry_db_connection()

            assert orchestrator._db_connected is True
            mock_health.set_ready.assert_called_with(True)


class TestRetryNatsConnection:
    """Tests for _retry_nats_connection() background task."""

    @pytest.mark.asyncio
    async def test_retry_nats_succeeds_on_second_attempt(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that NATS retry succeeds and sets connected flag."""
        orchestrator._health_server = MagicMock()
        orchestrator._db_connected = True
        call_count = 0

        async def mock_init_nats() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Still down")

        with patch("orchestrator.main.asyncio.sleep", new_callable=AsyncMock):
            orchestrator._init_nats = mock_init_nats  # type: ignore[assignment]
            await orchestrator._retry_nats_connection()

            assert orchestrator._nats_connected is True
            assert call_count == 2
            orchestrator._health_server.set_ready.assert_called_with(True)

    @pytest.mark.asyncio
    async def test_retry_nats_updates_readiness(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that successful NATS retry updates readiness probe."""
        mock_health = MagicMock()
        orchestrator._health_server = mock_health
        orchestrator._db_connected = True

        with patch("orchestrator.main.asyncio.sleep", new_callable=AsyncMock):
            orchestrator._init_nats = AsyncMock()  # type: ignore[assignment]
            await orchestrator._retry_nats_connection()

            assert orchestrator._nats_connected is True
            mock_health.set_ready.assert_called_with(True)


class TestSyncCheckJob:
    """Tests for _sync_check_job() method."""

    @pytest.mark.asyncio
    async def test_skips_when_not_running(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that sync job skips when orchestrator not running."""
        orchestrator._running = False
        orchestrator._db_connected = True
        orchestrator._nats_connected = True

        with patch("orchestrator.main.get_db_manager") as mock_get_db:
            await orchestrator._sync_check_job()
            mock_get_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_not_ready(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that sync job skips when connections not ready."""
        orchestrator._running = True
        orchestrator._db_connected = False
        orchestrator._nats_connected = True

        with patch("orchestrator.main.get_db_manager") as mock_get_db:
            await orchestrator._sync_check_job()
            mock_get_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_db_not_ready(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that sync job skips when DB not connected."""
        orchestrator._running = True
        orchestrator._db_connected = False
        orchestrator._nats_connected = False

        with patch("orchestrator.main.get_db_manager") as mock_get_db:
            await orchestrator._sync_check_job()
            mock_get_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_executes_when_ready(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that sync job executes when all connections ready."""
        orchestrator._running = True
        orchestrator._db_connected = True
        orchestrator._nats_connected = True

        mock_session = AsyncMock()
        mock_db = MagicMock()
        mock_db.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.session.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("orchestrator.main.get_db_manager", return_value=mock_db),
            patch("orchestrator.main.get_nats_publisher", return_value=AsyncMock()),
            patch(
                "orchestrator.main.OrchestratorService"
            ) as mock_svc_cls,
        ):
            mock_svc = AsyncMock()
            mock_svc.check_and_trigger_syncs = AsyncMock(return_value=2)
            mock_svc_cls.return_value = mock_svc

            await orchestrator._sync_check_job()

            mock_svc.check_and_trigger_syncs.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that sync job handles exceptions without crashing."""
        orchestrator._running = True
        orchestrator._db_connected = True
        orchestrator._nats_connected = True

        with patch(
            "orchestrator.main.get_db_manager",
            side_effect=RuntimeError("DB manager not initialized"),
        ):
            # Should not raise
            await orchestrator._sync_check_job()


class TestStop:
    """Tests for stop() method."""

    @pytest.mark.asyncio
    async def test_stop_cancels_retry_tasks(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that stop cancels all background retry tasks."""
        task1 = MagicMock()
        task2 = MagicMock()
        orchestrator._retry_tasks = [task1, task2]

        with (
            patch("orchestrator.main.close_nats_publisher", new_callable=AsyncMock),
            patch("orchestrator.main.close_db", new_callable=AsyncMock),
        ):
            await orchestrator.stop()

            task1.cancel.assert_called_once()
            task2.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that stop sets running flag to False."""
        orchestrator._running = True

        with (
            patch("orchestrator.main.close_nats_publisher", new_callable=AsyncMock),
            patch("orchestrator.main.close_db", new_callable=AsyncMock),
        ):
            await orchestrator.stop()

            assert orchestrator._running is False

    @pytest.mark.asyncio
    async def test_stop_marks_not_ready(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that stop marks health server as not ready."""
        mock_health = MagicMock()
        orchestrator._health_server = mock_health

        with (
            patch("orchestrator.main.close_nats_publisher", new_callable=AsyncMock),
            patch("orchestrator.main.close_db", new_callable=AsyncMock),
        ):
            await orchestrator.stop()

            mock_health.set_ready.assert_called_with(False)

    @pytest.mark.asyncio
    async def test_stop_shuts_down_scheduler(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that stop shuts down the scheduler."""
        mock_scheduler = MagicMock()
        orchestrator._scheduler = mock_scheduler

        with (
            patch("orchestrator.main.close_nats_publisher", new_callable=AsyncMock),
            patch("orchestrator.main.close_db", new_callable=AsyncMock),
        ):
            await orchestrator.stop()

            mock_scheduler.shutdown.assert_called_once_with(wait=False)

    @pytest.mark.asyncio
    async def test_stop_closes_connections(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that stop closes DB and NATS connections."""
        with (
            patch(
                "orchestrator.main.close_nats_publisher", new_callable=AsyncMock
            ) as mock_close_nats,
            patch(
                "orchestrator.main.close_db", new_callable=AsyncMock
            ) as mock_close_db,
        ):
            await orchestrator.stop()

            mock_close_nats.assert_called_once()
            mock_close_db.assert_called_once()


class TestInitNats:
    """Tests for _init_nats() method."""

    @pytest.mark.asyncio
    async def test_init_nats_creates_streams(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that _init_nats creates JetStream streams."""
        mock_publisher = AsyncMock()

        with patch(
            "orchestrator.main.init_nats_publisher",
            new_callable=AsyncMock,
            return_value=mock_publisher,
        ):
            await orchestrator._init_nats()

            # Should create main stream and DLQ stream
            assert mock_publisher.create_stream.call_count == 2

            # Verify stream names
            calls = mock_publisher.create_stream.call_args_list
            assert calls[0].kwargs["name"] == "ECHOMIND"
            assert calls[1].kwargs["name"] == "ECHOMIND_DLQ"

    @pytest.mark.asyncio
    async def test_init_nats_ignores_already_in_use_error(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that 'already in use' stream errors are silently ignored."""
        mock_publisher = AsyncMock()
        mock_publisher.create_stream.side_effect = Exception(
            "stream name already in use"
        )

        with patch(
            "orchestrator.main.init_nats_publisher",
            new_callable=AsyncMock,
            return_value=mock_publisher,
        ):
            # Should not raise
            await orchestrator._init_nats()

    @pytest.mark.asyncio
    async def test_init_nats_propagates_connection_error(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that NATS connection errors propagate up for retry handling."""
        with patch(
            "orchestrator.main.init_nats_publisher",
            new_callable=AsyncMock,
            side_effect=ConnectionError("NATS unreachable"),
        ):
            with pytest.raises(ConnectionError, match="NATS unreachable"):
                await orchestrator._init_nats()


class TestMaskUrl:
    """Tests for _mask_url() method."""

    def test_masks_password(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that password is masked in URL."""
        url = "postgresql+asyncpg://user:secretpass@localhost:5432/echomind"
        masked = orchestrator._mask_url(url)

        assert "secretpass" not in masked
        assert "***" in masked

    def test_returns_url_without_auth(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that URL without auth is returned unchanged."""
        url = "nats://localhost:4222"
        assert orchestrator._mask_url(url) == url

    def test_returns_simple_url_unchanged(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that simple URL without @ is returned unchanged."""
        url = "localhost:5432"
        assert orchestrator._mask_url(url) == url
