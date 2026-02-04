"""
Document processor using nv_ingest_api.

Handles extraction and chunking for all 18 supported file types.
Uses NVIDIA's tokenizer-based splitter (not langchain character-based).
"""

import base64
import logging
from typing import Any

import pandas as pd

from ingestor.config import IngestorSettings
from ingestor.logic.exceptions import (
    ChunkingError,
    ExtractionError,
    UnsupportedMimeTypeError,
)
from ingestor.logic.mime_router import MimeRouter

logger = logging.getLogger("echomind-ingestor.processor")


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

        logger.info(
            "📄 Processing document %d: %s (%s)",
            document_id,
            file_name,
            mime_type,
        )

        # Build input DataFrame
        df = self._build_dataframe(file_bytes, document_id, file_name, mime_type)

        # Extract content
        extracted_df = await self._extract(df, mime_type, document_id)

        # Chunk text content
        chunks = await self._chunk_content(extracted_df, document_id)

        # Extract structured images (tables/charts)
        structured_images = self._extract_structured_images(extracted_df)

        logger.info(
            "🏁 Processed document %d: %d chunks, %d images",
            document_id,
            len(chunks),
            len(structured_images),
        )

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
            if extractor_type == "pdf":
                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_pdf_pdfium,
                )
                return extract_primitives_from_pdf_pdfium(
                    df_extraction_ledger=df,
                    extract_text=True,
                    extract_tables=self._settings.yolox_enabled,
                    extract_charts=self._settings.yolox_enabled,
                    extract_images=False,
                )

            elif extractor_type == "docx":
                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_docx,
                )
                return extract_primitives_from_docx(
                    df_extraction_ledger=df,
                )

            elif extractor_type == "pptx":
                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_pptx,
                )
                return extract_primitives_from_pptx(
                    df_extraction_ledger=df,
                )

            elif extractor_type == "html":
                # HTML uses text extractor with markdown conversion
                return self._extract_html(df)

            elif extractor_type == "image":
                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_image,
                )
                return extract_primitives_from_image(
                    df_extraction_ledger=df,
                )

            elif extractor_type == "audio":
                if not self._settings.riva_enabled:
                    logger.warning(
                        "⚠️ Audio extraction disabled (Riva NIM not enabled)"
                    )
                    return pd.DataFrame()

                from nv_ingest_api.interface.extract import (
                    extract_primitives_from_audio,
                )
                return extract_primitives_from_audio(
                    df_extraction_ledger=df,
                    grpc_endpoint=self._settings.riva_endpoint,
                )

            elif extractor_type == "video":
                logger.warning("⚠️ Video extraction is early access")
                return self._extract_video(df)

            elif extractor_type == "text":
                return self._extract_text(df)

            else:
                raise UnsupportedMimeTypeError(mime_type)

        except UnsupportedMimeTypeError:
            raise
        except Exception as e:
            logger.exception(
                "❌ Extraction failed for document %d: %s",
                document_id,
                e,
            )
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

                df.at[idx, "metadata"] = {
                    **row["metadata"],
                    "content_metadata": {
                        **row["metadata"].get("content_metadata", {}),
                        "text": markdown.strip(),
                    },
                }
            except Exception as e:
                logger.warning("⚠️ HTML extraction warning: %s", e)

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
                df.at[idx, "metadata"] = {
                    **row["metadata"],
                    "content_metadata": {
                        **row["metadata"].get("content_metadata", {}),
                        "text": content,
                    },
                }
            except UnicodeDecodeError:
                # Try with latin-1 as fallback
                content = base64.b64decode(row["content"]).decode("latin-1")
                df.at[idx, "metadata"] = {
                    **row["metadata"],
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

            chunked_df = transform_text_split_and_tokenize(
                inputs=extracted_df,
                tokenizer=self._settings.tokenizer,
                chunk_size=self._settings.chunk_size,
                chunk_overlap=self._settings.chunk_overlap,
                split_source_types=["text", "PDF", "DOCX", "PPTX", "HTML"],
            )

            # Extract text from chunked DataFrame
            chunks: list[str] = []
            for _, row in chunked_df.iterrows():
                metadata = row.get("metadata", {})
                content_meta = metadata.get("content_metadata", {})

                text = content_meta.get("text")
                if text and isinstance(text, str) and text.strip():
                    chunks.append(text.strip())

            logger.info(
                "✂️ Chunked document %d: %d chunks (size=%d, overlap=%d)",
                document_id,
                len(chunks),
                self._settings.chunk_size,
                self._settings.chunk_overlap,
            )

            return chunks

        except Exception as e:
            logger.exception(
                "❌ Chunking failed for document %d: %s",
                document_id,
                e,
            )
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
            logger.info(
                "🖼️ Extracted %d structured images (tables/charts)",
                len(images),
            )

        return images
