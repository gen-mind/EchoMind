# Connector Service

> **Service:** `echomind-connector`
> **Protocol:** NATS (subscriber)
> **Port:** 8080 (health check only)

---

## What It Does

The Connector Service **fetches data from external sources** that require API authentication or special processing:

**Implemented:**
- **Google Drive** (files, folders, Google Workspace docs → PDF)
- **Microsoft OneDrive** (files, folders)

**Deferred (TBD):**
- ~~Web~~ - Needs web-to-PDF component (Puppeteer/Playwright research needed). Downloads page as PDF → Ingestor processes via nv-ingest.
- ~~YouTube~~ - Download MP4 when possible (yt-dlp research needed). Downloads video → Ingestor processes via nv-ingest (mp4 supported).
- ~~Microsoft Teams~~ - Future phase

**Not handled by Connector:**
- **File** (`connector.sync.file`) → Goes directly to Ingestor (no auth needed, files already in MinIO)

It handles OAuth token management, checkpoint-based resumable sync, and file download to MinIO.

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
    participant S as Ingestor

    O->>N: connector.sync.google_drive
    N->>C: ConnectorSyncRequest

    C->>DB: Set status = syncing

    Note over C,API: Step 1: Detect changes via metadata (NO download)
    C->>API: Get changes (Changes API / Delta API)
    API-->>C: Changed file metadata (md5/cTag)
    C->>DB: Compare with stored hashes
    Note over C: Filter to only changed files

    Note over C,API: Step 2: Download ONLY changed files
    loop Each changed file
        alt Google Workspace file
            C->>API: Export as PDF
        else Regular file
            C->>API: Download file
        end
        API-->>C: File bytes
        C->>M: Upload to MinIO
        C->>DB: Create/update document + store hash
        C->>N: document.process
    end

    N->>S: DocumentProcessRequest
    Note over S: Ingestor processes...

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
| `connector.sync.onedrive` | `ConnectorSyncRequest` | Orchestrator |
| `connector.sync.google_drive` | `ConnectorSyncRequest` | Orchestrator |

**Note:** `connector.sync.teams` deferred to future phase.

### Publications (Outgoing)

| Subject | Payload | To |
|---------|---------|-----|
| `document.process` | `DocumentProcessRequest` | Ingestor |

### Consumer Configuration

```python
subscriber = JetStreamEventSubscriber(
    nats_url="nats://nats:4222",
    stream_name="ECHOMIND",
    subjects=[
        "connector.sync.onedrive",
        "connector.sync.google_drive",
    ],
    durable_name="connector-consumer",
    queue_group="connector-workers"
)
```

---

## Change Detection Strategy

**Key Principle:** Check for changes via API metadata FIRST, download ONLY when needed.

### Per-Provider Change Detection

| Provider | Change Detection | What to Check |
|----------|------------------|---------------|
| **Google Drive** | Changes API + metadata | `md5Checksum` (files), `modifiedTime` |
| **OneDrive** | Delta API + metadata | `cTag` (content hash), `eTag` (any change) |
| **Teams** | Delta query | `lastModifiedDateTime` |

### Google Drive Change Detection

```python
async def check_changes(self, state: dict) -> list[FileChange]:
    """Check for changes without downloading files."""
    changes = []

    # Use Changes API with saved start_page_token
    start_token = state.get("changes_token")

    async for change in self.drive_client.list_changes(start_token):
        if change.removed:
            changes.append(FileChange(file_id=change.file_id, action="delete"))
        else:
            # Compare md5Checksum from metadata (no download needed)
            stored_hash = await self.get_stored_hash(change.file_id)
            if change.file.md5Checksum != stored_hash:
                changes.append(FileChange(
                    file_id=change.file_id,
                    action="update",
                    file=change.file
                ))

    # Save new token for next sync
    state["changes_token"] = self.drive_client.new_start_page_token
    return changes
```

### OneDrive Change Detection

```python
async def check_changes(self, state: dict) -> list[FileChange]:
    """Use Delta API to detect changes via cTag."""
    delta_link = state.get("delta_link")

    async for item in self.graph_client.get_delta(delta_link):
        if item.deleted:
            yield FileChange(file_id=item.id, action="delete")
        else:
            # cTag changes only when FILE CONTENT changes
            # eTag changes for any change (rename, move, etc.)
            stored_ctag = await self.get_stored_ctag(item.id)
            if item.cTag != stored_ctag:
                yield FileChange(file_id=item.id, action="update", file=item)

    state["delta_link"] = self.graph_client.delta_link
```

---

## Google Workspace Export Strategy

**All Google Workspace documents are exported as PDF** for consistent processing.

| Google Format | Export As | MIME Type | Notes |
|---------------|-----------|-----------|-------|
| Google Docs | PDF | `application/pdf` | Full document |
| Google Sheets | PDF | `application/pdf` | **All sheets** (unlike CSV which is first-sheet only) |
| Google Slides | PDF | `application/pdf` | Full presentation |
| Google Drawings | PDF | `application/pdf` | Full drawing |

**Limit:** 10MB max export size per file (Google API limitation).

### Why PDF?

1. **Consistent pipeline** - Ingestor processes all as PDF via nv-ingest (pdfium + YOLOX NIM)
2. **Preserves formatting** - Tables, charts, layouts retained
3. **All sheets included** - Google Sheets PDF exports all tabs (CSV only exports first sheet)
4. **No special handling** - Same flow as uploaded PDFs

**Source:** [Google Drive API Export Formats](https://developers.google.com/workspace/drive/api/guides/ref-export-formats)

### Export Flow

```python
GOOGLE_EXPORT_MIMES = {
    "application/vnd.google-apps.document": "application/pdf",      # Docs
    "application/vnd.google-apps.spreadsheet": "application/pdf",   # Sheets
    "application/vnd.google-apps.presentation": "application/pdf",  # Slides
    "application/vnd.google-apps.drawing": "application/pdf",       # Drawings
}

async def download_file(self, file: DriveFile) -> bytes:
    """Download or export file based on type."""
    if file.mimeType in GOOGLE_EXPORT_MIMES:
        # Google Workspace file - export as PDF
        export_mime = GOOGLE_EXPORT_MIMES[file.mimeType]
        return await self.drive_client.export_file(file.id, export_mime)
    else:
        # Regular file - download directly
        return await self.drive_client.download_file(file.id)
```

---

## Providers

**Implemented:** Google Drive, OneDrive

**Deferred (TBD):**
- **YouTube** - Download MP4 via yt-dlp
- **Web** - Convert to PDF via Puppeteer/Playwright
- **Teams** - Future phase

### Microsoft OneDrive

```python
class OneDriveProvider:
    """Fetch files from OneDrive folders."""

    async def sync(self, config: dict, state: dict) -> AsyncIterator[Document]:
        """
        Sync files from OneDrive.

        1. Use Delta API to get changed items
        2. Compare cTag to detect content changes (not just metadata)
        3. Download only files with content changes
        """
        folder_id = config["folder_id"]
        delta_link = state.get("delta_link")

        async for item in self.graph_client.get_drive_delta(folder_id, delta_link):
            if item.deleted:
                yield DocumentDelete(source_id=item.id)
                continue

            if not item.file:  # Skip folders
                continue

            # Check if content actually changed (cTag vs stored)
            stored_ctag = await self.get_stored_ctag(item.id)
            if stored_ctag and item.cTag == stored_ctag:
                continue  # No content change, skip download

            # Download only changed files
            content = await self.graph_client.download_file(item.id)
            minio_url = await self.upload_to_minio(content, item.name)

            yield Document(
                source_id=item.id,
                url=minio_url,
                title=item.name,
                content_type=item.file.mimeType,
                content_hash=item.cTag,  # Store cTag for future comparison
            )

        state["delta_link"] = self.graph_client.delta_link
```

### Google Drive

```python
class GoogleDriveProvider:
    """Fetch files from Google Drive folders."""

    GOOGLE_EXPORT_MIMES = {
        "application/vnd.google-apps.document": "application/pdf",
        "application/vnd.google-apps.spreadsheet": "application/pdf",
        "application/vnd.google-apps.presentation": "application/pdf",
        "application/vnd.google-apps.drawing": "application/pdf",
    }

    async def sync(self, config: dict, state: dict) -> AsyncIterator[Document]:
        """
        Sync files from Google Drive.

        1. Check for changes via API metadata (no download)
        2. Download/export only changed files
        3. Google Workspace files exported as PDF
        """
        # Step 1: Detect changes via metadata (md5Checksum comparison)
        changes = await self.check_changes(state)

        for change in changes:
            if change.action == "delete":
                yield DocumentDelete(source_id=change.file_id)
                continue

            file = change.file

            # Step 2: Download only if changed
            if file.mimeType in self.GOOGLE_EXPORT_MIMES:
                # Google Workspace → Export as PDF
                content = await self.drive_client.export_file(
                    file.id,
                    self.GOOGLE_EXPORT_MIMES[file.mimeType]
                )
                content_type = "application/pdf"
                filename = f"{file.name}.pdf"
            else:
                # Regular file → Download directly
                content = await self.drive_client.download_file(file.id)
                content_type = file.mimeType
                filename = file.name

            # Step 3: Upload to MinIO
            minio_url = await self.upload_to_minio(content, filename)

            yield Document(
                source_id=file.id,
                url=minio_url,
                title=file.name,
                content_type=content_type,
                content_hash=file.md5Checksum,  # Store for future comparison
            )
```

### YouTube Provider (TBD)

> **Status:** Deferred - Research needed for yt-dlp integration

```python
class YouTubeProvider:
    """Download videos from YouTube URLs."""

    async def sync(self, config: dict, state: dict) -> AsyncIterator[Document]:
        """
        TBD: Download MP4 from YouTube.

        1. Parse YouTube URL to get video ID
        2. Use yt-dlp to download MP4 (best quality that fits size limit)
        3. Upload MP4 to MinIO
        4. Publish document.process → Ingestor handles via nv-ingest

        Research needed:
        - yt-dlp Python API vs CLI wrapper
        - Video quality/size limits
        - Rate limiting / YouTube ToS compliance
        - Audio-only option (mp3) for podcasts
        """
        raise NotImplementedError("YouTube provider TBD")
```

### Web Provider (TBD)

> **Status:** Deferred - Research needed for Puppeteer/Playwright integration

```python
class WebProvider:
    """Convert web pages to PDF for processing."""

    async def sync(self, config: dict, state: dict) -> AsyncIterator[Document]:
        """
        TBD: Convert web URL to PDF.

        1. Render page with Puppeteer/Playwright (handles JS-heavy sites)
        2. Export as PDF
        3. Upload PDF to MinIO
        4. Publish document.process → Ingestor handles via nv-ingest

        Research needed:
        - Puppeteer vs Playwright (Playwright has better Python support)
        - Headless browser container (playwright-python docker image)
        - Cookie/auth handling for authenticated pages
        - Sitemap crawling for multi-page sites
        """
        raise NotImplementedError("Web provider TBD")
```

---

## Checkpoint-Based State Management

**Pattern:** Connectors use checkpoints for resumable, fault-tolerant syncing.

### Base Checkpoint

```python
class ConnectorCheckpoint(BaseModel):
    """Base checkpoint - all providers extend this."""
    has_more: bool  # Whether more documents remain to retrieve
```

### Google Drive Checkpoint

```python
class GoogleDriveCheckpoint(ConnectorCheckpoint):
    """Multi-stage checkpoint for Google Drive."""

    # Current retrieval stage
    completion_stage: DriveRetrievalStage  # START → MY_DRIVE → SHARED_DRIVES → FOLDERS → DONE

    # Per-user progress (for service account impersonation)
    completion_map: dict[str, StageCompletion]

    # Deduplication
    all_retrieved_file_ids: set[str]  # Prevents duplicates across runs
    retrieved_folder_and_drive_ids: set[str]

    # Cached data (fetched once, reused)
    drive_ids_to_retrieve: list[str] | None
    folder_ids_to_retrieve: list[str] | None
    user_emails: list[str] | None  # For service account


class StageCompletion(BaseModel):
    """Progress within a retrieval stage."""
    stage: DriveRetrievalStage
    completed_until: float  # Last file modified timestamp
    current_folder_or_drive_id: str | None  # What we're processing
    next_page_token: str | None  # API pagination state
    processed_drive_ids: set[str]  # Don't retry these


class DriveRetrievalStage(str, Enum):
    START = "start"
    USER_EMAILS = "user_emails"  # Service account: fetch all org users
    MY_DRIVE_FILES = "my_drive_files"  # Each user's personal drive
    DRIVE_IDS = "drive_ids"  # Fetch shared drive IDs
    SHARED_DRIVE_FILES = "shared_drive_files"  # Files from shared drives
    FOLDER_FILES = "folder_files"  # Custom folder crawling
    DONE = "done"
```

### OneDrive/SharePoint Checkpoint

```python
class SharePointCheckpoint(ConnectorCheckpoint):
    """Deque-based checkpoint for SharePoint/OneDrive."""

    # Sites to process (deque for FIFO)
    cached_site_descriptors: deque[SiteDescriptor] | None
    current_site_descriptor: SiteDescriptor | None

    # Drives within current site
    cached_drive_names: deque[str] | None
    current_drive_name: str | None
```

### Teams Checkpoint

```python
class TeamsCheckpoint(ConnectorCheckpoint):
    """Team-list checkpoint for Teams."""

    todo_team_ids: list[str] | None  # Teams remaining to process
```

### Resumption Flow

```python
async def load_from_checkpoint(
    self,
    start: float,
    end: float,
    checkpoint: CT,
) -> AsyncIterator[Document]:
    """
    Resume from checkpoint after failure.

    1. Check completion_stage to know where we stopped
    2. Use completed_until timestamp to skip already-processed files
    3. Use next_page_token to resume API pagination
    4. Use all_retrieved_file_ids for deduplication
    """
    if checkpoint.completion_stage == DriveRetrievalStage.MY_DRIVE_FILES:
        # Resume from last timestamp
        for file in self.get_files(start=checkpoint.completed_until):
            if file.id in checkpoint.all_retrieved_file_ids:
                continue  # Already processed

            checkpoint.all_retrieved_file_ids.add(file.id)
            checkpoint.completed_until = file.modified_time
            yield file

    # Return checkpoint for persistence
    checkpoint.has_more = self.has_more_files()
    return checkpoint
```

---

## Permission Sync System

**Purpose:** Track who has access to each document for search filtering.

### ExternalAccess Model

```python
@dataclass(frozen=True)
class ExternalAccess:
    """Document access permissions."""

    # Emails of users with direct access
    external_user_emails: set[str]

    # Group IDs with access (e.g., "engineering-team")
    external_user_group_ids: set[str]

    # Whether document is publicly accessible
    is_public: bool

    @classmethod
    def public(cls) -> "ExternalAccess":
        """Document accessible to everyone."""
        return cls(
            external_user_emails=set(),
            external_user_group_ids=set(),
            is_public=True,
        )

    @classmethod
    def empty(cls) -> "ExternalAccess":
        """Fallback when permissions unknown."""
        return cls(
            external_user_emails=set(),
            external_user_group_ids=set(),
            is_public=False,
        )
```

### Permission Fetching Per Provider

**Google Drive:**
```python
async def get_external_access(self, file: DriveFile) -> ExternalAccess:
    """Fetch permissions from Drive API."""
    permissions = await self.drive_service.permissions().list(
        fileId=file.id,
        fields="permissions(emailAddress, type, role)"
    ).execute()

    emails = set()
    is_public = False

    for perm in permissions.get("permissions", []):
        if perm["type"] == "anyone":
            is_public = True
        elif perm["type"] == "user":
            emails.add(perm["emailAddress"])

    return ExternalAccess(
        external_user_emails=emails,
        external_user_group_ids=set(),
        is_public=is_public,
    )
```

**OneDrive/SharePoint:**
```python
async def get_external_access(self, item: DriveItem) -> ExternalAccess:
    """Fetch sharing permissions."""
    permissions = await self.graph_client.get_item_permissions(item.id)

    emails = set()
    groups = set()
    is_public = False

    for perm in permissions:
        if perm.link and perm.link.scope == "anonymous":
            is_public = True
        elif perm.granted_to_v2:
            if perm.granted_to_v2.user:
                emails.add(perm.granted_to_v2.user.email)
            if perm.granted_to_v2.group:
                groups.add(perm.granted_to_v2.group.id)

    return ExternalAccess(
        external_user_emails=emails,
        external_user_group_ids=groups,
        is_public=is_public,
    )
```

### Document with Permissions

```python
class Document(BaseModel):
    id: str
    source_id: str
    url: str
    title: str
    content_type: str
    content_hash: str | None
    doc_updated_at: datetime | None

    # Permission info
    external_access: ExternalAccess | None
    primary_owners: list[str] | None  # Owner emails


# Lightweight version for permission-only sync
class SlimDocument(BaseModel):
    id: str
    external_access: ExternalAccess | None
```

### Database Storage

```sql
-- Document permissions table
CREATE TABLE document_permissions (
    document_id INTEGER REFERENCES documents(id),
    user_email VARCHAR(255),
    group_id VARCHAR(255),
    is_public BOOLEAN DEFAULT FALSE,
    synced_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (document_id)
);

CREATE INDEX idx_doc_perm_email ON document_permissions(user_email);
CREATE INDEX idx_doc_perm_group ON document_permissions(group_id);
```

---

## Service Structure

```
src/connector/
├── __init__.py
├── main.py                 # Entry point
├── config.py               # Pydantic settings
├── logic/
│   ├── __init__.py
│   ├── exceptions.py       # Domain exceptions
│   ├── connector_service.py
│   ├── checkpoint.py       # Checkpoint models
│   ├── permissions.py      # ExternalAccess, permission fetching
│   └── providers/
│       ├── __init__.py
│       ├── base.py         # BaseProvider ABC
│       ├── onedrive.py
│       └── google_drive.py
├── middleware/
│   └── error_handler.py
└── Dockerfile
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
| All docs processed | `active` | Ingestor (not Connector) |

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
├── test_checkpoint.py
├── test_permissions.py
├── test_providers/
│   ├── test_onedrive_provider.py
│   └── test_google_drive_provider.py
└── test_downloader.py
```

### What to Test

| Component | Test Coverage |
|-----------|---------------|
| ConnectorService | Event handling, routing, checkpoint persistence |
| Checkpoint | Stage transitions, resumption, deduplication |
| Permissions | ExternalAccess building, permission fetching |
| OneDriveProvider | Delta API, cTag comparison, file download |
| GoogleDriveProvider | Changes API, PDF export, checkpoint stages |
| Downloader | MinIO upload, size cap handling |

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
- [Ingestor Service](./ingestor-service.md) - Processes downloaded files (replaces Semantic)
