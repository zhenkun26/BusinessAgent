"""AgentState:LangGraph 全局状态定义(对应 v3 方案 6.3 节)

设计原则:
- 单一状态对象贯穿整个图执行
- 使用 TypedDict + reducer(annotated)处理并行写入
- 子 Agent 结果用 list + 可重置 reducer 累加(Send 并行 fan-out,新轮对话重置)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.agents.knowledge import AgentResult, RetrievalSource
from app.security.rbac import AgentRole


class Intent(str, Enum):
    """用户意图分类(Planner 输出)"""

    KNOWLEDGE_QA = "knowledge_qa"  # 知识问答(单 Agent)
    MULTI_TASK = "multi_task"  # 多任务(需分解 + 并行)
    APPROVAL_FLOW = "approval_flow"  # 审批流(需人机协同)
    DATA_OPERATION = "data_operation"  # 数据操作(需 RBAC 校验)
    DATA_ANALYSIS = "data_analysis"  # 数据分析(统计、趋势、对比、排名)
    CHITCHAT = "chitchat"  # 闲聊(直接回复)


class TaskType(str, Enum):
    """子任务类型(任务分解后)"""

    KNOWLEDGE = "knowledge"  # 知识检索
    ANALYSIS = "analysis"  # 数据分析
    EXECUTION = "execution"  # 工具执行(发邮件/创建任务等)
    APPROVAL = "approval"  # 审批


def _resettable_add(left: Optional[list], right: Optional[list]) -> list:
    """agent_results reducer:支持每轮对话重置 + Send 并行累加

    - right 为空列表(初始状态):返回 right,即重置(避免断点恢复后
      上一轮的结果残留并混入新一轮汇总)
    - right 非空(executor 并行写入):left + right 累加
    """
    if not right:
        return []
    return (left or []) + right


class SubTask(BaseModel):
    """Planner 分解出的子任务"""

    task_id: str = Field(description="唯一任务 ID,如 t1/t2")
    task_type: TaskType
    description: str = Field(description="子任务描述(传给子 Agent 的 query)")
    priority: int = Field(default=0, ge=0, le=10, description="优先级,0 最低")
    depends_on: list[str] = Field(default_factory=list, description="依赖的前置任务 ID")


class UserInput(BaseModel):
    """用户输入(请求入口)"""

    message: str
    user_id: str
    username: str
    role: AgentRole
    department: Optional[str] = None
    jwt_token: str = ""
    conversation_id: str = Field(description="会话 ID,用于多轮")
    request_id: str = Field(description="请求 ID,用于追踪")


class AgentState(TypedDict, total=False):
    """LangGraph 全局状态

    使用 TypedDict 而非 Pydantic,因为 LangGraph 原生支持 TypedDict + reducer。
    total=False 表示所有字段可选(图执行中逐步填充)。
    """

    # ===== 输入区(入口节点填充) =====
    user_input: UserInput
    request_id: str
    # 多轮对话历史(run_graph 入口从 checkpointer 加载,注入 planner/knowledge)
    # 结构: [{"user": ..., "assistant": ...}, ...] 按时间正序,最多 5 轮
    history: list[dict]

    # ===== Planner 区 =====
    intent: Intent
    subtasks: list[SubTask]
    plan_reasoning: str  # Planner 的推理过程(可观测)

    # ===== 子 Agent 执行区(Send fan-out 并行写入) =====
    # reducer: 每轮初始状态传入 [] 时重置;executor 并行写入时累加
    agent_results: Annotated[list[AgentResult], _resettable_add]
    # 当前正在执行的子任务(供 dispatcher 节点读取)
    current_subtask: SubTask

    # ===== 审批区(W6+ 启用,interrupt 场景) =====
    approval_required: bool
    approval_status: Optional[str]  # pending / approved / rejected
    approval_action: Optional[str]  # 审批动作描述

    # ===== Aggregator 区 =====
    final_answer: str
    sources: list[RetrievalSource]
    confidence: float
    needs_replan: bool
    replan_reason: Optional[str]

    # ===== 异常区 =====
    error: Optional[str]
    fallback_triggered: bool

    # ===== 元数据 =====
    started_at: datetime
    finished_at: datetime
    total_latency_ms: int
    tokens_used: int


def make_initial_state(user_input: UserInput) -> AgentState:
    """构造初始状态(入口节点用)"""
    now = datetime.now()
    return AgentState(
        user_input=user_input,
        request_id=user_input.request_id,
        agent_results=[],
        approval_required=False,
        approval_status=None,
        needs_replan=False,
        fallback_triggered=False,
        started_at=now,
        tokens_used=0,
    )
