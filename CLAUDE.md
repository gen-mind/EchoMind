# EchoMind Development Guidelines

> **IMPORTANT**: This file is automatically loaded by AI assistants. Keep it concise and universally applicable. For task-specific details, see the `agent_docs/` folder.

---

## Project Overview

EchoMind is a **Python-only Agentic RAG** platform. The agent reasons, plans multi-step retrieval, uses tools, and maintains memory.

| Component | Technology |
|-----------|------------|
| Agent Framework | Semantic Kernel |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL |
| API | FastAPI + WebSocket |
| Message Queue | NATS JetStream |
| Auth | Authentik (OIDC) |
| LLM Inference | TGI/vLLM or OpenAI/Anthropic |

### Architecture: Single-Tenant

EchoMind uses **single-tenant architecture** with per-user/group/org vector collections for data isolation.

### Key Domain Concepts

| Entity | Description |
|--------|-------------|
| **Assistant** | AI personality with custom prompts (system_prompt, task_prompt), linked to an LLM |
| **Connector** | Data source connection (Teams, Google Drive, etc.) with sync state |
| **Document** | Ingested content from connectors, chunked and embedded |
| **Chat Session** | Conversation thread between user and an assistant |
| **Agent Memory** | Long-term episodic/semantic memory for personalization |

---

## Mandatory Approved Patterns

### Clean Logging with Emoji Indicators (REQUIRED)

**ALL services MUST use emoji-enhanced logging for visual clarity:**

```python
# Suppress noisy third-party library errors
logging.getLogger('nats.aio.client').setLevel(logging.CRITICAL)
logging.getLogger('nats.aio.transport').setLevel(logging.CRITICAL)

# Use emojis consistently
logger.info("✅ Service connected successfully")
logger.warning("⚠️ Connection failed, retrying...")
logger.info("🔄 Will retry in background...")
logger.error("❌ Operation failed: %s", error)
```

**Standard Emoji Conventions:**
| Emoji | Meaning | Usage |
|-------|---------|-------|
| ✅ | Success | Service connections, successful operations |
| ⚠️ | Warning | Retries, recoverable errors, degraded state |
| ❌ | Error | Failed operations, exceptions |
| 🔄 | Processing | Background tasks, retry loops |
| 🛠️ | Starting | Service initialization |
| 🔌 | Connected | Network connections established |

**Rules:**
1. **Suppress noisy third-party logs** - Set external library loggers to CRITICAL level
2. **Clean output only** - No stack traces from libraries unless critical
3. **Emoji prefix all operational logs** - Makes scanning logs instant
4. **Consistent emoji usage** - Follow the standard conventions above

---

## Critical Rules

### 1. Shared Library - `echomind_lib`

**YOU MUST** import all shared code from `echomind_lib`. Never duplicate code across services.

**Structure:**
```
src/lib/echomind_lib/
├── db/                      # Database access (Postgres, Qdrant, NATS)
│   ├── postgres.py          # SQLAlchemy CRUD operations
│   ├── qdrant.py            # Vector DB operations  
│   ├── nats_subscriber.py   # JetStream consumer
│   └── nats_publisher.py    # JetStream publisher
├── helpers/                 # ALL utility code goes here
│   ├── minio_helper.py      # S3/MinIO file operations
│   ├── device_checker.py    # GPU/CPU detection
│   └── readiness_probe.py   # K8s health checks
└── models/                  # AUTO-GENERATED Pydantic models with protobuf conversion (READ-ONLY)
```

**Import Pattern:**
```python
from echomind_lib.db.postgres import DocumentCRUD, ConnectorCRUD
from echomind_lib.db.nats_subscriber import JetStreamEventSubscriber
from echomind_lib.db.nats_publisher import JetStreamPublisher
from echomind_lib.db.qdrant import QdrantDB
from echomind_lib.helpers.readiness_probe import ReadinessProbe
from echomind_lib.helpers.minio_helper import MinIOHelper
from echomind_lib.helpers.device_checker import DeviceChecker
from echomind_lib.models import SemanticData
```

### 2. Proto Files = Source of Truth (API & Messaging Contracts)

**NEVER** manually create Pydantic data models. All API/messaging models are generated from `src/proto/`:

```
src/proto/
├── public/          # Client-facing API objects (exposed to web/mobile)
├── internal/        # Internal service objects (NATS messages, backend only)
└── common.proto     # Shared types (pagination, enums)
```

**Generated Code Locations:**
| Source | Generated To | Used By |
|--------|--------------|----------|
| `src/proto/public/*.proto` | `echomind_lib/models/public/` | FastAPI routes, React client |
| `src/proto/internal/*.proto` | `echomind_lib/models/internal/` | NATS messages, backend services |
| `src/proto/public/*.proto` | `web/src/gen_types/` | React web client |

**CI Pipeline generates:**
- **Python**: Pydantic models with protobuf conversion → `echomind_lib/models/`
- **TypeScript**: Type definitions → `web/src/gen_types/`

**SQLAlchemy ORM models are separate (by design):**
- SQLAlchemy models live in `echomind_lib/db/models.py`
- They contain DB-only concerns: audit columns, soft deletes, relationships, constraints
- Use `model_validate(orm_obj, from_attributes=True)` to convert ORM → Pydantic for API responses

**Mapping Pattern:**
```python
# Read: ORM → Pydantic (one line)
from echomind_lib.models.public import User as UserRead
user_response = UserRead.model_validate(user_orm, from_attributes=True)

# Create/Update: Pydantic → ORM (explicit mapper, ~15-30 lines per entity)
# See echomind_lib/api/mappers/ for examples
```

### 3. Generated Code is Read-Only

**NEVER** edit files in:
- `echomind_lib/models/` (Python)
- `web/src/gen_types/` (TypeScript)

Regenerate from proto: `make gen-proto`

### 4. Database Audit Columns

**Every table MUST include these audit columns:**

| Column | Type | Description |
|--------|------|-------------|
| `creation_date` | `TIMESTAMP NOT NULL DEFAULT NOW()` | When the row was created |
| `last_update` | `TIMESTAMP` | When the row was last updated (auto-set by trigger) |
| `user_id_last_update` | `UUID REFERENCES users(id)` | User who performed the last update |

**Rules:**
- `creation_date` is auto-set on INSERT, never modified
- `last_update` is auto-set by database trigger on UPDATE
- `user_id_last_update` must be set by the application on every UPDATE
- On row creation, `last_update` and `user_id_last_update` are NULL (creation is not an update)

**Example SQLAlchemy pattern:**
```python
def update_document(self, doc_id: int, updates: dict, user_id: UUID) -> Document:
    updates["user_id_last_update"] = user_id  # Always set on update
    # last_update is handled by database trigger
    ...
```

### 5. Model Layer Separation

**Two model layers exist by design:**

| Layer | Location | Purpose |
|-------|----------|----------|
| **Proto/Pydantic** | `echomind_lib/models/` | API contracts, NATS messages (generated, read-only) |
| **SQLAlchemy ORM** | `echomind_lib/db/models/` | DB persistence, audit columns, relationships |

**Why separate?**
- SQLAlchemy needs DB-only fields: `external_id`, `user_id_last_update`, `deleted_date`
- Proto defines what clients see - no internal fields exposed
- ORM relationships don't belong in API contracts

**Rules:**
1. **Never hand-write Pydantic schemas** - generate from proto
2. **SQLAlchemy models may have extra fields** not in proto (audit, internal)
3. **Use mappers** to convert between layers

**SQLAlchemy ORM models MUST be organized in a `models/` folder with one file per entity:**

```
echomind_lib/db/models/
├── __init__.py          # Re-exports all models
├── base.py              # Shared imports (Base, column types)
├── user.py              # User
├── llm.py               # LLM
├── embedding_model.py   # EmbeddingModel
├── assistant.py         # Assistant
├── connector.py         # Connector
├── document.py          # Document
├── chat_session.py      # ChatSession
├── chat_message.py      # ChatMessage, ChatMessageFeedback, ChatMessageDocument
└── agent_memory.py      # AgentMemory
```

**ORM Organization Rules:**
1. **One entity per file** (related entities like ChatMessage* can share a file)
2. **Use `TYPE_CHECKING`** for forward references to avoid circular imports
3. **`__init__.py` re-exports all models** for backward-compatible imports
4. **Import pattern:** `from echomind_lib.db.models import User, Assistant`

### 6. Service Architecture: Logic & Middleware Separation

**ALL services MUST separate business logic from infrastructure concerns:**

```
src/{service_name}/
├── logic/               # Business logic & domain services
│   ├── exceptions.py    # Domain exceptions
│   └── *_service.py     # Service classes
├── middleware/          # Cross-cutting infrastructure concerns
│   └── error_handler.py # Error handling, logging, etc.
└── [entry_points]       # Service-specific entry points
    ├── routes/          # (API service only) HTTP endpoints
    ├── subscribers/     # (Worker services) NATS subscribers
    └── main.py          # Service initialization
```

#### Universal Layer Responsibilities

| Layer | Responsibility | Contains |
|-------|----------------|----------|
| **`logic/`** | Business logic & domain rules | Services, domain models, business validation |
| **`middleware/`** | Infrastructure & cross-cutting | Error handling, logging, monitoring, protocol adapters |
| **Entry points** | Interface adapters | HTTP routes, NATS subscribers, CLI commands, gRPC handlers |

#### Examples Across Services

**API Service:**
```
src/api/
├── logic/
│   ├── exceptions.py
│   ├── user_service.py
│   ├── assistant_service.py
│   └── connector_service.py
├── middleware/
│   └── error_handler.py       # HTTP error conversion
└── routes/                     # HTTP entry points
    ├── users.py
    └── assistants.py
```

**Semantic Service:**
```
src/semantic/
├── logic/
│   ├── exceptions.py
│   ├── document_processor.py
│   ├── chunking_service.py
│   └── embedding_service.py
├── middleware/
│   └── error_handler.py       # NATS error handling
└── subscribers/                # NATS entry points
    └── document_subscriber.py
```

**Embedder Service:**
```
src/embedder/
├── logic/
│   ├── exceptions.py
│   └── embedding_service.py
├── middleware/
│   └── error_handler.py       # gRPC error handling
└── grpc_server.py             # gRPC entry point
```

#### Entry Points: Thin Adapters

Entry points are thin adapters that delegate to `logic/` services.

```python
# ✅ CORRECT: Thin entry point (API route example)
@router.get("/{user_id}")
async def get_user(user_id: int, db: DbSession) -> User:
    service = UserService(db)
    return await service.get_user_by_id(user_id)

# ✅ CORRECT: Thin entry point (NATS subscriber example)
async def handle_document_message(msg: NATSMessage):
    service = DocumentService(db)
    await service.process_document(msg.document_id)

# ❌ WRONG: Business logic in entry point
@router.get("/{user_id}")
async def get_user(user_id: int, db: DbSession):
    result = await db.execute(...)  # DB queries
    if not result:  # Business logic
        raise HTTPException(...)
    # ... transformation logic
```

#### Logic Services: Domain Operations

Services in `logic/` contain ALL business logic, orchestration, and domain rules.

```python
# logic/user_service.py
class UserService:
    """User business operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_id(self, user_id: int) -> User:
        """Get user with business validation."""
        result = await self.db.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            raise NotFoundError("User", user_id)
        
        return User.model_validate(db_user, from_attributes=True)
```

#### Exception Handling Pattern

1. **Services raise domain exceptions** from `logic/exceptions.py`
2. **Middleware converts to protocol responses** (HTTP, gRPC status, NATS ack/nack)

```python
# logic/exceptions.py - Domain exceptions (shared)
class NotFoundError(DomainError):
    """Resource not found."""
    pass

# middleware/error_handler.py - Protocol-specific conversion
# API service: HTTP conversion
@app.exception_handler(NotFoundError)
async def handle_not_found(req: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"error": exc.message})

# Semantic service: NATS conversion
async def handle_message_error(exc: DomainError, msg: NATSMessage):
    if isinstance(exc, NotFoundError):
        await msg.nak()  # NATS negative acknowledgment
    else:
        await msg.term()  # NATS terminate
```

#### Rules

1. **`logic/` is protocol-agnostic** - No HTTP, gRPC, NATS imports in logic services
2. **Entry points are thin** - Only protocol handling, delegate to `logic/`
3. **One service per domain** - `UserService`, `DocumentService`, `ChunkingService`
4. **Services inject dependencies** - DB sessions, external clients, config
5. **Raise domain exceptions** - Use `NotFoundError`, `ValidationError` from `logic/exceptions.py`
6. **Middleware handles protocols** - Convert domain exceptions to HTTP/gRPC/NATS responses
7. **Services are reusable** - Same `logic/` services used by routes, subscribers, CLI

#### Testing Benefits

Protocol-agnostic logic enables easier testing:

```python
# Unit test logic directly (no HTTP/gRPC needed)
async def test_user_service():
    mock_db = MockSession()
    service = UserService(mock_db)
    user = await service.get_user_by_id(1)
    assert user.email == "test@example.com"

# Integration test with real protocol
async def test_http_endpoint(client: TestClient):
    response = client.get("/api/v1/users/1")
    assert response.status_code == 200
```

#### Migration Path

For existing services with mixed logic:

1. Create `logic/` folder
2. Move domain logic to `*_service.py` files in `logic/`
3. Extract exceptions to `logic/exceptions.py`
4. Refactor entry points to be thin (call services)
5. Move protocol-specific error handling to `middleware/`

### 7. Message Bus Uses Proto

**ALL messages sent to NATS JetStream MUST be serialized as Protocol Buffers.**

```python
# ✅ CORRECT: Serialize as proto
from echomind_lib.models import SemanticData
from echomind_lib.db.nats_publisher import JetStreamPublisher

msg = SemanticData(document_id=123, file_type=FileType.PDF)
await publisher.publish(msg.SerializeToString())

# ❌ WRONG: Never send JSON to message bus
await publisher.publish(json.dumps({"document_id": 123}))
```

### 7. Every Service MUST Have Readiness Probe

**ALL services MUST implement a readiness probe for Kubernetes health checks.**

```python
from echomind_lib.helpers.readiness_probe import ReadinessProbe
import threading

# Start readiness probe server in daemon thread
probe = ReadinessProbe()
threading.Thread(target=probe.start_server, daemon=True).start()

# In your processing loop, call update_last_seen()
probe.update_last_seen()  # Keeps /healthz returning 200
```

---

## Database Schema Pattern

### SQLAlchemy Models (in `echomind_lib/db/`)

**ALL database models MUST follow this pattern:**

```python
from sqlalchemy import Column, BigInteger, TIMESTAMP, Boolean, func, Text, Integer, String, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import enum

Base = declarative_base()


class Status(enum.Enum):
    """Status enum for connectors - define enums as Python enums."""
    READY_TO_PROCESS = "READY_TO_PROCESS"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED_SUCCESSFULLY = "COMPLETED_SUCCESSFULLY"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    DISABLED = "DISABLED"
    UNABLE_TO_PROCESS = "UNABLE_TO_PROCESS"


class Connector(Base):
    __tablename__ = 'connectors'

    id = Column(BigInteger, primary_key=True, default=func.unique_rowid())
    name = Column(String, nullable=False)
    type = Column(String(50), nullable=False)
    connector_specific_config = Column(JSON, nullable=False)  # Use JSON for flexible config
    refresh_freq = Column(BigInteger, nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)      # UUID for user/tenant IDs
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    last_successful_analyzed = Column(TIMESTAMP(timezone=False), nullable=True)
    status = Column(Enum(Status), nullable=True)              # Use SQLAlchemy Enum
    total_docs_analyzed = Column(BigInteger, nullable=False)
    creation_date = Column(TIMESTAMP(timezone=False), nullable=False)  # REQUIRED
    last_update = Column(TIMESTAMP(timezone=False), nullable=True)     # REQUIRED
    deleted_date = Column(TIMESTAMP(timezone=False), nullable=True)    # Soft delete

    def __repr__(self):
        return f"<Connector(id={self.id}, name={self.name}, type={self.type})>"


class Document(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(BigInteger, nullable=True)             # Self-referencing for hierarchy
    connector_id = Column(BigInteger, nullable=False)         # Foreign key to connector
    source_id = Column(Text, nullable=False)                  # External system ID
    url = Column(Text, nullable=True)
    signature = Column(Text, nullable=True)                   # For change detection
    chunking_session = Column(UUID(as_uuid=True), nullable=True)
    analyzed = Column(Boolean, nullable=False, default=False)
    creation_date = Column(TIMESTAMP(timezone=False), nullable=False, default=func.now())
    last_update = Column(TIMESTAMP(timezone=False), nullable=True)

    def __repr__(self):
        return f"<Document(id={self.id}, url={self.url}, analyzed={self.analyzed})>"
```

**Required Fields for ALL Tables:**
- `creation_date` - TIMESTAMP, set on insert
- `last_update` - TIMESTAMP, updated on modification

**Column Type Guidelines:**
| Use Case | Column Type |
|----------|-------------|
| Primary key | `BigInteger` with `func.unique_rowid()` or `Integer` with `autoincrement=True` |
| User/Tenant IDs | `UUID(as_uuid=True)` |
| Flexible config | `JSON` |
| Status fields | `Enum(StatusEnum)` |
| Timestamps | `TIMESTAMP(timezone=False)` |
| Soft delete | `deleted_date` column (nullable TIMESTAMP) |

### CRUD Class Pattern

**Each model gets a corresponding CRUD class:**

```python
from contextlib import contextmanager
from typing import List
from sqlalchemy.exc import OperationalError
import time

from echomind_lib.db.connection_manager import ConnectionManager


def with_retry(func):
    """Decorator for automatic retry with exponential backoff on DB errors."""
    def wrapper(*args, **kwargs):
        retries = 3
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                if i < retries - 1:
                    logger.warning(f"😱 DB retry {i+1}/{retries}: {e}")
                    time.sleep(2 ** i)  # Exponential backoff
                else:
                    raise e
    return wrapper


class DocumentCRUD:
    def __init__(self, connection_string: str):
        self.connection_manager = ConnectionManager(connection_string)

    @contextmanager
    def session_scope(self):
        with self.connection_manager.get_session() as session:
            yield session

    @with_retry
    def insert_document(self, **kwargs) -> int:
        with self.session_scope() as session:
            new_document = Document(**kwargs)
            session.add(new_document)
            session.commit()
            return new_document.id

    @with_retry
    def insert_documents_batch(self, documents: List[Document]) -> List[dict]:
        """Batch insert for efficiency."""
        with self.session_scope() as session:
            session.add_all(documents)
            session.commit()
            for doc in documents:
                session.refresh(doc)  # Get IDs from database
            return [{'id': doc.id, 'url': doc.url} for doc in documents]

    @with_retry
    def select_document(self, document_id: int) -> Document | None:
        if document_id <= 0:
            raise ValueError("ID value must be positive")
        with self.session_scope() as session:
            document = session.query(Document).filter_by(id=document_id).first()
            if document:
                session.expunge(document)  # Detach from session before returning
            return document

    @with_retry
    def update_document(self, document_id: int, **kwargs) -> int:
        if document_id <= 0:
            raise ValueError("ID value must be positive")
        with self.session_scope() as session:
            updated = session.query(Document).filter_by(id=document_id).update(kwargs)
            session.commit()
            return updated

    @with_retry
    def delete_by_document_id(self, document_id: int) -> int:
        if document_id <= 0:
            raise ValueError("ID value must be positive")
        with self.session_scope() as session:
            deleted = session.query(Document).filter_by(id=document_id).delete()
            session.commit()
            return deleted
```

**CRUD Pattern Rules:**
1. **Always use `@with_retry`** decorator on all DB operations
2. **Always validate IDs** - Check `id > 0` before queries
3. **Use `session.expunge()`** - Detach objects before returning from select
4. **Use `session.refresh()`** - Get auto-generated IDs after insert
5. **Batch operations** - Prefer `insert_documents_batch()` over multiple single inserts
6. **Connection pooling** - Use singleton `ConnectionManager` with `pool_size=20`

### Database Migrations

**Use Goose for SQL migrations:**

```
src/migrations/
└── versions/
    └── 20240606162757_add_documents_table.sql
```

**Migration file format:**
```sql
-- +goose Up
-- +goose StatementBegin
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    connector_id BIGINT NOT NULL,
    url TEXT,
    creation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    last_update TIMESTAMP
);
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP TABLE documents;
-- +goose StatementEnd
```

---

## Directory Structure

```
echomind/
├── src/
│   ├── api/                 # FastAPI application
│   ├── agent/               # Semantic Kernel agent
│   ├── services/            # NATS consumer workers
│   │   ├── embedder/        # Text → Vector embeddings (gRPC)
│   │   ├── semantic/        # Document analysis & chunking (NATS)
│   │   ├── search/          # Vector search service (gRPC)
│   │   ├── transformer/     # Semantic text splitting (gRPC)
│   │   ├── voice/           # Audio → Text via Whisper (NATS)
│   │   └── vision/          # Image → Text via BLIP+OCR (NATS)
│   ├── connectors/          # Data source connectors
│   ├── proto/               # Protocol Buffer definitions (SOURCE OF TRUTH)
│   │   ├── public/          # Client-facing API objects
│   │   └── internal/        # Internal service objects
│   └── lib/echomind_lib/    # SHARED LIBRARY (see Critical Rules)
│       ├── db/              # Database access helpers
│       ├── helpers/         # Utility helpers (MinIO, device, probe)
│       └── models/          # AUTO-GENERATED Pydantic models (READ-ONLY)
├── web/                     # React web client
│   └── src/
│       └── gen_types/       # AUTO-GENERATED TypeScript types from proto
├── deployment/
├── config/
├── tests/
└── agent_docs/              # Task-specific AI context files
```

---

## Python Coding Standards

### Type Hints, Pydantic, and Documentation

**ALL code MUST use type hints and docstrings for IntelliSense support.**

```python
from typing import Any
from pydantic import BaseModel, Field


class DocumentRequest(BaseModel):
    """Request model for document processing."""
    document_id: int = Field(..., description="Unique document identifier", gt=0)
    url: str | None = Field(None, description="Source URL of the document")
    file_type: str = Field(..., description="Type of file (PDF, DOCX, etc.)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DocumentResponse(BaseModel):
    """Response model for document processing."""
    id: int
    chunks_created: int
    processing_time_ms: float
    success: bool


def process_document(
    document: DocumentRequest,
    model_name: str = "default",
    batch_size: int = 32
) -> DocumentResponse:
    """
    Process a document and create vector embeddings.

    Args:
        document: The document request containing ID, URL, and metadata.
        model_name: Name of the embedding model to use.
        batch_size: Number of chunks to process in parallel.

    Returns:
        DocumentResponse with processing results.

    Raises:
        DocumentProcessingError: If document cannot be processed.
        ValueError: If document_id is invalid.
    """
    # Implementation here
    pass


async def fetch_documents(
    connector_id: int,
    limit: int = 100,
    offset: int = 0
) -> list[DocumentResponse]:
    """
    Fetch documents from a connector.

    Args:
        connector_id: ID of the connector to fetch from.
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.

    Returns:
        List of DocumentResponse objects.
    """
    pass
```

**Rules:**
1. **ALL function parameters MUST have type hints**
2. **ALL function return types MUST be specified**
3. **ALL functions/methods MUST have docstrings** with Args, Returns, Raises sections
4. **Use Pydantic `BaseModel`** for all request/response objects
5. **Use `Field()`** with descriptions for Pydantic models
6. **Use `T | None`** for nullable fields (modern Python 3.10+ syntax)
7. **Use built-in generics** (`list`, `dict`, `set`) instead of `typing` module aliases

**Pydantic v2 for Config/Settings:**
```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Service configuration loaded from environment."""
    log_level: str = Field("INFO", description="Logging level")
    grpc_port: int = Field(50051, description="gRPC server port")
    nats_url: str = Field("nats://localhost:4222", description="NATS server URL")
    model_cache_limit: int = Field(2, gt=0, description="Max models in cache")

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDER_",  # Reads EMBEDDER_LOG_LEVEL, etc.
        env_file=".env",
        env_file_encoding="utf-8",
    )
```

**NEVER DO THIS:**
```python
# ❌ WRONG: No type hints
def process(doc, model):
    return result

# ❌ WRONG: No docstring
def calculate_embeddings(texts: list[str]) -> list[list[float]]:
    return model.encode(texts)

# ❌ WRONG: Using dict instead of Pydantic
def create_response(id, chunks):
    return {"id": id, "chunks": chunks}  # Use Pydantic model instead

# ❌ WRONG: Using deprecated typing aliases
from typing import List, Dict, Optional
def old_style(items: List[str]) -> Optional[Dict[str, int]]: ...

# ❌ WRONG: Using deprecated Pydantic v1 Config class
class BadSettings(BaseSettings):
    class Config:  # DEPRECATED in Pydantic v2
        env_prefix = "MY_"
```

### Exception Handling

**Pattern 1: Catch, Log, and Re-raise with Context**
```python
try:
    result = await process_document(doc)
except DocumentProcessingError as e:
    logger.error(f"❌ Failed to process document {doc.id}: {e}")
    raise  # Re-raise original exception
except Exception as e:
    logger.exception(f"❌ Unexpected error processing document {doc.id}")
    raise DocumentProcessingError(f"Processing failed: {doc.id}") from e
```

**Pattern 2: Chain Exceptions with `from e`**
```python
try:
    data = fetch_from_api(url)
except RequestException as e:
    raise DataFetchError(f"Failed to fetch from {url}") from e
```

**Pattern 3: Graceful Degradation**
```python
try:
    result = await primary_service.call()
except ServiceUnavailableError:
    logger.warning("😱 Primary service unavailable, using fallback")
    result = await fallback_service.call()
```

**NEVER DO THIS:**
```python
# ❌ WRONG: Swallowing exceptions
try:
    risky_operation()
except Exception:
    pass  # NEVER silently ignore exceptions

# ❌ WRONG: Bare except
try:
    something()
except:  # Too broad, catches SystemExit, KeyboardInterrupt
    handle()

# ❌ WRONG: Losing traceback
try:
    something()
except SomeError as e:
    raise NewError("message")  # Missing `from e`
```

### Logging

**Configuration (at module top, before other imports):**
```python
import logging
import os
from dotenv import load_dotenv

load_dotenv()

log_level_str = os.getenv('SERVICE_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
log_format = os.getenv('LOG_FORMAT', '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s')

logging.basicConfig(level=log_level, format=log_format)
logger = logging.getLogger(__name__)
```

**Log Levels:**
| Level | Use For |
|-------|---------|
| `DEBUG` | Detailed diagnostic info (dev only) |
| `INFO` | Service lifecycle, successful operations |
| `WARNING` | Recoverable issues, retries, fallbacks |
| `ERROR` | Operation failures (with context) |
| `CRITICAL` | System-wide failures requiring immediate attention |

**Emoji Indicators for Quick Visual Parsing:**
```python
logger.info("🛠️ Service starting...")
logger.info("🔌 Connected to NATS")
logger.info("🔥 Processing document %s", doc_id)
logger.info("⏰ Processed in %.2f seconds", elapsed)
logger.info("👍 Message acknowledged")
logger.info("✅ Operation completed successfully")
logger.warning("😱 Retry attempt %d/%d", attempt, max_retries)
logger.error("❌ Failed to process: %s", error_message)
logger.critical("💀 Fatal error, service shutting down")
```

**Structured Logging with Extra Fields:**
```python
logger.info("Document processed", extra={
    "document_id": doc.id,
    "chunks_created": len(chunks),
    "processing_time_ms": elapsed_ms
})
```

**Consider `structlog` for Production:**

For production systems requiring structured JSON logs, consider using `structlog`:

```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Structured logging with automatic JSON output
logger.info("document_processed", 
    document_id=doc.id, 
    chunks=len(chunks),
    elapsed_ms=elapsed_ms
)
# Output: {"event": "document_processed", "document_id": 123, "chunks": 5, "elapsed_ms": 42.5, "timestamp": "2024-01-20T..."}
```

Benefits over standard logging:
- Native JSON output for log aggregation (ELK, Grafana Loki)
- Automatic context binding
- Better structured data handling
- Colorized console output for development

**NEVER DO THIS:**
```python
# ❌ WRONG: Using print for logging
print(f"Processing {doc_id}")

# ❌ WRONG: Logging sensitive data
logger.info(f"User authenticated with password: {password}")

# ❌ WRONG: f-strings in logger (use % formatting for lazy evaluation)
logger.debug(f"Processing {expensive_computation()}")  # Always evaluates
logger.debug("Processing %s", expensive_computation())  # Only evaluates if DEBUG

# ❌ WRONG: Catching exception without logging
try:
    something()
except Exception as e:
    raise CustomError("failed")  # Lost the original error details
```

### Async/Await Patterns

**Service Main Loop with Circuit Breaker:**
```python
async def main():
    probe = ReadinessProbe()
    threading.Thread(target=probe.start_server, daemon=True).start()
    
    while True:
        logger.info("🛠️ Service starting...")
        try:
            subscriber = JetStreamEventSubscriber(
                nats_url=nats_url,
                stream_name=stream_name,
                subject=subject,
                proto_message_type=MessageType
            )
            subscriber.set_event_handler(event_handler)
            await subscriber.connect_and_subscribe()
            
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down due to keyboard interrupt")
            break
        except Exception as e:
            logger.exception("💀 Fatal error, restarting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
```

**Event Handler Pattern:**
```python
async def event_handler(msg):
    start_time = time.time()
    try:
        data = MessageType()
        data.ParseFromString(msg.data)
        
        # Update readiness probe
        ReadinessProbe().update_last_seen()
        
        # Process the message
        result = await process(data)
        
        # Acknowledge on success
        await msg.ack_sync()
        logger.info("👍 Message acknowledged, processed %d items", result)
        
    except Exception as e:
        logger.error("❌ Failed to process message: %s", e)
        # Don't ack - message will be redelivered
    finally:
        elapsed = time.time() - start_time
        logger.info("⏰ Total processing time: %.2f seconds", elapsed)
```

**NEVER DO THIS:**
```python
# ❌ WRONG: Blocking call in async function
async def bad_async():
    time.sleep(5)  # Blocks the event loop!
    
# ✅ CORRECT:
async def good_async():
    await asyncio.sleep(5)

# ❌ WRONG: Long-running loop without yielding
async def bad_loop():
    while True:
        process_item()  # Never yields to event loop
        
# ✅ CORRECT:
async def good_loop():
    while True:
        await process_item()
        await asyncio.sleep(0)  # Yield to event loop
```

### Singleton Pattern

**For Connection Managers and Probes:**
```python
class ConnectionManager:
    _instance = None

    def __new__(cls, connection_string=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(connection_string)
        return cls._instance
    
    def _initialize(self, connection_string):
        self._engine = create_engine(
            connection_string,
            pool_size=20,
            max_overflow=0
        )
        self._session_factory = scoped_session(
            sessionmaker(bind=self._engine)
        )
```

### Context Manager for Database Sessions

```python
from contextlib import contextmanager

@contextmanager
def session_scope(self):
    session = self._session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### Retry with Exponential Backoff

```python
import functools
import time
from sqlalchemy.exc import OperationalError

def with_retry(max_retries=3, base_delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning("😱 Retry %d/%d after %.1fs: %s", 
                                      attempt + 1, max_retries, delay, e)
                        time.sleep(delay)
                    else:
                        logger.error("❌ All %d retries failed", max_retries)
                        raise
        return wrapper
    return decorator
```

### ML Model Caching Pattern (Thread-Safe with LRU Eviction)

**For services that load ML models (embedder, transformer, voice, vision):**

```python
import os
import threading
from typing import Dict, List
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

class SentenceEncoder:
    # Validate environment variables at class level initialization
    _cache_limit: int = int(os.getenv('MODEL_CACHE_LIMIT', 1))
    _local_model_dir: str = os.getenv('LOCAL_MODEL_PATH', 'models')
    
    # Fail fast if config is invalid
    if _cache_limit <= 0:
        raise ValueError("MODEL_CACHE_LIMIT must be an integer greater than 0")
    
    _local_model_dir = os.path.abspath(_local_model_dir)
    if not os.path.isdir(_local_model_dir):
        raise ValueError(f"LOCAL_MODEL_PATH '{_local_model_dir}' is not a valid directory")

    # Thread lock for thread-safe access to the cache
    _lock: threading.Lock = threading.Lock()
    
    # Dictionary to store cached model instances (acts as LRU cache)
    _model_cache: Dict[str, SentenceTransformer] = {}

    @classmethod
    def _load_model(cls, model_name: str) -> SentenceTransformer:
        """Load from local directory if available, otherwise download from HuggingFace."""
        model_path: str = os.path.join(cls._local_model_dir, model_name)
        
        if not os.path.exists(model_path) or not os.listdir(model_path):
            logger.info(f"{model_name} not found locally, downloading from HuggingFace...")
            try:
                model = SentenceTransformer(model_name)
                model.save(model_path)
                logger.info(f"{model_name} saved locally at {model_path}")
            except Exception as e:
                logger.error(f"❌ {model_name} failed to download: {e}")
                raise
        else:
            logger.info(f"Loading {model_name} from local directory...")
        
        return SentenceTransformer(model_path)

    @classmethod
    def _get_model(cls, model_name: str) -> SentenceTransformer:
        """Get model from cache or load it. Manages cache size with LRU eviction."""
        with cls._lock:
            # Return cached model if available
            if model_name in cls._model_cache:
                logger.info(f"Using cached model: {model_name}")
                return cls._model_cache[model_name]

            # Evict oldest model if cache limit reached
            if len(cls._model_cache) >= cls._cache_limit:
                oldest_model: str = next(iter(cls._model_cache))
                logger.info(f"Unloading model: {oldest_model}")
                del cls._model_cache[oldest_model]

            # Load and cache the new model
            logger.info(f"Loading model: {model_name}")
            model = cls._load_model(model_name)
            cls._model_cache[model_name] = model
            return model

    @classmethod
    def embed(cls, text: str, model_name: str) -> List[float]:
        """Encode single text."""
        model = cls._get_model(model_name)
        return model.encode(text).tolist()

    @classmethod
    def embed_batch(cls, texts: List[str], model_name: str) -> List[List[float]]:
        """Encode batch of texts (more efficient than single calls)."""
        model = cls._get_model(model_name)
        return [embedding.tolist() for embedding in model.encode(texts, batch_size=len(texts))]
```

**Key Patterns:**
- **Class-level env validation** - Fail fast at import time if config is invalid
- **Thread-safe cache** - Use `threading.Lock()` for concurrent access
- **LRU eviction** - Remove oldest model when cache limit reached
- **Local-first loading** - Check local directory before downloading from HuggingFace
- **Batch processing** - Always prefer `embed_batch()` over multiple `embed()` calls

**Environment Variables:**
```bash
MODEL_CACHE_LIMIT=2        # Max models to keep in memory
LOCAL_MODEL_PATH=/models   # Directory for cached model files
```

### Device Checker Pattern (GPU/CPU Detection)

**ALL ML services MUST log available compute device at startup:**

```python
import torch
import logging

class DeviceChecker:
    logger = logging.getLogger(__name__)

    @staticmethod
    def check_device():
        DeviceChecker.logger.info(f"🤖 PyTorch version: {torch.__version__}")

        # Check for NVIDIA GPU (CUDA)
        cuda_available = torch.cuda.is_available()
        
        # Check for Apple Silicon GPU (MPS)
        mps_available = torch.backends.mps.is_available()

        # Determine device priority: CUDA > MPS > CPU
        if cuda_available:
            device = "cuda"
        elif mps_available:
            device = "mps"
        else:
            device = "cpu"

        DeviceChecker.logger.info(f"🤖 Using device: {device}")
        
        # Verify device works
        x = torch.rand(size=(3, 4)).to(device)
        return device
```

**Usage in service startup:**
```python
def serve():
    server = grpc.server(...)
    server.start()
    logger.info(f"👂 Service listening on port {grpc_port}")
    DeviceChecker.check_device()  # MUST call after server starts
    server.wait_for_termination()
```

---

## Service Design Patterns

### gRPC Service (e.g., embedder, search, transformer)

```python
import time
import os
import grpc
from concurrent import futures
import logging
from dotenv import load_dotenv

from echomind_lib.models import EmbedServiceServicer, add_EmbedServiceServicer_to_server
from echomind_lib.models import EmbedResponse, EmbedResponseItem
from echomind_lib.helpers.device_checker import DeviceChecker

load_dotenv()

# Logging config at top
log_level_str = os.getenv('EMBEDDER_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
log_format = os.getenv('EMBEDDER_LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=log_level, format=log_format)
logger = logging.getLogger(__name__)

grpc_port = os.getenv('EMBEDDER_GRPC_PORT', '50051')


class EmbedServicer(EmbedServiceServicer):
    def GetEmbedding(self, request, context):
        start_time = time.time()
        try:
            logger.info(f"📥 Incoming request for {len(request.contents)} entities")
            logger.debug(f"📥 Request details: {request}")
            
            # Validate request
            if not request.contents:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "contents cannot be empty")
            
            # Process request
            embed_response = EmbedResponse()
            encoded_data = SentenceEncoder.embed_batch(texts=request.contents, model_name=request.model)
            
            for content, vector in zip(request.contents, encoded_data):
                response_item = EmbedResponseItem(content=content, vector=vector)
                embed_response.embeddings.append(response_item)
            
            logger.info("✅ Request processed successfully")
            return embed_response
        except grpc.RpcError:
            raise  # Re-raise gRPC errors (like abort)
        except ValueError as e:
            logger.error(f"❌ Validation error: {e}")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
        except Exception as e:
            logger.exception("❌ Request failed")
            context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {str(e)}")
        finally:
            elapsed = time.time() - start_time
            logger.info(f"⏰ Total elapsed time: {elapsed:.2f} seconds")


def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(),
        options=[
            ('grpc.max_send_message_length', 1024 * 1024 * 1024),  # 1 GB
            ('grpc.max_receive_message_length', 1024 * 1024 * 1024)  # 1 GB
        ]
    )
    add_EmbedServiceServicer_to_server(EmbedServicer(), server)
    server.add_insecure_port(f"0.0.0.0:{grpc_port}")
    server.start()
    logger.info(f"👂 Service listening on port {grpc_port}")
    DeviceChecker.check_device()  # Log GPU/CPU availability
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
```

### NATS Consumer Service (e.g., semantic, voice, vision)

```python
import asyncio
import logging
import os
import threading
import time
from dotenv import load_dotenv
from nats.aio.msg import Msg

from echomind_lib.db.postgres import DocumentCRUD, ConnectorCRUD
from echomind_lib.models import SemanticData
from echomind_lib.helpers.device_checker import DeviceChecker
from echomind_lib.helpers.readiness_probe import ReadinessProbe
from echomind_lib.db.nats_subscriber import JetStreamEventSubscriber

load_dotenv()

# Logging config
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
log_format = os.getenv('LOG_FORMAT', '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s')
logging.basicConfig(level=log_level, format=log_format)
logger = logging.getLogger(__name__)

# NATS config from env
nats_url = os.getenv('NATS_CLIENT_URL', 'nats://127.0.0.1:4222')
stream_name = os.getenv('NATS_CLIENT_STREAM_NAME', 'semantic')
stream_subject = os.getenv('NATS_CLIENT_STREAM_SUBJECT', 'semantic_activity')
ack_wait = int(os.getenv('NATS_CLIENT_ACK_WAIT', '3600'))
max_deliver = int(os.getenv('NATS_CLIENT_MAX_DELIVER', '3'))


async def event_handler(msg: Msg):
    """Process incoming NATS message. Messages are proto-serialized."""
    start_time = time.time()
    try:
        logger.info("🔥 Starting processing...")
        
        # Parse proto message
        data = SemanticData()
        data.ParseFromString(msg.data)
        
        # Process the data
        result = await process(data)
        
        if result is not None:
            await msg.ack_sync()
            logger.info(f"👍 Message acknowledged, processed {result} items")
        else:
            await msg.nak()
            logger.error(f"❌ Processing failed for document_id {data.document_id}")
            
    except Exception as e:
        logger.error(f"❌ Failed to process message: {e}")
        if msg:
            await msg.nak()
    finally:
        elapsed = time.time() - start_time
        logger.info(f"⏰ Total processing time: {elapsed:.2f} seconds")


async def main():
    # REQUIRED: Start readiness probe for K8s health checks
    readiness_probe = ReadinessProbe()
    threading.Thread(target=readiness_probe.start_server, daemon=True).start()
    
    while True:
        logger.info("🛠️ Service starting...")
        try:
            DeviceChecker.check_device()
            
            subscriber = JetStreamEventSubscriber(
                nats_url=nats_url,
                stream_name=stream_name,
                subject=stream_subject,
                ack_wait=ack_wait,
                max_deliver=max_deliver,
                proto_message_type=SemanticData
            )
            subscriber.set_event_handler(event_handler)
            await subscriber.connect_and_subscribe()
            
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down due to keyboard interrupt")
            break
        except Exception as e:
            logger.exception(f"💀 Fatal error: {e}. Restarting in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Environment Configuration

### Environment Variable Naming Convention

**ALL environment variables MUST follow the pattern: `{SERVICE_NAME}_{PARAMETER_NAME}`**

Where:
- `{SERVICE_NAME}` is the service name or short name (e.g., `API`, `EMBEDDER`, `SEMANTIC`)
- `{PARAMETER_NAME}` is the configuration parameter in UPPER_SNAKE_CASE

**Examples:**
```bash
# API Service
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false
API_DATABASE_URL=postgresql://...
API_REDIS_HOST=localhost

# Embedder Service
EMBEDDER_GRPC_PORT=50051
EMBEDDER_LOG_LEVEL=INFO
EMBEDDER_MODEL_CACHE_LIMIT=2

# Semantic Service
SEMANTIC_LOG_LEVEL=INFO
SEMANTIC_NATS_URL=nats://localhost:4222
```

**Pydantic Settings Implementation:**
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="{SERVICE_NAME}_",  # e.g., "API_", "EMBEDDER_"
        env_file=".env",
        env_file_encoding="utf-8",
    )
```

**Rules:**
1. Every service-specific `.env.example` MUST use the service prefix
2. The prefix MUST match the service name or its standard abbreviation
3. All parameters for a service share the same prefix

**Loading Pattern:**
```python
from dotenv import load_dotenv
load_dotenv()

# Use service-specific prefix
log_level = os.getenv('EMBEDDER_LOG_LEVEL', 'INFO')
grpc_port = os.getenv('EMBEDDER_GRPC_PORT', '50051')
```

---

## Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Services | `echomind-{name}` | `echomind-embedder` |
| ConfigMaps | `{service}-srv`, `{service}-cli` | `embedder-srv` |
| Python packages | `snake_case` | `echomind_lib` |
| Classes | `PascalCase` | `DocumentCRUD` |
| Functions/methods | `snake_case` | `process_document` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Proto packages | `com.echomind.v1` | `package com.echomind.v1;` |

---

## Ports

| Service Type | Port |
|--------------|------|
| gRPC | 50051 |
| HTTP/API | 8080 |
| Health check | 8080 (`/healthz`) |

---

## Testing

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_event_handler():
    mock_msg = AsyncMock()
    mock_msg.data = SemanticData(document_id=123).SerializeToString()
    
    with patch('module.process') as mock_process:
        mock_process.return_value = 5
        await event_handler(mock_msg)
        
    mock_msg.ack_sync.assert_called_once()
```

---

## File Processing Pipeline

```
FileType.PDF/DOC/XLS → semantic service → pymupdf4llm → markdown → chunks → embeddings
FileType.URL         → semantic service → BS4/Selenium spider → text → chunks → embeddings  
FileType.YT          → semantic service → youtube_transcript_api → text → chunks → embeddings
FileType.MP4/WAV     → voice service → Whisper → transcript → semantic service
FileType.JPEG/PNG    → vision service → BLIP + OCR → description → semantic service
```

---

## Quick Reference

### Start a New Service
1. Create `src/services/{name}/{name}_service.py`
2. Import ALL shared code from `echomind_lib` (db, helpers, models)
3. Define proto message in `src/proto/internal/`
4. Regenerate proto: `make gen-proto`
5. **Add ReadinessProbe** (REQUIRED for K8s)
6. Create Dockerfile
7. Add to docker-compose

### Add a New Proto Message
1. Edit/create `.proto` file in `src/proto/`
2. Run `make gen-proto`
3. Python: Import from `echomind_lib.models`
4. TypeScript: Import from `@/gen_types`

### Add a New Helper
1. Create file in `src/lib/echomind_lib/helpers/`
2. Export from `echomind_lib.helpers`
3. Import in services: `from echomind_lib.helpers.my_helper import MyHelper`

### Debug a Service
1. Set `SERVICE_LOG_LEVEL=DEBUG`
2. Check `/healthz` endpoint (readiness probe)
3. Check NATS dashboard for message flow
4. Check Grafana for metrics

---

## Dependency Management - Per-Service pyproject.toml

Each service has its own `pyproject.toml` that depends on `echomind_lib`:

```
src/
├── echomind_lib/
│   └── pyproject.toml    # Shared library - ALL version pins here
├── api/
│   └── pyproject.toml    # API service - depends on echomind_lib
├── agent/
│   └── pyproject.toml    # Agent service - depends on echomind_lib
└── worker/
    └── pyproject.toml    # Worker service - depends on echomind_lib
```

**Rules:**
1. `echomind_lib/pyproject.toml` contains ALL shared dependencies with **pinned versions**
2. Each service's `pyproject.toml` depends on `echomind_lib` + service-specific deps
3. Version pins in `echomind_lib` ensure compatibility for single-container deployment
4. When adding a new service, create `src/<service>/pyproject.toml` that depends on `echomind_lib`

**Installation:**
```bash
# Install shared library + dev tools
cd src/echomind_lib && pip install -e ".[dev]"

# Install a specific service
cd src/api && pip install -e .
```

---

## Code Quality Rules

### TODO Comments for Incomplete Code

**When code is incomplete or missing implementation, MUST add a TODO comment:**

```python
# TODO: Implement actual LLM connection test
return TestLLMResponse(success=True, message="Not yet implemented")

# TODO: Embed query using active embedding model
# TODO: Search Qdrant for relevant chunks
```

**Never leave incomplete code without a TODO marker.**

### No Unused Code

**Never add:**
- Imports that aren't used
- Functions that aren't called
- Dependencies that aren't imported
- Dead code or commented-out code blocks

**Keep requirements minimal** - only add packages that are actually imported in the codebase.

### Unit Tests Required

**When creating new functions, methods, or classes, MUST add corresponding unit tests.**

```python
# src/echomind_lib/helpers/my_helper.py
def calculate_something(value: int) -> int:
    return value * 2

# tests/helpers/test_my_helper.py
import pytest
from echomind_lib.helpers.my_helper import calculate_something

def test_calculate_something():
    assert calculate_something(5) == 10
    assert calculate_something(0) == 0
    assert calculate_something(-3) == -6
```

**Test file location mirrors source structure:**
- Source: `src/echomind_lib/helpers/my_helper.py`
- Test: `tests/helpers/test_my_helper.py`

---

## References

- `docs/architecture.md` - System architecture
- `docs/api-spec.md` - API specification
- `agent_docs/` - Task-specific context files
