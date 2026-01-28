# EchoMind Database Schema

> PostgreSQL 15+ schema for the EchoMind Agentic RAG platform.

**Schema file:** [`src/db-schema/schema.sql`](../src/db-schema/schema.sql)

## Architecture

- **Single-tenant** deployment
- **Per-user/group/org** vector collections in Qdrant for data isolation
- **Soft deletes** via `deleted_date` column where applicable

---

## Model Architecture Decision

### Proto + SQLAlchemy + Pydantic Separation

EchoMind uses a **pragmatic separation** between contract models and persistence models:

| Layer | Source of Truth | Purpose |
|-------|-----------------|---------|
| **Proto** (`src/proto/`) | API & messaging contracts | Defines public API schemas and internal NATS message formats |
| **SQLAlchemy** (`echomind_lib/db/models.py`) | Database persistence | Defines DB schema, constraints, relationships, audit columns |
| **Generated Pydantic** (`echomind_lib/models/`) | Validation & serialization | Auto-generated from Proto for FastAPI request/response |

### Why Two Model Layers?

**SQLAlchemy models contain DB-only concerns:**
- Audit columns (`user_id_last_update`, `creation_date`, `last_update`)
- Soft delete columns (`deleted_date`)
- Internal fields (`external_id` for Authentik sync)
- ORM relationships (foreign keys, back_populates)
- Database constraints and indexes

**Proto/Pydantic models define contracts:**
- Public API request/response schemas
- Internal service-to-service message formats (NATS/JetStream)
- No DB-specific fields exposed

### Mapping Strategy

**Read (DB → API):** Use Pydantic v2 ORM mode
```python
from echomind_lib.models.public import User as UserRead

def orm_to_read(user_orm) -> UserRead:
    return UserRead.model_validate(user_orm, from_attributes=True)
```

**Create/Update (API → DB):** Explicit mapper functions (~15-30 lines per entity)
- Apply only present fields for partial updates
- Set audit columns (`last_update`, `user_id_last_update`)
- Handle field transformations

### Benefits

- ✅ **Proto is the contract source of truth** - no hand-written Pydantic schemas
- ✅ **No drift risk** - API schemas are generated, not manually maintained
- ✅ **Public/internal separation** - prevents accidental field leakage
- ✅ **SQLAlchemy remains flexible** - can include DB-only columns and relationships
- ✅ **NATS protobuf unchanged** - `pb.SerializeToString()` / `pb.ParseFromString()`

### Trade-offs

- ⚠️ SQLAlchemy models maintained separately (by design)
- ⚠️ Small mapper functions needed for Create/Update operations
- ⚠️ DB-only fields must be explicitly added to Proto if needed in API

---

## Audit Columns

**Every table** includes these audit columns:

| Column | Type | Description |
|--------|------|-------------|
| `creation_date` | `TIMESTAMP` | When the row was created (auto-set to `NOW()`) |
| `last_update` | `TIMESTAMP` | When the row was last updated (auto-set by trigger) |
| `user_id_last_update` | `INTEGER` | User who performed the last update (FK to `users`) |

**Behavior:**
- On **INSERT**: `creation_date` is set automatically, `last_update` and `user_id_last_update` are NULL
- On **UPDATE**: `last_update` is set automatically by trigger, application must set `user_id_last_update`
- On row creation, `creation_date` = `last_update` semantically (first update is the creation)

---

## Tables Overview

| Table | Purpose | Expected Size |
|-------|---------|---------------|
| `users` | User accounts synced from Authentik | ~1M max |
| `llms` | LLM provider configurations | ~10 |
| `embedding_models` | Embedding model configs (cluster-wide) | ~10 |
| `assistants` | AI personalities with custom prompts | ~10 |
| `connectors` | Data source connections | ~100 |
| `documents` | Ingested content from connectors | Up to 1B |
| `chat_sessions` | Conversation threads | Large |
| `chat_messages` | Individual messages in sessions | Very large |
| `chat_message_feedbacks` | Thumbs up/down on messages | Medium |
| `chat_message_documents` | Document citations in messages | Large |
| `agent_memories` | Long-term agent memory | Medium |

---

## Users & Authentication

### `users`

Stores user accounts synchronized from Authentik (OIDC provider). This is the central identity table - all user-owned resources reference this table.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL` | Primary key (auto-increment) |
| `user_name` | `VARCHAR(255)` | Unique username |
| `email` | `VARCHAR(255)` | Unique email address |
| `first_name` | `VARCHAR(255)` | First name |
| `last_name` | `VARCHAR(255)` | Last name |
| `external_id` | `TEXT` | Authentik user ID |
| `roles` | `TEXT[]` | Array of roles: `['user', 'admin']` |
| `groups` | `TEXT[]` | Array of groups: `['engineering', 'sales']` |
| `preferences` | `JSONB` | User preferences (theme, default_assistant_id, etc.) |
| `is_active` | `BOOLEAN` | Account active status |
| `creation_date` | `TIMESTAMP` | When user was created |
| `last_update` | `TIMESTAMP` | Last profile update |
| `user_id_last_update` | `INTEGER` | User who performed the last update |
| `last_login` | `TIMESTAMP` | Last login timestamp |

**Notes:**
- Users are created/updated via Authentik sync, not directly
- `groups` array is used for vector collection scoping

---

## LLM & Embedding Models

### `llms`

Stores LLM provider configurations. Defines available language models (local TGI/vLLM or cloud OpenAI/Anthropic) that assistants can use for text generation.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `SMALLSERIAL` | Primary key |
| `name` | `VARCHAR(255)` | Display name (e.g., "Local Mistral") |
| `provider` | `VARCHAR(50)` | Provider type: `tgi`, `vllm`, `openai`, `anthropic`, `ollama` |
| `model_id` | `VARCHAR(255)` | Model identifier (e.g., `mistralai/Mistral-7B-Instruct-v0.2`) |
| `endpoint` | `VARCHAR` | Inference endpoint URL |
| `api_key` | `VARCHAR` | API key (encrypted, nullable for local models) |
| `max_tokens` | `INTEGER` | Maximum tokens for generation |
| `temperature` | `NUMERIC(3,2)` | Default temperature |
| `is_default` | `BOOLEAN` | Is this the default LLM? |
| `is_active` | `BOOLEAN` | Is this LLM available for use? |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |
| `deleted_date` | `TIMESTAMP` | Soft delete timestamp |

**Notes:**
- Multiple LLMs can be configured for different use cases
- `api_key` should be encrypted at rest

---

### `embedding_models`

Stores embedding model configurations. The active model converts text into vectors for semantic search. Only one model can be active cluster-wide.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `SMALLSERIAL` | Primary key |
| `model_id` | `VARCHAR` | Model identifier (e.g., `nvidia/llama-nemotron-embed-1b-v2`) |
| `model_name` | `VARCHAR` | Display name |
| `model_dimension` | `INTEGER` | Vector dimension (e.g., 768) |
| `endpoint` | `VARCHAR` | Optional external embedding service URL |
| `is_active` | `BOOLEAN` | Only one can be active at a time |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |
| `deleted_date` | `TIMESTAMP` | Soft delete timestamp |

**Notes:**
- **Only one embedding model can be active** (enforced by unique partial index)
- Changing the active model requires re-indexing all documents

---

## Assistants

### `assistants`

Stores AI assistant configurations. Each assistant defines a unique personality with custom system/task prompts that shape how the LLM responds to users.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `SMALLSERIAL` | Primary key |
| `name` | `VARCHAR(255)` | Assistant name (e.g., "Research Assistant") |
| `description` | `TEXT` | User-facing description |
| `llm_id` | `SMALLINT` | FK to `llms` - which LLM to use |
| `system_prompt` | `TEXT` | System prompt for the LLM |
| `task_prompt` | `TEXT` | Task prompt template with `{context}` and `{query}` placeholders |
| `starter_messages` | `JSONB` | Array of suggested conversation starters |
| `is_default` | `BOOLEAN` | Is this the default assistant? |
| `is_visible` | `BOOLEAN` | Show in UI? |
| `display_priority` | `INTEGER` | Order in UI (lower = higher priority) |
| `created_by` | `INTEGER` | FK to `users` - who created this assistant |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |
| `deleted_date` | `TIMESTAMP` | Soft delete timestamp |

**Example `task_prompt`:**
```
Answer the user's question based on the following context:

{context}

Question: {query}
```

---

## Connectors & Documents

### `connectors`

Stores data source connections. Each connector links to an external system (Teams, Google Drive, etc.) and tracks sync state, enabling automatic document ingestion.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `SMALLSERIAL` | Primary key |
| `name` | `VARCHAR(255)` | Display name (e.g., "Engineering Team Drive") |
| `type` | `VARCHAR(50)` | Connector type: `teams`, `google_drive`, `onedrive`, `web`, `file` |
| `config` | `JSONB` | Connector-specific configuration |
| `state` | `JSONB` | Sync state (cursors, tokens, pagination state) |
| `refresh_freq_minutes` | `INTEGER` | Auto-refresh interval (null = manual only) |
| `user_id` | `INTEGER` | FK to `users` - owner of this connector |
| `scope` | `VARCHAR(20)` | Vector collection scope: `user`, `group`, `org` |
| `scope_id` | `TEXT` | Group name if `scope='group'`, null otherwise |
| `status` | `VARCHAR(50)` | Status: `pending`, `syncing`, `active`, `error`, `disabled` |
| `status_message` | `TEXT` | Error message or status details |
| `last_sync_at` | `TIMESTAMP` | Last successful sync |
| `docs_analyzed` | `BIGINT` | Total documents processed |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |
| `deleted_date` | `TIMESTAMP` | Soft delete timestamp |

**Scope determines vector collection:**
- `user` → `user_{user_id}` collection
- `group` → `group_{scope_id}` collection
- `org` → `org` collection

---

### `documents`

Stores metadata for ingested documents. Tracks source, processing status, and links to chunks stored in Qdrant. The actual content is stored in MinIO.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `BIGSERIAL` | Primary key |
| `parent_id` | `BIGINT` | FK to `documents` - for hierarchical docs (folders, threads) |
| `connector_id` | `SMALLINT` | FK to `connectors` |
| `source_id` | `TEXT` | Unique ID from source system |
| `url` | `TEXT` | Source URL or MinIO path (`minio:bucket:file`) |
| `original_url` | `TEXT` | Original URL before transformations |
| `title` | `TEXT` | Document title/name |
| `content_type` | `VARCHAR(100)` | MIME type |
| `signature` | `TEXT` | Hash for change detection |
| `chunking_session` | `UUID` | Groups chunks from same processing run |
| `status` | `VARCHAR(50)` | Status: `pending`, `processing`, `completed`, `failed` |
| `status_message` | `TEXT` | Error message if failed |
| `chunk_count` | `INTEGER` | Number of chunks created |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |

**Notes:**
- `signature` is used to detect if document content has changed
- `chunking_session` links all chunks created in one processing run

---

## Chat Sessions & Messages

### `chat_sessions`

Stores conversation threads. Each session links a user to an assistant and contains multiple messages forming a conversation history.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL` | Primary key |
| `user_id` | `INTEGER` | FK to `users` |
| `assistant_id` | `SMALLINT` | FK to `assistants` |
| `title` | `TEXT` | Session title (default: "New Chat") |
| `mode` | `VARCHAR(20)` | Mode: `chat` (multi-turn) or `one_shot` (single query) |
| `message_count` | `INTEGER` | Number of messages (auto-updated by trigger) |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |
| `last_message_at` | `TIMESTAMP` | Timestamp of last message |
| `deleted_date` | `TIMESTAMP` | Soft delete timestamp |

---

### `chat_messages`

Stores individual messages within chat sessions. Captures user queries, assistant responses, retrieval context used, and any tools invoked during generation.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `BIGSERIAL` | Primary key |
| `chat_session_id` | `INTEGER` | FK to `chat_sessions` |
| `role` | `VARCHAR(20)` | Message role: `user`, `assistant`, `system` |
| `content` | `TEXT` | Message content |
| `token_count` | `INTEGER` | Token count for this message |
| `parent_message_id` | `BIGINT` | FK to `chat_messages` - for branching conversations |
| `rephrased_query` | `TEXT` | Agent's rephrased query for retrieval |
| `retrieval_context` | `JSONB` | Retrieved chunks used for this response |
| `tool_calls` | `JSONB` | Tools invoked during response generation |
| `error` | `TEXT` | Error message if generation failed |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |

**Notes:**
- `retrieval_context` stores the chunks retrieved from Qdrant
- `tool_calls` logs any tools the agent invoked (search, calculator, etc.)

---

### `chat_message_feedbacks`

Stores user feedback (thumbs up/down) on assistant responses. Used to track response quality and potentially for RLHF fine-tuning.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL` | Primary key |
| `chat_message_id` | `BIGINT` | FK to `chat_messages` |
| `user_id` | `INTEGER` | FK to `users` |
| `is_positive` | `BOOLEAN` | `true` = thumbs up, `false` = thumbs down |
| `feedback_text` | `TEXT` | Optional text feedback |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |

**Notes:**
- One feedback per user per message (enforced by unique constraint)

---

### `chat_message_documents`

Links chat messages to source documents. Enables citation display in the UI, showing users which documents were used to generate each response.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `BIGSERIAL` | Primary key |
| `chat_message_id` | `BIGINT` | FK to `chat_messages` |
| `document_id` | `BIGINT` | FK to `documents` |
| `chunk_id` | `TEXT` | Specific chunk ID from Qdrant |
| `relevance_score` | `NUMERIC(5,4)` | Retrieval relevance score |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |

---

## Agent Memory

### `agent_memories`

Stores long-term agent memory per user. Enables the agent to remember important facts, preferences, and successful interaction patterns across sessions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL` | Primary key |
| `user_id` | `INTEGER` | FK to `users` |
| `memory_type` | `VARCHAR(50)` | Type: `episodic`, `semantic`, `procedural` |
| `content` | `TEXT` | The memory content |
| `embedding_id` | `TEXT` | Reference to vector in Qdrant |
| `importance_score` | `NUMERIC(3,2)` | Importance score (0.0 - 1.0) |
| `access_count` | `INTEGER` | Times this memory was retrieved |
| `last_accessed_at` | `TIMESTAMP` | Last retrieval timestamp |
| `source_session_id` | `INTEGER` | FK to `chat_sessions` - where memory originated |
| `creation_date` | `TIMESTAMP` | When created |
| `last_update` | `TIMESTAMP` | When last updated |
| `user_id_last_update` | `INTEGER` | User who performed the last update |
| `expires_at` | `TIMESTAMP` | Optional expiration |

**Memory Types:**
- **Episodic**: Past interactions worth remembering
- **Semantic**: Learned facts about the user
- **Procedural**: Successful patterns/approaches

---

## Triggers

### `update_last_update_column`

Automatically updates `last_update` timestamp on row modification.

Applied to: `users`, `llms`, `embedding_models`, `assistants`, `connectors`, `documents`

### `update_chat_session_message_count`

Automatically updates `message_count` and `last_message_at` in `chat_sessions` when messages are inserted/deleted.

---

## Indexes

| Table | Index | Purpose |
|-------|-------|---------|
| `users` | `idx_users_email` | Fast lookup by email |
| `users` | `idx_users_external_id` | Fast lookup by Authentik ID |
| `embedding_models` | `idx_embedding_models_active` | Ensure only one active model |
| `assistants` | `idx_assistants_is_visible` | Filter visible assistants |
| `connectors` | `idx_connectors_user_id` | User's connectors |
| `connectors` | `idx_connectors_status` | Filter by status |
| `documents` | `idx_documents_connector_id` | Documents per connector |
| `documents` | `idx_documents_status` | Filter by status |
| `documents` | `idx_documents_source_id` | Lookup by source ID |
| `chat_sessions` | `idx_chat_sessions_user_id` | User's sessions |
| `chat_messages` | `idx_chat_messages_session_id` | Messages per session |
| `chat_message_documents` | `idx_chat_message_documents_message_id` | Citations per message |
| `agent_memories` | `idx_agent_memories_user_id` | User's memories |
| `agent_memories` | `idx_agent_memories_type` | Filter by memory type |
