"""限流中间件(async/await,无回调风格,对应 v3 方案 hard constraint)

设计:
- 基于 Redis 的滑动窗口限流(生产)
- Redis failure: non-dev returns 503; explicit dev uses labeled memory fallback
- 按 user_id 限流(已认证)或 IP(未认证)
- 超限返回 429 Too Many Requests

策略:
- 默认 60 次/分钟(可配置 RATE_LIMIT_PER_MINUTE)
- /api/v1/auth/login 放宽到 10 次/分钟(防爆破)
- /api/v1/chat/* 收紧到 30 次/分钟(防滥用)
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import get_settings
from app.security.rbac import decode_identity_token


# ============ 进程内内存限流(降级用) ============


class InMemoryRateLimiter:
    """进程内内存限流器(Redis 不可用时降级用)

    滑动窗口实现:记录每个 key 的最近请求时间戳,清理过期窗口。
    注意:多进程部署时不准确,生产环境应优先用 Redis。
    """

    def __init__(self):
        # key -> list[timestamp](最近 60 秒内的请求时间)
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    async def is_allowed(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        """检查是否允许请求

        Returns:
            (allowed, remaining) remaining = 剩余可用次数
        """
        now = time.time()

        # 定期清理过期窗口(每 5 分钟清理一次,避免内存泄漏)
        if now - self._last_cleanup > 300:
            self._cleanup(now, window_seconds)
            self._last_cleanup = now

        # 获取当前窗口内的请求
        window_start = now - window_seconds
        recent = [ts for ts in self._windows[key] if ts > window_start]
        self._windows[key] = recent

        if len(recent) >= limit:
            return False, 0

        # 记录本次请求
        self._windows[key].append(now)
        return True, limit - len(recent) - 1

    def _cleanup(self, now: float, window_seconds: int):
        """清理所有 key 的过期时间戳"""
        window_start = now - window_seconds
        keys_to_delete = []
        for key, timestamps in self._windows.items():
            recent = [ts for ts in timestamps if ts > window_start]
            if recent:
                self._windows[key] = recent
            else:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del self._windows[key]


# ============ Redis 限流(生产用) ============


class RedisRateLimiter:
    """Redis 滑动窗口限流器(生产推荐)

    用 Redis ZSET 实现精确滑动窗口:
    - ZADD key timestamp unique_member
    - ZREMRANGEBYSCORE key 0 (now - window)
    - ZCARD key(当前窗口内请求数)
    """

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis = None  # 懒加载

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            from redis.backoff import NoBackoff
            from redis.asyncio.retry import Retry

            self._redis = aioredis.from_url(
                self._redis_url, decode_responses=True, socket_timeout=2,
                socket_connect_timeout=2, retry_on_timeout=False,
                retry=Retry(NoBackoff(), 0),
            )
        return self._redis

    async def is_allowed(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        """Redis ZSET 滑动窗口限流"""
        try:
            redis = await self._get_redis()
            now = time.time()
            window_start = now - window_seconds
            redis_key = f"rate_limit:{key}"

            # 管道原子操作
            pipe = redis.pipeline(transaction=True)
            pipe.zremrangebyscore(redis_key, 0, window_start)  # 清理过期
            pipe.zadd(redis_key, {uuid4().hex: now})  # 添加当前请求
            pipe.zcard(redis_key)  # 统计当前窗口请求数
            pipe.expire(redis_key, window_seconds + 10)  # 设置 key 过期(防内存泄漏)
            results = await pipe.execute()

            count = results[2]
            if count > limit:
                return False, 0
            return True, limit - count
        except Exception:
            logger.warning("RATE_LIMIT_REDIS_COMMAND_FAILED")
            raise  # 由调用方降级


# ============ 限流器工厂 ============


REDIS_RETRY_SECONDS = 5
REDIS_OPERATION_TIMEOUT_SECONDS = 2
_retry_clock = time.monotonic

_memory_limiter: Optional[InMemoryRateLimiter] = None
_redis_limiter: Optional[RedisRateLimiter] = None
_use_redis: Optional[bool] = None
_redis_retry_at = 0.0
_redis_probe_in_progress = False
_redis_failure_generation = 0


class RateLimitUnavailable(RuntimeError):
    """A shared quota decision is unavailable; do not admit production work."""


def _mark_redis_failure() -> None:
    global _use_redis, _redis_retry_at, _redis_failure_generation
    if _use_redis is not False:
        logger.warning("RATE_LIMIT_REDIS_UNAVAILABLE")
    _use_redis = False
    _redis_retry_at = _retry_clock() + REDIS_RETRY_SECONDS
    _redis_failure_generation += 1


def _fallback_limiter() -> InMemoryRateLimiter:
    global _memory_limiter
    if get_settings().is_dev is not True:
        raise RateLimitUnavailable() from None
    if _memory_limiter is None:
        _memory_limiter = InMemoryRateLimiter()
    return _memory_limiter


async def _probe_redis(limiter: RedisRateLimiter) -> None:
    connection = await limiter._get_redis()
    await connection.ping()


async def _get_limiter() -> RedisRateLimiter | InMemoryRateLimiter:
    """Probe once per process/cooldown; followers never queue for recovery."""
    global _redis_limiter, _use_redis, _redis_probe_in_progress, _redis_retry_at
    if _use_redis is True and _redis_limiter is not None:
        return _redis_limiter
    if _redis_probe_in_progress or (_use_redis is False and _retry_clock() < _redis_retry_at):
        return _fallback_limiter()

    settings = get_settings()
    # No await between checking and claiming: one owner in this API event loop.
    _redis_probe_in_progress = True
    generation = _redis_failure_generation
    try:
        if _redis_limiter is None:
            _redis_limiter = RedisRateLimiter(settings.redis_url)
        await asyncio.wait_for(_probe_redis(_redis_limiter), REDIS_OPERATION_TIMEOUT_SECONDS)
        if generation != _redis_failure_generation:
            return _fallback_limiter()
        _use_redis = True
        _redis_retry_at = 0.0
        logger.info("RATE_LIMIT_REDIS_READY")
        return _redis_limiter
    except asyncio.CancelledError:
        _mark_redis_failure()
        raise
    except RateLimitUnavailable:
        raise
    except Exception:
        _mark_redis_failure()
        return _fallback_limiter()
    finally:
        _redis_probe_in_progress = False


async def _check_limit(key: str, limit: int) -> tuple[bool, int, str]:
    limiter = await _get_limiter()
    backend = "redis" if limiter is _redis_limiter else "memory"
    try:
        allowed, remaining = await asyncio.wait_for(
            limiter.is_allowed(key, limit, window_seconds=60), REDIS_OPERATION_TIMEOUT_SECONDS,
        )
    except asyncio.CancelledError:
        if backend == "redis":
            _mark_redis_failure()
        raise
    except Exception:
        if backend != "redis":
            raise RateLimitUnavailable() from None
        _mark_redis_failure()
        # An uncertain remote command is not replayed. Dev fallback is explicitly local.
        allowed, remaining = await _fallback_limiter().is_allowed(key, limit, window_seconds=60)
        backend = "memory"
    return allowed, remaining, backend


# ============ FastAPI 中间件 ============


# 路由级限流配置(路径前缀 -> 每分钟限制)
ROUTE_LIMITS: dict[str, int] = {
    "/api/v1/auth/login": 10,  # 登录防爆破
    "/api/v1/auth/refresh": 30,
    "/api/v1/chat": 30,  # 对话防滥用
    "/api/v1/approvals": 60,
}

MAX_AUTHORIZATION_LENGTH = 8192


async def rate_limit_middleware(request: Request, call_next):
    """限流中间件(async/await,无回调)

    按 user_id(已认证)或客户端 IP(未认证)限流。
    不同路由有不同的每分钟限制。
    """
    settings = get_settings()

    # 健康/文档检查不限流
    path = request.url.path
    if path in ("/health", "/ready", "/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    # 匹配路由限流配置
    limit = settings.rate_limit_per_minute
    for route_prefix, route_limit in ROUTE_LIMITS.items():
        if path.startswith(route_prefix):
            limit = route_limit
            break

    # Login attempts remain source-bound even when a bearer is supplied.
    # A verified quota identity does not replace downstream account authorization.
    user_id = None if path.startswith("/api/v1/auth/login") else _extract_user_id(request)
    if user_id:
        key = f"user:{user_id}"
    else:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ip:{client_ip}"

    try:
        allowed, remaining, backend = await _check_limit(key, limit)
    except RateLimitUnavailable:
        return JSONResponse(
            status_code=503,
            content={"detail": "RATE_LIMIT_UNAVAILABLE"},
            headers={"Retry-After": str(REDIS_RETRY_SECONDS),
                     "X-RateLimit-Backend": "unavailable"},
        )

    if not allowed:
        logger.warning(f"限流触发: key={key}, limit={limit}/min, path={path}")
        return JSONResponse(
            status_code=429,
            content={
                "detail": "请求过于频繁,请稍后再试",
                "retry_after_seconds": 60,
                "limit": limit,
            },
            headers={"Retry-After": "60", "X-RateLimit-Backend": backend},
        )

    # 添加限流信息到响应头
    response = await call_next(request)
    response.headers["X-RateLimit-Backend"] = backend
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


def _extract_user_id(request: Request) -> Optional[str]:
    """Select a quota identity only after shared signature and claim validation."""
    auth = request.headers.get("Authorization", "")
    if len(auth) > MAX_AUTHORIZATION_LENGTH:
        return None
    scheme, separator, token = auth.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        return None
    try:
        return decode_identity_token(token)["sub"]
    except HTTPException:
        # Invalid credentials still consume the anonymous source quota. The
        # protected route's dependency remains responsible for its 401 response.
        return None
