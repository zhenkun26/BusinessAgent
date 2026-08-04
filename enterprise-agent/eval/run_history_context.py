"""多轮上下文注入验证脚本

场景:同一 conversation_id 连发两轮
- 第 1 轮: "销售提成政策是怎么规定的?" (建立上下文)
- 第 2 轮: "那它的折扣呢?" (指代型追问)

断言:
1. 第 2 轮加载到了第 1 轮历史(load_recent_history 非空)
2. 第 2 轮意图 = knowledge_qa(历史注入让分类器不把追问误判闲聊)
3. 第 2 轮答案围绕"折扣"(指代消解生效)

运行:
    PYTHONIOENCODING=utf-8 REDIS_HOST=localhost POSTGRES_HOST=localhost \
        python -m eval.run_history_context
"""

import asyncio
import time
import uuid

from app.graph.graph import run_graph
from app.graph.history import load_recent_history
from app.graph.state import UserInput
from app.security.rbac import AgentRole


def make_input(message: str, conversation_id: str) -> UserInput:
    return UserInput(
        message=message,
        user_id="u001",
        username="销售员张三",
        role=AgentRole.SALESPERSON,
        department="dept_sales",
        jwt_token="",
        conversation_id=conversation_id,
        request_id=str(uuid.uuid4()),
    )


async def main():
    # 初始化 Milvus(检索依赖;和 run_w5_e2e 一致)
    from app.core.milvus_client import init_milvus

    await init_milvus(recreate=False)

    conversation_id = str(uuid.uuid4())
    failures = []

    # ===== 第 1 轮:建立上下文 =====
    print("=" * 60)
    print("第 1 轮: 销售提成政策是怎么规定的?")
    print("=" * 60)
    start = time.time()
    state1 = await run_graph(make_input("销售提成政策是怎么规定的?", conversation_id))
    print(f"意图: {state1.get('intent')}")
    print(f"回答: {(state1.get('final_answer') or '')[:200]}")
    print(f"耗时: {int((time.time() - start) * 1000)}ms")

    if not state1.get("final_answer"):
        failures.append("第 1 轮无 final_answer,无法建立历史")

    # ===== 历史加载自检 =====
    history = await load_recent_history(conversation_id)
    print(f"\n历史加载: {len(history)} 轮")
    for h in history:
        print(f"  用户: {h['user'][:50]}")
        print(f"  助手: {h['assistant'][:80]}")
    if not history:
        failures.append("load_recent_history 未取到第 1 轮历史")

    # ===== 第 2 轮:指代型追问 =====
    print("\n" + "=" * 60)
    print("第 2 轮: 那它的折扣呢?")
    print("=" * 60)
    start = time.time()
    state2 = await run_graph(make_input("那它的折扣呢?", conversation_id))
    intent2 = state2.get("intent")
    answer2 = state2.get("final_answer") or ""
    print(f"意图: {intent2}")
    print(f"回答: {answer2[:300]}")
    print(f"耗时: {int((time.time() - start) * 1000)}ms")

    intent_val = intent2.value if hasattr(intent2, "value") else str(intent2)
    if intent_val != "knowledge_qa":
        failures.append(f"第 2 轮意图应为 knowledge_qa,实际 {intent_val}")
    if "折扣" not in answer2:
        failures.append("第 2 轮答案未围绕「折扣」,指代消解可能未生效")
    if not state2.get("history"):
        failures.append("第 2 轮 state 中无 history")

    # ===== 结论 =====
    print("\n" + "=" * 60)
    if failures:
        print(f"验证失败 {len(failures)} 项:")
        for f in failures:
            print(f"  - {f}")
        raise SystemExit(1)
    print("多轮上下文注入验证通过:历史加载 / 意图分类 / 指代消解 均正常")


if __name__ == "__main__":
    asyncio.run(main())
