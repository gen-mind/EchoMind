"""Unit tests for Ingestor Service configuration."""

import os
from unittest.mock import patch

import pytest

from ingestor.config import IngestorSettings, get_settings, reset_settings


@pytest.fixture(autouse=True)
def mock_hf_token():
    """
    Auto-mock HF token for all tests.

    The default tokenizer (meta-llama/Llama-3.2-1B) requires HF auth.
    This fixture provides a fake token so tests don't need to set it explicitly.
    Tests that specifically test token validation can override this.
    """
    with patch.dict(os.environ, {"INGESTOR_HF_ACCESS_TOKEN": "hf_test_token_for_unit_tests"}):
        yield


class TestIngestorSettings:
    """Tests for IngestorSettings."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Reset settings after each test."""
        reset_settings()

    def test_default_values(self) -> None:
        """Test default configuration values."""
        settings = IngestorSettings()

        assert settings.enabled is True
        assert settings.health_port == 8080
        assert settings.database_echo is False
        assert settings.chunk_size == 1024
        assert settings.chunk_overlap == 124
        assert settings.text_depth == "page"
        # HF token comes from test fixture (autouse)
        assert settings.hf_access_token == "hf_test_token_for_unit_tests"
        assert settings.max_retries == 3
        assert settings.retry_base_delay == 1.0
        assert settings.log_level == "INFO"

    def test_database_url_default(self) -> None:
        """Test default database URL."""
        settings = IngestorSettings()

        assert "postgresql+asyncpg" in settings.database_url
        assert "echomind" in settings.database_url

    def test_nats_defaults(self) -> None:
        """Test NATS default configuration."""
        settings = IngestorSettings()

        assert settings.nats_url == "nats://localhost:4222"
        assert settings.nats_stream_name == "ECHOMIND"
        assert settings.nats_consumer_name == "ingestor-consumer"
        assert settings.nats_user is None
        assert settings.nats_password is None

    def test_minio_defaults(self) -> None:
        """Test MinIO default configuration."""
        settings = IngestorSettings()

        assert settings.minio_endpoint == "localhost:9000"
        assert settings.minio_access_key == "minioadmin"
        assert settings.minio_secret_key == "minioadmin"
        assert settings.minio_secure is False
        assert settings.minio_bucket == "echomind-documents"

    def test_qdrant_defaults(self) -> None:
        """Test Qdrant default configuration."""
        settings = IngestorSettings()

        assert settings.qdrant_host == "localhost"
        assert settings.qdrant_port == 6333
        assert settings.qdrant_api_key is None

    def test_embedder_defaults(self) -> None:
        """Test Embedder gRPC default configuration."""
        settings = IngestorSettings()

        assert settings.embedder_host == "echomind-embedder"
        assert settings.embedder_port == 50051
        assert settings.embedder_timeout == 600.0

    def test_extraction_defaults(self) -> None:
        """Test nv-ingest extraction default configuration."""
        settings = IngestorSettings()

        assert settings.extract_method == "pdfium"
        assert settings.text_depth == "page"
        assert settings.chunk_size == 1024
        assert settings.chunk_overlap == 124
        assert settings.tokenizer == "nvidia/llama-nemotron-embed-1b-v2"
        # HF token comes from test fixture
        assert settings.hf_access_token == "hf_test_token_for_unit_tests"

    def test_optional_nims_defaults(self) -> None:
        """Test optional NIMs have correct defaults."""
        settings = IngestorSettings()

        assert settings.yolox_enabled is False
        assert settings.riva_enabled is False

    def test_env_prefix(self) -> None:
        """Test environment variable prefix."""
        with patch.dict(os.environ, {"INGESTOR_ENABLED": "false"}):
            settings = IngestorSettings()
            assert settings.enabled is False

    def test_custom_chunk_settings(self) -> None:
        """Test custom chunk settings from environment."""
        with patch.dict(
            os.environ,
            {
                "INGESTOR_CHUNK_SIZE": "1024",
                "INGESTOR_CHUNK_OVERLAP": "100",
            },
        ):
            settings = IngestorSettings()
            assert settings.chunk_size == 1024
            assert settings.chunk_overlap == 100

    def test_custom_embedder_settings(self) -> None:
        """Test custom embedder settings from environment."""
        with patch.dict(
            os.environ,
            {
                "INGESTOR_EMBEDDER_HOST": "custom-embedder",
                "INGESTOR_EMBEDDER_PORT": "9999",
                "INGESTOR_EMBEDDER_TIMEOUT": "60.0",
            },
        ):
            settings = IngestorSettings()
            assert settings.embedder_host == "custom-embedder"
            assert settings.embedder_port == 9999
            assert settings.embedder_timeout == 60.0

    def test_log_level_validation_valid(self) -> None:
        """Test log level validation accepts valid levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            with patch.dict(os.environ, {"INGESTOR_LOG_LEVEL": level}):
                settings = IngestorSettings()
                assert settings.log_level == level

    def test_log_level_validation_case_insensitive(self) -> None:
        """Test log level validation is case insensitive."""
        with patch.dict(os.environ, {"INGESTOR_LOG_LEVEL": "debug"}):
            settings = IngestorSettings()
            assert settings.log_level == "DEBUG"

    def test_log_level_validation_invalid(self) -> None:
        """Test log level validation rejects invalid levels."""
        with patch.dict(os.environ, {"INGESTOR_LOG_LEVEL": "INVALID"}):
            with pytest.raises(ValueError, match="Invalid log level"):
                IngestorSettings()

    def test_extract_method_validation_valid(self) -> None:
        """Test extract method validation accepts valid methods."""
        for method in ["pdfium", "pdfium_hybrid", "nemotron_parse"]:
            with patch.dict(os.environ, {"INGESTOR_EXTRACT_METHOD": method}):
                settings = IngestorSettings()
                assert settings.extract_method == method

    def test_extract_method_validation_invalid(self) -> None:
        """Test extract method validation rejects invalid methods."""
        with patch.dict(os.environ, {"INGESTOR_EXTRACT_METHOD": "invalid"}):
            with pytest.raises(ValueError, match="Invalid extract method"):
                IngestorSettings()

    def test_chunk_size_constraints(self) -> None:
        """Test chunk size constraints."""
        # Test minimum (gt=0)
        with patch.dict(os.environ, {"INGESTOR_CHUNK_SIZE": "0"}):
            with pytest.raises(ValueError):
                IngestorSettings()

        # Test maximum (le=8192)
        with patch.dict(os.environ, {"INGESTOR_CHUNK_SIZE": "9000"}):
            with pytest.raises(ValueError):
                IngestorSettings()

    def test_chunk_overlap_constraint(self) -> None:
        """Test chunk overlap minimum constraint."""
        with patch.dict(os.environ, {"INGESTOR_CHUNK_OVERLAP": "-1"}):
            with pytest.raises(ValueError):
                IngestorSettings()

    def test_chunk_overlap_must_be_less_than_chunk_size(self) -> None:
        """Test chunk_overlap >= chunk_size is rejected.

        An overlap equal to or greater than size causes the tokenizer
        to enter an infinite loop or produce zero-length chunks.
        """
        # overlap == size
        with patch.dict(
            os.environ,
            {"INGESTOR_CHUNK_SIZE": "100", "INGESTOR_CHUNK_OVERLAP": "100"},
        ):
            with pytest.raises(ValueError, match="chunk_overlap.*must be less than.*chunk_size"):
                IngestorSettings()

        # overlap > size
        with patch.dict(
            os.environ,
            {"INGESTOR_CHUNK_SIZE": "100", "INGESTOR_CHUNK_OVERLAP": "200"},
        ):
            with pytest.raises(ValueError, match="chunk_overlap.*must be less than.*chunk_size"):
                IngestorSettings()

    def test_chunk_overlap_less_than_size_is_valid(self) -> None:
        """Test chunk_overlap < chunk_size is accepted."""
        with patch.dict(
            os.environ,
            {"INGESTOR_CHUNK_SIZE": "100", "INGESTOR_CHUNK_OVERLAP": "99"},
        ):
            settings = IngestorSettings()
            assert settings.chunk_overlap == 99
            assert settings.chunk_size == 100

    def test_riva_endpoint_default_is_grpc_format(self) -> None:
        """Test Riva endpoint default uses gRPC format (no http:// prefix).

        gRPC endpoints are host:port strings. HTTP prefix would confuse
        the nv-ingest-api audio extractor which passes this as the gRPC endpoint.
        """
        settings = IngestorSettings()
        assert settings.riva_endpoint == "riva:50051"
        assert not settings.riva_endpoint.startswith("http://")

    def test_text_depth_validation_valid(self) -> None:
        """Test text_depth validation accepts valid values."""
        for value in ["document", "page"]:
            with patch.dict(os.environ, {"INGESTOR_TEXT_DEPTH": value}):
                settings = IngestorSettings()
                assert settings.text_depth == value

    def test_text_depth_validation_invalid(self) -> None:
        """Test text_depth validation rejects invalid values."""
        with patch.dict(os.environ, {"INGESTOR_TEXT_DEPTH": "invalid"}):
            with pytest.raises(ValueError, match="Invalid text_depth"):
                IngestorSettings()

    def test_text_depth_default_is_page(self) -> None:
        """Test text_depth defaults to 'page' (NVIDIA recommended).

        NVIDIA research shows page-level chunking achieves highest
        accuracy (0.648) with lowest variance across document types.
        """
        settings = IngestorSettings()
        assert settings.text_depth == "page"

    def test_hf_token_optional_for_all_tokenizers(self) -> None:
        """Test HF token is optional at runtime for all tokenizers.

        Models are pre-downloaded at Docker build time and cached locally.
        Runtime runs in offline mode (HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1),
        so no HuggingFace authentication is needed at startup.
        """
        # Gated models work without token (pre-cached at build time)
        for tokenizer in [
            "meta-llama/Llama-3.2-1B",
            "meta-llama/Llama-3-8B",
            "nvidia/llama-nemotron-embed-1b-v2",
        ]:
            with patch.dict(
                os.environ,
                {"INGESTOR_TOKENIZER": tokenizer},
                clear=False,
            ):
                os.environ.pop("INGESTOR_HF_ACCESS_TOKEN", None)
                settings = IngestorSettings()
                assert settings.tokenizer == tokenizer
                assert settings.hf_access_token is None

        # Non-gated models also work without token
        with patch.dict(
            os.environ,
            {"INGESTOR_TOKENIZER": "gpt2"},
            clear=False,
        ):
            os.environ.pop("INGESTOR_HF_ACCESS_TOKEN", None)
            settings = IngestorSettings()
            assert settings.tokenizer == "gpt2"
            assert settings.hf_access_token is None

    def test_hf_token_accepted_when_provided(self) -> None:
        """Test HF token is accepted and stored when provided."""
        with patch.dict(
            os.environ,
            {
                "INGESTOR_TOKENIZER": "nvidia/llama-nemotron-embed-1b-v2",
                "INGESTOR_HF_ACCESS_TOKEN": "hf_test_token_67890",
            },
        ):
            settings = IngestorSettings()
            assert settings.tokenizer == "nvidia/llama-nemotron-embed-1b-v2"
            assert settings.hf_access_token == "hf_test_token_67890"

    def test_chunk_overlap_percentage_within_nvidia_range(self) -> None:
        """Test default chunk overlap is within NVIDIA's 10-20% recommendation.

        NVIDIA research found 15% optimal, with 10-20% acceptable.
        Default 124/1024 = 12.1% is within this range.
        """
        settings = IngestorSettings()
        overlap_percentage = (settings.chunk_overlap / settings.chunk_size) * 100
        assert 10.0 <= overlap_percentage <= 20.0, f"Overlap {overlap_percentage:.1f}% outside 10-20% range"
        assert overlap_percentage == pytest.approx(12.1, abs=0.1)


class TestGetSettings:
    """Tests for get_settings function."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Reset settings after each test."""
        reset_settings()

    def test_returns_settings(self) -> None:
        """Test get_settings returns IngestorSettings instance."""
        settings = get_settings()

        assert isinstance(settings, IngestorSettings)

    def test_caches_settings(self) -> None:
        """Test settings are cached after first call."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reset_clears_cache(self) -> None:
        """Test reset_settings clears the cache."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()

        assert settings1 is not settings2
