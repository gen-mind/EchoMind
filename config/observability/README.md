# EchoMind Observability Stack

Grafana + Prometheus + Loki observability stack for EchoMind.

## Quick Start

1. Set `ENABLE_OBSERVABILITY=true` in your `.env` file
2. Run `./cluster.sh -L start` (local) or `./cluster.sh -H start` (host)
3. Open Grafana at `http://grafana.localhost` (local) or `https://grafana.demo.echomind.ch` (host)

## Components

| Service | Purpose | Port |
|---------|---------|------|
| Prometheus | Metrics backend | 9090 |
| Loki | Log aggregation | 3100 |
| Grafana | Dashboards + visualization | 3000 |
| Alloy | Log collector (Docker stdout) | 12345 |
| cAdvisor | Container CPU/memory/network metrics | 8080 |
| node-exporter | Host OS metrics | 9100 |
| nats-exporter | NATS metrics (JSON → Prometheus) | 7777 |
| postgres-exporter | PostgreSQL metrics | 9187 |

## Pre-loaded Dashboards

All dashboards are in the "EchoMind" folder in Grafana:

| Dashboard | Source | What it shows |
|-----------|--------|---------------|
| Docker Containers | Grafana #14282 | Per-container CPU, memory, network, restarts |
| Node Exporter Full | Grafana #1860 | Host CPU, memory, disk, network |
| NATS Server | Grafana #2279 | NATS connections, throughput |
| NATS JetStream | Grafana #14725 | Stream/consumer message counts, pending |
| Traefik3 | Grafana #2870 | Request rate, latency, error % |
| PostgreSQL | Grafana #9628 | Connections, transactions, locks, cache hit ratio |
| MinIO | Grafana #13502 | Cluster capacity, S3 traffic |
| Qdrant | Grafana #24074 | Vector DB metrics + logs |
| Loki Metrics | Grafana #17781 | Loki self-monitoring |
| EchoMind Overview | Custom | Service health grid, error rate, NATS queue depth |
| Loki Logs Explorer | Custom | Service log browser with level filter |

## Authentik Setup (Required for Host Mode)

Grafana uses direct OIDC with Authentik. Follow these steps once in the Authentik admin UI:

### 1. Create Custom Scope Mapping

Go to **Customization → Property Mappings → Create → Scope Mapping**:

- **Name:** `Grafana Groups`
- **Scope name:** `grafana`
- **Expression:**
  ```python
  return {
      "info": {
          "groups": [group.name for group in request.user.ak_groups.all()],
      },
  }
  ```

### 2. Create OAuth2/OIDC Provider

Go to **Applications → Providers → Create → OAuth2/OpenID Provider**:

- **Name:** `Grafana`
- **Client type:** Confidential
- **Redirect URI:** `https://grafana.demo.echomind.ch/login/generic_oauth`
- **Signing Key:** Select available key
- **Scopes:** Add the `Grafana Groups` mapping created above (in addition to defaults)
- Copy the **Client ID** and **Client Secret** → paste into `.env.host` as `GRAFANA_OAUTH_CLIENT_ID` and `GRAFANA_OAUTH_CLIENT_SECRET`

### 3. Create Application

Go to **Applications → Applications → Create**:

- **Name:** `Grafana`
- **Slug:** `grafana`
- **Provider:** Select the Grafana provider created above
- **Launch URL:** `https://grafana.demo.echomind.ch`

### 4. Restrict Access

On the Application page, go to **Policy/Group/User Bindings**:

- Bind group: `echomind-admins`
- Only members of this group can access Grafana

### Role Mapping

The Grafana configuration maps Authentik groups to Grafana roles:
- `echomind-admins` group → **GrafanaAdmin** (full access)
- All other users → **Viewer** (read-only, but blocked at Authentik level by the binding above)

## Useful Loki Queries

```logql
# All logs from a specific service
{service="api"}

# Error logs across all services
{platform="docker"} |= "ERROR"

# Logs from a specific container
{container="echomind-api"}

# Filter by log level (if parsed by Alloy)
{service="api"} | level = "ERROR"

# Search for a specific term
{service="ingestor"} |= "document_id"
```

## Notes

- **macOS (dev):** cAdvisor and node-exporter require Linux. They will not produce metrics on macOS. This is expected.
- **Retention:** Prometheus retains metrics for 30 days. Loki accepts logs up to 7 days old and allows queries up to 30 days.
- **Alloy** automatically discovers all Docker containers. No per-service configuration needed.
- Containers can opt out of log collection by adding `labels: { logging: "false" }` in docker-compose.
