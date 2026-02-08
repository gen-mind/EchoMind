# EchoMind Server Installation - Quick Start Guide

> **Automated installation for Hetzner dedicated servers running Ubuntu 24.04**

## Overview

This directory contains a fully automated installation system that deploys EchoMind with:

- ✅ **HTTPS** (Let's Encrypt SSL certificates)
- ✅ **Security** (fail2ban, UFW firewall)
- ✅ **Docker** (version 28.5.2 for PyCharm compatibility)
- ✅ **Traefik** reverse proxy with subdomain routing
- ✅ **20+ microservices** (API, connectors, ingestor, etc.)
- ✅ **Authentik** OIDC authentication
- ✅ **Observability** (Grafana, Prometheus, Loki - optional)
- ✅ **Langfuse** LLM tracing (optional)

---

## Installation in 4 Steps

### Step 1: Prepare Configuration (5 minutes)

```bash
# On your Hetzner server (as root)
cd /root
git clone https://github.com/gen-mind/EchoMind.git echo-mind
cd echo-mind/deployment

# Copy template
cp echomind-install.conf.template echomind-install.conf

# Edit configuration
nano echomind-install.conf
```

**Fill these REQUIRED fields:**

```bash
DOMAIN="echomind.pinewood.com"           # Your domain
SERVER_IP="65.108.201.29"                # Your server IP
ACME_EMAIL="admin@pinewood.com"          # Email for SSL certs
POSTGRES_PASSWORD="strong-password-123"  # PostgreSQL password
AUTHENTIK_SECRET_KEY="$(openssl rand -hex 32)"  # Authentik secret
AUTHENTIK_BOOTSTRAP_PASSWORD="admin-pass-456"   # Authentik admin password
MINIO_ROOT_PASSWORD="minio-pass-789"     # MinIO password
```

Save and exit: `Ctrl+X`, `Y`, `Enter`

---

### Step 2: Configure DNS (5 minutes)

**Before running installation**, configure DNS wildcard record:

**Option A: Wildcard CNAME (Recommended)**

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `echomind` | `65.108.201.29` | 300 |
| CNAME | `*` | `echomind.pinewood.com` | 300 |

**Option B: Individual A Records**

| Type | Name | Value |
|------|------|-------|
| A | `echomind` | `65.108.201.29` |
| A | `auth` | `65.108.201.29` |
| A | `api` | `65.108.201.29` |
| A | `qdrant` | `65.108.201.29` |
| A | `minio` | `65.108.201.29` |
| A | `portainer` | `65.108.201.29` |
| ... | ... | ... |

**Verify DNS:**

```bash
dig echomind.pinewood.com +short
# Should return: 65.108.201.29

dig api.echomind.pinewood.com +short
# Should return: echomind.pinewood.com OR 65.108.201.29
```

**⚠️ Wait 5-10 minutes for DNS propagation before Step 3!**

---

### Step 3: Run Installation (20 minutes)

```bash
# Make script executable
chmod +x install-echomind-server.sh

# Run installation
bash install-echomind-server.sh
```

**The script will:**

1. Validate your configuration
2. Ask for confirmation (`y` to proceed)
3. Install system packages (fail2ban, git, curl, htop, ufw)
4. Configure UFW firewall (allow ports 22, 80, 443)
5. Install Docker 28.5.2
6. Clone repositories (echo-mind + echo-mind-webui)
7. Generate `.env.host` configuration
8. Create data directories
9. Deploy EchoMind cluster (pulls images, starts 20+ containers)
10. Display access URLs and next steps

**Installation time:** ~15-30 minutes (depends on internet speed)

---

### Step 4: Configure Authentik (10 minutes)

**After installation completes:**

1. **Access Authentik:**
   - URL: `https://auth.echomind.pinewood.com`
   - Email: (from installation output)
   - Password: (from installation output)

2. **Create OAuth2 Provider:**
   - **Admin Interface** → **Applications** → **Providers** → **Create**
   - Type: **OAuth2/OpenID Provider**
   - Name: `echomind-web`
   - Client Type: **Confidential**
   - Redirect URIs: `https://echomind.pinewood.com/oauth/oidc/callback`
   - **Copy Client ID and Client Secret**

3. **Update Configuration:**
   ```bash
   cd /root/echo-mind/deployment/docker-cluster
   nano .env.host

   # Update these lines:
   WEB_OIDC_CLIENT_ID=<paste-client-id>
   WEB_OIDC_CLIENT_SECRET=<paste-client-secret>
   ```

4. **Restart Cluster:**
   ```bash
   ./cluster.sh -H restart
   ```

5. **Test Login:**
   - Visit: `https://echomind.pinewood.com`
   - Click "Login with Authentik"
   - Should redirect and login successfully

---

## Access Your EchoMind Instance

After installation, access these URLs:

| Service | URL | Description |
|---------|-----|-------------|
| **Web App** | `https://echomind.pinewood.com` | Main application |
| **API Docs** | `https://api.echomind.pinewood.com/api/v1/docs` | Swagger UI |
| **Authentik** | `https://auth.echomind.pinewood.com` | Authentication |
| **Qdrant** | `https://qdrant.echomind.pinewood.com` | Vector database |
| **MinIO** | `https://minio.echomind.pinewood.com` | Object storage |
| **Portainer** | `https://portainer.echomind.pinewood.com` | Container management |
| **DB Admin** | `https://db.echomind.pinewood.com` | PostgreSQL (Adminer) |
| **NATS** | `https://nats.echomind.pinewood.com` | Message queue UI |

**Optional services:**

| Service | URL | When Available |
|---------|-----|----------------|
| **Langfuse** | `https://langfuse.echomind.pinewood.com` | If `ENABLE_LANGFUSE=true` |
| **Grafana** | `https://grafana.echomind.pinewood.com` | If `ENABLE_OBSERVABILITY=true` |
| **Prometheus** | `https://prometheus.echomind.pinewood.com` | If `ENABLE_OBSERVABILITY=true` |

---

## Useful Commands

```bash
cd /root/echo-mind/deployment/docker-cluster

# View cluster status
./cluster.sh -H status

# View logs (all services)
./cluster.sh -H logs

# View logs (specific service)
./cluster.sh -H logs api

# Restart cluster
./cluster.sh -H restart

# Stop cluster
./cluster.sh -H stop

# Rebuild service (force, no cache)
./cluster.sh -H rebuild api

# System monitoring
htop
docker stats
df -h
```

---

## Troubleshooting

### Installation Failed

```bash
# Check installation log
cat /root/echo-mind/deployment/install-*.log

# Verify configuration
cat /root/echo-mind/deployment/echomind-install.conf

# Re-run installation (idempotent, safe to re-run)
bash /root/echo-mind/deployment/install-echomind-server.sh
```

### DNS Not Working

```bash
# Test DNS resolution
dig echomind.pinewood.com +short
dig api.echomind.pinewood.com +short

# If empty, check:
# 1. DNS records created correctly in your DNS provider
# 2. Wait 5-10 minutes for propagation
# 3. Check TTL settings (lower = faster propagation)
```

### SSL Certificates Not Generating

```bash
# Check Traefik logs
docker logs echomind-traefik | grep -i acme

# Common causes:
# - DNS not propagated yet (wait longer)
# - Port 443 blocked (check UFW: sudo ufw status)
# - Let's Encrypt rate limit (wait 7 days or use staging)
```

### Service Not Starting

```bash
# Check service logs
./cluster.sh -H logs <service-name>

# Check container status
docker ps -a | grep echomind

# Check service health
docker inspect echomind-<service-name> | grep -i health
```

---

## Files Created by Installation

```
deployment/
├── install-echomind-server.sh          ← Main installation script
├── echomind-install.conf.template      ← Configuration template
├── echomind-install.conf               ← Your configuration
├── install-YYYYMMDD-HHMMSS.log         ← Installation log
├── INSTALLATION-README.md              ← Detailed documentation
├── QUICK-START.md                      ← This file
└── docker-cluster/
    ├── .env.host                       ← Generated config (from echomind-install.conf)
    └── cluster.sh                      ← Cluster management script

excluded/
├── todo-installation.md                ← Post-installation manual steps
└── installation-credentials.txt        ← All passwords (mode 600, KEEP SECURE)

data/                                   ← Persistent data
├── postgres/                           ← Database data
├── qdrant/                             ← Vector embeddings
├── minio/                              ← Object storage
├── traefik/certificates/               ← SSL certificates
└── ...
```

---

## Security Notes

### Firewall (UFW)

The installation configures UFW to **allow ONLY**:
- Port 22 (SSH)
- Port 80 (HTTP → redirects to HTTPS)
- Port 443 (HTTPS)

All other ports are **DENIED**.

### Fail2ban

Automatically bans IPs after failed SSH login attempts.

### Credentials File

All passwords saved to:
```
/root/echo-mind/excluded/installation-credentials.txt
```

**⚠️ IMPORTANT:**
- File permissions: `600` (owner-only read/write)
- Contains ALL sensitive credentials
- **Copy to secure location** (password manager, encrypted storage)
- **Delete from server** after copying (optional)

### SSH Hardening (Recommended)

After installation:

```bash
# Disable password authentication (key-only)
nano /etc/ssh/sshd_config
# Set: PermitRootLogin prohibit-password
# Set: PasswordAuthentication no
systemctl restart sshd
```

---

## Next Steps

1. ✅ **Installation Complete**
2. ✅ **DNS Configured**
3. ✅ **Authentik OIDC Setup** (Step 4 above)
4. ⏭️ **PyCharm Remote Docker** (optional, see `excluded/todo-installation.md` Section 4)
5. ⏭️ **Langfuse Configuration** (if enabled, see `excluded/todo-installation.md` Section 5)
6. ⏭️ **Upload Documents** via WebUI
7. ⏭️ **Create Assistants** and start chatting

---

## Documentation

| Document | Description |
|----------|-------------|
| `INSTALLATION-README.md` | Complete installation guide |
| `QUICK-START.md` | This quick start (4-step guide) |
| `echomind-install.conf.template` | Configuration template |
| `excluded/todo-installation.md` | Post-installation manual steps |
| `docker-cluster/README.md` | Cluster management guide |
| `../docs/architecture.md` | System architecture |
| `../docs/api-spec.md` | API documentation |

---

## Support

- **Installation Issues:** Check `install-*.log` and re-run script
- **DNS Issues:** See `excluded/todo-installation.md` Section 1
- **SSL Issues:** See `excluded/todo-installation.md` Section 2
- **Authentik Issues:** See `excluded/todo-installation.md` Section 3
- **GitHub Issues:** https://github.com/gen-mind/EchoMind/issues

---

**Version:** 1.0.0
**Date:** 2026-02-08
**Author:** EchoMind Team
