"""
Document business logic service.

Handles document CRUD operations with RBAC enforcement inherited from connectors.
"""

import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.config import get_settings
from api.logic.exceptions import ForbiddenError, NotFoundError, ServiceUnavailableError
from api.logic.permissions import (
    SCOPE_GROUP,
    SCOPE_ORG,
    SCOPE_TEAM,
    PermissionChecker,
)
from echomind_lib.db.minio import MinIOClient
from echomind_lib.db.models import Connector as ConnectorORM
from echomind_lib.db.models import Document as DocumentORM
from echomind_lib.db.qdrant import QdrantDB

if TYPE_CHECKING:
    from echomind_lib.helpers.auth import TokenUser

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document-related business logic with RBAC enforcement."""

    def __init__(
        self,
        db: AsyncSession,
        qdrant: QdrantDB | None = None,
        minio: MinIOClient | None = None,
    ):
        """
        Initialize document service.

        Args:
            db: Database session.
            qdrant: Qdrant client for vector operations (required for full deletion).
            minio: MinIO client for file operations (required for full deletion).
        """
        self.db = db
        self._qdrant = qdrant
        self._minio = minio
        self._settings = get_settings()
        self.permissions = PermissionChecker(db)

    async def get_document(
        self,
        document_id: int,
        user: "TokenUser",
    ) -> DocumentORM:
        """
        Get a document by ID with permission check.

        Documents inherit permissions from their parent connector.

        Args:
            document_id: The document ID.
            user: The authenticated user.

        Returns:
            DocumentORM: The document.

        Raises:
            NotFoundError: If document not found.
            ForbiddenError: If user lacks permission to view.
        """
        result = await self.db.execute(
            select(DocumentORM)
            .options(selectinload(DocumentORM.connector))
            .where(DocumentORM.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError("Document", document_id)

        # Check permission via connector
        access = await self.permissions.can_view_document(user, document.connector)
        if not access:
            logger.warning(
                "🚫 User %d denied access to document %d: %s",
                user.id,
                document_id,
                access.reason,
            )
            raise ForbiddenError(f"Cannot access document: {access.reason}")

        return document

    async def list_documents(
        self,
        user: "TokenUser",
        page: int = 1,
        limit: int = 20,
        connector_id: int | None = None,
        doc_status: str | None = None,
    ) -> list[DocumentORM]:
        """
        List documents accessible to the user.

        Args:
            user: The authenticated user.
            page: Page number (1-indexed).
            limit: Items per page.
            connector_id: Optional filter by specific connector.
            doc_status: Optional filter by document status.

        Returns:
            List of accessible documents.
        """
        # Get accessible connector IDs
        accessible_connector_ids = await self.permissions.get_accessible_connector_ids(
            user
        )

        if not accessible_connector_ids:
            return []

        # If specific connector requested, verify access
        if connector_id:
            if connector_id not in accessible_connector_ids:
                logger.warning(
                    "🚫 User %d requested documents from inaccessible connector %d",
                    user.id,
                    connector_id,
                )
                return []
            accessible_connector_ids = [connector_id]

        # Build query
        query = select(DocumentORM).where(
            DocumentORM.connector_id.in_(accessible_connector_ids)
        )

        if doc_status:
            query = query.where(DocumentORM.status == doc_status)

        query = query.order_by(DocumentORM.creation_date.desc())
        query = query.offset((page - 1) * limit).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_document(
        self,
        document_id: int,
        user: "TokenUser",
    ) -> None:
        """
        Delete a document with full cascade cleanup.

        Performs atomic deletion:
        1. Fail fast if storage services unavailable
        2. Delete vectors from Qdrant (raises on failure)
        3. Delete file from MinIO (raises on failure)
        4. Delete database record (commit transaction)

        Requires edit access to the parent connector.
        All operations must succeed or the entire deletion fails.

        Args:
            document_id: The document ID.
            user: The authenticated user.

        Raises:
            ServiceUnavailableError: If Qdrant or MinIO unavailable.
            NotFoundError: If document not found.
            ForbiddenError: If user lacks permission to delete.
        """
        # Fail fast if required services are unavailable
        if not self._qdrant:
            raise ServiceUnavailableError("Qdrant vector store")
        if not self._minio:
            raise ServiceUnavailableError("MinIO file storage")

        result = await self.db.execute(
            select(DocumentORM)
            .options(selectinload(DocumentORM.connector))
            .where(DocumentORM.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError("Document", document_id)

        # Check edit permission via connector
        access = await self.permissions.can_edit_document(user, document.connector)
        if not access:
            logger.warning(
                "🚫 User %d denied deleting document %d: %s",
                user.id,
                document_id,
                access.reason,
            )
            raise ForbiddenError(f"Cannot delete document: {access.reason}")

        connector = document.connector

        # Delete external resources BEFORE DB transaction commit
        # If these fail, exception propagates and DB transaction auto-rolls back

        # Step 1: Delete vectors from Qdrant
        await self._delete_document_vectors(document_id, connector, user.id)

        # Step 2: Delete file from MinIO
        await self._delete_document_file(document)

        # Step 3: Delete database record and commit
        await self.db.delete(document)
        await self.db.commit()

        logger.info(f"🗑️ Deleted document {document_id} by user {user.id}")

    async def _delete_document_vectors(
        self,
        document_id: int,
        connector: ConnectorORM,
        user_id: int,
    ) -> None:
        """
        Delete all vectors for a document from Qdrant.

        Raises exception on failure to ensure transactional consistency.

        Args:
            document_id: Document ID to filter by.
            connector: Parent connector (for collection name).
            user_id: User ID (for user-scoped collections).

        Raises:
            Exception: If Qdrant deletion fails.
        """
        collection_name = self._get_collection_for_connector(connector, user_id)

        # Qdrant filter format for delete_by_filter
        filter_ = {
            "must": [
                {"key": "document_id", "match": {"value": document_id}}
            ]
        }

        try:
            await self._qdrant.delete_by_filter(
                collection_name=collection_name,
                filter_=filter_,
            )
            logger.info(
                "🗑️ Deleted vectors for document %d from collection %s",
                document_id,
                collection_name,
            )
        except Exception as e:
            logger.error(
                "❌ Failed to delete vectors for document %d from %s: %s",
                document_id,
                collection_name,
                e,
            )
            raise  # Propagate exception to ensure transactional consistency

    async def _delete_document_file(self, document: DocumentORM) -> None:
        """
        Delete document file from MinIO.

        Raises exception on failure to ensure transactional consistency.
        Skips deletion if document has no URL (e.g., web content).

        Args:
            document: Document with url (MinIO object path).

        Raises:
            Exception: If MinIO deletion fails.
        """
        if not document.url:
            logger.debug(
                "📄 Document %d has no file URL, skipping MinIO deletion",
                document.id,
            )
            return

        bucket_name = self._settings.minio_bucket
        object_name = document.url  # url stores the MinIO object path

        try:
            # Check if file exists before attempting deletion
            if await self._minio.file_exists(bucket_name, object_name):
                await self._minio.delete_file(bucket_name, object_name)
                logger.info(
                    "🗑️ Deleted file %s from MinIO bucket %s",
                    object_name,
                    bucket_name,
                )
            else:
                logger.debug(
                    "📄 File %s not found in MinIO, already deleted",
                    object_name,
                )
        except Exception as e:
            logger.error(
                "❌ Failed to delete file %s from MinIO: %s",
                object_name,
                e,
            )
            raise  # Propagate exception to ensure transactional consistency

    async def search_documents(
        self,
        user: "TokenUser",
        query_text: str,
        connector_id: int | None = None,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> list[dict]:
        """
        Search documents using vector similarity.

        Searches across all collections accessible to the user.

        Args:
            user: The authenticated user.
            query_text: The search query.
            connector_id: Optional filter by specific connector.
            limit: Maximum results to return.
            min_score: Minimum relevance score threshold.

        Returns:
            List of search results with scores.
        """
        # Get collections to search
        collections = await self.permissions.get_search_collections(user)

        if not collections:
            return []

        # If specific connector requested, filter to its collection
        if connector_id:
            # Verify access to connector
            accessible_ids = await self.permissions.get_accessible_connector_ids(user)
            if connector_id not in accessible_ids:
                logger.warning(
                    "🚫 User %d search denied for connector %d",
                    user.id,
                    connector_id,
                )
                return []

            # Get connector to determine its collection
            result = await self.db.execute(
                select(ConnectorORM)
                .where(ConnectorORM.id == connector_id)
                .where(ConnectorORM.deleted_date.is_(None))
            )
            connector = result.scalar_one_or_none()

            if connector:
                collections = [self._get_collection_for_connector(connector, user.id)]

        # TODO: Implement actual vector search via Qdrant
        # 1. Embed query_text using active embedding model
        # 2. Search each collection in 'collections' list
        # 3. Merge and rank results by score
        # 4. Filter by min_score
        # 5. Return top 'limit' results

        logger.info(
            "🔍 Search by user %d: '%s' across %d collections",
            user.id,
            query_text[:50],
            len(collections),
        )

        return []

    def _get_collection_for_connector(
        self,
        connector: ConnectorORM,
        user_id: int,
    ) -> str:
        """
        Get the Qdrant collection name for a connector.

        Args:
            connector: The connector ORM object.
            user_id: The user ID (for user-scoped connectors).

        Returns:
            Collection name string.
        """
        scope = connector.scope or "user"

        if scope in (SCOPE_TEAM, SCOPE_GROUP):
            if connector.team_id:
                return f"team_{connector.team_id}"
            # Fallback for legacy data
            return f"user_{connector.user_id}"

        if scope == SCOPE_ORG:
            return "org_default"

        # User scope
        return f"user_{connector.user_id}"

    async def count_documents(
        self,
        user: "TokenUser",
        connector_id: int | None = None,
        doc_status: str | None = None,
    ) -> int:
        """
        Count documents accessible to the user.

        Args:
            user: The authenticated user.
            connector_id: Optional filter by specific connector.
            doc_status: Optional filter by document status.

        Returns:
            Total count of matching documents.
        """
        # Get accessible connector IDs
        accessible_connector_ids = await self.permissions.get_accessible_connector_ids(
            user
        )

        if not accessible_connector_ids:
            return 0

        if connector_id:
            if connector_id not in accessible_connector_ids:
                return 0
            accessible_connector_ids = [connector_id]

        query = select(func.count(DocumentORM.id)).where(
            DocumentORM.connector_id.in_(accessible_connector_ids)
        )

        if doc_status:
            query = query.where(DocumentORM.status == doc_status)

        result = await self.db.execute(query)
        return result.scalar() or 0
