"""HTTP client for the RAG micro‑service (singleton)."""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class RAGClient:
    """Thin wrapper around the RAG service HTTP API."""

    def __init__(self, base_url: str = settings.RAG_SERVICE_URL) -> None:
        self._base = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self._base, timeout=60.0)

    # ── health ────────────────────────────────────────────────────────────

    def healthy(self) -> bool:
        try:
            return self._http.get("/health").status_code == 200
        except httpx.HTTPError:
            return False

    # ── ingest ────────────────────────────────────────────────────────────

    def ingest(
        self, source_path: str, collection: str, *, overwrite: bool = False
    ) -> dict[str, Any]:
        r = self._http.post(
            "/ingest/",
            json={
                "source_path": source_path,
                "collection": collection,
                "overwrite": overwrite,
            },
        )
        r.raise_for_status()
        return r.json()

    # ── retrieve (ranked chunks + optional graph paths) ───────────────────

    def retrieve(
        self,
        query: str,
        collection: str,
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        r = self._http.post(
            "/retrieve/",
            json={
                "query": query,
                "collection": collection,
                "top_k": top_k,
                "filters": filters or {},
            },
        )
        r.raise_for_status()
        return r.json()

    # ── query (full RAG with LLM synthesis) ───────────────────────────────

    def query(
        self,
        question: str,
        collection: str,
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        chat_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "question": question,
            "collection": collection,
            "top_k": top_k,
            "filters": filters or {},
        }
        if chat_history:
            payload["chat_history"] = chat_history
        r = self._http.post("/query/", json=payload)
        r.raise_for_status()
        return r.json()

    # ── direct LLM (no index required) ─────────────────────────────────────

    def query_direct(
        self,
        question: str,
        *,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Call the LLM directly without needing a collection/index."""
        payload: dict[str, Any] = {"question": question}
        if system_prompt:
            payload["system_prompt"] = system_prompt
        r = self._http.post("/query/direct", json=payload)
        r.raise_for_status()
        return r.json()

    # ── graph exploration ─────────────────────────────────────────────────

    def explore_graph(
        self, entity: str, collection: str, *, depth: int = 2
    ) -> dict[str, Any]:
        r = self._http.post(
            "/explore/",
            json={"entity": entity, "collection": collection, "depth": depth},
        )
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()


# ── singleton accessor ────────────────────────────────────────────────────────

_instance: RAGClient | None = None


def get_rag_client() -> RAGClient:
    global _instance
    if _instance is None:
        _instance = RAGClient()
        logger.info("RAG client initialised → %s", _instance._base)
    return _instance
