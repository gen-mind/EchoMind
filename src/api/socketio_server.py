"""Socket.IO server for real-time WebUI communication.

Provides real-time bidirectional event-based communication
matching the Open WebUI frontend Socket.IO protocol.

The frontend connects with: io(url, { path: '/ws/socket.io', ... })
Events expected: connect (with auth token), user-join, heartbeat, disconnect.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import socketio

logger = logging.getLogger(__name__)

# Create async Socket.IO server with CORS support
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# Wrap in ASGI app with correct socketio_path
# Frontend connects to /ws/socket.io, FastAPI mounts at /ws
socket_app = socketio.ASGIApp(sio, socketio_path="/ws/socket.io")


@sio.event
async def connect(sid: str, environ: dict[str, Any], auth: dict[str, Any] | None = None) -> None:
    """
    Handle client connection with optional token authentication.

    Args:
        sid: Socket session ID.
        environ: WSGI environment dict.
        auth: Authentication data from client (contains 'token').
    """
    token = auth.get("token") if auth else None
    if token:
        logger.info(f"🌐 Socket.IO client connected: {sid} (authenticated)")
    else:
        logger.info(f"🌐 Socket.IO client connected: {sid} (anonymous)")


@sio.event
async def disconnect(sid: str) -> None:
    """
    Handle client disconnection.

    Args:
        sid: Socket session ID.
    """
    logger.info(f"💔 Socket.IO client disconnected: {sid}")


@sio.on("user-join")
async def user_join(sid: str, data: dict[str, Any] | None = None) -> None:
    """
    Handle user-join event from Open WebUI frontend.

    Called after connection to associate user with their session.

    Args:
        sid: Socket session ID.
        data: User data (may contain user ID, token).
    """
    logger.info(f"👤 User joined via Socket.IO: {sid}")


@sio.on("heartbeat")
async def heartbeat(sid: str, data: dict[str, Any] | None = None) -> None:
    """
    Handle heartbeat event for tracking active users.

    Args:
        sid: Socket session ID.
        data: Heartbeat data.
    """
    logger.debug(f"💓 Heartbeat from {sid}")


@sio.on("usage")
async def usage(sid: str, data: dict[str, Any] | None = None) -> None:
    """
    Handle usage tracking event.

    Args:
        sid: Socket session ID.
        data: Usage data (model, tokens, etc).
    """
    logger.debug(f"📊 Usage report from {sid}")


# Utility functions for emitting events from other parts of the app


async def emit_chat_event(event: str, data: dict[str, Any], room: str | None = None) -> None:
    """
    Emit a chat event to a specific room or all clients.

    Args:
        event: Event name.
        data: Event data to broadcast.
        room: Optional room to target.
    """
    if room:
        await sio.emit(event, data, room=room)
    else:
        await sio.emit(event, data)
    logger.debug(f"📡 Emitted '{event}' to {room or 'all'}")
