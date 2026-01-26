"""
WebSocket connection manager.

Manages active WebSocket connections and message broadcasting.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    """Represents an active WebSocket connection."""
    
    websocket: WebSocket
    user_id: int
    session_ids: set[int] = field(default_factory=set)


class ConnectionManager:
    """
    Manages WebSocket connections for chat streaming.
    
    Usage:
        manager = ConnectionManager()
        
        # On connect
        await manager.connect(websocket, user_id)
        
        # Subscribe to session
        manager.subscribe(user_id, session_id)
        
        # Send message to user
        await manager.send_to_user(user_id, message)
        
        # Send message to session subscribers
        await manager.send_to_session(session_id, message)
        
        # On disconnect
        manager.disconnect(user_id)
    """
    
    def __init__(self) -> None:
        """Initialize connection manager."""
        self._connections: dict[int, Connection] = {}
        self._session_subscribers: dict[int, set[int]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            user_id: User ID
        """
        await websocket.accept()
        
        async with self._lock:
            # Close existing connection for this user if any
            if user_id in self._connections:
                old_conn = self._connections[user_id]
                try:
                    await old_conn.websocket.close(code=1000, reason="New connection")
                except Exception:
                    pass
            
            self._connections[user_id] = Connection(
                websocket=websocket,
                user_id=user_id,
            )
        
        logger.info(f"🔌 User {user_id} connected via WebSocket")
    
    def disconnect(self, user_id: int) -> None:
        """
        Remove a WebSocket connection.
        
        Args:
            user_id: User ID
        """
        if user_id in self._connections:
            conn = self._connections[user_id]
            
            # Unsubscribe from all sessions
            for session_id in conn.session_ids:
                if session_id in self._session_subscribers:
                    self._session_subscribers[session_id].discard(user_id)
                    if not self._session_subscribers[session_id]:
                        del self._session_subscribers[session_id]
            
            del self._connections[user_id]
            logger.info(f"🔌 User {user_id} disconnected from WebSocket")
    
    def subscribe(self, user_id: int, session_id: int) -> None:
        """
        Subscribe a user to a chat session.
        
        Args:
            user_id: User ID
            session_id: Chat session ID
        """
        if user_id not in self._connections:
            return
        
        self._connections[user_id].session_ids.add(session_id)
        
        if session_id not in self._session_subscribers:
            self._session_subscribers[session_id] = set()
        self._session_subscribers[session_id].add(user_id)
    
    def unsubscribe(self, user_id: int, session_id: int) -> None:
        """
        Unsubscribe a user from a chat session.
        
        Args:
            user_id: User ID
            session_id: Chat session ID
        """
        if user_id in self._connections:
            self._connections[user_id].session_ids.discard(session_id)
        
        if session_id in self._session_subscribers:
            self._session_subscribers[session_id].discard(user_id)
            if not self._session_subscribers[session_id]:
                del self._session_subscribers[session_id]
    
    async def send_to_user(self, user_id: int, message: dict[str, Any]) -> bool:
        """
        Send a message to a specific user.
        
        Args:
            user_id: User ID
            message: Message dict to send
        
        Returns:
            True if sent successfully
        """
        if user_id not in self._connections:
            return False
        
        try:
            await self._connections[user_id].websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send message to user {user_id}: {e}")
            self.disconnect(user_id)
            return False
    
    async def send_to_session(self, session_id: int, message: dict[str, Any]) -> int:
        """
        Send a message to all subscribers of a session.
        
        Args:
            session_id: Chat session ID
            message: Message dict to send
        
        Returns:
            Number of users message was sent to
        """
        if session_id not in self._session_subscribers:
            return 0
        
        sent_count = 0
        failed_users = []
        
        for user_id in self._session_subscribers[session_id]:
            if await self.send_to_user(user_id, message):
                sent_count += 1
            else:
                failed_users.append(user_id)
        
        # Clean up failed connections
        for user_id in failed_users:
            self.disconnect(user_id)
        
        return sent_count
    
    async def broadcast(self, message: dict[str, Any]) -> int:
        """
        Broadcast a message to all connected users.
        
        Args:
            message: Message dict to send
        
        Returns:
            Number of users message was sent to
        """
        sent_count = 0
        failed_users = []
        
        for user_id in list(self._connections.keys()):
            if await self.send_to_user(user_id, message):
                sent_count += 1
            else:
                failed_users.append(user_id)
        
        # Clean up failed connections
        for user_id in failed_users:
            self.disconnect(user_id)
        
        return sent_count
    
    def is_connected(self, user_id: int) -> bool:
        """Check if a user is connected."""
        return user_id in self._connections
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self._connections)
    
    def get_session_subscriber_count(self, session_id: int) -> int:
        """Get number of subscribers for a session."""
        return len(self._session_subscribers.get(session_id, set()))


_connection_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
