"""
NATS JetStream publisher for message queue operations.

Provides async publishing to NATS JetStream streams.
"""

import nats
from nats.js import JetStreamContext


class JetStreamPublisher:
    """
    Async NATS JetStream publisher.
    
    Usage:
        publisher = JetStreamPublisher(servers=["nats://localhost:4222"])
        await publisher.init()
        
        await publisher.publish("stream.subject", message_bytes)
        
        await publisher.close()
    """
    
    def __init__(
        self,
        servers: list[str] | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        """
        Initialize NATS publisher.
        
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
    
    async def init(self, timeout: float = 5.0) -> None:
        """Connect to NATS and initialize JetStream context."""
        import asyncio
        self._nc = await asyncio.wait_for(
            nats.connect(
                servers=self._servers,
                user=self._user,
                password=self._password,
                connect_timeout=timeout,
                max_reconnect_attempts=0,
            ),
            timeout=timeout,
        )
        self._js = self._nc.jetstream()
    
    async def close(self) -> None:
        """Close the NATS connection."""
        if self._nc:
            await self._nc.close()
            self._nc = None
            self._js = None
    
    @property
    def js(self) -> JetStreamContext:
        """Get the JetStream context."""
        if self._js is None:
            raise RuntimeError("Publisher not initialized")
        return self._js
    
    async def publish(
        self,
        subject: str,
        payload: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Publish a message to a subject.
        
        Args:
            subject: Target subject (e.g., "documents.process")
            payload: Message payload as bytes
            headers: Optional message headers
        """
        await self.js.publish(subject, payload, headers=headers)
    
    async def create_stream(
        self,
        name: str,
        subjects: list[str],
        max_msgs: int = -1,
        max_bytes: int = -1,
        max_age: int = 0,
    ) -> None:
        """
        Create or update a JetStream stream.
        
        Args:
            name: Stream name
            subjects: List of subjects to capture
            max_msgs: Max messages (-1 = unlimited)
            max_bytes: Max bytes (-1 = unlimited)
            max_age: Max age in nanoseconds (0 = unlimited)
        """
        await self.js.add_stream(
            name=name,
            subjects=subjects,
            max_msgs=max_msgs,
            max_bytes=max_bytes,
            max_age=max_age,
        )
    
    async def delete_stream(self, name: str) -> bool:
        """Delete a stream."""
        return await self.js.delete_stream(name)


_nats_publisher: JetStreamPublisher | None = None


def get_nats_publisher() -> JetStreamPublisher:
    """Get the global NATS publisher instance."""
    if _nats_publisher is None:
        raise RuntimeError("NATS publisher not initialized. Call init_nats_publisher() first.")
    return _nats_publisher


async def init_nats_publisher(
    servers: list[str] | None = None,
    user: str | None = None,
    password: str | None = None,
    timeout: float = 5.0,
) -> JetStreamPublisher:
    """Initialize the global NATS publisher."""
    global _nats_publisher
    _nats_publisher = JetStreamPublisher(servers=servers, user=user, password=password)
    await _nats_publisher.init(timeout=timeout)
    return _nats_publisher


async def close_nats_publisher() -> None:
    """Close the global NATS publisher."""
    global _nats_publisher
    if _nats_publisher is not None:
        await _nats_publisher.close()
        _nats_publisher = None
