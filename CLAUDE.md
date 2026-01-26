# EchoMind Development Guidelines

> **Note**: Detailed rules in `.claude/rules/`. Task-specific docs in `agent_docs/`.

---

## Project Overview

EchoMind is a **Python-only Agentic RAG** platform with multi-step retrieval, tools, and memory.

| Component | Technology |
|-----------|------------|
| Agent Framework | Semantic Kernel |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL |
| API | FastAPI + WebSocket |
| Message Queue | NATS JetStream |
| Auth | Authentik (OIDC) |
| LLM Inference | TGI/vLLM or OpenAI/Anthropic |

**Architecture**: Single-tenant with per-user/group/org vector collections.

### Domain Concepts

| Entity | Description |
|--------|-------------|
| **Assistant** | AI personality with prompts, linked to LLM |
| **Connector** | Data source (Teams, Drive) with sync state |
| **Document** | Ingested content, chunked and embedded |
| **Chat Session** | Conversation thread |
| **Agent Memory** | Long-term episodic/semantic memory |

---

## Critical Rules (Always Apply)

1. **Import from `echomind_lib`** - Never duplicate code across services
2. **Proto = Source of Truth** - Never hand-write Pydantic models. Regenerate: `make gen-proto`
3. **Never edit generated code** in `echomind_lib/models/` or `web/src/models/`
4. **Emoji logging required** - See `.claude/rules/logging.md`
5. **Unit tests MANDATORY** - All services and web components MUST have unit tests. See `.claude/rules/testing.md`

---

## Directory Structure

```
echomind/
├── src/
│   ├── api/                 # FastAPI REST + WebSocket gateway
│   ├── search/              # Agentic search (Semantic Kernel, gRPC)
│   ├── orchestrator/        # Scheduler (APScheduler, NATS pub)
│   ├── connector/           # Data source fetcher (NATS sub)
│   ├── semantic/            # Content extraction + chunking (NATS sub)
│   ├── embedder/            # Text → Vector (gRPC)
│   ├── voice/               # Whisper transcription (NATS sub)
│   ├── vision/              # BLIP + OCR (NATS sub)
│   ├── guardian/            # DLQ monitoring + alerting (NATS sub)
│   ├── migration/           # Alembic migrations (batch job)
│   ├── proto/               # Protocol Buffers (SOURCE OF TRUTH)
│   ├── echomind_lib/        # SHARED LIBRARY
│   └── web/                 # React client
├── deployment/
├── tests/
└── agent_docs/              # Task-specific AI context
```

---

## Service Architecture

ALL services MUST separate business logic from infrastructure:

```
src/{service}/
├── logic/               # Business logic (protocol-agnostic)
│   ├── exceptions.py    # Domain exceptions
│   └── *_service.py     # Service classes
├── middleware/          # Infrastructure concerns
│   └── error_handler.py # Protocol-specific error handling
└── [entry_points]       # HTTP routes, NATS subscribers, gRPC handlers
```

**Entry points are thin adapters:**
```python
# ✅ CORRECT
@router.get("/{user_id}")
async def get_user(user_id: int, db: DbSession) -> User:
    service = UserService(db)
    return await service.get_user_by_id(user_id)

# ❌ WRONG: Business logic in route
@router.get("/{user_id}")
async def get_user(user_id: int, db: DbSession):
    result = await db.execute(...)  # DB queries in route
```

**Services raise domain exceptions, middleware converts to protocol responses.**

---

## Service Patterns

### gRPC Service (embedder, search)

```python
import grpc
from concurrent import futures
from echomind_lib.helpers.device_checker import DeviceChecker

class EmbedServicer(EmbedServiceServicer):
    def GetEmbedding(self, request, context):
        start_time = time.time()
        try:
            if not request.contents:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "contents cannot be empty")

            result = SentenceEncoder.embed_batch(request.contents, request.model)
            logger.info("✅ Request processed")
            return EmbedResponse(embeddings=result)
        except grpc.RpcError:
            raise
        except Exception as e:
            logger.exception("❌ Request failed")
            context.abort(grpc.StatusCode.INTERNAL, str(e))
        finally:
            logger.info(f"⏰ Elapsed: {time.time() - start_time:.2f}s")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor())
    server.add_insecure_port(f"0.0.0.0:{grpc_port}")
    server.start()
    logger.info(f"👂 Listening on {grpc_port}")
    DeviceChecker.check_device()
    server.wait_for_termination()
```

### NATS Consumer Service (connector, semantic, voice, vision)

```python
import asyncio
import threading
from echomind_lib.helpers.readiness_probe import ReadinessProbe
from echomind_lib.db.nats_subscriber import JetStreamEventSubscriber

async def event_handler(msg: Msg):
    start_time = time.time()
    try:
        data = SemanticData()
        data.ParseFromString(msg.data)

        result = await process(data)

        if result is not None:
            await msg.ack_sync()
            logger.info(f"👍 Processed {result} items")
        else:
            await msg.nak()
            logger.error(f"❌ Failed for doc {data.document_id}")
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        await msg.nak()
    finally:
        logger.info(f"⏰ Elapsed: {time.time() - start_time:.2f}s")

async def main():
    # REQUIRED: Readiness probe for K8s
    probe = ReadinessProbe()
    threading.Thread(target=probe.start_server, daemon=True).start()

    while True:
        try:
            subscriber = JetStreamEventSubscriber(
                nats_url=nats_url,
                stream_name=stream_name,
                subject=subject
            )
            subscriber.set_event_handler(event_handler)
            await subscriber.connect_and_subscribe()

            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception:
            logger.exception("💀 Fatal error, restarting in 5s...")
            await asyncio.sleep(5)
```

### ML Model Caching (embedder, semantic, voice, vision)

```python
class SentenceEncoder:
    _cache_limit = int(os.getenv('MODEL_CACHE_LIMIT', 1))
    _lock = threading.Lock()
    _model_cache: dict[str, SentenceTransformer] = {}

    @classmethod
    def _get_model(cls, model_name: str) -> SentenceTransformer:
        with cls._lock:
            if model_name in cls._model_cache:
                return cls._model_cache[model_name]

            if len(cls._model_cache) >= cls._cache_limit:
                oldest = next(iter(cls._model_cache))
                del cls._model_cache[oldest]

            model = SentenceTransformer(model_name)
            cls._model_cache[model_name] = model
            return model

    @classmethod
    def embed_batch(cls, texts: list[str], model_name: str) -> list[list[float]]:
        model = cls._get_model(model_name)
        return [e.tolist() for e in model.encode(texts)]
```

---

## Naming & Ports

| Type | Pattern | Example |
|------|---------|---------|
| Services | `echomind-{name}` | `echomind-embedder` |
| Python packages | `snake_case` | `echomind_lib` |
| Classes | `PascalCase` | `DocumentCRUD` |
| Functions | `snake_case` | `process_document` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |

| Service Type | Port |
|--------------|------|
| gRPC | 50051 |
| HTTP/API | 8080 |
| Health check | 8080 (`/healthz`) |

---

## Environment Variables

Pattern: `{SERVICE_NAME}_{PARAMETER_NAME}`

```bash
API_PORT=8000
EMBEDDER_GRPC_PORT=50051
SEMANTIC_NATS_URL=nats://localhost:4222
```

---

## File Processing Pipeline

```
PDF/DOC/XLS     → semantic → pymupdf4llm → markdown → chunks → embeddings
URL             → semantic → BS4/Selenium → text → chunks → embeddings
YouTube         → semantic → youtube_transcript_api → chunks → embeddings
MP3/WAV (audio) → voice → Whisper → transcript → semantic → embeddings
JPEG/PNG        → vision → BLIP+OCR → description → semantic → embeddings
Video (MP4)     → vision → frame extraction → BLIP → description → semantic → embeddings
```

---

## Quick Reference

### Start a New Service
1. Create `src/{name}/` (services go directly under src/)
2. Import from `echomind_lib`
3. Define proto in `src/proto/internal/`
4. Run `make gen-proto`
5. Add ReadinessProbe
6. Create Dockerfile

### Add Proto Message
1. Edit `.proto` in `src/proto/`
2. Run `make gen-proto`
3. Import from `echomind_lib.models`

### Debug
1. Set `SERVICE_LOG_LEVEL=DEBUG`
2. Check `/healthz`
3. Check NATS dashboard

---

## Code Quality & Testing

- **TODO comments** for incomplete code
- **No unused code** - imports, functions, dependencies
- **Unit tests REQUIRED** for all new code:
  - Python services: `tests/unit/{service}/test_*.py`
  - Web components: `web/src/**/*.test.ts(x)`
  - Mock all external dependencies (DB, APIs, queues)
  - Minimum coverage: 70% services, 80% utilities
- See `.claude/rules/testing.md` for patterns and examples

---

## References

- `.claude/rules/` - Coding standards (path-scoped)
- `agent_docs/` - Task-specific context
- `docs/architecture.md` - System architecture
- `docs/proto-definitions.md` - Enum values, message schemas
- `docs/db-schema.md` - PostgreSQL table definitions
- `docs/api-spec.md` - REST/WebSocket API