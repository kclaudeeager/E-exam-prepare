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
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

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
    # In non-production, run tasks synchronously in-process (no Redis needed).
    # Set CELERY_TASK_ALWAYS_EAGER=false in .env to use a real broker.
    CELERY_TASK_ALWAYS_EAGER: bool = True

    # ── Adaptive‑learning knobs ─────────────────────────────────────────
    WEAK_TOPIC_THRESHOLD: float = 0.60

    model_config = {"env_file": str(_ENV_FILE), "case_sensitive": True, "extra": "ignore"}


settings = Settings()
