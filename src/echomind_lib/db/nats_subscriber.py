"""
NATS JetStream subscriber for message queue consumption.

Provides async subscription to NATS JetStream streams with message acknowledgment.
"""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import nats
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy


class JetStreamSubscriber:
    """
    Async NATS JetStream subscriber.
    
    Usage:
        subscriber = JetStreamSubscriber(servers=["nats://localhost:4222"])
        await subscriber.init()
        
        async def handler(msg):
            print(f"Received: {msg.data}")
            await msg.ack()
        
        await subscriber.subscribe("stream", "consumer", "subject", handler)
        
        await subscriber.close()
    """
    
    def __init__(
        self,
        servers: list[str] | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        """
        Initialize NATS subscriber.
        
        Args:
            servers: List of NATS server URLs
            user: Optional username
            password: Optional password
        """
        self._servers = servers or ["nats://localhost:4222"]
        self._user = user
        self._password = password
        self._nc: nats.NATS | None = None
        self._js: JetStreamContext | None = None
        self._subscriptions: list[Any] = []
    
    async def init(self) -> None:
        """Connect to NATS and initialize JetStream context."""
        self._nc = await nats.connect(
            servers=self._servers,
            user=self._user,
            password=self._password,
        )
        self._js = self._nc.jetstream()
    
    async def close(self) -> None:
        """Unsubscribe all and close the NATS connection."""
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions.clear()
        
        if self._nc:
            await self._nc.close()
            self._nc = None
            self._js = None
    
    @property
    def js(self) -> JetStreamContext:
        """Get the JetStream context."""
        if self._js is None:
            raise RuntimeError("Subscriber not initialized")
        return self._js
    
    async def subscribe(
        self,
        stream: str,
        consumer: str,
        subject: str,
        handler: Callable[[Any], Coroutine[Any, Any, None]],
        deliver_policy: DeliverPolicy = DeliverPolicy.ALL,
        max_deliver: int = 3,
    ) -> None:
        """
        Subscribe to a subject with a durable consumer.
        
        Args:
            stream: Stream name
            consumer: Durable consumer name
            subject: Subject to subscribe to
            handler: Async callback for messages
            deliver_policy: Message delivery policy
            max_deliver: Max redelivery attempts
        """
        config = ConsumerConfig(
            durable_name=consumer,
            deliver_policy=deliver_policy,
            deliver_group=consumer,  # Enable queue-based load balancing
            max_deliver=max_deliver,
            ack_wait=30,  # 30 seconds to ack
        )
        
        sub = await self.js.subscribe(
            subject,
            stream=stream,
            config=config,
            cb=handler,
        )
        self._subscriptions.append(sub)
    
    async def pull_subscribe(
        self,
        stream: str,
        consumer: str,
        subject: str,
        batch_size: int = 10,
    ) -> Any:
        """
        Create a pull-based subscription.
        
        Args:
            stream: Stream name
            consumer: Durable consumer name
            subject: Subject filter
            batch_size: Messages to fetch per pull
        
        Returns:
            Pull subscription object
        """
        config = ConsumerConfig(
            durable_name=consumer,
            deliver_group=consumer,  # Enable queue-based load balancing
            ack_wait=30,
        )
        
        sub = await self.js.pull_subscribe(
            subject,
            durable=consumer,
            stream=stream,
            config=config,
        )
        self._subscriptions.append(sub)
        return sub
    
    async def fetch_messages(
        self,
        subscription: Any,
        batch_size: int = 10,
        timeout: float = 5.0,
    ) -> list[Any]:
        """
        Fetch messages from a pull subscription.
        
        Args:
            subscription: Pull subscription object
            batch_size: Max messages to fetch
            timeout: Timeout in seconds
        
        Returns:
            List of messages
        """
        try:
            return await subscription.fetch(batch_size, timeout=timeout)
        except asyncio.TimeoutError:
            return []


_nats_subscriber: JetStreamSubscriber | None = None


def get_nats_subscriber() -> JetStreamSubscriber:
    """Get the global NATS subscriber instance."""
    if _nats_subscriber is None:
        raise RuntimeError("NATS subscriber not initialized. Call init_nats_subscriber() first.")
    return _nats_subscriber


async def init_nats_subscriber(
    servers: list[str] | None = None,
    user: str | None = None,
    password: str | None = None,
) -> JetStreamSubscriber:
    """Initialize the global NATS subscriber."""
    global _nats_subscriber
    _nats_subscriber = JetStreamSubscriber(servers=servers, user=user, password=password)
    await _nats_subscriber.init()
    return _nats_subscriber


async def close_nats_subscriber() -> None:
    """Close the global NATS subscriber."""
    global _nats_subscriber
    if _nats_subscriber is not None:
        await _nats_subscriber.close()
        _nats_subscriber = None
