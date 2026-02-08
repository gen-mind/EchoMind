# Stage 1: Builder
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install system dependencies for TensorFlow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libhdf5-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY projector/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-103 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy source code
COPY echomind_lib /app/echomind_lib
COPY projector /app/projector

ENV PYTHONPATH="/app"

# Create logs directory for TensorBoard checkpoints
RUN mkdir -p /logs && \
    useradd -m -u 1000 projectoruser && \
    chown -R projectoruser:projectoruser /app /logs

USER projectoruser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

EXPOSE 8080

CMD ["python", "-m", "projector.main"]
