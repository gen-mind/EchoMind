# EchoMind Docker Cluster - Resource Requirements

This document outlines the CPU and RAM requirements for each service in the EchoMind Docker cluster based on official documentation, community best practices, and production deployment recommendations.

## Understanding Cloud vCPUs

### What is a vCPU?

**Virtual CPUs (vCPUs)** in cloud environments are NOT the same as physical CPU cores. Understanding this distinction is critical for proper resource planning.

#### vCPU Architecture

Most cloud providers use **Intel Hyper-Threading Technology** (or AMD equivalent):
- 1 Physical CPU Core → 2 Hardware Threads (Hyperthreads)
- 1 vCPU = 1 Hyperthread
- **Therefore: 2 vCPUs ≈ 1 Physical Core**

#### Performance Reality

**Important:** 2 vCPUs do NOT perform like 2 full physical cores:
- Hyperthreading provides ~20-30% performance boost (not 100%)
- 2 vCPUs ≈ 1.2-1.3 physical cores in real performance
- Software requirements stating "2 cores" typically mean "2 physical cores" = **4 vCPUs**

### Cloud Provider Specifics

#### AWS (Amazon Web Services)

**vCPU Definition:**
- 1 vCPU = 1 hyperthread of an Intel Xeon core
- Instance families: M5, M4, M6i, C5, C6i, R5, R6i, T3
- **Rule: 2 AWS vCPUs = 1 physical core**

**CPU Platforms (varies by instance family):**
- Intel Xeon Platinum 8175M (Skylake) - 3.1 GHz
- Intel Xeon Platinum 8259CL (Cascade Lake) - 3.1 GHz
- Intel Xeon Platinum 8375C (Ice Lake) - 3.5 GHz
- AMD EPYC 7R13 (Milan) - 3.6 GHz
- AWS Graviton3 (ARM) - 2.6 GHz

**Burstable Instances (T3/T4g):**
- Use CPU credits system (similar to Azure B-series)
- NOT recommended for production databases or sustained workloads
- Good for development/testing only

#### Azure (Microsoft)

**vCPU Definition:**
- 1 vCPU = 1 hyperthread (varies by series)
- **Standard Series (D, E, F):** 1 vCPU = 1 hyperthread
- **B-Series (Burstable):** Uses CPU credit model - NOT suitable for production

**CPU Platforms:**
- Intel Xeon Platinum 8370C (Ice Lake) - 2.8 GHz
- Intel Xeon Platinum 8272CL (Cascade Lake) - 2.6 GHz
- AMD EPYC 7763v (Milan) - 2.45 GHz
- Ampere Altra (ARM) - 3.0 GHz (Dpsv5/Epsv5)

**⚠️ B-Series Warning:**
- Accumulates CPU credits when idle
- Consumes credits when CPU usage exceeds baseline
- Throttled when credits exhausted
- **NEVER use for databases, message queues, or production services**
- Only for bursty workloads (web servers with low traffic)

#### Google Cloud Platform (GCP)

**vCPU Definition:**
- 1 vCPU = 1 hyperthread on Intel Xeon processors
- **Rule: 2 GCP vCPUs = 1 physical core**

**CPU Platforms (by machine series):**
- **N1:** Intel Xeon Sandy Bridge (2.6 GHz), Ivy Bridge (2.5 GHz), Haswell (2.3 GHz), Broadwell (2.2 GHz), Skylake (2.0 GHz)
- **N2:** Intel Cascade Lake (2.8 GHz), Ice Lake (3.1 GHz)
- **N2D:** AMD EPYC Rome (2.25 GHz), Milan (2.45 GHz)
- **C2:** Intel Cascade Lake (3.8 GHz all-core turbo)
- **C3:** Intel Sapphire Rapids (3.9 GHz all-core turbo)
- **T2D:** AMD EPYC Milan (2.25 GHz base) - shared-core

**Shared-core Instances (e2-micro, e2-small, e2-medium, f1-micro, g1-small):**
- Time-share physical cores with other VMs
- NOT recommended for production
- Development/testing only

### Converting Requirements to vCPUs

**When documentation says "X cores", you need:**

| Physical Cores | AWS vCPUs | Azure vCPUs | GCP vCPUs | Notes |
|----------------|-----------|-------------|-----------|-------|
| 0.25 core | 0.5 vCPU | 0.5 vCPU | 0.5 vCPU | Minimum for lightweight services |
| 0.5 core | 1 vCPU | 1 vCPU | 1 vCPU | Small utilities |
| 1 core | 2 vCPUs | 2 vCPUs | 2 vCPUs | Entry-level services |
| 2 cores | 4 vCPUs | 4 vCPUs | 4 vCPUs | Small databases, APIs |
| 4 cores | 8 vCPUs | 8 vCPUs | 8 vCPUs | Production databases |
| 8 cores | 16 vCPUs | 16 vCPUs | 16 vCPUs | High-performance workloads |

**⚠️ Critical:** All CPU values in this document refer to **physical core equivalents**. Double these values to get vCPUs when provisioning cloud instances.

## Summary Table

### Development Environment

| Service | CPU (Cores) | vCPUs | RAM (GB) | GPU VRAM | Notes |
|---------|-------------|-------|----------|----------|-------|
| **Traefik** | 0.25 | 0.5 | 0.25 | - | Reverse proxy |
| **PostgreSQL** | 1 | 2 | 1 | - | Shared database |
| **Authentik Server** | 1 | 2 | 1 | - | OIDC server |
| **Authentik Worker** | 0.5 | 1 | 0.5 | - | Background tasks |
| **Qdrant** | 1 | 2 | 0.5 | - | Vector DB (<100K) |
| **MinIO** | 1 | 2 | 1 | - | Object storage |
| **NATS** | 0.5 | 1 | 0.25 | - | Message bus |
| **EchoMind API** | 1 | 2 | 1 | - | FastAPI |
| **Embedder** | 0.5 | 1 | 1 | ~2-4 GB | nvidia/llama-nemotron-embed-1b-v2 (1B) |
| **Orchestrator** | 0.25 | 0.5 | 0.25 | - | Scheduler |
| **Connector** | 0.5 | 1 | 0.5 | - | OAuth sync |
| **Ingestor** | 0.5 | 1 | 1 | 0 | pdfium (CPU) |
| **Guardian** | 0.25 | 0.5 | 0.25 | - | DLQ monitor |
| **TOTAL** | **8.25** | **16.5** | **8.5** | **~2-4 GB** | **Default config** |

### Small Production Environment

| Service | CPU (Cores) | vCPUs | RAM (GB) | GPU VRAM | Notes |
|---------|-------------|-------|----------|----------|-------|
| **Traefik** | 0.5 | 1 | 0.5 | - | TLS termination |
| **PostgreSQL** | 2 | 4 | 2 | - | Connection pooling |
| **Authentik Server** | 1 | 2 | 1.5 | - | Moderate load |
| **Authentik Worker** | 1 | 2 | 1 | - | Email, webhooks |
| **Qdrant** | 2 | 4 | 2 | - | <1M vectors |
| **MinIO** | 2 | 4 | 4 | - | Redundancy |
| **NATS** | 1 | 2 | 1 | - | JetStream |
| **EchoMind API** | 2 | 4 | 2 | - | Multi-worker |
| **Embedder** | 1 | 2 | 2 | ~2-4 GB | nvidia/llama-nemotron-embed-1b-v2 (1B) |
| **Orchestrator** | 0.5 | 1 | 0.5 | - | Scheduler |
| **Connector** | 1 | 2 | 1 | - | Concurrent sync |
| **Ingestor** | 1 | 2 | 2 | 0 | pdfium (CPU) |
| **Guardian** | 0.5 | 1 | 0.5 | - | Alerting |
| **Search** | - | - | - | TBD | Not implemented |
| **TOTAL** | **15.5** | **31** | **20** | **~2-4 GB** | **Default config** |

### Production Environment

| Service | CPU (Cores) | vCPUs | RAM (GB) | GPU VRAM | Notes |
|---------|-------------|-------|----------|----------|-------|
| **Traefik** | 1 | 2 | 1 | - | High traffic |
| **PostgreSQL** | 4 | 8 | 8 | - | HA, caching |
| **Authentik Server** | 2 | 4 | 2 | - | Many users |
| **Authentik Worker** | 1 | 2 | 1.5 | - | Reliable tasks |
| **Qdrant** | 4 | 8 | 4-8 | - | 1M+ vectors |
| **MinIO** | 4 | 8 | 8 | - | High perf |
| **NATS** | 4 | 8 | 8 | - | JetStream prod |
| **EchoMind API** | 4 | 8 | 4 | - | Load balanced |
| **Embedder** | 2 | 4 | 4 | ~2-4 GB | nvidia/llama-nemotron-embed-1b-v2 (1B) |
| **Orchestrator** | 1 | 2 | 1 | - | Multi-scheduler |
| **Connector** | 2 | 4 | 2 | - | Multi-provider |
| **Ingestor** | 2 | 4 | 4 | 0 | pdfium (CPU) |
| **Guardian** | 1 | 2 | 1 | - | Multi-alerter |
| **Search** | - | - | - | TBD | Not implemented |
| **TOTAL** | **32** | **64** | **48-52** | **~2-4 GB** | **Default config** |

### Optional GPU Add-ons

These are **optional** features that require additional GPU VRAM beyond the base embedder:

| Feature | Config Change | GPU VRAM | Source |
|---------|---------------|----------|--------|
| YOLOX table detection | `INGESTOR_YOLOX_ENABLED=true` | +4 GB | [NVIDIA NIM](https://build.nvidia.com/nvidia/nv-yolox-page-elements-v1/modelcard) |
| Riva audio transcription | `INGESTOR_RIVA_ENABLED=true` | +16 GB | [NVIDIA Riva](https://docs.nvidia.com/nim/riva/asr/latest/support-matrix.html) |
| Local LLM (8B INT4) | Search service config | +5 GB | [vLLM Guide](https://www.digitalocean.com/community/conceptual-articles/vllm-gpu-sizing-configuration-guide) |
| Local LLM (70B INT4) | Search service config | +35 GB | [HuggingFace](https://huggingface.co/hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4) |

## Detailed Service Requirements

### 1. Traefik (Reverse Proxy)

**Purpose:** HTTP/HTTPS reverse proxy and load balancer

**Requirements:**
- **Development:** 0.25 CPU / 256 MB RAM
- **Production:** 0.5-1 CPU / 512 MB - 1 GB RAM

**Factors:**
- TLS certificates consume significant memory (~10MB per cert)
- CPU intensive during TLS negotiation
- Scales with number of routes and middleware
- Very lightweight for basic routing

**References:**
- Traefik Community Forums: 100MB-10GB depending on load
- Typical usage: 100-512MB for small deployments

### 2. PostgreSQL 16 (Database)

**Purpose:** Shared relational database for Authentik and API

**Requirements:**
- **Development:** 1 CPU / 1 GB RAM
- **Small Production:** 2 CPU / 2 GB RAM  
- **Production:** 4 CPU / 8 GB RAM

**Configuration Guidelines:**
- `shared_buffers`: ~25% of total RAM
- `effective_cache_size`: ~75% of total RAM
- `work_mem`: 16-64 MB per connection
- `maintenance_work_mem`: 256 MB - 1 GB

**Factors:**
- Connection count (Authentik + API + workers)
- Query complexity and caching needs
- Write-heavy vs. read-heavy workloads
- Disk I/O speed (SSD strongly recommended)

**References:**
- PostgreSQL Official Docs: Minimum 32MB, practical minimum 1GB
- Community recommendations: 2-4GB for small production

### 3. Authentik Server (OIDC Provider)

**Purpose:** Authentication server handling OIDC flows

**Requirements:**
- **Development:** 1 CPU / 1 GB RAM
- **Production:** 2 CPU / 2 GB RAM

**Factors:**
- Number of concurrent users
- Session management overhead
- LDAP/OAuth provider integrations
- Policy evaluation complexity

**References:**
- Official Authentik Docs: "Minimum 2 CPU cores and 2 GB RAM" (combined server + worker)
- Community reports: 200-400MB idle, up to 1-2GB under load

### 4. Authentik Worker (Background Tasks)

**Purpose:** Async task processing (emails, webhooks, scheduled jobs)

**Requirements:**
- **Development:** 0.5 CPU / 512 MB RAM
- **Production:** 1 CPU / 1-1.5 GB RAM

**Factors:**
- Email sending frequency
- Webhook processing load
- Scheduled maintenance tasks
- Event log processing

**References:**
- Shares same codebase as Authentik Server
- Typically uses less resources than server

### 5. Qdrant (Vector Database)

**Purpose:** Vector similarity search for RAG embeddings

**Requirements:**
- **Development:** 1 CPU / 512 MB RAM (small dataset)
- **Small Production:** 2 CPU / 2 GB RAM (<1M vectors)
- **Production:** 4 CPU / 4-8 GB RAM (1M+ vectors)

**Configuration Options:**
1. **All in Memory:** ~1.2GB per 1M vectors (128d)
2. **Vectors on Disk (mmap):** ~600MB per 1M vectors
3. **Vectors + HNSW on Disk:** ~135MB per 1M vectors (slower)

**Factors:**
- Vector dimension (768d for typical embeddings)
- Dataset size (number of vectors)
- Search performance requirements
- Disk speed (NVMe SSD for mmap)

**References:**
- Qdrant Official Docs: "Minimal RAM you need to serve a million vectors"
- Memory-optimized setup: 135MB-1.2GB per 1M vectors

### 6. MinIO (Object Storage)

**Purpose:** S3-compatible object storage for documents and files

**Requirements:**
- **Development:** 1 CPU / 1 GB RAM
- **Small Production:** 2 CPU / 4 GB RAM
- **Production:** 4 CPU / 8 GB RAM

**Factors:**
- Concurrent upload/download streams
- Object sizes (large files = more memory)
- Erasure coding (if enabled)
- Replication and versioning

**References:**
- MinIO Official: "Lightweight requirements for CPU and RAM"
- Community: 4 CPU / 8GB for single-node production
- Can run on 2 CPU / 4GB for lighter workloads

### 7. NATS with JetStream (Message Bus)

**Purpose:** Message broker for microservices communication

**Requirements:**
- **Development:** 0.5 CPU / 256 MB RAM
- **Small Production:** 1 CPU / 1 GB RAM
- **Production:** 4 CPU / 8 GB RAM

**Official Benchmarks (NATS Docs):**
- Core NATS: 1 CPU / 32-64 MB for basic messaging
- JetStream (1 publisher, 100 subscribers, 10K msg/s): 1 CPU / 64 MB
- JetStream Production: **4 CPU / 8 GB recommended**

**Factors:**
- Message throughput (messages/second)
- JetStream storage size (file-based)
- Number of streams and consumers
- Disk I/O for persistence

**References:**
- NATS Official Installation Docs
- Production minimum: 4 cores + 8GB for JetStream reliability

### 8. EchoMind API (FastAPI Application)

**Purpose:** Main application REST API

**Requirements:**
- **Development:** 1 CPU / 1 GB RAM (single worker)
- **Small Production:** 2 CPU / 2 GB RAM (2-4 workers)
- **Production:** 4 CPU / 4 GB RAM (4-8 workers)

**Worker Configuration:**
- Formula: `(2 x CPU cores) + 1` workers
- Memory per worker: ~256-512 MB

**Factors:**
- Request complexity (DB queries, vector search)
- External API calls (LLM providers)
- Concurrent request handling
- Static asset serving (if any)

**References:**
- FastAPI + Uvicorn: 256-512MB per worker
- Gunicorn recommendation: 2-4 workers for moderate load

## GPU / VRAM Requirements

EchoMind can use GPU acceleration for embedding generation and document extraction. This section covers VRAM requirements based on **actual configured models**.

### VRAM Calculation Formula

```
VRAM = Parameters × Bytes_per_param × 1.2 (overhead)

Bytes_per_param:
  - FP32: 4 bytes
  - FP16: 2 bytes
  - INT8: 1 byte
```

**Source:** [LLM VRAM Requirements Explained](https://www.propelrc.com/llm-gpu-vram-requirements-explained/)

---

### 1. Embedder Service

**Config file:** `config/embedder/embedder.env`

#### Default Model: `nvidia/llama-nemotron-embed-1b-v2`

| Metric | Value | Source |
|--------|-------|--------|
| Parameters | **1B** | [HuggingFace Model Card](https://huggingface.co/nvidia/llama-nemotron-embed-1b-v2) |
| Output Dimensions | 2048 | Model card |
| Max Sequence Length | 512 tokens | Model card |
| Precision | BF16 | Model card |

**VRAM Calculation:**
```
BF16: 1B × 2 bytes × 1.2 = 2.4 GB
+ Batch overhead (batch_size=32): ~500 MB - 1 GB
```

| Precision | Model VRAM | With Batch | Total |
|-----------|------------|------------|-------|
| BF16 | 2.4 GB | +1 GB | **~2-4 GB** |

#### Alternative NVIDIA Models

| Model | Parameters | Dimensions | VRAM | Source |
|-------|------------|------------|------|--------|
| `nvidia/llama-nemotron-embed-1b-v2` | 1B | 2048 | ~2-4 GB | [HuggingFace](https://huggingface.co/nvidia/llama-nemotron-embed-1b-v2) |
| `nvidia/llama-3.2-nv-embedqa-1b-v2` | 1B | 2048 | ~2-4 GB | [HuggingFace](https://huggingface.co/nvidia/llama-3.2-nv-embedqa-1b-v2) |
| `nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1` | 1B | 2048 | ~2-4 GB | [HuggingFace](https://huggingface.co/nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1) (Multimodal) |

**To change model:** Edit `EMBEDDER_MODEL_NAME` in `config/embedder/embedder.env`

---

### 2. Ingestor Service

**Config file:** `config/ingestor/ingestor.env`

#### Default Configuration (No GPU Required)

```env
INGESTOR_EXTRACT_METHOD=pdfium       # CPU-based PDF extraction
INGESTOR_TOKENIZER=meta-llama/Llama-3.2-1B  # Tokenizer only (no weights)
INGESTOR_YOLOX_ENABLED=false         # NIM disabled
INGESTOR_RIVA_ENABLED=false          # NIM disabled
```

**Tokenizer Note:** The `meta-llama/Llama-3.2-1B` tokenizer downloads only tokenizer files (~few MB), NOT the 1B model weights. No GPU needed.

| Component | GPU Required | VRAM |
|-----------|--------------|------|
| pdfium extraction | No | 0 |
| Tokenizer (Llama/GPT2) | No | 0 |
| **Total (default)** | **No** | **0** |

#### Optional NVIDIA NIMs (if enabled)

| NIM | Config Flag | VRAM | Source |
|-----|-------------|------|--------|
| YOLOX Page Elements | `INGESTOR_YOLOX_ENABLED=true` | **~4 GB** | [NVIDIA NIM](https://build.nvidia.com/nvidia/nv-yolox-page-elements-v1/modelcard) |
| Riva ASR | `INGESTOR_RIVA_ENABLED=true` | **16+ GB** | [NVIDIA Riva Support Matrix](https://docs.nvidia.com/nim/riva/asr/latest/support-matrix.html) |

**Total with all NIMs enabled:** ~20 GB VRAM

---

### 3. Search Service (Not Implemented)

Search service is **not yet implemented**. GPU requirements will depend on architecture decision:

1. **External API** (OpenAI, Anthropic, Azure OpenAI): **0 GB local VRAM**
2. **Local LLM** (vLLM, TGI): Depends on model choice

#### Reference: LLM VRAM Requirements

| Model | Parameters | FP16 | INT4 (AWQ) | Source |
|-------|------------|------|------------|--------|
| Llama 3.1 8B | 8B | ~16 GB | ~5 GB | [HuggingFace](https://huggingface.co/hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4) |
| Llama 3.1 70B | 70B | ~140 GB | ~35 GB | [HuggingFace](https://huggingface.co/hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4) |
| Mistral 7B | 7B | ~14 GB | ~4 GB | [vLLM Guide](https://www.digitalocean.com/community/conceptual-articles/vllm-gpu-sizing-configuration-guide) |

---

### Summary by Deployment Tier

#### Development (Default Config)

| Service | Model/Config | GPU | VRAM |
|---------|--------------|-----|------|
| Embedder | nvidia/llama-nemotron-embed-1b-v2 | Yes | ~2-4 GB (BF16) |
| Ingestor | pdfium + tokenizer | No | 0 |
| Search | Not implemented | - | - |
| **Total** | | **Yes** | **~2-4 GB** |

#### Production (With NIMs + Local LLM)

| Service | Model/Config | GPU | VRAM |
|---------|--------------|-----|------|
| Embedder | nvidia/llama-nemotron-embed-1b-v2 | Yes | ~2-4 GB |
| Ingestor | YOLOX + Riva NIMs | Yes | ~20 GB |
| Search | Llama 3.1 8B INT4 | Yes | ~5 GB |
| **Total** | | **Yes** | **~27-29 GB** |

---

### GPU Selection Guide

| GPU | VRAM | Price | Fits |
|-----|------|-------|------|
| **RTX 3060** | 12 GB | ~$300 | Embedder + 8B INT4 |
| **RTX 4070** | 12 GB | ~$550 | Embedder + 8B INT4 |
| **RTX 4090** | 24 GB | ~$1,600 | Embedder + NIMs (no LLM) |
| **T4** | 16 GB | $0.35/hr | Embedder only |
| **L4** | 24 GB | $0.50/hr | Full stack (8B INT4) |
| **A10G** | 24 GB | $1.00/hr | Full stack (8B INT4) |
| **A100 40GB** | 40 GB | $3.00/hr | Full stack + 70B INT4 |

---

## Storage Requirements

### Disk Space

| Service | Minimum | Recommended | Growth Rate |
|---------|---------|-------------|-------------|
| **PostgreSQL** | 5 GB | 20 GB | Depends on usage (logs, data) |
| **Qdrant** | 1 GB | 10 GB | ~200MB per 1M vectors (mmap) |
| **MinIO** | 10 GB | 100 GB+ | Depends on document storage |
| **NATS** | 1 GB | 10 GB | Depends on JetStream retention |
| **Authentik** | 500 MB | 2 GB | Media files, templates, certs |
| **Traefik** | 100 MB | 500 MB | Logs and certificates |

### Disk Performance

**Critical:**
- **PostgreSQL:** Requires SSD, NVMe preferred
- **Qdrant:** SSD strongly recommended (especially for mmap)
- **NATS JetStream:** SSD for reliable persistence

**Less Critical:**
- MinIO: HDD acceptable for archival, SSD for performance
- Traefik: Standard disk acceptable

## Scaling Recommendations

### Horizontal Scaling

Services that can scale horizontally:
- ✅ **EchoMind API** - Multiple instances behind load balancer
- ✅ **Authentik Server** - Multiple replicas with shared DB
- ✅ **Authentik Worker** - Multiple workers for task processing
- ⚠️ **NATS** - Cluster mode (requires configuration changes)

Services that scale vertically:
- 📈 **PostgreSQL** - More CPU/RAM for better performance
- 📈 **Qdrant** - More RAM for larger datasets
- 📈 **MinIO** - Can add nodes for distributed setup

### When to Scale

**Scale Up (Vertical) When:**
- CPU usage consistently >70%
- Memory usage >80%
- Disk I/O becomes bottleneck
- Response times degrade

**Scale Out (Horizontal) When:**
- Single instance hits CPU/RAM limits
- Need high availability
- Handling traffic spikes
- Geographic distribution required

## Cost Optimization Tips

### Development

1. **Use Docker resource limits** to prevent runaway containers
2. **Disable unnecessary features** (JetStream if not used, Qdrant if testing without vectors)
3. **Use SQLite for API** if Authentik not needed during dev
4. **Share PostgreSQL** instance (already configured)

### Production

1. **Start with "Small Production" specs** and monitor
2. **Enable Qdrant mmap** to reduce memory footprint
3. **Use PostgreSQL connection pooling** (PgBouncer)
4. **Optimize NATS retention policies** to limit disk usage
5. **Monitor and adjust** based on actual usage patterns

## Monitoring Recommendations

### Key Metrics to Track

**Per Service:**
- CPU usage (%)
- Memory usage (MB / %)
- Disk I/O (read/write MB/s)
- Network I/O (MB/s)

**Application Level:**
- Request latency (p50, p95, p99)
- Error rates
- Active connections
- Queue depths (NATS)

### Tools

- **Docker Stats:** `docker stats` (basic monitoring)
- **cAdvisor:** Container metrics
- **Prometheus + Grafana:** Production monitoring
- **Traefik Dashboard:** Request metrics

## References

### Official Documentation

1. **Traefik:** https://doc.traefik.io/traefik/
2. **PostgreSQL:** https://www.postgresql.org/docs/current/
3. **Authentik:** https://docs.goauthentik.io/
4. **Qdrant:** https://qdrant.tech/documentation/
5. **MinIO:** https://min.io/docs/
6. **NATS:** https://docs.nats.io/
7. **FastAPI:** https://fastapi.tiangolo.com/deployment/

### Community Resources

1. Authentik Reddit: System requirements for homelab
2. NATS Docs: Hardware requirements table
3. Qdrant: "Minimal RAM you need to serve a million vectors"
4. PostgreSQL Wiki: Performance Optimization
5. MinIO Blog: Best practices for virtualized environments

## Cloud Instance Recommendations

### Development Environment

**Requirements:** 6.25 physical cores (~13 vCPUs), 5.5 GB RAM

#### AWS Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **t3.xlarge** | 4 | 16 GB | ~$120 | ⚠️ Burstable - dev only |
| **t3a.xlarge** | 4 | 16 GB | ~$110 | ⚠️ Burstable AMD - dev only |
| **m6i.xlarge** | 4 | 16 GB | ~$175 | Better sustained performance |
| **m6a.xlarge** | 4 | 16 GB | ~$165 | AMD alternative |

**Recommended:** `t3.xlarge` for local development testing

#### Azure Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **B4ms** | 4 | 16 GB | ~$120 | ⚠️ Burstable - will throttle |
| **D4s_v5** | 4 | 16 GB | ~$175 | Standard, consistent performance |
| **D4as_v5** | 4 | 16 GB | ~$155 | AMD, good value |

**Recommended:** `D4s_v5` or `D4as_v5` (avoid B-series for databases)

#### GCP Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **e2-standard-4** | 4 | 16 GB | ~$120 | Shared-core, lower cost |
| **n2-standard-4** | 4 | 16 GB | ~$195 | Intel Ice Lake |
| **n2d-standard-4** | 4 | 16 GB | ~$175 | AMD EPYC Milan |

**Recommended:** `n2d-standard-4` for best price/performance

---

### Small Production Environment

**Requirements:** 11.5 physical cores (~23 vCPUs), 14 GB RAM

#### AWS Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **m6i.2xlarge** | 8 | 32 GB | ~$350 | ✅ Best all-around choice |
| **m6a.2xlarge** | 8 | 32 GB | ~$330 | AMD, excellent value |
| **r6i.xlarge** | 4 | 32 GB | ~$290 | Memory-optimized |
| **c6i.2xlarge** | 8 | 16 GB | ~$310 | Compute-optimized (if RAM sufficient) |

**Recommended:** `m6i.2xlarge` or `m6a.2xlarge`

**⚠️ DO NOT USE:** t3.2xlarge (burstable - will throttle under sustained load)

#### Azure Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **D8s_v5** | 8 | 32 GB | ~$350 | ✅ Standard, reliable |
| **D8as_v5** | 8 | 32 GB | ~$310 | AMD, cost-effective |
| **E8s_v5** | 8 | 64 GB | ~$505 | Memory-optimized, overkill RAM |
| **F8s_v2** | 8 | 16 GB | ~$340 | Compute-optimized |

**Recommended:** `D8as_v5` for best value, `D8s_v5` for Intel preference

**⚠️ DO NOT USE:** B-series (B8ms) - will throttle databases and NATS

#### GCP Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **n2-standard-8** | 8 | 32 GB | ~$390 | ✅ Intel Ice Lake |
| **n2d-standard-8** | 8 | 32 GB | ~$350 | AMD EPYC, best value |
| **n2-highmem-4** | 4 | 32 GB | ~$310 | Memory-optimized, fewer cores |
| **c2-standard-8** | 8 | 32 GB | ~$485 | High-performance compute |

**Recommended:** `n2d-standard-8` for optimal price/performance

---

### Production Environment

**Requirements:** 24 physical cores (~48 vCPUs), 36.5-40.5 GB RAM

#### AWS Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **m6i.4xlarge** | 16 | 64 GB | ~$700 | ✅ Excellent balance |
| **m6a.4xlarge** | 16 | 64 GB | ~$660 | AMD, great value |
| **r6i.2xlarge** | 8 | 64 GB | ~$580 | Memory-optimized, fewer cores |
| **c6i.4xlarge** | 16 | 32 GB | ~$620 | Compute-optimized, tight on RAM |
| **m5.4xlarge** | 16 | 64 GB | ~$700 | Previous gen, still solid |

**Recommended:** `m6a.4xlarge` (best value) or `m6i.4xlarge` (Intel preference)

**For High Availability:** 2x `m6a.2xlarge` with load balancing

#### Azure Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **D16s_v5** | 16 | 64 GB | ~$700 | ✅ Standard production |
| **D16as_v5** | 16 | 64 GB | ~$620 | AMD, excellent value |
| **E16s_v5** | 16 | 128 GB | ~$1,010 | Memory-optimized, excessive RAM |
| **F16s_v2** | 16 | 32 GB | ~$680 | Compute-optimized, tight on RAM |

**Recommended:** `D16as_v5` for cost efficiency, `D16s_v5` for Intel

**For High Availability:** 2x `D8as_v5` across availability zones

#### GCP Recommendations

| Instance Type | vCPUs | RAM | Cost/Month* | Notes |
|---------------|-------|-----|-------------|-------|
| **n2-standard-16** | 16 | 64 GB | ~$780 | ✅ Intel Ice Lake |
| **n2d-standard-16** | 16 | 64 GB | ~$700 | AMD EPYC, best value |
| **n2-highmem-8** | 8 | 64 GB | ~$620 | Memory-optimized, fewer cores |
| **c2-standard-16** | 16 | 64 GB | ~$970 | High-performance compute |
| **n1-standard-16** | 16 | 60 GB | ~$570 | Previous gen, budget option |

**Recommended:** `n2d-standard-16` for production, `n2-standard-16` for Intel preference

**For High Availability:** 2x `n2d-standard-8` across zones

---

### Multi-Server Production (Recommended for 100+ Users)

**Better approach than single large instance:**

#### Option 1: Database Separation (Recommended)

**Database Server:**
- AWS: `r6i.2xlarge` (8 vCPU, 64 GB RAM) - ~$580/mo
- Azure: `E8s_v5` (8 vCPU, 64 GB RAM) - ~$505/mo
- GCP: `n2-highmem-8` (8 vCPU, 64 GB RAM) - ~$620/mo

**Application Server:**
- AWS: `m6a.2xlarge` (8 vCPU, 32 GB RAM) - ~$330/mo
- Azure: `D8as_v5` (8 vCPU, 32 GB RAM) - ~$310/mo
- GCP: `n2d-standard-8` (8 vCPU, 32 GB RAM) - ~$350/mo

**Total Cost:** ~$835-920/month (better performance, easier to scale)

#### Option 2: Horizontal Scaling

**Load Balancer + 2x Application Servers + 1x Database Server:**

**Each Application Server:**
- AWS: `m6a.xlarge` (4 vCPU, 16 GB RAM) - ~$165/mo
- Azure: `D4as_v5` (4 vCPU, 16 GB RAM) - ~$155/mo
- GCP: `n2d-standard-4` (4 vCPU, 16 GB RAM) - ~$175/mo

**Database Server:**
- AWS: `r6i.xlarge` (4 vCPU, 32 GB RAM) - ~$290/mo
- Azure: `E4s_v5` (4 vCPU, 32 GB RAM) - ~$255/mo
- GCP: `n2-highmem-4` (4 vCPU, 32 GB RAM) - ~$310/mo

**Total Cost:** ~$610-720/month (high availability, better fault tolerance)

---

### Cost Optimization Strategies

#### 1. Use Reserved Instances / Savings Plans

**AWS:**
- 1-year Reserved Instance: ~35% discount
- 3-year Reserved Instance: ~55% discount
- Compute Savings Plans: Flexible across instance families

**Azure:**
- 1-year Reserved VM: ~40% discount
- 3-year Reserved VM: ~62% discount
- Azure Hybrid Benefit: Use existing Windows licenses

**GCP:**
- 1-year Committed Use: ~37% discount
- 3-year Committed Use: ~55% discount
- Sustained Use Discount: Automatic 20-30% for consistent usage

#### 2. Use Spot/Preemptible Instances (Non-Production Only)

**AWS Spot Instances:** Up to 90% discount (can be terminated)
**Azure Spot VMs:** Up to 90% discount (can be evicted)
**GCP Preemptible VMs:** Up to 80% discount (max 24h runtime)

**⚠️ Only suitable for:**
- Development environments
- Non-critical batch processing
- Stateless API workers (with auto-scaling)

**❌ NEVER use for:**
- Databases (PostgreSQL, Qdrant)
- Message queues (NATS)
- Authentication (Authentik)

#### 3. Right-Size Over Time

**Week 1:** Start with recommended instance
**Week 2-4:** Monitor actual usage with CloudWatch/Azure Monitor/Stackdriver
**Month 2:** Downsize if usage <50% or upsize if usage >80%
**Quarterly:** Review and adjust

---

## Quick Reference: Deployment Scenarios

### Scenario 1: Local Development (Laptop/Desktop)

**Target:** 4-8 GB RAM available, 4 CPU cores

**Recommendation:** Use Development specs
- Total: ~6.25 physical cores, ~5.5 GB RAM
- ✅ Fits on modern laptop with headroom
- Use Docker Desktop resource limits to constrain usage

### Scenario 2: Small VPS/Cloud Instance

**Target:** 10-20 users, moderate usage

**Recommendation:** Small Production specs

**Best Value Options:**
- **AWS:** `m6a.2xlarge` (8 vCPU, 32 GB) - ~$330/mo
- **Azure:** `D8as_v5` (8 vCPU, 32 GB) - ~$310/mo
- **GCP:** `n2d-standard-8` (8 vCPU, 32 GB) - ~$350/mo

**With 1-year commitment:** ~$200-230/month

### Scenario 3: Production Deployment (Single Server)

**Target:** 50-100 users, high availability needs

**Recommendation:** Production specs

**Best Options:**
- **AWS:** `m6a.4xlarge` (16 vCPU, 64 GB) - ~$660/mo
- **Azure:** `D16as_v5` (16 vCPU, 64 GB) - ~$620/mo
- **GCP:** `n2d-standard-16` (16 vCPU, 64 GB) - ~$700/mo

**With 1-year commitment:** ~$400-460/month

### Scenario 4: Production Deployment (Multi-Server)

**Target:** 100+ users, fault tolerance required

**Recommendation:** Separated database + load-balanced application servers

**Architecture:**
- 1x Database Server (PostgreSQL, Qdrant, NATS, MinIO)
- 2x Application Servers (API, Authentik, Traefik)
- 1x Load Balancer (managed service)

**Total Cost:** ~$700-950/month depending on cloud provider
**With 1-year commitment:** ~$460-620/month

---

**Document Version:** 2.0
**Last Updated:** January 28, 2026
**Author:** EchoMind Team
