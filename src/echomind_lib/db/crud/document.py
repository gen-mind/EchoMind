"""
Document CRUD operations.
"""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from echomind_lib.db.crud.base import CRUDBase
from echomind_lib.db.models import Document


class DocumentCRUD(CRUDBase[Document]):
    """
    CRUD operations for Document model.

    Documents do not support soft delete - they are hard deleted
    when their connector is removed.
    """

    def __init__(self):
        """Initialize DocumentCRUD."""
        super().__init__(Document)

    async def get_by_connector(
        self,
        session: AsyncSession,
        connector_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Document]:
        """
        Get documents for a connector.

        Args:
            session: Database session.
            connector_id: Connector ID.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of documents.
        """
        result = await session.execute(
            select(Document)
            .where(Document.connector_id == connector_id)
            .order_by(Document.creation_date.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_source_id(
        self,
        session: AsyncSession,
        connector_id: int,
        source_id: str,
    ) -> Document | None:
        """
        Get document by source ID within a connector.

        Args:
            session: Database session.
            connector_id: Connector ID.
            source_id: External source identifier.

        Returns:
            Document or None.
        """
        result = await session.execute(
            select(Document)
            .where(Document.connector_id == connector_id)
            .where(Document.source_id == source_id)
        )
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        session: AsyncSession,
        status: str,
        *,
        connector_id: int | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Document]:
        """
        Get documents by processing status.

        Args:
            session: Database session.
            status: Status (pending, processing, completed, failed).
            connector_id: Optional filter by connector.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of documents.
        """
        query = select(Document).where(Document.status == status)
        if connector_id is not None:
            query = query.where(Document.connector_id == connector_id)
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

    async def get_pending(
        self,
        session: AsyncSession,
        limit: int = 100,
    ) -> Sequence[Document]:
        """
        Get documents pending processing.

        Args:
            session: Database session.
            limit: Maximum number to return.

        Returns:
            List of pending documents.
        """
        result = await session.execute(
            select(Document)
            .where(Document.status == "pending")
            .order_by(Document.creation_date)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_by_connector(
        self,
        session: AsyncSession,
        connector_id: int,
    ) -> int:
        """
        Count documents for a connector.

        Args:
            session: Database session.
            connector_id: Connector ID.

        Returns:
            Document count.
        """
        result = await session.execute(
            select(func.count(Document.id))
            .where(Document.connector_id == connector_id)
        )
        return result.scalar_one()

    async def update_status(
        self,
        session: AsyncSession,
        document_id: int,
        status: str,
        status_message: str | None = None,
        user_id: int | None = None,
    ) -> Document | None:
        """
        Update document processing status.

        Args:
            session: Database session.
            document_id: Document ID.
            status: New status.
            status_message: Optional status message.
            user_id: User making the change.

        Returns:
            Updated document or None.
        """
        doc = await self.get_by_id(session, document_id)
        if doc:
            doc.status = status
            doc.status_message = status_message
            doc.last_update = datetime.now(timezone.utc)
            if user_id:
                doc.user_id_last_update = user_id
            await session.flush()
            return doc
        return None

    async def update_chunking(
        self,
        session: AsyncSession,
        document_id: int,
        chunk_count: int,
        chunking_session: str,
        signature: str | None = None,
    ) -> Document | None:
        """
        Update document after chunking.

        Args:
            session: Database session.
            document_id: Document ID.
            chunk_count: Number of chunks created.
            chunking_session: UUID of chunking session.
            signature: Content signature hash.

        Returns:
            Updated document or None.
        """
        doc = await self.get_by_id(session, document_id)
        if doc:
            doc.chunk_count = chunk_count
            doc.chunking_session = chunking_session
            doc.signature = signature
            doc.status = "completed"
            doc.last_update = datetime.now(timezone.utc)
            await session.flush()
            return doc
        return None

    async def delete_by_connector(
        self,
        session: AsyncSession,
        connector_id: int,
    ) -> int:
        """
        Delete all documents for a connector.

        Args:
            session: Database session.
            connector_id: Connector ID.

        Returns:
            Number of documents deleted.
        """
        result = await session.execute(
            select(Document)
            .where(Document.connector_id == connector_id)
        )
        docs = result.scalars().all()
        count = len(docs)
        for doc in docs:
            await session.delete(doc)
        await session.flush()
        return count


document_crud = DocumentCRUD()
