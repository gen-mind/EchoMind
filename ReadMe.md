
<div align="center">

# EchoMind

**Agentic RAG for Enterprise**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](license)

*An AI platform that reasons, retrieves, and responds—deployable anywhere from public cloud to air-gapped SCIF facilities.*

</div>

---

## What is EchoMind?

EchoMind is an **Agentic Retrieval-Augmented Generation (RAG)** platform that goes beyond traditional retrieve-then-generate patterns. Unlike conventional RAG systems that simply fetch and paste context, EchoMind's agent:

- **Reasons** about what information it needs before retrieving
- **Plans** multi-step retrieval strategies across multiple data sources
- **Uses tools** to execute actions, call APIs, and process data
- **Remembers** context across conversations with short-term and long-term memory

> New to RAG? [Watch this explainer video](https://www.youtube.com/watch?v=u47GtXwePms)

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Agentic Architecture** | Think → Act → Observe → Reflect loop for intelligent retrieval |
| **Multi-Source Connectors** | Microsoft Teams, Google Drive (v1), with more planned |
| **Flexible Deployment** | Cloud, Hybrid, or fully Air-Gapped (SCIF compliant) |
| **Private LLM Inference** | TGI/vLLM for on-premise GPU clusters |
| **Enterprise Auth** | Authentik with OIDC/LDAP/Active Directory support |
| **Per-User Vector Collections** | Scoped search across user, group, and organization data |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     EchoMind RAG Cluster                        │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  Authentik   │  │ API Gateway  │  │     Agent Core        │  │
│  │  (OIDC Auth) │→ │ REST + WS    │→ │ Semantic Kernel       │  │
│  └──────────────┘  └──────────────┘  │ Planning + Memory     │  │
│                                       └───────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │   Qdrant     │  │  PostgreSQL  │  │   Document Processing │  │
│  │  Vector DB   │  │   Metadata   │  │ Chunking + Embedding  │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Inference Cluster (Pluggable) │
              │   TGI/vLLM  or  Cloud APIs     │
              └───────────────────────────────┘
```

For detailed architecture with Mermaid diagrams, see [docs/architecture.md](docs/architecture.md).

---

## Deployment Modes

EchoMind adapts to your security requirements:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Cloud** | Full SaaS experience with cloud LLMs | Startups, teams without GPU infrastructure |
| **Hybrid** | Private RAG cluster + optional cloud LLM fallback | Enterprises with sensitive data |
| **Air-Gapped** | Fully disconnected, zero external dependencies | DoD, SCIF, classified networks |

### Air-Gapped / SCIF Compliance

EchoMind is designed for the most restricted environments:

- No internet access required
- No telemetry or phone-home capabilities
- All dependencies pre-packaged in container images
- Deployable to [Iron Bank (Platform One)](https://p1.dso.mil/iron-bank)
- LDAP/Active Directory integration via Authentik

---

## Tech Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Agent Framework | [Semantic Kernel](https://github.com/microsoft/semantic-kernel) | Microsoft's AI orchestration SDK |
| Vector Database | [Qdrant](https://qdrant.tech/) | High-performance, Rust-based |
| LLM Inference | TGI / vLLM | Private GPU cluster support |
| Auth | [Authentik](https://goauthentik.io/) | Self-hosted OIDC provider |
| API | FastAPI + WebSocket | Async, streaming responses |
| Message Queue | NATS JetStream | Lightweight, persistent |
| Metadata DB | PostgreSQL | Reliable, JSONB support |
| Object Storage | MinIO / RustFS | S3-compatible (evaluating RustFS) |

---

## Project Structure

```
echomind/
├── docs/                    # Documentation
│   └── architecture.md      # Technical architecture
├── src/
│   ├── api/                 # FastAPI application
│   ├── agent/               # Semantic Kernel agent core
│   ├── services/            # Background workers
│   ├── connectors/          # Data source connectors
│   └── db/                  # Database clients
├── deployment/
│   ├── docker/              # Docker Compose files
│   └── k8s/                 # Kubernetes manifests
├── config/                  # Configuration files
└── tests/
```

---

## Roadmap

### Phase 1: Core Infrastructure
- [ ] API Gateway with Authentik integration
- [ ] Database connections (PostgreSQL, Qdrant, Redis)
- [ ] Basic project scaffolding

### Phase 2: Document Ingestion
- [ ] Microsoft Teams connector
- [ ] Google Drive connector
- [ ] Semantic chunking pipeline
- [ ] Embedding service

### Phase 3: Basic RAG
- [ ] Vector search
- [ ] LLM integration (TGI/vLLM)
- [ ] Streaming responses

### Phase 4: Agentic Capabilities
- [ ] Semantic Kernel integration
- [ ] Multi-step planning
- [ ] Memory (short-term + long-term)
- [ ] Tool execution

### Phase 5: Production Hardening
- [ ] Observability (OpenTelemetry + Grafana)
- [ ] Iron Bank container certification
- [ ] Performance optimization

---

## Contributing

We're building EchoMind in Python and welcome contributions in:

- **Backend**: FastAPI, async Python, gRPC
- **AI/ML**: Semantic Kernel, embeddings, reranking
- **Infrastructure**: Kubernetes, Docker, CI/CD
- **Connectors**: Microsoft Graph API, Google APIs

---

## Documentation

- [Architecture](docs/architecture.md) - Technical design with Mermaid diagrams
- API Documentation - *Coming soon*

---

## License

MIT License - See [LICENSE](license) for details.
