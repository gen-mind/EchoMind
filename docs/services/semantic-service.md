# Semantic Service

> **Service:** `echomind-semantic`
> **Protocol:** NATS (subscriber)
> **Port:** 8080 (health check only)

---

## What It Does

The Semantic Service handles **content extraction and text chunking**:

- Extracts text from documents (PDF, DOCX, web pages, YouTube)
- Routes audio files to Voice service
- Routes images/videos to Vision service
- Splits text into chunks using configurable strategies
- Sends chunks to Embedder for vectorization
- Updates document status in database

---

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph SemanticService["echomind-semantic"]
        NATS_SUB[NATS Subscriber]
        ROUTER[Content Router]
        PDF[PDF Extractor]
        URL[URL Extractor]
        YT[YouTube Extractor]
        CHUNKER[Text Chunker]
        NATS_PUB[NATS Publisher]
        GRPC[gRPC Client]
    end

    subgraph External
        NATS[(NATS)]
        MINIO[(MinIO)]
        DB[(PostgreSQL)]
        EMBED[echomind-embedder]
        VOICE[echomind-voice]
        VISION[echomind-vision]
    end

    NATS -->|document.process| NATS_SUB
    NATS -->|connector.sync.web/file| NATS_SUB
    NATS_SUB --> ROUTER
    ROUTER -->|pdf/docx| PDF
    ROUTER -->|url| URL
    ROUTER -->|youtube| YT
    ROUTER -->|audio| NATS_PUB
    ROUTER -->|image/video| NATS_PUB
    NATS_PUB -->|audio.transcribe| VOICE
    NATS_PUB -->|image.analyze| VISION
    PDF & URL & YT --> CHUNKER
    CHUNKER --> GRPC
    GRPC -->|EmbedRequest| EMBED
    PDF --> MINIO
    CHUNKER --> DB
```

### Processing Flow

```mermaid
sequenceDiagram
    participant N as NATS
    participant S as Semantic
    participant M as MinIO
    participant V as Voice
    participant I as Vision
    participant E as Embedder (gRPC)
    participant Q as Qdrant
    participant DB as PostgreSQL

    N->>S: document.process

    alt Audio file
        S->>N: audio.transcribe
        N->>V: Process audio
        V-->>S: Transcript text
    else Image/Video
        S->>N: image.analyze
        N->>I: Process image
        I-->>S: Description text
    else PDF/DOCX
        S->>M: Download file
        M-->>S: File bytes
        S->>S: pymupdf4llm extract
    else URL
        S->>S: BS4/Selenium fetch
    else YouTube
        S->>S: youtube_transcript_api
    end

    S->>S: Chunk text
    S->>E: EmbedRequest (gRPC)
    E->>Q: Store vectors
    E-->>S: EmbedResponse

    S->>DB: Update document (chunk_count, status=completed)
    S->>DB: Update connector (status=active)
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| NATS Client | nats-py (async) |
| PDF Extraction | pymupdf4llm |
| Web Scraping | BeautifulSoup4, Selenium |
| YouTube | youtube_transcript_api |
| Chunking | langchain text splitters |
| gRPC Client | grpcio |

---

## Database Tables Used

| Table | Operations | Reference |
|-------|------------|-----------|
| `documents` | Read, Update | [DB Schema](../db-schema.md#documents) |
| `connectors` | Update (status) | [DB Schema](../db-schema.md#connectors) |

---

## Proto Definitions Used

| Proto | Direction | Description |
|-------|-----------|-------------|
| `ConnectorSyncRequest` | Subscribe | For web/file connectors |
| `DocumentProcessRequest` | Subscribe | From connector service |
| `AudioTranscribeRequest` | Publish | To voice service |
| `ImageAnalyzeRequest` | Publish | To vision service |
| `EmbedRequest` | gRPC | To embedder service |

See [Proto Definitions](../proto-definitions.md)

---

## NATS Messaging

### Subscriptions (Incoming)

| Subject | Payload | From |
|---------|---------|------|
| `connector.sync.web` | `ConnectorSyncRequest` | Orchestrator |
| `connector.sync.file` | `ConnectorSyncRequest` | Orchestrator |
| `document.process` | `DocumentProcessRequest` | Connector |

### Publications (Outgoing)

| Subject | Payload | To |
|---------|---------|-----|
| `audio.transcribe` | `AudioTranscribeRequest` | Voice |
| `image.analyze` | `ImageAnalyzeRequest` | Vision |

### Consumer Configuration

```python
subscriber = JetStreamEventSubscriber(
    nats_url="nats://nats:4222",
    stream_name="ECHOMIND",
    subjects=[
        "connector.sync.web",
        "connector.sync.file",
        "document.process"
    ],
    durable_name="semantic-consumer",
    queue_group="semantic-workers"
)
```

---

## Extractors

### PDF Extractor

```python
class PDFExtractor:
    """Extract text from PDF using pymupdf4llm."""

    async def extract(self, file_path: str) -> str:
        import pymupdf4llm
        return pymupdf4llm.to_markdown(file_path)
```

### URL Extractor

```python
class URLExtractor:
    """Extract text from web pages."""

    async def extract(self, url: str) -> str:
        if self.requires_javascript(url):
            return await self.selenium_extract(url)
        else:
            return await self.bs4_extract(url)

    async def bs4_extract(self, url: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text(separator="\n", strip=True)
```

### YouTube Extractor

```python
class YouTubeExtractor:
    """Extract transcript from YouTube videos."""

    async def extract(self, url: str) -> str:
        from youtube_transcript_api import YouTubeTranscriptApi
        video_id = self.parse_video_id(url)
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([t["text"] for t in transcript])
```

---

## Chunking Strategies

Configured via `SEMANTIC_CHUNK_STRATEGY` environment variable.

### Character-Based (Default)

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]
)
chunks = splitter.split_text(text)
```

### Semantic Chunking

```python
from langchain_experimental.text_splitter import SemanticChunker
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
splitter = SemanticChunker(embeddings=model)
chunks = splitter.split_text(text)
```

---

## Content Type Routing

```python
def route_content(content_type: str) -> str:
    """Determine processing route based on MIME type."""

    if content_type in ["audio/mpeg", "audio/wav", "audio/mp3"]:
        return "voice"
    elif content_type in ["image/jpeg", "image/png", "video/mp4"]:
        return "vision"
    elif content_type == "application/pdf":
        return "pdf"
    elif content_type in ["text/html", "application/xhtml+xml"]:
        return "url"
    else:
        return "text"  # Generic text extraction
```

---

## Service Structure

```
src/services/semantic/
├── main.py                 # Entry point
├── nats/
│   ├── subscriber.py
│   └── publisher.py
├── logic/
│   ├── semantic_service.py
│   ├── extractors/
│   │   ├── base.py
│   │   ├── pdf.py
│   │   ├── url.py
│   │   ├── youtube.py
│   │   └── text.py
│   ├── chunkers/
│   │   ├── base.py
│   │   ├── character.py
│   │   └── semantic.py
│   ├── router.py           # Content type routing
│   └── exceptions.py
├── grpc/
│   └── embedder_client.py
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

# Embedder (gRPC)
EMBEDDER_GRPC_HOST=echomind-embedder
EMBEDDER_GRPC_PORT=50051

# Chunking
SEMANTIC_CHUNK_STRATEGY=character   # character | semantic
SEMANTIC_CHUNK_SIZE=1000
SEMANTIC_CHUNK_OVERLAP=200
SEMANTIC_CHUNK_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Selenium (for JS-heavy pages)
SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub
```

---

## Status Updates

| When | Status | Table |
|------|--------|-------|
| Processing starts | `processing` | documents |
| Processing succeeds | `completed` | documents |
| Processing fails | `failed` | documents |
| All docs in batch done | `active` | connectors |
| Any doc fails | `error` | connectors |

---

## Health Check

```bash
GET :8080/healthz

# Response
{
  "status": "healthy",
  "nats": "connected",
  "embedder_grpc": "connected",
  "minio": "connected",
  "database": "connected"
}
```

---

## Unit Testing (MANDATORY)

All service logic MUST have unit tests. See [Testing Standards](../../.claude/rules/testing.md).

### Test Location

```
tests/unit/semantic/
├── test_semantic_service.py
├── test_extractors/
│   ├── test_pdf_extractor.py
│   ├── test_url_extractor.py
│   └── test_youtube_extractor.py
├── test_chunkers/
│   ├── test_character_chunker.py
│   └── test_semantic_chunker.py
└── test_router.py
```

### What to Test

| Component | Test Coverage |
|-----------|---------------|
| SemanticService | Event handling, routing |
| PDFExtractor | Text extraction from PDF |
| URLExtractor | HTML parsing, JS detection |
| YouTubeExtractor | Video ID parsing, transcript fetch |
| CharacterChunker | Chunk size, overlap |
| ContentRouter | MIME type routing |

### Example

```python
# tests/unit/semantic/test_extractors/test_pdf_extractor.py
class TestPDFExtractor:
    @pytest.fixture
    def extractor(self):
        return PDFExtractor()

    @pytest.mark.asyncio
    async def test_extracts_text_from_pdf(self, extractor, tmp_path):
        pdf_path = tmp_path / "test.pdf"
        create_test_pdf(pdf_path, "Hello World")

        text = await extractor.extract(str(pdf_path))

        assert "Hello World" in text

# tests/unit/semantic/test_chunkers/test_character_chunker.py
class TestCharacterChunker:
    def test_splits_text_into_chunks(self):
        chunker = CharacterChunker(chunk_size=100, overlap=20)
        text = "A" * 250

        chunks = chunker.split(text)

        assert len(chunks) == 3
        assert all(len(c) <= 100 for c in chunks)
```

### Minimum Coverage

- **70%** for service classes
- **80%** for extractors and chunkers

---

## References

- [NATS Messaging](../nats-messaging.md) - Message flow documentation
- [Proto Definitions](../proto-definitions.md) - Message schemas
- [Connector Service](./connector-service.md) - Sends document.process
- [Voice Service](./voice-service.md) - Receives audio.transcribe
- [Vision Service](./vision-service.md) - Receives image.analyze
- [Embedder Service](./embedder-service.md) - Receives EmbedRequest (gRPC)
