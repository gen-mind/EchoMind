"""
Configuration for the Orchestrator Service.

Uses Pydantic Settings to load environment variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorSettings(BaseSettings):
    """Settings for the orchestrator service."""

    # Service Settings
    enabled: bool = Field(
        True,
        description="Enable orchestrator scheduling",
    )
    check_interval_seconds: int = Field(
        60,
        description="Interval between sync checks (configurable, not hardcoded)",
        gt=0,
    )
    max_concurrent_syncs: int = Field(
        5,
        description="Maximum concurrent sync operations",
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

    # Default Refresh Intervals (can be overridden per connector)
    default_refresh_web_minutes: int = Field(
        10080,
        description="Default refresh interval for web connectors (7 days)",
    )
    default_refresh_drive_minutes: int = Field(
        10080,
        description="Default refresh interval for drive connectors (7 days)",
    )
    default_refresh_chat_minutes: int = Field(
        1440,
        description="Default refresh interval for chat connectors (1 day)",
    )

    # Logging
    log_level: str = Field(
        "INFO",
        description="Logging level",
    )

    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_",
        env_file=".env",
        extra="ignore",
    )


_settings: OrchestratorSettings | None = None


def get_settings() -> OrchestratorSettings:
    """
    Get orchestrator settings from environment.

    Returns:
        OrchestratorSettings instance.
    """
    global _settings
    if _settings is None:
        # Pydantic settings loads values from env vars; defaults are in Field()
        _settings = OrchestratorSettings()  # type: ignore[call-arg]
    return _settings
