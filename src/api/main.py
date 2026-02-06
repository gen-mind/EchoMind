"""
EchoMind API Service - FastAPI Application.

Main entry point for the REST API and WebSocket server.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.config import get_settings
from api.middleware.error_handler import setup_error_handlers
from api.routes import (
    assistants,
    auth,
    chat,
    connectors,
    documents,
    embedding_models,
    health,
    llms,
    oauth,
    teams,
    upload,
    users,
    webui_compat,
)
from api.logic.embedder_client import close_embedder_client, init_embedder_client
from api.logic.llm_client import close_llm_client
from api.socketio_server import socket_app
from api.websocket.chat_handler import create_chat_handler
from echomind_lib.db.connection import close_db, get_db_manager, init_db
from echomind_lib.constants import MinioBuckets
from echomind_lib.db.minio import close_minio, init_minio
from echomind_lib.db.nats_publisher import close_nats_publisher, init_nats_publisher
from echomind_lib.db.qdrant import close_qdrant, init_qdrant
from echomind_lib.helpers.auth import init_jwt_validator
from echomind_lib.helpers.readiness_probe import (
    HealthCheckResult,
    HealthStatus,
    get_readiness_probe,
)

if TYPE_CHECKING:
    from api.config import Settings

# Load environment variables from .env file
load_dotenv()

# Configure logging (use API_ prefix per naming convention)
log_level_str = os.getenv("API_LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
log_format = os.getenv(
    "API_LOG_FORMAT",
    "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s",
)
logging.basicConfig(level=log_level, format=log_format)
logger = logging.getLogger(__name__)

# Suppress noisy NATS library errors
logging.getLogger("nats.aio.client").setLevel(logging.CRITICAL)
logging.getLogger("nats.aio.transport").setLevel(logging.CRITICAL)


async def _check_database() -> HealthCheckResult:
    """Health check for database connection."""
    try:
        from echomind_lib.db.connection import get_db_manager

        db = get_db_manager()
        async with db.session() as session:
            await session.execute(text("SELECT 1"))
        return HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Connected",
        )
    except Exception as e:
        return HealthCheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


async def _check_redis() -> HealthCheckResult:
    """Health check for Redis connection."""
    try:
        from echomind_lib.db.redis import get_redis

        redis_client = get_redis()
        # Access internal client to call ping - justified for health check
        result = redis_client.client.ping()  # type: ignore[union-attr]
        if hasattr(result, "__await__"):
            await result
        return HealthCheckResult(
            name="redis",
            status=HealthStatus.HEALTHY,
            message="Connected",
        )
    except Exception as e:
        return HealthCheckResult(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


async def _check_qdrant() -> HealthCheckResult:
    """Health check for Qdrant connection."""
    try:
        from echomind_lib.db.qdrant import get_qdrant

        qdrant = get_qdrant()
        # Access internal client to check collections - justified for health check
        await qdrant._client.get_collections()
        return HealthCheckResult(
            name="qdrant",
            status=HealthStatus.HEALTHY,
            message="Connected",
        )
    except Exception as e:
        return HealthCheckResult(
            name="qdrant",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


async def _check_nats() -> HealthCheckResult:
    """Health check for NATS connection."""
    try:
        from echomind_lib.db.nats_publisher import get_nats_publisher

        publisher = get_nats_publisher()
        # Access internal NATS client to check connection - justified for health check
        if publisher._nc is not None and publisher._nc.is_connected:
            return HealthCheckResult(
                name="nats",
                status=HealthStatus.HEALTHY,
                message="Connected",
            )
        return HealthCheckResult(
            name="nats",
            status=HealthStatus.UNHEALTHY,
            message="Not connected",
        )
    except Exception as e:
        return HealthCheckResult(
            name="nats",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


def _register_health_checks(timeout: float) -> None:
    """Register all health checks with the readiness probe."""
    probe = get_readiness_probe()
    probe._timeout = timeout
    probe.register("database", _check_database)
    probe.register("redis", _check_redis)
    probe.register("qdrant", _check_qdrant)
    probe.register("nats", _check_nats)
    logger.info("Registered health checks: database, redis, qdrant, nats")


async def _retry_db_connection(settings: Settings) -> None:
    """Background task to retry database connection."""
    while True:
        await asyncio.sleep(30)
        try:
            await init_db(settings.database_url, echo=settings.database_echo)
            logger.info("🗄️ Database reconnected")
            break
        except Exception as e:
            logger.warning(f"⚠️ Database reconnection attempt failed: {e}")


async def _retry_qdrant_connection(settings: Settings) -> None:
    """Background task to retry Qdrant connection."""
    while True:
        await asyncio.sleep(30)
        try:
            await init_qdrant(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key,
            )
            logger.info("🔍 Qdrant reconnected")
            break
        except Exception as e:
            logger.warning(f"⚠️ Qdrant reconnection attempt failed: {e}")


async def _retry_minio_connection(settings: Settings) -> None:
    """Background task to retry MinIO connection."""
    while True:
        await asyncio.sleep(30)
        try:
            await init_minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
                ensure_buckets=MinioBuckets.all(),
                public_endpoint=settings.minio_public_endpoint,
            )
            logger.info(f"📦 MinIO reconnected (buckets: {MinioBuckets.all()})")
            break
        except Exception as e:
            logger.warning(f"⚠️ MinIO reconnection attempt failed: {e}")


async def _retry_nats_connection(settings: Settings) -> None:
    """Background task to retry NATS connection."""
    while True:
        await asyncio.sleep(30)
        try:
            await init_nats_publisher(
                servers=[settings.nats_url],
                user=settings.nats_user,
                password=settings.nats_password,
            )
            logger.info("📡 NATS publisher reconnected")
            break
        except Exception as e:
            logger.warning(f"⚠️ NATS reconnection attempt failed: {e}")


async def _retry_embedder_connection(settings: Settings) -> None:
    """Background task to retry Embedder gRPC client connection."""
    while True:
        await asyncio.sleep(30)
        try:
            await init_embedder_client(
                host=settings.embedder_host,
                port=settings.embedder_port,
                timeout=settings.embedder_timeout,
            )
            logger.info("🔗 Embedder gRPC client reconnected")
            break
        except Exception as e:
            logger.warning(f"⚠️ Embedder client reconnection attempt failed: {e}")


async def _retry_jwt_connection(settings: Settings) -> None:
    """Background task to retry JWT validator initialization."""
    while True:
        await asyncio.sleep(30)
        try:
            init_jwt_validator(
                issuer=settings.auth_issuer,
                audience=settings.auth_audience,
                jwks_url=settings.auth_jwks_url,
                secret=settings.auth_secret,
            )
            logger.info("🔑 JWT validator reconnected")
            break
        except Exception as e:
            logger.warning(f"⚠️ JWT validator reconnection attempt failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Initializes and closes all service connections.
    """
    settings = get_settings()
    retry_tasks: list[asyncio.Task[None]] = []

    # Initialize services - non-blocking, app starts even if services unavailable
    try:
        await init_db(settings.database_url, echo=settings.database_echo)
        logger.info("🗄️ Database connected")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization failed: {e}")
        logger.info("🔄 Will retry database connection in background...")
        retry_tasks.append(asyncio.create_task(_retry_db_connection(settings)))

    # Redis disabled for now
    # try:
    #     await init_redis(
    #         host=settings.redis_host,
    #         port=settings.redis_port,
    #         password=settings.redis_password,
    #     )
    #     logger.info("✅ Redis connected successfully")
    # except Exception as e:
    #     logger.warning(f"⚠️ Redis initialization failed: {e}")
    #     logger.info("🔄 Will retry Redis connection in background...")

    try:
        await init_qdrant(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
        )
        logger.info("🔍 Qdrant connected")
    except Exception as e:
        logger.warning(f"⚠️ Qdrant initialization failed: {e}")
        logger.info("🔄 Will retry Qdrant connection in background...")
        retry_tasks.append(asyncio.create_task(_retry_qdrant_connection(settings)))

    try:
        await init_minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            ensure_buckets=MinioBuckets.all(),
        )
        logger.info(f"📦 MinIO connected (buckets: {MinioBuckets.all()})")
    except Exception as e:
        logger.warning(f"⚠️ MinIO initialization failed: {e}")
        logger.info("🔄 Will retry MinIO connection in background...")
        retry_tasks.append(asyncio.create_task(_retry_minio_connection(settings)))

    try:
        init_jwt_validator(
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
            jwks_url=settings.auth_jwks_url,
            secret=settings.auth_secret,
        )
        logger.info("🔑 JWT validator initialized")
    except Exception as e:
        logger.warning(f"⚠️ JWT validator initialization failed: {e}")
        logger.info("🔄 Will retry JWT validator in background...")
        retry_tasks.append(asyncio.create_task(_retry_jwt_connection(settings)))

    try:
        await init_nats_publisher(
            servers=[settings.nats_url],
            user=settings.nats_user,
            password=settings.nats_password,
        )
        logger.info("📡 NATS publisher connected")
    except Exception as e:
        logger.warning(f"⚠️ NATS publisher initialization failed: {e}")
        logger.info("🔄 Will retry NATS connection in background...")
        retry_tasks.append(asyncio.create_task(_retry_nats_connection(settings)))

    # Initialize Embedder gRPC client for chat search
    try:
        await init_embedder_client(
            host=settings.embedder_host,
            port=settings.embedder_port,
            timeout=settings.embedder_timeout,
        )
        logger.info("🔗 Embedder gRPC client connected")
    except Exception as e:
        logger.warning(f"⚠️ Embedder client initialization failed: {e}")
        logger.info("🔄 Will retry Embedder client in background...")
        retry_tasks.append(asyncio.create_task(_retry_embedder_connection(settings)))

    # Register health checks for readiness probe
    _register_health_checks(settings.health_check_timeout)

    yield

    # Cancel all retry tasks
    for task in retry_tasks:
        task.cancel()

    # Cleanup
    try:
        await close_db()
    except Exception:
        pass

    # Redis disabled
    # try:
    #     await close_redis()
    # except Exception:
    #     pass

    try:
        await close_qdrant()
    except Exception:
        pass

    try:
        close_minio()
    except Exception:
        pass

    try:
        await close_nats_publisher()
    except Exception:
        pass

    try:
        await close_embedder_client()
    except Exception:
        pass

    try:
        await close_llm_client()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="EchoMind API",
        description="Agentic RAG Platform API",
        version="0.1.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # Register error handlers
    setup_error_handlers(app)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, tags=["Health"])  # Root level for /health
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])  # Versioned

    # Open WebUI compatibility endpoints (without /v1 prefix)
    # These enable the Open WebUI SvelteKit frontend to function with EchoMind backend
    app.include_router(
        webui_compat.router, prefix="/api", tags=["WebUI Compatibility"]
    )

    # OAuth endpoints for WebUI SSO login
    # Mounted at /oauth (not /api/oauth) as expected by Open WebUI frontend
    app.include_router(oauth.router, prefix="/oauth", tags=["OAuth"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(
        assistants.router, prefix="/api/v1/assistants", tags=["Assistants"]
    )
    app.include_router(llms.router, prefix="/api/v1/llms", tags=["LLMs"])
    app.include_router(
        embedding_models.router,
        prefix="/api/v1/embedding-models",
        tags=["Embedding Models"],
    )
    app.include_router(
        connectors.router, prefix="/api/v1/connectors", tags=["Connectors"]
    )
    app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
    app.include_router(
        upload.router, prefix="/api/v1/documents/upload", tags=["Upload"]
    )
    app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
    app.include_router(teams.router, prefix="/api/v1/teams", tags=["Teams"])

    # WebSocket endpoint
    @app.websocket("/api/v1/ws/chat")
    async def websocket_chat(websocket: WebSocket, token: str | None = None) -> None:
        """
        WebSocket endpoint for real-time chat.

        Creates a new ChatHandler per connection with its own DB session
        for proper transaction management.
        """
        if token is None:
            await websocket.close(code=4001, reason="Token required")
            return

        # Get DB session for this connection
        db_manager = get_db_manager()
        async with db_manager.session() as db:
            handler = create_chat_handler(db)
            await handler.handle_connection(websocket, token)

    # Mount Socket.IO for Open WebUI real-time communication
    # Frontend connects with path: '/ws/socket.io', so mount at /ws
    # and socketio_path is set in socket_app constructor
    app.mount("/ws", socket_app)
    logger.info("🌐 Socket.IO mounted at /ws (path: /ws/socket.io)")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
