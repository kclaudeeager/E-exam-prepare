FROM python:3.12-slim

WORKDIR /app

# System deps for healthcheck + psycopg
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files first (layer caching)
COPY pyproject.toml ./

# Install Python dependencies
RUN uv sync --no-dev --no-install-project

# Copy alembic config & migrations
COPY alembic.ini ./
COPY alembic/ alembic/

# Copy application code
COPY app/ app/
COPY seed_db.py ./

# Create non-root user & own the workdir
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
