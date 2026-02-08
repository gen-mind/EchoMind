"""
Unit tests for Embedder gRPC input validation.

Tests the string validation logic added to prevent processing
empty, whitespace-only, or too-short text strings.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../src"))

import grpc
import pytest
from unittest.mock import MagicMock, patch

from echomind_lib.models.internal.embedding_pb2 import EmbedRequest
from embedder.main import EmbedServicer


class TestEmbedderValidation:
    """Tests for embedder input validation."""

    @pytest.fixture
    def servicer(self):
        """Create an EmbedServicer instance."""
        return EmbedServicer(default_model="test-model", batch_size=32)

    @pytest.fixture
    def mock_context(self):
        """Create a mock gRPC context."""
        context = MagicMock()
        context.abort = MagicMock(side_effect=grpc.RpcError())
        return context

    def test_embed_rejects_empty_list(self, servicer, mock_context):
        """Test that empty texts list is rejected."""
        request = EmbedRequest(texts=[])

        with pytest.raises(grpc.RpcError):
            servicer.Embed(request, mock_context)

        mock_context.abort.assert_called_once_with(
            grpc.StatusCode.INVALID_ARGUMENT,
            "texts cannot be empty",
        )

    def test_embed_rejects_empty_string(self, servicer, mock_context):
        """Test that list containing empty string is rejected."""
        valid_long_text = "This is a valid text that is definitely longer than fifty characters."
        request = EmbedRequest(texts=[valid_long_text, ""])

        with pytest.raises(grpc.RpcError):
            servicer.Embed(request, mock_context)

        mock_context.abort.assert_called_once()
        call_args = mock_context.abort.call_args
        assert call_args[0][0] == grpc.StatusCode.INVALID_ARGUMENT
        assert "index 1 is empty" in call_args[0][1]

    def test_embed_rejects_whitespace_only(self, servicer, mock_context):
        """Test that whitespace-only strings are rejected."""
        valid_long_text = "This is a valid text that is definitely longer than fifty characters."
        request = EmbedRequest(texts=[valid_long_text, "   \n\t  "])

        with pytest.raises(grpc.RpcError):
            servicer.Embed(request, mock_context)

        mock_context.abort.assert_called_once()
        call_args = mock_context.abort.call_args
        assert call_args[0][0] == grpc.StatusCode.INVALID_ARGUMENT
        assert "only whitespace" in call_args[0][1]

    def test_embed_rejects_too_short_text(self, servicer, mock_context):
        """Test that texts below 50 characters are rejected."""
        short_text = "Too short"  # 9 chars
        request = EmbedRequest(texts=[short_text])

        with pytest.raises(grpc.RpcError):
            servicer.Embed(request, mock_context)

        mock_context.abort.assert_called_once()
        call_args = mock_context.abort.call_args
        assert call_args[0][0] == grpc.StatusCode.INVALID_ARGUMENT
        assert "too short" in call_args[0][1]
        assert "minimum 50" in call_args[0][1]

    def test_embed_accepts_valid_texts(self, servicer, mock_context):
        """Test that valid texts are accepted."""
        valid_text = "This is a valid text that is long enough to pass validation and be embedded properly."
        request = EmbedRequest(texts=[valid_text])

        # Mock the encoder to avoid actual model loading
        with patch("embedder.main.SentenceEncoder.encode") as mock_encode:
            mock_encode.return_value = [[0.1] * 384]  # Mock embedding

            response = servicer.Embed(request, mock_context)

            # Should not abort
            mock_context.abort.assert_not_called()
            assert len(response.embeddings) == 1

    def test_embed_validates_all_texts_in_batch(self, servicer, mock_context):
        """Test that all texts in a batch are validated."""
        texts = [
            "This is the first valid text that is long enough to pass validation.",
            "Short",  # Too short - should fail at index 1
            "This is the third valid text that is long enough to pass validation.",
        ]
        request = EmbedRequest(texts=texts)

        with pytest.raises(grpc.RpcError):
            servicer.Embed(request, mock_context)

        # Should abort on the second text (index 1)
        mock_context.abort.assert_called_once()
        call_args = mock_context.abort.call_args
        assert "index 1" in call_args[0][1]
        assert "too short" in call_args[0][1]

    def test_embed_trims_whitespace_for_length_check(self, servicer, mock_context):
        """Test that leading/trailing whitespace is trimmed for length validation."""
        # 60 chars of content, but with leading/trailing spaces
        text_with_spaces = "    This text has exactly sixty characters of actual content!     "
        request = EmbedRequest(texts=[text_with_spaces])

        # Mock the encoder
        with patch("embedder.main.SentenceEncoder.encode") as mock_encode:
            mock_encode.return_value = [[0.1] * 384]

            response = servicer.Embed(request, mock_context)

            # Should accept because stripped length >= 50
            mock_context.abort.assert_not_called()
            assert len(response.embeddings) == 1

    def test_embed_validation_order(self, servicer, mock_context):
        """Test that validation checks run in correct order."""
        # Empty string should be caught before length check
        request = EmbedRequest(texts=[""])

        with pytest.raises(grpc.RpcError):
            servicer.Embed(request, mock_context)

        call_args = mock_context.abort.call_args
        # Should fail on "is empty" not "too short"
        assert "is empty" in call_args[0][1]
        assert "too short" not in call_args[0][1]
