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

import json
import re
import time
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.graph.state import AgentState, Intent, SubTask, TaskType, UserInput
from app.rag.llm import get_cloud_lite_llm, get_lite_llm, get_local_llm, get_primary_llm


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
    """Planner 节点:意图分类 + 任务分解

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
    history = state.get("history") or []

    logger.info(f"Planner 开始: user={user_input.username}, message={message[:80]!r}")

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
        # 多轮上下文:有历史时拼进 message 槽(不改模板,兼容 prompt_versions 已激活版本)
        # 让"那它的折扣呢"这类指代型追问能被正确分类
        classify_message = message
        if history:
            from app.graph.history import format_history_block

            classify_message = (
                f"{format_history_block(history)}\n\n当前消息: {message}"
            )
        prompt = tpl.format(message=classify_message)

        parsed: Optional[dict] = None
        lite = None
        try:
            lite = get_lite_llm()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"轻量 LLM 初始化失败: {e}")
            reasoning = f"意图分类 LLM 降级: {e}"
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
        subtasks = _decompose_tasks(message)
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
    logger.info(
        f"Planner 完成: intent={intent.value}, subtasks={len(subtasks)}, "
        f"latency={latency_ms}ms, reasoning={reasoning[:80]}"
    )

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
    # 超短消息(<=4 字符)且无业务关键词,直接判为闲聊(免调 LLM)
    if len(message.strip()) <= 4 and not any(
        kw in message for kw in ["政策", "流程", "查询", "创建", "审批", "折扣", "佣金"]
    ):
        return True

    try:
        llm = get_local_llm()
        tpl, pv = get_prompt("planner_chitchat_detect")
        logger.debug(f"prompt=planner_chitchat_detect v{pv}")
        prompt = tpl.format(message=message)
        # num_predict 硬截断:只需"是/否"一个字,防 qwen3.5 reasoning=False 后仍啰嗦
        # (ChatOllama 用 model_copy 改 num_predict;非 Ollama 模型回退 max_tokens)
        from langchain_ollama import ChatOllama

        if isinstance(llm, ChatOllama):
            llm = llm.model_copy(update={"num_predict": 5})
        else:
            llm = llm.bind(max_tokens=5)
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = resp.content if hasattr(resp, "content") else str(resp)
        text = text.strip()
        logger.debug(f"本地闲聊判断响应: {text[:50]}")
        # 判断是否以"是"开头
        return text.startswith("是") or text.lower().startswith("yes")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"本地闲聊判断失败,降级为非闲聊: {e}")
        return False


def _decompose_tasks(message: str) -> list[SubTask]:
    """任务分解(用 primary 大模型)

    多任务场景下,调用大模型拆分独立子任务。
    大模型失败时降级为单一 knowledge 兜底。
    """
    try:
        llm = get_primary_llm()
        tpl, pv = get_prompt("planner_task_decompose")
        logger.debug(f"prompt=planner_task_decompose v{pv}")
        prompt = tpl.format(message=message)
        resp = llm.invoke([HumanMessage(content=prompt)])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        logger.debug(f"任务分解 LLM 响应: {raw[:300]}")

        parsed = _parse_llm_json(raw)
        if parsed:
            raw_subtasks = parsed.get("subtasks", [])
            subtasks = _dedup_subtasks(_build_subtasks_from_llm(raw_subtasks))
            if subtasks:
                logger.info(f"任务分解成功: {len(subtasks)} 个子任务")
                return subtasks
            logger.warning("任务分解返回空 subtasks,降级为单一 knowledge")
        else:
            logger.warning("任务分解 JSON 解析失败,降级为单一 knowledge")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"任务分解 LLM 失败,降级为单一 knowledge: {e}")

    # 降级:作为单一 knowledge 任务
    return [
        SubTask(
            task_id="t1",
            task_type=TaskType.KNOWLEDGE,
            description=message,
            priority=10,
        )
    ]


def _invoke_classify(llm, prompt: str, tag: str) -> Optional[dict]:
    """调用指定 LLM 做意图分类并解析 JSON;失败返回 None(由调用方决定降级路径)"""
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        logger.debug(f"Planner 意图分类 {tag} 响应: {raw[:300]}")
        return _parse_llm_json(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Planner 意图分类 {tag} 调用失败: {e}")
        return None


def _parse_llm_json(raw: str) -> Optional[dict]:
    """从 LLM 响应中解析 JSON(容错:剥离 markdown 代码块、提取首个 JSON 对象)"""
    if not raw:
        return None

    # 剥离 markdown 代码块
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # 直接尝试解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 提取首个 {...} 块
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _safe_intent(s: str) -> Optional[Intent]:
    """字符串安全转 Intent"""
    s = (s or "").strip().lower()
    for member in Intent:
        if member.value == s:
            return member
    return None


def _build_subtasks_from_llm(raw_subtasks: list[dict]) -> list[SubTask]:
    """从 LLM 输出构造 SubTask 列表"""
    out: list[SubTask] = []
    for i, item in enumerate(raw_subtasks, start=1):
        if not isinstance(item, dict):
            continue
        type_str = (item.get("type") or "").strip().lower()
        desc = (item.get("desc") or item.get("description") or "").strip()
        if not desc:
            continue
        task_type = _safe_task_type(type_str) or TaskType.KNOWLEDGE
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
                logger.info(
                    f"子任务去重: 合并重叠子任务 '{st.description[:30]}' → "
                    f"'{kept[i].description[:30]}'"
                )
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
