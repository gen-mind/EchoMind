# Orchestrator Service

> **Status**: Draft
> **Technology**: APScheduler
> **Location**: `src/orchestrator/`

---

## Overview

The Orchestrator Service is a **lightweight trigger service** that monitors the database and sends NATS messages when work needs to be done. It does NOT execute any business logic itself.

**What it does:**
- Query the database for connectors due for sync
- Update connector status to `pending`
- Publish a message to NATS

**What it does NOT do:**
- Fetch data from external sources
- Process documents
- Update status to `syncing`, `active`, or `error` (other services do this)
- Determine if content has changed (downstream services handle this)

---

## Responsibility Boundaries

```mermaid
flowchart LR
    subgraph Orchestrator["Orchestrator Service"]
        S1[1. Query DB]
        S2[2. Set PENDING]
        S3[3. Send NATS]
    end

    subgraph Connector["Connector Service"]
        C1[3. Pick up msg]
        C2[4. Set SYNCING]
        C3[5. Fetch data]
        C4[6. Send NATS]
    end

    subgraph Ingestor["Ingestor Service"]
        E1[5. Pick up msg]
        E2[6. Extract + Chunk]
        E3[7. Embed]
        E4[8. Set ACTIVE or ERROR]
    end

    Orchestrator -->|NATS| Connector
    Connector -->|NATS| Ingestor
```

| Action | Responsible Service |
|--------|---------------------|
| Set status to `pending` | Orchestrator |
| Set status to `syncing` | Connector or Ingestor |
| Set status to `active` | Ingestor (on success) |
| Set status to `error` | Any service (on failure) |

**Status Values:** See [Proto Definitions](../proto-definitions.md#connectorstatus)

---

## Core Responsibilities

### 1. Connector Sync Check

Query the `connectors` table for rows that need sync:

| Field | Purpose |
|-------|---------|
| `status` | Trigger if `active` or `error`. Skip if `pending`, `syncing`, or `disabled` |
| `refresh_freq_minutes` | Interval between syncs (null = manual only) |
| `last_sync_at` | Calculate next run time |
| `type` | Determines NATS subject routing |

**Database Schema:** See [DB Schema - connectors](../db-schema.md#connectors)

### 2. Refresh Rules by Connector Type

| Connector Type | Default Refresh | Route To | Behavior |
|----------------|-----------------|----------|----------|
| `web` | 7 days | Ingestor | Conditional fetch (ETag/Last-Modified) |
| `file` | One-time | Ingestor | Manual upload, no refresh |
| `onedrive` | 7 days | Connector | Delta API sync (cTag comparison) |
| `google_drive` | 7 days | Connector | Changes API sync (md5Checksum) |
| `teams` | 1 day | Connector | Incremental (new messages) |

**Connector Types:** See [Proto Definitions](../proto-definitions.md#connectortype)

---

## Change Detection Strategies

The orchestrator triggers syncs based on time intervals. **Change detection happens in downstream services** (Connector/Semantic) to avoid unnecessary processing.

### Web Pages (Ingestor Service)

Web pages use HTTP conditional requests:

| Method | Header | Description |
|--------|--------|-------------|
| **ETag** | `If-None-Match` | Server returns 304 if content unchanged |
| **Last-Modified** | `If-Modified-Since` | Server returns 304 if not modified since date |
| **Content Hash** | N/A | Fallback: compute MD5 of response body, compare with stored hash |

**Implementation:**
```python
# Store in connector.state
{
    "etag": "\"abc123\"",
    "last_modified": "Wed, 21 Oct 2023 07:28:00 GMT",
    "content_hash": "d41d8cd98f00b204e9800998ecf8427e"
}

# On sync, send conditional request
headers = {}
if state.get("etag"):
    headers["If-None-Match"] = state["etag"]
if state.get("last_modified"):
    headers["If-Modified-Since"] = state["last_modified"]

response = requests.get(url, headers=headers)
if response.status_code == 304:
    logger.info("📄 Content unchanged, skipping processing")
    return
```

### Google Drive (Connector Service)

Google Drive uses the **Changes API** with page tokens:

| Field | Purpose |
|-------|---------|
| `changes.list` | Returns changed files since last `pageToken` |
| `md5Checksum` | File metadata field for content verification |
| `pageToken` | Cursor for tracking sync position |

**Key Points:**
- Cannot compute hash without downloading file
- Use `md5Checksum` from file metadata (no download needed)
- Store `pageToken` in `connector.state` for incremental sync

**Implementation:**
```python
# Store in connector.state
{
    "page_token": "12345",
    "file_checksums": {
        "file_id_1": "d41d8cd98f00b204e9800998ecf8427e",
        "file_id_2": "098f6bcd4621d373cade4e832627b4f6"
    }
}

# On sync
changes = drive_service.changes().list(
    pageToken=state["page_token"],
    fields="newStartPageToken,changes(fileId,file(md5Checksum,name))"
).execute()

for change in changes.get("changes", []):
    file_id = change["fileId"]
    new_checksum = change.get("file", {}).get("md5Checksum")
    old_checksum = state["file_checksums"].get(file_id)

    if new_checksum != old_checksum:
        # File changed, download and process
        download_to_minio(file_id)
```

### OneDrive (Connector Service)

OneDrive uses the **Delta API** with cTag for content changes:

| Field | Purpose |
|-------|---------|
| `delta` endpoint | Returns changed items since last `deltaLink` |
| `cTag` | Changes when file **content** changes |
| `eTag` | Changes for any modification (content or metadata) |

**Key Points:**
- Use `cTag` (not `eTag`) to detect content changes
- Store `deltaLink` in `connector.state` for incremental sync
- No download needed to detect changes

**Implementation:**
```python
# Store in connector.state
{
    "delta_link": "https://graph.microsoft.com/v1.0/me/drive/root/delta?token=xxx",
    "file_ctags": {
        "item_id_1": "c:{abc123}",
        "item_id_2": "c:{def456}"
    }
}

# On sync
response = requests.get(state["delta_link"])
for item in response.json().get("value", []):
    item_id = item["id"]
    new_ctag = item.get("cTag")
    old_ctag = state["file_ctags"].get(item_id)

    if new_ctag != old_ctag:
        # Content changed, download and process
        download_to_minio(item_id)
```

### File Upload (Ingestor Service)

Uploaded files use hash-based change detection:

| Method | Description |
|--------|-------------|
| **MD5 Hash** | Compute hash of uploaded file, compare with stored hash |

Files are uploaded directly to MinIO, so hash computation is local.

---

## File Processing Flow

All files are **copied to MinIO** before processing. The physical file is **deleted after processing completes or errors**.

```mermaid
flowchart LR
    subgraph External["External Source"]
        GD[Google Drive]
        OD[OneDrive]
        WEB[Web Page]
    end

    subgraph MinIO["MinIO Storage"]
        FILE[Temporary File]
    end

    subgraph Processing["Processing Pipeline"]
        ING[Ingestor Service]
        EMB[Embedder Service]
    end

    subgraph Cleanup["Cleanup"]
        DEL[Delete Physical File]
    end

    GD -->|Download| FILE
    OD -->|Download| FILE
    WEB -->|Download| FILE

    FILE --> ING
    ING --> EMB
    EMB --> DEL
```

**Flow:**
1. **Download**: Connector downloads file to MinIO (temp bucket)
2. **Process**: Ingestor extracts content (nv-ingest), Embedder creates vectors
3. **Store**: Vectors stored in Qdrant, metadata in PostgreSQL
4. **Delete**: Physical file deleted from MinIO

**Why copy to MinIO?**
- External APIs have rate limits
- Processing may require multiple reads (chunking, embedding)
- Provides consistent storage interface
- Enables retry without re-downloading

**Cleanup triggers:**
- Processing completes successfully → Delete file
- Processing fails permanently → Delete file + mark connector as error
- Processing fails transiently → Keep file for retry (configurable TTL)

### 3. Status Flow

```mermaid
stateDiagram-v2
    direction LR

    ACTIVE: active
    PENDING: pending
    SYNCING: syncing
    ERROR: error
    DISABLED: disabled

    [*] --> ACTIVE: New connector
    ACTIVE --> PENDING: Orchestrator sets
    PENDING --> SYNCING: Connector/Ingestor sets
    SYNCING --> ACTIVE: Success (Ingestor)
    SYNCING --> ERROR: Failure (any service)
    ERROR --> PENDING: Retry (Orchestrator)
    ACTIVE --> DISABLED: User disables
```

**Statuses that ALLOW scheduling:**
- `active` - Ready for sync (check refresh_freq_minutes + last_sync_at)
- `error` - Failed, can retry

**Statuses that BLOCK scheduling:**
- `pending` - Already queued, waiting for worker
- `syncing` - Currently processing
- `disabled` - User disabled connector

---

## Architecture

```mermaid
flowchart TB
    subgraph Orchestrator["Orchestrator Service"]
        APS[APScheduler<br/>Interval: Configurable]
        JOB[ConnectorSync Job]
        APS --> JOB
    end

    subgraph DB["PostgreSQL"]
        CONN[(connectors table)]
    end

    subgraph NATS["NATS JetStream"]
        WEB[connector.sync.web]
        FILE[connector.sync.file]
        DRIVE[connector.sync.onedrive<br/>connector.sync.google_drive]
        TEAMS[connector.sync.teams]
    end

    subgraph Consumers
        INGESTOR[Ingestor Service]
        CONNECTOR[Connector Service]
    end

    JOB -->|1. Query eligible connectors| CONN
    JOB -->|2. Set status PENDING| CONN
    JOB -->|3. Publish| WEB & FILE & DRIVE & TEAMS

    WEB --> INGESTOR
    FILE --> INGESTOR
    DRIVE --> CONNECTOR
    TEAMS --> CONNECTOR
```

---

## Job Types

### 1. ConnectorSyncJob (Primary)

Runs at configurable interval (default: 60 seconds), checks for connectors due for sync:

```python
from datetime import datetime, timezone

async def connector_sync_check() -> None:
    """
    Check for connectors that need synchronization.

    For each connector due for sync:
    1. Update status to pending
    2. Publish NATS message

    Does NOT wait for response or do any processing.
    """
    now = datetime.now(timezone.utc)

    # Find connectors eligible for sync:
    # - Status is active (ready) or error (can retry)
    # - refresh_freq_minutes is set (not manual-only)
    # - last_sync_at + refresh_freq_minutes <= now
    connectors = await db.execute(
        select(Connector)
        .where(Connector.status.in_(["active", "error"]))
        .where(Connector.refresh_freq_minutes.isnot(None))
        .where(
            or_(
                Connector.last_sync_at.is_(None),
                Connector.last_sync_at +
                    func.make_interval(mins=Connector.refresh_freq_minutes) <= now
            )
        )
    )

    for connector in connectors.scalars():
        # 1. Update status to pending
        await db.execute(
            update(Connector)
            .where(Connector.id == connector.id)
            .values(status="pending")
        )
        await db.commit()

        # 2. Generate chunking session ID
        chunking_session = str(uuid.uuid4())

        # 3. Publish NATS message (fire-and-forget)
        subject = f"connector.sync.{connector.type}"
        await nats.publish(subject, ConnectorSyncRequest(
            connector_id=connector.id,
            type=connector.type,
            user_id=connector.user_id,
            scope=connector.scope,
            scope_id=connector.scope_id,
            config=connector.config,
            state=connector.state,
            chunking_session=chunking_session,
        ))

        logger.info("📤 Triggered sync for connector %s (session: %s)",
                    connector.id, chunking_session)
```

---

## Integration with Existing Services

### Message Flow (Fire-and-Forget)

The orchestrator publishes and moves on. It does NOT wait for responses.

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant DB as Database
    participant N as NATS
    participant C as Connector
    participant I as Ingestor

    O->>DB: 1. Set status = pending
    O->>N: 2. Publish connector.sync.*
    Note over O: Orchestrator done

    N->>C: 3. Consume message
    C->>DB: 4. Set status = syncing
    C->>C: Fetch from external source
    C->>N: 5. Publish document.process

    N->>I: 6. Consume message
    I->>I: Extract (nv-ingest) + Chunk + Embed
    I->>DB: 7. Set status = active
```

### NATS Subjects

| Subject | Publisher | Consumer | Payload |
|---------|-----------|----------|---------|
| `connector.sync.web` | Orchestrator | Ingestor | `ConnectorSyncRequest` |
| `connector.sync.file` | Orchestrator | Ingestor | `ConnectorSyncRequest` |
| `connector.sync.onedrive` | Orchestrator | Connector | `ConnectorSyncRequest` |
| `connector.sync.google_drive` | Orchestrator | Connector | `ConnectorSyncRequest` |
| `connector.sync.teams` | Orchestrator | Connector | `ConnectorSyncRequest` |
| `document.process` | Connector | Ingestor | `DocumentProcessRequest` |

**Note:** The orchestrator does NOT subscribe to any subjects. It only publishes.

**Proto Messages:** See [Proto Definitions](../proto-definitions.md#connectorsyncrequest)

---

## Service Structure

```
src/services/orchestrator/
├── __init__.py
├── main.py                 # Entry point
├── logic/
│   ├── __init__.py
│   ├── orchestrator_service.py  # Core scheduling logic
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── connector_sync.py    # Connector sync job
│   │   ├── cleanup.py           # Cleanup job
│   │   └── health_check.py      # Health check job
│   └── exceptions.py            # Domain exceptions
├── middleware/
│   └── error_handler.py
└── config.py               # Service configuration
```

---

## Configuration

### Environment Variables

```bash
# Orchestrator Settings
ORCHESTRATOR_ENABLED=true
ORCHESTRATOR_CHECK_INTERVAL_SECONDS=60       # Configurable job interval (default: 60s)
ORCHESTRATOR_MAX_CONCURRENT_SYNCS=5
ORCHESTRATOR_JOB_STORE_URL=${DATABASE_URL}

# Default Refresh Intervals (minutes) - can be overridden per connector
ORCHESTRATOR_DEFAULT_REFRESH_WEB=10080       # 7 days
ORCHESTRATOR_DEFAULT_REFRESH_DRIVE=10080     # 7 days
ORCHESTRATOR_DEFAULT_REFRESH_CHAT=1440       # 1 day
ORCHESTRATOR_DEFAULT_REFRESH_FILE=0          # Never (one-time)

# File Cleanup
ORCHESTRATOR_FILE_RETRY_TTL_HOURS=24         # Keep failed files for retry
ORCHESTRATOR_FILE_CLEANUP_ENABLED=true       # Auto-delete processed files
```

### Config Class

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class OrchestratorSettings(BaseSettings):
    """Orchestrator service configuration."""

    enabled: bool = True
    check_interval_seconds: int = 60  # Job interval - NOT hardcoded
    max_concurrent_syncs: int = 5
    job_store_url: str

    # Default refresh intervals (can be overridden per connector)
    default_refresh_web: int = 10080
    default_refresh_drive: int = 10080
    default_refresh_chat: int = 1440
    default_refresh_file: int = 0

    # File cleanup
    file_retry_ttl_hours: int = 24
    file_cleanup_enabled: bool = True

    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_",
        env_file=".env",
    )
```

---

## Implementation Phases

### Phase 1: Core Orchestrator (MVP)
- [ ] APScheduler setup with PostgreSQL job store
- [ ] Connector sync check job (configurable interval)
- [ ] Update connector status to pending
- [ ] NATS publisher for sync triggers
- [ ] Basic health endpoint (`/healthz`)
- [ ] Docker Compose integration

### Phase 2: Production Ready
- [ ] Metrics export (Prometheus)
- [ ] Leader election for K8s (only one orchestrator runs)
- [ ] Helm chart
- [ ] ConfigMap/Secret integration

---

## High Availability

### Single Instance (Docker Compose)
- Simple: one orchestrator container
- Job store in PostgreSQL ensures jobs persist across restarts

### Multiple Instances (Kubernetes)
- **Leader Election**: Use PostgreSQL advisory locks or Kubernetes Lease API
- Only the leader executes jobs
- Followers remain on standby for failover

```python
# Leader election with PostgreSQL advisory lock
async def acquire_leadership():
    result = await db.execute(
        text("SELECT pg_try_advisory_lock(12345)")
    )
    return result.scalar()
```

---

## Observability

### Logging (Emoji Convention)

```python
logger.info("🕐 Orchestrator started")
logger.info("🔍 Checking connectors for sync...")
logger.info("📤 Triggered sync for connector %s", connector_id)
logger.info("✅ Sync completed for connector %s", connector_id)
logger.error("❌ Sync failed for connector %s: %s", connector_id, error)
logger.warning("⏭️ Skipping connector %s (already syncing)", connector_id)
```

### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `orchestrator_jobs_total` | Counter | Total jobs executed |
| `orchestrator_jobs_failed` | Counter | Failed job executions |
| `orchestrator_sync_duration_seconds` | Histogram | Sync job duration |
| `orchestrator_pending_syncs` | Gauge | Connectors waiting for sync |

---

## Database Tables

See [DB Schema](../db-schema.md) for full definitions:
- [connectors](../db-schema.md#connectors) - Connector configurations
- [apscheduler_jobs](../db-schema.md#apscheduler_jobs) - APScheduler job store
- [scheduler_runs](../db-schema.md#scheduler_runs) - Audit log

---

## Dependencies

```toml
# pyproject.toml additions
[project.dependencies]
apscheduler = "^3.10"
sqlalchemy = "^2.0"  # Already in echomind_lib
nats-py = "^2.0"     # Already in echomind_lib
```

---

## Open Questions

1. **How to handle stuck connectors?**
   - If a connector stays in `pending` or `syncing` for too long, should the orchestrator reset it?
   - Or should another service (health monitor) handle this?

2. **Manual trigger via API?**
   - Should the main API have an endpoint to manually trigger a sync?
   - This would bypass the orchestrator and directly publish to NATS

---

## Unit Testing (MANDATORY)

All service logic MUST have unit tests. See [Testing Standards](../../.claude/rules/testing.md).

### Test Location

```
tests/unit/orchestrator/
├── test_scheduler_service.py
├── test_job_manager.py
└── test_sync_trigger.py
```

### What to Test

| Component | Test Coverage |
|-----------|---------------|
| SchedulerService | Job scheduling, connector queries |
| JobManager | Job creation, removal, updates |
| SyncTrigger | NATS message publishing |

### Example

```python
# tests/unit/orchestrator/test_scheduler_service.py
class TestSchedulerService:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_nats(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db, mock_nats):
        return SchedulerService(mock_db, mock_nats)

    @pytest.mark.asyncio
    async def test_triggers_sync_for_due_connectors(self, service, mock_db, mock_nats):
        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            mock_connector(id=1, type="google_drive")
        ]

        await service.check_and_trigger_syncs()

        mock_nats.publish.assert_called_once()
```

### Minimum Coverage

- **70%** for service classes
- **80%** for scheduling logic

---

## References

- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [EchoMind Architecture](../architecture.md)
- [Proto Definitions](../proto-definitions.md)
- [DB Schema](../db-schema.md)
