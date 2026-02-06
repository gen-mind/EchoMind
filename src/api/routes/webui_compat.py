"""
Open WebUI Compatibility Endpoints.

Provides API endpoints compatible with Open WebUI frontend at /api/* (without v1 prefix).
These endpoints enable the Open WebUI SvelteKit frontend to function with EchoMind backend.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.dependencies import DbSession, OptionalVerifiedUser
from echomind_lib.db.models import LLM as LLMORM

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# Response Models
# =============================================================================


class WebUIConfigResponse(BaseModel):
    """Response model for /api/config endpoint."""

    status: bool = Field(True, description="Backend status")
    name: str = Field("EchoMind", description="Application name")
    version: str = Field("0.1.0", description="Application version")
    default_locale: str = Field("en-US", description="Default locale")
    oauth: dict[str, Any] = Field(default_factory=dict, description="OAuth providers")
    features: dict[str, Any] = Field(
        default_factory=dict, description="Feature flags"
    )
    default_models: str = Field("", description="Default model ID")
    default_prompt_suggestions: list[dict[str, Any]] = Field(
        default_factory=list, description="Default prompt suggestions"
    )


class WebUIVersionResponse(BaseModel):
    """Response model for /api/version endpoint."""

    version: str = Field("0.1.0", description="Application version")


class WebUIChangelogResponse(BaseModel):
    """Response model for /api/changelog endpoint."""

    pass


class WebUIModelInfo(BaseModel):
    """Model information for Open WebUI format."""

    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model display name")
    object: str = Field("model", description="Object type")
    owned_by: str = Field("echomind", description="Model owner")


class WebUIModelsResponse(BaseModel):
    """Response model for /api/models endpoint."""

    data: list[WebUIModelInfo] = Field(
        default_factory=list, description="List of models"
    )


# =============================================================================
# Feature Configuration
# =============================================================================

DEFAULT_FEATURES = {
    "auth": True,
    "auth_trusted_header": False,
    "enable_signup": False,
    "enable_login_form": True,
    "enable_websocket": True,
    "enable_api_keys": False,
    "enable_version_update_check": False,
    "enable_public_active_users_count": False,
}

AUTHENTICATED_FEATURES = {
    **DEFAULT_FEATURES,
    "enable_direct_connections": False,
    "enable_folders": True,
    "folder_max_file_count": 100,
    "enable_channels": False,
    "enable_notes": False,
    "enable_web_search": False,
    "enable_code_execution": False,
    "enable_code_interpreter": False,
    "enable_image_generation": False,
    "enable_autocomplete_generation": False,
    "enable_community_sharing": False,
    "enable_message_rating": True,
    "enable_user_webhooks": False,
    "enable_user_status": False,
    "enable_admin_export": True,
    "enable_admin_chat_access": False,
    "enable_google_drive_integration": False,
    "enable_onedrive_integration": False,
    "enable_memories": False,
}


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/config", response_model=WebUIConfigResponse)
async def get_config(
    request: Request,
    user: OptionalVerifiedUser,
) -> WebUIConfigResponse:
    """
    Get application configuration for Open WebUI frontend.

    This is the critical endpoint that the frontend checks on startup.
    Returns status=true to indicate the backend is available.

    Args:
        request: The HTTP request.
        user: Optional authenticated user.

    Returns:
        WebUIConfigResponse: Application configuration.
    """
    logger.debug("📋 Config requested by user: %s", user.id if user else "anonymous")

    # Use authenticated features if user is logged in
    features = AUTHENTICATED_FEATURES if user else DEFAULT_FEATURES

    return WebUIConfigResponse(
        status=True,
        name="EchoMind",
        version="0.1.0",
        default_locale="en-US",
        oauth={"providers": {}},
        features=features,
        default_models="",
        default_prompt_suggestions=[
            {
                "title": ["Help me ", "with my research"],
                "content": "Help me understand the key findings from my documents.",
            },
            {
                "title": ["Summarize ", "my documents"],
                "content": "Please summarize the main points from my uploaded documents.",
            },
        ],
    )


@router.get("/models", response_model=WebUIModelsResponse)
async def get_models(
    user: OptionalVerifiedUser,
    db: DbSession,
) -> WebUIModelsResponse:
    """
    Get available models in Open WebUI format.

    Args:
        user: Optional authenticated user.
        db: Database session.

    Returns:
        WebUIModelsResponse: List of available models.
    """
    # Fetch active LLMs from database
    result = await db.execute(
        select(LLMORM)
        .where(LLMORM.deleted_date.is_(None))
        .where(LLMORM.is_active == True)  # noqa: E712
        .order_by(LLMORM.name)
    )
    db_llms = result.scalars().all()

    models = [
        WebUIModelInfo(
            id=llm.model_id,
            name=llm.name,
            object="model",
            owned_by="echomind",
        )
        for llm in db_llms
    ]

    logger.debug("📊 Returning %d models", len(models))
    return WebUIModelsResponse(data=models)


@router.get("/version", response_model=WebUIVersionResponse)
async def get_version() -> WebUIVersionResponse:
    """
    Get application version.

    Returns:
        WebUIVersionResponse: Application version.
    """
    return WebUIVersionResponse(version="0.1.0")


@router.get("/version/updates")
async def get_version_updates() -> dict[str, Any]:
    """
    Get version update information.

    Returns:
        Empty dict since we don't support auto-updates.
    """
    return {"available": False, "version": "0.1.0"}


@router.get("/changelog")
async def get_changelog() -> dict[str, Any]:
    """
    Get application changelog.

    Returns:
        Minimal changelog response.
    """
    return {
        "0.1.0": {
            "date": "2024-01-01",
            "description": "Initial release of EchoMind",
        }
    }


@router.get("/usage")
async def get_usage(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Get usage statistics.

    Args:
        user: Optional authenticated user.

    Returns:
        Usage statistics (stub).
    """
    return {
        "total_tokens": 0,
        "total_requests": 0,
    }


@router.get("/webhook")
async def get_webhook() -> dict[str, str]:
    """
    Get webhook URL (stub).

    Returns:
        Empty webhook URL.
    """
    return {"url": ""}


@router.post("/webhook")
async def update_webhook() -> dict[str, str]:
    """
    Update webhook URL (stub).

    Returns:
        Empty webhook URL.
    """
    return {"url": ""}


@router.get("/community_sharing")
async def get_community_sharing() -> dict[str, bool]:
    """
    Get community sharing status (stub).

    Returns:
        Community sharing disabled.
    """
    return {"enabled": False}


@router.get("/community_sharing/toggle")
async def toggle_community_sharing() -> dict[str, bool]:
    """
    Toggle community sharing (stub).

    Returns:
        Community sharing disabled.
    """
    return {"enabled": False}


@router.get("/config/models")
async def get_model_config() -> dict[str, list[Any]]:
    """
    Get model configuration (stub).

    Returns:
        Empty model configuration.
    """
    return {"models": []}


@router.post("/config/models")
async def update_model_config() -> dict[str, list[Any]]:
    """
    Update model configuration (stub).

    Returns:
        Empty model configuration.
    """
    return {"models": []}


@router.get("/config/model/filter")
async def get_model_filter() -> dict[str, Any]:
    """
    Get model filter configuration (stub).

    Returns:
        Model filter configuration.
    """
    return {"enabled": False, "models": []}


@router.post("/config/model/filter")
async def update_model_filter() -> dict[str, Any]:
    """
    Update model filter configuration (stub).

    Returns:
        Model filter configuration.
    """
    return {"enabled": False, "models": []}


# =============================================================================
# Chat-related stubs (not fully implemented)
# =============================================================================


@router.post("/chat/completed")
async def chat_completed() -> dict[str, bool]:
    """
    Mark chat as completed (stub).

    Returns:
        Success status.
    """
    return {"success": True}


@router.post("/chat/actions/{action_id}")
async def chat_action(action_id: str) -> dict[str, bool]:
    """
    Execute chat action (stub).

    Args:
        action_id: The action ID.

    Returns:
        Success status.
    """
    return {"success": True}


@router.get("/tasks")
async def list_tasks() -> dict[str, list[Any]]:
    """
    List tasks (stub).

    Returns:
        Empty task list.
    """
    return {"tasks": []}


@router.get("/tasks/chat/{chat_id}")
async def get_tasks_by_chat(chat_id: str) -> dict[str, list[Any]]:
    """
    Get tasks by chat ID (stub).

    Args:
        chat_id: The chat ID.

    Returns:
        Empty task list.
    """
    return {"tasks": []}


@router.post("/tasks/stop/{task_id}")
async def stop_task(task_id: str) -> dict[str, bool]:
    """
    Stop a task (stub).

    Args:
        task_id: The task ID.

    Returns:
        Success status.
    """
    return {"success": True}
