"""
Configuration for the Migration Service.

Uses Pydantic Settings to load environment variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MigrationSettings(BaseSettings):
    """Settings for the migration service."""

    # Database (sync driver for Alembic)
    database_url: str = Field(
        ...,
        description="PostgreSQL connection URL (postgresql://user:pass@host:port/db)",
    )

    # Migration settings
    retry_count: int = Field(
        5,
        description="Number of retries if database is not ready",
    )
    retry_delay: int = Field(
        5,
        description="Seconds between retries",
    )

    # Logging
    log_level: str = Field(
        "INFO",
        description="Logging level",
    )

    model_config = SettingsConfigDict(
        env_prefix="MIGRATION_",
        env_file=".env",
        extra="ignore",
    )


def get_settings() -> MigrationSettings:
    """
    Get migration settings from environment.

    Returns:
        MigrationSettings instance.
    """
    return MigrationSettings()
