"""
EchoMind API Service - FastAPI Application.

Main entry point for the REST API and WebSocket server.
"""

import logging
import os

from dotenv import load_dotenv

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

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.middleware.error_handler import setup_error_handlers
from api.routes import assistants, chat, connectors, documents, embedding_models, health, llms, users
from api.websocket.chat_handler import ChatHandler
from echomind_lib.db.connection import close_db, init_db
from echomind_lib.db.nats_publisher import close_nats_publisher, init_nats_publisher
from echomind_lib.db.minio import close_minio, init_minio
from echomind_lib.db.qdrant import close_qdrant, init_qdrant
from echomind_lib.db.redis import close_redis, init_redis
from echomind_lib.helpers.auth import init_jwt_validator
from echomind_lib.helpers.readiness_probe import (
    get_readiness_probe,
    HealthCheckResult,
    HealthStatus,
)


async def _check_database() -> HealthCheckResult:
    """Health check for database connection."""
    try:
        from echomind_lib.db.connection import get_db_manager
        db = get_db_manager()
        async with db.session() as session:
            await session.execute("SELECT 1")
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
        redis = get_redis()
        await redis.ping()
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
        await qdrant.get_collections()
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
        from echomind_lib.db.nats_publisher import get_nats
        nats = get_nats()
        if nats.is_connected:
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Initializes and closes all service connections.
    """
    settings = get_settings()
    
    # Initialize services
    await init_db(settings.database_url, echo=settings.database_echo)
    await init_redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
    )
    await init_qdrant(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )
    await init_minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    init_jwt_validator(
        issuer=settings.auth_issuer,
        audience=settings.auth_audience,
        jwks_url=settings.auth_jwks_url,
        secret=settings.auth_secret,
    )
    await init_nats_publisher(
        servers=[settings.nats_url],
        user=settings.nats_user,
        password=settings.nats_password,
    )
    
    # Register health checks for readiness probe
    _register_health_checks(settings.health_check_timeout)
    
    yield
    
    # Cleanup
    await close_db()
    await close_redis()
    await close_qdrant()
    close_minio()
    await close_nats_publisher()


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
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(assistants.router, prefix="/api/v1/assistants", tags=["Assistants"])
    app.include_router(llms.router, prefix="/api/v1/llms", tags=["LLMs"])
    app.include_router(embedding_models.router, prefix="/api/v1/embedding-models", tags=["Embedding Models"])
    app.include_router(connectors.router, prefix="/api/v1/connectors", tags=["Connectors"])
    app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
    app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
    
    # WebSocket endpoint
    chat_handler = ChatHandler()
    
    @app.websocket("/api/v1/ws/chat")
    async def websocket_chat(websocket: WebSocket, token: str | None = None):
        """WebSocket endpoint for real-time chat."""
        await chat_handler.handle_connection(websocket, token)
    
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
