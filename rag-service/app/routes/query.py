"""Full RAG query endpoint — retrieval + LLM synthesis."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.rag.engine import get_rag_engine

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class QueryRequest(BaseModel):
    question: str
    collection: str
    top_k: int = 10
    filters: dict = {}
    chat_history: list[ChatMessage] | None = None


class DirectQueryRequest(BaseModel):
    """Query the LLM directly without needing a vector index."""
    question: str
    system_prompt: str | None = None


@router.post("/")
async def rag_query(body: QueryRequest):
    """Retrieve context and synthesise an LLM answer.

    When chat_history is provided, the engine will:
    1. Condense the follow-up question into a standalone query
    2. Use the condensed query for retrieval
    3. Include conversation context in the synthesis prompt
    """
    engine = get_rag_engine()
    # Convert Pydantic models to dicts for the engine
    history = (
        [msg.model_dump() for msg in body.chat_history]
        if body.chat_history
        else None
    )
    try:
        return engine.query(
            body.question,
            body.collection,
            top_k=body.top_k,
            chat_history=history,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No index found for collection '{body.collection}'. "
                   "An admin must ingest documents into this collection first.",
        )


@router.post("/direct")
async def direct_llm_query(body: DirectQueryRequest):
    """Call the LLM directly without retrieval — no collection/index needed.

    Used for generating explanations, reviews, and tutoring when no
    document index is available. The LLM uses its training knowledge.
    """
    engine = get_rag_engine()
    engine._ensure_configured()
    from llama_index.core import Settings as LISettings

    system = body.system_prompt or (
        "You are an expert, friendly exam tutor. "
        "Provide clear, thorough, educational explanations. "
        "Use examples and analogies. Be encouraging."
    )

    full_prompt = f"{system}\n\n{body.question}"

    try:
        response = LISettings.llm.complete(full_prompt)
        return {
            "success": True,
            "answer": str(response).strip(),
            "sources": [],
            "graph_enhanced": False,
        }
    except Exception as e:
        logger.error("Direct LLM query failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM query failed: {str(e)}",
        )
