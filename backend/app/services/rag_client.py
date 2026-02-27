"""HTTP client for the RAG micro‑service (singleton)."""

import logging
from typing import Any

import httpx

from app.config import settings
from app.services.rag_cache import cache_get, cache_set

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
        params = {"query": query, "collection": collection, "top_k": top_k}
        cached = cache_get("retrieve", params)
        if cached is not None:
            return cached

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
        result = r.json()
        cache_set("retrieve", params, result)
        return result

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
        # Skip cache for contextual follow-up questions (contain chat history)
        use_cache = not chat_history
        if use_cache:
            params = {"question": question, "collection": collection, "top_k": top_k}
            cached = cache_get("query", params)
            if cached is not None:
                return cached

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
        result = r.json()

        if use_cache:
            cache_set("query", params, result)
        return result

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

    # ── OCR for handwritten answers ───────────────────────────────────────

    def ocr_handwritten(
        self,
        image_base64: str,
        *,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """Send a handwritten answer image to the RAG service for OCR."""
        payload: dict[str, Any] = {"image_base64": image_base64}
        if prompt:
            payload["prompt"] = prompt
        r = self._http.post("/ocr/handwritten", json=payload, timeout=90.0)
        r.raise_for_status()
        return r.json()

    # ── Web search ────────────────────────────────────────────────────────

    def web_search(
        self, query: str, *, max_results: int = 5
    ) -> dict[str, Any]:
        """Search the web via the RAG service's DuckDuckGo integration."""
        r = self._http.post(
            "/search/web",
            json={"query": query, "max_results": max_results},
        )
        r.raise_for_status()
        return r.json()

    def web_image_search(
        self, query: str, *, max_results: int = 5
    ) -> dict[str, Any]:
        """Search for images on the web via the RAG service."""
        r = self._http.post(
            "/search/web/images",
            json={"query": query, "max_results": max_results},
        )
        r.raise_for_status()
        return r.json()

    # ── Image serving ─────────────────────────────────────────────────────

    def get_collection_images(self, collection: str) -> dict[str, Any]:
        """List all extracted images in a collection."""
        r = self._http.get(f"/images/{collection}")
        r.raise_for_status()
        return r.json()

    def get_image_url(self, collection: str, filename: str) -> str:
        """Get the direct URL for an extracted image."""
        return f"{self._base}/images/{collection}/{filename}"

    # ── Seed ingestion ────────────────────────────────────────────────────

    def seed_ingest(
        self, folder: str | None = None, *, overwrite: bool = False
    ) -> dict[str, Any]:
        """Ingest curated documents from the raw/ seed folder."""
        payload: dict[str, Any] = {"overwrite": overwrite}
        if folder:
            payload["folder"] = folder
        r = self._http.post("/ingest/seed", json=payload, timeout=600.0)
        r.raise_for_status()
        return r.json()

    def list_seed_folders(self) -> dict[str, Any]:
        """List available seed folders and their PDF counts."""
        r = self._http.get("/ingest/seed/available")
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
