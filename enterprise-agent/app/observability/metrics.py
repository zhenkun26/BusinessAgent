"""可观测性:Prometheus 指标(对应 v3 方案 12.2 节)"""

import time
from typing import Awaitable, Callable

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ============ 业务指标 ============
rag_hit_rate = Gauge("agent_rag_hit_rate", "RAG 检索命中率")
approval_pass_rate = Gauge("agent_approval_pass_rate", "审批通过率")
human_escalation_rate = Gauge("agent_human_escalation_rate", "人工兜底率")

# ============ LLM 降级 ============
llm_degradation_count = Counter(
    "agent_llm_degradation_total",
    "LLM 降级次数",
    ["level"],  # primary / lite / local / faq
)

# ============ 性能指标 ============
node_latency = Histogram(
    "agent_node_latency_seconds",
    "LangGraph 节点耗时",
    ["node_name"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
)

workflow_total_latency = Histogram(
    "agent_workflow_latency_seconds",
    "工作流总耗时",
    buckets=(1, 5, 10, 30, 60, 120, 300),
)

http_request_latency = Histogram(
    "agent_http_request_latency_seconds",
    "HTTP 请求耗时",
    ["method", "path", "status"],
    buckets=(0.05, 0.1, 0.5, 1, 2, 5, 10),
)

# ============ 错误指标 ============
error_count = Counter(
    "agent_errors_total",
    "错误总数",
    ["error_type", "severity"],
)

saga_rollback_count = Counter(
    "agent_saga_rollback_total",
    "Saga 回滚次数",
    ["operation_type"],
)

# ============ 会话指标 ============
active_sessions = Gauge("agent_active_sessions", "活跃会话数")
total_sessions = Counter("agent_total_sessions_total", "累计会话数")


class MetricsMiddleware:
    """HTTP 指标采集中间件"""

    async def __call__(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        http_request_latency.labels(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        ).observe(duration)

        return response


# 全局实例(供 FastAPI 中间件使用)
metrics_middleware = MetricsMiddleware()
