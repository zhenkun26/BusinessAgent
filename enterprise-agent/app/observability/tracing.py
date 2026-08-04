"""OpenTelemetry 全链路追踪(对应 v3 方案 12.3 节)

设计:
- 自动 instrumentation:FastAPI / requests / asyncpg / redis
- 手动 span:LangGraph 节点 / RAG 阶段 / 工具调用 / Saga 步骤
- 导出器:OTLP → Jaeger(生产) / Console(开发)

启用:
    .env 设置 OTEL_ENABLED=true
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

依赖:
    pip install opentelemetry-distro opentelemetry-exporter-otlp
    opentelemetry-instrument fastapi requests asyncpg redis
"""

from __future__ import annotations

import os
from typing import Optional

from loguru import logger

# 全局 tracer(懒加载)
_tracer: Optional[object] = None
_initialized: bool = False


def init_tracing(service_name: str = "enterprise-agent") -> bool:
    """初始化 OpenTelemetry(应用启动时调用一次)

    Returns:
        True 表示已启用 tracing;False 表示未启用(开发环境或依赖缺失)
    """
    global _tracer, _initialized

    if _initialized:
        return _tracer is not None

    _initialized = True

    # 环境变量开关(默认关闭,避免开发期增加复杂度)
    if os.environ.get("OTEL_ENABLED", "false").lower() != "true":
        logger.info("OpenTelemetry 未启用(设置 OTEL_ENABLED=true 启用)")
        return False

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
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "0.1.0",
                "deployment.env": os.environ.get("APP_ENV", "dev"),
            }
        )

        provider = TracerProvider(resource=resource)

        # OTLP 导出器(发送到 Jaeger / Tempo / Honeycomb 等)
        endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)

        # 自动 instrumentation
        RequestsInstrumentor().instrument()  # HTTP 客户端(DeepSeek API 调用)
        RedisInstrumentor().instrument()  # Redis Checkpointer
        # FastAPIInstrumentor 在 create_app 后调用(需要 app 实例)
        # asyncpg instrumentation 需在 engine 创建前

        logger.info(
            f"OpenTelemetry 已启用: service={service_name}, endpoint={endpoint}"
        )
        return True

    except ImportError as e:
        logger.warning(
            f"OpenTelemetry 依赖缺失,tracing 未启用: {e}. "
            "安装: pip install opentelemetry-distro opentelemetry-exporter-otlp"
        )
        return False
    except Exception as e:
        logger.warning(f"OpenTelemetry 初始化失败: {e}")
        return False


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
    if _tracer is None:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation 已启用")
    except Exception as e:
        logger.warning(f"FastAPI instrumentation 失败: {e}")


# ============ 便捷装饰器 ============


def traced_span(name: str, attributes: Optional[dict] = None):
    """便捷 span 上下文管理器(未启用 tracing 时为 no-op)

    用法:
        from app.observability.tracing import traced_span

        with traced_span("rag.retrieve", {"query": query}):
            results = retriever.retrieve(query)
    """
    import contextlib

    if _tracer is None:
        return contextlib.nullcontext()

    ctx = _tracer.start_as_current_span(name)
    span = ctx.__enter__()
    if attributes:
        for k, v in attributes.items():
            try:
                span.set_attribute(k, v)
            except Exception:
                pass  # 非法属性值忽略
    return ctx


def record_span_attributes(attributes: dict) -> None:
    """在当前 span 上记录属性(无 span 时为 no-op)"""
    if _tracer is None:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            for k, v in attributes.items():
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
            span.add_event(name, attributes=attributes or {})
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
            span.record_exception(exc)
    except Exception:
        pass
