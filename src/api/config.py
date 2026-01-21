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
