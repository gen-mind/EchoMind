# multi-stage build for producing a small and secure image

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
COPY api/requirements.txt .

# Install Python dependencies in a separate location
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===============================================
# Stage 2: Runtime - Minimal final image
# ===============================================
FROM python:3.12.12-slim-bookworm

WORKDIR /app

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY api /app/api
COPY echomind_lib /app/echomind_lib

# Set Python path
ENV PYTHONPATH="/app"

# Create non-root user for security
RUN useradd -m -u 1000 apiuser && \
    chown -R apiuser:apiuser /app
USER apiuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
