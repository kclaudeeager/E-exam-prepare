"""Web search integration for the RAG pipeline.

Uses DuckDuckGo search (free, no API key) to fetch supplementary information
when the local document index doesn't have sufficient context.

Usage::

    searcher = WebSearcher()
    results = searcher.search("road signs in Rwanda", max_results=5)
    context = searcher.search_and_format("what does a stop sign look like")
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class WebSearcher:
    """Web search using DuckDuckGo (free, no API key required)."""

    def __init__(self) -> None:
        self._available: bool | None = None

    def _check_available(self) -> bool:
        """Check if duckduckgo-search is installed."""
        if self._available is not None:
            return self._available
        try:
            from duckduckgo_search import DDGS  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning(
                "duckduckgo-search not installed — web search disabled. "
                "Install with: pip install duckduckgo-search"
            )
            self._available = False
        return self._available

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        region: str = "wt-wt",
        time_range: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search the web using DuckDuckGo.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            region: DuckDuckGo region code (wt-wt = no region)
            time_range: Time filter (d=day, w=week, m=month, y=year)

        Returns:
            List of dicts with keys: title, href, body
        """
        if not self._check_available():
            return []

        from duckduckgo_search import DDGS

        try:
            t0 = time.time()
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results,
                    region=region,
                    timelimit=time_range,
                ))
            elapsed = round(time.time() - t0, 2)
            logger.info(
                "Web search for '%s': %d results in %.2fs",
                query[:80], len(results), elapsed,
            )
            return results

        except Exception as e:
            logger.warning("Web search failed for '%s': %s", query[:80], e)
            return []

    def search_images(
        self,
        query: str,
        *,
        max_results: int = 5,
        region: str = "wt-wt",
    ) -> list[dict[str, Any]]:
        """Search for images using DuckDuckGo.

        Returns:
            List of dicts with keys: title, image, thumbnail, url, source
        """
        if not self._check_available():
            return []

        from duckduckgo_search import DDGS

        try:
            with DDGS() as ddgs:
                results = list(ddgs.images(
                    query,
                    max_results=max_results,
                    region=region,
                ))
            logger.info("Web image search for '%s': %d results", query[:80], len(results))
            return results

        except Exception as e:
            logger.warning("Web image search failed for '%s': %s", query[:80], e)
            return []

    def search_and_format(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> str:
        """Search and format results as a text block for LLM context.

        Returns a formatted string suitable for inclusion in an LLM prompt.
        """
        results = self.search(query, max_results=max_results)
        if not results:
            return ""

        parts = [f"[Web Search Results for: '{query}']\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            parts.append(f"{i}. **{title}**\n   {body}\n   Source: {href}\n")

        return "\n".join(parts)


# ── Singleton ─────────────────────────────────────────────────────────────────

_searcher: WebSearcher | None = None


def get_web_searcher() -> WebSearcher:
    global _searcher
    if _searcher is None:
        _searcher = WebSearcher()
    return _searcher
