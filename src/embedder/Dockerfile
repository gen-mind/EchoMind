# EchoMind Embedder Service Dockerfile
#
# Multi-stage build for GPU-enabled embedding service.
# Supports CUDA for GPU acceleration.

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

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
# Note: transformers==4.47.1 is required for NVIDIA embedding models
# Using --retries and --timeout for network resilience
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --retries 10 --timeout 120 \
    grpcio>=1.60.0 \
    grpcio-tools>=1.60.0 \
    sentence-transformers>=2.2.0 \
    transformers==4.47.1 \
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
# NVIDIA embedding model: 1B params, 2048 dim, ~2-4GB VRAM (BF16)
# Note: trust_remote_code=True is required for NVIDIA models
# Note: nvidia/llama-nemotron-embed-1b-v2 is publicly available (not gated)
ARG HF_TOKEN=""
RUN if [ -n "$HF_TOKEN" ]; then \
        echo "🔑 Using provided HF_TOKEN for authentication"; \
        pip install --no-cache-dir huggingface_hub && \
        python -c "from huggingface_hub import login; login(token='$HF_TOKEN')"; \
    else \
        echo "ℹ️  No HF_TOKEN provided - downloading publicly available model"; \
    fi && \
    echo "📥 Pre-downloading model: nvidia/llama-nemotron-embed-1b-v2" && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nvidia/llama-nemotron-embed-1b-v2', trust_remote_code=True)"

# Set offline mode AFTER download to prevent runtime network calls
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# Expose ports
EXPOSE 50051 8080

# Set working directory
WORKDIR /app/src/embedder

# Health check - model is pre-downloaded so startup is fast
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Run embedder
CMD ["python", "main.py"]
