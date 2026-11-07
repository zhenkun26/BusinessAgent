"""Bounded capability observations; no paid model calls or raw diagnostics."""
from __future__ import annotations

import asyncio
from typing import Any


async def probe(name: str, operation: Any) -> tuple[str, dict[str, Any]]:
    try:
        async with asyncio.timeout(4):
            value = await operation()
        if not isinstance(value, dict) or value.get('status') != 'healthy':
            return name, {'status': 'unhealthy'}
        return name, value
    except Exception:
        return name, {'status': 'unhealthy'}


async def worker_observation(worker_id: str | None = None) -> dict[str, Any]:
    from sqlalchemy import text
    from app.core.database import get_session_factory
    from app.core.task_queue import QUEUES
    async with get_session_factory()() as session:
        rows = (await session.execute(text('''SELECT DISTINCT queue_name FROM task_consumers
            WHERE last_seen >= clock_timestamp() - interval '75 seconds'
            AND (CAST(:worker AS UUID) IS NULL OR worker_id=CAST(:worker AS UUID))'''),
            {'worker': worker_id})).scalars().all()
    return {'status': 'healthy' if set(QUEUES).issubset(rows) else 'unhealthy'}


async def collect_readiness(*, worker_id: str | None = None,
                            worker: bool = False) -> dict[str, Any]:
    from app.config import get_settings
    from app.core.database import check_db_health
    from app.core.runtime_state import runtime_client
    from app.observability.audit import get_audit_logger
    from app.tools.base import list_tools
    settings = get_settings()

    async def redis() -> dict[str, str]:
        async with runtime_client() as client:
            ok = await client.ping()
        return {'status': 'healthy' if ok else 'unhealthy'}

    async def vector() -> dict[str, str]:
        if settings.vector_store_provider == 'memory' and settings.app_env == 'dev':
            return {'status': 'healthy', 'profile': 'development_memory'}
        if settings.vector_store_provider != 'milvus':
            return {'status': 'unhealthy'}
        from app.core.milvus_client import get_collection
        from pymilvus import utility
        exists = await asyncio.to_thread(utility.has_collection, get_collection().name, timeout=2)
        return {'status': 'healthy' if exists else 'unhealthy'}

    async def checkpoint() -> dict[str, str]:
        from app.graph import checkpointer
        from app.graph.checkpoint_access import read_checkpoint
        saver = checkpointer._checkpointer_instance
        if saver is None:
            return {'status': 'unhealthy'}
        await read_checkpoint(saver, {'configurable': {
            'thread_id': '__checkpoint_readiness__', 'checkpoint_ns': ''}})
        return {'status': 'healthy'}

    async def tools() -> dict[str, str]:
        required = {'query_customer', 'query_order', 'create_crm_task', 'create_ticket',
                    'update_ticket', 'send_email_internal', 'send_email_external',
                    'query_my_approvals'}
        return {'status': 'healthy' if required.issubset({v['name'] for v in list_tools()})
                else 'unhealthy'}

    checks = {'db': check_db_health, 'redis': redis, 'milvus': vector, 'tools': tools,
              'workers': lambda: worker_observation(worker_id),
              'audit': get_audit_logger().health}
    if not worker:
        checks['checkpointer'] = checkpoint
    components = dict(await asyncio.gather(*(probe(k, f) for k, f in checks.items())))
    ready = all(v['status'] == 'healthy' for v in components.values())
    # Keep only safe scalars and fixed component labels.
    from app.observability.metrics import dependency_ready, audit_pending, audit_oldest
    for name, value in components.items():
        dependency_ready.labels(component=name).set(int(value['status'] == 'healthy'))
    audit = components['audit']
    audit_pending.set(audit.get('pending', 0) if audit['status'] == 'healthy' else -1)
    audit_oldest.set(audit.get('oldest_seconds', 0) if audit['status'] == 'healthy' else -1)
    return {'status': 'ready' if ready else 'unavailable', 'components': components}
