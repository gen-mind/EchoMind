"""
Domain exceptions for the Ingestor Service.

All business logic errors are represented as domain exceptions.
Middleware converts these to protocol-specific responses.
"""


class IngestorError(Exception):
    """
    Base exception for all Ingestor service errors.

    Attributes:
        message: Human-readable error message.
    """

    def __init__(self, message: str) -> None:
        """
        Initialize IngestorError.

        Args:
            message: Human-readable error message.
        """
        self.message = message
        super().__init__(message)


class ValidationError(IngestorError):
    """
    Raised when input validation fails.

    This is a terminal error - retrying will not help.
    """

    def __init__(self, message: str, field: str | None = None) -> None:
        """
        Initialize ValidationError.

        Args:
            message: Validation error description.
            field: Optional field name that failed validation.
        """
        self.field = field
        full_message = f"Validation error: {message}"
        if field:
            full_message = f"Validation error on '{field}': {message}"
        super().__init__(full_message)


class DocumentNotFoundError(IngestorError):
    """
    Raised when document is not found in database.

    Terminal error - document doesn't exist.
    """

    def __init__(self, document_id: int) -> None:
        """
        Initialize DocumentNotFoundError.

        Args:
            document_id: ID of missing document.
        """
        self.document_id = document_id
        super().__init__(f"Document {document_id} not found")


class OwnershipMismatchError(IngestorError):
    """
    Raised when NATS message claims don't match database records.

    Security error - prevents processing documents under wrong user's collection.
    Terminal error - don't retry, this indicates a forged/corrupted message.
    """

    def __init__(
        self,
        document_id: int,
        expected_connector_id: int,
        actual_connector_id: int,
        expected_user_id: int | None = None,
        actual_user_id: int | None = None,
    ) -> None:
        """
        Initialize OwnershipMismatchError.

        Args:
            document_id: The document ID being processed.
            expected_connector_id: Connector ID from NATS message.
            actual_connector_id: Connector ID from database.
            expected_user_id: Optional user ID from NATS message.
            actual_user_id: Optional user ID from database.
        """
        self.document_id = document_id
        self.expected_connector_id = expected_connector_id
        self.actual_connector_id = actual_connector_id
        self.expected_user_id = expected_user_id
        self.actual_user_id = actual_user_id

        msg = (
            f"🚨 SECURITY: Ownership mismatch for document {document_id}. "
            f"Message claims connector_id={expected_connector_id}, "
            f"but document belongs to connector_id={actual_connector_id}"
        )
        if expected_user_id is not None and actual_user_id is not None:
            msg += (
                f". Message claims user_id={expected_user_id}, "
                f"but connector belongs to user_id={actual_user_id}"
            )
        super().__init__(msg)


class FileNotFoundInStorageError(IngestorError):
    """
    Raised when file is not found in MinIO.

    May be transient if file is still uploading.
    """

    def __init__(self, file_path: str, bucket: str) -> None:
        """
        Initialize FileNotFoundInStorageError.

        Args:
            file_path: Path to missing file.
            bucket: MinIO bucket name.
        """
        self.file_path = file_path
        self.bucket = bucket
        super().__init__(f"File not found: {bucket}/{file_path}")


class ExtractionError(IngestorError):
    """
    Raised when content extraction fails.

    May be transient (NIM unavailable) or terminal (corrupt file).
    """

    def __init__(
        self,
        source_type: str,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = True,
    ) -> None:
        """
        Initialize ExtractionError.

        Args:
            source_type: Type of source (pdf, docx, etc).
            reason: Reason for extraction failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient (retryable).
        """
        self.source_type = source_type
        self.reason = reason
        self.document_id = document_id
        self.is_transient = is_transient
        msg = f"Failed to extract {source_type}: {reason}"
        if document_id:
            msg = f"Failed to extract {source_type} for document {document_id}: {reason}"
        super().__init__(msg)


class PDFExtractionError(ExtractionError):
    """Raised when PDF extraction fails."""

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = True,
    ) -> None:
        """
        Initialize PDFExtractionError.

        Args:
            reason: Reason for extraction failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient.
        """
        super().__init__("PDF", reason, document_id, is_transient)


class DocxExtractionError(ExtractionError):
    """Raised when DOCX extraction fails."""

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = True,
    ) -> None:
        """
        Initialize DocxExtractionError.

        Args:
            reason: Reason for extraction failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient.
        """
        super().__init__("DOCX", reason, document_id, is_transient)


class PptxExtractionError(ExtractionError):
    """Raised when PPTX extraction fails."""

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = True,
    ) -> None:
        """
        Initialize PptxExtractionError.

        Args:
            reason: Reason for extraction failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient.
        """
        super().__init__("PPTX", reason, document_id, is_transient)


class HtmlExtractionError(ExtractionError):
    """Raised when HTML extraction fails."""

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = True,
    ) -> None:
        """
        Initialize HtmlExtractionError.

        Args:
            reason: Reason for extraction failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient.
        """
        super().__init__("HTML", reason, document_id, is_transient)


class ImageExtractionError(ExtractionError):
    """Raised when image extraction fails."""

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = True,
    ) -> None:
        """
        Initialize ImageExtractionError.

        Args:
            reason: Reason for extraction failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient.
        """
        super().__init__("image", reason, document_id, is_transient)


class AudioExtractionError(ExtractionError):
    """Raised when audio extraction fails (Riva NIM)."""

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
    ) -> None:
        """
        Initialize AudioExtractionError.

        Args:
            reason: Reason for extraction failure.
            document_id: Optional document ID.
        """
        # Audio is always transient (Riva NIM availability)
        super().__init__("audio", reason, document_id, is_transient=True)


class VideoExtractionError(ExtractionError):
    """Raised when video extraction fails."""

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = True,
    ) -> None:
        """
        Initialize VideoExtractionError.

        Args:
            reason: Reason for extraction failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient.
        """
        super().__init__("video", reason, document_id, is_transient)


class TextExtractionError(ExtractionError):
    """Raised when text file extraction fails."""

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = False,
    ) -> None:
        """
        Initialize TextExtractionError.

        Args:
            reason: Reason for extraction failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient.
        """
        # Text extraction errors are usually terminal (encoding issues)
        super().__init__("text", reason, document_id, is_transient)


class NoExtractableContentError(IngestorError):
    """
    Raised when document extraction produces no content chunks.

    Terminal error - file may be empty, corrupt, or unsupported format variant.
    Retrying will not help unless file is replaced.
    """

    def __init__(
        self,
        document_id: int,
        mime_type: str | None = None,
    ) -> None:
        """
        Initialize NoExtractableContentError.

        Args:
            document_id: Document ID that produced no content.
            mime_type: Optional MIME type of the file.
        """
        self.document_id = document_id
        self.mime_type = mime_type
        msg = f"No extractable content from document {document_id}"
        if mime_type:
            msg += f" (type: {mime_type})"
        msg += ". File may be empty, corrupt, or use unsupported format variant."
        super().__init__(msg)


class ChunkingError(IngestorError):
    """
    Raised when tokenizer-based chunking fails.

    Usually transient (tokenizer download) or terminal (invalid content).
    """

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        is_transient: bool = True,
    ) -> None:
        """
        Initialize ChunkingError.

        Args:
            reason: Reason for chunking failure.
            document_id: Optional document ID.
            is_transient: Whether error is transient.
        """
        self.reason = reason
        self.document_id = document_id
        self.is_transient = is_transient
        msg = f"Chunking failed: {reason}"
        if document_id:
            msg = f"Chunking failed for document {document_id}: {reason}"
        super().__init__(msg)


class UnsupportedMimeTypeError(IngestorError):
    """
    Raised when MIME type is not supported.

    Terminal error - file type cannot be processed.
    """

    def __init__(self, mime_type: str) -> None:
        """
        Initialize UnsupportedMimeTypeError.

        Args:
            mime_type: The unsupported MIME type.
        """
        self.mime_type = mime_type
        super().__init__(f"Unsupported MIME type: {mime_type}")


class EmbeddingError(IngestorError):
    """
    Raised when embedding generation fails via gRPC.

    Usually transient - Embedder service may be overloaded.
    """

    def __init__(
        self,
        reason: str,
        document_id: int | None = None,
        chunk_index: int | None = None,
    ) -> None:
        """
        Initialize EmbeddingError.

        Args:
            reason: Reason for embedding failure.
            document_id: Optional document ID.
            chunk_index: Optional chunk index that failed.
        """
        self.reason = reason
        self.document_id = document_id
        self.chunk_index = chunk_index
        msg = f"Embedding failed: {reason}"
        if document_id and chunk_index is not None:
            msg = f"Embedding failed for document {document_id} chunk {chunk_index}: {reason}"
        elif document_id:
            msg = f"Embedding failed for document {document_id}: {reason}"
        super().__init__(msg)


class MinioError(IngestorError):
    """
    Raised when MinIO operations fail.

    Usually transient - network or service issues.
    """

    def __init__(self, operation: str, reason: str) -> None:
        """
        Initialize MinioError.

        Args:
            operation: MinIO operation that failed (download, upload, etc).
            reason: Reason for failure.
        """
        self.operation = operation
        self.reason = reason
        super().__init__(f"MinIO {operation} failed: {reason}")


class DatabaseError(IngestorError):
    """
    Raised when database operations fail.

    Usually transient - connection or lock issues.
    """

    def __init__(self, operation: str, reason: str) -> None:
        """
        Initialize DatabaseError.

        Args:
            operation: Database operation that failed.
            reason: Reason for failure.
        """
        self.operation = operation
        self.reason = reason
        super().__init__(f"Database {operation} failed: {reason}")


class GrpcError(IngestorError):
    """
    Raised when gRPC communication fails.

    Usually transient - network or service issues.
    """

    def __init__(self, service: str, reason: str, code: str | None = None) -> None:
        """
        Initialize GrpcError.

        Args:
            service: gRPC service name (embedder, etc).
            reason: Reason for failure.
            code: Optional gRPC status code.
        """
        self.service = service
        self.reason = reason
        self.code = code
        msg = f"gRPC call to {service} failed: {reason}"
        if code:
            msg = f"gRPC call to {service} failed ({code}): {reason}"
        super().__init__(msg)


class NatsError(IngestorError):
    """
    Raised when NATS operations fail.

    Usually transient - connection issues.
    """

    def __init__(self, operation: str, reason: str) -> None:
        """
        Initialize NatsError.

        Args:
            operation: NATS operation that failed.
            reason: Reason for failure.
        """
        self.operation = operation
        self.reason = reason
        super().__init__(f"NATS {operation} failed: {reason}")
