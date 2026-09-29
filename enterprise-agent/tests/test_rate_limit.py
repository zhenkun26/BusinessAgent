"""Offline behavior checks for limiter selection, failover and HTTP responses."""

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Response

from app.middleware import rate_limit


@pytest.fixture(autouse=True)
def isolated_limiters(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings = SimpleNamespace(redis_url="redis://unused.invalid/0", rate_limit_per_minute=2)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    for name in ("_memory_limiter", "_redis_limiter", "_use_redis"):
        monkeypatch.setattr(rate_limit, name, None)
    yield


def request(path: str = "/limited") -> SimpleNamespace:
    return SimpleNamespace(url=SimpleNamespace(path=path), headers={},
                           client=SimpleNamespace(host="127.0.0.1"))


@pytest.mark.asyncio
async def test_should_probe_once_and_reuse_redis_when_connection_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = SimpleNamespace(ping=AsyncMock())
    limiter = SimpleNamespace(_get_redis=AsyncMock(return_value=connection),
                              is_allowed=AsyncMock(return_value=(True, 1)))
    factory = Mock(return_value=limiter)
    monkeypatch.setattr(rate_limit, "RedisRateLimiter", factory)
    next_handler = AsyncMock(return_value=Response("ok"))

    for _ in range(2):
        response = await rate_limit.rate_limit_middleware(request(), next_handler)
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "2"
        assert response.headers["X-RateLimit-Remaining"] == "1"

    factory.assert_called_once_with("redis://unused.invalid/0")
    connection.ping.assert_awaited_once()
    assert rate_limit._redis_limiter is limiter
    assert rate_limit._use_redis is True
    assert rate_limit._memory_limiter is None
    assert limiter.is_allowed.await_count == 2
    limiter.is_allowed.assert_awaited_with("ip:127.0.0.1", 2, window_seconds=60)


@pytest.mark.asyncio
async def test_should_reuse_memory_and_reject_excess_when_initial_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = SimpleNamespace(ping=AsyncMock(side_effect=ConnectionError("offline")))
    factory = Mock(return_value=SimpleNamespace(_get_redis=AsyncMock(return_value=connection)))
    monkeypatch.setattr(rate_limit, "RedisRateLimiter", factory)
    next_handler = AsyncMock(return_value=Response("ok"))

    first = await rate_limit.rate_limit_middleware(request(), next_handler)
    memory = rate_limit._memory_limiter
    # Characterize base 5446a70: appending mutates `recent`, then one is subtracted again.
    # Keep the existing off-by-one header behavior; fixing it is outside this refactor.
    assert first.headers["X-RateLimit-Remaining"] == "0"
    second = await rate_limit.rate_limit_middleware(request(), next_handler)
    assert second.headers["X-RateLimit-Remaining"] == "-1"
    rejected = await rate_limit.rate_limit_middleware(request(), next_handler)

    assert rate_limit._memory_limiter is memory
    assert rate_limit._use_redis is False
    factory.assert_called_once()
    connection.ping.assert_awaited_once()
    assert next_handler.await_count == 2
    assert rejected.status_code == 429
    assert rejected.headers["Retry-After"] == "60"
    assert rejected.body.decode() == (
        '{"detail":"请求过于频繁,请稍后再试","retry_after_seconds":60,"limit":2}'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_memory", [False, True])
async def test_should_preserve_memory_state_when_redis_fails_during_a_request(
    monkeypatch: pytest.MonkeyPatch, existing_memory: bool,
) -> None:
    remote = SimpleNamespace(is_allowed=AsyncMock(side_effect=ConnectionError("offline")))
    monkeypatch.setattr(rate_limit, "_redis_limiter", remote)
    monkeypatch.setattr(rate_limit, "_use_redis", True)
    memory = rate_limit.InMemoryRateLimiter() if existing_memory else None
    if memory is not None:
        await memory.is_allowed("ip:127.0.0.1", 2)
    monkeypatch.setattr(rate_limit, "_memory_limiter", memory)
    next_handler = AsyncMock(return_value=Response("ok"))

    response = await rate_limit.rate_limit_middleware(request(), next_handler)

    assert response.status_code == 200
    # Preserve the same pre-existing header behavior characterized above.
    assert response.headers["X-RateLimit-Remaining"] == ("-1" if existing_memory else "0")
    assert rate_limit._use_redis is False
    assert rate_limit._redis_limiter is remote
    if memory is not None:
        assert rate_limit._memory_limiter is memory
    else:
        assert isinstance(rate_limit._memory_limiter, rate_limit.InMemoryRateLimiter)
    remote.is_allowed.assert_awaited_once_with("ip:127.0.0.1", 2, window_seconds=60)


@pytest.mark.asyncio
@pytest.mark.parametrize("path,limit", [("/api/v1/auth/login", 10),
                                       ("/api/v1/chat/session", 30), ("/other", 2)])
async def test_should_preserve_route_limit_and_user_key_when_user_is_identified(
    monkeypatch: pytest.MonkeyPatch, path: str, limit: int,
) -> None:
    memory = SimpleNamespace(is_allowed=AsyncMock(return_value=(True, 1)))
    monkeypatch.setattr(rate_limit, "_memory_limiter", memory)
    monkeypatch.setattr(rate_limit, "_use_redis", False)
    monkeypatch.setattr(rate_limit, "_extract_user_id", lambda _: "user-42")

    response = await rate_limit.rate_limit_middleware(
        request(path), AsyncMock(return_value=Response("ok")),
    )

    memory.is_allowed.assert_awaited_once_with("user:user-42", limit, window_seconds=60)
    assert response.headers["X-RateLimit-Limit"] == str(limit)


@pytest.mark.asyncio
async def test_should_bypass_limiter_when_health_is_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = AsyncMock(side_effect=AssertionError("health must not initialize Redis"))
    monkeypatch.setattr(rate_limit, "_get_limiter", factory)
    expected = Response("ok")

    response = await rate_limit.rate_limit_middleware(
        request("/health"), AsyncMock(return_value=expected),
    )

    assert response is expected
    assert "X-RateLimit-Limit" not in response.headers
    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_propagate_factory_setup_error_without_runtime_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = RuntimeError("factory settings unavailable")
    settings = SimpleNamespace(rate_limit_per_minute=2)
    monkeypatch.setattr(rate_limit, "get_settings", Mock(side_effect=[settings, error]))
    next_handler = AsyncMock()

    with pytest.raises(RuntimeError) as caught:
        await rate_limit.rate_limit_middleware(request(), next_handler)

    assert caught.value is error
    assert rate_limit._memory_limiter is None
    assert rate_limit._use_redis is None
    next_handler.assert_not_awaited()
