
<div align="center">

# EchoMind

### OpenClaw for Business — With Zero Security Risk

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](license)
[![Deploy Anywhere](https://img.shields.io/badge/Deploy-Anywhere-brightgreen.svg)](#deployment-modes)

**The power of personal AI assistants like OpenClaw — but for your entire organization.**<br/>
**Your company knowledge + your business tools. Fully sandboxed. Completely free.**

[Documentation](docs/architecture.md) · [Why EchoMind?](#why-echomind) · [OpenClaw vs EchoMind](#openclaw-vs-echomind)

</div>

---

## 🧠 What is it?

EchoMind brings the power of personal AI assistants to the enterprise — **without the security nightmares**.

Like [OpenClaw](https://openclaw.ai/), EchoMind is an AI agent that can access your data, execute workflows, and automate tasks. But instead of running with unrestricted access on personal devices, EchoMind runs in **isolated, ephemeral sandboxes** with enterprise-grade authentication and permission controls.

**EchoMind connects to:**
- **Organizational knowledge** — Teams, SharePoint, Google Drive, internal wikis, policies, and documents
- **Personal business tools** — Email, calendar, CRM, and the apps your teams use daily

> See [63 Supported Connectors](docs/personal-assistant/echomind-connectors.md) — including Salesforce, SAP, ServiceNow, Workday, and more.

**EchoMind is an AI agent** that **thinks** about what the workflow needs, **retrieves** the right internal context, **acts** using tools, then **verifies** the result — all within a secure, permission-aware sandbox.

> Built for real work: support automation, IT deflection, meeting follow-ups, contract review,
> AP/invoice handling, onboarding, and any process where the bottleneck is "finding the right info + doing the next step".

## 🔒 Secure by Design — Sandboxed Execution

Unlike personal AI assistants that run with full system access, EchoMind executes every workflow in an **ephemeral, isolated sandbox**:

| Security Feature | How It Works |
|------------------|--------------|
| **Ephemeral Sandboxes** | Each workflow runs in a fresh container that's destroyed after completion — no state leaks between runs |
| **Delegated Authorization** | Sandboxes call your tools with user-scoped tokens; permissions enforced at every layer |
| **No Direct System Access** | Workflows can't execute arbitrary shell commands on your infrastructure |
| **Lease-Based Execution** | Exclusive access with TTL prevents runaway processes and resource exhaustion |
| **Air-Gap Ready** | Deploy fully disconnected — no internet, no telemetry, no phone-home |

**The result:** Your teams get the productivity of an AI assistant. Your security team sleeps at night.

---

## ⚡ AI in Minutes (Not Months)

**Skip procurement. Start building today.**

No budget approvals. No vendor negotiations.
Deploy EchoMind now and ship your first internal AI workflow this week.

---
### 🤝 Need help getting started? Let’s jump on a quick call (free)

If you want a fast setup review, architecture feedback, or help choosing the right deployment mode,
you can book a **free call** with the author.

📅 [**Book a free call**](https://calendar.app.google/QuNua7HxdsSasCGu9) with [gsantopaolo](https://github.com/gsantopaolo)
---
## ✨ How it works

```
🔄 Think → Act → Observe → Reflect → Evaluate → Answer
```

> The agent 🤔 **thinks** about what information it needs, 👷‍♂️ **acts** by querying sources and tools, 🔍 **observes** the results, and 🤖 **reflects** on whether it has enough context. Before responding, it ⚖️ **evaluates** the quality and completeness of its answer — looping back if needed — then delivers a grounded 💬 **answer**.
## ⚙️ Automation Use Cases (Real-World Inspired)

EchoMind is built for *process automation*, not just Q&A:
**think → act → observe → reflect → evaluate → answer**, with permission-aware answers and source-grounded output.

### 🎧 Customer Support Automation
- Deflect repetitive chats and tickets with grounded answers from your KB and policies
- Escalate only complex cases with full context + suggested replies

### 📝 Meetings → Actions → Follow-ups → CRM
- Generate meeting notes + action items
- Draft follow-up emails
- Save structured notes into your CRM (e.g., Salesforce)

### 🧠 “Knowledge Coach” for Frontline Teams
- Make staff dramatically faster at finding the right internal info
- Serve answers grounded in policies, research, and product docs

### 🧰 IT Helpdesk Ticket Deflection (Shift-Left)
- Resolve common issues without creating tickets
- Pre-fill tickets only when needed (device, logs, steps tried)

### ⚖️ Contract Review Acceleration
- Extract key terms, flag risky clauses, summarize obligations
- Suggest redlines based on your playbooks and templates

### 🧾 Accounts Payable Automation
- Invoice extraction + coding suggestions
- Approval routing + audit-ready explanations

> **Deep Dive:** [Business Use Cases](docs/personal-assistant/echomind-use-cases-business-problems.md) — 4 productized solutions (SmartTicketing, DataInsight, OnboardingBot, CustomerContext360)
> | [Connector Use Cases](docs/personal-assistant/echomind-connector-use-cases.md) — 79 real-world workflows across 37 connectors

## 🚀 Why EchoMind?

**Enterprise AI assistants without the enterprise price tag — or the security risks.**

| Why It Matters | EchoMind Delivers |
|----------------|-------------------|
| **Free forever** | MIT licensed. $0. No usage caps. No "enterprise" tier. |
| **Secure by default** | Sandboxed execution, not "trust the user" security |
| **Your infrastructure** | Self-host on-prem, in your cloud, or air-gapped |
| **Your data stays yours** | No telemetry, no phone-home, no vendor lock-in |

---


## 🧬 What makes EchoMind agentic?
EchoMind is an **agentic RAG platform** that actually *thinks* before it retrieves — and it’s **100% free (MIT)** 🆓.

- **Reasons** about what information it needs before retrieving
- **Plans** multi-step retrieval strategies across multiple data sources
- **Uses tools** to execute actions, call APIs, and process data
- **Remembers** context across conversations with short-term and long-term memory

---
 
## Key Features

| Feature | Description |
|---------|-------------|
| **Agentic Architecture** | Think → Act → Observe → Reflect loop for intelligent retrieval |
| **Multi-Source Connectors** | [63 connectors](docs/personal-assistant/echomind-connectors.md) — Salesforce, SAP, Teams, Drive, and more |
| **Flexible Deployment** | Cloud, Hybrid, or fully Air-Gapped (SCIF compliant) |
| **Private LLM Inference** | TGI/vLLM for on-premise GPU clusters |
| **Enterprise Auth** | Authentik with OIDC/LDAP/Active Directory support |
| **Per-User Vector Collections** | Scoped search across user, group, and organization data |


|                                   |                                                                             |
|-----------------------------------|-----------------------------------------------------------------------------|
| 🔍 **Multi-Step Retrieval**       | Goes beyond "retrieve-then-generate" — reasons across multiple sources      |
| 🏠 **Private and SaaS LLM Ready** | Run with TGI/vLLM on your own GPU cluster or connected to your favorite LLM API |
| 🔒 **Air-Gap / SCIF Ready**       | No internet, no telemetry, no phone-home — fully self-contained             |
| 📦 **Deploy Anywhere**            | Single container to Kubernetes cluster — your choice                        |
| 🆓 **MIT Licensed — Free Forever** | No paid tiers. No usage caps. No hidden licensing surprises |


---

## Architecture Overview

```mermaid
flowchart LR
    subgraph Clients
        C[Web / API / Bot]
    end

    subgraph EchoMind["EchoMind RAG Cluster"]
        API[API Gateway]
        AGENT[Agent Core<br/>Semantic Kernel]
        PROC[Doc Processing]

        subgraph Storage
            QDRANT[(Qdrant)]
            PG[(PostgreSQL)]
        end
    end

    subgraph Inference["Inference Cluster"]
        LLM[TGI/vLLM<br/>or Cloud APIs]
    end

    C --> AUTH --> API --> AGENT
    AGENT --> QDRANT
    AGENT --> LLM
    PROC --> QDRANT
    AGENT --> PG
```

For detailed architecture, see [docs/architecture.md](docs/architecture.md).

---

## Deployment Modes

EchoMind adapts to your security requirements:

| Mode | Description                                              | Use Case |
|------|----------------------------------------------------------|----------|
| **Cloud** | Deploy on your Could | Startups, teams without GPU infrastructure |
| **Hybrid** | Private RAG cluster + optional cloud LLM fallback        | Enterprises with sensitive data |
| **Air-Gapped** | Fully disconnected, zero external dependencies           | DoD, SCIF, classified networks |

### Air-Gapped / SCIF Compliance

EchoMind is designed for the most restricted environments:

- No internet access required
- No telemetry or phone-home capabilities
- All dependencies pre-packaged in container images
- Deployable to [Iron Bank (Platform One)](https://p1.dso.mil/iron-bank)
- LDAP/Active Directory integration via Authentik

---

### Deploy It Yourself — or Let Us Deploy It for You

**Option 1: Self-Hosted** — Deploy EchoMind anywhere you want on any GPU-equipped server. You own the hardware, you control the data. Follow the [quickstart guide](deployment/docker-cluster/QUICKSTART.md) and you're up in under an hour.

**Option 2: Fully Managed** — We deploy and manage EchoMind on a **dedicated server exclusively for you** in our datacenter in **Germany (EU)**, fully **GDPR-compliant**. No shared infrastructure, no multi-tenancy — your own machine, your own data.

At the **lowest price on the world wide web**:

#### 1–50 Users

| Spec | Details |
|------|---------|
| **CPU** | Intel Core i5-13500 (6P + 8E cores, Hyper-Threading) |
| **GPU** | NVIDIA RTX 4000 SFF Ada Generation — **20 GB GDDR6 ECC** |
| **RAM** | 64 GB DDR4 |
| **Storage** | 2 x 1.92 TB NVMe SSD (RAID 1) |
| **Network** | 1 Gbit/s, unlimited traffic |
| **Price** | **Starting at ~$200/month** |

#### 50–200 Users

| Spec | Details |
|------|---------|
| **CPU** | Intel Xeon Gold 5412U (24 cores, Hyper-Threading) |
| **GPU** | NVIDIA RTX PRO 6000 Blackwell Max-Q — **96 GB GDDR7 ECC**, 5th-gen Tensor Cores |
| **RAM** | 256 GB DDR5 ECC (expandable to 768 GB) |
| **Storage** | 2 x 960 GB NVMe SSD Datacenter Edition (RAID 1) |
| **Network** | 1 Gbit/s guaranteed, unlimited traffic |
| **Price** | **Starting at ~$990/month** |

> Both plans include: dedicated server setup, EchoMind deployment, SSL certificates, Authentik SSO configuration, and ongoing maintenance. No minimum contract — cancel anytime.

📅 [**Book a free call**](https://calendar.app.google/QuNua7HxdsSasCGu9) to discuss your deployment with [gsantopaolo](https://github.com/gsantopaolo)

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
│   ├── db/                  # Database clients
│   └── proto/               # Protocol Buffer definitions
│       ├── public/          # API objects (client-facing)
│       └── internal/        # Internal service objects
├── deployment/
│   ├── docker/              # Docker Compose files
│   └── k8s/                 # Kubernetes manifests
├── config/                  # Configuration files
└── tests/
```

> **Schema-First Development**: Proto definitions in `src/proto/` are the source of truth. CI generates TypeScript types (for clients) and Pydantic models (for Python) automatically.

---

## Contributing

We're building EchoMind in Python and welcome contributions in:

- **Backend**: FastAPI, async Python, gRPC
- **AI/ML**: Semantic Kernel, embeddings, reranking
- **Infrastructure**: Kubernetes, Docker, CI/CD
- **Connectors**: Microsoft Graph, Google APIs, and [60+ more](docs/personal-assistant/echomind-connectors.md)

---

## Documentation

- [Architecture](docs/architecture.md) - Technical design with Mermaid diagrams
- [Supported Connectors](docs/personal-assistant/echomind-connectors.md) - 63 data source integrations with market analysis
- [Business Use Cases](docs/personal-assistant/echomind-use-cases-business-problems.md) - Productized solutions for real business problems
- [Connector Use Cases](docs/personal-assistant/echomind-connector-use-cases.md) - 79 workflows showing what each connector enables
- [API Specification](docs/api-spec.md) - REST/WebSocket endpoint reference
- [Langfuse Setup](docs/langfuse-setup.md) - LLM observability and RAGAS evaluation

---

## OpenClaw vs EchoMind

[OpenClaw](https://openclaw.ai/) is an open-source personal AI assistant that runs locally with full system access — shell commands, file operations, browser control. It's powerful for individuals, but [security researchers have flagged serious concerns](https://blogs.cisco.com/ai/personal-ai-agents-like-openclaw-are-a-security-nightmare) for organizational use: credential exposure, malicious skill injection, and no secure-by-default setup.

**EchoMind is OpenClaw for business** — the same AI agent capabilities, redesigned for enterprise security:

| Capability | OpenClaw | EchoMind |
|------------|----------|----------|
| AI-powered workflows | Personal device | Isolated sandbox |
| System access | Unrestricted shell/files | Permission-controlled APIs |
| Data sources | Local files, messaging apps | Org knowledge + business tools |
| Security model | User responsibility | Enterprise-grade (OIDC, LDAP, air-gap) |
| Execution environment | Persistent on device | Ephemeral containers |
| Target use case | Personal productivity | Team/org automation |
| Cost | Free + API costs | Free (MIT) + API costs |

**Bottom line:** If you want an AI assistant for personal use, OpenClaw is excellent. If you want to deploy AI assistants across your organization without creating security vulnerabilities, EchoMind is built for that.

---

## Observability & Visualization

EchoMind includes a full observability stack covering infrastructure metrics, log aggregation, Gen AI evaluation, and vector visualization. All observability features are **optional** and gated by environment flags.

---

### Vector Visualization with TensorBoard

The **Projector Service** generates interactive 3D/2D visualizations of your vector collections using [TensorBoard Projector](https://projector.tensorflow.org/).

| Feature | Description |
|---------|-------------|
| **Collection Scoping** | Visualize vectors scoped to user (`user_{id}`), team (`team_{id}`), or organization (`org_{id}`) |
| **Search Filtering** | Optionally filter vectors by full-text search on title and content |
| **On-Demand Generation** | Trigger via API (`POST /api/v1/projector/generate`) or WebUI |
| **Batch Processing** | Fetches up to 20,000 vectors from Qdrant in batches of 500 |

**How it works:**
1. API receives a generation request with collection scope and optional search query
2. Request is published to NATS (`projector.generate`)
3. Projector worker fetches vectors from Qdrant, generates TensorFlow checkpoints + metadata
4. TensorBoard serves the visualization at `https://tensorboard.<DOMAIN>`

**Configuration:** `TENSORBOARD_DOMAIN`, `PROJECTOR_QDRANT_URL`, `PROJECTOR_LOG_DIR`

> See [Architecture](docs/architecture.md) for service interaction diagrams.

---

### Gen AI Observability with RAGAS and Langfuse

[Langfuse v3](https://langfuse.com/) provides **LLM observability** and [RAGAS](https://docs.ragas.io/) provides **RAG quality evaluation** — giving you visibility into how well your AI is performing.

| Component | What It Does |
|-----------|-------------|
| **Langfuse Traces** | Records every chat interaction: query, response, context chunks, latency |
| **RAGAS Faithfulness** | Is the response grounded in the retrieved context? (0-1 score) |
| **RAGAS Response Relevancy** | Is the response relevant to the user's query? (0-1 score) |
| **RAGAS Context Precision** | Are the retrieved chunks relevant to the query? (0-1 score) |

**Two evaluation modes:**
- **Online (sampled)**: Configurable fraction of chat requests auto-evaluated (`RAGAS_SAMPLE_RATE`, default 10%)
- **Batch**: Admin-triggered evaluation of recent sessions via WebUI or API (`POST /api/v1/evaluate/batch`)

**Enabling:** Set `ENABLE_LANGFUSE=true` in `.env.host` and configure secrets. See [Langfuse Setup](docs/langfuse-setup.md).

Langfuse shares PostgreSQL, MinIO, and Redis with EchoMind. ClickHouse is dedicated to Langfuse for OLAP trace storage.

---

### Standard Observability with Grafana, Loki, Prometheus

The infrastructure observability stack provides metrics, logs, and dashboards — all self-hosted with no external dependencies.

| Component | Purpose |
|-----------|---------|
| [**Prometheus**](https://prometheus.io/) | Metrics collection — scrapes `/metrics` from all services every 10s |
| [**Loki**](https://grafana.com/oss/loki/) | Log aggregation — collects container stdout via Alloy |
| [**Grafana**](https://grafana.com/oss/grafana/) | Dashboards — 12 pre-shipped dashboards, Authentik SSO |
| [**Alloy**](https://grafana.com/docs/alloy/) | Log collector — auto-discovers Docker containers |
| **Exporters** | cAdvisor (containers), node-exporter (host), postgres-exporter, nats-exporter |

**12 Pre-Shipped Grafana Dashboards:**

| Dashboard | What It Shows |
|-----------|---------------|
| EchoMind Overview | Service health, error rates, NATS queue depth |
| Loki Logs Explorer | Service log browser with level filtering and full-text search |
| RAGAS Evaluation | RAG quality score trends, distributions, evaluation rates |
| Docker Containers | Per-container CPU, memory, network I/O, restarts |
| Node Exporter | Host CPU, memory, disk, network interfaces |
| NATS Server | Connections, messages in/out, throughput |
| NATS JetStream | Stream/consumer message counts, pending, lag |
| Traefik | HTTP request rate, latency percentiles, error rates |
| PostgreSQL | Connections, transactions, locks, cache hit ratio |
| MinIO | Object storage capacity, S3 traffic, request latency |
| Qdrant | Vector DB collection stats, query performance |
| Loki (self-monitoring) | Ingestion rate, error rates |

**Enabling:** Set `ENABLE_OBSERVABILITY=true` in `.env.host`. Access Grafana at `https://grafana.<DOMAIN>`.

> OpenTelemetry compatibility: The stack uses Prometheus exposition format and Loki's log pipeline, both of which are OpenTelemetry-compatible. Services can be instrumented with OTel SDKs to push traces and metrics alongside the pull-based Prometheus scraping.

---

## License

MIT License - See [LICENSE](license) for details.
