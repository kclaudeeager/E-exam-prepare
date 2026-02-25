"""Integration tests for RAG cache and rate limiter against live Redis."""

import time


def test_cache():
    from app.services.rag_cache import cache_get, cache_set, _make_key, _get_redis

    # Test 1: Round-trip write + read
    params = {"question": "What is photosynthesis?", "collection": "P6_Science", "top_k": 5}
    payload = {"answer": "Photosynthesis is...", "sources": [{"text": "chunk1"}]}
    cache_set("query", params, payload, ttl=30)
    hit = cache_get("query", params)
    assert hit is not None, "FAIL: cache miss after set"
    assert hit["answer"] == "Photosynthesis is...", "FAIL: wrong value"
    print("  ✅ Test 1: cache round-trip OK")

    # Test 2: Cache miss for different params
    miss = cache_get("query", {"question": "other", "collection": "P6_Science", "top_k": 5})
    assert miss is None, "FAIL: unexpected hit"
    print("  ✅ Test 2: cache miss for different params OK")

    # Test 3: TTL expiry
    cache_set("query", {"q": "expire_test"}, {"x": 1}, ttl=1)
    time.sleep(2)
    expired = cache_get("query", {"q": "expire_test"})
    assert expired is None, "FAIL: should have expired"
    print("  ✅ Test 3: TTL expiry OK")

    # Test 4: Key determinism
    k1 = _make_key("query", params)
    k2 = _make_key("query", params)
    assert k1 == k2, "FAIL: keys not deterministic"
    k3 = _make_key("retrieve", params)
    assert k1 != k3, "FAIL: different prefixes should produce different keys"
    print("  ✅ Test 4: key determinism OK")

    # Cleanup
    r = _get_redis()
    r.delete(_make_key("query", params))
    print("  ✅ All cache tests passed\n")


def test_rate_limiter():
    from app.services.rate_limiter import _check

    bucket = "rl:test:integration"

    # Test 1: First requests should be allowed (burst=5)
    allowed_count = 0
    for _ in range(5):
        if _check(bucket):
            allowed_count += 1
    assert allowed_count == 5, f"FAIL: expected 5 allowed, got {allowed_count}"
    print("  ✅ Test 1: burst of 5 allowed")

    # Test 2: 6th request should be rejected (bucket empty)
    assert not _check(bucket), "FAIL: 6th request should be rejected"
    print("  ✅ Test 2: 6th request rejected (bucket empty)")

    # Test 3: After waiting, tokens refill
    time.sleep(2.5)  # at 30 RPM = 0.5 tokens/sec, 2.5s => ~1 token
    assert _check(bucket), "FAIL: should have refilled at least 1 token"
    print("  ✅ Test 3: token refill after wait OK")

    # Cleanup
    from app.services.rate_limiter import _get_redis
    _get_redis().delete(bucket)
    print("  ✅ All rate limiter tests passed\n")


if __name__ == "__main__":
    print("\n=== RAG Cache Tests ===")
    test_cache()
    print("=== Rate Limiter Tests ===")
    test_rate_limiter()
    print("🎉 All integration tests passed!")
