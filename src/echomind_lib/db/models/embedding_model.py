"""EmbeddingModel ORM model."""

from echomind_lib.db.models.base import (
    TIMESTAMP,
    Base,
    Boolean,
    ForeignKey,
    Integer,
    Mapped,
    SmallInteger,
    String,
    datetime,
    mapped_column,
)


class EmbeddingModel(Base):
    """Embedding model configurations (cluster-wide)."""
    
    __tablename__ = "embedding_models"
    
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creation_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    last_update: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    user_id_last_update: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    deleted_date: Mapped[datetime | None] = mapped_column(TIMESTAMP)
