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
        subgraph Auth["Authentication Layer"]
            AUTHENTIK[Authentik<br/>OIDC Provider]
        end

        subgraph Gateway["API Gateway"]
            API[echomind-api<br/>REST + WebSocket]
        end

        subgraph Search["Agentic Search"]
            SEARCH[echomind-search<br/>Semantic Kernel]
        end

        subgraph Ingestion["Document Ingestion"]
            ORCH[echomind-orchestrator<br/>APScheduler]
            CONN[echomind-connector<br/>Teams/Drive/OneDrive]
            SEM[echomind-semantic<br/>Extract + Chunk]
            EMBED[echomind-embedder<br/>Text → Vector]
            VOICE[echomind-voice<br/>Whisper]
            VISION[echomind-vision<br/>BLIP + OCR]
        end

        subgraph Storage["Data Layer"]
            VECTORDB[(Qdrant<br/>Vector DB)]
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
        PRIVATE_LLM[Private Inference<br/>TGI/vLLM]
        CLOUD_LLM[Cloud APIs<br/>OpenAI/Anthropic]
    end

    subgraph External["External Data Sources"]
        CONNECTORS_EXT[OneDrive/Teams<br/>GDrive/Web/Files]
    end

    WEB & API_CLIENT & BOT --> AUTHENTIK
    AUTHENTIK -->|JWT Token| API
    API -->|Query| SEARCH
    SEARCH --> VECTORDB
    SEARCH --> LLM_ROUTER
    SEARCH --> CACHE

    ORCH -->|NATS| CONN
    CONN -->|NATS| SEM
    SEM -->|gRPC| EMBED
    SEM -->|NATS| VOICE
    SEM -->|NATS| VISION
    VOICE -->|text| SEM
    VISION -->|text| SEM
    EMBED --> VECTORDB

    CONN --> OBJSTORE
    CONN --> CONNECTORS_EXT
    API --> RELDB

    LLM_ROUTER --> PRIVATE_LLM
    LLM_ROUTER --> CLOUD_LLM
```

> **Authentication Flow**: Clients authenticate with Authentik (OIDC) first, receive a JWT token, then include it in requests to the API Gateway. The gateway validates the token before forwarding to backend services. This follows the [OAuth 2.0 Resource Server pattern](https://www.solo.io/topics/api-gateway/api-gateway-authentication).

---

## Agentic RAG Flow

The key differentiator from traditional RAG: **the agent decides what to retrieve, when, and whether to retrieve at all**. The `echomind-search` service implements this using Semantic Kernel.

```mermaid
sequenceDiagram
    participant U as User
    participant API as echomind-api
    participant S as echomind-search<br/>(Semantic Kernel)
    participant Q as Qdrant
    participant R as Redis
    participant L as LLM Router

    U->>API: User Query (HTTP/WebSocket)
    API->>S: Forward query (gRPC)

    S->>R: Load conversation context
    R-->>S: Short-term + Long-term memory

    S->>S: Think: What info do I need?

    alt Needs retrieval
        S->>Q: Execute retrieval strategy
        Q-->>S: Retrieved chunks + scores
        S->>S: Evaluate: sufficient?

        opt Needs more context
            S->>Q: Refined query
            Q-->>S: Additional chunks
        end
    end

    alt Needs tool execution
        S->>S: Execute tool (calculator, web, etc)
    end

    S->>L: Generate response with context
    L-->>S: Streamed tokens
    S->>R: Update memory
    S-->>API: Stream response
    API-->>U: Stream to client
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
        QDRANT[(Qdrant)]
        PG[(PostgreSQL)]
    end

    FILE & URL & DRIVE & TEAMS --> CONN
    CONN --> DETECT
    DETECT --> EXTRACT
    EXTRACT --> MINIO
    EXTRACT --> SPLIT
    SPLIT --> EMBED
    EMBED --> QDRANT
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
    Embedding --> Complete: Stored in Qdrant

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
    subgraph Collections["Qdrant Collections"]
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
        QDRANT[(Qdrant)]
    end

    CONV --> REDIS
    WORKING --> REDIS
    EPISODIC --> PG
    SEMANTIC --> QDRANT
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
        QDRANT[(Qdrant)]
        REDIS[(Redis)]
        MINIO[(MinIO)]
    end

    API_SVC <--> AGENT_SVC
    AGENT_SVC <--> SEARCH_SVC
    AGENT_SVC <--> EMBED_SVC

    CONNECTOR_SVC --> NATS
    SEMANTIC_SVC --> NATS
    NATS --> EMBED_SVC

    EMBED_SVC --> QDRANT
    SEARCH_SVC --> QDRANT
    CONNECTOR_SVC --> MINIO
    API_SVC --> PG
    AGENT_SVC --> REDIS
```

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **API** | FastAPI + WebSocket | Async, streaming, OpenAPI docs |
| **Agent Framework** | Semantic Kernel | Microsoft's AI orchestration SDK, air-gap compatible, Python native |
| **Embeddings** | SentenceTransformers | Local, configurable per cluster |
| **Vector DB** | Qdrant | High-performance, HNSW indexes, rich filtering, Rust-based |
| **Relational DB** | PostgreSQL | Reliable, JSONB support |
| **Cache/Memory** | Redis | Fast, pub/sub, streams |
| **Object Storage** | MinIO ⚠️ | S3-compatible, self-hosted (see warning below) |
| **Message Queue** | NATS JetStream | Lightweight, persistent |
| **LLM Private** | TGI / vLLM | Production-grade inference, GPU optimized |
| **LLM Cloud** | OpenAI / Anthropic | Optional, for connected deployments |
| **Auth** | Authentik | SSO, OIDC, self-hosted, inside cluster |
| **Observability** | OpenTelemetry + Grafana | Traces, metrics, logs |

### ⚠️ Object Storage Warning: MinIO

> **Warning**: MinIO is currently under maintenance mode and is not accepting new changes. This may impact long-term support and security updates.

**Recommended Alternative**: [RustFS](https://github.com/rustfs/rustfs) - A high-performance, S3-compatible object storage written in Rust. Benefits:
- Active development
- Rust-based (memory safe, high performance)
- S3-compatible API
- Better suited for air-gapped deployments

**Decision**: Evaluate RustFS as primary object storage. If not mature enough for v1, use MinIO with migration path to RustFS planned.

---

### Flexible Deployment: Cloud, Hybrid, or Air-Gapped

EchoMind is designed to run anywhere—from public cloud to the most restricted environments. Whether you're deploying in AWS/Azure/GCP, a private data center, or a fully air-gapped SCIF facility, EchoMind adapts to your security requirements.

| Deployment Mode | Description |
|-----------------|-------------|
| **Cloud** | Full SaaS experience with cloud LLMs (OpenAI, Anthropic) and managed services |
| **Hybrid** | Private RAG cluster with optional cloud LLM fallback |
| **Air-Gapped** | Fully disconnected, meets SCIF standards, zero external dependencies |

#### Air-Gapped Compliance

For classified networks and air-gapped data centers, EchoMind provides:

| Requirement | Solution |
|-------------|----------|
| No internet access | All dependencies pre-packaged, offline container images |
| No telemetry/phone-home | Semantic Kernel runs fully offline, no hidden network calls |
| Private LLM inference | TGI/vLLM with pre-downloaded models |
| Local embeddings | SentenceTransformers with cached models |
| Self-contained auth | Authentik inside cluster, LDAP/AD integration |
| Audit compliance | Full request/response logging, no data exfiltration |

### Why Semantic Kernel

[Semantic Kernel](https://github.com/microsoft/semantic-kernel) is Microsoft's open-source AI orchestration SDK:

- **Air-gap compatible**: No telemetry, no phone-home, works fully offline
- **Python native**: First-class Python support alongside C# and Java
- **Pluggable connectors**: Easy to swap LLM providers (local or cloud)
- **Memory & planning**: Built-in support for agent memory and multi-step planning
- **Enterprise-ready**: Backed by Microsoft, used in production at scale
- **Auditable**: Clean dependency tree, no hidden LangChain-style network calls

### Embedding Model Configuration

Embedding model is **cluster-wide** and configured via environment variables:

```bash
# .env or ConfigMap
ECHOMIND_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
ECHOMIND_EMBEDDING_DIMENSION=768
```

**Important**: Changing the embedding model requires:
1. Delete all vectors from Qdrant
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
        QDRANT[qdrant]
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
            QDRANT[Qdrant]
            REDIS[Redis]
        end

        subgraph Ingress
            ING[Ingress Controller]
        end
    end

    ING --> API
```

---

## Directory Structure

```
echomind/
├── docs/                    # Documentation
│   ├── architecture.md      # This file
│   └── services/            # Service-specific docs
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
│   │   ├── embedder/        # Text → Vector (gRPC)
│   │   ├── semantic/        # Document chunking (NATS)
│   │   ├── search/          # Vector search (gRPC)
│   │   ├── transformer/     # Text splitting (gRPC)
│   │   ├── voice/           # Whisper (NATS)
│   │   └── vision/          # BLIP+OCR (NATS)
│   ├── connectors/          # Data source connectors
│   │   ├── onedrive/
│   │   ├── teams/
│   │   ├── web/
│   │   └── file/
│   ├── proto/               # Protocol Buffer definitions (source of truth)
│   │   ├── public/          # Client-facing API objects
│   │   └── internal/        # Internal service objects
│   ├── echomind_lib/        # SHARED LIBRARY
│   │   ├── db/              # Database clients
│   │   │   ├── models/      # SQLAlchemy ORM models
│   │   │   ├── postgres.py
│   │   │   ├── qdrant.py
│   │   │   └── nats_*.py
│   │   ├── helpers/         # Utility code
│   │   └── models/          # AUTO-GENERATED (from proto)
│   └── web/                 # React client
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

- [x] **Agent framework**: Semantic Kernel (Microsoft's AI orchestration SDK, air-gap compatible)
- [x] **Vector database**: Qdrant (high-performance, HNSW, rich filtering)
- [x] **Embedding model**: Cluster-wide config via env vars, requires re-index on change
- [x] **Deployment targets**: Single container, Docker Compose, Kubernetes
- [x] **Deployment modes**: Cloud, Hybrid, or Air-Gapped (SCIF compliant)
- [x] **LLM strategy**: Private inference (TGI/vLLM), cloud optional for connected envs
- [x] **Auth**: Authentik (self-hosted, OIDC/LDAP, inside RAG cluster)
- [x] **Tenancy**: Single-tenant with per-user/group/org vector collections

## Open Questions

- [ ] Memory persistence strategy (how long to retain episodic memory?) — **TBD**
- [ ] Reranker strategy (cross-encoder model selection, when to apply reranking?) — **TBD**
- [ ] Object storage selection: MinIO (maintenance mode) vs [RustFS](https://github.com/rustfs/rustfs) — **Evaluate**

## Resolved

- [x] **Offline dependency bundling**: Docker images from authorized container registries, deployable to [Iron Bank (Platform One)](https://p1.dso.mil/iron-bank)
- [x] **Connector priority for v1**: Microsoft Teams, Google Drive
