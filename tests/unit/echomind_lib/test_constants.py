"""
Unit tests for central constants.

Verifies the MinioBuckets registry is correct and complete.
"""

from echomind_lib.constants import MinioBuckets


class TestMinioBuckets:
    """Tests for MinioBuckets registry."""

    def test_documents_bucket_name(self) -> None:
        """DOCUMENTS constant has correct value."""
        assert MinioBuckets.DOCUMENTS == "echomind-documents"

    def test_all_returns_list(self) -> None:
        """all() returns a list of strings."""
        buckets = MinioBuckets.all()
        assert isinstance(buckets, list)
        assert all(isinstance(b, str) for b in buckets)

    def test_all_contains_documents(self) -> None:
        """all() includes the documents bucket."""
        assert MinioBuckets.DOCUMENTS in MinioBuckets.all()

    def test_all_not_empty(self) -> None:
        """all() is never empty."""
        assert len(MinioBuckets.all()) > 0

    def test_bucket_names_are_s3_compatible(self) -> None:
        """All bucket names comply with S3 naming rules.

        S3/MinIO bucket names must be 3-63 chars, lowercase, no underscores.
        """
        for name in MinioBuckets.all():
            assert 3 <= len(name) <= 63, f"Bucket '{name}' length out of range"
            assert name == name.lower(), f"Bucket '{name}' must be lowercase"
            assert "_" not in name, f"Bucket '{name}' must not contain underscores"
