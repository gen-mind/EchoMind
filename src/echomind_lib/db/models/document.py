"""Document ORM model."""

from typing import TYPE_CHECKING

from echomind_lib.db.models.base import (
    TIMESTAMP,
    Base,
    BigInteger,
    ForeignKey,
    Integer,
    Mapped,
    SmallInteger,
    String,
    Text,
    datetime,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    from echomind_lib.db.models.chat_message import ChatMessageDocument
    from echomind_lib.db.models.connector import Connector


class Document(Base):
    """Documents ingested from connectors."""
    
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("documents.id"))
    connector_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("connectors.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    original_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(100))
    signature: Mapped[str | None] = mapped_column(Text)
    chunking_session: Mapped[str | None] = mapped_column(Text)  # UUID stored as text
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    status_message: Mapped[str | None] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    
    connector: Mapped["Connector"] = relationship(back_populates="documents")
    parent: Mapped["Document | None"] = relationship(remote_side=[id])
    message_documents: Mapped[list["ChatMessageDocument"]] = relationship(back_populates="document")
