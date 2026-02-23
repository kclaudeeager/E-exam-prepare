"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.api import (
    health_router,
    users_router,
    documents_router,
    quiz_router,
    attempts_router,
    progress_router,
    rag_router,
    chat_router,
    admin_router,
)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(name)-25s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 E-exam-prepare backend starting…")
    yield
    logger.info("✅ E-exam-prepare backend shut down")


app = FastAPI(
    title="E-exam-prepare API",
    description="Personalized exam preparation platform",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health_router, tags=["Health"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(documents_router, prefix="/api/documents", tags=["Documents"])
app.include_router(quiz_router, prefix="/api/quiz", tags=["Quiz"])
app.include_router(attempts_router, prefix="/api/attempts", tags=["Attempts"])
app.include_router(progress_router, prefix="/api/progress", tags=["Progress"])
app.include_router(rag_router, prefix="/api/rag", tags=["RAG"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])


@app.get("/")
async def root():
    return {
        "name": "E-exam-prepare API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
