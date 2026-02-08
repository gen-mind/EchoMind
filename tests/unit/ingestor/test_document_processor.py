"""Unit tests for DocumentProcessor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from ingestor.config import IngestorSettings, reset_settings
from ingestor.logic.document_processor import DocumentProcessor
from ingestor.logic.exceptions import (
    ChunkingError,
    DocxExtractionError,
    ExtractionError,
    PDFExtractionError,
    UnsupportedMimeTypeError,
)


class TestDocumentProcessor:
    """Tests for DocumentProcessor class."""

    def setup_method(self) -> None:
        """Create processor instance for each test."""
        reset_settings()
        self.settings = IngestorSettings()
        self.processor = DocumentProcessor(self.settings)

    def teardown_method(self) -> None:
        """Reset after tests."""
        reset_settings()

    # ==========================================
    # Initialization tests
    # ==========================================

    def test_init_creates_mime_router(self) -> None:
        """Test processor initializes with MimeRouter."""
        assert self.processor._router is not None

    def test_init_stores_settings(self) -> None:
        """Test processor stores settings."""
        assert self.processor._settings is self.settings

    # ==========================================
    # MIME type validation tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_process_unsupported_mime_type_raises(self) -> None:
        """Test process raises for unsupported MIME type."""
        with pytest.raises(UnsupportedMimeTypeError) as exc_info:
            await self.processor.process(
                file_bytes=b"test",
                document_id=1,
                file_name="test.xyz",
                mime_type="application/x-unknown",
            )

        assert "application/x-unknown" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_validates_mime_type_first(self) -> None:
        """Test MIME type validation happens before any processing."""
        # Even with empty bytes, should fail on MIME type first
        with pytest.raises(UnsupportedMimeTypeError):
            await self.processor.process(
                file_bytes=b"",
                document_id=1,
                file_name="test",
                mime_type="video/webm",  # Not supported
            )

    # ==========================================
    # DataFrame building tests
    # ==========================================

    def test_build_dataframe_structure(self) -> None:
        """Test _build_dataframe creates correct structure."""
        df = self.processor._build_dataframe(
            file_bytes=b"test content",
            document_id=123,
            file_name="test.pdf",
            mime_type="application/pdf",
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "source_id" in df.columns
        assert "source_name" in df.columns
        assert "content" in df.columns
        assert "document_type" in df.columns
        assert "metadata" in df.columns

    def test_build_dataframe_source_id_is_string(self) -> None:
        """Test source_id is stored as string."""
        df = self.processor._build_dataframe(
            file_bytes=b"test",
            document_id=456,
            file_name="test.pdf",
            mime_type="application/pdf",
        )

        assert df.iloc[0]["source_id"] == "456"

    def test_build_dataframe_content_is_base64(self) -> None:
        """Test content is base64 encoded."""
        import base64

        original = b"hello world"
        df = self.processor._build_dataframe(
            file_bytes=original,
            document_id=1,
            file_name="test.txt",
            mime_type="text/plain",
        )

        encoded = df.iloc[0]["content"]
        decoded = base64.b64decode(encoded)
        assert decoded == original

    def test_build_dataframe_document_type_from_mime(self) -> None:
        """Test document_type is derived from MIME type."""
        test_cases = [
            ("application/pdf", "pdf"),
            ("image/jpeg", "jpeg"),
            ("text/plain", "txt"),
            ("audio/mpeg", "mp3"),
        ]

        for mime_type, expected_doc_type in test_cases:
            df = self.processor._build_dataframe(
                file_bytes=b"test",
                document_id=1,
                file_name="test",
                mime_type=mime_type,
            )
            assert df.iloc[0]["document_type"] == expected_doc_type

    def test_build_dataframe_metadata_structure(self) -> None:
        """Test metadata has correct structure."""
        df = self.processor._build_dataframe(
            file_bytes=b"test",
            document_id=789,
            file_name="mydoc.pdf",
            mime_type="application/pdf",
        )

        metadata = df.iloc[0]["metadata"]
        assert "content_metadata" in metadata
        assert "source_metadata" in metadata
        assert metadata["source_metadata"]["source_name"] == "mydoc.pdf"
        assert metadata["source_metadata"]["source_id"] == "789"

    # ==========================================
    # Text extraction tests
    # ==========================================

    def test_extract_text_basic(self) -> None:
        """Test _extract_text extracts plain text to both metadata fields."""
        import base64

        content = "Hello, World!"
        encoded = base64.b64encode(content.encode()).decode()

        df = pd.DataFrame({
            "content": [encoded],
            "metadata": [{"content_metadata": {}}],
        })

        result = self.processor._extract_text(df)

        meta = result.iloc[0]["metadata"]
        # Must be in metadata["content"] for nv-ingest chunker
        assert meta["content"] == content
        # Also in content_metadata["text"] for consistency
        assert meta["content_metadata"]["text"] == content

    def test_extract_text_handles_unicode(self) -> None:
        """Test _extract_text handles UTF-8 content."""
        import base64

        content = "Hello, \u4e16\u754c!"  # "Hello, 世界!"
        encoded = base64.b64encode(content.encode("utf-8")).decode()

        df = pd.DataFrame({
            "content": [encoded],
            "metadata": [{"content_metadata": {}}],
        })

        result = self.processor._extract_text(df)

        text = result.iloc[0]["metadata"]["content_metadata"]["text"]
        assert content in text

    def test_extract_text_fallback_to_latin1(self) -> None:
        """Test _extract_text falls back to latin-1 encoding."""
        import base64

        # Create content that's valid latin-1 but not UTF-8
        content = bytes([0xe0, 0xe1, 0xe2])  # Latin-1 specific chars
        encoded = base64.b64encode(content).decode()

        df = pd.DataFrame({
            "content": [encoded],
            "metadata": [{"content_metadata": {}}],
        })

        # Should not raise, should fall back to latin-1
        result = self.processor._extract_text(df)
        meta = result.iloc[0]["metadata"]
        assert "text" in meta["content_metadata"]
        # metadata["content"] must also be set for chunker
        assert "content" in meta
        assert len(meta["content"]) > 0

    # ==========================================
    # HTML extraction tests
    # ==========================================

    def test_extract_html_removes_script_tags(self) -> None:
        """Test _extract_html removes script elements and sets both fields."""
        import base64

        html = "<html><body><script>alert('xss')</script><p>Hello</p></body></html>"
        encoded = base64.b64encode(html.encode()).decode()

        df = pd.DataFrame({
            "content": [encoded],
            "metadata": [{"content_metadata": {}}],
        })

        result = self.processor._extract_html(df)

        meta = result.iloc[0]["metadata"]
        text = meta["content_metadata"]["text"]
        assert "alert" not in text
        assert "Hello" in text
        # metadata["content"] must also be set for nv-ingest chunker
        assert meta["content"] == text

    def test_extract_html_removes_style_tags(self) -> None:
        """Test _extract_html removes style elements."""
        import base64

        html = "<html><head><style>body{color:red}</style></head><body>Content</body></html>"
        encoded = base64.b64encode(html.encode()).decode()

        df = pd.DataFrame({
            "content": [encoded],
            "metadata": [{"content_metadata": {}}],
        })

        result = self.processor._extract_html(df)

        text = result.iloc[0]["metadata"]["content_metadata"]["text"]
        assert "color:red" not in text
        assert "Content" in text

    # ==========================================
    # Structured image extraction tests
    # ==========================================

    def test_extract_structured_images_empty_when_yolox_disabled(self) -> None:
        """Test no structured images when YOLOX is disabled."""
        with patch.object(self.processor._settings, "yolox_enabled", False):
            df = pd.DataFrame({
                "metadata": [{
                    "content_metadata": {
                        "type": "table",
                        "image_data": "base64data",
                    }
                }]
            })

            result = self.processor._extract_structured_images(df)

            assert result == []

    def test_extract_structured_images_with_yolox(self) -> None:
        """Test structured images extracted when YOLOX enabled."""
        import base64

        image_bytes = b"\x89PNG\r\n\x1a\n"  # Fake PNG header
        encoded = base64.b64encode(image_bytes).decode()

        df = pd.DataFrame({
            "metadata": [{
                "content_metadata": {
                    "type": "table",
                    "image_data": encoded,
                }
            }]
        })

        with patch.object(self.processor._settings, "yolox_enabled", True):
            result = self.processor._extract_structured_images(df)

        assert len(result) == 1
        assert result[0] == image_bytes

    def test_extract_structured_images_filters_by_type(self) -> None:
        """Test only table/chart/infographic types are extracted."""
        import base64

        image_bytes = b"imagedata"
        encoded = base64.b64encode(image_bytes).decode()

        df = pd.DataFrame({
            "metadata": [
                {"content_metadata": {"type": "table", "image_data": encoded}},
                {"content_metadata": {"type": "chart", "image_data": encoded}},
                {"content_metadata": {"type": "infographic", "image_data": encoded}},
                {"content_metadata": {"type": "text", "image_data": encoded}},  # Should be skipped
            ]
        })

        with patch.object(self.processor._settings, "yolox_enabled", True):
            result = self.processor._extract_structured_images(df)

        assert len(result) == 3

    # ==========================================
    # YOLOX endpoints helper tests
    # ==========================================

    def test_build_yolox_endpoints_returns_tuple(self) -> None:
        """Test _build_yolox_endpoints returns correct tuple format."""
        result = self.processor._build_yolox_endpoints()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] is None
        assert result[1] == self.settings.yolox_endpoint

    def test_build_yolox_endpoints_uses_setting(self) -> None:
        """Test _build_yolox_endpoints reflects current yolox_endpoint setting."""
        with patch.object(self.processor._settings, "yolox_endpoint", "http://custom:9000"):
            result = self.processor._build_yolox_endpoints()

            assert result == (None, "http://custom:9000")

    # ==========================================
    # Extraction routing tests
    # ==========================================

    def test_extract_routes_by_extractor_type(self) -> None:
        """Test _extract routes to correct extractor based on MIME type."""
        # Verify the router returns correct extractor types
        test_cases = [
            ("application/pdf", "pdf"),
            ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
            ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"),
            ("image/png", "image"),
            ("audio/mpeg", "audio"),
            ("video/mp4", "video"),
            ("text/plain", "text"),
            ("text/html", "html"),
        ]

        for mime_type, expected_extractor in test_cases:
            extractor = self.processor._router.get_extractor_type(mime_type)
            assert extractor == expected_extractor, f"{mime_type} should use {expected_extractor}"

    # ==========================================
    # nv-ingest-api call signature tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_extract_pdf_passes_correct_kwargs_yolox_disabled(self) -> None:
        """Test PDF extraction with yolox_enabled=False (default)."""
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_pdf_pdfium",
                mock_fn,
            ):
                df = pd.DataFrame({"test": [1]})
                await self.processor._extract(df, "application/pdf", document_id=1)

                mock_fn.assert_called_once()
                kwargs = mock_fn.call_args[1]
                # Must use df_extraction_ledger (PDF uses decorator path)
                assert "df_extraction_ledger" in kwargs
                # yolox_endpoints always passed (schema crashes on None)
                assert kwargs["yolox_endpoints"] == (None, self.settings.yolox_endpoint)
                # extract_text always True
                assert kwargs["extract_text"] is True
                # YOLOX-dependent flags are False when yolox_enabled=False
                assert kwargs["extract_tables"] is False
                assert kwargs["extract_charts"] is False
                assert kwargs["extract_images"] is False
                assert kwargs["extract_infographics"] is False

    @pytest.mark.asyncio
    async def test_extract_pdf_passes_correct_kwargs_yolox_enabled(self) -> None:
        """Test PDF extraction with yolox_enabled=True enables all flags."""
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_pdf_pdfium",
                mock_fn,
            ):
                with patch.object(self.processor._settings, "yolox_enabled", True):
                    df = pd.DataFrame({"test": [1]})
                    await self.processor._extract(df, "application/pdf", document_id=1)

                    kwargs = mock_fn.call_args[1]
                    assert kwargs["yolox_endpoints"] == (None, self.settings.yolox_endpoint)
                    assert kwargs["extract_text"] is True
                    assert kwargs["extract_tables"] is True
                    assert kwargs["extract_charts"] is True
                    assert kwargs["extract_images"] is True
                    assert kwargs["extract_infographics"] is True

    @pytest.mark.asyncio
    async def test_extract_pdf_always_passes_yolox_endpoints(self) -> None:
        """Test PDF extraction ALWAYS passes yolox_endpoints (schema requires it).

        PDFiumConfigSchema.validate_endpoints crashes with TypeError when
        yolox_endpoints is None. A valid endpoint tuple must always be supplied
        regardless of yolox_enabled.
        """
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_pdf_pdfium",
                mock_fn,
            ):
                with patch.object(self.processor._settings, "yolox_enabled", False):
                    df = pd.DataFrame({"test": [1]})
                    await self.processor._extract(df, "application/pdf", document_id=1)

                    kwargs = mock_fn.call_args[1]
                    # Must STILL pass valid endpoints — schema crashes on None
                    assert kwargs["yolox_endpoints"] == (None, self.settings.yolox_endpoint)
                    # YOLOX-dependent flags are False when disabled
                    assert kwargs["extract_tables"] is False
                    assert kwargs["extract_charts"] is False
                    assert kwargs["extract_images"] is False
                    assert kwargs["extract_infographics"] is False
                    # Text extraction always on
                    assert kwargs["extract_text"] is True

    @pytest.mark.asyncio
    async def test_extract_docx_passes_correct_kwargs(self) -> None:
        """Test DOCX extraction uses df_ledger (not df_extraction_ledger)."""
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_docx",
                mock_fn,
            ):
                df = pd.DataFrame({"test": [1]})
                await self.processor._extract(
                    df,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    document_id=1,
                )

                mock_fn.assert_called_once()
                kwargs = mock_fn.call_args[1]
                assert "df_ledger" in kwargs
                assert "df_extraction_ledger" not in kwargs
                assert kwargs["extract_text"] is True

    @pytest.mark.asyncio
    async def test_extract_pptx_passes_correct_kwargs(self) -> None:
        """Test PPTX extraction uses df_ledger (not df_extraction_ledger)."""
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_pptx",
                mock_fn,
            ):
                df = pd.DataFrame({"test": [1]})
                await self.processor._extract(
                    df,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    document_id=1,
                )

                mock_fn.assert_called_once()
                kwargs = mock_fn.call_args[1]
                assert "df_ledger" in kwargs
                assert "df_extraction_ledger" not in kwargs

    @pytest.mark.asyncio
    async def test_extract_image_passes_correct_kwargs(self) -> None:
        """Test image extraction uses df_ledger and respects yolox_enabled."""
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_image",
                mock_fn,
            ):
                df = pd.DataFrame({"test": [1]})
                await self.processor._extract(df, "image/png", document_id=1)

                mock_fn.assert_called_once()
                kwargs = mock_fn.call_args[1]
                assert "df_ledger" in kwargs
                assert "df_extraction_ledger" not in kwargs
                assert kwargs["extract_text"] is True
                # Default yolox_enabled=False
                assert kwargs["extract_images"] is False
                assert kwargs["extract_tables"] is False

    @pytest.mark.asyncio
    async def test_extract_audio_passes_correct_kwargs(self) -> None:
        """Test audio extraction uses df_ledger and audio_endpoints tuple."""
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_audio",
                mock_fn,
            ):
                with patch.object(self.processor._settings, "riva_enabled", True):
                    df = pd.DataFrame({"test": [1]})
                    await self.processor._extract(df, "audio/mpeg", document_id=1)

                    mock_fn.assert_called_once()
                    kwargs = mock_fn.call_args[1]
                    assert "df_ledger" in kwargs
                    assert "df_extraction_ledger" not in kwargs
                    assert "audio_endpoints" in kwargs
                    assert isinstance(kwargs["audio_endpoints"], tuple)
                    assert kwargs["audio_endpoints"][0] == self.settings.riva_endpoint
                    assert kwargs["audio_infer_protocol"] == "grpc"

    @pytest.mark.asyncio
    async def test_extract_audio_returns_empty_when_riva_disabled(self) -> None:
        """Test audio extraction returns empty when Riva disabled."""
        # Default settings have riva_enabled=False
        df = pd.DataFrame({"test": [1]})

        result = await self.processor._extract(df, "audio/mpeg", document_id=1)

        assert result.empty

    @pytest.mark.asyncio
    async def test_extract_docx_with_yolox_enabled(self) -> None:
        """Test DOCX passes yolox_endpoints and enables flags when YOLOX enabled."""
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_docx",
                mock_fn,
            ):
                with patch.object(self.processor._settings, "yolox_enabled", True):
                    df = pd.DataFrame({"test": [1]})
                    await self.processor._extract(
                        df,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        document_id=1,
                    )

                    kwargs = mock_fn.call_args[1]
                    assert kwargs["yolox_endpoints"] == (None, self.settings.yolox_endpoint)
                    assert kwargs["extract_tables"] is True
                    assert kwargs["extract_charts"] is True
                    assert kwargs["extract_images"] is True

    @pytest.mark.asyncio
    async def test_extract_docx_always_passes_yolox_endpoints(self) -> None:
        """Test DOCX always passes yolox_endpoints (schema requires it).

        DocxExtractorSchema.validate_endpoints also crashes on None.
        Endpoints must always be a valid tuple, even when YOLOX is disabled.
        YOLOX-dependent flags are False when yolox_enabled=False.
        """
        mock_fn = MagicMock(return_value=pd.DataFrame())
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_docx",
                mock_fn,
            ):
                with patch.object(self.processor._settings, "yolox_enabled", False):
                    df = pd.DataFrame({"test": [1]})
                    await self.processor._extract(
                        df,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        document_id=1,
                    )

                    kwargs = mock_fn.call_args[1]
                    # Must STILL pass valid endpoints — schema crashes on None
                    assert kwargs["yolox_endpoints"] == (None, self.settings.yolox_endpoint)
                    # YOLOX-dependent flags are False when disabled
                    assert kwargs["extract_tables"] is False
                    assert kwargs["extract_charts"] is False
                    assert kwargs["extract_images"] is False
                    # Text extraction always on
                    assert kwargs["extract_text"] is True

    @pytest.mark.asyncio
    async def test_extract_wraps_exception_in_extraction_error(self) -> None:
        """Test extraction errors are wrapped in ExtractionError."""
        mock_fn = MagicMock(side_effect=RuntimeError("pdfium crashed"))
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_pdf_pdfium",
                mock_fn,
            ):
                df = pd.DataFrame({"test": [1]})

                with pytest.raises(ExtractionError) as exc_info:
                    await self.processor._extract(df, "application/pdf", document_id=42)

                assert exc_info.value.document_id == 42
                assert "pdfium crashed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_raises_type_specific_exception_for_pdf(self) -> None:
        """Test PDF extraction failures raise PDFExtractionError (not generic)."""
        mock_fn = MagicMock(side_effect=RuntimeError("bad PDF"))
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_pdf_pdfium",
                mock_fn,
            ):
                df = pd.DataFrame({"test": [1]})

                with pytest.raises(PDFExtractionError) as exc_info:
                    await self.processor._extract(df, "application/pdf", document_id=1)

                assert exc_info.value.source_type == "PDF"

    @pytest.mark.asyncio
    async def test_extract_raises_type_specific_exception_for_docx(self) -> None:
        """Test DOCX extraction failures raise DocxExtractionError."""
        mock_fn = MagicMock(side_effect=RuntimeError("not a zip"))
        with patch.dict(
            "sys.modules",
            {"nv_ingest_api": MagicMock(), "nv_ingest_api.interface": MagicMock(), "nv_ingest_api.interface.extract": MagicMock()},
        ):
            with patch(
                "nv_ingest_api.interface.extract.extract_primitives_from_docx",
                mock_fn,
            ):
                df = pd.DataFrame({"test": [1]})

                with pytest.raises(DocxExtractionError) as exc_info:
                    await self.processor._extract(
                        df,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        document_id=2,
                    )

                assert exc_info.value.source_type == "DOCX"

    # ==========================================
    # Video extraction tests
    # ==========================================

    def test_extract_video_returns_empty(self) -> None:
        """Test video extraction returns empty (early access feature)."""
        df = pd.DataFrame({"test": [1]})

        result = self.processor._extract_video(df)

        assert result.empty

    # ==========================================
    # Chunking tests
    # ==========================================

    @pytest.mark.asyncio
    async def test_chunk_content_empty_dataframe(self) -> None:
        """Test chunking returns empty list for empty DataFrame."""
        df = pd.DataFrame()

        result = await self.processor._chunk_content(df, document_id=1)

        assert result == []

    @pytest.mark.asyncio
    async def test_chunk_content_extracts_text_from_metadata(self) -> None:
        """Test chunking extracts text from metadata['content'].

        nv-ingest stores chunk text in metadata['content'], NOT in
        metadata['content_metadata']['text'].
        """
        nv_ingest = pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        # Mock matches real nv-ingest chunker output: text in metadata["content"]
        with patch(
            "nv_ingest_api.interface.transform.transform_text_split_and_tokenize"
        ) as mock_transform:
            mock_transform.return_value = pd.DataFrame({
                "metadata": [
                    {"content": "chunk 1", "content_metadata": {"type": "text"}},
                    {"content": "chunk 2", "content_metadata": {"type": "text"}},
                    {"content": "  ", "content_metadata": {"type": "text"}},  # Empty, should be filtered
                ]
            })

            df = pd.DataFrame({"test": [1]})
            result = await self.processor._chunk_content(df, document_id=1)

            assert result == ["chunk 1", "chunk 2"]

    @pytest.mark.asyncio
    async def test_chunk_content_uses_settings(self) -> None:
        """Test chunking uses settings for size and overlap."""
        nv_ingest = pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        with patch(
            "nv_ingest_api.interface.transform.transform_text_split_and_tokenize"
        ) as mock_transform:
            mock_transform.return_value = pd.DataFrame()

            df = pd.DataFrame({"test": [1]})
            await self.processor._chunk_content(df, document_id=1)

            # Verify settings were passed
            call_kwargs = mock_transform.call_args[1]
            assert call_kwargs["chunk_size"] == self.settings.chunk_size
            assert call_kwargs["chunk_overlap"] == self.settings.chunk_overlap
            assert call_kwargs["tokenizer"] == self.settings.tokenizer

    @pytest.mark.asyncio
    async def test_chunk_content_passes_hf_token_when_set(self) -> None:
        """Test chunking passes hugging_face_access_token (not 'params') when token is set.

        The nv-ingest-api function signature uses hugging_face_access_token
        as a direct kwarg, NOT a 'params' dict. This test prevents regression
        of the wrong kwarg name being used.
        """
        nv_ingest = pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        with patch(
            "nv_ingest_api.interface.transform.transform_text_split_and_tokenize"
        ) as mock_transform:
            mock_transform.return_value = pd.DataFrame()

            with patch.object(self.processor._settings, "hf_access_token", "hf_test_token"):
                df = pd.DataFrame({"test": [1]})
                await self.processor._chunk_content(df, document_id=1)

                call_kwargs = mock_transform.call_args[1]
                # Must use hugging_face_access_token, NOT params
                assert "hugging_face_access_token" in call_kwargs
                assert call_kwargs["hugging_face_access_token"] == "hf_test_token"
                assert "params" not in call_kwargs

    @pytest.mark.asyncio
    async def test_chunk_content_omits_hf_token_when_none(self) -> None:
        """Test chunking does NOT pass hugging_face_access_token when token is None.

        When no HF token is configured (models are pre-cached at Docker build
        time), the kwarg should be omitted entirely to let nv-ingest-api
        use its default.
        """
        nv_ingest = pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        with patch(
            "nv_ingest_api.interface.transform.transform_text_split_and_tokenize"
        ) as mock_transform:
            mock_transform.return_value = pd.DataFrame()

            with patch.object(self.processor._settings, "hf_access_token", None):
                df = pd.DataFrame({"test": [1]})
                await self.processor._chunk_content(df, document_id=1)

                call_kwargs = mock_transform.call_args[1]
                assert "hugging_face_access_token" not in call_kwargs
                assert "params" not in call_kwargs

    @pytest.mark.asyncio
    async def test_chunk_content_raises_chunking_error(self) -> None:
        """Test chunking raises ChunkingError on failure."""
        nv_ingest = pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        with patch(
            "nv_ingest_api.interface.transform.transform_text_split_and_tokenize",
            side_effect=Exception("tokenizer failed"),
        ):
            df = pd.DataFrame({"test": [1]})

            with pytest.raises(ChunkingError) as exc_info:
                await self.processor._chunk_content(df, document_id=123)

            assert exc_info.value.document_id == 123


class TestDocumentProcessorIntegration:
    """Integration-style tests for full processing flow."""

    def setup_method(self) -> None:
        """Create processor instance."""
        reset_settings()
        self.settings = IngestorSettings()
        self.processor = DocumentProcessor(self.settings)

    def teardown_method(self) -> None:
        """Reset after tests."""
        reset_settings()

    @pytest.mark.asyncio
    async def test_process_text_file_end_to_end(self) -> None:
        """Test full processing of a text file."""
        nv_ingest = pytest.importorskip("nv_ingest_api", reason="nv_ingest_api not installed")

        content = "This is a test document with some content for chunking."

        # Mock the chunking function — nv-ingest puts text in metadata["content"]
        with patch(
            "nv_ingest_api.interface.transform.transform_text_split_and_tokenize"
        ) as mock_transform:
            mock_transform.return_value = pd.DataFrame({
                "metadata": [
                    {"content": content, "content_metadata": {"type": "text"}},
                ]
            })

            chunks, images = await self.processor.process(
                file_bytes=content.encode(),
                document_id=1,
                file_name="test.txt",
                mime_type="text/plain",
            )

            assert len(chunks) == 1
            assert chunks[0] == content
            assert images == []  # No structured images for text

    @pytest.mark.asyncio
    async def test_process_returns_tuple(self) -> None:
        """Test process returns (chunks, images) tuple."""
        with patch.object(self.processor, "_extract", return_value=pd.DataFrame()):
            with patch.object(self.processor, "_chunk_content", return_value=["chunk1"]):
                with patch.object(self.processor, "_extract_structured_images", return_value=[]):
                    result = await self.processor.process(
                        file_bytes=b"test",
                        document_id=1,
                        file_name="test.pdf",
                        mime_type="application/pdf",
                    )

                    assert isinstance(result, tuple)
                    assert len(result) == 2
                    chunks, images = result
                    assert isinstance(chunks, list)
                    assert isinstance(images, list)
