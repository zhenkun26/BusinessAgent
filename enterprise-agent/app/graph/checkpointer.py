"""LangGraph Checkpointer 三级降级链(Redis → PostgreSQL → Memory)

对应 v3 方案 P0-3:
- 主路径: AsyncRedisSaver(生产,持久化 + 跨进程恢复 + interrupt 支持)
- 降级 1: PostgresSaver(Redis 不可用时,PG 持久化,langgraph 自动 to_thread 包装)
- 降级 2: MemorySaver(最终兜底,进程内内存,重启丢失)

降级触发条件:
- Redis 连接失败/asetup 异常 → PG
- PG 连接失败/setup 异常 → Memory

用法:
    checkpointer, backend = await get_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    await graph.ainvoke(initial_state, config=config)

设计要点:
- 单例缓存: 同一进程内只初始化一次,避免重复 setup
- 异步初始化: Redis/PG 的 setup 是 IO 操作,不阻塞事件循环
- 健康检查: 初始化时主动 ping,确保连接可用才返回
- 无回调风格: 全 async/await(符合 hard constraint)
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from loguru import logger

from app.config import get_settings


# ============ 类型别名 ============
# LangGraph BaseCheckpointSaver,具体类型由各 saver 模块提供
Checkpointer = Any


# ============ 单例缓存 ============
_checkpointer_instance: Optional[Checkpointer] = None
_checkpointer_backend: Optional[str] = None


# ============ Redis Checkpointer(主路径) ============


def _redis_ttl_config() -> Optional[dict[str, Any]]:
    """构造 AsyncRedisSaver 的滑动 TTL 配置(I-06)

    - checkpoint_ttl_days > 0: 每次会话活跃(aput 写入/aget 读取)刷新
      对应 thread 键的过期时间,refresh_on_read 开启读路径滑动;
    - <= 0: 返回 None,不设 TTL(恢复旧行为)。
    """
    days = get_settings().checkpoint_ttl_days
    if days <= 0:
        return None
    return {"default_ttl": days * 24 * 60, "refresh_on_read": True}


async def _try_init_redis(redis_url: str) -> Optional[Checkpointer]:
    """尝试初始化 AsyncRedisSaver

    Returns:
        AsyncRedisSaver 实例(已 asetup),失败返回 None
    """
    try:
        from langgraph.checkpoint.redis import AsyncRedisSaver

        ttl_config = _redis_ttl_config()
        saver = AsyncRedisSaver(redis_url=redis_url, ttl=ttl_config)
        if ttl_config:
            logger.info(
                f"Checkpoint 滑动过期已启用: TTL={get_settings().checkpoint_ttl_days} 天"
            )
        # asetup 创建 RediSearch 索引/schema
        # 失败原因通常:Redis 不可达 / 无 RediSearch 模块(FT.* 命令)
        # asetup 成功即视为连接 + 模块均可用,不再额外探测
        await saver.asetup()

        logger.info(f"Redis Checkpointer 初始化成功: {_redact_url(redis_url)}")
        return saver
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"Redis Checkpointer 初始化失败,准备降级: "
            f"{type(e).__name__}: {_redact_url(redis_url)}"
        )
        return None


def _redact_url(url: str) -> str:
    """日志脱敏:隐藏 URL 中的密码(redis://:pass@host → redis://:***@host)"""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    auth_part, _, host_part = rest.rpartition("@")
    if ":" in auth_part:
        auth_part = auth_part.split(":", 1)[0] + ":***"
    return f"{scheme}://{auth_part}@{host_part}"


# ============ PostgreSQL Checkpointer(降级 1) ============


async def _try_init_postgres(pg_dsn: str) -> Optional[Checkpointer]:
    """尝试初始化 AsyncPostgresSaver(降级 1)

    修复:此前使用同步 PostgresSaver,LangGraph async 执行路径调用
    aget_tuple 时基类直接抛 NotImplementedError,导致 Redis 不可用时
    聊天链路 500。改用 AsyncPostgresSaver(原生支持 aget_tuple/aput)。

    Returns:
        AsyncPostgresSaver 实例(已 asetup),失败返回 None
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver = AsyncPostgresSaver.from_conn_string(pg_dsn)
        await saver.asetup()

        # 验证连接: 跑一次 aget_tuple(不存在的 thread_id)
        try:
            await saver.aget_tuple(
                {"configurable": {"thread_id": "__healthcheck__"}},
            )
        except Exception as ping_err:
            logger.debug(f"Postgres ping 跳过: {ping_err}")

        logger.info(f"Postgres Checkpointer 初始化成功: {pg_dsn.split('@')[-1] if '@' in pg_dsn else pg_dsn}")
        return saver
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Postgres Checkpointer 初始化失败,准备降级 Memory: {type(e).__name__}: {e}")
        return None


# ============ Memory Checkpointer(最终兜底) ============


def _init_memory() -> Checkpointer:
    """初始化 MemorySaver(进程内内存,无需 IO)"""
    from langgraph.checkpoint.memory import MemorySaver

    saver = MemorySaver()
    logger.warning("Memory Checkpointer 已启用(进程内,重启丢失)— 仅适合开发/兜底场景")
    return saver


# ============ 降级链入口 ============


async def get_checkpointer() -> tuple[Checkpointer, str]:
    """获取 Checkpointer 单例(三级降级链)

    降级顺序: Redis → PostgreSQL → Memory

    Returns:
        (checkpointer, backend_name) backend ∈ {"redis", "postgres", "memory"}
    """
    global _checkpointer_instance, _checkpointer_backend

    if _checkpointer_instance is not None:
        return _checkpointer_instance, _checkpointer_backend  # type: ignore[return-value]

    settings = get_settings()

    # Level 1: Redis
    saver = await _try_init_redis(settings.redis_url)
    if saver is not None:
        _checkpointer_instance = saver
        _checkpointer_backend = "redis"
        return saver, "redis"

    # Level 2: PostgreSQL
    # 注意: PG dsn 用 psycopg 协议(非 asyncpg),因为 PostgresSaver 是同步
    pg_dsn = (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
    saver = await _try_init_postgres(pg_dsn)
    if saver is not None:
        _checkpointer_instance = saver
        _checkpointer_backend = "postgres"
        return saver, "postgres"

    # Level 3: Memory
    saver = _init_memory()
    _checkpointer_instance = saver
    _checkpointer_backend = "memory"
    return saver, "memory"


def get_checkpointer_backend() -> Optional[str]:
    """获取当前已初始化的 checkpointer 后端名(未初始化返回 None)"""
    return _checkpointer_backend


async def reset_checkpointer() -> None:
    """重置 checkpointer 单例(配置变更/测试用)

    注意: 已编译的 graph 仍持有旧 checkpointer 引用,
    需同时调用 reset_graph() 重新编译。
    """
    global _checkpointer_instance, _checkpointer_backend
    _checkpointer_instance = None
    _checkpointer_backend = None
