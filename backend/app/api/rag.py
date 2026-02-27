"""RAG proxy endpoints — forwards requests from frontend → RAG micro-service.

Exposes two routes:
  POST /api/rag/query    → full LLM answer + sources (for "Ask AI" / show solution)
  POST /api/rag/retrieve → ranked chunks only (for document search preview)
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin
from app.db.models import User
from app.services.rag_client import get_rag_client
from app.services.rate_limiter import require_rag_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessageIn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class RAGQueryRequest(BaseModel):
    question: str
    collection: str  # Must be provided; no default
    top_k: int = 5
    chat_history: list[ChatMessageIn] | None = None


class RAGRetrieveRequest(BaseModel):
    query: str
    collection: str  # Must be provided; no default
    top_k: int = 5


def _proxy_error(exc: Exception, operation: str) -> HTTPException:
    """Convert RAG-service HTTP errors to appropriate FastAPI responses."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        return HTTPException(status_code=code, detail=detail)
    logger.error("RAG %s failed: %s", operation, exc)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="RAG service unavailable. Please try again later.",
    )


@router.post("/query")
async def rag_query(
    body: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
    _rl=Depends(require_rag_rate_limit),
):
    """Ask the RAG engine a question and get an LLM-synthesised answer with sources."""
    try:
        history = (
            [msg.model_dump() for msg in body.chat_history]
            if body.chat_history
            else None
        )
        return get_rag_client().query(
            question=body.question,
            collection=body.collection,
            top_k=body.top_k,
            chat_history=history,
        )
    except Exception as exc:
        raise _proxy_error(exc, "query")


@router.post("/retrieve")
async def rag_retrieve(
    body: RAGRetrieveRequest,
    current_user: User = Depends(get_current_user),
    _rl=Depends(require_rag_rate_limit),
):
    """Retrieve top-k ranked chunks for a query (no LLM synthesis)."""
    try:
        return get_rag_client().retrieve(
            query=body.query,
            collection=body.collection,
            top_k=body.top_k,
        )
    except Exception as exc:
        raise _proxy_error(exc, "retrieve")


# ── Web Search ────────────────────────────────────────────────────────────────


class WebSearchRequest(BaseModel):
    query: str
    max_results: int = 5


class WebImageSearchRequest(BaseModel):
    query: str
    max_results: int = 5


@router.post("/search/web")
async def web_search(
    body: WebSearchRequest,
    current_user: User = Depends(get_current_user),
    _rl=Depends(require_rag_rate_limit),
):
    """Search the web for supplementary information (DuckDuckGo, free)."""
    try:
        return get_rag_client().web_search(
            body.query, max_results=body.max_results
        )
    except Exception as exc:
        raise _proxy_error(exc, "web_search")


@router.post("/search/web/images")
async def web_image_search(
    body: WebImageSearchRequest,
    current_user: User = Depends(get_current_user),
    _rl=Depends(require_rag_rate_limit),
):
    """Search for images on the web (DuckDuckGo, free)."""
    try:
        return get_rag_client().web_image_search(
            body.query, max_results=body.max_results
        )
    except Exception as exc:
        raise _proxy_error(exc, "web_image_search")


# ── Image Proxy ───────────────────────────────────────────────────────────────


@router.get("/images/{collection}")
async def list_collection_images(
    collection: str,
    current_user: User = Depends(get_current_user),
):
    """List all extracted images in a collection."""
    try:
        return get_rag_client().get_collection_images(collection)
    except Exception as exc:
        raise _proxy_error(exc, "list_images")


# ── Seed Ingestion ────────────────────────────────────────────────────────────


class SeedIngestRequest(BaseModel):
    folder: str | None = None  # e.g. "driving"; None = all available
    overwrite: bool = False


@router.post("/seed/ingest")
async def seed_ingest(
    body: SeedIngestRequest,
    _admin: User = Depends(require_admin),
):
    """Ingest curated documents from the RAG storage/raw/ folder (admin only)."""
    try:
        return get_rag_client().seed_ingest(body.folder, overwrite=body.overwrite)
    except Exception as exc:
        raise _proxy_error(exc, "seed_ingest")


@router.get("/seed/available")
async def list_seed_folders(
    _admin: User = Depends(require_admin),
):
    """List available seed folders and their PDFs (admin only)."""
    try:
        return get_rag_client().list_seed_folders()
    except Exception as exc:
        raise _proxy_error(exc, "list_seed_folders")
