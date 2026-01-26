# Migration Service

> **Service:** `echomind-migration`
> **Protocol:** None (batch job)
> **Port:** None

---

## What It Does

The Migration Service is a **batch job** that manages database schema migrations:

- Runs Alembic migrations on startup
- Applies pending schema changes to PostgreSQL
- Handles version tracking and rollback capability
- Runs as an init container in Kubernetes
- Ensures database is ready before other services start

---

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph MigrationService["echomind-migration"]
        ALEMBIC[Alembic Runner]
        VERSIONS[Migration Scripts]
    end

    subgraph External
        DB[(PostgreSQL)]
    end

    ALEMBIC --> VERSIONS
    ALEMBIC --> DB
    DB -->|alembic_version| ALEMBIC
```

### Migration Flow

```mermaid
sequenceDiagram
    participant K as Kubernetes
    participant M as Migration Job
    participant DB as PostgreSQL

    K->>M: Start init container

    M->>DB: Check connection
    alt Connection failed
        M->>K: Exit 1 (retry)
    end

    M->>DB: Query alembic_version
    DB-->>M: Current revision

    M->>M: Get target revision (head)

    alt Migrations pending
        loop Each migration
            M->>DB: Apply migration
            M->>DB: Update alembic_version
        end
        M-->>K: Exit 0 (success)
    else Already up-to-date
        M-->>K: Exit 0 (success)
    end

    K->>K: Start main services
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Migration Tool | Alembic |
| ORM | SQLAlchemy |
| Database | PostgreSQL |

---

## Database Tables Used

| Table | Operations | Reference |
|-------|------------|-----------|
| `alembic_version` | Read, Create, Update | Alembic internal |
| All tables | Create, Alter, Drop | [DB Schema](../db-schema.md) |

---

## Proto Definitions Used

**None.** This service does not use Protocol Buffers.

---

## NATS Messaging

**None.** This service does not use NATS messaging.

---

## Alembic Configuration

### alembic.ini

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[alembic:exclude]
tables = spatial_ref_sys

sqlalchemy.url = driver://user:pass@localhost/dbname
```

### env.py

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

from echomind_lib.db.models import Base

config = context.config

# Override with environment variable
config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
)

target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## Service Structure

```
src/services/migration/
├── main.py                 # Entry point
├── alembic.ini             # Alembic config
├── alembic/
│   ├── env.py              # Migration environment
│   ├── script.py.mako      # Migration template
│   └── versions/           # Migration scripts
│       ├── 001_initial.py
│       ├── 002_add_connectors.py
│       ├── 003_add_documents.py
│       └── ...
└── config.py
```

---

## Migration Scripts

### Example Migration

```python
# alembic/versions/001_initial.py
"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # Connectors table
    op.create_table(
        "connectors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("connectors")
    op.drop_table("users")
```

---

## Configuration

```bash
# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/echomind

# Migration settings
MIGRATION_RETRY_COUNT=5       # Retries if DB not ready
MIGRATION_RETRY_DELAY=5       # Seconds between retries
```

---

## Entry Point

```python
# main.py
import os
import sys
import time
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def wait_for_db(database_url: str, retries: int = 5, delay: int = 5):
    """Wait for database to be ready."""
    engine = create_engine(database_url)

    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Database is ready")
            return True
        except OperationalError as e:
            print(f"⏳ Waiting for database (attempt {attempt + 1}/{retries})...")
            time.sleep(delay)

    print("❌ Database not ready after retries")
    return False


def run_migrations():
    """Run Alembic migrations."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)

    # Wait for database
    if not wait_for_db(database_url):
        sys.exit(1)

    # Run migrations
    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

        print("🚀 Running migrations...")
        command.upgrade(alembic_cfg, "head")
        print("✅ Migrations completed successfully")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migrations()
```

---

## Kubernetes Deployment

### Init Container

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echomind-api
spec:
  template:
    spec:
      initContainers:
        - name: migration
          image: echomind-migration:latest
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: echomind-secrets
                  key: database-url
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "200m"
      containers:
        - name: api
          image: echomind-api:latest
          # ... API container config
```

### Standalone Job

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: echomind-migration
spec:
  template:
    spec:
      containers:
        - name: migration
          image: echomind-migration:latest
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: echomind-secrets
                  key: database-url
      restartPolicy: OnFailure
  backoffLimit: 3
```

---

## CLI Commands

### Create New Migration

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "Add new_column to users"

# Create empty migration
alembic revision -m "Custom migration"
```

### Apply Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade 003

# Upgrade one step
alembic upgrade +1
```

### Rollback Migrations

```bash
# Downgrade one step
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade 002

# Downgrade to base (empty)
alembic downgrade base
```

### View Status

```bash
# Show current revision
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic history --indicate-current
```

---

## Error Handling

| Error | Handling |
|-------|----------|
| Database not reachable | Retry with exponential backoff |
| Migration conflict | Exit with error, manual intervention needed |
| Syntax error in migration | Exit with error, fix migration script |
| Constraint violation | Rollback, exit with error |

---

## Best Practices

1. **Always test migrations** on a copy of production data
2. **Never edit** a migration that's been deployed
3. **Keep migrations small** and focused
4. **Use transactions** (Alembic does this by default)
5. **Back up database** before major migrations
6. **Review autogenerated** migrations before applying

---

## Health Check

This service is a batch job and does not expose health endpoints. Success/failure is determined by exit code:

| Exit Code | Meaning |
|-----------|---------|
| 0 | Migrations successful |
| 1 | Migration failed |

---

## References

- [DB Schema](../db-schema.md) - Database schema documentation
- [Alembic Documentation](https://alembic.sqlalchemy.org/) - Migration tool docs
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM documentation
