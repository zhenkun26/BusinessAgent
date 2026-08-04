"""限流中间件(async/await,无回调风格,对应 v3 方案 hard constraint)

设计:
- 基于 Redis 的滑动窗口限流(生产)
- 降级:Redis 不可用时用进程内内存计数器
- 按 user_id 限流(已认证)或 IP(未认证)
- 超限返回 429 Too Many Requests

策略:
- 默认 60 次/分钟(可配置 RATE_LIMIT_PER_MINUTE)
- /api/v1/auth/login 放宽到 10 次/分钟(防爆破)
- /api/v1/chat/* 收紧到 30 次/分钟(防滥用)
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import get_settings


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
    - ZADD key timestamp timestamp
    - ZREMRANGEBYSCORE key 0 (now - window)
    - ZCARD key(当前窗口内请求数)
    """

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis = None  # 懒加载

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url, decode_responses=True, socket_timeout=2
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
            pipe = redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)  # 清理过期
            pipe.zadd(redis_key, {str(now): now})  # 添加当前请求
            pipe.zcard(redis_key)  # 统计当前窗口请求数
            pipe.expire(redis_key, window_seconds + 10)  # 设置 key 过期(防内存泄漏)
            results = await pipe.execute()

            count = results[2]
            if count > limit:
                return False, 0
            return True, limit - count
        except Exception as e:
            logger.warning(f"Redis 限流失败,降级到内存: {e}")
            raise  # 由调用方降级


# ============ 限流器工厂 ============


_memory_limiter: Optional[InMemoryRateLimiter] = None
_redis_limiter: Optional[RedisRateLimiter] = None
_use_redis: Optional[bool] = None  # None=未检测, True=用 Redis, False=用内存


async def _get_limiter():
    """获取限流器(Redis 优先,失败降级内存)"""
    global _memory_limiter, _redis_limiter, _use_redis

    # 已检测过,直接返回
    if _use_redis is True and _redis_limiter is not None:
        return _redis_limiter, True
    if _use_redis is False and _memory_limiter is not None:
        return _memory_limiter, False

    # 首次初始化
    settings = get_settings()

    # 尝试 Redis
    try:
        _redis_limiter = RedisRateLimiter(settings.redis_url)
        # 探测连接
        redis = await _redis_limiter._get_redis()
        await redis.ping()
        _use_redis = True
        logger.info("限流器: Redis(生产模式)")
        return _redis_limiter, True
    except Exception as e:
        logger.warning(f"Redis 限流器初始化失败,降级内存: {e}")
        _use_redis = False
        _memory_limiter = InMemoryRateLimiter()
        return _memory_limiter, False


# ============ FastAPI 中间件 ============


# 路由级限流配置(路径前缀 -> 每分钟限制)
ROUTE_LIMITS: dict[str, int] = {
    "/api/v1/auth/login": 10,  # 登录防爆破
    "/api/v1/auth/refresh": 30,
    "/api/v1/chat": 30,  # 对话防滥用
    "/api/v1/approvals": 60,
}


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

    # 限流 key:优先用 user_id,无认证用 IP
    # user_id 从 JWT 解析(轻量解析,不验签,只取 sub)
    user_id = _extract_user_id(request)
    if user_id:
        key = f"user:{user_id}"
    else:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ip:{client_ip}"

    # 检查限流
    limiter, is_redis = await _get_limiter()
    try:
        allowed, remaining = await limiter.is_allowed(key, limit, window_seconds=60)
    except Exception:
        # Redis 异常,降级内存
        global _use_redis, _memory_limiter
        _use_redis = False
        if _memory_limiter is None:
            _memory_limiter = InMemoryRateLimiter()
        allowed, remaining = await _memory_limiter.is_allowed(key, limit, window_seconds=60)

    if not allowed:
        logger.warning(f"限流触发: key={key}, limit={limit}/min, path={path}")
        return JSONResponse(
            status_code=429,
            content={
                "detail": "请求过于频繁,请稍后再试",
                "retry_after_seconds": 60,
                "limit": limit,
            },
            headers={"Retry-After": "60"},
        )

    # 添加限流信息到响应头
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


def _extract_user_id(request: Request) -> Optional[str]:
    """从请求头解析 user_id(轻量,不验签)

    限流场景不需要完整 JWT 验证(那由业务层 get_current_user 做),
    这里只取 sub 字段作为限流 key,避免每个请求都解 JWT。
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None

    token = auth[7:]
    try:
        import jwt

        # 不验签,只解析 payload
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("sub")
    except Exception:
        return None
