"""Document ingestion endpoint."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.rag.engine import get_rag_engine

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestRequest(BaseModel):
    source_path: str
    collection: str
    overwrite: bool = False


@router.post("/")
async def ingest_documents(body: IngestRequest):
    """Ingest PDFs from *source_path* into the given collection index."""
    src = Path(body.source_path)
    if not src.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path not found: {body.source_path}",
        )

    engine = get_rag_engine()
    result = engine.ingest(str(src), body.collection, overwrite=body.overwrite)
    return result
