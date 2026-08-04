"""Redis 简单任务队列(外部系统接入,规格 5.6)

语义:
- 任务以 JSON 消息写入 Redis List(LPUSH),worker 用 BLPOP 消费
- 失败消息携带 retry_count 与 next_retry_at,按指数退避回写延迟队列
  (next_retry_at 未到时 worker 重新入队并等待,避免忙等)
- 不引入 Celery:复用现有 Redis,零新增基础设施
"""

from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable, Optional

from loguru import logger


async def enqueue_task(
    redis_url: str,
    queue_name: str,
    payload: dict,
    *,
    retry_count: int = 0,
    next_retry_at: float = 0.0,
) -> None:
    """入队任务(消息体含重试元数据)"""
    import redis.asyncio as aioredis

    message = {
        "payload": payload,
        "retry_count": retry_count,
        "next_retry_at": next_retry_at,
    }
    redis = aioredis.from_url(redis_url, decode_responses=True, socket_timeout=3)
    try:
        await redis.lpush(queue_name, json.dumps(message, ensure_ascii=False))
    finally:
        await redis.aclose()


async def consume_tasks(
    redis_url: str,
    queue_name: str,
    handler: Callable[[dict], Awaitable[None]],
    *,
    max_retries: int = 3,
    backoff_base_seconds: float = 5.0,
    idle_sleep_seconds: float = 1.0,
) -> None:
    """消费任务队列(阻塞循环,由 worker 主循环驱动)

    Args:
        redis_url: Redis 连接串
        queue_name: 队列名
        handler: 任务处理协程(入参为 payload dict;抛异常视为失败)
        max_retries: 最大重试次数(不含首次)
        backoff_base_seconds: 指数退避基数(2^retry * base)
        idle_sleep_seconds: 队列空时的休眠秒数
    """
    import redis.asyncio as aioredis

    redis = aioredis.from_url(redis_url, decode_responses=True, socket_timeout=3)
    try:
        while True:
            raw = await redis.brpop(queue_name, timeout=idle_sleep_seconds)
            if raw is None:
                continue
            try:
                message = json.loads(raw[1])
            except json.JSONDecodeError:
                logger.error(f"任务队列消息损坏,丢弃: {queue_name}: {raw[1][:200]}")
                continue

            payload = message.get("payload", {})
            retry_count = int(message.get("retry_count", 0))
            next_retry_at = float(message.get("next_retry_at", 0.0))

            if next_retry_at > time.time():
                # 延迟任务未到期:放回队尾等待(短暂休眠避免忙等)
                await redis.lpush(queue_name, json.dumps(message, ensure_ascii=False))
                await asyncio_sleep(min(next_retry_at - time.time(), idle_sleep_seconds))
                continue

            try:
                await handler(payload)
                logger.debug(f"任务完成: {queue_name} {str(payload)[:100]}")
            except Exception as e:  # noqa: BLE001 任务失败按重试策略处理
                logger.warning(
                    f"任务失败: {queue_name} retry={retry_count}/{max_retries}: {e}"
                )
                if retry_count < max_retries:
                    new_retry_count = retry_count + 1
                    delay = backoff_base_seconds * (2 ** retry_count)
                    await redis.lpush(
                        queue_name,
                        json.dumps(
                            {
                                "payload": payload,
                                "retry_count": new_retry_count,
                                "next_retry_at": time.time() + delay,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    logger.info(
                        f"任务已按退避重排: {queue_name} retry={new_retry_count}, "
                        f"{delay:.0f}s 后重试"
                    )
                else:
                    logger.error(f"任务重试耗尽,丢弃: {queue_name} {str(payload)[:200]}")
    finally:
        await redis.aclose()


async def asyncio_sleep(seconds: float) -> None:
    """包装 asyncio.sleep(最小 0.05s,防止 0 休眠忙等)"""
    import asyncio

    await asyncio.sleep(max(seconds, 0.05))
