"""Supervised audit replay and an internal worker observation endpoint."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from collections.abc import Iterator
import json
from typing import Any

from loguru import logger


async def replay_loop(audit: Any) -> None:
    while True:
        try:
            await audit.flush_local_cache()
        except Exception:
            logger.error('AUDIT_REPLAY_LOOP_FAILED')
        await asyncio.sleep(10)


class WorkerObservations:
    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope['type'] != 'http':
            return
        from app.observability.readiness import collect_readiness
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        path = scope.get('path')
        code, content_type = 200, 'application/json'
        if scope.get('method') != 'GET':
            code, value = 405, {'detail': 'METHOD_NOT_ALLOWED'}
        elif path == '/health':
            value = {'status': 'alive'}
        elif path in {'/ready', '/metrics'}:
            value = await collect_readiness(worker_id=self.worker_id, worker=True)
            if path == '/metrics':
                content_type, value = CONTENT_TYPE_LATEST, generate_latest()
            elif value['status'] != 'ready':
                code = 503
        else:
            code, value = 404, {'detail': 'NOT_FOUND'}
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        await send({'type': 'http.response.start', 'status': code,
                    'headers': [(b'content-type', content_type.encode()),
                                (b'cache-control', b'no-store')]})
        await send({'type': 'http.response.body', 'body': body})


async def serve_worker_observations(worker_id: str) -> None:
    import uvicorn
    class WorkerServer(uvicorn.Server):
        @contextmanager
        def capture_signals(self) -> Iterator[None]:
            # The worker supervisor owns process signals and cancels this child.
            yield

    config = uvicorn.Config(WorkerObservations(worker_id), host='0.0.0.0', port=8001,
                            lifespan='off', access_log=False, log_level='warning',
                            timeout_graceful_shutdown=5)
    server = WorkerServer(config)
    try:
        await server.serve()
    except BaseException:
        if server.started:
            await server.shutdown()
        raise
