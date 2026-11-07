"""Planner 节点:意图分类 + 任务分解(对应 v3 方案 6.3 节 planner_node)

输入:AgentState.user_input
输出:AgentState.intent + AgentState.subtasks

策略(三层模型分层):
1. [local 本地小模型] 闲聊快速判断:先用本地 qwen3.5:4b 判断是否闲聊
   - 是闲聊:直接返回,不走云端(节省成本)
   - 非闲聊:继续走云端分类
2. [lite 云端轻量] 意图分类:用 DeepSeek v4-flash 做 5 类分类(JSON)
3. [primary 云端大模型] 任务分解:多任务场景用 v4-pro 拆分子任务(需要推理)
4. LLM 失败时降级规则匹配(关键词触发)

模型分层理由:
- 闲聊判断最简单(是/否),用本地小模型免费且低延迟
- 意图分类(5类选1)用云端轻量模型,准确且成本低
- 任务分解需要推理能力,用大模型保证质量
"""

from __future__ import annotations

import re
import time
from typing import Optional

from loguru import logger

from app.core.execution_budget import ExecutionBudgetExceeded
from app.graph.state import AgentState, Intent, SubTask, TaskType, UserInput
from app.graph.plan_policy import PlanRejected, check_dependencies, check_plan
from app.rag.llm import get_cloud_lite_llm, get_lite_llm, get_local_llm, get_primary_llm
from app.security.planning_boundary import (
    PlanningBoundaryError, PlanningPrompt, action_excerpt, build_prompt, json_value,
    model_text, request_data, text,
)


# Prompt 统一从注册表获取(P2-1:版本管理/A/B;代码默认值见 app/prompts/defaults.py)
from app.prompts import get_prompt

# 规则降级:关键词触发(LLM 不可用时)
RULE_KEYWORDS = {
    Intent.APPROVAL_FLOW: ["审批", "申请", "提单", "走流程", "打报告"],
    Intent.DATA_OPERATION: [
        "创建", "新建", "更新", "发送邮件", "发邮件", "建任务", "录入",
        # 具体业务记录查询(与 LLM 分类 prompt 的 data_operation 定义对齐)
        "查询订单", "订单详情", "ord-", "查一下订单", "工单", "查客户", "查一下客户",
    ],
    Intent.MULTI_TASK: ["并且", "另外", "同时", "还有", "以及"],
    Intent.DATA_ANALYSIS: ["统计", "趋势", "对比", "分析", "排名"],
    Intent.KNOWLEDGE_QA: ["什么是", "怎么", "如何", "政策", "流程", "规定", "制度", "请问"],
}


def planner_node(state: AgentState) -> AgentState:
    """Reject invalid proposals before the graph can dispatch any agent."""
    try:
        return _plan(state)
    except PlanRejected as exc:
        return AgentState(subtasks=[], plan_error=str(exc))


def _plan(state: AgentState) -> AgentState:
    """Planner 节点:意图分类 + 任务分解

    重规划模式:当 state 携带 replan_reason(来自 aggregator 的 needs_replan)时,
    不再做闲聊/意图分类/任务分解,直接针对知识子任务重新规划——
    用重规划提示(replan_hint.query)或原消息重建检索目标,并把本轮原因记入
    replan_history,供重规划轮次护栏与审计追溯。

    流程(三层模型分层):
    1. [local 本地小模型] 闲聊快速判断(是闲聊直接返回,节省云端调用)
    2. [lite 云端轻量] 意图分类(非闲聊场景,5 类选 1)
    3. [primary 云端大模型] 任务分解(多任务场景)
    4. LLM 失败时降级规则匹配
    """
    start = time.time()
    user_input: UserInput = state["user_input"]
    message = user_input.message
    # 多轮对话历史(run_graph 入口注入;无历史为 [])
    history = state.get("history")
    data = request_data(message, history)

    logger.info("PLANNER_STARTED")

    # ===== 重规划模式(agent-replan):跳过分类直接重建知识子任务 =====
    # 状态更新也在此完成(轮次递增/历史追加/agent_results 重置)——
    # langgraph 1.2 条件边不支持携带 updates,故集中在重规划分支落地
    replan_reason = state.get("replan_reason")
    if replan_reason:
        replan_hint = state.get("replan_hint")
        if replan_hint is None:
            replan_hint = {}
        if type(replan_hint) is not dict or set(replan_hint) - {'query', 'stage'}:
            raise PlanningBoundaryError()
        replan_query = replan_hint.get('query', message)
        if replan_query is None or replan_query == '':
            replan_query = message
        text(replan_query)
        text(replan_reason)
        if 'stage' in replan_hint:
            text(replan_hint['stage'])
        subtasks = [
            SubTask(
                task_id="t1",
                task_type=TaskType.KNOWLEDGE,
                description=replan_query,
                priority=10,
            )
        ]
        replan_count = state.get("replan_count", 0) + 1
        replan_history = list(state.get("replan_history") or [])
        replan_history.append(replan_reason)
        logger.info(f"PLANNER_REPLAN round={replan_count}")
        return AgentState(
            intent=Intent.KNOWLEDGE_QA,
            subtasks=subtasks,
            plan_reasoning=f"重规划第 {replan_count} 轮: {replan_reason}",
            replan_count=replan_count,
            replan_history=replan_history,
            # 空列表触发 _resettable_add 重置,防止上一轮结果混入新一轮
            agent_results=[],
        )

    intent: Optional[Intent] = None
    subtasks: list[SubTask] = []
    reasoning = ""

    # 1. 闲聊快速判断(用本地小模型,免费低延迟)
    is_chitchat = _quick_chitchat_check(message)
    if is_chitchat:
        intent = Intent.CHITCHAT
        reasoning = "本地小模型判定:闲聊"
        logger.info(f"Planner 本地快速判定:闲聊(跳过云端分类)")
    else:
        # 2. 意图分类(lite 本地优先;失败或输出不可用 → 云端 flash 补一枪 → 规则兜底)
        tpl, pv = get_prompt("planner_intent_classify")
        logger.debug(f"prompt=planner_intent_classify v{pv}")
        prompt = build_prompt(tpl, pv, data)

        parsed: Optional[dict] = None
        lite = None
        try:
            lite = get_lite_llm()
        except ExecutionBudgetExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            from app.core.execution_budget import check_execution_budget
            check_execution_budget()
            logger.warning("PLANNER_LITE_INIT_FAILED")
            reasoning = "INTENT_MODEL_UNAVAILABLE"
        if lite is not None:
            parsed = _invoke_classify(lite, prompt, "lite")

        if not parsed or not _safe_intent(parsed.get("intent", "")):
            # 本地小模型失败或输出不可用(4B 能力边界):云端 flash(deepseek-v4-flash)补一枪
            cloud = get_cloud_lite_llm()
            if cloud is not None and cloud is not lite:
                logger.info("意图分类本地结果不可用,云端 flash 重试")
                cloud_parsed = _invoke_classify(cloud, prompt, "cloud_flash")
                if cloud_parsed and _safe_intent(cloud_parsed.get("intent", "")):
                    parsed = cloud_parsed

        if parsed:
            intent = _safe_intent(parsed.get("intent", ""))
            reasoning = parsed.get("reasoning", "")

        # 规则降级
        if intent is None:
            intent = _rule_classify(message)
            reasoning = reasoning or f"规则匹配: {intent.value}"

    # 3. 任务分解(多任务场景用 primary 大模型)
    if intent == Intent.MULTI_TASK:
        try:
            subtasks = _decompose_tasks(message)
        except PlanRejected as exc:
            return AgentState(intent=intent, subtasks=[], plan_error=str(exc))
    elif intent == Intent.KNOWLEDGE_QA:
        subtasks = [
            SubTask(
                task_id="t1",
                task_type=TaskType.KNOWLEDGE,
                description=message,
                priority=10,
            )
        ]
    elif intent == Intent.CHITCHAT:
        subtasks = []  # 闲聊不需要子任务
    else:
        # 其他单任务场景
        task_type = _intent_to_task_type(intent)
        subtasks = [
            SubTask(
                task_id="t1",
                task_type=task_type,
                description=message,
                priority=10,
            )
        ]

    latency_ms = int((time.time() - start) * 1000)
    logger.info(f"PLANNER_COMPLETED tasks={len(subtasks)} latency_ms={latency_ms}")

    return AgentState(
        intent=intent,
        subtasks=subtasks,
        plan_reasoning=reasoning,
    )


def _quick_chitchat_check(message: str) -> bool:
    """本地小模型快速判断是否闲聊(二分类)

    用本地 qwen3.5:4b(ChatOllama+reasoning=False,实测 ~0.2s),零云端成本。
    是闲聊 → True,直接返回,跳过云端分类
    非闲聊 → False,继续走云端意图分类

    本地不可用时降级为非闲聊(继续走后续分类流程)。
    """
    text(message)
    # 超短消息(<=4 字符)且无业务关键词,直接判为闲聊(免调 LLM)
    if len(message.strip()) <= 4 and not any(
        kw in message for kw in ["政策", "流程", "查询", "创建", "审批", "折扣", "佣金"]
    ):
        return True

    try:
        tpl, pv = get_prompt("planner_chitchat_detect")
        logger.debug(f"prompt=planner_chitchat_detect v{pv}")
        prompt = build_prompt(tpl, pv, request_data(message))
        llm = get_local_llm()
        # num_predict 硬截断:只需"是/否"一个字,防 qwen3.5 reasoning=False 后仍啰嗦
        # (ChatOllama 用 model_copy 改 num_predict;非 Ollama 模型回退 max_tokens)
        from langchain_ollama import ChatOllama

        if isinstance(llm, ChatOllama):
            llm = llm.model_copy(update={"num_predict": 5})
        else:
            llm = llm.bind(max_tokens=5)
        resp = llm.invoke(prompt.messages(), config=prompt.config())
        answer = model_text(resp).strip().lower()
        if answer not in {'是', '否', 'yes', 'no'}:
            raise PlanningBoundaryError()
        logger.debug("PLANNER_CHITCHAT_RESPONSE_RECEIVED")
        # 判断是否以"是"开头
        return answer in {'是', 'yes'}
    except (PlanRejected, ExecutionBudgetExceeded):
        raise
    except Exception as e:  # noqa: BLE001
        from app.core.execution_budget import check_execution_budget
        check_execution_budget()
        logger.warning("PLANNER_CHITCHAT_FAILED")
        return False


def _decompose_tasks(message: str) -> list[SubTask]:
    """任务分解(用 primary 大模型)

    多任务场景下,调用大模型拆分独立子任务。
    大模型失败时降级为单一 knowledge 兜底。
    """
    try:
        tpl, pv = get_prompt("planner_task_decompose")
        logger.debug(f"prompt=planner_task_decompose v{pv}")
        prompt = build_prompt(tpl, pv, request_data(message))
        llm = get_primary_llm()
        resp = llm.invoke(prompt.messages(), config=prompt.config())
        raw = model_text(resp)
        logger.debug("PLANNER_DECOMPOSITION_RESPONSE_RECEIVED")

        parsed = _parse_llm_json(raw)
        if set(parsed) != {'subtasks'}:
            raise PlanningBoundaryError()
        subtasks = _build_subtasks_from_llm(parsed['subtasks'])
        for task in subtasks:
            if task.task_type in (TaskType.EXECUTION, TaskType.APPROVAL):
                action_excerpt(task.description, message)
        subtasks = _dedup_subtasks(subtasks)
        if subtasks:
            logger.info(f"PLANNER_DECOMPOSITION_COMPLETED count={len(subtasks)}")
            return subtasks
        logger.info("PLANNER_DECOMPOSITION_EMPTY")
    except (PlanRejected, ExecutionBudgetExceeded):
        raise
    except Exception as e:  # noqa: BLE001
        from app.core.execution_budget import check_execution_budget
        check_execution_budget()
        logger.warning("PLANNER_DECOMPOSITION_FAILED")

    # 降级:作为单一 knowledge 任务
    return [
        SubTask(
            task_id="t1",
            task_type=TaskType.KNOWLEDGE,
            description=message,
            priority=10,
        )
    ]


def _invoke_classify(llm, prompt: PlanningPrompt, tag: str) -> Optional[dict]:
    """调用指定 LLM 做意图分类并解析 JSON;失败返回 None(由调用方决定降级路径)"""
    try:
        resp = llm.invoke(prompt.messages(), config=prompt.config())
        raw = model_text(resp)
        logger.debug("PLANNER_CLASSIFICATION_RESPONSE_RECEIVED")
        parsed = _parse_llm_json(raw)
        if (set(parsed) - {'intent', 'reasoning', 'subtasks'}
                or _safe_intent(parsed.get('intent')) is None):
            raise PlanningBoundaryError()
        text(parsed.get('reasoning', ''), empty=True)
        _build_subtasks_from_llm(parsed.get('subtasks', []))
        return parsed
    except (PlanRejected, ExecutionBudgetExceeded):
        raise
    except Exception as e:  # noqa: BLE001
        from app.core.execution_budget import check_execution_budget
        check_execution_budget()
        logger.warning("PLANNER_CLASSIFICATION_FAILED")
        return None


def _parse_llm_json(raw: str) -> Optional[dict]:
    """A complete unambiguous object only; no prose/fence extraction."""
    parsed = json_value(raw)
    if type(parsed) is not dict:
        raise PlanningBoundaryError()
    return parsed


def _safe_intent(s: str) -> Optional[Intent]:
    """字符串安全转 Intent"""
    if type(s) is not str:
        return None
    s = s.strip().lower()
    for member in Intent:
        if member.value == s:
            return member
    return None


def _build_subtasks_from_llm(raw_subtasks: list[dict]) -> list[SubTask]:
    """从 LLM 输出构造 SubTask 列表"""
    if not isinstance(raw_subtasks, list):
        raise PlanRejected("INVALID_TASK_DEPENDENCIES")
    from app.core.execution_budget import check_task_count

    check_task_count(len(raw_subtasks))
    # Check even incomplete tasks: skipping a malformed task must not erase a dependency.
    for item in raw_subtasks:
        if isinstance(item, dict):
            check_dependencies(item.get("depends_on", []))
    out: list[SubTask] = []
    for i, item in enumerate(raw_subtasks, start=1):
        if (type(item) is not dict or set(item) - {
                'task_id', 'type', 'desc', 'description', 'depends_on'}
                or ('desc' in item and 'description' in item)):
            raise PlanningBoundaryError()
        type_str = text(item.get('type')).strip().lower()
        desc = text(item.get('desc', item.get('description'))).strip()
        if 'task_id' in item:
            text(item['task_id'])
        task_type = _safe_task_type(type_str)
        if task_type is None:
            raise PlanningBoundaryError()
        out.append(
            SubTask(
                task_id=f"t{i}",
                task_type=task_type,
                description=desc,
                priority=max(0, 10 - i + 1),  # 靠前的优先级高
            )
        )
    return out


def _extract_entities(text: str) -> set[str]:
    """从子任务描述中提取业务实体(客户/订单/任务 ID、邮箱),用于重叠检测"""
    entities = set(re.findall(r"C\d{3}", text))
    entities.update(re.findall(r"ORD-[\w-]+", text))
    entities.update(re.findall(r"CT-[\w-]+", text))
    entities.update(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text))
    return entities


# 动作动词(判定"同一类动作";查询⊂查、发送⊂发 的前缀关系不影响集合交集)
_ACTION_KEYWORDS = ["查询", "查", "创建", "建", "发送", "发", "更新", "通知", "审批", "申请"]


def _extract_actions(text: str) -> set[str]:
    """从子任务描述中提取动作动词,用于区分同实体不同动作(查 C005 vs 为 C005 建工单)"""
    return {kw for kw in _ACTION_KEYWORDS if kw in text}


def _dedup_subtasks(subtasks: list[SubTask]) -> list[SubTask]:
    """合并语义重叠的子任务(防止 multi_task 拆出重复执行分支导致双写)

    规则:task_type 相同,且一方描述包含另一方 → 合并;
    或 task_type 相同 + 业务实体有交集 + **动作动词也有交集** → 合并
    (同实体不同动作——如「查 C005」/「为 C005 建工单」/「为 C005 发邮件」——不是重复,不合并)。
    合并时保留描述更完整(更长)的一条,合并后重排 task_id 与 priority。
    """
    check_plan(subtasks)
    if len(subtasks) <= 1:
        return subtasks

    kept: list[SubTask] = []
    kept_entities: list[set[str]] = []
    kept_actions: list[set[str]] = []
    for st in subtasks:
        entities = _extract_entities(st.description)
        actions = _extract_actions(st.description)
        merged = False
        for i, prev in enumerate(kept):
            if prev.task_type != st.task_type:
                continue
            contains = st.description in prev.description or prev.description in st.description
            same_action_dup = bool(
                entities & kept_entities[i] and actions & kept_actions[i]
            )
            if contains or same_action_dup:
                # 保留描述更长(信息更全)的一条
                if len(st.description) > len(prev.description):
                    kept[i] = st
                    kept_entities[i] = entities
                    kept_actions[i] = actions
                logger.info("PLANNER_DUPLICATE_TASK_MERGED")
                merged = True
                break
        if not merged:
            kept.append(st)
            kept_entities.append(entities)
            kept_actions.append(actions)

    if len(kept) < len(subtasks):
        logger.info(f"子任务去重: {len(subtasks)} → {len(kept)}")
    # 重排 task_id 与 priority
    return [
        SubTask(
            task_id=f"t{i}",
            task_type=st.task_type,
            description=st.description,
            priority=max(0, 10 - i + 1),
            depends_on=st.depends_on,
        )
        for i, st in enumerate(kept, start=1)
    ]


def _safe_task_type(s: str) -> Optional[TaskType]:
    s = (s or "").strip().lower()
    for member in TaskType:
        if member.value == s:
            return member
    return None


def _intent_to_task_type(intent: Intent) -> TaskType:
    """单任务意图转 TaskType"""
    mapping = {
        Intent.KNOWLEDGE_QA: TaskType.KNOWLEDGE,
        Intent.DATA_OPERATION: TaskType.EXECUTION,
        Intent.DATA_ANALYSIS: TaskType.ANALYSIS,
        Intent.APPROVAL_FLOW: TaskType.APPROVAL,
        Intent.MULTI_TASK: TaskType.KNOWLEDGE,  # 兜底
        Intent.CHITCHAT: TaskType.KNOWLEDGE,
    }
    return mapping.get(intent, TaskType.KNOWLEDGE)


def _rule_classify(message: str) -> Intent:
    """规则降级:关键词匹配"""
    msg = message.lower()
    # 按优先级匹配(多任务关键词优先)
    for intent in [
        Intent.MULTI_TASK,
        Intent.APPROVAL_FLOW,
        Intent.DATA_OPERATION,
        Intent.DATA_ANALYSIS,
        Intent.KNOWLEDGE_QA,
    ]:
        keywords = RULE_KEYWORDS.get(intent, [])
        if any(kw in msg for kw in keywords):
            return intent
    # 默认闲聊
    return Intent.CHITCHAT
