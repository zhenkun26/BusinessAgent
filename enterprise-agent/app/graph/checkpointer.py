"""Explicit checkpoint backend, bounded initialization and owned resource lifetime.

No automatic failover or state migration. Redis may create its existing indexes;
PostgreSQL schema setup requires the separate, explicit provisioning command.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import AsyncExitStack
import sys
from typing import Any

from loguru import logger

from app.config import get_settings
from app.graph.checkpoint_access import CheckpointUnavailable, read_checkpoint

Checkpointer = Any
INIT_TIMEOUT_SECONDS = 15
CLOSE_TIMEOUT_SECONDS = 5
_checkpointer_instance: Checkpointer | None = None
_checkpointer_backend: str | None = None
_resources: AsyncExitStack | None = None
_init_lock = asyncio.Lock()


def _selected_backend() -> str:
    settings = get_settings()
    backend = settings.checkpoint_backend
    if backend not in {"redis", "postgres", "memory"}:
        raise CheckpointUnavailable()
    if backend == "memory" and settings.app_env != "dev":
        raise CheckpointUnavailable()
    return backend


def _redis_ttl_config() -> dict[str, Any] | None:
    days = get_settings().checkpoint_ttl_days
    if days <= 0:
        return None
    return {"default_ttl": days * 24 * 60, "refresh_on_read": True}


def _postgres_conninfo() -> str:
    from psycopg.conninfo import make_conninfo

    settings = get_settings()
    return make_conninfo(
        host=settings.postgres_host, port=settings.postgres_port,
        user=settings.postgres_user, password=settings.postgres_password,
        dbname=settings.postgres_db, connect_timeout=5,
        options="-c statement_timeout=5000 -c lock_timeout=5000",
    )


async def _open_backend(backend: str, resources: AsyncExitStack) -> Checkpointer:
    if backend == "redis":
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        saver = AsyncRedisSaver(
            redis_url=get_settings().redis_url, ttl=_redis_ttl_config(),
            connection_args={"socket_connect_timeout": 5, "socket_timeout": 5,
                             "retry": Retry(NoBackoff(), 0)},
        )
        # Register before setup so partially initialized clients also close.
        resources.push_async_callback(saver.__aexit__, None, None, None)
        await saver.asetup()
        return saver
    if backend == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        return await resources.enter_async_context(
            AsyncPostgresSaver.from_conn_string(_postgres_conninfo())
        )
    from langgraph.checkpoint.memory import MemorySaver

    logger.warning("CHECKPOINT_MEMORY_NON_DURABLE")
    return MemorySaver()


async def _close(resources: AsyncExitStack) -> None:
    try:
        await asyncio.wait_for(resources.aclose(), CLOSE_TIMEOUT_SECONDS)
    except Exception:
        logger.warning("CHECKPOINT_CLOSE_FAILED")


async def get_checkpointer() -> tuple[Checkpointer, str]:
    """Publish one probed saver; initialization failure never selects a fallback."""
    global _checkpointer_instance, _checkpointer_backend, _resources
    async with _init_lock:
        if _checkpointer_instance is not None:
            assert _checkpointer_backend is not None
            return _checkpointer_instance, _checkpointer_backend
        resources = AsyncExitStack()
        try:
            backend = _selected_backend()
            async with asyncio.timeout(INIT_TIMEOUT_SECONDS):
                saver = await _open_backend(backend, resources)
                await read_checkpoint(saver, {"configurable": {
                    "thread_id": "__checkpoint_readiness__", "checkpoint_ns": "",
                }})
        except BaseException as exc:
            await _close(resources)
            if isinstance(exc, asyncio.CancelledError):
                raise
            if not isinstance(exc, Exception):
                raise
            raise CheckpointUnavailable() from None
        _checkpointer_instance, _checkpointer_backend, _resources = saver, backend, resources
        logger.info(f"Checkpoint initialized: backend={backend}")
        return saver, backend


def get_checkpointer_backend() -> str | None:
    """Selected backend label, not a continuous health/durability assertion."""
    return _checkpointer_backend


async def reset_checkpointer() -> None:
    """Close after requests drain; never use for live backend switching."""
    global _checkpointer_instance, _checkpointer_backend, _resources
    async with _init_lock:
        resources = _resources
        _checkpointer_instance = _checkpointer_backend = _resources = None
        graph = sys.modules.get("app.graph.graph")
        if graph is not None and hasattr(graph, "reset_graph"):
            graph.reset_graph()
        if resources is not None:
            await _close(resources)


async def setup_postgres() -> None:
    """Explicit provisioning only; callers must authorize an isolated target first."""
    resources = AsyncExitStack()
    try:
        if _selected_backend() != "postgres":
            raise CheckpointUnavailable()
        async with asyncio.timeout(INIT_TIMEOUT_SECONDS):
            saver = await _open_backend("postgres", resources)
            await saver.setup()
            await read_checkpoint(saver, {"configurable": {
                "thread_id": "__checkpoint_readiness__", "checkpoint_ns": "",
            }})
    except Exception:
        raise CheckpointUnavailable() from None
    finally:
        await _close(resources)


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicit checkpoint schema provisioning")
    parser.add_argument("command", choices=["setup-postgres"])
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("CHECKPOINT_SETUP_REQUIRES_EXECUTE")
        return 2
    try:
        asyncio.run(setup_postgres())
    except CheckpointUnavailable:
        print("CHECKPOINT_UNAVAILABLE")
        return 1
    print("CHECKPOINT_SETUP_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
