# EchoMind Ingestor Service Dockerfile
#
# Multi-stage build for document ingestion pipeline.
# Uses nv-ingest-api for extraction and transformers for tokenization.

# ===============================================
# Stage 1: Builder - Install dependencies
# ===============================================
FROM python:3.12.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (cache layer optimization)
COPY ingestor/requirements.txt .

# Install Python dependencies in a separate location
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===============================================
# Stage 2: Runtime - Minimal final image
# ===============================================
FROM python:3.12.12-slim-bookworm

WORKDIR /app

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY ingestor /app/ingestor
COPY echomind_lib /app/echomind_lib

# Set Python path
ENV PYTHONPATH="/app"

# Pre-download the default tokenizer during build
# CRITICAL: Must match INGESTOR_TOKENIZER in config (nvidia/llama-nemotron-embed-1b-v2)
# Note: nvidia/llama-nemotron-embed-1b-v2 is publicly available (not gated)
ARG HF_TOKEN=""
RUN if [ -n "$HF_TOKEN" ]; then \
        echo "🔑 Using provided HF_TOKEN for authentication"; \
        pip install --no-cache-dir huggingface_hub && \
        python -c "from huggingface_hub import login; login(token='$HF_TOKEN')"; \
    else \
        echo "ℹ️  No HF_TOKEN provided - downloading publicly available model"; \
    fi && \
    echo "📥 Pre-downloading tokenizer: nvidia/llama-nemotron-embed-1b-v2" && \
    python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('nvidia/llama-nemotron-embed-1b-v2')"

# Set offline mode AFTER download to prevent runtime network calls
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# Create non-root user for security
RUN useradd -m -u 1000 ingestoruser && \
    chown -R ingestoruser:ingestoruser /app
USER ingestoruser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Expose port
EXPOSE 8080

# Run ingestor
CMD ["python", "-m", "ingestor.main"]
