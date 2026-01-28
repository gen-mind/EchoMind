# Ingestor Service Implementation Plan

> **Service:** `echomind-ingestor`
> **Status:** Planning
> **Created:** 2026-01-28
> **Replaces:** `echomind-semantic`, `echomind-voice`, `echomind-vision`

---

## Executive Summary

The Ingestor service is the **most critical service** in the EchoMind pipeline. It transforms raw documents into searchable vector embeddings. This plan details the implementation strategy, risk assessment, and evaluation scoring.

---

## 1. Information Assessment

### 1.1 What We Know (Verified)

| Item | Source | Confidence |
|------|--------|------------|
| nv-ingest-api package exists | `pip index versions` | 100% |
| Package version: 26.1.2 (latest) | PyPI | 100% |
| NATS subjects: `document.process`, `connector.sync.web`, `connector.sync.file` | nats-messaging.md | 100% |
| Existing service patterns (connector, embedder) | Source code | 100% |
| DocumentProcessRequest protobuf exists | connector_service.py:415 | 100% |
| Embedder gRPC interface (EmbedRequest, EmbedResponse) | embedding.proto | 100% |
| Database schema (documents table) | db-schema.md | 100% |
| MinIO integration pattern | connector/main.py | 100% |

### 1.2 What We Need to Verify (Uncertain)

| Item | Risk | Mitigation |
|------|------|------------|
| nv-ingest-api actual API surface | Medium | Install and test locally before coding |
| YOLOX NIM requirement for table detection | High | Check if optional or required |
| Riva NIM requirement for audio | High | Check if optional or required |
| Token-based chunking parameters | Low | Use defaults from docs, tune later |
| Multimodal embedding support in current Embedder | High | **Embedder needs update** |

### 1.3 What We Don't Know (Gaps)

| Gap | Impact | Action Required |
|-----|--------|-----------------|
| nv-ingest-api internal implementation | Medium | Read package source after install |
| NIMs (YOLOX, Riva) deployment | High | Research containerized deployment |
| HuggingFace token for Llama tokenizer | Medium | May need authentication |
| GPU requirements for nv-ingest | High | Profile memory/compute needs |

---

## 2. Dependency Analysis

### 2.1 Python Dependencies

```toml
[project]
dependencies = [
    # Core nv-ingest
    "nv-ingest-api>=26.1.0",

    # Data handling
    "pandas>=2.0.0",
    "pypdfium2>=4.0.0",

    # Network
    "grpcio>=1.60.0",
    "nats-py>=2.6.0",
    "minio>=7.2.0",

    # Database
    "asyncpg>=0.29.0",
    "sqlalchemy[asyncio]>=2.0.0",

    # Configuration
    "pydantic-settings>=2.0.0",

    # Shared library
    "echomind-lib",  # Local package
]
```

### 2.2 External Service Dependencies

| Service | Required | Status | Notes |
|---------|----------|--------|-------|
| PostgreSQL | Yes | ✅ Running | Document status updates |
| MinIO | Yes | ✅ Running | File download |
| NATS | Yes | ✅ Running | Message subscription |
| Qdrant | No | ✅ Running | Via Embedder only |
| Embedder (gRPC) | Yes | ✅ Running | Needs multimodal update |
| YOLOX NIM | Optional | ❌ Not deployed | Table/chart detection |
| Riva NIM | Optional | ❌ Not deployed | Audio transcription |

### 2.3 Dependency Risk Assessment

**Risk Level: MEDIUM-HIGH**

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| nv-ingest-api API changes | Low | High | Pin version, write adapter layer |
| YOLOX NIM unavailable | High | Medium | Implement without table detection first |
| Riva NIM unavailable | High | Medium | Skip audio initially, add later |
| Embedder multimodal missing | Certain | High | **Must update Embedder first** |

---

## 3. Implementation Phases

### Phase 3.1: Foundation (No External NIMs)

**Goal:** Basic PDF/DOCX/TXT extraction without table detection or audio.

**Duration Estimate:** Not provided per policy

**Tasks:**
1. Create service structure (`src/ingestor/`)
2. Implement config.py with Pydantic settings
3. Implement NATS subscriber (copy pattern from connector)
4. Implement MinIO file download
5. Integrate nv-ingest-api for basic extraction
6. Implement tokenizer-based chunking
7. Create Embedder gRPC client
8. Write unit tests (target: 80+ tests)

**Files to Create:**
```
src/ingestor/
├── __init__.py
├── main.py                     # NATS subscriber entry point
├── config.py                   # Pydantic settings (25+ options)
├── Dockerfile
├── requirements.txt
│
├── logic/
│   ├── __init__.py
│   ├── exceptions.py           # Domain exceptions (10+)
│   ├── ingestor_service.py     # Main orchestration
│   ├── document_processor.py   # nv-ingest wrapper
│   ├── chunker.py              # Tokenizer-based chunking
│   └── content_router.py       # MIME type routing
│
├── grpc/
│   ├── __init__.py
│   └── embedder_client.py      # gRPC client for Embedder
│
└── middleware/
    ├── __init__.py
    └── error_handler.py
```

**Success Criteria:**
- [ ] Process PDF files end-to-end
- [ ] Process DOCX files end-to-end
- [ ] Process TXT/MD files end-to-end
- [ ] Tokenizer chunking working
- [ ] Embedder integration working
- [ ] 80+ unit tests passing
- [ ] mypy: 0 errors
- [ ] ruff: 0 errors

### Phase 3.2: Multimodal Support

**Goal:** Add image and HTML support.

**Prerequisite:** Phase 3.1 complete

**Tasks:**
1. Add HTML extraction via nv-ingest
2. Add image extraction (bmp, jpeg, png, tiff)
3. Update Embedder proto for multimodal
4. Update Embedder service for VLM model
5. Wire image embeddings through pipeline
6. Add unit tests for multimodal

**Proto Changes Required (embedding.proto):**
```protobuf
message EmbedRequest {
  repeated string texts = 1;
  string input_type = 2;        // NEW: "query" | "passage"
  string modality = 3;          // NEW: "text" | "image" | "image_text"
  repeated bytes images = 4;    // NEW: Base64 images for VLM
  string collection_name = 5;   // NEW: Qdrant collection
  int32 document_id = 6;        // NEW: For payload metadata
}
```

**Success Criteria:**
- [ ] Process HTML files
- [ ] Process image files (OCR)
- [ ] Embedder supports `modality` field
- [ ] VLM embedding working for tables/charts
- [ ] Unit tests for all new code

### Phase 3.3: Audio Support (Requires Riva NIM)

**Goal:** Add audio transcription.

**Prerequisite:** Riva NIM deployed

**Tasks:**
1. Deploy Riva NIM container
2. Add audio extraction via nv-ingest
3. Configure Riva endpoint
4. Wire transcription through pipeline
5. Add unit tests

**Decision Point:** If Riva NIM unavailable, defer to future phase.

### Phase 3.4: Advanced Features (Requires YOLOX NIM)

**Goal:** Table/chart detection.

**Prerequisite:** YOLOX NIM deployed

**Tasks:**
1. Deploy YOLOX NIM container
2. Enable table/chart detection in nv-ingest
3. Route detected tables to VLM embedding
4. Add unit tests

**Decision Point:** If YOLOX NIM unavailable, defer to future phase.

---

## 4. Proto Schema Updates

### 4.1 New Proto: ingestor.proto

```protobuf
syntax = "proto3";
package echomind.internal;

// Document processing request (already exists in semantic.proto)
// Reuse existing DocumentProcessRequest

// Ingestor-specific messages
message ChunkMetadata {
  int32 chunk_index = 1;
  int32 start_offset = 2;
  int32 end_offset = 3;
  string content_type = 4;      // "text" | "table" | "chart" | "image"
}

message ProcessedChunk {
  string content = 1;
  ChunkMetadata metadata = 2;
  bytes image_data = 3;         // For tables/charts as images
}

message DocumentProcessResult {
  int32 document_id = 1;
  bool success = 2;
  int32 chunk_count = 3;
  string error_message = 4;
}
```

### 4.2 Updated Proto: embedding.proto

```protobuf
syntax = "proto3";
package echomind.internal;

message EmbedRequest {
  repeated string texts = 1;
  string input_type = 2;        // "query" | "passage"
  string modality = 3;          // "text" | "image" | "image_text"
  repeated bytes images = 4;    // Base64 images
  string collection_name = 5;   // Qdrant collection
  int32 document_id = 6;        // Document ID for payload
  repeated ChunkMetadata metadata = 7;
}

message ChunkMetadata {
  int32 chunk_index = 1;
  string content_type = 2;      // "text" | "table" | "chart"
}

message EmbedResponse {
  repeated Embedding embeddings = 1;
  bool success = 2;
  int32 vectors_stored = 3;
  string error = 4;
}

service EmbedService {
  rpc Embed(EmbedRequest) returns (EmbedResponse);
  rpc GetDimension(DimensionRequest) returns (DimensionResponse);
}
```

---

## 5. Configuration Schema

```python
class IngestorSettings(BaseSettings):
    """Ingestor service configuration."""

    # Service
    enabled: bool = True
    health_port: int = 8080
    log_level: str = "INFO"

    # Database
    database_url: str
    database_echo: bool = False

    # NATS
    nats_url: str = "nats://nats:4222"
    nats_user: str | None = None
    nats_password: str | None = None
    nats_stream_name: str = "ECHOMIND"
    nats_consumer_name: str = "ingestor-consumer"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool = False
    minio_bucket: str = "documents"

    # Embedder (gRPC)
    embedder_host: str = "embedder"
    embedder_port: int = 50051
    embedder_timeout: int = 60

    # nv-ingest extraction
    extract_method: str = "pdfium"  # pdfium | nemotron_parse
    extract_tables: bool = False     # Requires YOLOX NIM
    extract_charts: bool = False     # Requires YOLOX NIM
    extract_images: bool = False

    # Chunking
    chunk_size: int = 512           # Tokens, not characters
    chunk_overlap: int = 50
    tokenizer: str = "meta-llama/Llama-3.2-1B"

    # NIMs (optional)
    yolox_endpoint: str | None = None
    riva_endpoint: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="INGESTOR_",
        env_file=".env",
    )
```

---

## 6. Risk Assessment Matrix

| Risk | Probability | Impact | Severity | Mitigation |
|------|-------------|--------|----------|------------|
| nv-ingest-api incompatibility | Low | High | Medium | Pin version, adapter layer |
| YOLOX NIM not available | High | Medium | Medium | Skip table detection Phase 3.1 |
| Riva NIM not available | High | Medium | Medium | Skip audio Phase 3.1 |
| Embedder needs update | Certain | High | **High** | **Do Phase 3.2 first or parallel** |
| HuggingFace auth required | Medium | Low | Low | Document setup steps |
| Memory issues with large PDFs | Medium | Medium | Medium | Implement streaming, limits |
| GPU memory exhaustion | Medium | High | Medium | Model caching, queue limits |
| Tokenizer model download | Low | Low | Low | Pre-download in Dockerfile |

---

## 7. Blockers and Dependencies

### 7.1 Hard Blockers (Must resolve before starting)

| Blocker | Owner | Status | Resolution |
|---------|-------|--------|------------|
| Embedder multimodal support | Team | ❌ Not started | Update embedding.proto, add VLM model |

### 7.2 Soft Blockers (Can proceed without)

| Blocker | Owner | Status | Impact if Missing |
|---------|-------|--------|-------------------|
| YOLOX NIM deployment | Ops | ❌ Not deployed | No table/chart detection |
| Riva NIM deployment | Ops | ❌ Not deployed | No audio transcription |
| HuggingFace token | Dev | ❓ Unknown | May block tokenizer download |

---

## 8. Test Strategy

### 8.1 Unit Test Categories

| Category | Test Count | Coverage |
|----------|------------|----------|
| Config | 15+ | Settings validation, defaults |
| Exceptions | 12+ | All exception classes |
| IngestorService | 25+ | Message handling, orchestration |
| DocumentProcessor | 20+ | nv-ingest integration mocks |
| ContentRouter | 10+ | MIME type routing |
| Chunker | 15+ | Token-based splitting |
| EmbedderClient | 15+ | gRPC client mocks |
| **Total** | **112+** | |

### 8.2 Mock Strategy

| External Dependency | Mock Approach |
|---------------------|---------------|
| nv-ingest-api | Mock `extract_primitives_*` functions |
| Embedder gRPC | Mock gRPC stub |
| MinIO | Mock file download |
| PostgreSQL | AsyncMock session |
| NATS | Mock subscriber |

---

## 9. Evaluation Scoring

### 9.1 Plan Completeness Score

| Criterion | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| Information completeness | 20% | 8/10 | 1.6 |
| Dependency clarity | 15% | 9/10 | 1.35 |
| Risk identification | 15% | 9/10 | 1.35 |
| Implementation detail | 20% | 7/10 | 1.4 |
| Test strategy | 10% | 8/10 | 0.8 |
| Proto definitions | 10% | 8/10 | 0.8 |
| Configuration schema | 10% | 9/10 | 0.9 |
| **Total** | **100%** | | **8.2/10** |

### 9.2 Score Breakdown

**Strengths (+):**
- Clear dependency mapping
- Phased implementation approach
- Comprehensive test strategy
- Detailed proto changes
- Risk mitigation documented

**Weaknesses (-):**
- nv-ingest-api actual API not verified (need to install and test)
- NIM deployment requirements unclear
- Embedder update scope not fully defined
- No performance benchmarks planned

### 9.3 Confidence Level

**Overall Confidence: 75%**

| Aspect | Confidence |
|--------|------------|
| Can implement basic extraction | 90% |
| Can implement tokenizer chunking | 85% |
| Can integrate with Embedder | 70% (needs proto update) |
| Can process all file types | 60% (depends on NIMs) |

---

## 10. Recommendations

### 10.1 Before Starting Implementation

1. **Install and test nv-ingest-api locally**
   ```bash
   pip install nv-ingest-api==26.1.2
   python -c "from nv_ingest_api.interface.extract import extract_primitives_from_pdf; print('OK')"
   ```

2. **Verify HuggingFace tokenizer access**
   ```bash
   python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('meta-llama/Llama-3.2-1B')"
   ```

3. **Update Embedder proto first** (or in parallel)
   - Add `input_type`, `modality`, `images` fields
   - Add `collection_name`, `document_id` for direct Qdrant storage

### 10.2 Implementation Order

1. **Embedder proto update** (blocker)
2. **Phase 3.1: Basic extraction** (PDF, DOCX, TXT)
3. **Phase 3.2: HTML + images** (after Embedder update)
4. **Phase 3.3: Audio** (when Riva NIM available)
5. **Phase 3.4: Tables/charts** (when YOLOX NIM available)

### 10.3 Decision Points

| Milestone | Decision |
|-----------|----------|
| After Phase 3.1 | Proceed to 3.2 or ship MVP? |
| After Phase 3.2 | Deploy NIMs or defer? |
| After Phase 3.3 | YOLOX worth the complexity? |

---

## 11. Open Questions

1. **Should Embedder store directly to Qdrant?**
   - Current: Yes (Embedder has Qdrant client)
   - Alternative: Return vectors, Ingestor stores
   - Recommendation: Keep current (Embedder stores)

2. **Chunk ID generation strategy?**
   - Option A: `{document_id}_{chunk_index}` (deterministic, idempotent)
   - Option B: UUID per chunk (simpler, not idempotent)
   - Recommendation: Option A for crash recovery

3. **How to handle very large files (>100MB)?**
   - Option A: Reject with error
   - Option B: Stream processing
   - Recommendation: Set limit initially, add streaming later

4. **Should Ingestor update document status or return result?**
   - Current plan: Ingestor updates PostgreSQL directly
   - Alternative: Return result, let caller update
   - Recommendation: Direct update (matches connector pattern)

---

## 12. Approval Checklist

- [ ] nv-ingest-api installation verified
- [ ] HuggingFace tokenizer access verified
- [ ] Embedder proto update scope agreed
- [ ] NIM deployment decision made
- [ ] Phase 3.1 scope approved
- [ ] Test target (112+ tests) approved

---

## References

- [Ingestor Service Documentation](../services/ingestor-service.md)
- [NATS Messaging](../nats-messaging.md)
- [Architecture](../architecture.md)
- [DB Schema](../db-schema.md)
- [Connector Service](../../src/connector/) - Pattern reference
- [Embedder Service](../../src/embedder/) - Pattern reference
