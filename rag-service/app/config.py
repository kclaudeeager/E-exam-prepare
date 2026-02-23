"""RAG service configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings

# Always resolve .env relative to this file, no matter where uvicorn is started from
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """RAG service settings — all from env / .env file."""

    # ── Server ──────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = False

    # ── LLM / Embedding provider ────────────────────────────────────────
    # Supported providers: openai, gemini, groq
    # Use "groq" for free development (RECOMMENDED during dev)
    # Use "gemini" for Google's models with custom embedding
    # Use "openai" for OpenAI's models
    LLAMA_INDEX_PROVIDER: str = "groq"
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""  # Free during development
    GROQ_MODEL: str = "llama-3.3-70b-versatile"  # https://console.groq.com/docs/models
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"  # Vision-capable model for OCR

    # ── Chunking ────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 100

    # ── Retrieval ───────────────────────────────────────────────────────
    SIMILARITY_TOP_K: int = 10

    # ── PropertyGraph (optional) ────────────────────────────────────────
    KG_RAG_ENABLED: bool = False
    KG_EXTRACTOR_TYPE: str = "simple"  # simple | dynamic | schema
    KG_GRAPH_STORE: str = "simple"  # simple | neo4j

    # ── Storage ─────────────────────────────────────────────────────────
    # Absolute default so it doesn't depend on CWD at startup
    STORAGE_DIR: str = str(Path(__file__).resolve().parent.parent / "storage")

    # ── LlamaParse (optional) ───────────────────────────────────────────
    LLAMA_CLOUD_API_KEY: str = ""

    model_config = {"env_file": str(_ENV_FILE), "case_sensitive": True, "extra": "ignore"}


settings = Settings()
