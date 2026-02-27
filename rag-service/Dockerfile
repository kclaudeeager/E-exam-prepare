FROM python:3.12-slim

WORKDIR /app

# System deps for healthcheck, PDF processing, and onnxruntime
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files first (layer caching)
COPY pyproject.toml ./

# Install Python dependencies
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY app/ app/

# Create non-root user & storage directory
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/storage \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Use start.sh as entrypoint to merge indexes before starting the service
COPY scripts/merge_driving_indexes.py scripts/merge_driving_indexes.py
COPY start.sh start.sh
ENTRYPOINT ["/bin/bash", "/app/start.sh"]
