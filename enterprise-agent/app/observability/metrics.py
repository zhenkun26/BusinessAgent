"""可观测性:Prometheus 指标(对应 v3 方案 12.2 节)"""

import time
from typing import Any
import uuid

from app.observability.correlation import request_id

from prometheus_client import Counter, Gauge, Histogram

# Unproduced historical quality/session/node gauges are intentionally not exported.

# ============ LLM token 用量(I-07,经 TokenUsageCallbackHandler 统一采集) ============
llm_token_usage = Counter(
    "agent_llm_tokens_total",
    "LLM token 消耗总量",
    ["model", "token_type"],  # token_type: prompt / completion / total
)

http_request_latency = Histogram(
    "agent_http_request_latency_seconds",
    "HTTP 请求耗时",
    ["method", "path", "status"],
    buckets=(0.05, 0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)

dependency_ready = Gauge('agent_dependency_ready', 'Required dependency observed ready', ['component'])
audit_pending = Gauge('agent_audit_pending', 'Retained audit events pending delivery; -1 unavailable')
audit_oldest = Gauge('agent_audit_oldest_seconds', 'Oldest pending audit age; -1 unavailable')
http_response_start = Histogram('agent_http_response_start_seconds', 'Time to response headers',
                                ['method', 'path'], buckets=(0.05, 0.1, 0.5, 1, 2, 5, 30))
http_outcomes = Counter('agent_http_outcomes_total', 'HTTP transport completion; not business outcome',
                        ['method', 'path', 'outcome'])


def route_label(scope: dict[str, Any]) -> str:
    path = getattr(scope.get('route'), 'path', None)
    if isinstance(path, str):
        return path
    if scope.get('path', '').startswith('/ui/') or scope.get('path') == '/ui':
        return '/ui/{asset}'
    return '__unmatched__'


class MetricsMiddleware:
    """ASGI timing includes streaming body completion, with server-owned request context."""
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        method = scope.get('method', 'OTHER')
        if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'}:
            method = 'OTHER'
        status, complete, disconnected = 500, False, False
        ended = None
        rid = uuid.uuid4().hex
        scope.setdefault('state', {})['request_id'] = rid
        token = request_id.set(rid)

        async def observed_receive() -> Any:
            nonlocal disconnected
            message = await receive()
            if message['type'] == 'http.disconnect':
                disconnected = True
            return message

        async def observed_send(message: Any) -> None:
            nonlocal status, complete, ended
            if message['type'] == 'http.response.start':
                status = message['status']
                message = dict(message)
                message['headers'] = [(k, v) for k, v in message.get('headers', [])
                                      if k.lower() != b'x-request-id'] + [(b'x-request-id', rid.encode())]
                http_response_start.labels(method=method, path=route_label(scope)).observe(
                    time.perf_counter()-start)
            await send(message)
            if message['type'] == 'http.response.body' and not message.get('more_body', False):
                complete = True
                ended = time.perf_counter()

        try:
            await self.app(scope, observed_receive, observed_send)
        finally:
            path = route_label(scope)
            outcome = 'complete' if complete else 'disconnected' if disconnected else 'aborted'
            http_request_latency.labels(method=method, path=path, status=str(status)).observe(
                (ended if ended is not None else time.perf_counter())-start)
            http_outcomes.labels(method=method, path=path, outcome=outcome).inc()
            request_id.reset(token)
