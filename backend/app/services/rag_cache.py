"""Redis-backed cache for RAG query and retrieval results.

Avoids redundant LLM calls when the same question + collection + params
have already been answered. Uses content-addressable keys (SHA-256 hash
of the serialised request).
"""

import hashlib
import json
import logging
from typing import Any

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None


def _get_redis() -> redis.Redis:
    """Return a Redis client backed by a shared connection pool."""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=10,
        )
    return redis.Redis(connection_pool=_pool)


def _make_key(prefix: str, params: dict[str, Any]) -> str:
    """Create a deterministic cache key from prefix + sorted param hash."""
    serialised = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(serialised.encode()).hexdigest()[:16]
    return f"rag_cache:{prefix}:{digest}"


def cache_get(prefix: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Retrieve a cached RAG result (or None on miss/disabled)."""
    if not settings.RAG_CACHE_ENABLED:
        return None
    try:
        r = _get_redis()
        key = _make_key(prefix, params)
        raw = r.get(key)
        if raw:
            logger.debug("RAG cache HIT: %s", key)
            return json.loads(raw)
        logger.debug("RAG cache MISS: %s", key)
        return None
    except Exception as e:
        logger.warning("RAG cache read failed (non-fatal): %s", e)
        return None


def cache_set(
    prefix: str,
    params: dict[str, Any],
    result: dict[str, Any],
    ttl: int | None = None,
) -> None:
    """Store a RAG result in cache."""
    if not settings.RAG_CACHE_ENABLED:
        return
    try:
        r = _get_redis()
        key = _make_key(prefix, params)
        r.setex(key, ttl or settings.RAG_CACHE_TTL_SECONDS, json.dumps(result, default=str))
        logger.debug("RAG cache SET: %s (ttl=%ds)", key, ttl or settings.RAG_CACHE_TTL_SECONDS)
    except Exception as e:
        logger.warning("RAG cache write failed (non-fatal): %s", e)
