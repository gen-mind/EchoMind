# Langfuse Setup Guide

Langfuse v3 provides LLM observability and RAGAS evaluation for EchoMind.

## Prerequisites

- Running EchoMind cluster (`./cluster.sh -H` or `./cluster.sh -L`)
- PostgreSQL, MinIO, and Redis already operational
- DNS record for `langfuse.<DOMAIN>` pointing to your server

## Architecture

```
                    +------------------+
                    | langfuse-web:3000|
                    |  (UI + API)      |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
    +---------+--+   +------+-----+  +-----+------+
    | PostgreSQL |   | ClickHouse |  |   Redis    |
    | (langfuse) |   |  (traces)  |  |  (cache)   |
    +------------+   +------------+  +------------+
              |
    +---------+--+
    | langfuse-  |
    | worker:3030|
    | (async)    |
    +------------+
```

Langfuse shares PostgreSQL, MinIO, and Redis with EchoMind. ClickHouse is dedicated to Langfuse for OLAP trace storage.

## Environment Variables

All variables are set in `deployment/docker-cluster/.env.host`:

| Variable | Description | Example |
|----------|-------------|---------|
| `ENABLE_LANGFUSE` | Master toggle | `true` |
| `LANGFUSE_NEXTAUTH_SECRET` | NextAuth session encryption | `openssl rand -hex 32` |
| `LANGFUSE_SALT` | Password hashing salt | `openssl rand -hex 32` |
| `LANGFUSE_ENCRYPTION_KEY` | Data-at-rest encryption (64 hex chars) | `openssl rand -hex 32` |
| `LANGFUSE_CLICKHOUSE_PASSWORD` | ClickHouse auth password | `openssl rand -hex 16` |
| `LANGFUSE_PUBLIC_KEY` | SDK public key (set once) | `pk-echomind-<random>` |
| `LANGFUSE_SECRET_KEY` | SDK secret key (set once) | `sk-echomind-<random>` |
| `LANGFUSE_INIT_EMAIL` | Bootstrap admin email | `admin@echomind.ch` |
| `LANGFUSE_INIT_PASSWORD` | Bootstrap admin password | Strong password |
| `LANGFUSE_DOMAIN` | Subdomain (auto-derived) | `langfuse.demo.echomind.ch` |
| `LANGFUSE_OAUTH_ENABLED` | Enable Authentik SSO | `true` / `false` |
| `LANGFUSE_OAUTH_CLIENT_ID` | Authentik OAuth2 client ID | From Authentik UI |
| `LANGFUSE_OAUTH_CLIENT_SECRET` | Authentik OAuth2 client secret | From Authentik UI |
| `RAGAS_SAMPLE_RATE` | Fraction of requests to auto-evaluate | `0.1` (10%) |

## Generating Secrets

```bash
# Run these commands and paste results into .env.host
echo "LANGFUSE_NEXTAUTH_SECRET=$(openssl rand -hex 32)"
echo "LANGFUSE_SALT=$(openssl rand -hex 32)"
echo "LANGFUSE_ENCRYPTION_KEY=$(openssl rand -hex 32)"
echo "LANGFUSE_CLICKHOUSE_PASSWORD=$(openssl rand -hex 16)"
echo "LANGFUSE_INIT_PASSWORD=$(openssl rand -base64 24)"

# SDK keys (prefix helps identify in logs)
echo "LANGFUSE_PUBLIC_KEY=pk-echomind-$(openssl rand -hex 8)"
echo "LANGFUSE_SECRET_KEY=sk-echomind-$(openssl rand -hex 16)"
```

## Enabling Langfuse

1. Edit `deployment/docker-cluster/.env.host`:
   ```
   ENABLE_LANGFUSE=true
   ```

2. Set all secrets (see Generating Secrets above).

3. Deploy:
   ```bash
   ./cluster.sh -H
   ```

The `cluster.sh` script reads `ENABLE_LANGFUSE` and includes the Langfuse compose file with the `langfuse` Docker Compose profile. The migration container auto-creates the `langfuse` PostgreSQL database on first run.

## Authentik OIDC Setup (Optional)

To enable SSO via Authentik:

1. Open Authentik Admin: `https://auth.<DOMAIN>/if/admin/`

2. Create a new **OAuth2/OpenID Provider**:
   - Name: `langfuse`
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - Client Type: `Confidential`
   - Redirect URI: `https://langfuse.<DOMAIN>/api/auth/callback/custom`
   - Signing Key: Select your existing key

3. Create a new **Application**:
   - Name: `Langfuse`
   - Slug: `langfuse`
   - Provider: Select `langfuse` (created above)

4. Copy the Client ID and Client Secret from the provider.

5. Update `.env.host`:
   ```
   LANGFUSE_OAUTH_ENABLED=true
   LANGFUSE_OAUTH_CLIENT_ID=<paste client ID>
   LANGFUSE_OAUTH_CLIENT_SECRET=<paste client secret>
   ```

6. Redeploy:
   ```bash
   ./cluster.sh -H
   ```

## Verification

1. **Health check**:
   ```bash
   curl https://langfuse.<DOMAIN>/api/public/health
   # Expected: {"status":"OK"}
   ```

2. **Login**: Navigate to `https://langfuse.<DOMAIN>` and sign in with the bootstrap admin credentials (or Authentik SSO if configured).

3. **Trigger a chat**: Send a message through EchoMind. Check Langfuse Traces for a new trace with the conversation.

4. **Run batch evaluation**: In the WebUI, go to Admin > Evaluations > RAGAS tab. Set limit and min messages, then click "Run Batch Evaluation". Results appear as scores on the Langfuse traces.

5. **Check Prometheus metrics**:
   ```bash
   curl https://api.<DOMAIN>/metrics | grep ragas_
   ```

6. **Grafana dashboard**: Navigate to Grafana > EchoMind > RAGAS Evaluation dashboard.

7. **Migration logs** (first deployment only):
   ```bash
   docker logs echomind-migration 2>&1 | grep -i langfuse
   # Expected: "Langfuse database created" or "Langfuse database already exists"
   ```
