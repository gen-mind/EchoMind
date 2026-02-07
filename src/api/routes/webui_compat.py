"""
Open WebUI Compatibility Endpoints.

Provides API endpoints compatible with Open WebUI frontend at /api/* (without v1 prefix).
These endpoints enable the Open WebUI SvelteKit frontend to function with EchoMind backend.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.config import get_settings
from api.dependencies import DbSession, OptionalVerifiedUser
from echomind_lib.db.models import LLM as LLMORM
from echomind_lib.db.models import User as UserORM
import jwt as pyjwt

from echomind_lib.helpers.auth import extract_bearer_token, get_jwt_validator

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# Response Models
# =============================================================================


class WebUIConfigResponse(BaseModel):
    """Response model for /api/config endpoint.

    Must include all nested objects the frontend accesses:
    audio, permissions, code, file, ui, google_drive, onedrive.
    Missing nested objects cause TypeError in frontend components.
    [Source: Open WebUI main.py get_app_config()]
    """

    status: bool = Field(True, description="Backend status")
    name: str = Field("Echo-Mind", description="Application name")
    version: str = Field("0.1.0", description="Application version")
    default_locale: str = Field("en-US", description="Default locale")
    oauth: dict[str, Any] = Field(default_factory=dict, description="OAuth providers")
    features: dict[str, Any] = Field(
        default_factory=dict, description="Feature flags"
    )
    default_models: str = Field("", description="Comma-separated default model IDs")
    default_prompt_suggestions: list[dict[str, Any]] = Field(
        default_factory=list, description="Default prompt suggestions"
    )
    # Nested objects required by authenticated frontend components
    audio: dict[str, Any] = Field(default_factory=dict, description="Audio TTS/STT config")
    permissions: dict[str, Any] = Field(default_factory=dict, description="User permissions")
    code: dict[str, Any] = Field(default_factory=dict, description="Code execution config")
    file: dict[str, Any] = Field(default_factory=dict, description="File upload config")
    ui: dict[str, Any] = Field(default_factory=dict, description="UI overlay config")
    google_drive: dict[str, Any] = Field(
        default_factory=dict, description="Google Drive config"
    )
    onedrive: dict[str, Any] = Field(default_factory=dict, description="OneDrive config")


class WebUIVersionResponse(BaseModel):
    """Response model for /api/version endpoint."""

    version: str = Field("0.1.0", description="Application version")


class WebUIChangelogResponse(BaseModel):
    """Response model for /api/changelog endpoint."""

    pass


class WebUIModelMeta(BaseModel):
    """Model metadata for Open WebUI format."""

    hidden: bool = Field(False, description="Whether model is hidden")
    description: str = Field("", description="Model description")
    tags: list[dict[str, str]] = Field(default_factory=list, description="Model tags")


class WebUIModelInfoDetail(BaseModel):
    """Model info wrapper for Open WebUI format."""

    meta: WebUIModelMeta = Field(default_factory=WebUIModelMeta, description="Model metadata")


class WebUIModelInfo(BaseModel):
    """Model information for Open WebUI format."""

    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model display name")
    object: str = Field("model", description="Object type")
    owned_by: str = Field("echomind", description="Model owner")
    info: WebUIModelInfoDetail = Field(
        default_factory=WebUIModelInfoDetail, description="Model info"
    )
    actions: list[Any] = Field(default_factory=list, description="Model actions")
    filters: list[Any] = Field(default_factory=list, description="Model filters")


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
    logger.debug(f"📋 Config requested by user: {user.id if user else 'anonymous'}")

    # Use authenticated features if user is logged in
    features = AUTHENTICATED_FEATURES if user else DEFAULT_FEATURES

    # Build OAuth providers config
    settings = get_settings()
    oauth_providers: dict[str, Any] = {}
    if settings.oauth_client_id and settings.oauth_authorize_url:
        # OIDC provider configured (Authentik)
        oauth_providers["oidc"] = settings.oauth_provider_name

    # CRITICAL: These nested objects MUST always be returned with full structure.
    # The frontend accesses $config.audio.tts.engine WITHOUT optional chaining.
    # If audio is {}, $config.audio.tts is undefined → TypeError crashes the UI.
    # [Source: Open WebUI Audio.svelte lines 53, 97, 182, 350]
    audio = {
        "tts": {"engine": "", "voice": "", "split_on": ""},
        "stt": {"engine": ""},
    }
    code = {"engine": ""}
    file_config = {
        "max_size": 0,
        "max_count": 0,
        "image_compression": {"width": None, "height": None},
    }
    ui = {
        "pending_user_overlay_title": "",
        "pending_user_overlay_content": "",
    }
    google_drive = {"client_id": "", "api_key": ""}
    onedrive = {"client_id_personal": "", "client_id_business": ""}

    # Permissions are user-specific
    permissions: dict[str, Any] = {}
    if user:
        permissions = {
            "workspace": {
                "models": True,
                "knowledge": True,
                "prompts": True,
                "tools": True,
            },
            "chat": {
                "controls": True,
                "file_upload": True,
                "delete": True,
                "edit": True,
                "share": True,
                "export": True,
                "temporary": True,
                "temporary_enforced": False,
            },
            "features": {
                "web_search": False,
                "image_generation": False,
                "code_interpreter": False,
            },
        }

    return WebUIConfigResponse(
        status=True,
        name="Echo-Mind",
        version="0.1.0",
        default_locale="en-US",
        oauth={"providers": oauth_providers},
        features=features,
        default_models="gpt-4o",
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
        audio=audio,
        permissions=permissions,
        code=code,
        file=file_config,
        ui=ui,
        google_drive=google_drive,
        onedrive=onedrive,
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
    # Try fetching from DB first, fall back to hardcoded defaults
    models: list[WebUIModelInfo] = []
    try:
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
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch models from DB: {e}")

    # Hardcoded fallback if no models in DB
    if not models:
        models = [
            WebUIModelInfo(
                id="gpt-4o",
                name="GPT-4o",
                object="model",
                owned_by="openai",
            ),
            WebUIModelInfo(
                id="claude-3-5-sonnet-20241022",
                name="Claude 3.5 Sonnet",
                object="model",
                owned_by="anthropic",
            ),
        ]

    logger.debug(f"📊 Returning {len(models)} models")
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


# =============================================================================
# User Settings & Config Stubs (for Open WebUI frontend)
# =============================================================================


@router.get("/v1/users/user/settings")
async def get_user_settings(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Get user settings.

    Open WebUI reads `settings.models` as an array for selectedModelIds.
    The `models` field MUST be a top-level array, NOT nested under `ui`.
    [Source: Open WebUI Chat.svelte - selectedModels = $settings?.models]

    Args:
        user: Optional authenticated user.

    Returns:
        User settings with models as top-level array.
    """
    return {
        "ui": {},
        "models": ["gpt-4o"],
    }


@router.post("/v1/users/user/settings")
async def update_user_settings(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Update user settings (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Updated settings.
    """
    return {
        "ui": {},
        "models": ["gpt-4o"],
    }


@router.post("/v1/users/user/settings/update")
async def update_user_settings_alt(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Update user settings - alternative endpoint (stub).

    Open WebUI calls this endpoint for settings updates.

    Args:
        user: Optional authenticated user.

    Returns:
        Updated settings.
    """
    return {
        "ui": {},
        "models": ["gpt-4o"],
    }


@router.get("/v1/configs/banners")
async def get_banners() -> list[Any]:
    """
    Get banner notifications (stub).

    Returns:
        Empty list of banners.
    """
    return []


@router.get("/v1/groups/")
async def list_groups() -> list[Any]:
    """
    List user groups (stub).

    Returns:
        Empty list of groups.
    """
    return []


@router.get("/v1/tools/")
async def get_tools() -> list[Any]:
    """
    Get available tools (stub).

    Returns:
        Empty list of tools.
    """
    return []


@router.get("/v1/functions/")
async def get_functions() -> list[Any]:
    """
    Get available functions (stub).

    Returns:
        Empty list of functions.
    """
    return []


@router.get("/v1/prompts/")
async def get_prompts() -> list[Any]:
    """
    Get saved prompts (stub).

    Returns:
        Empty list of prompts.
    """
    return []


@router.get("/v1/memories/")
async def get_memories() -> list[Any]:
    """
    Get user memories (stub).

    Returns:
        Empty list of memories.
    """
    return []


@router.get("/v1/knowledge/")
async def get_knowledge() -> list[Any]:
    """
    Get knowledge bases (stub).

    Returns:
        Empty list of knowledge bases.
    """
    return []


@router.get("/v1/chats/")
async def get_chats(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get user chats (stub).

    Returns:
        Empty list of chats.
    """
    return []


@router.get("/v1/chats/list")
async def get_chats_list(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get user chats list (stub).

    Returns:
        Empty list of chats.
    """
    return []


@router.get("/v1/chats/tags/all")
async def get_all_chat_tags(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get all chat tags (stub).

    Returns:
        Empty list of tags.
    """
    return []


@router.get("/v1/chats/all/tags")
async def get_chats_all_tags(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get all chat tags - alternative endpoint (stub).

    Returns:
        Empty list of tags.
    """
    return []


@router.get("/v1/chats/pinned")
async def get_pinned_chats(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get pinned chats (stub).

    Returns:
        Empty list of pinned chats.
    """
    return []


@router.get("/v1/models/list")
async def get_models_list(
    user: OptionalVerifiedUser,
    db: DbSession,
) -> dict[str, Any]:
    """
    Get available models in Open WebUI format.

    Args:
        user: Optional authenticated user.
        db: Database session.

    Returns:
        List of available models.
    """
    # Try fetching from DB, fall back to hardcoded defaults
    models: list[dict[str, Any]] = []
    try:
        result = await db.execute(
            select(LLMORM)
            .where(LLMORM.deleted_date.is_(None))
            .where(LLMORM.is_active == True)  # noqa: E712
            .order_by(LLMORM.name)
        )
        db_llms = result.scalars().all()
        models = [
            {
                "id": llm.model_id,
                "name": llm.name,
                "object": "model",
                "owned_by": "echomind",
                "info": {"meta": {}},
            }
            for llm in db_llms
        ]
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch models from DB: {e}")

    # Hardcoded fallback if no models in DB
    if not models:
        models = [
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "object": "model",
                "owned_by": "openai",
                "info": {"meta": {}},
            },
            {
                "id": "claude-3-5-sonnet-20241022",
                "name": "Claude 3.5 Sonnet",
                "object": "model",
                "owned_by": "anthropic",
                "info": {"meta": {}},
            },
        ]

    return {"models": models}


@router.get("/v1/models/base")
async def get_base_models(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get base models (stub).

    Returns:
        Empty list.
    """
    return []


@router.get("/v1/models/tags")
async def get_model_tags(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get model tags (stub).

    Returns:
        Empty list of tags.
    """
    return []


@router.get("/v1/folders/")
async def get_folders(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get user folders (stub).

    Returns:
        Empty list of folders.
    """
    return []


@router.get("/v1/configs/")
async def get_configs() -> dict[str, Any]:
    """
    Get app configs (stub).

    Returns:
        Default configs.
    """
    return {}


# =============================================================================
# Auth Compatibility Endpoints (for Open WebUI frontend)
# =============================================================================


@router.post("/v1/auths/update/timezone")
async def update_user_timezone(user: OptionalVerifiedUser) -> dict[str, str]:
    """
    Update user timezone (stub).

    Returns:
        Timezone set to CET.
    """
    return {"timezone": "Europe/Zurich"}


@router.post("/v1/auths/update/profile")
async def update_user_profile(user: OptionalVerifiedUser) -> dict[str, bool]:
    """
    Update user profile (stub).

    Returns:
        Success status.
    """
    return {"success": True}


@router.get("/v1/auths/")
async def get_session_user(
    request: Request,
    db: DbSession,
) -> dict[str, Any]:
    """
    Get current session user from token.

    Open WebUI frontend calls this to validate the token and get user info.

    Args:
        request: The HTTP request.
        db: Database session.

    Returns:
        User info including the token.
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    token = extract_bearer_token(auth_header)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    try:
        validator = get_jwt_validator()
        token_user = validator.validate_token(token)
    except Exception as e:
        logger.info(f"🔒 Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Extract token expiry for frontend timer
    # jwt.decode without verify to get exp (token already validated above)
    try:
        unverified = pyjwt.decode(token, options={"verify_signature": False})
        expires_at = unverified.get("exp")
    except Exception:
        expires_at = None

    # Look up user in database
    result = await db.execute(
        select(UserORM).where(UserORM.external_id == token_user.external_id)
    )
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Return user info in Open WebUI format
    return {
        "id": str(db_user.id),
        "email": db_user.email,
        "name": f"{db_user.first_name} {db_user.last_name}".strip() or db_user.user_name,
        "role": "admin" if "admin" in (db_user.roles or []) else "user",
        "profile_image_url": f"/api/v1/users/{db_user.id}/profile/image",
        "token": token,  # Return the token back
        "expires_at": expires_at,  # For frontend token expiry timer
        "permissions": {
            "chat": {
                "controls": True,
                "file_upload": True,
                "delete": True,
            },
            "workspace": {
                "models": True,
                "knowledge": True,
                "prompts": True,
                "tools": True,
            },
        },
    }



# =============================================================================
# Image/Avatar Endpoints (for profile pictures)
# =============================================================================


@router.get("/v1/users/{user_id}/profile/image")
async def get_user_profile_image(user_id: str) -> Response:
    """
    Get user profile image (returns placeholder SVG).

    Args:
        user_id: User ID.

    Returns:
        SVG placeholder image.
    """
    # Generate a simple geometric SVG avatar (no emojis)
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="50" fill="#6366f1"/>
        <circle cx="50" cy="35" r="15" fill="white"/>
        <ellipse cx="50" cy="75" rx="25" ry="20" fill="white"/>
    </svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/v1/models/{model_id}/profile/image")
async def get_model_profile_image(model_id: str) -> Response:
    """
    Get model profile image (returns placeholder SVG).

    Args:
        model_id: Model ID.

    Returns:
        SVG placeholder image.
    """
    # Generate a simple geometric SVG icon (no emojis)
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="50" fill="#10b981"/>
        <rect x="30" y="35" width="40" height="30" rx="5" fill="white"/>
        <circle cx="40" cy="45" r="3" fill="#10b981"/>
        <circle cx="60" cy="45" r="3" fill="#10b981"/>
        <path d="M 35 55 Q 50 60 65 55" stroke="white" stroke-width="2" fill="none"/>
    </svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/v1/models/model/profile/image")
async def get_model_profile_image_legacy() -> Response:
    """
    Get model profile image - legacy endpoint (returns placeholder SVG).

    This is a fallback for older frontend code that calls /model/profile/image
    instead of /{model_id}/profile/image.

    Returns:
        SVG placeholder image.
    """
    # Generate a simple geometric SVG icon (no emojis)
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="50" fill="#10b981"/>
        <rect x="30" y="35" width="40" height="30" rx="5" fill="white"/>
        <circle cx="40" cy="45" r="3" fill="#10b981"/>
        <circle cx="60" cy="45" r="3" fill="#10b981"/>
        <path d="M 35 55 Q 50 60 65 55" stroke="white" stroke-width="2" fill="none"/>
    </svg>"""
    return Response(content=svg, media_type="image/svg+xml")


# =============================================================================
# Settings Modal Endpoint Stubs
# These endpoints are called by Open WebUI SettingsModal tabs.
# Each tab mounts components that call specific APIs on render.
# =============================================================================


# --- Audio Tab ---
# [Source: Open WebUI Audio.svelte → getVoices() → _getVoices(token)]


@router.get("/v1/audio/voices")
async def get_audio_voices(user: OptionalVerifiedUser) -> dict[str, list[Any]]:
    """
    Get available TTS voices (stub).

    Called by Audio settings tab when TTS engine is not browser-default.

    Args:
        user: Optional authenticated user.

    Returns:
        Empty voices list.
    """
    return {"voices": []}


@router.get("/v1/audio/config")
async def get_audio_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Get audio configuration (stub).

    Called by admin Audio settings tab.

    Args:
        user: Optional authenticated user.

    Returns:
        Default audio config.
    """
    return {
        "tts": {
            "OPENAI_API_BASE_URL": "",
            "OPENAI_API_KEY": "",
            "ENGINE": "",
            "MODEL": "",
            "VOICE": "",
            "SPLIT_ON": "",
        },
        "stt": {
            "OPENAI_API_BASE_URL": "",
            "OPENAI_API_KEY": "",
            "ENGINE": "",
            "MODEL": "",
        },
    }


@router.post("/v1/audio/config/update")
async def update_audio_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Update audio configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Updated audio config.
    """
    return {
        "tts": {"ENGINE": "", "MODEL": "", "VOICE": ""},
        "stt": {"ENGINE": "", "MODEL": ""},
    }


@router.get("/v1/audio/models")
async def get_audio_models(user: OptionalVerifiedUser) -> dict[str, list[Any]]:
    """
    Get available audio models (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty models list.
    """
    return {"models": []}


# --- Account Tab ---
# [Source: Open WebUI Account.svelte → getAPIKey(token)]


@router.get("/v1/auths/api_key")
async def get_api_key(user: OptionalVerifiedUser) -> dict[str, str]:
    """
    Get user API key (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty API key.
    """
    return {"api_key": ""}


@router.post("/v1/auths/api_key")
async def create_api_key(user: OptionalVerifiedUser) -> dict[str, str]:
    """
    Create/regenerate API key (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty API key.
    """
    return {"api_key": ""}


@router.delete("/v1/auths/api_key")
async def delete_api_key(user: OptionalVerifiedUser) -> dict[str, bool]:
    """
    Delete API key (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Success status.
    """
    return {"success": True}


@router.post("/v1/users/user/info/update")
async def update_user_info(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Update user info like location (stub).

    Called by Interface settings tab when location access is enabled.

    Args:
        user: Optional authenticated user.

    Returns:
        Empty user info.
    """
    return {}


# --- Data Controls Tab ---
# [Source: Open WebUI DataControls.svelte → archiveAllChats, deleteAllChats, etc.]


@router.get("/v1/chats/all")
async def get_all_chats(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get all chats for export (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty list of chats.
    """
    return []


@router.post("/v1/chats/archive/all")
async def archive_all_chats(user: OptionalVerifiedUser) -> dict[str, bool]:
    """
    Archive all chats (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Success status.
    """
    return {"success": True}


@router.delete("/v1/chats/")
async def delete_all_chats(user: OptionalVerifiedUser) -> dict[str, bool]:
    """
    Delete all chats (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Success status.
    """
    return {"success": True}


@router.post("/v1/chats/import")
async def import_chats(user: OptionalVerifiedUser) -> list[Any]:
    """
    Import chats (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty list.
    """
    return []


# --- About Tab ---
# [Source: Open WebUI About.svelte → getVersionUpdates, getOllamaVersion]


@router.get("/ollama/config")
async def get_ollama_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Get Ollama configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Ollama disabled config.
    """
    return {
        "ENABLE_OLLAMA_API": False,
        "OLLAMA_BASE_URLS": [],
        "OLLAMA_API_CONFIGS": {},
    }


@router.get("/openai/config")
async def get_openai_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Get OpenAI API configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Default OpenAI config.
    """
    return {
        "ENABLE_OPENAI_API": True,
        "OPENAI_API_BASE_URLS": ["https://api.openai.com/v1"],
        "OPENAI_API_KEYS": [""],
        "OPENAI_API_CONFIGS": {},
    }


# --- Admin Config Endpoints ---
# [Source: Open WebUI admin Settings pages]


@router.get("/v1/configs/models")
async def get_models_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Get models configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Default models config.
    """
    return {
        "DEFAULT_MODELS": "gpt-4o",
        "DEFAULT_PINNED_MODELS": "",
        "MODEL_ORDER_LIST": [],
    }


@router.post("/v1/configs/models")
async def set_models_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Set models configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Models config.
    """
    return {
        "DEFAULT_MODELS": "gpt-4o",
        "DEFAULT_PINNED_MODELS": "",
        "MODEL_ORDER_LIST": [],
    }


@router.get("/v1/configs/connections")
async def get_connections_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Get connections configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty connections config.
    """
    return {}


@router.post("/v1/configs/connections")
async def set_connections_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Set connections configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty connections config.
    """
    return {}


@router.get("/v1/configs/tool_servers")
async def get_tool_servers(user: OptionalVerifiedUser) -> list[Any]:
    """
    Get tool server connections (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty list.
    """
    return []


@router.post("/v1/configs/tool_servers")
async def set_tool_servers(user: OptionalVerifiedUser) -> list[Any]:
    """
    Set tool server connections (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Empty list.
    """
    return []


@router.get("/v1/auths/admin/config")
async def get_admin_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Get admin configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Default admin config.
    """
    return {
        "SHOW_ADMIN_DETAILS": True,
        "ENABLE_SIGNUP": False,
        "DEFAULT_USER_ROLE": "user",
    }


@router.post("/v1/auths/admin/config")
async def set_admin_config(user: OptionalVerifiedUser) -> dict[str, Any]:
    """
    Set admin configuration (stub).

    Args:
        user: Optional authenticated user.

    Returns:
        Admin config.
    """
    return {
        "SHOW_ADMIN_DETAILS": True,
        "ENABLE_SIGNUP": False,
        "DEFAULT_USER_ROLE": "user",
    }
