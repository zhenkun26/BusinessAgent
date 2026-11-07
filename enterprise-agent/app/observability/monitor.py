"""Opt-in controlled monitor: retained firing/resolved events, no business data or cleanup."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any
import uuid

import httpx
from loguru import logger

from app.observability.retained import RetainedStore

TARGETS = {'api': 'http://api:8000/ready', 'api2': 'http://api2:8000/ready',
           'worker': 'http://worker:8001/ready'}


async def bounded_json(client: Any, method: str, url: str, **kwargs: Any) -> tuple[int, Any]:
    async with asyncio.timeout(5):
        async with client.stream(method, url, **kwargs) as response:
            data = bytearray()
            async for chunk in response.aiter_bytes():
                if len(data)+len(chunk) > 65536:
                    raise ValueError('OBSERVATION_RESPONSE_TOO_LARGE')
                data.extend(chunk)
            return response.status_code, json.loads(data)


class Monitor:
    def __init__(self, store: RetainedStore, client: Any, token: str,
                 targets: tuple[str, ...] = ('api', 'worker')) -> None:
        if len(token) < 32 or not targets or any(t not in TARGETS for t in targets):
            raise ValueError('MONITOR_CONFIGURATION_REJECTED')
        self.store, self.client, self.token, self.targets = store, client, token, targets

    async def tick(self) -> None:
        for name in self.targets:
            try:
                status, data = await bounded_json(self.client, 'GET', TARGETS[name])
                failing = status != 200 or data.get('status') != 'ready'
                # Persistent backlog is a fault even when retention remains available.
                audit = data.get('components', {}).get('audit', {})
                failing = failing or audit.get('oldest_seconds', 0) > 60
            except Exception:
                failing = True
            await asyncio.to_thread(self.store.observe, name, failing)
        # Ordered transport: stop at first unknown acknowledgement to preserve fault/recovery order.
        for item in await asyncio.to_thread(self.store.pending, 'alert', 100):
            try:
                status, body = await bounded_json(self.client, 'POST',
                    'http://alert-receiver:8090/alerts', json=item['body'],
                    headers={'Authorization': 'Bearer '+self.token})
                if status != 200 or body != {'event_id': item['event_id'], 'status': 'retained'}:
                    raise ValueError('ALERT_ACK_INVALID')
                await asyncio.to_thread(self.store.acknowledge, item['event_id'])
            except Exception:
                logger.warning('CONTROLLED_ALERT_DELIVERY_PENDING')
                break


def validate_alert(body: Any) -> dict[str, str]:
    if (not isinstance(body, dict) or set(body) != {'event_id', 'condition', 'state'}
            or body['condition'] not in TARGETS or body['state'] not in {'firing', 'resolved'}
            or str(uuid.UUID(body['event_id'])) != body['event_id']):
        raise ValueError('ALERT_REJECTED')
    return body


async def main() -> None:
    token = os.environ.get('CONTROLLED_ALERT_TOKEN', '')
    store = RetainedStore(os.environ.get('OBSERVABILITY_STORE_PATH', '/data/monitor/state.sqlite3'))
    targets = ('api', 'api2', 'worker') if os.environ.get('OBSERVABILITY_DUAL_API') == 'true' else ('api', 'worker')
    async with httpx.AsyncClient(timeout=5, trust_env=False, follow_redirects=False) as client:
        monitor = Monitor(store, client, token, targets)
        while True:
            try:
                await monitor.tick()
            except Exception:
                logger.error('CONTROLLED_MONITOR_STORE_FAILED')
            await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(main())
