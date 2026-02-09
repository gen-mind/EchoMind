# Google OAuth 2.0 Architecture in EchoMind

**Version:** 1.0
**Last Updated:** 2026-02-09
**Status:** Production (V1)

This document describes how Google OAuth 2.0 is implemented in EchoMind, covering authentication flow, token management, scope handling, API quota limits, and the V2 roadmap.

---

## Table of Contents

1. [Overview](#overview)
2. [OAuth Pattern: User Delegation (V1)](#oauth-pattern-user-delegation-v1)
3. [Authentication Flow](#authentication-flow)
4. [Incremental Authorization](#incremental-authorization)
5. [Token Management](#token-management)
6. [Database Schema](#database-schema)
7. [API Endpoints](#api-endpoints)
8. [Google API Quota Limits](#google-api-quota-limits)
9. [V2 Roadmap](#v2-roadmap)
10. [References](#references)

---

## Overview

EchoMind integrates with Google Workspace services (Drive, Gmail, Calendar, Contacts) to allow users to ingest and search their personal Google data. **V1 uses OAuth 2.0 User Delegation**, where each user authorizes EchoMind to access their individual Google account.

### Key Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend OAuth Routes** | FastAPI (`google_oauth.py`) | Handles OAuth flow, token exchange, credential storage |
| **Frontend OAuth UI** | SvelteKit 5 | OAuth popup, workspace cards, connector modal |
| **Token Storage** | PostgreSQL (`google_credentials` table) | Per-user tokens, scopes, expiry |
| **Google APIs** | Drive, Gmail, Calendar, People APIs | Data fetching via connectors |

### Deployment Model

- **Pattern:** One EchoMind installation per customer (dedicated GPU server)
- **Domains:** All deployments use `*.echomind.ch` subdomains (e.g., `customer-a.echomind.ch`)
- **OAuth App:** **Single OAuth app** managed by EchoMind admin serves all customer subdomains
- **Redirect URIs:** Each customer subdomain requires explicit redirect URI in Google Cloud Console (no wildcards supported)

---

## OAuth Pattern: User Delegation (V1)

### What is User Delegation?

**User Delegation** means each EchoMind user connects their **personal Google account** via OAuth. The user grants EchoMind permission to access their Drive files, Gmail messages, etc. on their behalf.

### How It Works

1. **User clicks "Connect to Google"** in EchoMind UI (workspace card or connector modal)
2. **OAuth popup opens** with Google consent screen
3. **User authorizes** EchoMind to access their Google data (e.g., "EchoMind wants to access your Google Drive")
4. **Google returns tokens** (access token + refresh token)
5. **EchoMind stores tokens** in PostgreSQL `google_credentials` table (one row per user)
6. **Connectors use tokens** to fetch user's Google data (Drive files, Gmail messages, etc.)

### Characteristics of V1 (User Delegation)

✅ **Pros:**
- Simple setup (no Google Workspace admin required)
- Works with personal Google accounts (gmail.com)
- Per-user granular control (users can revoke anytime)
- No shared credentials

❌ **Cons:**
- Each user must authorize individually
- Cannot access shared organizational resources (e.g., Shared Drives) unless user has access
- Higher OAuth request volume (one flow per user per service)

---

## Authentication Flow

### Flow Diagram

```
┌─────────┐                  ┌─────────────┐                 ┌────────────┐
│ EchoMind│                  │   Backend   │                 │   Google   │
│   UI    │                  │  (FastAPI)  │                 │   OAuth    │
└────┬────┘                  └──────┬──────┘                 └─────┬──────┘
     │                              │                              │
     │  1. Click "Connect to Google"│                              │
     ├─────────────────────────────►│                              │
     │                              │                              │
     │  2. GET /google/auth/url?service=drive&mode=popup           │
     │                              │                              │
     │  3. Return OAuth URL         │                              │
     │◄─────────────────────────────┤                              │
     │                              │                              │
     │  4. Open popup with OAuth URL│                              │
     ├──────────────────────────────┼─────────────────────────────►│
     │                              │                              │
     │                              │  5. User authorizes          │
     │                              │◄─────────────────────────────┤
     │                              │                              │
     │                              │  6. Redirect with code       │
     │                              │  /google/auth/callback?code=..
     │                              │◄─────────────────────────────┤
     │                              │                              │
     │                              │  7. Exchange code for tokens │
     │                              ├─────────────────────────────►│
     │                              │                              │
     │                              │  8. Return access + refresh token
     │                              │◄─────────────────────────────┤
     │                              │                              │
     │                              │  9. Store tokens in DB       │
     │                              │  (google_credentials table)  │
     │                              │                              │
     │  10. postMessage success     │                              │
     │◄─────────────────────────────┤                              │
     │                              │                              │
     │  11. Close popup, reload status                             │
     └──────────────────────────────┘                              │
```

### Detailed Steps

#### Step 1-3: OAuth URL Generation

**Frontend:**
```typescript
// User clicks "Connect to Google" button
const result = await openGoogleOAuthPopup(localStorage.token, 'drive');
```

**Backend (`GET /google/auth/url`):**
```python
# Generate OAuth URL with service-specific scopes
params = {
    "client_id": settings.google_client_id,
    "redirect_uri": settings.google_redirect_uri,
    "response_type": "code",
    "scope": " ".join(scopes_for_service("drive")),  # e.g., drive.readonly
    "access_type": "offline",  # Request refresh token
    "prompt": "consent" if first_time else "select_account",
    "include_granted_scopes": "true",  # Incremental auth
    "state": secrets.token_urlsafe(32)  # CSRF protection
}
url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
```

**State Management:**
- State token stored in-memory dict with (user_id, service, mode, created_at)
- TTL: 10 minutes
- Validated on callback to prevent CSRF attacks

#### Step 4-5: User Authorization

- Frontend opens OAuth URL in 500x600 popup window
- User sees Google consent screen: "EchoMind wants to access your Google Drive"
- User clicks "Allow"

#### Step 6: Google Redirects to Callback

Google redirects to: `https://demo.echomind.ch/api/v1/google/auth/callback?code=4/0AXXX&state=abc123`

#### Step 7-8: Token Exchange

**Backend (`GET /google/auth/callback`):**
```python
# Exchange authorization code for tokens
async with httpx.AsyncClient() as client:
    token_response = await client.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "redirect_uri": settings.google_redirect_uri,
        }
    )

tokens = token_response.json()
# {
#   "access_token": "ya29.a0XXX",
#   "refresh_token": "1//0gXXX",  # Only on first auth or prompt=consent
#   "expires_in": 3600,
#   "scope": "https://www.googleapis.com/auth/drive.readonly ...",
#   "token_type": "Bearer"
# }
```

#### Step 9: Store Tokens in Database

```python
# Upsert google_credentials for user
credential = GoogleCredential(
    user_id=user_id,
    access_token=tokens["access_token"],
    refresh_token=tokens["refresh_token"],
    token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=3600),
    granted_scopes=tokens["scope"].split(),
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
)
db.add(credential)
await db.commit()
```

**Scope Merging:** If user previously authorized Drive and now authorizes Gmail, scopes are merged (union of both).

#### Step 10-11: Return to Frontend

**Popup Mode (V1 default):**
```html
<!-- Backend returns HTML with postMessage script -->
<script>
  window.opener.postMessage({
    type: 'google-oauth-success',
    service: 'drive'
  }, '*');
  window.close();
</script>
```

**Frontend:**
```typescript
// Listen for postMessage from popup
window.addEventListener('message', (event) => {
  if (event.data.type === 'google-oauth-success') {
    toast.success('Connected to Google');
    loadGoogleStatus();  // Refresh UI
  }
});
```

---

## Incremental Authorization

EchoMind uses **incremental authorization** to request scopes only when needed, improving user consent experience.

### How It Works

1. **User connects Drive:** First OAuth flow requests only `drive.readonly` scopes
2. **Later, user connects Gmail:** Second OAuth flow requests `gmail.readonly` scopes
3. **Google merges scopes:** User sees only new scopes (Gmail) for consent, Drive scopes automatically included
4. **Backend merges scopes:** `google_credentials.granted_scopes` becomes union of Drive + Gmail scopes

### Implementation

**OAuth URL includes `include_granted_scopes=true`:**
```python
params = {
    # ...
    "include_granted_scopes": "true",  # Preserve previous grants
}
```

**Backend scope merging (google_oauth.py:302-304):**
```python
if credential:
    # Merge scopes: union of existing + newly granted
    existing_scopes = set(credential.granted_scopes or [])
    merged_scopes = sorted(existing_scopes | set(new_scopes))
    credential.granted_scopes = merged_scopes
```

**Benefits:**
- Users don't see repetitive consent screens
- Avoids "authorization fatigue"
- Follows [Google's best practices](https://developers.google.com/identity/protocols/oauth2/web-server#incrementalAuth)

---

## Token Management

### Token Lifecycle

1. **Access Token:**
   - **Lifespan:** 1 hour (3600 seconds)
   - **Storage:** `google_credentials.access_token`
   - **Usage:** Passed as `Authorization: Bearer <token>` to Google APIs

2. **Refresh Token:**
   - **Lifespan:** No expiry (valid until revoked)
   - **Storage:** `google_credentials.refresh_token`
   - **Usage:** Used to obtain new access tokens when expired

3. **Token Refresh:**
   - **When:** Before making Google API request, check if `token_expires_at` < now
   - **How:** POST to `https://oauth2.googleapis.com/token` with `grant_type=refresh_token`
   - **Result:** New access token (refresh token remains same)

### Token Refresh Implementation

**Connector logic (pseudocode):**
```python
async def get_google_drive_files(user_id: int):
    credential = await get_google_credential(user_id)

    # Check if token expired
    if credential.token_expires_at < datetime.now(timezone.utc):
        # Refresh access token
        new_token = await refresh_google_token(credential.refresh_token)
        credential.access_token = new_token["access_token"]
        credential.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
        await db.commit()

    # Use access token to call Google Drive API
    headers = {"Authorization": f"Bearer {credential.access_token}"}
    response = await httpx.get("https://www.googleapis.com/drive/v3/files", headers=headers)
    return response.json()
```

### Token Revocation

**User-initiated (via UI):**
```bash
DELETE /api/v1/google/auth
```

**Backend:**
1. Calls Google to revoke token: `POST https://oauth2.googleapis.com/revoke?token=<access_token>`
2. Deletes row from `google_credentials` table
3. User must re-authorize to reconnect

**User can also revoke via Google:**
- [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions)
- When user revokes here, EchoMind's next API call will fail with 401, prompting re-auth

---

## Database Schema

### `google_credentials` Table

```sql
CREATE TABLE google_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ NOT NULL,
    granted_scopes TEXT[] NOT NULL DEFAULT '{}',
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    last_update TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_google_credentials_user_id ON google_credentials(user_id);
```

**Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | INTEGER | Foreign key to `users.id`. **One row per user** (not per service). |
| `access_token` | TEXT | Current access token (expires in 1 hour) |
| `refresh_token` | TEXT | Long-lived refresh token |
| `token_expires_at` | TIMESTAMPTZ | When access token expires (UTC) |
| `granted_scopes` | TEXT[] | Array of all scopes user has granted (merged across services) |
| `client_id` | TEXT | Google OAuth Client ID (stored for refresh) |
| `client_secret` | TEXT | Google OAuth Client Secret (stored for refresh) |
| `last_update` | TIMESTAMPTZ | Last token refresh timestamp |
| `created_at` | TIMESTAMPTZ | Initial authorization timestamp |

**Why one row per user?**
- Google's incremental authorization returns cumulative scopes
- Simpler token refresh (one refresh token serves all services)
- Matches Google's intent: "user has authorized EchoMind" vs. "user has authorized EchoMind for each service separately"

---

## API Endpoints

### `GET /api/v1/google/auth/configured`

**Purpose:** Check if Google OAuth is configured on backend (public endpoint, no auth required).

**Response:**
```json
{
  "configured": true
}
```

**Usage:** Frontend calls this on page load to decide whether to show Google connector options.

---

### `GET /api/v1/google/auth/url`

**Purpose:** Generate Google OAuth authorization URL for a specific service.

**Query Parameters:**
- `service` (required): `drive` | `gmail` | `calendar` | `contacts`
- `mode` (optional): `popup` (default) | `redirect`

**Headers:**
- `Authorization: Bearer <jwt_token>`

**Response:**
```json
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=..."
}
```

**Error (501):**
```json
{
  "detail": "Google OAuth is not configured"
}
```

---

### `GET /api/v1/google/auth/callback`

**Purpose:** Handle OAuth callback from Google (exchanges code for tokens).

**Query Parameters:**
- `code`: Authorization code from Google
- `state`: CSRF protection token
- `error`: Error code (if user denied)

**Response (popup mode):**
- HTML page with `postMessage` script to notify opener window

**Response (redirect mode):**
- 302 redirect to `${OAUTH_FRONTEND_URL}/connectors/google/setup`

---

### `GET /api/v1/google/auth/status`

**Purpose:** Check user's Google connection status and authorized services.

**Headers:**
- `Authorization: Bearer <jwt_token>`

**Response:**
```json
{
  "connected": true,
  "granted_scopes": [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly"
  ],
  "email": null,
  "services": {
    "drive": true,
    "gmail": true,
    "calendar": false,
    "contacts": false
  }
}
```

---

### `DELETE /api/v1/google/auth`

**Purpose:** Revoke Google tokens and delete credentials.

**Headers:**
- `Authorization: Bearer <jwt_token>`

**Response:**
- 204 No Content (success)

**Error (404):**
```json
{
  "detail": "No Google credentials found"
}
```

---

## Google API Quota Limits

### Default Quotas (Per Project)

| API | Quota Limit | Unit |
|-----|-------------|------|
| **Google Drive API** | 10,000 requests/day | Per-project |
| **Gmail API** | 10,000 requests/day | Per-project |
| **Google Calendar API** | 10,000 requests/day | Per-project |
| **People API** | 10,000 requests/day | Per-project |

**Per-user limit:** 100 requests/user/100 seconds (burst protection).

### Monitoring (V2 Roadmap)

**Current:** No automated monitoring (manual check in Google Cloud Console).

**V2 Plan:** Add Prometheus metrics + Grafana dashboard:

```python
# Example Prometheus metrics
oauth_requests_total = Counter('google_oauth_requests_total', 'Total OAuth requests', ['service', 'status'])
oauth_rate_limit_errors = Counter('google_oauth_rate_limit_errors', 'Rate limit errors (429)', ['service'])
api_quota_usage = Gauge('google_api_quota_usage', 'API quota usage %', ['api'])
```

**Alerts:**
- Alert when any API exceeds 80% of daily quota
- Alert on 429 (rate limit) errors
- Daily summary of quota usage per API

**Dashboard sections:**
- OAuth success rate (by service)
- Top users by API request volume
- Quota usage trends (7-day rolling average)
- 429 error rate

**Google Cloud Console Monitoring:**
- Navigate to **"APIs & Services" > "Dashboard"**
- Select API (e.g., Google Drive API)
- Click **"Quotas"** tab
- View current usage vs. limit

---

## V2 Roadmap

### V2.1: Service Account Support (Organizational Access)

**Problem:** V1 requires each user to authorize individually. For large orgs, admins want to grant org-wide access once.

**Solution:** Add Service Account pattern (Pattern 2).

**How it works:**
1. **Google Workspace admin** creates a Service Account in Google Cloud Console
2. **Admin delegates domain-wide authority** to Service Account (grants access to all users' data)
3. **EchoMind backend stores Service Account credentials** (JSON key file)
4. **Connectors impersonate users** to access their data (no individual OAuth needed)

**Benefits:**
- One-time setup (admin action only)
- Access to shared organizational resources (Shared Drives, etc.)
- Lower OAuth request volume

**Cons:**
- Requires Google Workspace admin privileges
- Doesn't work with personal gmail.com accounts
- Higher security risk (one compromised key = access to all users)

**Implementation Status:** Planned, no ETA (driven by customer demand).

---

### V2.2: Rate Limit Monitoring & Auto-Throttling

**Problem:** No visibility into API quota usage, risk of hitting limits unexpectedly.

**Solution:** Add Prometheus metrics + Grafana dashboards + auto-throttling.

**Features:**
- **Metrics:** Capture API call volume, errors, quota usage per API/service
- **Dashboard:** Real-time visualization of quota usage, success rates, top users
- **Alerts:** Notify when approaching quota limits (80%, 90%, 95%)
- **Auto-throttling:** When quota usage > 90%, queue requests and rate-limit per-user

**Implementation Status:** Planned for Q2 2026.

---

### V2.3: Customer-Managed OAuth Apps

**Problem:** All customers use EchoMind's shared OAuth app. Some enterprise customers want to use their own OAuth app (for branding, audit trail, quota isolation).

**Solution:** Support customer-provided OAuth credentials.

**How it works:**
1. **Customer creates OAuth app** in their Google Cloud Console
2. **Customer provides credentials** to EchoMind admin (via UI or config)
3. **EchoMind stores per-customer OAuth credentials** in database
4. **Connectors use customer-specific credentials** for OAuth flows

**Benefits:**
- Customer has full control over OAuth app (branding, quotas, audit logs)
- Quota isolation (customer's API calls don't affect others)
- Enables custom redirect URIs (customer's own domain)

**Implementation Status:** Planned for V3.

---

## References

### Official Google Documentation

1. **[Using OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)**
2. **[OAuth 2.0 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)**
3. **[Incremental Authorization](https://developers.google.com/identity/protocols/oauth2/web-server#incrementalAuth)**
4. **[Using OAuth 2.0 for Service Accounts](https://developers.google.com/identity/protocols/oauth2/service-account)**
5. **[Google Drive API Quotas](https://developers.google.com/drive/api/guides/limits)**
6. **[Gmail API Quotas](https://developers.google.com/gmail/api/reference/quota)**

### EchoMind Documentation

- [Google OAuth Setup Guide (Admin)](../setup/google-oauth-setup.md)
- [Google OAuth Limitations (V1)](../setup/google-oauth-limitations.md)
- [Connecting Google Services (User Guide)](../user-guides/connecting-google-services.md)

---

**Last Updated:** 2026-02-09
**Document Version:** 1.0
**Status:** Production (V1)
