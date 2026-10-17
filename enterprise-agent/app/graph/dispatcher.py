"""路由函数:Planner 后的条件边(含 Send fan-out)

LangGraph Send API 正确用法:
- 条件边函数返回 list[Send] 实现 map-reduce fan-out
- 每个 Send 携带独立子状态,LangGraph 自动并行执行
- 节点本身不应返回 list[Send](会报 Expected dict 错误)
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from langgraph.types import Send
from loguru import logger

from app.graph.state import AgentState, Intent, UserInput
from app.graph.plan_policy import PlanRejected, check_plan
from app.observability.token_usage import snapshot_total_tokens


def plan_rejected_node(state: AgentState) -> AgentState:
    """Terminate unsupported plans without executing an agent or model."""
    finished_at = datetime.now()
    started_at = state.get("started_at") or finished_at
    return AgentState(
        final_answer="当前不支持自动执行含前置依赖的任务计划。请按先后顺序分别提交任务。",
        sources=[], confidence=0.0, agent_results=[], needs_replan=False,
        replan_reason=None, replan_hint=None, answer_request_id=None,
        error="TASK_PLAN_REJECTED",
        finished_at=finished_at,
        total_latency_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
        tokens_used=snapshot_total_tokens(),
    )


def route_after_planner(state: AgentState):
    """Planner 后的条件边函数

    返回值:
    - "plan_rejected": 不支持的依赖计划,整体拒绝并结束
    - "aggregator": 闲聊或无子任务,直接汇总
    - list[Send]: 多子任务,并行 fan-out 到 agent_executor
    """
    intent: Intent = state.get("intent", Intent.KNOWLEDGE_QA)
    subtasks = state.get("subtasks", [])

    if state.get("plan_error"):
        return "plan_rejected"
    try:
        check_plan(subtasks)
    except PlanRejected:
        return "plan_rejected"

    # 闲聊或无子任务:直接进 aggregator
    if intent == Intent.CHITCHAT or not subtasks:
        logger.info(f"路由: planner → aggregator(意图={intent.value})")
        return "aggregator"

    # 有子任务:Send fan-out 到 agent_executor
    user_input: UserInput = state["user_input"]
    sends = []
    for st in subtasks:
        sub_state: AgentState = {
            "user_input": deepcopy(user_input),
            "request_id": state["request_id"],
            "current_subtask": deepcopy(st),
            "history": deepcopy(state.get("history") or []),
            "intent": intent,
        }
        sends.append(Send("agent_executor", sub_state))

    logger.info(
        f"路由: planner → {len(sends)}x agent_executor(fan-out), "
        f"tasks={[(st.task_id, st.task_type.value) for st in subtasks]}"
    )
    return sends
