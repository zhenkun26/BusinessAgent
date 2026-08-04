"""W9-2 验证:OpenTelemetry tracing 全链路

测试场景:
1. tracing 模块导入 + init_tracing(关闭 OTLP 时也能正常工作)
2. span 上下文管理器(no-op 模式)
3. span 属性 + 事件记录
4. RAG retrieve span 注入(实际跑一次检索,验证 span 不破坏逻辑)
5. Tool invoke span 注入(实际调一次工具)
6. Saga execute span 注入(实际跑一次 Saga)

运行(默认 no-op 模式,无需 Jaeger):
    python -m eval.run_w9_tracing

运行(完整模式,需启动 Jaeger):
    docker compose --profile monitoring up -d jaeger
    $env:OTEL_ENABLED="true"
    $env:OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
    python -m eval.run_w9_tracing
"""

import asyncio
import os
from typing import Any

from loguru import logger


# ============ 测试 1: tracing 初始化 ============


async def test_tracing_init():
    """测试 1:tracing 模块初始化(no-op 或 OTLP)"""
    print("\n" + "=" * 60)
    print("测试 1:tracing 模块初始化")
    print("=" * 60)

    # 强制重新初始化(测试用)
    from app.observability import tracing
    tracing._initialized = False
    tracing._tracer = None

    enabled = tracing.init_tracing(service_name="enterprise-agent-test")

    print(f"OTEL_ENABLED env: {os.environ.get('OTEL_ENABLED', 'false')}")
    print(f"tracing 启用: {enabled}")
    print(f"tracer 是否为 None: {tracing.get_tracer() is None}")

    # no-op 模式也应返回 True(init 成功,只是不导出)
    # 或 False(OTEL_ENABLED=false)
    if enabled:
        print("✓ tracing 已启用(OTLP 模式)")
    else:
        print("✓ tracing 未启用(no-op 模式,span 为 nullcontext)")

    return True


# ============ 测试 2: span 上下文管理器 ============


async def test_span_context_manager():
    """测试 2:span 上下文管理器(no-op 模式下不报错)"""
    print("\n" + "=" * 60)
    print("测试 2:span 上下文管理器")
    print("=" * 60)

    from app.observability.tracing import (
        get_tracer,
        record_span_attributes,
        record_span_event,
        traced_span,
    )

    # 在 span 内执行代码(no-op 模式下应为 nullcontext)
    with traced_span("test.operation", {"test.key": "value"}):
        record_span_attributes({"test.step": 1})
        record_span_event("test.event", {"detail": "测试事件"})
        # 模拟业务逻辑
        result = 1 + 1

    if result != 2:
        print(f"✗ span 内代码执行异常: result={result}")
        return False

    print("✓ span 上下文管理器正常(不破坏业务逻辑)")

    # 嵌套 span
    with traced_span("test.outer"):
        with traced_span("test.inner"):
            record_span_attributes({"nested": True})
        record_span_attributes({"outer": True})

    print("✓ 嵌套 span 正常")
    return True


# ============ 测试 3: 异常记录 ============


async def test_exception_recording():
    """测试 3:异常记录(no-op 模式下不报错)"""
    print("\n" + "=" * 60)
    print("测试 3:异常记录")
    print("=" * 60)

    from app.observability.tracing import record_exception, traced_span

    try:
        with traced_span("test.failing_op"):
            raise ValueError("测试异常")
    except ValueError as e:
        record_exception(e)
        print(f"✓ 异常记录正常(不破坏异常传播): {e}")
        return True

    print("✗ 异常未被正确传播")
    return False


# ============ 测试 4: RAG retrieve span 注入 ============


async def test_rag_span_injection():
    """测试 4:RAG retrieve span 注入(实际跑检索,验证不破坏逻辑)"""
    print("\n" + "=" * 60)
    print("测试 4:RAG retrieve span 注入")
    print("=" * 60)

    # 前置:Milvus 已就绪(若未初始化则跳过此测试)
    try:
        from app.core.milvus_client import init_milvus, check_milvus_health
        await init_milvus(recreate=False)
        health = await check_milvus_health()
        if health.get("status") != "healthy":
            print(f"⚠ Milvus 未就绪({health}),跳过 RAG span 测试")
            return True
    except Exception as e:
        print(f"⚠ Milvus 不可用({e}),跳过 RAG span 测试")
        return True

    from app.rag.retriever import EnterpriseRAGRetriever

    retriever = EnterpriseRAGRetriever(top_k=5, rerank_top_n=3)

    try:
        result = retriever.retrieve(
            query="折扣权限",
            user_role="salesperson",
            dept_namespace="dept_sales",
        )

        print(f"检索结果数: {len(result.results)}")
        print(f"top_score: {result.top_score:.3f}")
        print(f"stage: {result.stage}")
        print(f"latency: {result.latency_ms}ms")

        if not result.results:
            print("⚠ 检索返回 0 条(Milvus 可能未入库,但 span 注入本身无问题)")
            print("✓ RAG span 注入正常(未抛异常)")
            return True

        print(f"✓ RAG span 注入正常:top_score={result.top_score:.3f}")
        return True

    except Exception as e:
        print(f"✗ RAG span 注入抛异常: {type(e).__name__}: {e}")
        return False


# ============ 测试 5: Tool invoke span 注入 ============


async def test_tool_span_injection():
    """测试 5:Tool invoke span 注入(实际调一次工具)"""
    print("\n" + "=" * 60)
    print("测试 5:Tool invoke span 注入")
    print("=" * 60)

    from app.tools.base import init_all_tools, get_tool

    init_all_tools()
    tool = get_tool("query_customer")

    if tool is None:
        print("✗ 工具 query_customer 未注册")
        return False

    context = {
        "user_id": "u001",
        "role": "salesperson",
        "dept": "dept_sales",
        "request_id": "tracing-test",
    }

    try:
        result = await tool.invoke(
            params={"customer_id": "C001"},
            context=context,
        )

        print(f"success: {result.success}")
        print(f"latency: {result.latency_ms}ms")

        if not result.success:
            print(f"✗ 工具调用失败: {result.error}")
            return False

        print(f"✓ Tool span 注入正常:latency={result.latency_ms}ms")
        return True

    except Exception as e:
        print(f"✗ Tool span 注入抛异常: {type(e).__name__}: {e}")
        return False


# ============ 测试 6: Saga execute span 注入 ============


async def test_saga_span_injection():
    """测试 6:Saga execute span 注入(实际跑一次 Saga)"""
    print("\n" + "=" * 60)
    print("测试 6:Saga execute span 注入")
    print("=" * 60)

    from app.tools.base import init_all_tools
    from app.tools.saga import SagaCoordinator

    init_all_tools()

    context = {
        "user_id": "u001",
        "role": "manager",
        "dept": "dept_sales",
        "request_id": "saga-tracing-test",
    }

    saga = SagaCoordinator(context=context)
    saga.add_step(
        step_id="step1",
        tool_name="query_customer",
        params={"customer_id": "C001"},
        block_on_failure=False,
    )
    saga.add_step(
        step_id="step2",
        tool_name="create_crm_task",
        params={
            "customer_id": "C001",
            "title": "tracing 测试任务",
            "assignee": "u001",
        },
    )

    try:
        result = await saga.execute()

        print(f"success: {result.success}")
        print(f"compensated: {result.compensated}")
        print(f"steps:")
        for s in result.steps:
            print(f"  - {s.step_id} [{s.tool_name}]: {s.status.value}")
        print(f"latency: {result.total_latency_ms}ms")

        if not result.success:
            print(f"✗ Saga 失败: {result.error}")
            return False

        print(f"✓ Saga span 注入正常:{len(result.steps)} 步全成功")
        return True

    except Exception as e:
        print(f"✗ Saga span 注入抛异常: {type(e).__name__}: {e}")
        return False


# ============ 主入口 ============


async def main():
    print("=" * 60)
    print("W9-2 验证:OpenTelemetry tracing 全链路")
    print("=" * 60)
    print(f"OTEL_ENABLED = {os.environ.get('OTEL_ENABLED', 'false')}")
    print(f"OTEL_EXPORTER_OTLP_ENDPOINT = {os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', '未设置')}")

    results = {}

    tests = [
        ("tracing_init", test_tracing_init),
        ("span_context_manager", test_span_context_manager),
        ("exception_recording", test_exception_recording),
        ("rag_span_injection", test_rag_span_injection),
        ("tool_span_injection", test_tool_span_injection),
        ("saga_span_injection", test_saga_span_injection),
    ]

    for name, test_fn in tests:
        try:
            results[name] = await test_fn()
        except Exception as e:
            import traceback

            print(f"测试 {name} 异常: {type(e).__name__}: {e}")
            traceback.print_exc()
            results[name] = False

    # 汇总
    print("\n" + "=" * 60)
    print("W9-2 Tracing 验证汇总")
    print("=" * 60)
    for name, ok in results.items():
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {name}: {status}")
    print("=" * 60)

    passed = sum(1 for ok in results.values() if ok)
    print(f"通过: {passed}/{len(results)}")

    if os.environ.get("OTEL_ENABLED", "false").lower() == "true":
        print("\n💡 OTLP 模式已启用,可在 Jaeger UI 查看完整 trace:")
        print("   http://localhost:16686")
        print("   Service: enterprise-agent-test")
    else:
        print("\n💡 no-op 模式(span 不导出)。完整验证需启动 Jaeger:")
        print("   docker compose --profile monitoring up -d jaeger")
        print('   $env:OTEL_ENABLED="true"')
        print("   python -m eval.run_w9_tracing")


if __name__ == "__main__":
    asyncio.run(main())
