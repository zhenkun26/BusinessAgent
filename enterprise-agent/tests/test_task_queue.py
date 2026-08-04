"""Redis 任务队列测试(规格 5.6:fakeredis 离线验证)"""

from __future__ import annotations

import asyncio

import pytest

from app.core.task_queue import consume_tasks, enqueue_task


@pytest.fixture
def fake_redis_server():
    """返回 fakeredis 服务实例,并全局注入 redis.asyncio.from_url"""
    import redis.asyncio as aioredis
    from fakeredis import FakeServer
    from fakeredis import aioredis as fake_aioredis

    server = FakeServer()
    original_from_url = aioredis.from_url

    def fake_from_url(url, **kwargs):
        return fake_aioredis.FakeRedis(server=server, **kwargs)

    aioredis.from_url = fake_from_url
    yield server
    aioredis.from_url = original_from_url


@pytest.mark.asyncio
async def test_should_consume_task_successfully_when_handler_ok(fake_redis_server):
    """Given 队列有任务且 handler 成功, When 消费,
    Then 任务被处理且不重试"""
    await enqueue_task("redis://x", "t:test", {"job": 1})
    handled: list[dict] = []

    async def handler(payload):
        handled.append(payload)

    consumer = asyncio.create_task(
        consume_tasks(
            "redis://x",
            "t:test",
            handler,
            max_retries=3,
            idle_sleep_seconds=0.1,
        )
    )
    await asyncio.sleep(0.3)
    consumer.cancel()
    await asyncio.gather(consumer, return_exceptions=True)

    assert handled == [{"job": 1}]


@pytest.mark.asyncio
async def test_should_retry_with_backoff_then_exhaust_when_handler_fails(
    fake_redis_server,
):
    """Given handler 持续失败, When 消费,
    Then 按重试计数退避,耗尽后丢弃(不无限重试)"""
    await enqueue_task("redis://x", "t:fail", {"job": "boom"})
    attempts: list[int] = []

    async def handler(payload):
        attempts.append(payload["job"])
        raise RuntimeError("boom")

    consumer = asyncio.create_task(
        consume_tasks(
            "redis://x",
            "t:fail",
            handler,
            max_retries=2,
            backoff_base_seconds=0.05,
            idle_sleep_seconds=0.05,
        )
    )
    await asyncio.sleep(1.0)
    consumer.cancel()
    await asyncio.gather(consumer, return_exceptions=True)

    # 首次 + 2 次重试 = 3 次尝试;之后重试耗尽丢弃
    assert len(attempts) == 3
