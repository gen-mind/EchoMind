"""
MinIO/S3 object storage client.

Provides async operations for file storage and retrieval.
"""

import io
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, AsyncIterator, BinaryIO

from miniopy_async import Minio


@dataclass
class StreamUploadResult:
    """Result of a streaming upload operation."""

    etag: str
    size: int
    storage_path: str


class MinIOClient:
    """
    Async MinIO client for object storage operations.
    
    Usage:
        minio = MinIOClient(endpoint="localhost:9000", access_key="...", secret_key="...")
        await minio.init()
        
        await minio.upload_file("bucket", "path/file.pdf", file_data)
        data = await minio.download_file("bucket", "path/file.pdf")
        
        # No close needed - uses HTTP
    """
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        region: str | None = None,
        public_endpoint: str | None = None,
    ):
        """
        Initialize MinIO client.

        Args:
            endpoint: MinIO server endpoint (host:port).
            access_key: Access key ID.
            secret_key: Secret access key.
            secure: Use HTTPS.
            region: Optional region.
            public_endpoint: Public endpoint for presigned URLs (e.g.,
                https://s3.demo.echomind.ch). If set, presigned URLs are
                signed against this host so browsers can use them directly.
        """
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )
        self._presign_client: Minio | None = None
        if public_endpoint:
            if public_endpoint.startswith("https://"):
                presign_secure = True
                presign_host = public_endpoint[len("https://"):]
            elif public_endpoint.startswith("http://"):
                presign_secure = False
                presign_host = public_endpoint[len("http://"):]
            else:
                presign_secure = True
                presign_host = public_endpoint
            self._presign_client = Minio(
                endpoint=presign_host,
                access_key=access_key,
                secret_key=secret_key,
                secure=presign_secure,
                region=region,
            )
    
    async def init(self) -> None:
        """Verify connectivity by listing buckets."""
        await self._client.list_buckets()
    
    async def bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists."""
        return await self._client.bucket_exists(bucket_name)
    
    async def create_bucket(self, bucket_name: str) -> None:
        """Create a bucket if it doesn't exist."""
        if not await self.bucket_exists(bucket_name):
            await self._client.make_bucket(bucket_name)
    
    async def delete_bucket(self, bucket_name: str) -> None:
        """Delete an empty bucket."""
        await self._client.remove_bucket(bucket_name)
    
    async def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Upload a file to MinIO.
        
        Args:
            bucket_name: Target bucket
            object_name: Object path/name
            data: File content as bytes or file-like object
            content_type: MIME type
            metadata: Optional metadata dict
        
        Returns:
            Object ETag
        """
        if isinstance(data, bytes):
            data = io.BytesIO(data)
            length = len(data.getvalue())
        else:
            data.seek(0, 2)
            length = data.tell()
            data.seek(0)
        
        result = await self._client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=data,
            length=length,
            content_type=content_type,
            metadata=metadata,
        )
        return result.etag

    async def stream_upload(
        self,
        bucket_name: str,
        object_name: str,
        data_stream: AsyncIterator[bytes],
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StreamUploadResult:
        """
        Upload a file from an async stream to MinIO.

        This method collects the stream into memory before uploading.
        For true streaming with unknown size, miniopy-async requires the
        length parameter. Future optimization: use multipart upload for
        very large files.

        Args:
            bucket_name: Target bucket.
            object_name: Object path/name.
            data_stream: Async iterator yielding bytes chunks.
            content_type: MIME type.
            metadata: Optional metadata dict.

        Returns:
            StreamUploadResult with etag, size, and storage path.
        """
        # Collect stream into buffer
        # Note: For files > 5GB, should use multipart upload
        chunks: list[bytes] = []
        async for chunk in data_stream:
            chunks.append(chunk)

        content = b"".join(chunks)
        length = len(content)

        result = await self._client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=io.BytesIO(content),
            length=length,
            content_type=content_type,
            metadata=metadata,
        )

        return StreamUploadResult(
            etag=result.etag,
            size=length,
            storage_path=f"minio:{bucket_name}:{object_name}",
        )

    async def presigned_put_url(
        self,
        bucket_name: str,
        object_name: str,
        expires: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for uploading (PUT).

        Uses the public endpoint client if configured, so the signature
        matches the host the browser will send the request to.

        Args:
            bucket_name: Bucket name.
            object_name: Object path.
            expires: URL validity in seconds.

        Returns:
            Presigned PUT URL.
        """
        client = self._presign_client or self._client
        return await client.presigned_put_object(
            bucket_name,
            object_name,
            expires=timedelta(seconds=expires),
        )

    async def download_file(self, bucket_name: str, object_name: str) -> bytes:
        """
        Download a file from MinIO.
        
        Args:
            bucket_name: Source bucket
            object_name: Object path/name
        
        Returns:
            File content as bytes
        """
        response = await self._client.get_object(bucket_name, object_name)
        try:
            return await response.read()
        finally:
            response.close()
            await response.release()
    
    async def delete_file(self, bucket_name: str, object_name: str) -> None:
        """Delete a file from MinIO."""
        await self._client.remove_object(bucket_name, object_name)
    
    async def file_exists(self, bucket_name: str, object_name: str) -> bool:
        """Check if a file exists."""
        try:
            await self._client.stat_object(bucket_name, object_name)
            return True
        except Exception:
            return False
    
    async def get_file_info(self, bucket_name: str, object_name: str) -> dict[str, Any]:
        """Get file metadata."""
        stat = await self._client.stat_object(bucket_name, object_name)
        return {
            "size": stat.size,
            "etag": stat.etag,
            "content_type": stat.content_type,
            "last_modified": stat.last_modified,
            "metadata": stat.metadata,
        }
    
    async def list_objects(
        self,
        bucket_name: str,
        prefix: str = "",
        recursive: bool = False,
    ) -> list[dict[str, Any]]:
        """
        List objects in a bucket.
        
        Args:
            bucket_name: Bucket to list
            prefix: Filter by prefix
            recursive: Include nested objects
        
        Returns:
            List of object info dicts
        """
        objects = []
        async for obj in self._client.list_objects(
            bucket_name, prefix=prefix, recursive=recursive
        ):
            objects.append({
                "name": obj.object_name,
                "size": obj.size,
                "etag": obj.etag,
                "last_modified": obj.last_modified,
                "is_dir": obj.is_dir,
            })
        return objects
    
    async def get_presigned_url(
        self,
        bucket_name: str,
        object_name: str,
        expires: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for temporary download access.

        Uses the public endpoint client if configured, so the signature
        matches the host the browser will send the request to.

        Args:
            bucket_name: Bucket name.
            object_name: Object path.
            expires: URL validity in seconds.

        Returns:
            Presigned URL.
        """
        client = self._presign_client or self._client
        return await client.presigned_get_object(
            bucket_name, object_name, expires=expires
        )


_minio_client: MinIOClient | None = None


def get_minio() -> MinIOClient:
    """Get the global MinIO client instance."""
    if _minio_client is None:
        raise RuntimeError("MinIO client not initialized. Call init_minio() first.")
    return _minio_client


async def init_minio(
    endpoint: str,
    access_key: str,
    secret_key: str,
    secure: bool = False,
    ensure_buckets: list[str] | None = None,
    public_endpoint: str | None = None,
) -> MinIOClient:
    """
    Initialize the global MinIO client.

    Args:
        endpoint: MinIO server endpoint (host:port).
        access_key: Access key ID.
        secret_key: Secret access key.
        secure: Use HTTPS.
        ensure_buckets: Optional list of bucket names to create if they don't exist.
        public_endpoint: Public endpoint for browser-facing presigned URLs.

    Returns:
        Initialized MinIOClient instance.
    """
    global _minio_client
    _minio_client = MinIOClient(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
        public_endpoint=public_endpoint,
    )
    await _minio_client.init()

    if ensure_buckets:
        for bucket_name in ensure_buckets:
            await _minio_client.create_bucket(bucket_name)

    return _minio_client


def close_minio() -> None:
    """Close the global MinIO client (no-op, uses HTTP)."""
    global _minio_client
    _minio_client = None
