"""
API service configuration using Pydantic Settings.

All configuration is loaded from environment variables.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API service configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # API Settings
    host: str = Field(default="0.0.0.0", description="API server host")
    port: int = Field(default=8000, description="API server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    reload: bool = Field(default=False, description="Enable auto-reload")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s",
        description="Log format string",
    )
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://echomind:echomind@localhost:5432/echomind",
        description="PostgreSQL connection URL",
    )
    database_echo: bool = Field(default=False, description="Log SQL statements")
    
    # Redis
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: str | None = Field(default=None, description="Redis password")
    
    # Qdrant
    qdrant_host: str = Field(default="localhost", description="Qdrant host")
    qdrant_port: int = Field(default=6333, description="Qdrant REST port")
    qdrant_api_key: str | None = Field(default=None, description="Qdrant API key")
    
    # MinIO
    minio_endpoint: str = Field(default="localhost:9000", description="MinIO endpoint")
    minio_access_key: str = Field(default="minioadmin", description="MinIO access key")
    minio_secret_key: str = Field(default="minioadmin", description="MinIO secret key")
    minio_secure: bool = Field(default=False, description="Use HTTPS for MinIO")
    minio_bucket: str = Field(default="echomind-documents", description="Default bucket")
    minio_public_endpoint: str | None = Field(
        default=None,
        description="Public MinIO endpoint for presigned URLs (e.g., https://s3.demo.echomind.ch). "
        "If not set, presigned URLs use the internal endpoint.",
    )
    
    # NATS
    nats_url: str = Field(default="nats://localhost:4222", description="NATS server URL")
    nats_user: str | None = Field(default=None, description="NATS username")
    nats_password: str | None = Field(default=None, description="NATS password")
    nats_connect_timeout: int = Field(default=30, description="NATS connection timeout in seconds")
    nats_reconnect_time_wait: int = Field(default=30, description="NATS reconnect wait time in seconds")
    nats_max_reconnect_attempts: int = Field(default=3, description="NATS max reconnect attempts")
    
    # Authentication
    auth_issuer: str = Field(
        default="https://auth.echomind.local",
        description="JWT issuer (Authentik URL)",
    )
    auth_audience: str = Field(default="echomind-api", description="JWT audience")
    auth_jwks_url: str | None = Field(
        default=None,
        description="JWKS URL for RS256 validation",
    )
    auth_secret: str | None = Field(
        default=None,
        description="Secret for HS256 validation (dev only)",
    )

    # OAuth/OIDC (for WebUI SSO login)
    oauth_client_id: str | None = Field(
        default=None,
        description="OAuth client ID for OIDC provider",
    )
    oauth_client_secret: str | None = Field(
        default=None,
        description="OAuth client secret",
    )
    oauth_provider_name: str = Field(
        default="Authentik",
        description="OAuth provider display name",
    )
    oauth_authorize_url: str | None = Field(
        default=None,
        description="OAuth authorization endpoint",
    )
    oauth_token_url: str | None = Field(
        default=None,
        description="OAuth token endpoint",
    )
    oauth_userinfo_url: str | None = Field(
        default=None,
        description="OAuth userinfo endpoint",
    )
    oauth_redirect_uri: str | None = Field(
        default=None,
        description="OAuth redirect URI (callback URL)",
    )
    oauth_scope: str = Field(
        default="openid profile email",
        description="OAuth scopes to request",
    )
    oauth_frontend_url: str | None = Field(
        default=None,
        description="Frontend URL for OAuth redirect (e.g., https://demo.echomind.ch)",
    )
    oauth_cookie_domain: str | None = Field(
        default=None,
        description="Cookie domain for cross-subdomain auth (e.g., .demo.echomind.ch)",
    )
    
    
    # Google OAuth (for Google Workspace integration)
    google_client_id: str | None = Field(
        default=None,
        description="Google OAuth client ID for Google Workspace integration",
    )
    google_client_secret: str | None = Field(
        default=None,
        description="Google OAuth client secret",
    )
    google_redirect_uri: str | None = Field(
        default=None,
        description="Google OAuth redirect URI (callback URL)",
    )

    # Embedder gRPC
    embedder_host: str = Field(default="localhost", description="Embedder gRPC host")
    embedder_port: int = Field(default=50051, description="Embedder gRPC port")
    embedder_timeout: float = Field(default=30.0, description="Embedder call timeout")

    # Langfuse (LLM Observability)
    langfuse_public_key: str | None = Field(
        default=None,
        description="Langfuse public API key",
    )
    langfuse_secret_key: str | None = Field(
        default=None,
        description="Langfuse secret API key",
    )
    langfuse_base_url: str = Field(
        default="http://langfuse-web:3000",
        description="Langfuse server URL",
    )

    # RAGAS Evaluation
    ragas_sample_rate: float = Field(
        default=0.1,
        description="Fraction of chat requests to evaluate with RAGAS (0.0-1.0)",
    )
    ragas_eval_llm_model: str | None = Field(
        default=None,
        description="Override LLM model for RAGAS evaluation",
    )
    ragas_eval_llm_endpoint: str | None = Field(
        default=None,
        description="Override LLM endpoint for RAGAS evaluation",
    )
    ragas_eval_llm_api_key: str | None = Field(
        default=None,
        description="Override API key for RAGAS evaluation LLM",
    )

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )
    
    # Health Check
    health_check_timeout: float = Field(
        default=5.0,
        description="Timeout for health checks in seconds",
    )
    
    @property
    def nats_servers(self) -> list[str]:
        """Get NATS servers as a list."""
        return [self.nats_url]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
