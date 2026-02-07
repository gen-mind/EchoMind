"""
Document processor using nv_ingest_api.

Handles extraction and chunking for all 18 supported file types.
Uses NVIDIA's tokenizer-based splitter (not langchain character-based).
"""

import asyncio
import base64
import functools
import logging
from typing import Any

import pandas as pd

from ingestor.config import IngestorSettings
from ingestor.logic.exceptions import (
    AudioExtractionError,
    ChunkingError,
    DocxExtractionError,
    ExtractionError,
    HtmlExtractionError,
    ImageExtractionError,
    PDFExtractionError,
    PptxExtractionError,
    TextExtractionError,
    UnsupportedMimeTypeError,
    VideoExtractionError,
)
from ingestor.logic.mime_router import MimeRouter

logger = logging.getLogger("echomind-ingestor.processor")

# Map extractor type → specific exception class for precise error handling
_EXTRACTOR_ERROR_MAP: dict[str, type[ExtractionError]] = {
    "pdf": PDFExtractionError,
    "docx": DocxExtractionError,
    "pptx": PptxExtractionError,
    "html": HtmlExtractionError,
    "image": ImageExtractionError,
    "audio": AudioExtractionError,
    "video": VideoExtractionError,
    "text": TextExtractionError,
}


class DocumentProcessor:
    """
    Wrapper around nv_ingest_api for document processing.

    Responsibilities:
    - Route content by MIME type
    - Build DataFrame for nv_ingest_api
    - Extract content using appropriate extractor
    - Chunk content using tokenizer-based splitter
    - Return text chunks and optional structured images

    Attributes:
        settings: Ingestor service settings.
    """

    def __init__(self, settings: IngestorSettings) -> None:
        """
        Initialize document processor.

        Args:
            settings: Service configuration.
        """
        self._settings = settings
        self._router = MimeRouter()

    def _build_yolox_endpoints(self) -> tuple[str | None, str]:
        """
        Build YOLOX endpoint tuple for nv-ingest-api extractors.

        Returns a ``(gRPC, HTTP)`` tuple expected by nv-ingest-api when
        table/chart extraction via YOLOX is enabled. Only call this when
        ``yolox_enabled`` is ``True`` — passing a non-None endpoint tuple
        causes nv-ingest to attempt a connection even if extract_tables and
        extract_charts are ``False``.

        Returns:
            Tuple of (gRPC endpoint, HTTP endpoint) for YOLOX services.
        """
        return (None, self._settings.yolox_endpoint)

    async def process(
        self,
        file_bytes: bytes,
        document_id: int,
        file_name: str,
        mime_type: str,
    ) -> tuple[list[str], list[bytes]]:
        """
        Extract content and chunk using nv_ingest_api.

        Args:
            file_bytes: Raw file content.
            document_id: Document ID for tracking.
            file_name: Original filename.
            mime_type: MIME type of file.

        Returns:
            Tuple of (text_chunks, structured_images):
            - text_chunks: List of text strings ready for embedding
            - structured_images: List of image bytes (tables/charts)

        Raises:
            UnsupportedMimeTypeError: If MIME type not supported.
            ExtractionError: If extraction fails.
            ChunkingError: If chunking fails.
        """
        # Validate MIME type
        if not self._router.is_supported(mime_type):
            raise UnsupportedMimeTypeError(mime_type)

        logger.debug(f"[id:{document_id}] Extracting {file_name} ({mime_type})")

        # Build input DataFrame
        df = self._build_dataframe(file_bytes, document_id, file_name, mime_type)

        # Extract content
        extracted_df = await self._extract(df, mime_type, document_id)

        # Chunk text content
        chunks = await self._chunk_content(extracted_df, document_id)

        # Extract structured images (tables/charts)
        structured_images = self._extract_structured_images(extracted_df)

        logger.debug(f"[id:{document_id}] Extracted: {len(chunks)} chunks, {len(structured_images)} images")

        return chunks, structured_images

    def _build_dataframe(
        self,
        file_bytes: bytes,
        document_id: int,
        file_name: str,
        mime_type: str,
    ) -> pd.DataFrame:
        """
        Build pandas DataFrame in nv_ingest_api format.

        Args:
            file_bytes: Raw file content.
            document_id: Document ID.
            file_name: Original filename.
            mime_type: MIME type.

        Returns:
            DataFrame with columns: source_id, source_name, content,
            document_type, metadata.
        """
        document_type = self._router.get_document_type(mime_type)

        return pd.DataFrame({
            "source_id": [str(document_id)],
            "source_name": [file_name],
            "content": [base64.b64encode(file_bytes).decode("utf-8")],
            "document_type": [document_type],
            "metadata": [{
                "content_metadata": {"type": "document"},
                "source_metadata": {
                    "source_name": file_name,
                    "source_id": str(document_id),
                },
            }],
        })

    @staticmethod
    def _unpack_extraction_result(result: pd.DataFrame | tuple) -> pd.DataFrame:
        """
        Normalize nv-ingest extraction results to a DataFrame.

        nv-ingest-api extractors are inconsistent: PDF extractor (decorator
        path) returns a plain DataFrame, while DOCX/PPTX/Image/Audio
        extractors (direct path) return ``(DataFrame, dict)`` tuples.

        Args:
            result: Extraction result — DataFrame or (DataFrame, dict) tuple.

        Returns:
            Extracted DataFrame, discarding metadata dict if present.
        """
        if isinstance(result, tuple):
            return result[0]
        return result

    async def _extract(
        self,
        df: pd.DataFrame,
        mime_type: str,
        document_id: int,
    ) -> pd.DataFrame:
        """
        Extract content using appropriate nv_ingest_api function.

        Args:
            df: Input DataFrame.
            mime_type: MIME type for routing.
            document_id: Document ID for error context.

        Returns:
            DataFrame with extracted content.

        Raises:
            ExtractionError: If extraction fails.
        """
        extractor_type = self._router.get_extractor_type(mime_type)

        try:
            # Import nv_ingest_api functions lazily to avoid startup cost
            #
            # YOLOX-dependent flags (tables, charts, images, infographics)
            # are gated on yolox_enabled. When YOLOX NIM is not deployed,
            # these flags cause nv-ingest to hang ~30s/page retrying.
            # yolox_endpoints tuple is ALWAYS passed — schema crashes on None.
            #
            # All nv-ingest extraction calls are synchronous and CPU-bound.
            # We run them in a thread pool executor to avoid blocking the
            # event loop for large files.
            yolox_on = self._settings.yolox_enabled
            loop = asyncio.get_running_loop()

            if extractor_type == "pdf":
                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_pdf_pdfium,
                )

                # PDF extractor (decorator path) returns DataFrame directly
                return await loop.run_in_executor(
                    None,
                    functools.partial(
                        extract_primitives_from_pdf_pdfium,
                        df_extraction_ledger=df,
                        extract_text=True,
                        extract_tables=yolox_on,
                        extract_charts=yolox_on,
                        extract_images=yolox_on,
                        extract_infographics=yolox_on,
                        yolox_endpoints=self._build_yolox_endpoints(),
                    ),
                )

            elif extractor_type == "docx":
                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_docx,
                )

                # DOCX/PPTX/Image/Audio (direct path) return (DataFrame, dict)
                raw = await loop.run_in_executor(
                    None,
                    functools.partial(
                        extract_primitives_from_docx,
                        df_ledger=df,
                        extract_text=True,
                        extract_tables=yolox_on,
                        extract_charts=yolox_on,
                        extract_images=yolox_on,
                        yolox_endpoints=self._build_yolox_endpoints(),
                    ),
                )
                return self._unpack_extraction_result(raw)

            elif extractor_type == "pptx":
                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_pptx,
                )

                raw = await loop.run_in_executor(
                    None,
                    functools.partial(
                        extract_primitives_from_pptx,
                        df_ledger=df,
                        extract_text=True,
                        extract_tables=yolox_on,
                        extract_charts=yolox_on,
                        extract_images=yolox_on,
                        yolox_endpoints=self._build_yolox_endpoints(),
                    ),
                )
                return self._unpack_extraction_result(raw)

            elif extractor_type == "html":
                # HTML uses our own text extractor (lightweight, no NIM needed)
                return await loop.run_in_executor(
                    None, self._extract_html, df,
                )

            elif extractor_type == "image":
                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_image,
                )

                raw = await loop.run_in_executor(
                    None,
                    functools.partial(
                        extract_primitives_from_image,
                        df_ledger=df,
                        extract_text=True,
                        extract_tables=yolox_on,
                        extract_charts=yolox_on,
                        extract_images=yolox_on,
                        yolox_endpoints=self._build_yolox_endpoints(),
                    ),
                )
                return self._unpack_extraction_result(raw)

            elif extractor_type == "audio":
                if not self._settings.riva_enabled:
                    logger.warning(
                        "⚠️ Audio extraction disabled (Riva NIM not enabled)"
                    )
                    return pd.DataFrame()

                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_audio,
                )

                raw = await loop.run_in_executor(
                    None,
                    functools.partial(
                        extract_primitives_from_audio,
                        df_ledger=df,
                        audio_endpoints=(self._settings.riva_endpoint, ""),
                        audio_infer_protocol="grpc",
                    ),
                )
                return self._unpack_extraction_result(raw)

            elif extractor_type == "video":
                logger.warning("⚠️ Video extraction is early access")
                return self._extract_video(df)

            elif extractor_type == "text":
                # Text extraction is lightweight (base64 decode only)
                return await loop.run_in_executor(
                    None, self._extract_text, df,
                )

            else:
                raise UnsupportedMimeTypeError(mime_type)

        except UnsupportedMimeTypeError:
            raise
        except Exception as e:
            logger.exception(f"❌ [id:{document_id}] Extraction failed: {e}")

            # Raise type-specific exception for better error handling
            error_cls = _EXTRACTOR_ERROR_MAP.get(extractor_type)
            if error_cls:
                raise error_cls(
                    reason=str(e),
                    document_id=document_id,
                ) from e
            raise ExtractionError(
                source_type=extractor_type,
                reason=str(e),
                document_id=document_id,
            ) from e

    def _extract_html(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract content from HTML files.

        Converts HTML to markdown for text extraction.

        Args:
            df: Input DataFrame with HTML content.

        Returns:
            DataFrame with extracted text.
        """
        from bs4 import BeautifulSoup
        import html2text

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True

        for idx, row in df.iterrows():
            try:
                content = base64.b64decode(row["content"]).decode("utf-8")
                soup = BeautifulSoup(content, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Convert to markdown
                markdown = h.handle(str(soup))

                text = markdown.strip()
                df.at[idx, "metadata"] = {
                    **row["metadata"],
                    "content": text,
                    "content_metadata": {
                        **row["metadata"].get("content_metadata", {}),
                        "text": text,
                    },
                }
            except Exception as e:
                logger.warning(f"⚠️ HTML extraction warning: {e}")

        return df

    def _extract_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract content from plain text files.

        Text files are passed through as-is.

        Args:
            df: Input DataFrame with text content.

        Returns:
            DataFrame with text content in metadata.
        """
        for idx, row in df.iterrows():
            try:
                content = base64.b64decode(row["content"]).decode("utf-8")
            except UnicodeDecodeError:
                # Try with latin-1 as fallback
                content = base64.b64decode(row["content"]).decode("latin-1")

            # Set text in both locations:
            # - metadata["content"]: where nv-ingest chunker reads from
            # - content_metadata["text"]: for consistency
            df.at[idx, "metadata"] = {
                **row["metadata"],
                "content": content,
                "content_metadata": {
                    **row["metadata"].get("content_metadata", {}),
                    "text": content,
                },
            }

        return df

    def _extract_video(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract content from video files (early access).

        Args:
            df: Input DataFrame with video content.

        Returns:
            DataFrame with extracted frames/audio.
        """
        # Video extraction is early access in nv-ingest
        # Return empty for now
        logger.warning("⚠️ Video extraction not yet implemented")
        return pd.DataFrame()

    async def _chunk_content(
        self,
        extracted_df: pd.DataFrame,
        document_id: int,
    ) -> list[str]:
        """
        Chunk content using NVIDIA's tokenizer-based splitter.

        Uses HuggingFace AutoTokenizer for token-boundary splitting.
        NOT character-based like langchain.

        Args:
            extracted_df: DataFrame with extracted content.
            document_id: Document ID for error context.

        Returns:
            List of text chunks.

        Raises:
            ChunkingError: If chunking fails.
        """
        if extracted_df.empty:
            return []

        try:
            from nv_ingest_api.interface.transform import (
                transform_text_split_and_tokenize,
            )

            # Tokenization is CPU-bound; run in executor to avoid
            # blocking the event loop for large documents.
            loop = asyncio.get_running_loop()
            chunked_df = await loop.run_in_executor(
                None,
                functools.partial(
                    transform_text_split_and_tokenize,
                    inputs=extracted_df,
                    tokenizer=self._settings.tokenizer,
                    chunk_size=self._settings.chunk_size,
                    chunk_overlap=self._settings.chunk_overlap,
                    split_source_types=["text", "PDF", "DOCX", "PPTX", "HTML"],
                ),
            )

            # Extract text from chunked DataFrame.
            # nv-ingest stores chunk text in metadata["content"],
            # NOT in metadata["content_metadata"]["text"].
            chunks: list[str] = []
            for _, row in chunked_df.iterrows():
                metadata = row.get("metadata", {})
                text = metadata.get("content")
                if text and isinstance(text, str) and text.strip():
                    chunks.append(text.strip())

            logger.info(f"✂️ [id:{document_id}] Chunked: {len(chunks)} chunks")

            return chunks

        except Exception as e:
            logger.exception(f"❌ [id:{document_id}] Chunking failed: {e}")
            raise ChunkingError(str(e), document_id) from e

    def _extract_structured_images(self, df: pd.DataFrame) -> list[bytes]:
        """
        Extract structured element images (tables/charts).

        Used for Strategy 2: embed tables/charts as images.

        Args:
            df: DataFrame with extracted content.

        Returns:
            List of image bytes for tables/charts.
        """
        images: list[bytes] = []

        if not self._settings.yolox_enabled:
            return images

        for _, row in df.iterrows():
            metadata = row.get("metadata", {})
            content_meta = metadata.get("content_metadata", {})

            # Check for table/chart image data
            if content_meta.get("type") in ("table", "chart", "infographic"):
                image_data = content_meta.get("image_data")
                if image_data:
                    if isinstance(image_data, str):
                        images.append(base64.b64decode(image_data))
                    elif isinstance(image_data, bytes):
                        images.append(image_data)

        if images:
            logger.info(f"🖼️ Extracted {len(images)} structured images (tables/charts)")

        return images
