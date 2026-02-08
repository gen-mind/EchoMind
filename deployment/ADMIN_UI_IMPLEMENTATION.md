# Admin UI Access - Complete Implementation Guide

## Overview

This document provides step-by-step instructions for deploying admin UIs for all EchoMind infrastructure components with Authentik SSO protection.

## Prerequisites

- ✅ Authentik configured with `echomind-admins` group
- ✅ Traefik with ForwardAuth middleware (already configured)
- ✅ DNS records for new subdomains (postgres.demo.echomind.ch, nats.demo.echomind.ch)

---

## Step 1: Update Environment Variables

### Edit `.env.host`

Add new domain definitions after existing domains:

```bash
# Admin UI Subdomains
POSTGRES_DOMAIN=postgres.${DOMAIN}
NATS_DOMAIN=nats.${DOMAIN}
```

**Location**: `/Users/gp/Developer/echo-mind/deployment/docker-cluster/.env.host`
**After line**: 48 (after `PORTAINER_DOMAIN=portainer.${DOMAIN}`)

---

## Step 2: Add Services to docker-compose-host.yml

### Service 1: Adminer (PostgreSQL Admin UI)

Add after the `postgres` service (around line 128):

```yaml
  # ===============================================
  # Adminer - PostgreSQL Web UI (Protected by Authentik)
  # ===============================================
  adminer:
    image: adminer:4.8.1-standalone
    container_name: echomind-adminer
    hostname: adminer
    environment:
      - ADMINER_DEFAULT_SERVER=postgres
      - ADMINER_DESIGN=pepa-linha-dark
      - ADMINER_PLUGINS=tables-filter tinymce
    restart: unless-stopped
    networks:
      - backend
      - frontend
    depends_on:
      postgres:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.adminer.rule=Host(`${POSTGRES_DOMAIN}`)"
      - "traefik.http.routers.adminer.entrypoints=websecure"
      - "traefik.http.routers.adminer.tls.certresolver=letsencrypt"
      - "traefik.http.routers.adminer.middlewares=authentik-forward-auth"
      - "traefik.http.services.adminer.loadbalancer.server.port=8080"
```

**Key Configuration**:
- `ADMINER_DEFAULT_SERVER=postgres`: Auto-connects to PostgreSQL container
- `ADMINER_DESIGN=pepa-linha-dark`: Modern dark theme
- `ADMINER_PLUGINS=tables-filter tinymce`: Enhanced table filtering + WYSIWYG editor
- **Security**: Protected by `authentik-forward-auth` middleware

---

### Service 2: Nui (NATS Management UI)

Add after the `nats` service (around line 287):

```yaml
  # ===============================================
  # Nui - NATS Management UI (Protected by Authentik)
  # ===============================================
  nui:
    image: ghcr.io/nats-nui/nui:latest
    container_name: echomind-nui
    hostname: nui
    environment:
      # NATS connection defaults
      - NUI_NATS_URL=nats://nats:4222
      - NUI_NATS_NAME=EchoMind NATS
      # Server configuration
      - NUI_SERVER_PORT=31311
      - NUI_SERVER_HOST=0.0.0.0
      # Authentication disabled (handled by Traefik ForwardAuth)
      - NUI_SERVER_AUTH_ENABLED=false
    restart: unless-stopped
    networks:
      - backend
      - frontend
    depends_on:
      nats:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.nui.rule=Host(`${NATS_DOMAIN}`)"
      - "traefik.http.routers.nui.entrypoints=websecure"
      - "traefik.http.routers.nui.tls.certresolver=letsencrypt"
      - "traefik.http.routers.nui.middlewares=authentik-forward-auth"
      - "traefik.http.services.nui.loadbalancer.server.port=31311"
```

**Key Configuration**:
- `NUI_NATS_URL=nats://nats:4222`: Auto-connects to internal NATS server
- `NUI_SERVER_PORT=31311`: Nui's default web UI port
- `NUI_SERVER_AUTH_ENABLED=false`: Authentik handles all authentication
- **Security**: Protected by `authentik-forward-auth` middleware

---

## Step 3: Update Portainer for OAuth2/OIDC SSO

### 3.1 Create Authentik OAuth Provider

**In Authentik Admin UI** (`https://auth.demo.echomind.ch/if/admin`):

1. Navigate to **Applications** → **Providers** → **Create**
2. Select **OAuth2/OpenID Provider**
3. Configure:
   - **Name**: `portainer-oauth`
   - **Authorization flow**: `Explicit consent` (recommended) or `Implicit consent`
   - **Client type**: `Confidential`
   - **Redirect URIs**: `https://portainer.demo.echomind.ch/` (trailing slash important!)
   - **Signing Key**: `authentik Self-signed Certificate` (auto-generated)
   - **Scopes**: Select `openid`, `profile`, `email`, `groups`
4. Click **Create**
5. **Save** the generated `Client ID` and `Client Secret`

### 3.2 Create Authentik Application

1. Navigate to **Applications** → **Applications** → **Create**
2. Configure:
   - **Name**: `Portainer`
   - **Slug**: `portainer`
   - **Provider**: Select `portainer-oauth` (created above)
   - **Launch URL**: `https://portainer.demo.echomind.ch/`
3. Click **Create**

### 3.3 Assign Group Access

1. In the Portainer application page, go to **Policy / Group / User Bindings** tab
2. Click **Create Binding**
3. Select **Group**: `echomind-admins`
4. Click **Create**

### 3.4 Configure Portainer

**Access Portainer** (`https://portainer.demo.echomind.ch`):

1. Login as admin (local account)
2. Navigate to **Settings** → **Authentication**
3. Click **OAuth** tab
4. Configure:
   ```
   Client ID: <paste from Authentik provider>
   Client Secret: <paste from Authentik provider>
   Authorization URL: https://auth.demo.echomind.ch/application/o/authorize/
   Access token URL: https://auth.demo.echomind.ch/application/o/token/
   Resource URL: https://auth.demo.echomind.ch/application/o/userinfo/
   Redirect URL: https://portainer.demo.echomind.ch/
   Logout URL: https://auth.demo.echomind.ch/application/o/portainer/end-session/
   User identifier: preferred_username
   Scopes: openid profile email groups
   ```
   **IMPORTANT**: Use **spaces** between scopes, NOT commas!

5. Scroll down to **Automatic user provisioning** → **Enable**
6. Click **Save settings**

### 3.5 Test SSO Login

1. Logout from Portainer
2. You should now see **"Login with OAuth"** button
3. Click it → redirects to Authentik → auto-login → returns to Portainer
4. Verify you're logged in as your Authentik user

**Note**: Portainer Community Edition does NOT support automatic team membership or admin rights via groups. You must manually:
- Go to **Users** → find your OAuth user → **Edit** → check **Administrator** role

---

## Step 4: DNS Configuration

Add the following DNS A records pointing to your host (`demo.echomind.ch` IP):

```
postgres.demo.echomind.ch  →  <same IP as demo.echomind.ch>
nats.demo.echomind.ch      →  <same IP as demo.echomind.ch>
```

**How to verify**:
```bash
dig postgres.demo.echomind.ch +short
dig nats.demo.echomind.ch +short
# Should return your host's public IP
```

---

## Step 5: Deploy Services

### 5.1 Rebuild and Restart Cluster

```bash
cd /Users/gp/Developer/echo-mind/deployment/docker-cluster

# Deploy with host configuration
./cluster.sh -H up

# Or if services are already running:
./cluster.sh -H restart
```

### 5.2 Verify Services are Running

```bash
docker ps | grep -E "adminer|nui"
# Should show both containers running
```

### 5.3 Check Traefik Routes

```bash
# SSH tunnel to Traefik dashboard (if needed)
ssh -L 8080:localhost:8080 user@demo.echomind.ch

# Open http://localhost:8080 → HTTP Routers
# Verify: adminer@docker, nui@docker routes exist
```

---

## Step 6: Authentik Group Configuration

### 6.1 Create echomind-admins Group (if not exists)

**In Authentik Admin UI**:

1. Navigate to **Directory** → **Groups** → **Create**
2. Configure:
   - **Name**: `echomind-admins`
   - **Parent**: None
3. Click **Create**

### 6.2 Add Users to Group

1. Navigate to **Directory** → **Users**
2. Click on user → **Groups** tab → **Add to existing group**
3. Select `echomind-admins`
4. Click **Add**

### 6.3 Verify Group Access

**Test ForwardAuth protection**:

1. **Logout** from all services (clear browser cookies)
2. Visit `https://postgres.demo.echomind.ch`
   - Should redirect to Authentik login
   - After login, should show Adminer UI
3. Visit `https://nats.demo.echomind.ch`
   - Should redirect to Authentik login
   - After login, should show Nui dashboard
4. Visit `https://minio.demo.echomind.ch` (existing)
   - Verify still works with Authentik SSO
5. Visit `https://qdrant.demo.echomind.ch` (existing)
   - Verify still works with Authentik SSO

**If redirected to Authentik but get "Access Denied"**:
- User is NOT in `echomind-admins` group
- Check user's group membership in Authentik

---

## Step 7: Security Hardening

### 7.1 Rate Limiting (Optional)

Add rate limiting to admin UIs to prevent brute force:

```yaml
# In Traefik service labels (docker-compose-host.yml)
- "traefik.http.middlewares.admin-ratelimit.ratelimit.average=10"
- "traefik.http.middlewares.admin-ratelimit.ratelimit.burst=20"

# Apply to admin services:
- "traefik.http.routers.adminer.middlewares=authentik-forward-auth,admin-ratelimit"
- "traefik.http.routers.nui.middlewares=authentik-forward-auth,admin-ratelimit"
```

### 7.2 IP Whitelisting (Optional - High Security)

If you want to restrict admin UIs to specific IPs:

```yaml
# In Traefik service labels
- "traefik.http.middlewares.admin-ipwhitelist.ipwhitelist.sourcerange=YOUR_OFFICE_IP/32,YOUR_HOME_IP/32"

# Apply:
- "traefik.http.routers.adminer.middlewares=authentik-forward-auth,admin-ipwhitelist"
```

### 7.3 Audit Logging

**Adminer**: Database queries are NOT logged by default. Enable PostgreSQL query logging:

```sql
-- In PostgreSQL (via Adminer)
ALTER SYSTEM SET log_statement = 'all';
SELECT pg_reload_conf();
```

**Portainer**: Audit logs available at **Settings** → **Audit**

**Authentik**: All SSO events logged at **Events** → **Logs**

---

## Step 8: Access URLs Summary

| Service | URL | Auth Method | Credentials |
|---------|-----|-------------|-------------|
| **Adminer** | https://postgres.demo.echomind.ch | Authentik SSO | `echomind-admins` group |
| **Nui** | https://nats.demo.echomind.ch | Authentik SSO | `echomind-admins` group |
| **Portainer** | https://portainer.demo.echomind.ch | OAuth2/OIDC | Authentik user account |
| **MinIO** | https://minio.demo.echomind.ch | ForwardAuth | `echomind-admins` group |
| **Qdrant** | https://qdrant.demo.echomind.ch | ForwardAuth | `echomind-admins` group |
| **Authentik** | https://auth.demo.echomind.ch | Local login | Bootstrap credentials |

**First-time Adminer Login**:
- **Server**: `postgres` (auto-filled)
- **Username**: `echomind` (from `POSTGRES_USER` env var)
- **Password**: `POSTGRES_PASSWORD` value from `.env.host`
- **Database**: Select `echomind` or `authentik`

**First-time Nui Access**:
- Opens directly to NATS dashboard
- Pre-configured connection to `nats://nats:4222`
- Click **Streams** to view JetStream streams
- Click **Consumers** to view consumer groups

---

## Troubleshooting

### Issue: "Access Denied" after Authentik login

**Cause**: User not in `echomind-admins` group

**Solution**:
1. Login to Authentik as admin
2. Navigate to **Directory** → **Users** → [Your User]
3. Go to **Groups** tab → **Add to existing group** → `echomind-admins`

---

### Issue: Adminer shows "Connection refused"

**Cause**: Adminer container cannot reach PostgreSQL

**Solution**:
```bash
# Check if both containers are on same network
docker network inspect docker-cluster_backend | grep -E "adminer|postgres"

# Should show both containers
```

---

### Issue: Nui shows "Connection failed"

**Cause**: NATS connection string incorrect

**Solution**:
1. Check NATS is running: `docker ps | grep nats`
2. Verify network: `docker network inspect docker-cluster_backend | grep nui`
3. Check Nui logs: `docker logs echomind-nui`

---

### Issue: Portainer OAuth button not appearing

**Cause**: OAuth not enabled or misconfigured

**Solution**:
1. Login as local admin
2. Go to **Settings** → **Authentication** → **OAuth** tab
3. Verify all fields are filled
4. Click **Save settings**
5. Logout and refresh page

---

### Issue: SSL certificate errors

**Cause**: Let's Encrypt not yet issued certificates for new subdomains

**Solution**:
```bash
# Check Traefik logs
docker logs echomind-traefik 2>&1 | grep -i "postgres\|nats"

# Check certificate status
ls -lah /Users/gp/Developer/echo-mind/data/traefik/certificates/

# Force certificate renewal (if needed)
docker exec echomind-traefik traefik healthcheck
```

Wait 1-2 minutes for Let's Encrypt to issue certificates.

---

## Security Best Practices

1. **Rotate Credentials**: Change PostgreSQL password periodically
2. **Audit Logs**: Review Authentik event logs weekly
3. **Update Images**: Run `docker compose pull` monthly for security patches
4. **Backup**: Backup PostgreSQL data and Authentik config before changes
5. **Least Privilege**: Only add users to `echomind-admins` who need full cluster access
6. **MFA**: Enable 2FA in Authentik for admin users (**Settings** → **MFA**)

---

## Rollback Procedure

If any service fails, you can quickly rollback:

```bash
# Remove new services
docker compose -f docker-compose-host.yml stop adminer nui
docker compose -f docker-compose-host.yml rm -f adminer nui

# Revert .env.host changes
git checkout deployment/docker-cluster/.env.host

# Restart cluster
./cluster.sh -H restart
```

---

## Next Steps

After successful deployment:

1. ✅ Add DNS records for new subdomains
2. ✅ Configure Portainer OAuth provider in Authentik
3. ✅ Test SSO login for all services
4. ✅ Add yourself to `echomind-admins` group
5. ✅ Verify PostgreSQL access via Adminer
6. ✅ Verify NATS streams visible in Nui
7. ✅ Document credentials in password manager
8. ✅ Set up automated backups for PostgreSQL

---

**Last Updated**: 2026-02-07
**Tested Environment**: EchoMind v0.1.0-beta.5, Authentik 2025.10.3, Traefik 3.3
