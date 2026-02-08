"""
Tests for NATS JetStream subscriber.

Covers subscription management, message handling, and connection lifecycle.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nats.js.api import ConsumerConfig, DeliverPolicy


@pytest.fixture
def mock_nats_client():
    """
    Create a mock NATS client.

    Returns:
        MagicMock: Mock NATS client instance
    """
    client = AsyncMock()
    client.jetstream = MagicMock(return_value=AsyncMock())
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_subscription():
    """
    Create a mock NATS subscription.

    Returns:
        AsyncMock: Mock subscription instance
    """
    sub = AsyncMock()
    sub.unsubscribe = AsyncMock()
    sub.fetch = AsyncMock(return_value=[])
    return sub


@pytest.fixture
async def subscriber(mock_nats_client):
    """
    Create a JetStreamSubscriber with mocked NATS connection.

    Args:
        mock_nats_client: Mocked NATS client

    Returns:
        JetStreamSubscriber: Subscriber instance for testing
    """
    from echomind_lib.db.nats_subscriber import JetStreamSubscriber

    with patch("nats.connect", return_value=mock_nats_client):
        subscriber = JetStreamSubscriber(servers=["nats://localhost:4222"])
        await subscriber.init()
        return subscriber


class TestJetStreamSubscriberInit:
    """Tests for initialization and connection."""

    @pytest.mark.asyncio
    async def test_init_success(
        self,
        mock_nats_client: AsyncMock,
    ) -> None:
        """
        Test successful NATS connection initialization.

        Verifies:
        - Connects to NATS
        - Creates JetStream context
        - Stores connection
        """
        from echomind_lib.db.nats_subscriber import JetStreamSubscriber

        with patch("nats.connect", return_value=mock_nats_client):
            subscriber = JetStreamSubscriber(servers=["nats://test:4222"])
            await subscriber.init()

            # Verify connection established
            assert subscriber._nc is not None
            assert subscriber._js is not None

    @pytest.mark.asyncio
    async def test_init_with_auth(
        self,
        mock_nats_client: AsyncMock,
    ) -> None:
        """
        Test initialization with username/password.

        Verifies:
        - Auth credentials passed to nats.connect
        """
        from echomind_lib.db.nats_subscriber import JetStreamSubscriber

        with patch("nats.connect", return_value=mock_nats_client) as mock_connect:
            subscriber = JetStreamSubscriber(
                servers=["nats://test:4222"],
                user="admin",
                password="secret",
            )
            await subscriber.init()

            # Verify auth passed
            mock_connect.assert_called_once_with(
                servers=["nats://test:4222"],
                user="admin",
                password="secret",
            )

    @pytest.mark.asyncio
    async def test_init_connection_error(
        self,
    ) -> None:
        """
        Test initialization failure.

        Verifies:
        - Exception propagates
        """
        from echomind_lib.db.nats_subscriber import JetStreamSubscriber

        with patch("nats.connect", side_effect=Exception("Connection failed")):
            subscriber = JetStreamSubscriber()

            with pytest.raises(Exception, match="Connection failed"):
                await subscriber.init()


class TestJetStreamSubscriberClose:
    """Tests for connection cleanup."""

    @pytest.mark.asyncio
    async def test_close_unsubscribes_all(
        self,
        subscriber,
        mock_subscription: AsyncMock,
    ) -> None:
        """
        Test close unsubscribes all subscriptions.

        Verifies:
        - Calls unsubscribe on each subscription
        - Clears subscription list
        """
        # Add mock subscriptions
        subscriber._subscriptions = [mock_subscription, mock_subscription]

        await subscriber.close()

        # Verify all unsubscribed
        assert mock_subscription.unsubscribe.call_count == 2
        assert len(subscriber._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_close_closes_connection(
        self,
        subscriber,
    ) -> None:
        """
        Test close closes NATS connection.

        Verifies:
        - Calls nc.close()
        - Nulls out connection references
        """
        # Save reference to mock before close nulls it
        mock_nc = subscriber._nc

        await subscriber.close()

        # Verify connection closed
        mock_nc.close.assert_called_once()
        assert subscriber._nc is None
        assert subscriber._js is None

    @pytest.mark.asyncio
    async def test_close_no_connection(
        self,
    ) -> None:
        """
        Test close when not connected.

        Verifies:
        - Does not crash
        """
        from echomind_lib.db.nats_subscriber import JetStreamSubscriber

        subscriber = JetStreamSubscriber()

        # Should not raise
        await subscriber.close()


class TestJetStreamSubscriberJSProperty:
    """Tests for JetStream context property."""

    @pytest.mark.asyncio
    async def test_js_property_when_initialized(
        self,
        subscriber,
    ) -> None:
        """
        Test js property returns context when initialized.

        Verifies:
        - Returns JetStream context
        """
        js = subscriber.js

        assert js is not None
        assert js == subscriber._js

    def test_js_property_not_initialized(
        self,
    ) -> None:
        """
        Test js property raises when not initialized.

        Verifies:
        - Raises RuntimeError
        """
        from echomind_lib.db.nats_subscriber import JetStreamSubscriber

        subscriber = JetStreamSubscriber()

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = subscriber.js


class TestJetStreamSubscriberSubscribe:
    """Tests for push-based subscription."""

    @pytest.mark.asyncio
    async def test_subscribe_success(
        self,
        subscriber,
        mock_subscription: AsyncMock,
    ) -> None:
        """
        Test successful push subscription.

        Verifies:
        - Calls js.subscribe with correct parameters
        - Uses deliver_group for queue-based load balancing
        - Stores subscription
        """
        subscriber._js.subscribe = AsyncMock(return_value=mock_subscription)

        async def handler(msg):
            await msg.ack()

        await subscriber.subscribe(
            stream="test-stream",
            consumer="test-consumer",
            subject="test.subject",
            handler=handler,
        )

        # Verify subscribe called
        subscriber._js.subscribe.assert_called_once()
        call_args = subscriber._js.subscribe.call_args

        # Verify parameters
        assert call_args.args[0] == "test.subject"
        assert call_args.kwargs["stream"] == "test-stream"
        assert call_args.kwargs["cb"] == handler

        # Verify consumer config
        config: ConsumerConfig = call_args.kwargs["config"]
        assert config.durable_name == "test-consumer"
        assert config.deliver_group == "test-consumer"  # Queue-based load balancing
        assert config.max_deliver == 3
        assert config.ack_wait == 30

        # Verify subscription stored
        assert len(subscriber._subscriptions) == 1

    @pytest.mark.asyncio
    async def test_subscribe_custom_policy(
        self,
        subscriber,
        mock_subscription: AsyncMock,
    ) -> None:
        """
        Test subscription with custom deliver policy.

        Verifies:
        - Custom deliver_policy passed through
        """
        subscriber._js.subscribe = AsyncMock(return_value=mock_subscription)

        async def handler(msg):
            pass

        await subscriber.subscribe(
            stream="test-stream",
            consumer="test-consumer",
            subject="test.subject",
            handler=handler,
            deliver_policy=DeliverPolicy.NEW,
            max_deliver=5,
        )

        call_args = subscriber._js.subscribe.call_args
        config: ConsumerConfig = call_args.kwargs["config"]

        assert config.deliver_policy == DeliverPolicy.NEW
        assert config.max_deliver == 5


class TestJetStreamSubscriberPullSubscribe:
    """Tests for pull-based subscription."""

    @pytest.mark.asyncio
    async def test_pull_subscribe_success(
        self,
        subscriber,
        mock_subscription: AsyncMock,
    ) -> None:
        """
        Test successful pull subscription.

        Verifies:
        - Calls js.pull_subscribe with correct parameters
        - Uses deliver_group for queue-based load balancing
        - Returns subscription object
        - Stores subscription
        """
        subscriber._js.pull_subscribe = AsyncMock(return_value=mock_subscription)

        sub = await subscriber.pull_subscribe(
            stream="test-stream",
            consumer="test-consumer",
            subject="test.subject",
        )

        # Verify pull_subscribe called
        subscriber._js.pull_subscribe.assert_called_once()
        call_args = subscriber._js.pull_subscribe.call_args

        # Verify parameters
        assert call_args.args[0] == "test.subject"
        assert call_args.kwargs["durable"] == "test-consumer"
        assert call_args.kwargs["stream"] == "test-stream"

        # Verify consumer config
        config: ConsumerConfig = call_args.kwargs["config"]
        assert config.durable_name == "test-consumer"
        assert config.deliver_group == "test-consumer"  # Queue-based load balancing
        assert config.ack_wait == 30

        # Verify subscription returned and stored
        assert sub == mock_subscription
        assert len(subscriber._subscriptions) == 1


class TestJetStreamSubscriberFetchMessages:
    """Tests for fetching messages from pull subscription."""

    @pytest.mark.asyncio
    async def test_fetch_messages_success(
        self,
        subscriber,
        mock_subscription: AsyncMock,
    ) -> None:
        """
        Test successful message fetch.

        Verifies:
        - Calls subscription.fetch
        - Returns messages
        """
        mock_msg1 = MagicMock()
        mock_msg2 = MagicMock()
        mock_subscription.fetch = AsyncMock(return_value=[mock_msg1, mock_msg2])

        messages = await subscriber.fetch_messages(
            subscription=mock_subscription,
            batch_size=10,
            timeout=5.0,
        )

        # Verify fetch called
        mock_subscription.fetch.assert_called_once_with(10, timeout=5.0)

        # Verify messages returned
        assert len(messages) == 2
        assert messages == [mock_msg1, mock_msg2]

    @pytest.mark.asyncio
    async def test_fetch_messages_timeout(
        self,
        subscriber,
        mock_subscription: AsyncMock,
    ) -> None:
        """
        Test fetch timeout handling.

        Verifies:
        - Returns empty list on timeout
        - Does not raise
        """
        mock_subscription.fetch = AsyncMock(side_effect=asyncio.TimeoutError())

        messages = await subscriber.fetch_messages(
            subscription=mock_subscription,
            batch_size=10,
            timeout=1.0,
        )

        # Verify empty list returned (not exception)
        assert messages == []


class TestGlobalSubscriberFunctions:
    """Tests for global singleton subscriber management."""

    @pytest.mark.asyncio
    async def test_init_nats_subscriber(
        self,
        mock_nats_client: AsyncMock,
    ) -> None:
        """
        Test global subscriber initialization.

        Verifies:
        - Creates and initializes subscriber
        - Stores in global variable
        """
        from echomind_lib.db.nats_subscriber import (
            init_nats_subscriber,
            get_nats_subscriber,
            close_nats_subscriber,
        )

        with patch("nats.connect", return_value=mock_nats_client):
            await init_nats_subscriber(servers=["nats://test:4222"])

            # Verify global set
            subscriber = get_nats_subscriber()
            assert subscriber is not None

            # Cleanup
            await close_nats_subscriber()

    def test_get_nats_subscriber_not_initialized(
        self,
    ) -> None:
        """
        Test get_nats_subscriber when not initialized.

        Verifies:
        - Raises RuntimeError
        """
        from echomind_lib.db.nats_subscriber import (
            get_nats_subscriber,
            close_nats_subscriber,
            _nats_subscriber,
        )

        # Ensure global is None (cleanup from previous tests)
        import echomind_lib.db.nats_subscriber as module
        module._nats_subscriber = None

        with pytest.raises(RuntimeError, match="not initialized"):
            get_nats_subscriber()

    @pytest.mark.asyncio
    async def test_close_nats_subscriber(
        self,
        mock_nats_client: AsyncMock,
    ) -> None:
        """
        Test global subscriber cleanup.

        Verifies:
        - Closes subscriber
        - Nulls out global variable
        """
        from echomind_lib.db.nats_subscriber import (
            init_nats_subscriber,
            close_nats_subscriber,
        )

        import echomind_lib.db.nats_subscriber as module

        with patch("nats.connect", return_value=mock_nats_client):
            await init_nats_subscriber()
            await close_nats_subscriber()

            # Verify global nulled
            assert module._nats_subscriber is None

    @pytest.mark.asyncio
    async def test_close_nats_subscriber_not_initialized(
        self,
    ) -> None:
        """
        Test close when not initialized.

        Verifies:
        - Does not crash
        """
        from echomind_lib.db.nats_subscriber import close_nats_subscriber

        import echomind_lib.db.nats_subscriber as module
        module._nats_subscriber = None

        # Should not raise
        await close_nats_subscriber()
