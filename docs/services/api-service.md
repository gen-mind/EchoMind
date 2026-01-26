# API Service

> **Service:** `echomind-api`
> **Protocol:** HTTP/WebSocket
> **Port:** 8080

---

## What It Does

The API Service is the **gateway** for all client interactions. It handles:

- REST API endpoints for CRUD operations
- WebSocket connections for real-time chat streaming
- JWT token validation (Authentik OIDC)
- Request routing to backend services
- Serving the React web client (static files)

---

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph Clients
        WEB[Web App]
        CLI[API Client]
        BOT[Bot Plugin]
    end

    subgraph API["echomind-api"]
        AUTH[Auth Middleware]
        REST[REST Routes]
        WS[WebSocket Handler]
        STATIC[Static Files]
    end

    subgraph Backend
        SEARCH[echomind-search<br/>gRPC]
        DB[(PostgreSQL)]
    end

    WEB & CLI & BOT --> AUTH
    AUTH --> REST & WS & STATIC
    REST --> DB
    WS --> SEARCH
    SEARCH --> WS
```

### Request Flow

1. Client sends request with JWT token
2. Auth middleware validates token with Authentik
3. Request routed to appropriate handler
4. For queries: Forward to echomind-search via gRPC
5. For CRUD: Direct database access
6. Response returned to client

### WebSocket Streaming

```mermaid
sequenceDiagram
    participant C as Client
    participant API as echomind-api
    participant S as echomind-search

    C->>API: WS Connect + JWT
    API->>API: Validate token
    API-->>C: Connected

    C->>API: chat.start {query}
    API->>S: SearchRequest (gRPC stream)

    loop Streaming
        S-->>API: Token
        API-->>C: generation.token
    end

    S-->>API: Complete
    API-->>C: generation.complete
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI |
| WebSocket | Starlette WebSocket |
| Auth | python-jose (JWT), httpx (OIDC) |
| Database | SQLAlchemy async |
| gRPC Client | grpcio-tools |
| Static Files | FastAPI StaticFiles |

---

## Database Tables Used

| Table | Operations | Reference |
|-------|------------|-----------|
| `users` | Read, Update | [DB Schema](../db-schema.md#users) |
| `connectors` | CRUD | [DB Schema](../db-schema.md#connectors) |
| `documents` | Read, Delete | [DB Schema](../db-schema.md#documents) |
| `assistants` | CRUD | [DB Schema](../db-schema.md#assistants) |
| `llms` | CRUD | [DB Schema](../db-schema.md#llms) |
| `embedding_models` | Read, Update | [DB Schema](../db-schema.md#embedding_models) |
| `chat_sessions` | CRUD | [DB Schema](../db-schema.md#chat_sessions) |
| `chat_messages` | Read, Create | [DB Schema](../db-schema.md#chat_messages) |

---

## Proto Definitions Used

| Proto | Usage |
|-------|-------|
| `SearchRequest` | gRPC call to search service |
| `SearchResponse` | gRPC response from search |
| All public protos | API response serialization |

See [Proto Definitions](../proto-definitions.md)

---

## NATS Messaging

**This service does NOT use NATS.** All communication is synchronous:
- REST for CRUD operations
- gRPC for search queries
- WebSocket for streaming responses

For manual sync trigger (`POST /connectors/{id}/sync`), the API could optionally publish directly to NATS, bypassing the orchestrator.

---

## Service Structure

```
src/api/
├── main.py                 # FastAPI app entry
├── routes/
│   ├── users.py
│   ├── connectors.py
│   ├── documents.py
│   ├── assistants.py
│   ├── llms.py
│   ├── embedding_models.py
│   └── chat.py
├── websocket/
│   ├── handler.py          # WS connection manager
│   └── protocol.py         # Message types
├── middleware/
│   ├── auth.py             # JWT validation
│   ├── error_handler.py    # Exception → HTTP response
│   └── cors.py
├── logic/
│   ├── user_service.py
│   ├── connector_service.py
│   └── ...
└── config.py
```

---

## Configuration

```bash
# Server
API_HOST=0.0.0.0
API_PORT=8080

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/echomind

# Auth
AUTHENTIK_ISSUER=https://auth.example.com/application/o/echomind/
AUTHENTIK_CLIENT_ID=echomind-api
AUTHENTIK_JWKS_URL=https://auth.example.com/application/o/echomind/jwks/

# Search Service (gRPC)
SEARCH_GRPC_HOST=echomind-search
SEARCH_GRPC_PORT=50051

# Static Files (React build)
STATIC_FILES_PATH=/app/web/dist
```

---

## API Endpoints Summary

See [API Specification](../api-spec.md) for full details.

| Resource | Endpoints |
|----------|-----------|
| Users | `GET/PUT /users/me`, `GET /users` |
| Connectors | CRUD + `POST /{id}/sync` |
| Documents | `GET`, `DELETE`, `GET /search` |
| Assistants | CRUD |
| LLMs | CRUD + `POST /{id}/test` |
| Embedding Models | `GET`, `POST`, `PUT /{id}/activate` |
| Chat | Sessions CRUD, Messages read |
| WebSocket | `WS /ws/chat` |

---

## Health Check

```bash
GET /healthz

# Response
{
  "status": "healthy",
  "database": "connected",
  "search_service": "connected"
}
```

---

## Unit Testing (MANDATORY)

All service logic MUST have unit tests. See [Testing Standards](../../.claude/rules/testing.md).

### Test Location

```
tests/unit/services/
├── test_user_service.py
├── test_assistant_service.py
├── test_connector_service.py
├── test_chat_service.py
└── ...
```

### What to Test

| Component | Test Coverage |
|-----------|---------------|
| Service classes | All public methods |
| Exception handling | NotFoundError, ValidationError, etc. |
| Business logic | Validation, transformations |

### Example

```python
# tests/unit/services/test_user_service.py
class TestUserService:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return UserService(mock_db)

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, service, mock_db):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_user_by_id(999)
```

### Minimum Coverage

- **70%** for service classes
- **80%** for utility functions

---

## References

- [API Specification](../api-spec.md) - Full endpoint documentation
- [Architecture](../architecture.md) - System overview
- [Proto Definitions](../proto-definitions.md) - Message schemas
