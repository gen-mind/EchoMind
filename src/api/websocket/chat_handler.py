"""
WebSocket chat handler for real-time streaming.

Handles chat messages and streams responses back to clients.
"""

import asyncio
import json
import logging
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from api.websocket.manager import ConnectionManager, get_connection_manager
from echomind_lib.helpers.auth import TokenUser, extract_bearer_token, get_jwt_validator

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    
    # Client -> Server
    CHAT_START = "chat.start"
    CHAT_CANCEL = "chat.cancel"
    PING = "ping"
    
    # Server -> Client
    RETRIEVAL_START = "retrieval.start"
    RETRIEVAL_COMPLETE = "retrieval.complete"
    GENERATION_TOKEN = "generation.token"
    GENERATION_COMPLETE = "generation.complete"
    ERROR = "error"
    PONG = "pong"


class ChatHandler:
    """
    Handles WebSocket chat interactions.
    
    Usage:
        handler = ChatHandler()
        await handler.handle_connection(websocket, token)
    """
    
    def __init__(
        self,
        manager: ConnectionManager | None = None,
    ):
        """
        Initialize chat handler.
        
        Args:
            manager: Connection manager (uses global if not provided)
        """
        self._manager = manager
        self._active_generations: dict[int, asyncio.Task] = {}
    
    @property
    def manager(self) -> ConnectionManager:
        """Get the connection manager."""
        if self._manager:
            return self._manager
        return get_connection_manager()
    
    async def handle_connection(self, websocket: WebSocket, token: str) -> None:
        """
        Handle a WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            token: JWT token for authentication
        """
        # Authenticate
        try:
            validator = get_jwt_validator()
            user = validator.validate_token(token)
        except Exception as e:
            await websocket.close(code=4001, reason=f"Authentication failed: {e}")
            return
        
        # Connect
        await self.manager.connect(websocket, user.id)
        
        try:
            await self._message_loop(websocket, user)
        except WebSocketDisconnect:
            logger.info(f"User {user.id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for user {user.id}: {e}")
        finally:
            # Cancel any active generations
            if user.id in self._active_generations:
                self._active_generations[user.id].cancel()
                del self._active_generations[user.id]
            
            self.manager.disconnect(user.id)
    
    async def _message_loop(self, websocket: WebSocket, user: TokenUser) -> None:
        """Process incoming messages."""
        while True:
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await self._send_error(user.id, "INVALID_JSON", "Invalid JSON message")
                continue
            
            msg_type = data.get("type")
            
            if msg_type == MessageType.PING:
                await self.manager.send_to_user(user.id, {"type": MessageType.PONG})
            
            elif msg_type == MessageType.CHAT_START:
                await self._handle_chat_start(user, data)
            
            elif msg_type == MessageType.CHAT_CANCEL:
                await self._handle_chat_cancel(user, data)
            
            else:
                await self._send_error(
                    user.id,
                    "UNKNOWN_MESSAGE_TYPE",
                    f"Unknown message type: {msg_type}",
                )
    
    async def _handle_chat_start(self, user: TokenUser, data: dict[str, Any]) -> None:
        """Handle chat.start message."""
        session_id = data.get("session_id")
        query = data.get("query")
        mode = data.get("mode", "chat")
        
        if not session_id or not query:
            await self._send_error(
                user.id,
                "INVALID_REQUEST",
                "session_id and query are required",
            )
            return
        
        # Cancel any existing generation for this user
        if user.id in self._active_generations:
            self._active_generations[user.id].cancel()
        
        # Subscribe to session
        self.manager.subscribe(user.id, session_id)
        
        # Start generation task
        task = asyncio.create_task(
            self._process_chat(user, session_id, query, mode)
        )
        self._active_generations[user.id] = task
    
    async def _handle_chat_cancel(self, user: TokenUser, data: dict[str, Any]) -> None:
        """Handle chat.cancel message."""
        if user.id in self._active_generations:
            self._active_generations[user.id].cancel()
            del self._active_generations[user.id]
            logger.info(f"Cancelled generation for user {user.id}")
    
    async def _process_chat(
        self,
        user: TokenUser,
        session_id: int,
        query: str,
        mode: str,
    ) -> None:
        """
        Process a chat query and stream the response.
        
        This is where the agent orchestration would happen.
        """
        try:
            # Send retrieval start
            await self.manager.send_to_user(user.id, {
                "type": MessageType.RETRIEVAL_START,
                "session_id": session_id,
                "query": query,
                "rephrased_query": query,  # TODO: Implement query rephrasing
            })
            
            # TODO: Implement actual retrieval
            # 1. Rephrase query using LLM
            # 2. Embed query
            # 3. Search Qdrant for relevant chunks
            # 4. Return sources
            
            await asyncio.sleep(0.5)  # Simulate retrieval
            
            # Send retrieval complete
            sources = []  # TODO: Get actual sources
            await self.manager.send_to_user(user.id, {
                "type": MessageType.RETRIEVAL_COMPLETE,
                "session_id": session_id,
                "sources": sources,
            })
            
            if mode == "search":
                # Search mode - no generation needed
                await self.manager.send_to_user(user.id, {
                    "type": MessageType.GENERATION_COMPLETE,
                    "session_id": session_id,
                    "message_id": None,
                    "token_count": 0,
                })
                return
            
            # TODO: Implement actual LLM generation with streaming
            # 1. Build prompt with context
            # 2. Call LLM with streaming
            # 3. Stream tokens back to client
            # 4. Save message to database
            
            # Simulate streaming response
            response = "This is a placeholder response. The actual implementation would stream tokens from the LLM."
            token_count = 0
            
            for word in response.split():
                if asyncio.current_task().cancelled():
                    return
                
                await self.manager.send_to_user(user.id, {
                    "type": MessageType.GENERATION_TOKEN,
                    "session_id": session_id,
                    "token": word + " ",
                })
                token_count += 1
                await asyncio.sleep(0.05)  # Simulate token delay
            
            # Send generation complete
            await self.manager.send_to_user(user.id, {
                "type": MessageType.GENERATION_COMPLETE,
                "session_id": session_id,
                "message_id": 0,  # TODO: Return actual message ID
                "token_count": token_count,
            })
            
        except asyncio.CancelledError:
            logger.info(f"Generation cancelled for user {user.id}")
            raise
        except Exception as e:
            logger.error(f"Error processing chat for user {user.id}: {e}")
            await self._send_error(user.id, "GENERATION_ERROR", str(e))
        finally:
            if user.id in self._active_generations:
                del self._active_generations[user.id]
    
    async def _send_error(self, user_id: int, code: str, message: str) -> None:
        """Send an error message to a user."""
        await self.manager.send_to_user(user_id, {
            "type": MessageType.ERROR,
            "code": code,
            "message": message,
        })


_chat_handler: ChatHandler | None = None


def get_chat_handler() -> ChatHandler:
    """Get the global chat handler instance."""
    global _chat_handler
    if _chat_handler is None:
        _chat_handler = ChatHandler()
    return _chat_handler
