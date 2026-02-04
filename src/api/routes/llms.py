"""LLM configuration endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.dependencies import DbSession, SuperAdminUser
from echomind_lib.db.models import LLM as LLMORM
from echomind_lib.models.public import (
    CreateLLMRequest,
    ListLLMsResponse,
    LLM,
    UpdateLLMRequest,
)

router = APIRouter()


class TestLLMResponse(BaseModel):
    """Response model for LLM connection test."""
    success: bool
    message: str
    latency_ms: int | None = None


@router.get("", response_model=ListLLMsResponse)
async def list_llms(
    user: SuperAdminUser,
    db: DbSession,
    page: int = 1,
    limit: int = 20,
    is_active: bool | None = None,
) -> ListLLMsResponse:
    """
    List all LLM configurations.

    Args:
        user: The authenticated user.
        db: Database session.
        page: Page number for pagination.
        limit: Number of items per page.
        is_active: Optional filter by active status.

    Returns:
        ListLLMsResponse: Paginated list of LLMs.
    """
    query = select(LLMORM).where(LLMORM.deleted_date.is_(None))
    
    if is_active is not None:
        query = query.where(LLMORM.is_active == is_active)
    
    query = query.order_by(LLMORM.name)
    
    # Count total
    count_query = select(LLMORM.id).where(LLMORM.deleted_date.is_(None))
    if is_active is not None:
        count_query = count_query.where(LLMORM.is_active == is_active)
    # Paginate
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    db_llms = result.scalars().all()
    
    llms = [_orm_to_pydantic(llm_obj) for llm_obj in db_llms]
    
    return ListLLMsResponse(llms=llms)


def _provider_to_db_string(provider: "LLMProvider") -> str:
    """
    Convert LLMProvider enum to database string.

    Maps enum to lowercase canonical names for database storage.

    Args:
        provider: The LLMProvider enum value.

    Returns:
        Canonical provider string (openai-compatible, anthropic, anthropic-token).
    """
    from echomind_lib.models.public import LLMProvider

    mapping = {
        LLMProvider.LLM_PROVIDER_OPENAI_COMPATIBLE: "openai-compatible",
        LLMProvider.LLM_PROVIDER_ANTHROPIC: "anthropic",
        LLMProvider.LLM_PROVIDER_ANTHROPIC_TOKEN: "anthropic-token",
    }
    return mapping.get(provider, "openai-compatible")


def _db_string_to_provider(provider_str: str) -> "LLMProvider":
    """
    Convert database string to LLMProvider enum.

    Handles both new canonical names and legacy values.

    Args:
        provider_str: Provider string from database.

    Returns:
        LLMProvider enum value.
    """
    from echomind_lib.models.public import LLMProvider

    normalized = provider_str.lower().strip()

    # Map to enum - handles legacy values
    if normalized in ("openai-compatible", "openai_compatible", "openai", "tgi", "vllm", "ollama",
                      "llm_provider_openai_compatible", "llm_provider_tgi", "llm_provider_vllm",
                      "llm_provider_openai", "llm_provider_ollama"):
        return LLMProvider.LLM_PROVIDER_OPENAI_COMPATIBLE
    elif normalized in ("anthropic", "llm_provider_anthropic"):
        return LLMProvider.LLM_PROVIDER_ANTHROPIC
    elif normalized in ("anthropic-token", "anthropic_token", "llm_provider_anthropic_token"):
        return LLMProvider.LLM_PROVIDER_ANTHROPIC_TOKEN
    else:
        return LLMProvider.LLM_PROVIDER_OPENAI_COMPATIBLE  # Default fallback


def _orm_to_pydantic(db_llm: LLMORM) -> LLM:
    """
    Convert ORM model to Pydantic model with proper provider conversion.

    Args:
        db_llm: Database ORM model.

    Returns:
        Pydantic LLM model.
    """
    return LLM(
        id=db_llm.id,
        name=db_llm.name,
        provider=_db_string_to_provider(db_llm.provider),
        model_id=db_llm.model_id,
        endpoint=db_llm.endpoint,
        has_api_key=db_llm.api_key is not None and len(db_llm.api_key) > 0,
        max_tokens=db_llm.max_tokens,
        temperature=float(db_llm.temperature),
        is_default=db_llm.is_default,
        is_active=db_llm.is_active,
        creation_date=db_llm.creation_date,
        last_update=db_llm.last_update,
    )


@router.post("", response_model=LLM, status_code=status.HTTP_201_CREATED)
async def create_llm(
    data: CreateLLMRequest,
    user: SuperAdminUser,
    db: DbSession,
) -> LLM:
    """
    Create a new LLM configuration.

    Args:
        data: The LLM creation data.
        user: The authenticated user.
        db: Database session.

    Returns:
        LLM: The created LLM configuration.
    """
    llm = LLMORM(
        name=data.name,
        provider=_provider_to_db_string(data.provider),
        model_id=data.model_id,
        endpoint=data.endpoint,
        api_key=data.api_key,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
        is_default=data.is_default,
        is_active=data.is_active,
        user_id_last_update=user.id,
    )

    db.add(llm)
    await db.flush()
    await db.refresh(llm)

    return _orm_to_pydantic(llm)


@router.get("/{llm_id}", response_model=LLM)
async def get_llm(
    llm_id: int,
    user: SuperAdminUser,
    db: DbSession,
) -> LLM:
    """
    Get an LLM configuration by ID.

    Args:
        llm_id: The ID of the LLM to retrieve.
        user: The authenticated user.
        db: Database session.

    Returns:
        LLM: The requested LLM configuration.

    Raises:
        HTTPException: 404 if LLM not found.
    """
    result = await db.execute(
        select(LLMORM)
        .where(LLMORM.id == llm_id)
        .where(LLMORM.deleted_date.is_(None))
    )
    db_llm = result.scalar_one_or_none()
    
    if not db_llm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM not found",
        )
    
    return _orm_to_pydantic(db_llm)


@router.put("/{llm_id}", response_model=LLM)
async def update_llm(
    llm_id: int,
    data: UpdateLLMRequest,
    user: SuperAdminUser,
    db: DbSession,
) -> LLM:
    """
    Update an LLM configuration.

    Args:
        llm_id: The ID of the LLM to update.
        data: The fields to update.
        user: The authenticated user.
        db: Database session.

    Returns:
        LLM: The updated LLM configuration.

    Raises:
        HTTPException: 404 if LLM not found.
    """
    result = await db.execute(
        select(LLMORM)
        .where(LLMORM.id == llm_id)
        .where(LLMORM.deleted_date.is_(None))
    )
    db_llm = result.scalar_one_or_none()
    
    if not db_llm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM not found",
        )
    
    if data.name:
        db_llm.name = data.name
    if data.provider:
        db_llm.provider = _provider_to_db_string(data.provider)
    if data.model_id:
        db_llm.model_id = data.model_id
    if data.endpoint:
        db_llm.endpoint = data.endpoint
    if data.api_key:
        db_llm.api_key = data.api_key
    if data.max_tokens:
        db_llm.max_tokens = data.max_tokens
    if data.temperature:
        db_llm.temperature = data.temperature
    if data.is_default is not None:
        db_llm.is_default = data.is_default
    if data.is_active is not None:
        db_llm.is_active = data.is_active
    
    db_llm.user_id_last_update = user.id
    
    return _orm_to_pydantic(db_llm)


@router.delete("/{llm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm(
    llm_id: int,
    user: SuperAdminUser,
    db: DbSession,
) -> None:
    """
    Delete an LLM configuration (soft delete).

    Args:
        llm_id: The ID of the LLM to delete.
        user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if LLM not found.
    """
    result = await db.execute(
        select(LLMORM)
        .where(LLMORM.id == llm_id)
        .where(LLMORM.deleted_date.is_(None))
    )
    db_llm = result.scalar_one_or_none()
    
    if not db_llm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM not found",
        )
    
    db_llm.deleted_date = datetime.now(timezone.utc)
    db_llm.user_id_last_update = user.id


@router.post("/{llm_id}/test", response_model=TestLLMResponse)
async def test_llm_connection(
    llm_id: int,
    user: SuperAdminUser,
    db: DbSession,
) -> TestLLMResponse:
    """
    Test LLM connection.

    Args:
        llm_id: The ID of the LLM to test.
        user: The authenticated user.
        db: Database session.

    Returns:
        TestLLMResponse: Connection test result.

    Raises:
        HTTPException: 404 if LLM not found.
    """
    result = await db.execute(
        select(LLMORM)
        .where(LLMORM.id == llm_id)
        .where(LLMORM.deleted_date.is_(None))
    )
    db_llm = result.scalar_one_or_none()
    
    if not db_llm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM not found",
        )
    
    # Stub: LLM connection test requires LLM router integration (Phase 5)
    return TestLLMResponse(
        success=True,
        message="Connection test not yet implemented",
        latency_ms=None,
    )
