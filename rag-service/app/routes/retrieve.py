"""Retrieval endpoint — ranked chunks + optional graph paths."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.rag.engine import get_rag_engine

logger = logging.getLogger(__name__)
router = APIRouter()


class RetrieveRequest(BaseModel):
    query: str
    collection: str
    top_k: int = 10
    filters: dict = {}


@router.post("/")
async def retrieve(body: RetrieveRequest):
    """Return top‑k ranked chunks (Vector + BM25 fusion)."""
    engine = get_rag_engine()
    try:
        return engine.retrieve(body.query, body.collection, top_k=body.top_k)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No index found for collection '{body.collection}'. "
                   "An admin must ingest documents into this collection first.",
        )
