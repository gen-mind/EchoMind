# Search Service

> **Service:** `echomind-search`
> **Protocol:** gRPC
> **Port:** 50051

---

## What It Does

The Search Service is the **agentic brain** of EchoMind. Powered by Semantic Kernel, it:

- Receives queries from the API service
- Decides what information to retrieve (and whether to retrieve at all)
- Executes multi-step retrieval strategies
- Invokes tools (calculator, web search, etc.)
- Manages conversation memory (short-term and long-term)
- Generates responses using the configured LLM
- Streams tokens back to the API

---

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph SearchService["echomind-search"]
        GRPC[gRPC Server]
        SK[Semantic Kernel]
        PLANNER[Planner]
        MEMORY[Memory Manager]
        TOOLS[Tool Router]
        RETRIEVER[Vector Retriever]
        RERANKER[Reranker]
    end

    subgraph External
        API[echomind-api]
        QDRANT[(Qdrant)]
        REDIS[(Redis)]
        LLM[LLM Router]
    end

    API -->|gRPC| GRPC
    GRPC --> SK
    SK --> PLANNER
    SK --> MEMORY
    SK --> TOOLS
    TOOLS --> RETRIEVER
    RETRIEVER --> QDRANT
    RETRIEVER --> RERANKER
    MEMORY --> REDIS
    SK --> LLM
```

### Agentic Flow

```mermaid
sequenceDiagram
    participant API as echomind-api
    participant SK as Semantic Kernel
    participant M as Memory
    participant Q as Qdrant
    participant L as LLM

    API->>SK: SearchRequest (query, session_id)

    SK->>M: Load conversation context
    M-->>SK: History + long-term memory

    SK->>SK: Think: What info do I need?

    alt Needs retrieval
        SK->>Q: Vector search (query embedding)
        Q-->>SK: Retrieved chunks
        SK->>SK: Rerank results
        SK->>SK: Evaluate: sufficient?

        opt Needs more
            SK->>Q: Refined search
            Q-->>SK: More chunks
        end
    end

    alt Needs tool
        SK->>SK: Execute tool (calc, web, etc.)
    end

    SK->>L: Generate with context
    loop Streaming
        L-->>SK: Token
        SK-->>API: StreamResponse (token)
    end

    SK->>M: Update memory
    SK-->>API: SearchComplete
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Framework | Semantic Kernel (Python) |
| gRPC | grpcio |
| Vector Search | Qdrant client |
| Memory | Redis (short-term), PostgreSQL (long-term) |
| Reranking | Cross-encoder (sentence-transformers) |
| LLM Client | Semantic Kernel connectors |

---

## Database Tables Used

| Table | Operations | Reference |
|-------|------------|-----------|
| `chat_sessions` | Read | [DB Schema](../db-schema.md#chat_sessions) |
| `chat_messages` | Read, Create | [DB Schema](../db-schema.md#chat_messages) |
| `assistants` | Read | [DB Schema](../db-schema.md#assistants) |
| `llms` | Read | [DB Schema](../db-schema.md#llms) |

---

## Proto Definitions Used

### gRPC Service Definition

```protobuf
// src/proto/internal/search.proto

service SearchService {
    rpc Search(SearchRequest) returns (stream SearchResponse);
    rpc Cancel(CancelRequest) returns (CancelResponse);
}

message SearchRequest {
    int32 session_id = 1;
    string query = 2;
    string mode = 3;           // "chat" or "search"
    int32 assistant_id = 4;
    repeated string collection_names = 5;  // Qdrant collections to search
}

message SearchResponse {
    oneof response {
        RetrievalStart retrieval_start = 1;
        RetrievalComplete retrieval_complete = 2;
        GenerationToken token = 3;
        GenerationComplete complete = 4;
        SearchError error = 5;
    }
}
```

See [Proto Definitions](../proto-definitions.md)

---

## NATS Messaging

**This service does NOT use NATS.** Communication is synchronous via gRPC:

| Direction | Protocol | Peer |
|-----------|----------|------|
| Incoming | gRPC | echomind-api |
| Outgoing | gRPC (stream) | echomind-api |

---

## Qdrant Integration

### Collections Accessed

Determined by user's scope and query context:

| Scope | Collection | Access |
|-------|------------|--------|
| User | `user_{user_id}` | Read |
| Group | `group_{scope_id}` | Read |
| Org | `org` | Read |

### Search Strategy

```python
async def search(query: str, collections: list[str], top_k: int = 10) -> list[Chunk]:
    # 1. Embed query
    query_embedding = await embedder.embed(query)

    # 2. Search each collection
    results = []
    for collection in collections:
        hits = await qdrant.search(
            collection_name=collection,
            query_vector=query_embedding,
            limit=top_k
        )
        results.extend(hits)

    # 3. Rerank combined results
    reranked = reranker.rerank(query, results)

    return reranked[:top_k]
```

---

## Memory Architecture

### Short-Term Memory (Redis)

- Conversation buffer (last N messages)
- Working memory (current task context)
- TTL: Session duration + 1 hour

### Long-Term Memory (PostgreSQL + Qdrant)

- Episodic memory (past interactions) → PostgreSQL
- Semantic memory (learned facts) → Qdrant
- Procedural memory (successful patterns) → PostgreSQL

```python
class MemoryManager:
    async def load_context(self, session_id: int, user_id: int) -> Context:
        # Short-term from Redis
        conversation = await redis.get(f"session:{session_id}:messages")

        # Long-term episodic
        past_sessions = await db.query(
            ChatMessage
        ).filter(user_id=user_id).limit(100)

        # Long-term semantic (similar past queries)
        similar = await qdrant.search(
            collection_name=f"memory_user_{user_id}",
            query_vector=current_query_embedding,
            limit=5
        )

        return Context(conversation, past_sessions, similar)
```

---

## Tools

Available tools the agent can invoke:

| Tool | Description |
|------|-------------|
| `vector_search` | Search Qdrant collections |
| `web_search` | External web search (if enabled) |
| `calculator` | Math operations |
| `date_time` | Current date/time |
| `code_executor` | Run Python code (sandboxed) |

```python
# Semantic Kernel plugin registration
kernel.add_plugin(VectorSearchPlugin(qdrant_client))
kernel.add_plugin(CalculatorPlugin())
kernel.add_plugin(DateTimePlugin())
```

---

## Service Structure

```
src/services/search/
├── main.py                 # gRPC server entry
├── grpc/
│   ├── server.py
│   └── servicer.py         # SearchServiceServicer
├── logic/
│   ├── search_service.py   # Core search logic
│   ├── planner.py          # SK planner configuration
│   ├── memory/
│   │   ├── manager.py
│   │   ├── short_term.py   # Redis
│   │   └── long_term.py    # PostgreSQL + Qdrant
│   ├── retrieval/
│   │   ├── retriever.py
│   │   └── reranker.py
│   └── tools/
│       ├── vector_search.py
│       ├── calculator.py
│       └── web_search.py
├── middleware/
│   └── error_handler.py
└── config.py
```

---

## Configuration

```bash
# gRPC Server
SEARCH_GRPC_HOST=0.0.0.0
SEARCH_GRPC_PORT=50051

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Redis (short-term memory)
REDIS_URL=redis://redis:6379/0

# Database (long-term memory)
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/echomind

# LLM
LLM_PROVIDER=tgi
LLM_ENDPOINT=http://inference:8080
LLM_MODEL=mistralai/Mistral-7B-Instruct-v0.2

# Reranker
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RERANKER_TOP_K=5

# Search
SEARCH_TOP_K=10
SEARCH_SIMILARITY_THRESHOLD=0.7
```

---

## Health Check

```bash
# gRPC health check (grpc_health_probe)
grpc_health_probe -addr=:50051

# HTTP health endpoint (optional)
GET :8080/healthz
```

---

## Future: Reranker Extraction

The reranker may become a separate service (`echomind-reranker`) if:
- Cross-encoder models prove too expensive for the search service
- Need to A/B test different reranking strategies
- Want to cache reranking results independently

---

## Unit Testing (MANDATORY)

All service logic MUST have unit tests. See [Testing Standards](../../.claude/rules/testing.md).

### Test Location

```
tests/unit/search/
├── test_search_service.py
├── test_retriever.py
├── test_reranker.py
├── test_memory_manager.py
└── test_tools.py
```

### What to Test

| Component | Test Coverage |
|-----------|---------------|
| SearchService | Query processing, tool routing |
| Retriever | Vector search logic |
| Reranker | Scoring, ranking logic |
| MemoryManager | Context loading, updates |
| Tools | Calculator, date_time, etc. |

### Example

```python
# tests/unit/search/test_retriever.py
class TestRetriever:
    @pytest.fixture
    def mock_qdrant(self):
        return AsyncMock()

    @pytest.fixture
    def retriever(self, mock_qdrant):
        return Retriever(mock_qdrant)

    @pytest.mark.asyncio
    async def test_search_returns_top_k_results(self, retriever, mock_qdrant):
        mock_qdrant.search.return_value = [mock_hit(0.9), mock_hit(0.8)]

        results = await retriever.search("query", top_k=2)

        assert len(results) == 2
        mock_qdrant.search.assert_called_once()
```

### Minimum Coverage

- **70%** for service classes
- **80%** for retrieval/reranking logic

---

## References

- [Architecture](../architecture.md) - System overview
- [Proto Definitions](../proto-definitions.md) - Message schemas
- [Semantic Kernel Docs](https://github.com/microsoft/semantic-kernel)
