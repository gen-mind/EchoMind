# EchoMind Embedder Service Dockerfile
#
# Multi-stage build for GPU-enabled embedding service.
# Supports CUDA for GPU acceleration.

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first (for caching)
COPY echomind_lib /app/src/echomind_lib

# Copy embedder service
COPY embedder /app/src/embedder

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    grpcio>=1.60.0 \
    grpcio-tools>=1.60.0 \
    sentence-transformers>=2.2.0 \
    torch>=2.0.0 \
    pydantic>=2.0.0 \
    pydantic-settings>=2.0.0 \
    protobuf>=5.28.0 \
    protobuf-pydantic-gen>=0.1.8 \
    qdrant-client>=1.12.0 \
    requests>=2.28.0


# Stage 2: Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app/src /app/src

# Set Python path
ENV PYTHONPATH=/app/src

# Pre-download the default model during build (required for fast startup)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Set offline mode AFTER download to prevent runtime network calls
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# Expose ports
EXPOSE 50051 8080

# Set working directory
WORKDIR /app/src/embedder

# Health check - start-period extended for initial model download
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Run embedder
CMD ["python", "main.py"]
