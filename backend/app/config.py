"""Backend configuration loaded from environment variables."""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings

# Always resolve .env relative to this file, no matter where uvicorn is started from
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings — all values sourced from env / .env file."""

    # ── Server ──────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    ENV: str = "development"

    # ── CORS ────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+psycopg://exam_prep:exam_prep_dev@localhost:5432/exam_prep"
    DATABASE_ECHO: bool = False

    # ── JWT / Auth ──────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── RAG Service ─────────────────────────────────────────────────────
    RAG_SERVICE_URL: str = "http://localhost:8001"
    GROQ_API_KEY: str = ""  # Optional, for RAG service

    # ── Celery / Redis ──────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    REDIS_URL: str = ""  # defaults to CELERY_BROKER_URL at runtime
    # In non-production, run tasks synchronously in-process (no Redis needed).
    # Set CELERY_TASK_ALWAYS_EAGER=false in .env to use a real broker.
    CELERY_TASK_ALWAYS_EAGER: bool = True

    @property
    def redis_url(self) -> str:
        """Return REDIS_URL, falling back to CELERY_BROKER_URL."""
        return self.REDIS_URL or self.CELERY_BROKER_URL

    # ── RAG Cache ───────────────────────────────────────────────────────
    RAG_CACHE_TTL_SECONDS: int = 3600  # 1 hour default
    RAG_CACHE_ENABLED: bool = True

    # ── Rate Limiting (leaky bucket) ────────────────────────────────────
    RATE_LIMIT_RAG_RPM: int = 30       # max requests per minute to RAG/LLM
    RATE_LIMIT_RAG_BURST: int = 5      # burst allowance

    # ── Adaptive‑learning knobs ─────────────────────────────────────────
    WEAK_TOPIC_THRESHOLD: float = 0.60

    model_config = {"env_file": str(_ENV_FILE), "case_sensitive": True, "extra": "ignore"}


settings = Settings()
