"""路由函数:Planner 后的条件边(含 Send fan-out)

LangGraph Send API 正确用法:
- 条件边函数返回 list[Send] 实现 map-reduce fan-out
- 每个 Send 携带独立子状态,LangGraph 自动并行执行
- 节点本身不应返回 list[Send](会报 Expected dict 错误)
"""

from __future__ import annotations

from langgraph.types import Send
from loguru import logger

from app.graph.state import AgentState, Intent, UserInput


def route_after_planner(state: AgentState):
    """Planner 后的条件边函数

    返回值:
    - "aggregator": 闲聊或无子任务,直接汇总
    - list[Send]: 多子任务,并行 fan-out 到 agent_executor
    """
    intent: Intent = state.get("intent", Intent.KNOWLEDGE_QA)
    subtasks = state.get("subtasks", [])

    # 闲聊或无子任务:直接进 aggregator
    if intent == Intent.CHITCHAT or not subtasks:
        logger.info(f"路由: planner → aggregator(意图={intent.value})")
        return "aggregator"

    # 有子任务:Send fan-out 到 agent_executor
    user_input: UserInput = state["user_input"]
    sends = []
    for st in subtasks:
        sub_state: AgentState = {
            "user_input": user_input,
            "request_id": state["request_id"],
            "current_subtask": st,
            "intent": intent,
        }
        sends.append(Send("agent_executor", sub_state))

    logger.info(
        f"路由: planner → {len(sends)}x agent_executor(fan-out), "
        f"tasks={[(st.task_id, st.task_type.value) for st in subtasks]}"
    )
    return sends
