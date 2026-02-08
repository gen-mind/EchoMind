"""
MinIO/S3 helper utilities for common file operations.

Provides high-level utilities for document storage and retrieval.
"""

import hashlib
import mimetypes
from pathlib import Path
from typing import Any, AsyncIterator

from echomind_lib.constants import MinioBuckets
from echomind_lib.db.minio import get_minio, MinIOClient, StreamUploadResult


class MinIOHelper:
    """
    High-level helper for MinIO document operations.
    
    Usage:
        helper = MinIOHelper(bucket="documents")
        await helper.init()
        
        # Upload a document
        path = await helper.upload_document(connector_id=1, doc_id=123, content=data)
        
        # Download
        content = await helper.download_document(path)
    """
    
    def __init__(
        self,
        bucket: str = MinioBuckets.DOCUMENTS,
        client: MinIOClient | None = None,
    ):
        """
        Initialize MinIO helper.
        
        Args:
            bucket: Default bucket name
            client: Optional MinIO client (uses global if not provided)
        """
        self._bucket = bucket
        self._client = client
    
    @property
    def client(self) -> MinIOClient:
        """Get the MinIO client."""
        if self._client:
            return self._client
        return get_minio()
    
    async def init(self) -> None:
        """Ensure bucket exists."""
        await self.client.create_bucket(self._bucket)
    
    def _get_document_path(
        self,
        connector_id: int,
        document_id: int,
        filename: str | None = None,
    ) -> str:
        """
        Generate storage path for a document.
        
        Path format: connectors/{connector_id}/documents/{document_id}/{filename}
        """
        base = f"connectors/{connector_id}/documents/{document_id}"
        if filename:
            return f"{base}/{filename}"
        return base
    
    def _get_chunk_path(
        self,
        connector_id: int,
        document_id: int,
        chunk_id: str,
    ) -> str:
        """Generate storage path for a document chunk."""
        return f"connectors/{connector_id}/documents/{document_id}/chunks/{chunk_id}.txt"
    
    async def upload_document(
        self,
        connector_id: int,
        document_id: int,
        content: bytes,
        filename: str = "content",
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Upload a document to MinIO.
        
        Args:
            connector_id: Connector ID
            document_id: Document ID
            content: File content
            filename: Original filename
            content_type: MIME type (auto-detected if not provided)
            metadata: Optional metadata
        
        Returns:
            Storage path (minio:{bucket}:{path})
        """
        if content_type is None:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        
        path = self._get_document_path(connector_id, document_id, filename)
        
        await self.client.upload_file(
            bucket_name=self._bucket,
            object_name=path,
            data=content,
            content_type=content_type,
            metadata=metadata,
        )
        
        return f"minio:{self._bucket}:{path}"

    async def stream_upload_document(
        self,
        connector_id: int,
        document_id: int,
        data_stream: AsyncIterator[bytes],
        filename: str = "content",
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StreamUploadResult:
        """
        Upload a document from an async stream to MinIO.

        Memory-efficient upload for large files using streaming.

        Args:
            connector_id: Connector ID.
            document_id: Document ID.
            data_stream: Async iterator yielding bytes chunks.
            filename: Original filename.
            content_type: MIME type (auto-detected if not provided).
            metadata: Optional metadata.

        Returns:
            StreamUploadResult with etag, size, and storage path.
        """
        if content_type is None:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        path = self._get_document_path(connector_id, document_id, filename)

        result = await self.client.stream_upload(
            bucket_name=self._bucket,
            object_name=path,
            data_stream=data_stream,
            content_type=content_type,
            metadata=metadata,
        )

        # Override storage_path with correct format
        result.storage_path = f"minio:{self._bucket}:{path}"

        return result

    async def download_document(self, storage_path: str) -> bytes:
        """
        Download a document from MinIO.
        
        Args:
            storage_path: Path in format "minio:{bucket}:{path}"
        
        Returns:
            File content as bytes
        """
        bucket, path = self._parse_storage_path(storage_path)
        return await self.client.download_file(bucket, path)
    
    async def delete_document(self, storage_path: str) -> None:
        """Delete a document from MinIO."""
        bucket, path = self._parse_storage_path(storage_path)
        await self.client.delete_file(bucket, path)
    
    async def document_exists(self, storage_path: str) -> bool:
        """Check if a document exists."""
        bucket, path = self._parse_storage_path(storage_path)
        return await self.client.file_exists(bucket, path)
    
    async def get_document_info(self, storage_path: str) -> dict[str, Any]:
        """Get document metadata."""
        bucket, path = self._parse_storage_path(storage_path)
        return await self.client.get_file_info(bucket, path)
    
    async def upload_chunk(
        self,
        connector_id: int,
        document_id: int,
        chunk_id: str,
        content: str,
    ) -> str:
        """
        Upload a text chunk to MinIO.
        
        Args:
            connector_id: Connector ID
            document_id: Document ID
            chunk_id: Unique chunk ID
            content: Chunk text content
        
        Returns:
            Storage path
        """
        path = self._get_chunk_path(connector_id, document_id, chunk_id)
        
        await self.client.upload_file(
            bucket_name=self._bucket,
            object_name=path,
            data=content.encode("utf-8"),
            content_type="text/plain",
        )
        
        return f"minio:{self._bucket}:{path}"
    
    async def download_chunk(self, storage_path: str) -> str:
        """Download a text chunk from MinIO."""
        content = await self.download_document(storage_path)
        return content.decode("utf-8")
    
    async def list_document_files(
        self,
        connector_id: int,
        document_id: int,
    ) -> list[dict[str, Any]]:
        """List all files for a document."""
        prefix = self._get_document_path(connector_id, document_id)
        return await self.client.list_objects(
            self._bucket,
            prefix=prefix,
            recursive=True,
        )
    
    async def delete_document_files(
        self,
        connector_id: int,
        document_id: int,
    ) -> int:
        """
        Delete all files for a document.
        
        Returns:
            Number of files deleted
        """
        files = await self.list_document_files(connector_id, document_id)
        count = 0
        
        for f in files:
            if not f["is_dir"]:
                await self.client.delete_file(self._bucket, f["name"])
                count += 1
        
        return count
    
    def _parse_storage_path(self, storage_path: str) -> tuple[str, str]:
        """
        Parse a storage path into bucket and object path.
        
        Args:
            storage_path: Path in format "minio:{bucket}:{path}"
        
        Returns:
            Tuple of (bucket, path)
        """
        if not storage_path.startswith("minio:"):
            raise ValueError(f"Invalid storage path: {storage_path}")
        
        parts = storage_path.split(":", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid storage path format: {storage_path}")
        
        return parts[1], parts[2]
    
    @staticmethod
    def compute_signature(content: bytes) -> str:
        """
        Compute a signature hash for content change detection.
        
        Args:
            content: File content
        
        Returns:
            SHA-256 hash string
        """
        return hashlib.sha256(content).hexdigest()


_minio_helper: MinIOHelper | None = None


def get_minio_helper() -> MinIOHelper:
    """Get the global MinIO helper instance."""
    if _minio_helper is None:
        raise RuntimeError("MinIO helper not initialized. Call init_minio_helper() first.")
    return _minio_helper


async def init_minio_helper(bucket: str = MinioBuckets.DOCUMENTS) -> MinIOHelper:
    """Initialize the global MinIO helper."""
    global _minio_helper
    _minio_helper = MinIOHelper(bucket=bucket)
    await _minio_helper.init()
    return _minio_helper
