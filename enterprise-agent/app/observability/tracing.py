"""OpenTelemetry 全链路追踪(对应 v3 方案 12.3 节)

设计:
- 自动 instrumentation:FastAPI / requests / asyncpg / redis
- 手动 span:LangGraph 节点 / RAG 阶段 / 工具调用 / Saga 步骤
- 导出器:OTLP → Jaeger(生产) / Console(开发)

Synthetic reference admission:
    TELEMETRY_MODE=synthetic, OTEL_ENABLED=true
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 (explicit process configuration)

Optional exporter/client instrumentors require separately reviewed dependencies.
The current production pins omit them; explicit enablement fails closed if unavailable.
Do not use an auto-instrumented launcher. See docs/50-engineering/telemetry-admission.md.
"""

from __future__ import annotations

import os
import math
from contextlib import contextmanager
from typing import Optional

from loguru import logger

from app import __version__
from app.observability.telemetry_policy import admit_telemetry, TelemetryConfigurationError

# 全局 tracer(懒加载)
_tracer: Optional[object] = None
_initialized: bool = False
_policy = None
_failed: bool = False

# Manual diagnostics only. Automatic SDK instrumentation has a separate review gate.
_SPAN_NAMES = frozenset({
    "rag.retrieve", "rag.embed_query", "rag.coarse_search", "rag.rerank", "worker.task",
})
_EVENT_NAMES = frozenset({
    "rag.no_results", "rag.rerank_failed", "rbac.unknown_role", "rbac.denied",
    "param.invalid", "security.injection_detected",
})
_NUMERIC_ATTRIBUTES = frozenset({
    "rag.top_k", "rag.rerank_top_n", "rag.coarse.count", "rag.coarse.k",
    "rag.rerank.count", "rag.rerank.top_score", "rag.final.top_score",
    "rag.latency_ms", "tool.latency_ms",
})
_BOOLEAN_ATTRIBUTES = frozenset({"tool.success", "tool.skip_rbac"})
_ENUM_ATTRIBUTES = {
    "rag.scene": frozenset({"policy", "factual", "inferential", "default"}),
    "rag.final.stage": frozenset({"vector", "rerank"}),
    "stage": frozenset({"coarse"}),
}


def _manual_attributes(attributes: object) -> dict:
    """Omit unknown/free-text data without evaluating opaque values or their repr."""
    if type(attributes) is not dict:
        return {}
    result = {}
    for key, value in attributes.items():
        if type(key) is not str:
            continue
        if key in _NUMERIC_ATTRIBUTES and type(value) in (int, float):
            if 0 <= value <= 1e12 and math.isfinite(value):
                result[key] = value
        elif key in _BOOLEAN_ATTRIBUTES and type(value) is bool:
            result[key] = value
        elif key in _ENUM_ATTRIBUTES and type(value) is str and value in _ENUM_ATTRIBUTES[key]:
            result[key] = value
    return result


def _manual_span_name(name: object) -> str:
    if type(name) is str:
        if name in _SPAN_NAMES:
            return name
        if name.startswith("tool."):
            return "tool.invoke"
    return "application.operation"


def _manual_event_name(name: object) -> str:
    return name if type(name) is str and name in _EVENT_NAMES else "application.event"


def init_tracing(service_name: str = "enterprise-agent") -> bool:
    """初始化 OpenTelemetry(应用启动时调用一次)

    Returns:
        True means admitted synthetic tracing; False means explicitly disabled.
        A requested SDK failure raises a fixed error and requires process restart.
    """
    global _tracer, _initialized, _policy, _failed

    policy = admit_telemetry()
    if _failed:
        raise TelemetryConfigurationError('TELEMETRY_INITIALIZATION_FAILED') from None
    if service_name not in {'enterprise-agent', 'enterprise-agent-worker', 'enterprise-agent-test'}:
        raise TelemetryConfigurationError('TELEMETRY_CONFIGURATION_REJECTED') from None
    if _policy is not None and policy != _policy:
        raise TelemetryConfigurationError('TELEMETRY_CONFIGURATION_CHANGED') from None

    if _initialized:
        return _tracer is not None

    if not policy.enabled:
        logger.info("TELEMETRY_DISABLED")
        return False

    provider = None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # 资源标识(在 Jaeger 中按 service_name 过滤)
        resource = Resource(
            {
                "service.name": service_name,
                "service.version": __version__,
                "deployment.env": (
                    os.environ.get('APP_ENV', 'dev')
                    if os.environ.get('APP_ENV', 'dev') in {'dev', 'test', 'prod'} else 'unknown'
                ),
            }
        )

        provider = TracerProvider(resource=resource)

        # OTLP 导出器(发送到 Jaeger / Tempo / Honeycomb 等)
        exporter = OTLPSpanExporter(
            endpoint=policy.endpoint, insecure=policy.endpoint.startswith('http://'), headers={},
        )
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)

        # 自动 instrumentation
        RequestsInstrumentor().instrument()  # HTTP 客户端(DeepSeek API 调用)
        RedisInstrumentor().instrument()  # Redis Checkpointer
        # FastAPIInstrumentor 在 create_app 后调用(需要 app 实例)
        # asyncpg instrumentation 需在 engine 创建前

        _initialized = True
        _policy = policy
        logger.info("TELEMETRY_SYNTHETIC_ENABLED")
        return True

    except Exception:
        _tracer = None
        _failed = True
        if provider is not None:
            try:
                provider.shutdown()
            except Exception:
                pass
        logger.error("TELEMETRY_INITIALIZATION_FAILED")
        raise TelemetryConfigurationError('TELEMETRY_INITIALIZATION_FAILED') from None


def get_tracer():
    """获取全局 tracer(未启用时返回 None)

    用法:
        from app.observability.tracing import get_tracer
        tracer = get_tracer()
        if tracer:
            with tracer.start_as_current_span("my_operation") as span:
                span.set_attribute("key", "value")
                ...
    """
    return _tracer


def instrument_fastapi(app):
    """FastAPI 应用 instrumentation(在 create_app 后调用)"""
    global _failed
    if _failed:
        raise TelemetryConfigurationError('TELEMETRY_INITIALIZATION_FAILED') from None
    if not admit_telemetry().enabled:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation 已启用")
    except Exception:
        _failed = True
        logger.error("FASTAPI_INSTRUMENTATION_UNAVAILABLE")
        raise TelemetryConfigurationError('TELEMETRY_INITIALIZATION_FAILED') from None


# ============ 便捷装饰器 ============


@contextmanager
def traced_span(name: str, attributes: Optional[dict] = None):
    """便捷 span 上下文管理器(未启用 tracing 时为 no-op)

    用法:
        from app.observability.tracing import traced_span

        with traced_span("rag.retrieve", {"rag.top_k": 5}):
            results = retriever.retrieve(query)
    """
    if _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(
        _manual_span_name(name), record_exception=False, set_status_on_exception=False,
    ) as span:
        for key, value in _manual_attributes(attributes).items():
            try:
                span.set_attribute(key, value)
            except Exception:
                pass
        yield span


def record_span_attributes(attributes: dict) -> None:
    """在当前 span 上记录属性(无 span 时为 no-op)"""
    if _tracer is None:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            for k, v in _manual_attributes(attributes).items():
                try:
                    span.set_attribute(k, v)
                except Exception:
                    pass
    except Exception:
        pass


def record_span_event(name: str, attributes: Optional[dict] = None) -> None:
    """在当前 span 上记录事件(无 span 时为 no-op)"""
    if _tracer is None:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            span.add_event(_manual_event_name(name), attributes=_manual_attributes(attributes))
    except Exception:
        pass


def record_exception(exc: Exception) -> None:
    """在当前 span 上记录异常(无 span 时为 no-op)"""
    if _tracer is None:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            span.add_event("exception", attributes={"error.message": "OPERATION_FAILED"})
    except Exception:
        pass
