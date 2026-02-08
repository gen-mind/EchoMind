"""
Connector Service business logic.

Orchestrates provider sync operations, MinIO uploads, and NATS publishing.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.constants import MinioBuckets
from echomind_lib.db.minio import MinIOClient
from echomind_lib.db.models import Connector, Document
from echomind_lib.db.nats_publisher import JetStreamPublisher

from connector.logic.checkpoint import (
    ConnectorCheckpoint,
    deserialize_checkpoint,
    serialize_checkpoint,
)
from connector.logic.exceptions import (
    DatabaseError,
    MinioUploadError,
    ProviderNotFoundError,
)
from connector.logic.providers.base import (
    BaseProvider,
    DeletedFile,
    DownloadedFile,
    FileMetadata,
    StreamResult,
)
from connector.logic.providers.google_calendar import GoogleCalendarProvider
from connector.logic.providers.google_contacts import GoogleContactsProvider
from connector.logic.providers.google_drive import GoogleDriveProvider
from connector.logic.providers.google_gmail import GmailProvider
from connector.logic.providers.onedrive import OneDriveProvider

logger = logging.getLogger("echomind-connector.service")


# Provider registry
PROVIDERS: dict[str, type[BaseProvider]] = {
    "google_drive": GoogleDriveProvider,
    "gmail": GmailProvider,
    "google_calendar": GoogleCalendarProvider,
    "google_contacts": GoogleContactsProvider,
    "onedrive": OneDriveProvider,
}


class ConnectorService:
    """
    Main connector service that handles sync operations.

    Coordinates between:
    - Database (connector config, document records)
    - Providers (Google Drive, OneDrive)
    - MinIO (file storage)
    - NATS (publishing document.process messages)
    """

    def __init__(
        self,
        db_session: AsyncSession,
        minio_client: MinIOClient,
        nats_publisher: JetStreamPublisher,
        minio_bucket: str = MinioBuckets.DOCUMENTS,
    ):
        """
        Initialize connector service.

        Args:
            db_session: Async database session.
            minio_client: MinIO client for file storage.
            nats_publisher: NATS publisher for messages.
            minio_bucket: MinIO bucket name.
        """
        self._db = db_session
        self._minio = minio_client
        self._nats = nats_publisher
        self._bucket = minio_bucket
        self._providers: dict[str, BaseProvider] = {}

    async def get_provider(self, connector_type: str) -> BaseProvider:
        """
        Get or create a provider instance.

        Args:
            connector_type: Type of connector (e.g., 'google_drive').

        Returns:
            BaseProvider instance.

        Raises:
            ProviderNotFoundError: If provider type not supported.
        """
        if connector_type not in self._providers:
            if connector_type not in PROVIDERS:
                raise ProviderNotFoundError(connector_type)
            self._providers[connector_type] = PROVIDERS[connector_type]()
        return self._providers[connector_type]

    async def sync_connector(
        self,
        connector_id: int,
        chunking_session: str = "",
    ) -> int:
        """
        Sync a connector by ID.

        Main entry point for sync operations triggered by NATS messages.

        Args:
            connector_id: ID of the connector to sync.
            chunking_session: UUID for this sync session from orchestrator.

        Returns:
            Number of documents processed.

        Raises:
            ConnectorError: If sync fails.
        """
        logger.info(
            f"🔄 Starting sync for connector {connector_id} (session: {chunking_session or 'none'})"
        )

        # Load connector from database
        connector = await self._get_connector(connector_id)
        if not connector:
            raise DatabaseError(
                "get_connector",
                f"Connector {connector_id} not found",
            )

        # Update status to syncing
        await self._update_connector_status(connector, "syncing")

        try:
            # Get provider
            provider = await self.get_provider(connector.type)

            # Load checkpoint from state
            checkpoint = self._load_checkpoint(connector.state, connector.type)

            # Authenticate
            await provider.authenticate(connector.config)

            # Sync and process documents using streaming
            docs_processed = 0

            # Detect changes via provider's change detection
            async for change in provider.get_changes(connector.config, checkpoint):
                if change.action == "delete":
                    await self._process_deleted_file(
                        connector, DeletedFile(source_id=change.source_id)
                    )
                elif change.file:
                    # Check for duplicates in checkpoint
                    if hasattr(checkpoint, "mark_file_retrieved"):
                        if not checkpoint.mark_file_retrieved(change.source_id):
                            continue
                    elif hasattr(checkpoint, "mark_item_retrieved"):
                        if not checkpoint.mark_item_retrieved(change.source_id):
                            continue

                    # Stream file directly to storage
                    try:
                        await self._process_file_stream(
                            connector, provider, change.file, chunking_session
                        )
                        docs_processed += 1
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed to stream file {change.source_id}: {e}"
                        )
                        checkpoint.error_count += 1

                # Save checkpoint periodically
                if docs_processed % 10 == 0:
                    await self._save_checkpoint(connector, checkpoint)

            checkpoint.has_more = False

            # Save final checkpoint
            await self._save_checkpoint(connector, checkpoint)

            # Update connector stats
            connector.docs_analyzed = (connector.docs_analyzed or 0) + docs_processed
            connector.last_sync_at = datetime.now(timezone.utc)
            await self._db.commit()

            logger.info(
                f"✅ Sync completed for connector {connector_id}: {docs_processed} documents processed"
            )
            return docs_processed

        except Exception as e:
            logger.exception(f"❌ Sync failed for connector {connector_id}")
            await self._update_connector_status(
                connector, "error", str(e)
            )
            raise

    async def _get_connector(self, connector_id: int) -> Connector | None:
        """
        Load connector from database.

        Args:
            connector_id: Connector ID.

        Returns:
            Connector model or None if not found.
        """
        result = await self._db.execute(
            select(Connector).where(Connector.id == connector_id)
        )
        return result.scalar_one_or_none()

    async def _update_connector_status(
        self,
        connector: Connector,
        status: str,
        message: str | None = None,
    ) -> None:
        """
        Update connector status in database.

        Args:
            connector: Connector model.
            status: New status.
            message: Optional status message.
        """
        connector.status = status
        connector.status_message = message
        connector.last_update = datetime.now(timezone.utc)
        await self._db.commit()

    def _load_checkpoint(
        self,
        state: dict[str, Any],
        connector_type: str,
    ) -> ConnectorCheckpoint:
        """
        Load checkpoint from connector state.

        Args:
            state: Connector state JSON.
            connector_type: Type of connector.

        Returns:
            Checkpoint instance.
        """
        if "checkpoint" in state:
            try:
                return deserialize_checkpoint(state["checkpoint"])
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to deserialize checkpoint, creating new: {e}"
                )

        # Create fresh checkpoint based on provider
        provider_class = PROVIDERS.get(connector_type)
        if provider_class:
            return provider_class().create_checkpoint()
        return ConnectorCheckpoint()

    async def _save_checkpoint(
        self,
        connector: Connector,
        checkpoint: ConnectorCheckpoint,
    ) -> None:
        """
        Save checkpoint to connector state.

        Args:
            connector: Connector model.
            checkpoint: Checkpoint to save.
        """
        if connector.state is None:
            connector.state = {}
        connector.state["checkpoint"] = serialize_checkpoint(checkpoint)
        await self._db.commit()

    async def _process_downloaded_file(
        self,
        connector: Connector,
        file: DownloadedFile,
        chunking_session: str = "",
    ) -> None:
        """
        Process a downloaded file.

        1. Upload to MinIO
        2. Create/update document record
        3. Publish to NATS

        Args:
            connector: Connector model.
            file: Downloaded file.
            chunking_session: UUID for this sync session from orchestrator.
        """
        # Generate MinIO path
        object_name = self._generate_minio_path(connector, file)

        # Upload to MinIO
        try:
            await self._minio.upload_file(
                bucket_name=self._bucket,
                object_name=object_name,
                data=file.content,
                content_type=file.mime_type,
            )
            logger.info(f"📦 Uploaded {file.name} to MinIO: {object_name}")
        except Exception as e:
            raise MinioUploadError(object_name, str(e)) from e

        # Create or update document
        doc = await self._upsert_document(connector, file, object_name)

        # Publish to NATS
        await self._publish_document_process(doc, connector, chunking_session)

    async def _process_file_stream(
        self,
        connector: Connector,
        provider: BaseProvider,
        file: FileMetadata,
        chunking_session: str = "",
    ) -> None:
        """
        Stream a file from provider directly to MinIO storage.

        Memory-efficient method that streams file content without loading
        the entire file into memory.

        Args:
            connector: Connector model.
            provider: Provider instance.
            file: File metadata from change detection.
            chunking_session: UUID for this sync session.
        """
        # Generate MinIO path
        object_name = self._generate_minio_path_from_metadata(connector, file)

        # Stream directly to storage
        try:
            result = await provider.stream_to_storage(
                file=file,
                config=connector.config,
                minio_client=self._minio,
                bucket=self._bucket,
                object_key=object_name,
            )
            logger.info(
                f"📦 Streamed {file.name} to MinIO: {object_name} ({result.size} bytes)"
            )
        except Exception as e:
            raise MinioUploadError(object_name, str(e)) from e

        # Fetch permissions
        external_access = await provider.get_file_permissions(file, connector.config)

        # Create or update document record
        doc = await self._upsert_document_from_stream(
            connector, file, object_name, result, external_access
        )

        # Publish to NATS
        await self._publish_document_process(doc, connector, chunking_session)

    def _generate_minio_path_from_metadata(
        self,
        connector: Connector,
        file: FileMetadata,
    ) -> str:
        """
        Generate MinIO object path for a file from metadata.

        Format: {connector_id}/{source_id}/{uuid}_{filename}

        Args:
            connector: Connector model.
            file: File metadata.

        Returns:
            MinIO object path.
        """
        safe_name = file.name.replace("/", "_").replace("\\", "_")
        unique_id = uuid.uuid4().hex[:8]
        return f"{connector.id}/{file.source_id}/{unique_id}_{safe_name}"

    async def _upsert_document_from_stream(
        self,
        connector: Connector,
        file: FileMetadata,
        minio_url: str,
        stream_result: StreamResult,
        external_access: Any,
    ) -> Document:
        """
        Create or update document record from stream result.

        Args:
            connector: Connector model.
            file: File metadata.
            minio_url: MinIO object path.
            stream_result: Result from streaming upload.
            external_access: File permissions.

        Returns:
            Document model.
        """
        # Check for existing document
        result = await self._db.execute(
            select(Document).where(
                Document.connector_id == connector.id,
                Document.source_id == file.source_id,
            )
        )
        doc = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if doc:
            # Update existing
            doc.url = minio_url
            doc.original_url = file.web_url
            doc.title = file.name
            doc.content_type = file.mime_type
            doc.signature = stream_result.content_hash or file.content_hash
            doc.status = "pending"
            doc.last_update = now
        else:
            # Create new
            doc = Document(
                connector_id=connector.id,
                source_id=file.source_id,
                url=minio_url,
                original_url=file.web_url,
                title=file.name,
                content_type=file.mime_type,
                signature=stream_result.content_hash or file.content_hash,
                status="pending",
                creation_date=now,
            )
            self._db.add(doc)

        await self._db.commit()
        await self._db.refresh(doc)

        logger.info(
            f"✅ {'Updated' if doc else 'Created'} document {doc.id} for source {file.source_id}"
        )
        return doc

    async def _process_deleted_file(
        self,
        connector: Connector,
        file: DeletedFile,
    ) -> None:
        """
        Process a deleted file.

        Marks document as deleted in database.

        Args:
            connector: Connector model.
            file: Deleted file info.
        """
        result = await self._db.execute(
            select(Document).where(
                Document.connector_id == connector.id,
                Document.source_id == file.source_id,
            )
        )
        doc = result.scalar_one_or_none()

        if doc:
            doc.status = "deleted"
            doc.last_update = datetime.now(timezone.utc)
            await self._db.commit()
            logger.info(
                f"🔄 Marked document {doc.id} as deleted (source: {file.source_id})"
            )

    def _generate_minio_path(
        self,
        connector: Connector,
        file: DownloadedFile,
    ) -> str:
        """
        Generate MinIO object path for a file.

        Format: {connector_id}/{source_id}/{uuid}_{filename}

        Args:
            connector: Connector model.
            file: Downloaded file.

        Returns:
            MinIO object path.
        """
        safe_name = file.name.replace("/", "_").replace("\\", "_")
        unique_id = uuid.uuid4().hex[:8]
        return f"{connector.id}/{file.source_id}/{unique_id}_{safe_name}"

    async def _upsert_document(
        self,
        connector: Connector,
        file: DownloadedFile,
        minio_url: str,
    ) -> Document:
        """
        Create or update document record.

        Args:
            connector: Connector model.
            file: Downloaded file.
            minio_url: MinIO object path.

        Returns:
            Document model.
        """
        # Check for existing document
        result = await self._db.execute(
            select(Document).where(
                Document.connector_id == connector.id,
                Document.source_id == file.source_id,
            )
        )
        doc = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if doc:
            # Update existing
            doc.url = minio_url
            doc.original_url = file.original_url
            doc.title = file.name
            doc.content_type = file.mime_type
            doc.signature = file.content_hash
            doc.status = "pending"
            doc.last_update = now
        else:
            # Create new
            doc = Document(
                connector_id=connector.id,
                source_id=file.source_id,
                url=minio_url,
                original_url=file.original_url,
                title=file.name,
                content_type=file.mime_type,
                signature=file.content_hash,
                status="pending",
                creation_date=now,
            )
            self._db.add(doc)

        await self._db.commit()
        await self._db.refresh(doc)

        logger.info(
            f"✅ {'Updated' if doc else 'Created'} document {doc.id} for source {file.source_id}"
        )
        return doc

    async def _publish_document_process(
        self,
        doc: Document,
        connector: Connector,
        chunking_session: str = "",
    ) -> None:
        """
        Publish document.process message to NATS.

        Args:
            doc: Document model to process.
            connector: Connector model with user and scope info.
            chunking_session: UUID for this sync session from orchestrator.
        """
        # Generated protobuf lacks type stubs
        from echomind_lib.models.internal.orchestrator_pb2 import (  # type: ignore[import-untyped]
            DocumentProcessRequest,
        )
        from echomind_lib.models.public.connector_pb2 import (  # type: ignore[import-untyped]
            ConnectorScope,
        )

        # Map scope string to enum
        scope_map = {
            "user": ConnectorScope.CONNECTOR_SCOPE_USER,
            "group": ConnectorScope.CONNECTOR_SCOPE_GROUP,
            "org": ConnectorScope.CONNECTOR_SCOPE_ORG,
        }
        scope_enum = scope_map.get(connector.scope, ConnectorScope.CONNECTOR_SCOPE_USER)

        message = DocumentProcessRequest(
            document_id=doc.id,
            connector_id=doc.connector_id,
            user_id=connector.user_id,
            minio_path=doc.url or "",  # doc.url stores the MinIO object path
            chunking_session=chunking_session,
            scope=scope_enum,
            scope_id=connector.scope_id or "",
        )

        # Set team_id for team-scoped connectors
        if connector.team_id is not None:
            message.team_id = connector.team_id

        await self._nats.publish(
            subject="document.process",
            payload=message.SerializeToString(),
        )

        logger.info(f"📤 Published document.process for document {doc.id}")

    async def close(self) -> None:
        """
        Clean up resources.

        Closes all provider connections.
        """
        for provider in self._providers.values():
            await provider.close()
        self._providers.clear()
