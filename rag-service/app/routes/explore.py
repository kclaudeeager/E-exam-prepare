"""PropertyGraph exploration endpoint (debugging / admin)."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.rag.engine import get_rag_engine

logger = logging.getLogger(__name__)
router = APIRouter()


class ExploreRequest(BaseModel):
    entity: str
    collection: str
    depth: int = 2


@router.post("/")
async def explore_graph(body: ExploreRequest):
    """Traverse PropertyGraph relationships for an entity."""
    engine = get_rag_engine()
    try:
        return engine.explore_graph(body.entity, body.collection, depth=body.depth)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No index found for collection '{body.collection}'.",
        )
