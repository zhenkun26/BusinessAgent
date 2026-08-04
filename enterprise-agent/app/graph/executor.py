"""Agent Executor 节点:子任务执行器(对应 v3 方案 6.3 节)

职责:
- 从 state.current_subtask 读取子任务
- 根据 task_type 路由到对应 Agent(knowledge/analysis/execution)
- 调用 Agent.run(),返回 AgentResult(由 LangGraph 自动合并到 agent_results)
"""

from __future__ import annotations

import time
from typing import Optional

from loguru import logger

from app.agents.analysis import AnalysisAgent
from app.agents.execution import ExecutionAgent
from app.agents.knowledge import AgentResult
from app.graph.state import AgentState, SubTask, TaskType, UserInput
from app.security.rbac import AgentRole


# 子 Agent 单例缓存(按 user_role + user_id 缓存,避免串用户身份)
_agent_cache: dict[tuple[str, str, AgentRole, str], object] = {}


async def agent_executor_node(state: AgentState) -> AgentState:
    """子任务执行器节点(并行 fan-out 的目标节点)

    每个 Send 会调用一次本节点,执行 current_subtask。
    返回的 AgentResult 会被 LangGraph 通过可重置 reducer 合并到 agent_results。

    节点必须是 async:Agent.run 内会访问 SQLAlchemy async 引擎(审计/审批建单),
    引擎绑定主事件循环,若在同步节点里开新线程跑 asyncio.run 会报
    "Future attached to a different loop"。
    """
    start = time.time()
    user_input: UserInput = state["user_input"]
    subtask: SubTask = state["current_subtask"]

    logger.info(
        f"AgentExecutor 开始: task_id={subtask.task_id}, type={subtask.task_type.value}, "
        f"desc={subtask.description[:60]!r}"
    )

    try:
        agent = _get_agent(subtask.task_type, user_input)

        # 调用 Agent.run(异步方法,LangGraph 原生支持 async 节点,直接 await)
        # knowledge 支持多轮上下文(指代消解 + 答案生成带历史);其余 agent 签名不变
        if subtask.task_type == TaskType.KNOWLEDGE:
            result = await agent.run(subtask.description, history=state.get("history"))
        else:
            result = await agent.run(subtask.description)

        latency_ms = int((time.time() - start) * 1000)
        logger.info(
            f"AgentExecutor 完成: task_id={subtask.task_id}, agent={result.agent_name}, "
            f"success={result.success}, confidence={result.confidence:.3f}, "
            f"latency={latency_ms}ms"
        )

        # 返回新的 agent_results(LangGraph 通过 operator.add 合并)
        return AgentState(agent_results=[result])

    except Exception as e:  # noqa: BLE001
        logger.exception(f"AgentExecutor 异常: task_id={subtask.task_id}, error={e}")
        latency_ms = int((time.time() - start) * 1000)
        error_result = AgentResult(
            agent_name=subtask.task_type.value,
            success=False,
            confidence=0.0,
            output={
                "answer": f"子任务执行异常: {e}",
                "coverage": "none",
                "stage": "error",
            },
            sources=[],
            error=str(e),
            latency_ms=latency_ms,
        )
        return AgentState(agent_results=[error_result])




def _get_agent(task_type: TaskType, user_input: UserInput):
    """获取子 Agent 单例(按 task_type + dept + role + user_id 缓存,避免串用户身份)"""
    role = user_input.role
    dept = user_input.department or "shared_company"
    cache_key = (task_type.value, dept, role, user_input.user_id)

    if cache_key in _agent_cache:
        return _agent_cache[cache_key]

    if task_type == TaskType.KNOWLEDGE:
        from app.agents.knowledge import KnowledgeAgent

        agent = KnowledgeAgent(user_role=role, user_dept=dept)
    elif task_type == TaskType.ANALYSIS:
        agent = AnalysisAgent(user_role=role, user_dept=dept)
    elif task_type in (TaskType.EXECUTION, TaskType.APPROVAL):
        # ExecutionAgent 需要用户身份与会话信息(审批建单/审计用)
        agent = ExecutionAgent(
            user_role=role,
            user_dept=dept,
            user_id=user_input.user_id,
            conversation_id=user_input.conversation_id,
            jwt_token=user_input.jwt_token,
        )
    else:
        # 兜底:Knowledge
        from app.agents.knowledge import KnowledgeAgent

        agent = KnowledgeAgent(user_role=role, user_dept=dept)

    _agent_cache[cache_key] = agent
    return agent


def clear_agent_cache():
    """清理 Agent 缓存(测试用)"""
    _agent_cache.clear()
