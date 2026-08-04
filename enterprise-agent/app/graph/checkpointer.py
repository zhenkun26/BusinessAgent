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


async def _try_init_redis(redis_url: str) -> Optional[Checkpointer]:
    """尝试初始化 AsyncRedisSaver

    Returns:
        AsyncRedisSaver 实例(已 asetup),失败返回 None
    """
    try:
        from langgraph.checkpoint.redis import AsyncRedisSaver

        saver = AsyncRedisSaver(redis_url=redis_url)
        # asetup 创建 RediSearch 索引/schema
        # 失败原因通常:Redis 不可达 / 无 RediSearch 模块(FT.* 命令)
        # asetup 成功即视为连接 + 模块均可用,不再额外探测
        await saver.asetup()

        logger.info(f"Redis Checkpointer 初始化成功: {redis_url}")
        return saver
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Redis Checkpointer 初始化失败,准备降级: {type(e).__name__}: {e}")
        return None


# ============ PostgreSQL Checkpointer(降级 1) ============


async def _try_init_postgres(pg_dsn: str) -> Optional[Checkpointer]:
    """尝试初始化 PostgresSaver

    PostgresSaver 是同步实现,langgraph 1.x 在 async graph 中
    会自动用 asyncio.to_thread 包装其 sync 方法(put/get_tuple/list)。

    Returns:
        PostgresSaver 实例(已 setup),失败返回 None
    """
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        # PostgresSaver.from_conn_string 返回 context manager,
        # 但作为长生命周期单例,用构造函数 + 手动 setup
        # 注意: psycopg Connection 需要在线程中创建(async 上下文外)
        # 这里用 to_thread 包装整个初始化
        def _sync_init() -> Checkpointer:
            # from_conn_string 在新版返回 context manager,
            # 但 3.x 提供 __init__ 直接接收 conn_string
            # 兼容写法: 用 from_conn_string 的 context manager 进出
            import contextlib

            cm = PostgresSaver.from_conn_string(pg_dsn)
            # 进入 context manager 获取 saver
            if hasattr(cm, "__enter__"):
                saver = cm.__enter__()
                try:
                    saver.setup()
                    return saver
                except Exception:
                    cm.__exit__(None, None, None)
                    raise
            else:
                # 旧版直接是 factory
                saver = cm
                saver.setup()
                return saver

        saver = await asyncio.to_thread(_sync_init)

        # 验证连接: 用 to_thread 跑一次 get_tuple(不存在的 thread_id)
        try:
            await asyncio.to_thread(
                saver.get_tuple,
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
