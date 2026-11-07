"""F2-02 failure-policy counterexamples, using no live Redis or network."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Response

from app.middleware import rate_limit


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("_memory_limiter", "_redis_limiter", "_use_redis"):
        monkeypatch.setattr(rate_limit, name, None)
    for name, value in (("_redis_retry_at", 0.0), ("_redis_probe_in_progress", False),
                        ("_redis_failure_generation", 0)):
        monkeypatch.setattr(rate_limit, name, value, raising=False)


def settings(monkeypatch: pytest.MonkeyPatch, *, dev: bool = False) -> SimpleNamespace:
    config = SimpleNamespace(is_dev=dev, rate_limit_per_minute=2,
                             redis_url="redis://unused.invalid/0")
    monkeypatch.setattr(rate_limit, "get_settings", lambda: config)
    return config


def request() -> SimpleNamespace:
    return SimpleNamespace(url=SimpleNamespace(path="/limited"), headers={},
                           client=SimpleNamespace(host="192.0.2.2"))


def remote(monkeypatch: pytest.MonkeyPatch, *, probe_error: bool = False) -> SimpleNamespace:
    connection = SimpleNamespace(ping=AsyncMock(
        side_effect=ConnectionError("SYNTHETIC_PRIVATE_REDIS_ERROR") if probe_error else None,
    ))
    limiter = SimpleNamespace(_get_redis=AsyncMock(return_value=connection),
                              is_allowed=AsyncMock(return_value=(True, 1)))
    monkeypatch.setattr(rate_limit, "RedisRateLimiter", Mock(return_value=limiter))
    return limiter


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [True, False])
async def test_should_fail_closed_in_production_when_redis_fails(
    monkeypatch: pytest.MonkeyPatch, initial: bool,
) -> None:
    settings(monkeypatch)
    limiter = remote(monkeypatch, probe_error=initial)
    if not initial:
        monkeypatch.setattr(rate_limit, "_use_redis", True)
        monkeypatch.setattr(rate_limit, "_redis_limiter", limiter)
        limiter.is_allowed.side_effect = ConnectionError("SYNTHETIC_PRIVATE_REDIS_ERROR")
    handler = AsyncMock(return_value=Response("unsafe"))
    response = await rate_limit.rate_limit_middleware(request(), handler)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.headers["X-RateLimit-Backend"] == "unavailable"
    assert response.body == b'{"detail":"RATE_LIMIT_UNAVAILABLE"}'
    handler.assert_not_awaited()
    assert rate_limit._memory_limiter is None


@pytest.mark.asyncio
async def test_should_recover_after_cooldown_without_process_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings(monkeypatch)
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(rate_limit, "_retry_clock", clock)
    limiter = remote(monkeypatch, probe_error=True)
    handler = AsyncMock(return_value=Response("ok"))
    await rate_limit.rate_limit_middleware(request(), handler)
    connection = await limiter._get_redis()
    connection.ping.side_effect = None
    clock.return_value = 104.0
    response = await rate_limit.rate_limit_middleware(request(), handler)
    assert response.status_code == 503
    assert connection.ping.await_count == 1
    clock.return_value = 105.0
    response = await rate_limit.rate_limit_middleware(request(), handler)
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Backend"] == "redis"
    assert connection.ping.await_count == 2
    limiter.is_allowed.assert_awaited_once()
    handler.assert_awaited_once()
    rate_limit.RedisRateLimiter.assert_called_once()


@pytest.mark.asyncio
async def test_should_retain_development_windows_across_failed_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings(monkeypatch, dev=True)
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(rate_limit, "_retry_clock", clock)
    limiter = remote(monkeypatch, probe_error=True)
    handler = AsyncMock(return_value=Response("ok"))
    first = await rate_limit.rate_limit_middleware(request(), handler)
    memory = rate_limit._memory_limiter
    assert first.status_code == 200
    assert first.headers["X-RateLimit-Backend"] == "memory"
    clock.return_value = 105.0
    second = await rate_limit.rate_limit_middleware(request(), handler)
    assert second.status_code == 200
    clock.return_value = 110.0
    third = await rate_limit.rate_limit_middleware(request(), handler)
    assert third.status_code == 429
    assert third.headers["X-RateLimit-Backend"] == "memory"
    assert rate_limit._memory_limiter is memory
    handler.assert_awaited()
    assert handler.await_count == 2
    connection = await limiter._get_redis()
    assert connection.ping.await_count == 3
    connection.ping.side_effect = None
    clock.return_value = 115.0
    recovered = await rate_limit.rate_limit_middleware(request(), handler)
    assert recovered.status_code == 200
    assert recovered.headers["X-RateLimit-Backend"] == "redis"
    assert rate_limit._memory_limiter is memory


@pytest.mark.asyncio
@pytest.mark.parametrize("dev", [False, True])
async def test_should_run_one_probe_without_queueing_followers(
    monkeypatch: pytest.MonkeyPatch, dev: bool,
) -> None:
    import asyncio

    settings(monkeypatch, dev=dev)
    limiter = remote(monkeypatch)
    connection = await limiter._get_redis()
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_ping() -> None:
        entered.set()
        await release.wait()

    connection.ping.side_effect = blocked_ping
    handler = AsyncMock(return_value=Response("ok"))
    owner = asyncio.create_task(rate_limit.rate_limit_middleware(request(), handler))
    try:
        await entered.wait()
        followers = await asyncio.wait_for(asyncio.gather(*[
            rate_limit.rate_limit_middleware(request(), handler) for _ in range(8)
        ]), timeout=1)
        assert connection.ping.await_count == 1
        if dev:
            assert sorted(r.status_code for r in followers) == [200, 200] + [429] * 6
            assert all(r.headers["X-RateLimit-Backend"] == "memory" for r in followers)
        else:
            assert all(r.status_code == 503 for r in followers)
            handler.assert_not_awaited()
    finally:
        release.set()
        response = await owner
    assert response.status_code == 200
    assert rate_limit._redis_probe_in_progress is False


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["probe", "command"])
async def test_should_bound_slow_remote_operations(
    monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    import asyncio

    settings(monkeypatch)
    monkeypatch.setattr(rate_limit, "REDIS_OPERATION_TIMEOUT_SECONDS", 0.01)
    limiter = remote(monkeypatch)
    connection = await limiter._get_redis()
    target = connection.ping if phase == "probe" else limiter.is_allowed

    async def hang(*args: object, **kwargs: object) -> None:
        await asyncio.Event().wait()

    target.side_effect = hang
    handler = AsyncMock(return_value=Response("unsafe"))
    response = await asyncio.wait_for(rate_limit.rate_limit_middleware(request(), handler), 1)
    assert response.status_code == 503
    target.assert_awaited_once()
    handler.assert_not_awaited()
    assert rate_limit._use_redis is False
    assert rate_limit._redis_probe_in_progress is False


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["probe", "command"])
async def test_should_release_recovery_state_and_propagate_cancellation(
    monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    import asyncio

    settings(monkeypatch)
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(rate_limit, "_retry_clock", clock)
    limiter = remote(monkeypatch)
    connection = await limiter._get_redis()
    target = connection.ping if phase == "probe" else limiter.is_allowed
    entered = asyncio.Event()

    async def hang(*args: object, **kwargs: object) -> None:
        entered.set()
        await asyncio.Event().wait()

    target.side_effect = hang
    handler = AsyncMock(return_value=Response("ok"))
    operation = asyncio.create_task(rate_limit.rate_limit_middleware(request(), handler))
    await entered.wait()
    operation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await operation
    handler.assert_not_awaited()
    assert rate_limit._redis_probe_in_progress is False
    assert rate_limit._use_redis is False
    target.side_effect = None
    clock.return_value = 105.0
    assert (await rate_limit.rate_limit_middleware(request(), handler)).status_code == 200
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_not_let_old_probe_success_erase_newer_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    settings(monkeypatch)
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(rate_limit, "_retry_clock", clock)
    limiter = remote(monkeypatch)
    connection = await limiter._get_redis()
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_ping() -> None:
        entered.set()
        await release.wait()

    connection.ping.side_effect = blocked_ping
    handler = AsyncMock(return_value=Response("unsafe"))
    owner = asyncio.create_task(rate_limit.rate_limit_middleware(request(), handler))
    await entered.wait()
    # Model a previously in-flight quota command reporting failure during this probe.
    rate_limit._mark_redis_failure()
    release.set()
    response = await owner
    assert response.status_code == 503
    assert rate_limit._use_redis is False
    assert rate_limit._redis_retry_at == 105.0
    handler.assert_not_awaited()
    limiter.is_allowed.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_not_let_late_quota_success_clear_failure_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    settings(monkeypatch)
    limiter = remote(monkeypatch)
    await rate_limit._get_limiter()
    entered, release = asyncio.Event(), asyncio.Event()

    async def late_success(*args: object, **kwargs: object) -> tuple[bool, int]:
        entered.set()
        await release.wait()
        return True, 1

    limiter.is_allowed.side_effect = late_success
    handler = AsyncMock(return_value=Response("ok"))
    operation = asyncio.create_task(rate_limit.rate_limit_middleware(request(), handler))
    await entered.wait()
    rate_limit._mark_redis_failure()
    release.set()
    assert (await operation).status_code == 200  # This request has a successful shared count.
    assert rate_limit._use_redis is False
    assert (await rate_limit.rate_limit_middleware(request(), handler)).status_code == 503
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_keep_real_quota_exhaustion_distinct_from_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings(monkeypatch)
    limiter = remote(monkeypatch)
    limiter.is_allowed.return_value = False, 0
    handler = AsyncMock()
    response = await rate_limit.rate_limit_middleware(request(), handler)
    assert response.status_code == 429
    assert response.headers["X-RateLimit-Backend"] == "redis"
    assert rate_limit._use_redis is True
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_ignore_existing_memory_quota_in_non_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = settings(monkeypatch, dev=True)
    remote(monkeypatch, probe_error=True)
    handler = AsyncMock(return_value=Response("ok"))
    assert (await rate_limit.rate_limit_middleware(request(), handler)).status_code == 200
    memory = rate_limit._memory_limiter
    before = list(memory._windows["ip:192.0.2.2"])
    config.is_dev = False
    assert (await rate_limit.rate_limit_middleware(request(), handler)).status_code == 503
    assert memory._windows["ip:192.0.2.2"] == before
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_sanitize_probe_and_command_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    settings(monkeypatch)
    logger = Mock()
    monkeypatch.setattr(rate_limit, "logger", logger)
    adapter_class = rate_limit.RedisRateLimiter
    remote(monkeypatch, probe_error=True)
    response = await rate_limit.rate_limit_middleware(request(), AsyncMock())
    assert "SYNTHETIC_PRIVATE" not in response.body.decode()
    assert "SYNTHETIC_PRIVATE" not in str(logger.mock_calls)
    # Exercise the real adapter's command error, not just the policy double.
    adapter = adapter_class("redis://unused.invalid/0")
    adapter._redis = SimpleNamespace(pipeline=Mock(
        side_effect=ConnectionError("SYNTHETIC_PRIVATE_COMMAND_ERROR"),
    ))
    with pytest.raises(ConnectionError):
        await adapter.is_allowed("ip:synthetic", 2)
    assert "SYNTHETIC_PRIVATE" not in str(logger.mock_calls)


@pytest.mark.asyncio
async def test_should_configure_bounded_nonretrying_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import redis.asyncio
    from redis.asyncio.retry import Retry

    factory = Mock(return_value=object())
    monkeypatch.setattr(redis.asyncio, "from_url", factory)
    limiter = rate_limit.RedisRateLimiter("redis://unused.invalid/0")
    assert await limiter._get_redis() is await limiter._get_redis()
    factory.assert_called_once()
    kwargs = factory.call_args.kwargs
    assert kwargs["socket_timeout"] == kwargs["socket_connect_timeout"] == 2
    assert kwargs["retry_on_timeout"] is False
    assert isinstance(kwargs["retry"], Retry)
    assert kwargs["retry"].get_retries() == 0


@pytest.mark.asyncio
async def test_should_count_independent_clients_with_equal_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import fakeredis
    from fakeredis.aioredis import FakeRedis

    server = fakeredis.FakeServer()
    clients = [FakeRedis(server=server, decode_responses=True) for _ in range(2)]
    limiters = [rate_limit.RedisRateLimiter("redis://unused.invalid/0") for _ in clients]
    for limiter, client in zip(limiters, clients):
        limiter._redis = client
        monkeypatch.setattr(client, "pipeline", Mock(wraps=client.pipeline))
    monkeypatch.setattr(rate_limit.time, "time", lambda: 100.0)
    try:
        results = await asyncio.gather(*[
            limiters[i % 2].is_allowed("user:synthetic", 3) for i in range(10)
        ])
        assert sum(allowed for allowed, _ in results) == 3
        assert await clients[0].zcard("rate_limit:user:synthetic") == 10
        for client in clients:
            client.pipeline.assert_called_with(transaction=True)
        assert sorted(remaining for allowed, remaining in results if allowed) == [0, 1, 2]
    finally:
        for client in clients:
            await client.aclose()


@pytest.mark.asyncio
async def test_should_recover_after_ambiguous_command_without_replaying_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings(monkeypatch)
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(rate_limit, "_retry_clock", clock)
    limiter = remote(monkeypatch)
    limiter.is_allowed.side_effect = [
        (True, 1), ConnectionError("reply lost after possible commit"), (True, 0),
    ]
    handler = AsyncMock(return_value=Response("ok"))
    assert (await rate_limit.rate_limit_middleware(request(), handler)).status_code == 200
    assert (await rate_limit.rate_limit_middleware(request(), handler)).status_code == 503
    assert (await rate_limit.rate_limit_middleware(request(), handler)).status_code == 503
    assert limiter.is_allowed.await_count == 2
    clock.return_value = 105.0
    assert (await rate_limit.rate_limit_middleware(request(), handler)).status_code == 200
    assert limiter.is_allowed.await_count == 3
    assert handler.await_count == 2
    connection = await limiter._get_redis()
    assert connection.ping.await_count == 2
