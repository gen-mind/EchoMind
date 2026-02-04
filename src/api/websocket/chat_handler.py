"""
WebSocket chat handler for real-time streaming.

Handles chat messages and streams responses back to clients.
Integrates with ChatService for retrieval-augmented generation.
"""

import asyncio
import json
import logging
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from api.logic.chat_service import ChatService, RetrievedSource
from api.logic.embedder_client import get_embedder_client
from api.logic.exceptions import NotFoundError, ServiceUnavailableError
from api.logic.llm_client import get_llm_client
from api.websocket.manager import ConnectionManager, get_connection_manager
from echomind_lib.db.qdrant import get_qdrant
from echomind_lib.helpers.auth import TokenUser, get_jwt_validator

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

    Integrates with ChatService for full RAG pipeline:
    1. Receive query via WebSocket
    2. Retrieve relevant context from Qdrant
    3. Stream LLM response tokens
    4. Persist messages to database

    Usage:
        handler = ChatHandler(db_session)
        await handler.handle_connection(websocket, token)
    """

    def __init__(
        self,
        db: AsyncSession,
        manager: ConnectionManager | None = None,
    ):
        """
        Initialize chat handler.

        Args:
            db: Database session for persistence.
            manager: Connection manager (uses global if not provided).
        """
        self._db = db
        self._manager = manager
        self._active_generations: dict[int, asyncio.Task[None]] = {}

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
            websocket: WebSocket connection.
            token: JWT token for authentication.
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
            logger.info("💔 User %d disconnected", user.id)
        except Exception as e:
            logger.error("❌ WebSocket error for user %d: %s", user.id, e)
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
            logger.info("🛑 Cancelled generation for user %d", user.id)

    async def _process_chat(
        self,
        user: TokenUser,
        session_id: int,
        query: str,
        mode: str,
    ) -> None:
        """
        Process a chat query and stream the response.

        Full RAG pipeline:
        1. Validate session ownership
        2. Embed query and retrieve context
        3. Stream LLM response
        4. Save messages to database
        """
        try:
            # Initialize service with dependencies
            service = ChatService(
                db=self._db,
                qdrant=get_qdrant(),
                embedder=get_embedder_client(),
                llm=get_llm_client(),
            )

            # Validate session and get assistant config
            try:
                session = await service.get_session(session_id, user)
            except NotFoundError:
                await self._send_error(
                    user.id,
                    "SESSION_NOT_FOUND",
                    f"Chat session {session_id} not found",
                )
                return

            # Send retrieval start
            await self.manager.send_to_user(user.id, {
                "type": MessageType.RETRIEVAL_START,
                "session_id": session_id,
                "query": query,
                "rephrased_query": query,  # TODO: Implement query rephrasing
            })

            # Retrieve relevant context
            try:
                sources = await service.retrieve_context(
                    query=query,
                    user=user,
                    limit=5,
                    min_score=0.4,
                )
            except ServiceUnavailableError as e:
                await self._send_error(
                    user.id,
                    "RETRIEVAL_ERROR",
                    f"Retrieval failed: {e.message}",
                )
                return

            # Get document titles for display
            doc_ids = [s.document_id for s in sources if s.document_id]
            titles = await service.get_document_titles(doc_ids)

            # Send retrieval complete with sources
            await self.manager.send_to_user(user.id, {
                "type": MessageType.RETRIEVAL_COMPLETE,
                "session_id": session_id,
                "sources": [
                    {
                        "document_id": s.document_id,
                        "chunk_id": s.chunk_id,
                        "score": s.score,
                        "title": titles.get(s.document_id, s.title),
                        "snippet": s.content[:200] + "..." if len(s.content) > 200 else s.content,
                    }
                    for s in sources
                ],
            })

            # Save user message
            user_message = await service.save_user_message(
                session_id=session_id,
                content=query,
            )
            await self._db.commit()

            if mode == "search":
                # Search mode - no generation needed
                await self.manager.send_to_user(user.id, {
                    "type": MessageType.GENERATION_COMPLETE,
                    "session_id": session_id,
                    "message_id": user_message.id,
                    "token_count": 0,
                })
                return

            # Stream LLM response
            response_content = ""
            token_count = 0
            current_task = asyncio.current_task()

            try:
                async for token in service.stream_response(
                    session=session,
                    query=query,
                    sources=sources,
                    user=user,
                ):
                    if current_task is not None and current_task.cancelled():
                        return

                    response_content += token
                    token_count += 1

                    await self.manager.send_to_user(user.id, {
                        "type": MessageType.GENERATION_TOKEN,
                        "session_id": session_id,
                        "token": token,
                    })

            except ServiceUnavailableError as e:
                await self._send_error(
                    user.id,
                    "GENERATION_ERROR",
                    f"LLM generation failed: {e.message}",
                )
                return

            # Save assistant message with sources
            assistant_message = await service.save_assistant_message(
                session_id=session_id,
                content=response_content,
                sources=sources,
                parent_message_id=user_message.id,
            )
            await self._db.commit()

            # Send generation complete
            await self.manager.send_to_user(user.id, {
                "type": MessageType.GENERATION_COMPLETE,
                "session_id": session_id,
                "message_id": assistant_message.id,
                "token_count": token_count,
            })

            logger.info(
                "🏁 Chat completed for user %d session %d: %d tokens, %d sources",
                user.id,
                session_id,
                token_count,
                len(sources),
            )

        except asyncio.CancelledError:
            logger.info("🛑 Generation cancelled for user %d", user.id)
            raise
        except Exception as e:
            logger.exception("❌ Error processing chat for user %d: %s", user.id, e)
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


# Factory function for creating handlers with DB session
def create_chat_handler(db: AsyncSession) -> ChatHandler:
    """
    Create a ChatHandler with database session.

    Args:
        db: Async database session.

    Returns:
        Configured ChatHandler.
    """
    return ChatHandler(db=db)
