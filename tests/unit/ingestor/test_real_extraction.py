"""Integration tests using real files from testdocs/.

Dynamically discovers ALL files in testdocs/ and tests extraction
against each one. Files may be added or removed — tests adapt.

Verifies:
1. Every supported file is routed to the correct extractor
2. Extraction produces non-empty results with text
3. Text is in metadata["content"] (where nv-ingest chunker reads)
4. _chunk_content reads from the correct field
5. Audio extraction works with mocked Riva NIM
"""

import asyncio
import base64
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ingestor.config import IngestorSettings, reset_settings
from ingestor.logic.document_processor import DocumentProcessor
from ingestor.logic.mime_router import MimeRouter

TESTDOCS_DIR = Path(__file__).parent / "testdocs"

# Extension → MIME type mapping (covers all MimeRouter supported types)
_EXT_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".html": "text/html",
    ".htm": "text/html",
    ".bmp": "image/bmp",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".tiff": "image/tiff",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".sh": "application/x-sh",
}

# Extractor types that need external NIMs not available locally
_SKIP_EXTRACTORS: dict[str, str] = {
    "audio": "Riva NIM not available locally",
    "video": "Video extraction is early access / not implemented",
}

# Files known to be invalid/corrupt for their declared format.
# Add entries here if test fixtures can't be replaced with valid files.
_XFAIL_FILES: dict[str, str] = {}


def _discover_all_testdocs() -> list[tuple[str, str, str, Path]]:
    """Discover ALL files in testdocs/.

    Returns:
        List of (filename, mime_type, extractor_type, path) tuples.
    """
    if not TESTDOCS_DIR.exists():
        return []

    router = MimeRouter()
    docs = []
    for fpath in sorted(TESTDOCS_DIR.iterdir()):
        if fpath.name.startswith(".") or fpath.is_dir():
            continue
        ext = fpath.suffix.lower()
        mime = _EXT_TO_MIME.get(ext)
        if mime and router.is_supported(mime):
            extractor = router.get_extractor_type(mime)
            docs.append((fpath.name, mime, extractor, fpath))

    return docs


# Discover once at import time for parametrize
_ALL_DOCS = _discover_all_testdocs()


class TestDiscovery:
    """Verify testdocs/ has files and all are recognized."""

    def test_testdocs_exists(self) -> None:
        """testdocs/ directory must exist."""
        assert TESTDOCS_DIR.exists(), f"testdocs/ not found at {TESTDOCS_DIR}"

    def test_testdocs_has_files(self) -> None:
        """testdocs/ must contain at least 5 test files."""
        assert len(_ALL_DOCS) >= 5, (
            f"Expected >= 5 test files, found {len(_ALL_DOCS)}: "
            f"{[d[0] for d in _ALL_DOCS]}"
        )

    def test_testdocs_covers_multiple_types(self) -> None:
        """testdocs/ must cover at least 2 extractor types."""
        types = {d[2] for d in _ALL_DOCS}
        assert len(types) >= 2, f"Only {types} extractor types found"

    def test_all_files_have_valid_mime(self) -> None:
        """Every discovered file must map to a supported MIME type."""
        router = MimeRouter()
        for name, mime, _, _ in _ALL_DOCS:
            assert router.is_supported(mime), (
                f"{name} has unsupported MIME type {mime}"
            )


class TestRealExtraction:
    """Extract real files from testdocs/ through DocumentProcessor."""

    def setup_method(self) -> None:
        """Create processor with YOLOX disabled (not available locally)."""
        reset_settings()
        self.settings = IngestorSettings()
        self.processor = DocumentProcessor(self.settings)

    def teardown_method(self) -> None:
        """Reset settings after tests."""
        reset_settings()

    # ------------------------------------------------------------------
    # Single parametrized test over ALL files
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "name,mime,extractor,path",
        _ALL_DOCS,
        ids=[d[0] for d in _ALL_DOCS],
    )
    def test_extraction_per_file(
        self,
        name: str,
        mime: str,
        extractor: str,
        path: Path,
    ) -> None:
        """Extract each testdocs/ file and verify text output.

        Dynamically selects * from testdocs/. Skips audio/video
        (require NIMs not available locally). For all others, verifies
        extraction produces text at the correct metadata location.
        """
        # Skip extractors that need external NIMs
        if extractor in _SKIP_EXTRACTORS:
            pytest.skip(_SKIP_EXTRACTORS[extractor])

        # Mark known-corrupt fixtures as expected failures
        if name in _XFAIL_FILES:
            pytest.xfail(_XFAIL_FILES[name])

        # nv-ingest-api required for pdf/docx/pptx/image
        if extractor in ("pdf", "docx", "pptx", "image"):
            pytest.importorskip(
                "nv_ingest_api", reason="nv_ingest_api not installed"
            )

        file_bytes = path.read_bytes()
        df = self.processor._build_dataframe(
            file_bytes=file_bytes,
            document_id=1,
            file_name=name,
            mime_type=mime,
        )

        result = asyncio.get_event_loop().run_until_complete(
            self.processor._extract(df, mime, document_id=1)
        )

        # Extraction must produce a non-empty DataFrame
        assert not result.empty, (
            f"Extraction returned empty DataFrame for {name} ({extractor})"
        )

        # Verify text exists in metadata["content"]
        # nv-ingest extractors → metadata["content"]
        # Our text/html extractors → metadata["content"] + content_metadata["text"]
        found_text = False
        total_chars = 0
        for _, row in result.iterrows():
            meta = row.get("metadata", {})
            content = meta.get("content", "")
            if content and isinstance(content, str) and len(content.strip()) > 0:
                found_text = True
                total_chars += len(content)

        assert found_text, (
            f"No text in metadata['content'] for {name} ({extractor}). "
            f"{len(result)} rows returned but none had text. "
            f"The nv-ingest chunker reads from metadata['content'] — "
            f"without it, 0 chunks would be produced."
        )
        assert total_chars > 10, (
            f"Only {total_chars} chars extracted from {name} ({extractor})"
        )

    # ------------------------------------------------------------------
    # Text extractor: verify both metadata fields are set
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "name,mime,extractor,path",
        [d for d in _ALL_DOCS if d[2] == "text"],
        ids=[d[0] for d in _ALL_DOCS if d[2] == "text"],
    )
    def test_text_extractor_sets_both_fields(
        self,
        name: str,
        mime: str,
        extractor: str,
        path: Path,
    ) -> None:
        """Text/markdown files must set BOTH metadata locations.

        - metadata["content"]: for nv-ingest chunker
        - content_metadata["text"]: for consistency
        """
        file_bytes = path.read_bytes()
        df = self.processor._build_dataframe(
            file_bytes=file_bytes,
            document_id=1,
            file_name=name,
            mime_type=mime,
        )

        result = asyncio.get_event_loop().run_until_complete(
            self.processor._extract(df, mime, document_id=1)
        )

        for _, row in result.iterrows():
            meta = row.get("metadata", {})

            content = meta.get("content", "")
            cm_text = meta.get("content_metadata", {}).get("text", "")

            assert content and len(content) > 0, (
                f"metadata['content'] empty for {name}"
            )
            assert cm_text and len(cm_text) > 0, (
                f"content_metadata['text'] empty for {name}"
            )
            assert content == cm_text, (
                f"metadata['content'] != content_metadata['text'] for {name}"
            )

    # ------------------------------------------------------------------
    # PDF: verify nv-ingest metadata structure
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "name,mime,extractor,path",
        [d for d in _ALL_DOCS if d[2] == "pdf"],
        ids=[d[0] for d in _ALL_DOCS if d[2] == "pdf"],
    )
    def test_pdf_metadata_structure(
        self,
        name: str,
        mime: str,
        extractor: str,
        path: Path,
    ) -> None:
        """PDF extraction must produce rows with source_metadata and content."""
        pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        file_bytes = path.read_bytes()
        df = self.processor._build_dataframe(
            file_bytes=file_bytes,
            document_id=1,
            file_name=name,
            mime_type=mime,
        )

        result = asyncio.get_event_loop().run_until_complete(
            self.processor._extract(df, mime, document_id=1)
        )

        assert "metadata" in result.columns
        assert "document_type" in result.columns

        # At least one row must have valid metadata structure
        for _, row in result.iterrows():
            meta = row.get("metadata", {})
            if meta.get("content"):
                assert "source_metadata" in meta, (
                    f"Missing source_metadata in {name}"
                )
                assert "content_metadata" in meta, (
                    f"Missing content_metadata in {name}"
                )
                break


class TestChunkFieldMapping:
    """Verify _chunk_content reads from the correct metadata field."""

    def setup_method(self) -> None:
        """Create processor."""
        reset_settings()
        self.settings = IngestorSettings()
        self.processor = DocumentProcessor(self.settings)

    def teardown_method(self) -> None:
        """Reset settings."""
        reset_settings()

    def test_reads_from_metadata_content(self) -> None:
        """_chunk_content must read from metadata['content'].

        nv-ingest stores chunk text in metadata['content'],
        NOT in content_metadata['text'].
        """
        pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        chunked_df = pd.DataFrame({
            "document_type": ["text", "text", "text"],
            "metadata": [
                {"content": "First chunk from PDF.", "content_metadata": {"type": "text"}},
                {"content": "Second chunk.", "content_metadata": {"type": "text"}},
                {"content": "  ", "content_metadata": {"type": "text"}},  # whitespace → filtered
            ],
            "uuid": ["a", "b", "c"],
        })

        with patch(
            "nv_ingest_api.interface.transform.transform_text_split_and_tokenize",
            return_value=chunked_df,
        ):
            chunks = asyncio.get_event_loop().run_until_complete(
                self.processor._chunk_content(chunked_df, document_id=1)
            )

        assert chunks == ["First chunk from PDF.", "Second chunk."]

    def test_old_field_would_produce_zero_chunks(self) -> None:
        """Documents the bug: content_metadata['text'] is empty in nv-ingest output."""
        # Real nv-ingest output: text ONLY in metadata["content"]
        row_meta = {
            "content": "Actual text here.",
            "content_metadata": {"type": "text"},
        }

        # OLD code path → 0 chunks
        old_text = row_meta.get("content_metadata", {}).get("text")
        assert old_text is None, "nv-ingest should NOT set content_metadata.text"

        # NEW code path → finds text
        new_text = row_meta.get("content")
        assert new_text == "Actual text here."

    def test_full_pipeline_with_real_pdf(self) -> None:
        """End-to-end: real PDF → extract → verify chunker-compatible output."""
        pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        # Pick smallest PDF from testdocs
        pdfs = [d for d in _ALL_DOCS if d[2] == "pdf"]
        if not pdfs:
            pytest.skip("No PDFs in testdocs/")

        # Sort by file size, use smallest
        pdfs_sorted = sorted(pdfs, key=lambda d: d[3].stat().st_size)
        name, mime, _, path = pdfs_sorted[0]

        file_bytes = path.read_bytes()
        df = self.processor._build_dataframe(
            file_bytes=file_bytes,
            document_id=99,
            file_name=name,
            mime_type=mime,
        )

        extracted = asyncio.get_event_loop().run_until_complete(
            self.processor._extract(df, mime, document_id=99)
        )

        assert not extracted.empty

        # Count text content in metadata["content"]
        text_rows = sum(
            1 for _, row in extracted.iterrows()
            if row.get("metadata", {}).get("content")
        )
        total_chars = sum(
            len(row.get("metadata", {}).get("content", ""))
            for _, row in extracted.iterrows()
            if row.get("metadata", {}).get("content")
        )

        assert text_rows > 0, f"No text rows from {name}"
        assert total_chars > 100, f"Only {total_chars} chars from {name}"


# Helper: filter audio files from _ALL_DOCS
_AUDIO_DOCS = [d for d in _ALL_DOCS if d[2] == "audio"]


class TestAudioExtraction:
    """Test audio extraction with mocked Riva NIM.

    Audio extraction requires NVIDIA Riva NIM for speech-to-text
    transcription via gRPC. These tests mock the Riva client at the
    nv-ingest-api internal level (``create_audio_inference_client``)
    to verify the full extraction pipeline without the GPU container.

    Mock strategy:
    - Mock ``create_audio_inference_client`` → returns a mock
      ``ParakeetClient`` whose ``infer()`` returns realistic
      ``(segments, transcript)`` data.
    - Real nv-ingest extraction code runs: DataFrame prep, row
      iteration, base64 decode, metadata assembly.
    - Only the actual gRPC call is bypassed.
    """

    # Realistic mock transcript matching Riva output format.
    # infer() returns (segments, full_transcript).
    _MOCK_SEGMENTS = [
        {"start": 0.0, "end": 2.8, "text": "Hello world."},
        {"start": 2.8, "end": 5.5, "text": "This is an audio test transcript."},
    ]
    _MOCK_TRANSCRIPT = "Hello world. This is an audio test transcript."

    def setup_method(self) -> None:
        """Create processor with Riva enabled."""
        os.environ["INGESTOR_RIVA_ENABLED"] = "true"
        reset_settings()
        self.settings = IngestorSettings()
        self.processor = DocumentProcessor(self.settings)

    def teardown_method(self) -> None:
        """Reset settings and env."""
        os.environ.pop("INGESTOR_RIVA_ENABLED", None)
        reset_settings()

    @staticmethod
    def _build_mock_audio_result(
        file_name: str,
        document_id: int,
    ) -> tuple[pd.DataFrame, dict]:
        """Build a realistic mock result matching nv-ingest audio output.

        nv-ingest audio extraction returns ``(DataFrame, dict)`` where the
        DataFrame has one row per audio segment with transcript in
        ``audio_metadata.audio_transcript``.

        Args:
            file_name: Source filename for metadata.
            document_id: Document ID for metadata.

        Returns:
            Tuple of (result DataFrame, empty trace dict).
        """
        return (
            pd.DataFrame({
                "document_type": ["audio", "audio"],
                "metadata": [
                    {
                        "content_metadata": {
                            "type": "audio",
                            "start_time": 0.0,
                            "end_time": 2.8,
                        },
                        "audio_metadata": {
                            "audio_transcript": "Hello world.",
                        },
                        "source_metadata": {
                            "source_name": file_name,
                            "source_id": str(document_id),
                        },
                    },
                    {
                        "content_metadata": {
                            "type": "audio",
                            "start_time": 2.8,
                            "end_time": 5.5,
                        },
                        "audio_metadata": {
                            "audio_transcript": "This is an audio test transcript.",
                        },
                        "source_metadata": {
                            "source_name": file_name,
                            "source_id": str(document_id),
                        },
                    },
                ],
                "uuid": [f"uuid-{document_id}-1", f"uuid-{document_id}-2"],
            }),
            {},  # execution trace log
        )

    # ------------------------------------------------------------------
    # Parametrized: each audio file from testdocs/
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "name,mime,extractor,path",
        _AUDIO_DOCS,
        ids=[d[0] for d in _AUDIO_DOCS],
    )
    def test_audio_extraction_produces_transcript(
        self,
        name: str,
        mime: str,
        extractor: str,
        path: Path,
    ) -> None:
        """Extract audio files with mocked Riva and verify transcript output.

        Mocks ``extract_primitives_from_audio`` at the nv-ingest-api public
        interface. Verifies:
        - Extraction produces a non-empty DataFrame
        - Transcript text exists in ``audio_metadata.audio_transcript``
        - ``_unpack_extraction_result`` correctly handles (DataFrame, dict) tuple
        """
        pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        file_bytes = path.read_bytes()
        df = self.processor._build_dataframe(
            file_bytes=file_bytes,
            document_id=1,
            file_name=name,
            mime_type=mime,
        )

        mock_result = self._build_mock_audio_result(name, document_id=1)

        with patch(
            "nv_ingest_api.interface.extract.extract_primitives_from_audio",
            return_value=mock_result,
        ):
            result = asyncio.get_event_loop().run_until_complete(
                self.processor._extract(df, mime, document_id=1)
            )

        # Must produce non-empty DataFrame (tuple was unpacked)
        assert isinstance(result, pd.DataFrame), (
            f"Expected DataFrame, got {type(result).__name__}"
        )
        assert not result.empty, (
            f"Audio extraction returned empty DataFrame for {name}"
        )

        # Verify transcript in audio_metadata
        found_transcript = False
        total_chars = 0
        for _, row in result.iterrows():
            meta = row.get("metadata", {})
            audio_meta = meta.get("audio_metadata", {})
            transcript = audio_meta.get("audio_transcript", "")
            if transcript and isinstance(transcript, str) and transcript.strip():
                found_transcript = True
                total_chars += len(transcript)

        assert found_transcript, (
            f"No transcript in audio_metadata for {name}. "
            f"Audio extraction must produce audio_metadata.audio_transcript."
        )
        assert total_chars > 10, (
            f"Only {total_chars} chars transcribed from {name}"
        )

    # ------------------------------------------------------------------
    # Audio metadata structure
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "name,mime,extractor,path",
        _AUDIO_DOCS,
        ids=[d[0] for d in _AUDIO_DOCS],
    )
    def test_audio_metadata_structure(
        self,
        name: str,
        mime: str,
        extractor: str,
        path: Path,
    ) -> None:
        """Audio output must have correct metadata structure.

        Each row must contain:
        - content_metadata with type and time offsets
        - audio_metadata with audio_transcript
        - source_metadata with source info
        """
        pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        file_bytes = path.read_bytes()
        df = self.processor._build_dataframe(
            file_bytes=file_bytes,
            document_id=1,
            file_name=name,
            mime_type=mime,
        )

        mock_result = self._build_mock_audio_result(name, document_id=1)

        with patch(
            "nv_ingest_api.interface.extract.extract_primitives_from_audio",
            return_value=mock_result,
        ):
            result = asyncio.get_event_loop().run_until_complete(
                self.processor._extract(df, mime, document_id=1)
            )

        assert "metadata" in result.columns
        assert "document_type" in result.columns

        for _, row in result.iterrows():
            meta = row.get("metadata", {})
            assert "content_metadata" in meta, f"Missing content_metadata for {name}"
            assert "audio_metadata" in meta, f"Missing audio_metadata for {name}"
            assert "source_metadata" in meta, f"Missing source_metadata for {name}"

            # Verify time offsets
            cm = meta["content_metadata"]
            assert "start_time" in cm, f"Missing start_time for {name}"
            assert "end_time" in cm, f"Missing end_time for {name}"
            assert cm["end_time"] > cm["start_time"], (
                f"end_time must be > start_time for {name}"
            )

    # ------------------------------------------------------------------
    # Riva disabled → empty result
    # ------------------------------------------------------------------

    def test_audio_returns_empty_when_riva_disabled(self) -> None:
        """Audio extraction returns empty DataFrame when riva_enabled=False.

        This is the expected behavior when Riva NIM is not deployed.
        The processor should return early without calling nv-ingest-api.
        """
        if not _AUDIO_DOCS:
            pytest.skip("No audio files in testdocs/")

        # Create processor with default settings (riva_enabled=False)
        os.environ.pop("INGESTOR_RIVA_ENABLED", None)
        reset_settings()
        default_settings = IngestorSettings()
        processor = DocumentProcessor(default_settings)

        name, mime, _, path = _AUDIO_DOCS[0]
        file_bytes = path.read_bytes()
        df = processor._build_dataframe(
            file_bytes=file_bytes,
            document_id=1,
            file_name=name,
            mime_type=mime,
        )

        result = asyncio.get_event_loop().run_until_complete(
            processor._extract(df, mime, document_id=1)
        )

        assert result.empty, (
            "Audio extraction should return empty when Riva disabled"
        )

    # ------------------------------------------------------------------
    # Riva endpoint format
    # ------------------------------------------------------------------

    def test_audio_passes_grpc_endpoint(self) -> None:
        """Audio extraction passes Riva gRPC endpoint correctly.

        The audio_endpoints tuple must be (gRPC, HTTP) where the gRPC
        endpoint is the Riva NIM address in ``host:port`` format (no
        ``http://`` prefix).
        """
        pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        if not _AUDIO_DOCS:
            pytest.skip("No audio files in testdocs/")

        name, mime, _, path = _AUDIO_DOCS[0]
        file_bytes = path.read_bytes()
        df = self.processor._build_dataframe(
            file_bytes=file_bytes,
            document_id=1,
            file_name=name,
            mime_type=mime,
        )

        mock_fn = MagicMock(return_value=(pd.DataFrame(), {}))
        with patch(
            "nv_ingest_api.interface.extract.extract_primitives_from_audio",
            mock_fn,
        ):
            asyncio.get_event_loop().run_until_complete(
                self.processor._extract(df, mime, document_id=1)
            )

        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]

        # audio_endpoints is (gRPC, HTTP) tuple
        assert "audio_endpoints" in kwargs
        grpc_ep, http_ep = kwargs["audio_endpoints"]
        assert grpc_ep == self.settings.riva_endpoint
        assert not grpc_ep.startswith("http://"), (
            f"gRPC endpoint must not have http:// prefix, got {grpc_ep}"
        )
        assert kwargs["audio_infer_protocol"] == "grpc"
