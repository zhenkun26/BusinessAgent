"""W5 端到端验证脚本:多 Agent 图能跑通

测试场景:
1. 闲聊(直接 aggregator,无 Agent)
2. 单知识问答(planner → knowledge → aggregator)
3. 多任务(planner → dispatcher → 多 Agent 并行 → aggregator)

运行:
    python -m eval.run_w5_e2e
"""

import asyncio
import time
import uuid
from pathlib import Path

from loguru import logger

from app.graph.graph import run_graph
from app.graph.state import UserInput
from app.rag.ingest import MilvusIngestService
from app.rag.vector_store import get_vector_store
from app.security.rbac import AgentRole


async def ensure_ingest():
    """确保 sample_docs 已入库(W5 测试前置;milvus 后端先初始化连接)"""
    # milvus 后端需先初始化(memory 后端跳过;P1 起 .env 默认 milvus)
    from app.config import get_settings
    if get_settings().vector_store_provider == "milvus":
        from app.core.milvus_client import init_milvus
        await init_milvus(recreate=False)

    sample_dir = Path(__file__).parent / "sample_docs"
    if not sample_dir.exists():
        logger.warning(f"sample_docs 目录不存在: {sample_dir}")
        return 0

    vs = get_vector_store()
    stats = vs.get_stats()
    existing = stats.get("total_chunks", 0) if isinstance(stats, dict) else 0

    if existing > 0:
        logger.info(f"VectorStore 已有 {existing} chunks,跳过入库")
        return existing

    ingest = MilvusIngestService()
    total = 0
    for md_file in sorted(sample_dir.glob("*.md")):
        try:
            count = ingest.ingest_file(
                file_path=md_file,
                title=md_file.stem,
                doc_type="policy",
                dept_namespace="shared_company",
            )
            total += count
            logger.info(f"入库 {md_file.name}: {count} chunks")
        except Exception as e:
            logger.error(f"入库 {md_file.name} 失败: {e}")

    logger.info(f"入库完成,共 {total} chunks")
    return total


async def test_chitchat():
    """测试 1:闲聊场景"""
    print("\n" + "=" * 60)
    print("测试 1:闲聊场景")
    print("=" * 60)

    user_input = UserInput(
        message="你好",
        user_id="u001",
        username="测试用户",
        role=AgentRole.SALESPERSON,
        department="dept_sales",
        jwt_token="",
        conversation_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
    )

    start = time.time()
    final_state = await run_graph(user_input)
    latency = int((time.time() - start) * 1000)

    print(f"消息: {user_input.message}")
    print(f"意图: {final_state.get('intent')}")
    print(f"子任务数: {len(final_state.get('subtasks', []))}")
    print(f"最终回答: {final_state.get('final_answer')}")
    print(f"置信度: {final_state.get('confidence')}")
    print(f"总耗时: {latency}ms")


async def test_single_knowledge():
    """测试 2:单知识问答"""
    print("\n" + "=" * 60)
    print("测试 2:单知识问答")
    print("=" * 60)

    user_input = UserInput(
        message="折扣权限是怎么规定的?",
        user_id="u001",
        username="销售员张三",
        role=AgentRole.SALESPERSON,
        department="dept_sales",
        jwt_token="",
        conversation_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
    )

    start = time.time()
    final_state = await run_graph(user_input)
    latency = int((time.time() - start) * 1000)

    print(f"消息: {user_input.message}")
    print(f"意图: {final_state.get('intent')}")
    print(f"子任务数: {len(final_state.get('subtasks', []))}")
    print(f"Agent 结果数: {len(final_state.get('agent_results', []))}")
    print(f"最终回答: {final_state.get('final_answer')}")
    print(f"置信度: {final_state.get('confidence')}")
    print(f"来源数: {len(final_state.get('sources', []))}")
    print(f"needs_replan: {final_state.get('needs_replan')}")
    print(f"总耗时: {latency}ms")


async def test_multi_task():
    """测试 3:多任务场景(并行 fan-out)

    用真正的多任务类型(知识查询 + 数据操作)触发 multi_task 意图,
    避免 LLM 把两个同类型任务合并为单一 knowledge_qa。
    """
    print("\n" + "=" * 60)
    print("测试 3:多任务场景(并行 fan-out)")
    print("=" * 60)

    user_input = UserInput(
        message="帮我查一下折扣政策是什么,然后给经理发一封邮件说明折扣审批流程",
        user_id="u001",
        username="销售员张三",
        role=AgentRole.SALESPERSON,
        department="dept_sales",
        jwt_token="",
        conversation_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
    )

    start = time.time()
    final_state = await run_graph(user_input)
    latency = int((time.time() - start) * 1000)

    print(f"消息: {user_input.message}")
    print(f"意图: {final_state.get('intent')}")
    print(f"Planner 推理: {final_state.get('plan_reasoning')}")
    print(f"子任务数: {len(final_state.get('subtasks', []))}")
    for st in final_state.get("subtasks", []):
        print(f"  - {st.task_id} [{st.task_type.value}] {st.description[:50]}")
    print(f"Agent 结果数: {len(final_state.get('agent_results', []))}")
    for r in final_state.get("agent_results", []):
        print(
            f"  - {r.agent_name}: success={r.success}, "
            f"confidence={r.confidence:.3f}, latency={r.latency_ms}ms"
        )
    print(f"最终回答: {final_state.get('final_answer')}")
    print(f"置信度: {final_state.get('confidence')}")
    print(f"来源数: {len(final_state.get('sources', []))}")
    print(f"总耗时: {latency}ms")


async def main():
    """主测试入口"""
    print("=" * 60)
    print("W5 端到端验证:多 Agent 图")
    print("=" * 60)

    # 前置:确保 sample_docs 已入库到 memory 后端
    print("\n[前置] 入库 sample_docs...")
    total = await ensure_ingest()
    print(f"[前置] 入库完成,共 {total} chunks")

    try:
        await test_chitchat()
    except Exception as e:
        print(f"测试 1 失败: {e}")

    try:
        await test_single_knowledge()
    except Exception as e:
        print(f"测试 2 失败: {e}")

    try:
        await test_multi_task()
    except Exception as e:
        print(f"测试 3 失败: {e}")

    print("\n" + "=" * 60)
    print("W5 端到端验证完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
