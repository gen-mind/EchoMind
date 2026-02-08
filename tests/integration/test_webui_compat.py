"""Integration tests for Open WebUI compatibility endpoints.

Tests verify that response formats match what the frontend expects,
catching data structure mismatches before deployment.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from api.main import app


@pytest.mark.asyncio
async def test_config_endpoint_unauthenticated():
    """Test /api/config returns correct structure for anonymous users."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/config")
        assert response.status_code == 200
        data = response.json()

        # Critical fields that frontend expects
        assert data["status"] is True
        assert "name" in data
        assert "version" in data
        assert "oauth" in data
        assert "providers" in data["oauth"]
        assert "features" in data

        # CRITICAL: default_models MUST be string (frontend calls .split(','))
        assert isinstance(data["default_models"], str)

        # Default features for unauthenticated users
        features = data["features"]
        assert features["enable_signup"] is False
        assert features["enable_web_search"] is False


@pytest.mark.asyncio
async def test_models_list_structure():
    """Test /api/v1/models/list returns correct format."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/models/list")
        assert response.status_code == 200
        data = response.json()

        # Must have "models" array
        assert "models" in data
        assert isinstance(data["models"], list)

        # If models exist, verify structure
        if data["models"]:
            model = data["models"][0]
            assert "id" in model
            assert "name" in model
            assert "object" in model
            assert model["object"] == "model"
            assert "owned_by" in model


@pytest.mark.asyncio
async def test_user_settings_stub():
    """Test /api/v1/users/user/settings returns expected structure."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # This is a stub endpoint, should return 200 with empty object
        response = await client.get("/api/v1/users/user/settings")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_configs_banners():
    """Test /api/v1/configs/banners returns array."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/configs/banners")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_tools_list():
    """Test /api/v1/tools/ returns array."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/tools/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_chats_list():
    """Test /api/v1/chats/ returns array."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/chats/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_chats_all_tags():
    """Test /api/v1/chats/all/tags returns array."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/chats/all/tags")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_chats_pinned():
    """Test /api/v1/chats/pinned returns array."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/chats/pinned")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_prompts_list():
    """Test /api/v1/prompts/ returns array."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/prompts/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_knowledge_list():
    """Test /api/v1/knowledge/ returns array."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/knowledge/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_profile_image_svg():
    """Test profile image endpoints return valid SVG."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # User profile image
        response = await client.get("/api/v1/users/test-user/profile/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert b"<svg" in response.content
        assert b"xmlns" in response.content  # Valid SVG namespace

        # Model profile image (with model_id parameter)
        response = await client.get("/api/v1/models/gpt-4/profile/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert b"<svg" in response.content
        assert b"xmlns" in response.content  # Valid SVG namespace


@pytest.mark.asyncio
async def test_session_user_without_auth():
    """Test /api/v1/auths/ requires authentication."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/auths/")
        # Should return 401 or redirect to login
        assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_oauth_login_redirect():
    """Test /oauth/oidc/login redirects to OAuth provider."""
    async with AsyncClient(app=app, base_url="http://test", follow_redirects=False) as client:
        response = await client.get("/oauth/oidc/login")

        # If OAuth is configured, should redirect
        # If not configured, should return 501
        assert response.status_code in [302, 501]

        if response.status_code == 302:
            assert "location" in response.headers
            # Should redirect to OAuth provider
            location = response.headers["location"]
            assert "authorize" in location or "oauth" in location.lower()
