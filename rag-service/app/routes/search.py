"""Web search routes — search the web for supplementary information.

Routes:
  POST /search/web         → text search using DuckDuckGo
  POST /search/web/images  → image search using DuckDuckGo
"""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.rag.web_search import get_web_searcher

logger = logging.getLogger(__name__)
router = APIRouter()


class WebSearchRequest(BaseModel):
    query: str
    max_results: int = 5


class WebImageSearchRequest(BaseModel):
    query: str
    max_results: int = 5


@router.post("/web")
async def web_search(body: WebSearchRequest):
    """Search the web using DuckDuckGo (free, no API key needed).

    Returns a list of web results with title, body/snippet, and URL.
    """
    searcher = get_web_searcher()
    results = searcher.search(body.query, max_results=body.max_results)

    if not results:
        return {
            "success": True,
            "results": [],
            "total": 0,
            "message": "No web results found. DuckDuckGo search may be unavailable.",
        }

    return {
        "success": True,
        "results": results,
        "total": len(results),
    }


@router.post("/web/images")
async def web_image_search(body: WebImageSearchRequest):
    """Search for images on the web using DuckDuckGo.

    Returns image URLs, thumbnails, and source information.
    """
    searcher = get_web_searcher()
    results = searcher.search_images(body.query, max_results=body.max_results)

    return {
        "success": True,
        "results": results,
        "total": len(results),
    }
