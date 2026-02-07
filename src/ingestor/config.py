"""
Configuration for the Ingestor Service.

Uses Pydantic Settings to load environment variables.
All settings prefixed with INGESTOR_ for namespace isolation.
"""

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestorSettings(BaseSettings):
    """
    Settings for the Ingestor service.

    All environment variables are prefixed with INGESTOR_.
    Example: INGESTOR_DATABASE_URL, INGESTOR_NATS_URL
    """

    # Service Settings
    enabled: bool = Field(
        True,
        description="Enable ingestor service",
    )
    health_port: int = Field(
        8080,
        description="Health check HTTP port",
    )

    # Database
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/echomind",
        description="PostgreSQL async connection URL",
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
        gt=0,
    )
    nats_stream_name: str = Field(
        "ECHOMIND",
        description="NATS JetStream stream name",
    )
    nats_consumer_name: str = Field(
        "ingestor-consumer",
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

    # Qdrant
    qdrant_host: str = Field(
        "localhost",
        description="Qdrant server hostname",
    )
    qdrant_port: int = Field(
        6333,
        description="Qdrant REST API port",
    )
    qdrant_api_key: str | None = Field(
        None,
        description="Qdrant API key for authentication",
    )

    # Embedder gRPC
    embedder_host: str = Field(
        "echomind-embedder",
        description="Embedder service hostname",
    )
    embedder_port: int = Field(
        50051,
        description="Embedder gRPC port",
    )
    # TODO: Revert to 30s once embedder runs on GPU. Currently 600s
    # because CPU inference takes ~200s per batch with the 1B model.
    embedder_timeout: float = Field(
        600.0,
        description="gRPC call timeout in seconds",
        gt=0,
    )

    # nv_ingest_api Settings
    extract_method: str = Field(
        "pdfium",
        description="PDF extraction method: pdfium | pdfium_hybrid | nemotron_parse",
    )
    chunk_size: int = Field(
        1024,
        description="Chunk size in TOKENS (not characters). NVIDIA recommends 512-1024 for enterprise docs.",
        gt=0,
        le=8192,
    )
    chunk_overlap: int = Field(
        124,
        description="Chunk overlap in TOKENS. NVIDIA research shows 10-20% overlap optimal (154 tokens = 15% for size 1024).",
        ge=0,
    )
    tokenizer: str = Field(
        "nvidia/llama-nemotron-embed-1b-v2",
        description="HuggingFace tokenizer for chunking (must match embedding model for perfect alignment)",
    )
    text_depth: str = Field(
        "page",
        description="Text extraction granularity: 'document' (full doc) or 'page' (per-page). "
                    "NVIDIA research shows 'page' achieves highest accuracy (0.648).",
    )
    hf_access_token: str | None = Field(
        None,
        description="HuggingFace access token (REQUIRED for meta-llama/Llama-3.2-1B tokenizer). "
                    "Get token at: https://huggingface.co/settings/tokens",
    )

    # Optional NIMs
    yolox_enabled: bool = Field(
        False,
        description="Enable YOLOX NIM for table/chart detection (requires yolox-nim service)",
    )
    yolox_endpoint: str = Field(
        "http://yolox-nim:8000",
        description="YOLOX NIM endpoint",
    )
    riva_enabled: bool = Field(
        False,
        description="Enable Riva NIM for audio transcription",
    )
    riva_endpoint: str = Field(
        "riva:50051",
        description="Riva NIM gRPC endpoint (host:port, no http:// prefix)",
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
        env_prefix="INGESTOR_",
        env_file=".env",
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """
        Validate log level is valid.

        Args:
            v: Log level string.

        Returns:
            Uppercase log level.

        Raises:
            ValueError: If log level is invalid.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()

    @field_validator("extract_method")
    @classmethod
    def validate_extract_method(cls, v: str) -> str:
        """
        Validate extraction method.

        Args:
            v: Extraction method string.

        Returns:
            Validated extraction method.

        Raises:
            ValueError: If extraction method is invalid.
        """
        valid_methods = {"pdfium", "pdfium_hybrid", "nemotron_parse"}
        if v not in valid_methods:
            raise ValueError(f"Invalid extract method: {v}. Must be one of {valid_methods}")
        return v

    @field_validator("text_depth")
    @classmethod
    def validate_text_depth(cls, v: str) -> str:
        """
        Validate text_depth parameter.

        Args:
            v: Text depth string.

        Returns:
            Validated text_depth.

        Raises:
            ValueError: If text_depth is invalid.
        """
        valid_values = {"document", "page"}
        if v not in valid_values:
            raise ValueError(
                f"Invalid text_depth: {v}. Must be one of {valid_values}. "
                f"NVIDIA recommends 'page' for best retrieval accuracy."
            )
        return v

    @model_validator(mode="after")
    def validate_hf_token_for_gated_models(self) -> "IngestorSettings":
        """
        Validate HF token is provided for gated tokenizers.

        Raises:
            ValueError: If using gated tokenizer without token (CRITICAL).
        """
        import logging
        logger = logging.getLogger("echomind-ingestor.config")

        # CRITICAL: Gated models REQUIRE HF token
        gated_model_patterns = [
            "meta-llama/Llama-3.2",
            "meta-llama/Llama-3",
            "nvidia/llama-nemotron",
        ]

        is_gated = any(pattern in self.tokenizer for pattern in gated_model_patterns)

        if is_gated:
            if not self.hf_access_token:
                raise ValueError(
                    f"❌ CRITICAL: HuggingFace access token is MANDATORY for tokenizer '{self.tokenizer}'. "
                    f"This is a gated model that requires authentication. "
                    f"Set INGESTOR_HF_ACCESS_TOKEN environment variable. "
                    f"Get token at: https://huggingface.co/settings/tokens "
                    f"Accept license at: https://huggingface.co/{self.tokenizer}"
                )
            logger.info(f"✅ HuggingFace token configured for tokenizer: {self.tokenizer}")

        # WARNING: Other gated models may need token
        elif not self.hf_access_token:
            logger.warning(
                f"⚠️ WARNING: HuggingFace access token not set. "
                f"Tokenizer '{self.tokenizer}' may fail if it's a gated model. "
                f"Set INGESTOR_HF_ACCESS_TOKEN if you encounter authentication errors. "
                f"Get token at: https://huggingface.co/settings/tokens"
            )

        return self

    @model_validator(mode="after")
    def validate_chunk_overlap_less_than_size(self) -> "IngestorSettings":
        """
        Validate chunk_overlap is strictly less than chunk_size.

        An overlap >= size causes the tokenizer to enter an infinite loop
        or produce zero-length chunks.

        Returns:
            Validated settings instance.

        Raises:
            ValueError: If chunk_overlap >= chunk_size.
        """
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_size ({self.chunk_size})"
            )
        return self


_settings: IngestorSettings | None = None


def get_settings() -> IngestorSettings:
    """
    Get ingestor settings from environment.

    Returns:
        IngestorSettings instance.
    """
    global _settings
    if _settings is None:
        _settings = IngestorSettings()  # type: ignore[call-arg]
    return _settings


def reset_settings() -> None:
    """
    Reset settings for testing.

    Clears the cached settings instance.
    """
    global _settings
    _settings = None
