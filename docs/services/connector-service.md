# Connector Service

> **Service:** `echomind-connector`
> **Protocol:** NATS (subscriber)
> **Port:** 8080 (health check only)

---

## What It Does

The Connector Service **fetches data from external sources** that require API authentication:

- Microsoft Teams (messages, files)
- Microsoft OneDrive (files, folders)
- Google Drive (files, folders)

It handles OAuth token management, delta sync (incremental updates), and file download to MinIO.

---

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph ConnectorService["echomind-connector"]
        NATS_SUB[NATS Subscriber]
        ROUTER[Provider Router]
        TEAMS[Teams Provider]
        ONEDRIVE[OneDrive Provider]
        GDRIVE[Google Drive Provider]
        DOWNLOADER[File Downloader]
        NATS_PUB[NATS Publisher]
    end

    subgraph External
        NATS[(NATS)]
        MINIO[(MinIO)]
        DB[(PostgreSQL)]
        MS_API[Microsoft Graph API]
        GOOGLE_API[Google Drive API]
    end

    NATS -->|connector.sync.*| NATS_SUB
    NATS_SUB --> ROUTER
    ROUTER --> TEAMS & ONEDRIVE & GDRIVE
    TEAMS --> MS_API
    ONEDRIVE --> MS_API
    GDRIVE --> GOOGLE_API
    TEAMS & ONEDRIVE & GDRIVE --> DOWNLOADER
    DOWNLOADER --> MINIO
    DOWNLOADER --> DB
    DOWNLOADER --> NATS_PUB
    NATS_PUB -->|document.process| NATS
```

### Message Flow

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant N as NATS
    participant C as Connector
    participant API as External API
    participant M as MinIO
    participant DB as PostgreSQL
    participant S as Semantic

    O->>N: connector.sync.google_drive
    N->>C: ConnectorSyncRequest

    C->>DB: Set status = syncing
    C->>API: Fetch file list (delta)
    API-->>C: Changed files

    loop Each file
        C->>API: Download file
        API-->>C: File bytes
        C->>M: Upload to MinIO
        C->>DB: Create document record
        C->>N: document.process
    end

    N->>S: DocumentProcessRequest
    Note over S: Semantic processes...

    S->>DB: Set status = active
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| NATS Client | nats-py (async) |
| HTTP Client | httpx (async) |
| OAuth | authlib |
| MinIO | minio-py |
| Database | SQLAlchemy async |

---

## Database Tables Used

| Table | Operations | Reference |
|-------|------------|-----------|
| `connectors` | Read, Update (status, state) | [DB Schema](../db-schema.md#connectors) |
| `documents` | Create | [DB Schema](../db-schema.md#documents) |

---

## Proto Definitions Used

| Proto | Direction | Description |
|-------|-----------|-------------|
| `ConnectorSyncRequest` | Subscribe | Incoming sync trigger |
| `DocumentProcessRequest` | Publish | Outgoing to semantic |

See [Proto Definitions](../proto-definitions.md)

---

## NATS Messaging

### Subscriptions (Incoming)

| Subject | Payload | From |
|---------|---------|------|
| `connector.sync.teams` | `ConnectorSyncRequest` | Orchestrator |
| `connector.sync.onedrive` | `ConnectorSyncRequest` | Orchestrator |
| `connector.sync.google_drive` | `ConnectorSyncRequest` | Orchestrator |

### Publications (Outgoing)

| Subject | Payload | To |
|---------|---------|-----|
| `document.process` | `DocumentProcessRequest` | Semantic |

### Consumer Configuration

```python
subscriber = JetStreamEventSubscriber(
    nats_url="nats://nats:4222",
    stream_name="ECHOMIND",
    subjects=[
        "connector.sync.teams",
        "connector.sync.onedrive",
        "connector.sync.google_drive"
    ],
    durable_name="connector-consumer",
    queue_group="connector-workers"
)
```

---

## Providers

### Microsoft Teams

```python
class TeamsProvider:
    """Fetch messages and files from Teams channels."""

    async def sync(self, config: dict, state: dict) -> AsyncIterator[Document]:
        # Use delta query for incremental sync
        delta_url = state.get("delta_link") or "/teams/{team_id}/channels/{channel_id}/messages/delta"

        async for message in self.graph_client.get_delta(delta_url):
            if message.attachments:
                for attachment in message.attachments:
                    yield Document(
                        source_id=attachment.id,
                        url=await self.download_to_minio(attachment),
                        title=attachment.name
                    )

        # Save delta link for next sync
        state["delta_link"] = self.graph_client.delta_link
```

### Microsoft OneDrive

```python
class OneDriveProvider:
    """Fetch files from OneDrive folders."""

    async def sync(self, config: dict, state: dict) -> AsyncIterator[Document]:
        folder_id = config["folder_id"]
        delta_token = state.get("delta_token")

        async for item in self.graph_client.get_drive_delta(folder_id, delta_token):
            if item.file:  # Skip folders
                yield Document(
                    source_id=item.id,
                    url=await self.download_to_minio(item),
                    title=item.name,
                    content_type=item.file.mime_type
                )

        state["delta_token"] = self.graph_client.delta_token
```

### Google Drive

```python
class GoogleDriveProvider:
    """Fetch files from Google Drive folders."""

    async def sync(self, config: dict, state: dict) -> AsyncIterator[Document]:
        folder_id = config["folder_id"]
        page_token = state.get("page_token")

        query = f"'{folder_id}' in parents and trashed = false"

        async for file in self.drive_client.list_files(query, page_token):
            yield Document(
                source_id=file.id,
                url=await self.download_to_minio(file),
                title=file.name,
                content_type=file.mime_type
            )

        state["page_token"] = self.drive_client.next_page_token
```

---

## Service Structure

```
src/services/connector/
├── main.py                 # Entry point
├── nats/
│   ├── subscriber.py       # NATS consumer
│   └── publisher.py        # NATS producer
├── logic/
│   ├── connector_service.py
│   ├── providers/
│   │   ├── base.py         # BaseProvider ABC
│   │   ├── teams.py
│   │   ├── onedrive.py
│   │   └── google_drive.py
│   ├── downloader.py       # MinIO upload
│   └── exceptions.py
├── middleware/
│   └── error_handler.py
└── config.py
```

---

## Configuration

```bash
# NATS
NATS_URL=nats://nats:4222
NATS_STREAM_NAME=ECHOMIND

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/echomind

# Microsoft Graph (Teams, OneDrive)
MS_GRAPH_CLIENT_ID=xxx
MS_GRAPH_CLIENT_SECRET=xxx
MS_GRAPH_TENANT_ID=xxx

# Google Drive
GOOGLE_SERVICE_ACCOUNT_JSON=/secrets/google-sa.json
```

---

## Status Updates

| When | Status | Updated By |
|------|--------|------------|
| Sync starts | `syncing` | Connector |
| Sync fails | `error` | Connector |
| All docs processed | `active` | Semantic (not Connector) |

---

## Health Check

```bash
GET :8080/healthz

# Response
{
  "status": "healthy",
  "nats": "connected",
  "minio": "connected",
  "database": "connected"
}
```

---

## Unit Testing (MANDATORY)

All service logic MUST have unit tests. See [Testing Standards](../../.claude/rules/testing.md).

### Test Location

```
tests/unit/connector/
├── test_connector_service.py
├── test_providers/
│   ├── test_teams_provider.py
│   ├── test_onedrive_provider.py
│   └── test_google_drive_provider.py
└── test_downloader.py
```

### What to Test

| Component | Test Coverage |
|-----------|---------------|
| ConnectorService | Event handling, routing |
| TeamsProvider | Delta sync, message parsing |
| OneDriveProvider | File listing, delta tokens |
| GoogleDriveProvider | Query building, pagination |
| Downloader | MinIO upload logic |

### Example

```python
# tests/unit/connector/test_providers/test_google_drive_provider.py
class TestGoogleDriveProvider:
    @pytest.fixture
    def mock_drive_client(self):
        return AsyncMock()

    @pytest.fixture
    def provider(self, mock_drive_client):
        return GoogleDriveProvider(mock_drive_client)

    @pytest.mark.asyncio
    async def test_sync_returns_files_from_folder(self, provider, mock_drive_client):
        mock_drive_client.list_files.return_value = [mock_file("doc.pdf")]

        files = [f async for f in provider.sync({"folder_id": "123"}, {})]

        assert len(files) == 1
        assert files[0].title == "doc.pdf"
```

### Minimum Coverage

- **70%** for service classes
- **80%** for provider logic

---

## References

- [NATS Messaging](../nats-messaging.md) - Message flow documentation
- [Proto Definitions](../proto-definitions.md) - Message schemas
- [Orchestrator Service](./orchestrator-service.md) - Triggers connector sync
- [Semantic Service](./semantic-service.md) - Processes downloaded files
