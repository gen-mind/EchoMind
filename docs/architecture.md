# EchoMind - Agentic RAG Architecture

> Technical specification for EchoMind, a Python-based Agentic Retrieval-Augmented Generation platform.

## Overview

EchoMind is an **Agentic RAG** system that goes beyond traditional retrieve-then-generate patterns. The agent reasons about what information it needs, plans multi-step retrieval strategies, uses external tools, and maintains memory across sessions.

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Clients
        WEB[Web App]
        API_CLIENT[API Client]
        BOT[Chat Bot Plugin]
    end

    subgraph EchoMind["EchoMind RAG Cluster"]
        subgraph Gateway["API Gateway"]
            REST[REST API]
            WS[WebSocket<br/>Streaming]
            GRPC[gRPC Internal]
        end

        subgraph Core["Agent Core"]
            ORCHESTRATOR[Agent Orchestrator]
            PLANNER[Query Planner]
            EXECUTOR[Tool Executor]
            MEMORY[Memory Manager]
        end

        subgraph Processing["Document Processing"]
            CONNECTOR[Connectors]
            CHUNKER[Semantic Chunker]
            EMBEDDER[Embedder Service]
        end

        subgraph Storage["Data Layer"]
            VECTORDB[(Milvus<br/>Vector DB)]
            RELDB[(PostgreSQL<br/>Metadata)]
            OBJSTORE[(MinIO<br/>File Storage)]
            CACHE[(Redis<br/>Cache + Memory)]
        end

        subgraph Messaging
            NATS[NATS JetStream]
        end
    end

    subgraph Inference["Inference Cluster (Pluggable)"]
        LLM_ROUTER[LLM Router]
        LOCAL_LLM[Local Models<br/>Ollama/vLLM]
        CLOUD_LLM[Cloud APIs<br/>OpenAI/Anthropic]
    end

    subgraph External["External Services"]
        AUTHENTIK[Authentik<br/>Auth Provider]
        CONNECTORS_EXT[Data Sources<br/>OneDrive/Teams/etc]
    end

    WEB & API_CLIENT & BOT --> REST & WS
    REST & WS --> ORCHESTRATOR
    ORCHESTRATOR --> PLANNER
    ORCHESTRATOR --> EXECUTOR
    ORCHESTRATOR --> MEMORY
    PLANNER --> VECTORDB
    EXECUTOR --> NATS
    MEMORY --> CACHE
    MEMORY --> RELDB

    NATS --> CONNECTOR
    NATS --> CHUNKER
    NATS --> EMBEDDER

    CONNECTOR --> OBJSTORE
    CHUNKER --> EMBEDDER
    EMBEDDER --> VECTORDB

    ORCHESTRATOR --> LLM_ROUTER
    LLM_ROUTER --> LOCAL_LLM
    LLM_ROUTER --> CLOUD_LLM

    REST --> AUTHENTIK
    CONNECTOR --> CONNECTORS_EXT
```

---

## Agentic RAG Flow

The key differentiator from traditional RAG: **the agent decides what to retrieve, when, and whether to retrieve at all**.

```mermaid
sequenceDiagram
    participant U as User
    participant O as Agent Orchestrator
    participant P as Query Planner
    participant M as Memory Manager
    participant R as Retriever
    participant T as Tool Executor
    participant L as LLM Router

    U->>O: User Query
    O->>M: Load conversation context
    M-->>O: Short-term + Long-term memory

    O->>P: Analyze query intent
    P->>L: "What info do I need?"
    L-->>P: Retrieval plan

    alt Needs retrieval
        P->>R: Execute retrieval strategy
        R->>R: Multi-collection search<br/>(user/group/org)
        R-->>P: Retrieved chunks + scores
        P->>P: Evaluate: sufficient?

        opt Needs more context
            P->>R: Refined query
            R-->>P: Additional chunks
        end
    end

    alt Needs tool execution
        P->>T: Execute tool (API call, code, etc)
        T-->>P: Tool result
    end

    P->>L: Generate response with context
    L-->>O: Streamed response
    O->>M: Update memory
    O->>U: Stream response
```

---

## Agent Planning Loop

```mermaid
flowchart LR
    subgraph Planning["Agent Planning"]
        THINK[Think:<br/>What do I need?]
        ACT[Act:<br/>Retrieve/Tool/Generate]
        OBSERVE[Observe:<br/>Evaluate results]
        REFLECT[Reflect:<br/>Is this sufficient?]
    end

    THINK --> ACT
    ACT --> OBSERVE
    OBSERVE --> REFLECT
    REFLECT -->|No, need more| THINK
    REFLECT -->|Yes, respond| RESPOND[Generate Final Response]
```

---

## Data Ingestion Pipeline

```mermaid
flowchart LR
    subgraph Sources["Data Sources"]
        FILE[File Upload]
        URL[Web URL]
        DRIVE[OneDrive/GDrive]
        TEAMS[Teams/Slack]
    end

    subgraph Ingestion["Ingestion Pipeline"]
        CONN[Connector Service]
        DETECT[Content Detection]
        EXTRACT[Content Extraction]
        SPLIT[Semantic Splitter]
        EMBED[Embedder]
    end

    subgraph Storage["Storage"]
        MINIO[(MinIO)]
        MILVUS[(Milvus)]
        PG[(PostgreSQL)]
    end

    FILE & URL & DRIVE & TEAMS --> CONN
    CONN --> DETECT
    DETECT --> EXTRACT
    EXTRACT --> MINIO
    EXTRACT --> SPLIT
    SPLIT --> EMBED
    EMBED --> MILVUS
    CONN --> PG

    style SPLIT fill:#f96,stroke:#333
    style EMBED fill:#f96,stroke:#333
```

### Document Processing States

```mermaid
stateDiagram-v2
    [*] --> Pending: Document received
    Pending --> Downloading: Connector fetches
    Downloading --> Extracting: Content extraction
    Extracting --> Chunking: Semantic split
    Chunking --> Embedding: Generate vectors
    Embedding --> Complete: Stored in Milvus

    Downloading --> Failed: Download error
    Extracting --> Failed: Parse error
    Chunking --> Failed: Split error
    Embedding --> Failed: Embed error

    Failed --> Pending: Retry
```

---

## Vector Collection Strategy

Per-user, per-group, and per-org collections enable scoped retrieval:

```mermaid
flowchart TB
    subgraph Collections["Milvus Collections"]
        ORG[org_acme_corp]
        GRP1[group_engineering]
        GRP2[group_sales]
        USR1[user_alice]
        USR2[user_bob]
    end

    subgraph Query["Query Scope"]
        Q[User Query]
    end

    Q -->|Personal docs| USR1
    Q -->|Team docs| GRP1
    Q -->|Company docs| ORG

    style ORG fill:#e1f5fe
    style GRP1 fill:#fff3e0
    style GRP2 fill:#fff3e0
    style USR1 fill:#e8f5e9
    style USR2 fill:#e8f5e9
```

---

## Memory Architecture

```mermaid
flowchart TB
    subgraph Memory["Agent Memory"]
        subgraph ShortTerm["Short-Term Memory"]
            CONV[Conversation Buffer]
            WORKING[Working Memory<br/>Current task context]
        end

        subgraph LongTerm["Long-Term Memory"]
            EPISODIC[Episodic Memory<br/>Past interactions]
            SEMANTIC[Semantic Memory<br/>Learned facts]
            PROCEDURAL[Procedural Memory<br/>Successful patterns]
        end
    end

    subgraph Storage
        REDIS[(Redis)]
        PG[(PostgreSQL)]
        MILVUS[(Milvus)]
    end

    CONV --> REDIS
    WORKING --> REDIS
    EPISODIC --> PG
    SEMANTIC --> MILVUS
    PROCEDURAL --> PG
```

---

## Tool System

The agent can invoke tools during reasoning:

```mermaid
flowchart LR
    subgraph Tools["Available Tools"]
        SEARCH[Vector Search]
        WEB[Web Search]
        CODE[Code Executor]
        API[External APIs]
        CALC[Calculator]
        FILE[File Operations]
    end

    AGENT[Agent] --> ROUTER[Tool Router]
    ROUTER --> SEARCH & WEB & CODE & API & CALC & FILE

    SEARCH --> RESULT[Tool Result]
    WEB --> RESULT
    CODE --> RESULT
    API --> RESULT
    CALC --> RESULT
    FILE --> RESULT

    RESULT --> AGENT
```

---

## Service Architecture

```mermaid
flowchart TB
    subgraph Services["Python Services"]
        API_SVC[API Service<br/>FastAPI + WebSocket]
        AGENT_SVC[Agent Service<br/>Orchestration + Planning]
        EMBED_SVC[Embedder Service<br/>gRPC]
        SEMANTIC_SVC[Semantic Service<br/>NATS Consumer]
        CONNECTOR_SVC[Connector Service<br/>NATS Consumer]
        SEARCH_SVC[Search Service<br/>gRPC]
    end

    subgraph Infra["Infrastructure"]
        NATS[NATS JetStream]
        PG[(PostgreSQL)]
        MILVUS[(Milvus)]
        REDIS[(Redis)]
        MINIO[(MinIO)]
    end

    API_SVC <--> AGENT_SVC
    AGENT_SVC <--> SEARCH_SVC
    AGENT_SVC <--> EMBED_SVC

    CONNECTOR_SVC --> NATS
    SEMANTIC_SVC --> NATS
    NATS --> EMBED_SVC

    EMBED_SVC --> MILVUS
    SEARCH_SVC --> MILVUS
    CONNECTOR_SVC --> MINIO
    API_SVC --> PG
    AGENT_SVC --> REDIS
```

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **API** | FastAPI + WebSocket | Async, streaming, OpenAPI docs |
| **Agent Framework** | Custom State Machine | Zero external deps, air-gap safe (see below) |
| **Embeddings** | SentenceTransformers | Local, configurable per cluster |
| **Vector DB** | Milvus | Scalable, HNSW/DiskANN indexes |
| **Relational DB** | PostgreSQL | Reliable, JSONB support |
| **Cache/Memory** | Redis | Fast, pub/sub, streams |
| **Object Storage** | MinIO | S3-compatible, self-hosted |
| **Message Queue** | NATS JetStream | Lightweight, persistent |
| **LLM Local** | Ollama / vLLM | Easy deployment, GPU support |
| **LLM Cloud** | OpenAI / Anthropic | Optional, for connected deployments |
| **Auth** | Authentik | SSO, OIDC, self-hosted |
| **Observability** | OpenTelemetry + Grafana | Traces, metrics, logs |

### Air-Gapped Deployment Requirement

EchoMind must support **fully disconnected environments** (e.g., DoD classified networks, SCIF, air-gapped data centers). This drives key architectural decisions:

| Requirement | Solution |
|-------------|----------|
| No internet access | All dependencies pre-packaged, offline installers |
| No telemetry/phone-home | Custom agent framework (no LangChain telemetry) |
| Local LLM only | Ollama/vLLM with pre-downloaded models |
| Local embeddings | SentenceTransformers with cached models |
| No external auth | Authentik self-hosted, LDAP/AD integration |
| Audit compliance | Full request/response logging, no data exfil |

### Why Custom Agent Framework (not LangGraph)

LangGraph is powerful but has concerns for air-gapped:
- LangChain dependencies can attempt network calls
- LangSmith integration is opt-out, not opt-in
- Complex dependency tree harder to audit
- Version pinning doesn't guarantee no network calls

**EchoMind Agent Core** will be a custom state machine:
- Pure Python, zero hidden network calls
- Explicit state transitions, fully auditable
- Same Think→Act→Observe→Reflect pattern
- Can be formally verified if needed

### Embedding Model Configuration

Embedding model is **cluster-wide** and configured via environment variables:

```bash
# .env or ConfigMap
ECHOMIND_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
ECHOMIND_EMBEDDING_DIMENSION=768
```

**Important**: Changing the embedding model requires:
1. Delete all vectors from Milvus
2. Mark all documents as `pending`
3. Re-scan all data sources
4. Re-embed all documents

This is enforced at startup: if model config changes, system blocks until admin confirms re-indexing.

---

## Deployment Modes

### Single Container (Development)

```mermaid
flowchart LR
    subgraph Container["echomind:latest"]
        ALL[All Services<br/>+ Embedded DBs]
    end

    USER[User] --> Container
```

### Docker Compose (Small Scale)

```mermaid
flowchart TB
    subgraph Compose["docker-compose.yml"]
        API[echomind-api]
        AGENT[echomind-agent]
        WORKER[echomind-worker]
        PG[postgres]
        MILVUS[milvus]
        REDIS[redis]
        MINIO[minio]
        NATS[nats]
    end
```

### Kubernetes (Production)

```mermaid
flowchart TB
    subgraph K8s["Kubernetes Cluster"]
        subgraph Deployments
            API[API Deployment<br/>HPA enabled]
            AGENT[Agent Deployment]
            WORKER[Worker Deployment]
        end

        subgraph StatefulSets
            PG[PostgreSQL]
            MILVUS[Milvus]
            REDIS[Redis]
        end

        subgraph Ingress
            ING[Ingress Controller]
        end
    end

    ING --> API
```

---

## Directory Structure (Proposed)

```
echomind/
├── docs/                    # Documentation
│   ├── architecture.md      # This file
│   └── api/                 # API documentation
├── src/
│   ├── api/                 # FastAPI application
│   │   ├── routes/
│   │   ├── middleware/
│   │   └── websocket/
│   ├── agent/               # Agent core
│   │   ├── orchestrator.py
│   │   ├── planner.py
│   │   ├── memory/
│   │   └── tools/
│   ├── services/            # Background services
│   │   ├── embedder/
│   │   ├── semantic/
│   │   ├── connector/
│   │   └── search/
│   ├── connectors/          # Data source connectors
│   │   ├── onedrive/
│   │   ├── teams/
│   │   ├── web/
│   │   └── file/
│   ├── db/                  # Database clients
│   │   ├── postgres.py
│   │   ├── milvus.py
│   │   ├── redis.py
│   │   └── minio.py
│   ├── models/              # Pydantic models
│   ├── proto/               # gRPC definitions
│   └── lib/                 # Shared utilities
├── deployment/
│   ├── docker/
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   └── k8s/
│       └── manifests/
├── config/                  # Configuration files
├── tests/
└── scripts/
```

---

## Next Steps

1. **Phase 1**: Core infrastructure (API, DB connections, auth)
2. **Phase 2**: Document ingestion pipeline (connectors, chunking, embedding)
3. **Phase 3**: Basic RAG (search, retrieval, generation)
4. **Phase 4**: Agent capabilities (planning, memory, tools)
5. **Phase 5**: Production hardening (observability, scaling)

---

## Decisions Made

- [x] **Agent framework**: Custom state machine (air-gap requirement)
- [x] **Embedding model**: Cluster-wide config via env vars, requires re-index on change
- [x] **Deployment targets**: Single container, Docker Compose, Kubernetes
- [x] **LLM strategy**: Local-first (Ollama/vLLM), cloud optional for connected envs
- [x] **Auth**: Authentik (self-hosted, OIDC/LDAP)
- [x] **Tenancy**: Single-tenant with per-user/group/org vector collections

## Open Questions

- [ ] Memory persistence strategy (how long to retain episodic memory?)
- [ ] Tool sandboxing approach (code execution in air-gapped environments)
- [ ] Model packaging strategy (how to ship Ollama models for air-gap?)
- [ ] Offline dependency bundling (pip wheels, Docker images)
