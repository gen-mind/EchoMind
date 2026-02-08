# Open WebUI Integration Guide

This document explains the integration between Open WebUI frontend and EchoMind backend.

## Overview

EchoMind provides compatibility endpoints that allow the Open WebUI SvelteKit frontend to function with the EchoMind backend, using Authentik for authentication.

## Components

### 1. OAuth Authentication Flow

**Files:**
- `src/api/routes/oauth.py` - OAuth login and callback handlers
- `src/api/config.py` - OAuth configuration settings

**Flow:**
1. User clicks "Login with Authentik" in WebUI
2. Frontend redirects to `/oauth/oidc/login`
3. Backend redirects to Authentik authorization endpoint
4. User authenticates with Authentik
5. Authentik redirects back to `/oauth/oidc/callback` with authorization code
6. Backend exchanges code for tokens, creates/updates user in database
7. Backend sets token as cookie and redirects to frontend
8. Frontend reads token from cookie and makes authenticated requests

**Environment Variables:**
```bash
API_OAUTH_CLIENT_ID=your-client-id
API_OAUTH_CLIENT_SECRET=your-client-secret
API_OAUTH_PROVIDER_NAME=Authentik
API_OAUTH_AUTHORIZE_URL=https://auth.example.com/application/o/authorize/
API_OAUTH_TOKEN_URL=https://auth.example.com/application/o/token/
API_OAUTH_USERINFO_URL=https://auth.example.com/application/o/userinfo/
API_OAUTH_REDIRECT_URI=https://example.com/oauth/oidc/callback
API_OAUTH_SCOPE=openid profile email
API_OAUTH_FRONTEND_URL=https://example.com
API_OAUTH_COOKIE_DOMAIN=.example.com
```

### 2. WebUI Compatibility Endpoints

**File:** `src/api/routes/webui_compat.py`

Provides API endpoints that match Open WebUI's expected interface:

| Endpoint | Purpose |
|----------|---------|
| `/api/config` | Frontend configuration, feature flags, OAuth providers |
| `/api/v1/auths/` | Session user info with permissions |
| `/api/v1/models/list` | Available LLM models |
| `/api/v1/users/user/settings` | User settings (stub) |
| `/api/v1/configs/banners` | UI banners (stub) |
| `/api/v1/tools/` | Available tools (stub) |
| `/api/v1/chats/` | Chat list (stub) |
| `/api/v1/chats/all/tags` | Chat tags (stub) |
| `/api/v1/prompts/` | Saved prompts (stub) |
| `/api/v1/knowledge/` | Knowledge bases (stub) |
| `/api/v1/users/{user_id}/profile/image` | User profile image (SVG placeholder) |
| `/api/v1/models/{model_id}/profile/image` | Model icon (SVG placeholder) |

**Note:** Most endpoints are stubs returning empty arrays/objects for MVP. Full implementation will be added incrementally.

### 3. Socket.IO Real-Time Communication

**File:** `src/api/socketio_server.py`

Provides real-time bidirectional communication for:
- Chat room subscriptions
- Live message updates
- Typing indicators
- Model status updates

**Events:**
- `connect` - Client connection established
- `disconnect` - Client disconnection
- `join_room` - Subscribe to chat room events
- `leave_room` - Unsubscribe from chat room
- `ping` - Connection health check

**Mounted at:** `/ws/socket.io/`

### 4. Database Seeding

**File:** `src/migration/migrations/versions/20260206_010000_seed_default_llm.py`

Seeds default LLMs on first deployment:
- GPT-4o (default)
- GPT-4o Mini
- Claude 3.5 Sonnet

## Testing

### Integration Tests

**File:** `tests/integration/test_webui_compat.py`

Comprehensive tests verifying that API responses match Open WebUI's expected format. Catches data structure mismatches before deployment.

**Install test dependencies:**
```bash
pip install -r tests/requirements-test.txt
```

**Run integration tests:**
```bash
# From project root
python -m pytest tests/integration/ -v

# With coverage
python -m pytest tests/integration/ --cov=api.routes.webui_compat --cov-report=term-missing
```

**Critical tests:**
- `test_config_endpoint_unauthenticated` - Verifies config structure and default_models is string (not array)
- `test_models_list_structure` - Validates LLM model response format
- `test_profile_image_svg` - Ensures profile images return valid SVG
- `test_session_user_without_auth` - Verifies authentication requirement

## Deployment

### Docker Compose

The API container needs Socket.IO support:

**Update `deployment/docker-cluster/docker-compose-host.yml`:**
```yaml
echomind-api:
  environment:
    # OAuth settings (see above)
    - API_OAUTH_CLIENT_ID=${WEB_OIDC_CLIENT_ID}
    # ... other OAuth vars ...
```

**Rebuild API container:**
```bash
cd deployment/docker-cluster
docker compose -f docker-compose-host.yml up -d --build echomind-api
```

### Traefik Routing

Ensure Traefik routes WebSocket connections to Socket.IO:

```yaml
labels:
  - "traefik.http.routers.api.rule=Host(`example.com`) && PathPrefix(`/api`, `/oauth`, `/ws`)"
```

## Troubleshooting

### Login Loop (Redirects Back to Auth Page)

**Symptom:** After OAuth callback, user redirects back to login page

**Causes:**
1. Cookie domain mismatch - check `API_OAUTH_COOKIE_DOMAIN`
2. Token not set as cookie - verify `httponly=False` in oauth.py
3. Frontend can't read cookie - check browser dev tools → Application → Cookies

**Fix:** Ensure `API_OAUTH_COOKIE_DOMAIN` starts with `.` for subdomain sharing (e.g., `.demo.echomind.ch`)

### Socket.IO Connection Failed

**Symptom:** Console errors: `WebSocket connection to 'wss://example.com/ws/socket.io/' failed`

**Causes:**
1. Socket.IO not mounted - check main.py has `app.mount("/ws/socket.io", socket_app)`
2. Missing python-socketio dependency
3. Traefik not routing /ws/* to API

**Fix:**
```bash
pip install python-socketio==5.11.4
# Restart API container
```

### JavaScript Error: `split is not a function`

**Symptom:** Frontend error: `rt.default_models.split is not a function`

**Cause:** `default_models` field returned as array instead of string

**Fix:** In webui_compat.py, ensure `default_models=""` (empty string, not empty array)

### 404 Errors on Profile Images

**Symptom:** Missing icons for users and models

**Cause:** Profile image endpoints not implemented

**Fix:** Already implemented as SVG placeholders in webui_compat.py

## Future Enhancements

### Priority 1: Full Endpoint Implementation
- Replace stub endpoints with actual database queries
- Implement chat CRUD operations
- Add prompt and tool management

### Priority 2: Enhanced Socket.IO
- Implement real-time chat message streaming
- Add typing indicators
- Broadcast model status changes

### Priority 3: Profile Image Storage
- Replace SVG placeholders with actual image uploads
- Store in MinIO/S3
- Support avatar generation services

### Priority 4: Advanced Authentication
- Implement refresh token rotation
- Add session management
- Support multiple OAuth providers
