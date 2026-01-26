# EchoMind Migration Service Dockerfile
#
# Multi-stage build for minimal production image.
# This service runs as a Kubernetes init container or batch job.

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first (for caching)
COPY echomind_lib /app/src/echomind_lib

# Copy migration service
COPY migration /app/src/migration

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    alembic>=1.13.0 \
    sqlalchemy>=2.0.0 \
    psycopg2-binary>=2.9.0 \
    pydantic>=2.0.0 \
    pydantic-settings>=2.0.0


# Stage 2: Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app/src /app/src

# Set Python path
ENV PYTHONPATH=/app/src

# Set working directory to migration service
WORKDIR /app/src/migration

# Run migrations
CMD ["python", "main.py"]
