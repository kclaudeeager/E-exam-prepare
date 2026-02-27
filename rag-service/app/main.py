"""RAG service FastAPI entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import ingest, retrieve, query, explore, ocr, images, search

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(name)-25s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 RAG Service starting…")
    yield
    logger.info("✅ RAG Service shut down")


app = FastAPI(
    title="E-exam-prepare RAG Service",
    description="LlamaIndex‑based RAG for document ingestion and question retrieval",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(ingest.router, prefix="/ingest", tags=["Ingestion"])
app.include_router(retrieve.router, prefix="/retrieve", tags=["Retrieval"])
app.include_router(query.router, prefix="/query", tags=["RAG Query"])
app.include_router(explore.router, prefix="/explore", tags=["Graph Explore"])
app.include_router(ocr.router, prefix="/ocr", tags=["OCR"])
app.include_router(images.router, prefix="/images", tags=["Images"])
app.include_router(search.router, prefix="/search", tags=["Web Search"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "rag-service"}


@app.get("/")
async def root():
    return {
        "name": "E-exam-prepare RAG Service",
        "version": "0.1.0",
        "docs": "/docs",
    }
