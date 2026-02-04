
<div align="center">

# EchoMind

### Your Organization's AI Adoption Starts Now. **For Free** 🆓🚀

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](license)
[![Deploy Anywhere](https://img.shields.io/badge/Deploy-Anywhere-brightgreen.svg)](#deployment-modes)

**EchoMind is OpenClaw for business with no security risk**
**From single container to cluster. From one user to the whole org.**<br/>
**One platform. $0 forever. No trials. No limits.** ✨

[Documentation](docs/architecture.md) · [Why EchoMind?](#why-echomind)

</div>

---

## 🧠 What is it?
EchoMind is the free, deploy-anywhere **agentic AI platform** that automates workflows —
so your teams move faster and handle significantly more work with the same headcount.

EchoMind is an **AI agent**:
it **thinks** about what the workflow needs, **retrieves** the right internal context, **acts** using tools,
then **verifies** the result before responding.

> EchoMind is built for real work: support automation, IT deflection, meeting follow-ups, contract review,
> AP/invoice handling, onboarding, and any process where the bottleneck is “finding the right info + doing the next step”.

## ⚡ AI in Minutes (Not Months)

**Skip procurement. Start building today.**

No budget approvals. No vendor negotiations.  
Deploy EchoMind now and ship your first internal AI workflow this week. ✅

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


## 🚀Why EchoMind?
Because teams shouldn’t need a budget to start using AI. EchoMind is **$0, MIT-licensed, and self-hostable** 🆓🏠.


### 🆓 Free. Forever.
**MIT Licensed. $0. No strings attached.**

From startups to Fortune 500—EchoMind stays free.  
No usage limits. No “enterprise” paywalls. No vendor lock-in. 🔓

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
| **Multi-Source Connectors** | Microsoft Teams, Google Drive (v1), with more planned |
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
- **Connectors**: Microsoft Graph API, Google APIs

---

## Documentation

- [Architecture](docs/architecture.md) - Technical design with Mermaid diagrams
- API Documentation - *Coming soon*

---

## License

MIT License - See [LICENSE](license) for details.
