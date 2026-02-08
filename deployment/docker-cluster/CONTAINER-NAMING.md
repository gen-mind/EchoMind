# Container Naming & Grouping Architecture

## 📋 Overview

All containers in the EchoMind platform are organized into logical groups with consistent naming prefixes for better management and monitoring.

## 🏷️ Naming Scheme

| Prefix | Purpose | Example | Count |
|--------|---------|---------|-------|
| `echomind-*` | Application services | `echomind-api`, `echomind-connector` | 9 |
| `data-*` | All databases | `data-postgres`, `data-qdrant`, `data-minio` | 5 |
| `infra-*` | Infrastructure | `infra-traefik`, `infra-authentik-server` | 6 |
| `observability-*` | Monitoring/Tracing | `observability-grafana`, `observability-langfuse` | 10 |
| `init-*` | Initialization jobs | `init-migration`, `init-langfuse-bucket` | 2 |

**Total: 32 containers**

---

## 📦 Complete Container Inventory

### 🚀 Application Services (`echomind-*`)

| Container Name | Description | Service Name |
|----------------|-------------|--------------|
| `echomind-api` | REST API backend | `api` |
| `echomind-nui` | Neural UI service | `nui` |
| `echomind-embedder` | Text embedding service (gRPC) | `embedder` |
| `echomind-orchestrator` | Job scheduler | `orchestrator` |
| `echomind-connector` | Data source integrations | `connector` |
| `echomind-ingestor` | Document processing pipeline | `ingestor` |
| `echomind-guardian` | Dead letter queue monitor | `guardian` |
| `echomind-projector` | Vector projection service | `projector` |
| `echomind-webui` | Web application UI | `webui` |

### 🗄️ Data Services (`data-*`)

| Container Name | Description | Service Name |
|----------------|-------------|--------------|
| `data-postgres` | PostgreSQL 16.4 (shared DB) | `postgres` |
| `data-qdrant` | Vector database | `qdrant` |
| `data-minio` | S3-compatible object storage | `minio` |
| `data-redis` | Cache and message broker | `redis` |
| `data-clickhouse` | OLAP database (Langfuse traces) | `langfuse-clickhouse` |

### 🏗️ Infrastructure Services (`infra-*`)

| Container Name | Description | Service Name |
|----------------|-------------|--------------|
| `infra-traefik` | Reverse proxy & SSL termination | `traefik` |
| `infra-adminer` | PostgreSQL web admin UI | `adminer` |
| `infra-authentik-server` | SSO/OIDC provider | `authentik-server` |
| `infra-authentik-worker` | Authentik background jobs | `authentik-worker` |
| `infra-nats` | Message queue (JetStream) | `nats` |
| `infra-portainer` | Container management UI | `portainer` |

### 📊 Observability Services (`observability-*`)

| Container Name | Description | Service Name |
|----------------|-------------|--------------|
| `observability-prometheus` | Metrics time-series DB | `prometheus` |
| `observability-loki` | Log aggregation | `loki` |
| `observability-alloy` | Grafana agent (metrics/logs collector) | `alloy` |
| `observability-grafana` | Dashboards and visualization | `grafana` |
| `observability-tensorboard` | ML training metrics | `tensorboard` |
| `observability-cadvisor` | Container metrics exporter | `cadvisor` |
| `observability-node-exporter` | Host metrics exporter | `node-exporter` |
| `observability-nats-exporter` | NATS metrics exporter | `nats-exporter` |
| `observability-postgres-exporter` | PostgreSQL metrics exporter | `postgres-exporter` |
| `observability-langfuse` | LLM tracing & evaluation UI | `langfuse-web` |
| `observability-langfuse-worker` | Langfuse background processor | `langfuse-worker` |

### ⚙️ Initialization Jobs (`init-*`)

| Container Name | Description | Service Name | Restart Policy |
|----------------|-------------|--------------|----------------|
| `init-migration` | Alembic schema migrations | `migration` | `no` (one-time) |
| `init-langfuse-bucket` | Create Langfuse S3 bucket | `langfuse-minio-init` | `no` (one-time) |

---

## 🔍 Viewing Containers by Group

### Using `docker ps` with Filters

```bash
# View all application services
docker ps --filter "name=echomind-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View all data services
docker ps --filter "name=data-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View all infrastructure
docker ps --filter "name=infra-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View observability stack
docker ps --filter "name=observability-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View initialization jobs (usually exited)
docker ps -a --filter "name=init-" --format "table {{.Names}}\t{{.Status}}"
```

### Using `cluster.sh status` (Improved)

The `./cluster.sh status` command now displays containers **grouped by category** with color coding:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 Application Services (GREEN)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  echomind-api                Up 2 hours
  echomind-connector          Up 2 hours
  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗄️  Data Services (CYAN)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  data-postgres               Up 2 hours (healthy)
  data-qdrant                 Up 2 hours
  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏗️  Infrastructure Services (BLUE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  infra-traefik               Up 2 hours
  infra-authentik-server      Up 2 hours
  ...

📈 Summary: 25/28 containers running
```

---

## 🔧 Docker Compose Service Names

**IMPORTANT:** Docker Compose **service names** (used for DNS resolution) remain unchanged!

- Container name: `data-postgres` ← What you see in `docker ps`
- Service name: `postgres` ← Used in connection strings and `depends_on`
- DNS name: `postgres` ← Internal Docker network DNS

**Example:**
```yaml
services:
  postgres:  # ← Service name (DNS)
    container_name: data-postgres  # ← Container name (docker ps)
    hostname: postgres  # ← Hostname (internal)
```

**Connection strings remain the same:**
```bash
DATABASE_URL=postgresql://user:pass@postgres:5432/db  # ← Uses service name
QDRANT_HOST=qdrant  # ← Uses service name
NATS_URL=nats://nats:4222  # ← Uses service name
```

---

## 🎯 Benefits of This Architecture

1. **Clear Visual Grouping** - Easy to identify service types in `docker ps`
2. **Better Filtering** - Use `docker ps --filter "name=data-"` to view specific groups
3. **Improved Monitoring** - Tools can filter/group by container name prefix
4. **Cleaner Status Output** - `cluster.sh status` shows organized view
5. **Easier Troubleshooting** - Quickly identify which layer has issues
6. **No Breaking Changes** - Service names and DNS remain unchanged

---

## 📝 Migration Notes

### For Existing Deployments

**The change is transparent** - no action needed! Container names changed, but:
- Service names (DNS) unchanged ✅
- Connection strings unchanged ✅
- Traefik routes unchanged ✅
- Docker Compose configs unchanged ✅

### If You Have Custom Scripts

Update any scripts that reference container names:

```bash
# OLD
docker logs echomind-postgres

# NEW
docker logs data-postgres
```

---

## 🐛 Troubleshooting

### Check Service Status by Group

```bash
# Check if any data services are down
docker ps --filter "name=data-" --filter "status=exited"

# Check observability stack health
docker ps --filter "name=observability-" --format "{{.Names}}: {{.Status}}"

# View logs for all app services
docker logs echomind-api -f
```

### Common Issues

1. **Container not found** - Use service name, not container name, in depends_on
2. **DNS resolution fails** - Use service name (e.g., `postgres`), not container name (`data-postgres`)
3. **Init jobs show as "Exited"** - This is normal! Init jobs run once and exit successfully

---

## 🔗 Related Documentation

- `PUBLIC-SERVICES.md` - List of all publicly accessible services
- `README-ENV.md` - Environment configuration guide
- `cluster.sh --help` - Full cluster management commands
