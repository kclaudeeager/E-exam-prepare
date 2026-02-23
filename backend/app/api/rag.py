"""RAG proxy endpoints — forwards requests from frontend → RAG micro-service.

Exposes two routes:
  POST /api/rag/query    → full LLM answer + sources (for "Ask AI" / show solution)
  POST /api/rag/retrieve → ranked chunks only (for document search preview)
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.models import User
from app.services.rag_client import get_rag_client

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessageIn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class RAGQueryRequest(BaseModel):
    question: str
    collection: str = "General"
    top_k: int = 5
    chat_history: list[ChatMessageIn] | None = None


class RAGRetrieveRequest(BaseModel):
    query: str
    collection: str = "General"
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
def rag_query(
    body: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
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
def rag_retrieve(
    body: RAGRetrieveRequest,
    current_user: User = Depends(get_current_user),
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
