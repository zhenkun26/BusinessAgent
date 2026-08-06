"""I-06:checkpoint Redis 滑动过期(TTL)配置测试

验证 _try_init_redis 将配置项 checkpoint_ttl_days 转换为
AsyncRedisSaver 的滑动 TTL 参数(default_ttl 分钟 + refresh_on_read)。
"""

from __future__ import annotations

import langgraph.checkpoint.redis as redis_ckpt
import pytest

from app.config import get_settings
from app.graph.checkpointer import _try_init_redis


class _FakeRedisSaver:
    """记录构造参数的 AsyncRedisSaver 替身"""

    def __init__(self, redis_url: str | None = None, ttl: dict | None = None, **kwargs):
        self.redis_url = redis_url
        self.ttl = ttl

    async def asetup(self) -> None:
        return None


@pytest.mark.asyncio
async def test_should_pass_sliding_ttl_to_redis_saver_when_ttl_days_positive(monkeypatch):
    """Given checkpoint_ttl_days=7, When 初始化 Redis saver,
    Then 构造参数带滑动 TTL(default_ttl=10080 分钟, refresh_on_read=True)"""
    monkeypatch.setattr(get_settings(), "checkpoint_ttl_days", 7)
    monkeypatch.setattr(redis_ckpt, "AsyncRedisSaver", _FakeRedisSaver)

    saver = await _try_init_redis("redis://localhost:6379/0")

    assert saver is not None
    assert saver.ttl == {"default_ttl": 7 * 24 * 60, "refresh_on_read": True}


@pytest.mark.asyncio
async def test_should_disable_ttl_when_ttl_days_not_positive(monkeypatch):
    """Given checkpoint_ttl_days=0, When 初始化 Redis saver,
    Then 不传 TTL 配置(恢复旧行为)"""
    monkeypatch.setattr(get_settings(), "checkpoint_ttl_days", 0)
    monkeypatch.setattr(redis_ckpt, "AsyncRedisSaver", _FakeRedisSaver)

    saver = await _try_init_redis("redis://localhost:6379/0")

    assert saver is not None
    assert saver.ttl is None
