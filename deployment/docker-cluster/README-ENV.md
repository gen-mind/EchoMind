# Environment Configuration Guide

## 🔑 Key Principle

**`.env.host` and `.env.example` are TEMPLATES ONLY**

Each deployment environment (local dev, staging, production) has its own **`.env`** file with actual credentials.

---

## 📁 File Purpose

| File | Purpose | Contains Secrets? | Git Tracked? |
|------|---------|-------------------|--------------|
| **`.env`** | Actual config with real secrets | ✅ YES | ❌ NO (gitignored) |
| `.env.example` | Template for local development | ❌ NO (placeholders) | ✅ YES |
| `.env.host` | Template for production deployment | ❌ NO (placeholders) | ✅ YES |

---

## 🚀 Setup Instructions

### For Local Development

```bash
cd deployment/docker-cluster

# 1. Create .env from template
cp .env.example .env

# 2. Edit .env with your local settings
nano .env

# 3. Start cluster
./cluster.sh -L start
```

### For Production (Host) Deployment

```bash
cd deployment/docker-cluster

# 1. Create .env from template
cp .env.host .env

# 2. Edit .env and replace ALL CHANGE_ME_* values
nano .env
# - Generate secrets: openssl rand -hex 32
# - Replace your-domain.example.com with actual domain
# - Set real passwords for all services

# 3. Start cluster
./cluster.sh -H start
```

---

## ⚠️ Important Notes

1. **Never commit `.env`** - It contains real secrets and is gitignored
2. **Both `cluster.sh -L` and `-H` use `.env`** - Templates are just starting points
3. **Each environment needs its own `.env`** - Local, staging, and production each have separate `.env` files
4. **Templates are safe to edit and commit** - `.env.example` and `.env.host` have no real secrets

---

## 🔧 Migration from Old Architecture (Pre-2026-02-08)

If you have an existing deployment where `cluster.sh -H` was using `.env.host` directly:

```bash
# On production host
cd /path/to/deployment/docker-cluster

# Option 1: If your .env.host has real secrets (old architecture)
cp .env.host .env
./cluster.sh -H restart

# Option 2: If you have a separate .env already
# Just verify it has correct secrets and restart
./cluster.sh -H restart
```

---

## 🛡️ Security Best Practices

1. **Generate strong secrets:**
   ```bash
   openssl rand -hex 32
   ```

2. **Never share `.env` files** - Each team member/environment gets their own

3. **Back up `.env` securely** - Store encrypted backups of production `.env` in a secure location

4. **Rotate secrets regularly** - Update passwords and keys periodically

5. **Use environment-specific values** - Don't reuse passwords across environments

---

## 🐛 Troubleshooting

### Error: ".env file not found"
```bash
cp .env.host .env  # or .env.example for local
nano .env          # Edit with real values
```

### Error: "password authentication failed"
- Check `POSTGRES_PASSWORD` in `.env` matches what PostgreSQL was initialized with
- If unsure, see recovery steps in `deployment-config.md`

### Warning: ".env contains placeholder values"
- Search for `CHANGE_ME_` in `.env` and replace with real secrets
- Never deploy with placeholder values

---

## 📚 Related Documentation

- `deployment-config.md` - Detailed architecture explanation
- `CLAUDE.md` - Full project guidelines
- `.claude/projects/.../memory/MEMORY.md` - AI assistant memory
