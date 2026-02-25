"""Redis-backed leaky-bucket rate limiter for RAG / LLM endpoints.

Algorithm
---------
Each bucket is a Redis key that stores the number of *tokens* (remaining
requests) and the timestamp of the last refill.  Tokens leak (refill) at a
constant rate of ``RPM / 60`` tokens per second up to a maximum of
``BURST``.  A request is allowed only when at least one token is available;
otherwise a 429 response is returned.

Usage as a FastAPI dependency
-----------------------------
```python
from app.services.rate_limiter import require_rag_rate_limit

@router.post("/query")
async def query(..., _rl=Depends(require_rag_rate_limit)):
    ...
```
"""

import logging
import time

import redis
from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None

# Lua script executed atomically inside Redis.
# KEYS[1] = bucket key
# ARGV[1] = max tokens (burst)
# ARGV[2] = refill rate (tokens per second)
# ARGV[3] = current timestamp (float seconds)
# Returns  1 if request allowed, 0 if rejected.
_LUA_SCRIPT = """
local key        = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now        = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens      = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    -- first request: initialise full bucket
    tokens = max_tokens
    last_refill = now
end

-- refill tokens since last check
local elapsed = math.max(0, now - last_refill)
tokens = math.min(max_tokens, tokens + elapsed * refill_rate)

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, 120)  -- auto-cleanup idle buckets
return allowed
"""


def _get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=10,
        )
    return redis.Redis(connection_pool=_pool)


def _client_key(request: Request) -> str:
    """Derive a per-user bucket key from the JWT subject or the IP."""
    # If auth middleware already decoded the token, ``request.state.user``
    # will carry the user id.  Otherwise fall back to the client IP.
    user_id = getattr(getattr(request, "state", None), "user_id", None)
    if user_id:
        return f"rl:rag:u:{user_id}"
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"rl:rag:ip:{ip}"


def _check(bucket_key: str) -> bool:
    """Return True if the request should be allowed."""
    rpm = settings.RATE_LIMIT_RAG_RPM
    burst = settings.RATE_LIMIT_RAG_BURST
    if rpm <= 0:
        return True  # rate limiting disabled

    refill_rate = rpm / 60.0  # tokens per second
    try:
        r = _get_redis()
        allowed = r.eval(_LUA_SCRIPT, 1, bucket_key, burst, refill_rate, time.time())
        return bool(allowed)
    except Exception as e:
        logger.warning("Rate-limiter Redis error (allowing request): %s", e)
        return True  # fail-open: don't block users if Redis is down


async def require_rag_rate_limit(request: Request) -> None:
    """FastAPI dependency — raises 429 if the caller exceeds the limit."""
    key = _client_key(request)
    if not _check(key):
        logger.info("Rate-limited: %s", key)
        raise HTTPException(
            status_code=429,
            detail="Too many requests — please slow down.",
        )
