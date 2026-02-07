"""Embedding model configuration endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.dependencies import AdminUser, DbSession
from echomind_lib.db.models import Document as DocumentORM
from echomind_lib.db.models import EmbeddingModel as EmbeddingModelORM
from echomind_lib.models.public import (
    CreateEmbeddingModelRequest,
    EmbeddingModel,
    ListEmbeddingModelsResponse,
)

router = APIRouter()


class ActivateEmbeddingModelResponse(BaseModel):
    """Response model for activating an embedding model."""
    success: bool
    message: str
    requires_reindex: bool
    documents_affected: int


@router.get("", response_model=ListEmbeddingModelsResponse)
async def list_embedding_models(
    user: AdminUser,
    db: DbSession,
) -> ListEmbeddingModelsResponse:
    """
    List all embedding model configurations.

    Args:
        user: The authenticated user.
        db: Database session.

    Returns:
        ListEmbeddingModelsResponse: List of embedding models.
    """
    result = await db.execute(
        select(EmbeddingModelORM)
        .where(EmbeddingModelORM.deleted_date.is_(None))
        .order_by(EmbeddingModelORM.model_name)
    )
    db_models = result.scalars().all()
    
    models = [EmbeddingModel.model_validate(m, from_attributes=True) for m in db_models]
    
    return ListEmbeddingModelsResponse(models=models)


@router.get("/active", response_model=EmbeddingModel)
async def get_active_embedding_model(
    user: AdminUser,
    db: DbSession,
) -> EmbeddingModel:
    """
    Get the currently active embedding model.

    Args:
        user: The authenticated user.
        db: Database session.

    Returns:
        EmbeddingModel: The active embedding model.

    Raises:
        HTTPException: 404 if no active model configured.
    """
    result = await db.execute(
        select(EmbeddingModelORM)
        .where(EmbeddingModelORM.is_active.is_(True))
        .where(EmbeddingModelORM.deleted_date.is_(None))
    )
    db_model = result.scalar_one_or_none()
    
    if not db_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active embedding model configured",
        )
    
    return EmbeddingModel.model_validate(db_model, from_attributes=True)


@router.post("", response_model=EmbeddingModel, status_code=status.HTTP_201_CREATED)
async def create_embedding_model(
    data: CreateEmbeddingModelRequest,
    user: AdminUser,
    db: DbSession,
) -> EmbeddingModel:
    """
    Create a new embedding model configuration.

    Args:
        data: The embedding model creation data.
        user: The authenticated user.
        db: Database session.

    Returns:
        EmbeddingModel: The created embedding model.
    """
    model = EmbeddingModelORM(
        model_id=data.model_id,
        model_name=data.model_name,
        model_dimension=data.model_dimension,
        endpoint=data.endpoint,
        is_active=False,
        user_id_last_update=user.id,
    )
    
    db.add(model)
    await db.flush()
    await db.refresh(model)
    
    return EmbeddingModel.model_validate(model, from_attributes=True)


@router.put("/{model_id}/activate", response_model=ActivateEmbeddingModelResponse)
async def activate_embedding_model(
    model_id: int,
    user: AdminUser,
    db: DbSession,
) -> ActivateEmbeddingModelResponse:
    """
    Set an embedding model as active.

    Warning: This may require re-indexing all documents if the model dimension changes.

    Args:
        model_id: The ID of the embedding model to activate.
        user: The authenticated user.
        db: Database session.

    Returns:
        ActivateEmbeddingModelResponse: Activation result with reindex info.

    Raises:
        HTTPException: 404 if embedding model not found.
    """
    # Get the model to activate
    result = await db.execute(
        select(EmbeddingModelORM)
        .where(EmbeddingModelORM.id == model_id)
        .where(EmbeddingModelORM.deleted_date.is_(None))
    )
    new_model = result.scalar_one_or_none()
    
    if not new_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Embedding model not found",
        )
    
    # Get current active model
    result = await db.execute(
        select(EmbeddingModelORM)
        .where(EmbeddingModelORM.is_active.is_(True))
        .where(EmbeddingModelORM.deleted_date.is_(None))
    )
    current_model = result.scalar_one_or_none()
    
    # Check if reindex is needed
    requires_reindex = False
    if current_model and current_model.id != new_model.id:
        requires_reindex = current_model.model_dimension != new_model.model_dimension
    
    # Count affected documents
    doc_count_result = await db.execute(
        select(DocumentORM.id).where(DocumentORM.status == "completed")
    )
    documents_affected = len(doc_count_result.all()) if requires_reindex else 0
    
    # Deactivate current model
    if current_model and current_model.id != new_model.id:
        current_model.is_active = False
        current_model.user_id_last_update = user.id
    
    # Activate new model
    new_model.is_active = True
    new_model.user_id_last_update = user.id
    
    message = "Embedding model activated"
    if requires_reindex:
        message = f"Embedding model activated. Re-indexing required for {documents_affected} documents."
    
    return ActivateEmbeddingModelResponse(
        success=True,
        message=message,
        requires_reindex=requires_reindex,
        documents_affected=documents_affected,
    )
