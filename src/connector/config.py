"""
Configuration for the Connector Service.

Uses Pydantic Settings to load environment variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConnectorSettings(BaseSettings):
    """Settings for the connector service."""

    # Service Settings
    enabled: bool = Field(
        True,
        description="Enable connector service",
    )
    max_concurrent_downloads: int = Field(
        5,
        description="Maximum concurrent file downloads",
        gt=0,
    )
    max_file_size_bytes: int = Field(
        100 * 1024 * 1024,  # 100MB
        description="Maximum file size to download",
        gt=0,
    )
    google_export_max_size_bytes: int = Field(
        10 * 1024 * 1024,  # 10MB - Google API limit
        description="Maximum size for Google Workspace export",
        gt=0,
    )

    # Health Check
    health_port: int = Field(
        8080,
        description="Health check HTTP port",
    )

    # Database
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/echomind",
        description="PostgreSQL connection URL",
    )
    database_echo: bool = Field(
        False,
        description="Log SQL statements",
    )

    # NATS
    nats_url: str = Field(
        "nats://localhost:4222",
        description="NATS server URL",
    )
    nats_user: str | None = Field(
        None,
        description="NATS username",
    )
    nats_password: str | None = Field(
        None,
        description="NATS password",
    )
    nats_connect_timeout: float = Field(
        5.0,
        description="NATS connection timeout in seconds",
    )
    nats_stream_name: str = Field(
        "ECHOMIND",
        description="NATS JetStream stream name",
    )
    nats_consumer_name: str = Field(
        "connector-consumer",
        description="NATS consumer durable name",
    )

    # MinIO
    minio_endpoint: str = Field(
        "localhost:9000",
        description="MinIO server endpoint",
    )
    minio_access_key: str = Field(
        "minioadmin",
        description="MinIO access key",
    )
    minio_secret_key: str = Field(
        "minioadmin",
        description="MinIO secret key",
    )
    minio_secure: bool = Field(
        False,
        description="Use HTTPS for MinIO",
    )
    minio_bucket: str = Field(
        "echomind-documents",
        description="MinIO bucket for document storage",
    )

    # Google Drive
    google_service_account_json: str | None = Field(
        None,
        description="Path to Google service account JSON file",
    )
    google_client_id: str | None = Field(
        None,
        description="Google OAuth2 client ID",
    )
    google_client_secret: str | None = Field(
        None,
        description="Google OAuth2 client secret",
    )

    # Microsoft Graph (OneDrive)
    ms_graph_client_id: str | None = Field(
        None,
        description="Microsoft Graph client ID",
    )
    ms_graph_client_secret: str | None = Field(
        None,
        description="Microsoft Graph client secret",
    )
    ms_graph_tenant_id: str | None = Field(
        None,
        description="Microsoft Graph tenant ID",
    )

    # Retry Settings
    max_retries: int = Field(
        3,
        description="Maximum retry attempts for failed operations",
        ge=0,
    )
    retry_base_delay: float = Field(
        1.0,
        description="Base delay in seconds for exponential backoff",
        gt=0,
    )

    # Logging
    log_level: str = Field(
        "INFO",
        description="Logging level",
    )

    model_config = SettingsConfigDict(
        env_prefix="CONNECTOR_",
        env_file=".env",
        extra="ignore",
    )


_settings: ConnectorSettings | None = None


def get_settings() -> ConnectorSettings:
    """
    Get connector settings from environment.

    Returns:
        ConnectorSettings instance.
    """
    global _settings
    if _settings is None:
        # Pydantic settings loads values from env vars; defaults are in Field()
        _settings = ConnectorSettings()  # type: ignore[call-arg]
    return _settings


def reset_settings() -> None:
    """
    Reset settings for testing.

    Clears the cached settings instance.
    """
    global _settings
    _settings = None
