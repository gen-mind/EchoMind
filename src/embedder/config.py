"""
Configuration for the Embedder Service.

Uses Pydantic Settings to load environment variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbedderSettings(BaseSettings):
    """Settings for the embedder service."""

    # gRPC Server
    grpc_port: int = Field(
        50051,
        description="gRPC server port",
    )
    grpc_max_workers: int = Field(
        10,
        description="Maximum gRPC worker threads",
    )

    # Health Check
    health_port: int = Field(
        8080,
        description="Health check HTTP port",
    )

    # Model Configuration
    model_name: str = Field(
        "all-MiniLM-L6-v2",
        description="SentenceTransformer model name",
    )
    model_cache_limit: int = Field(
        1,
        description="Maximum number of models to cache in memory",
    )
    batch_size: int = Field(
        32,
        description="Batch size for encoding",
    )

    # Device
    prefer_gpu: bool = Field(
        True,
        description="Prefer GPU over CPU if available",
    )

    # Qdrant (vector storage)
    qdrant_host: str = Field(
        "localhost",
        description="Qdrant server hostname",
    )
    qdrant_port: int = Field(
        6333,
        description="Qdrant server port",
    )

    # Logging
    log_level: str = Field(
        "INFO",
        description="Logging level",
    )

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDER_",
        env_file=".env",
        extra="ignore",
    )


def get_settings() -> EmbedderSettings:
    """
    Get embedder settings from environment.

    Returns:
        EmbedderSettings instance.
    """
    return EmbedderSettings()
