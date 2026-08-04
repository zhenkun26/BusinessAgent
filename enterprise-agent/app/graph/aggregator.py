"""Aggregator 节点：汇总子 Agent 结果(对应 v3 方案 6.3 节 aggregator_node)

输入：AgentState.agent_results(并行执行后的结果列表)
输出：AgentState.final_answer + sources + confidence + needs_replan

策略(大模型 + 小模型分层):
1. 单 Agent 结果：直接采用(不调 LLM)
2. 多 Agent 结果：用 primary 大模型汇总(需要理解 + 整合能力)
3. 失败结果：标记并降低综合置信度
4. needs_replan 传播：任一子 Agent 标记重规划，则整体重规划

模型分层理由：
- 单结果无需 LLM(直接采用，节省成本)
- 多结果汇总需要理解各 Agent 回答 + 整合，用大模型保证质量
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage
from loguru import logger

from app.agents.knowledge import AgentResult, RetrievalSource
from app.graph.state import AgentState, Intent
from app.rag.llm import get_lite_llm, get_primary_llm


# 多结果汇总 Prompt 从注册表获取(P2-1:版本管理/A/B;默认值见 app/prompts/defaults.py)
from app.prompts import get_prompt


async def aggregator_node(state: AgentState) -> AgentState:
    """Aggregator 节点：汇总子 Agent 结果(async:支持汇总 LLM 的 token 流式)"""
    start = time.time()
    # 断点恢复后,checkpoint 反序列化可能把 AgentResult 变成 dict,统一转回模型
    results: list[AgentResult] = [
        AgentResult.model_validate(r) if isinstance(r, dict) else r
        for r in state.get("agent_results", [])
    ]
    intent: Intent = state.get("intent", Intent.KNOWLEDGE_QA)
    user_input = state["user_input"]

    logger.info(f"Aggregator 开始： intent={intent.value}, results={len(results)}")

    # 1. 闲聊场景:人格化话术(命中分支用模板,未命中用 lite LLM 生成)
    if intent == Intent.CHITCHAT:
        final_answer = await _chitchat_reply(user_input.message, user_input.username)
        latency_ms = int((time.time() - start) * 1000)
        return AgentState(
            final_answer=final_answer,
            sources=[],
            confidence=0.9,
            needs_replan=False,
            finished_at=datetime.now(),
            total_latency_ms=latency_ms,
        )

    # 2. 无结果:返回失败回复
    if not results:
        latency_ms = int((time.time() - start) * 1000)
        return AgentState(
            final_answer="抱歉，我暂时无法处理您的请求。请稍后重试或重新描述问题。",
            sources=[],
            confidence=0.0,
            needs_replan=False,
            error="no_agent_results",
            finished_at=datetime.now(),
            total_latency_ms=latency_ms,
        )

    # 3. 单 Agent:直接采用
    if len(results) == 1:
        r = results[0]
        final_answer = r.output.get("answer", "")
        if not r.success and not final_answer:
            # Agent 未给出可读回答时,才用错误信息兜底(避免掩盖 RBAC 拒绝等友好提示)
            final_answer = f"处理失败： {r.error or '未知错误'}"
        latency_ms = int((time.time() - start) * 1000)
        logger.info(
            f"Aggregator 单 Agent: success={r.success}, confidence={r.confidence:.3f}, "
            f"latency={latency_ms}ms"
        )
        return AgentState(
            final_answer=final_answer,
            sources=r.sources,
            confidence=r.confidence,
            needs_replan=r.needs_replan,
            replan_reason=r.replan_reason,
            tokens_used=r.tokens_used,
            error=r.error,
            finished_at=datetime.now(),
            total_latency_ms=latency_ms,
        )

    # 4. 多 Agent:LLM 汇总
    success_results = [r for r in results if r.success]
    if not success_results:
        # 全部失败,返回第一个的错误
        first_err = results[0].error or "所有子 Agent 执行失败"
        latency_ms = int((time.time() - start) * 1000)
        return AgentState(
            final_answer=f"处理失败： {first_err}",
            sources=[],
            confidence=0.0,
            needs_replan=False,
            error="all_agents_failed",
            finished_at=datetime.now(),
            total_latency_ms=latency_ms,
        )

    # 构造汇总输入
    agent_answers = _format_agent_answers(results)
    final_answer = await _llm_aggregate(user_input.message, agent_answers)

    # 合并 sources
    all_sources: list[RetrievalSource] = []
    seen_chunk_ids: set[str] = set()
    for r in success_results:
        for s in r.sources:
            if s.chunk_id not in seen_chunk_ids:
                all_sources.append(s)
                seen_chunk_ids.add(s.chunk_id)

    # 综合置信度:成功 Agent 的加权平均(按 confidence 降序加权)
    sorted_succ = sorted(success_results, key=lambda x: x.confidence, reverse=True)
    weights = [1.0 / (i + 1) for i in range(len(sorted_succ))]  # 靠前权重高
    total_w = sum(weights)
    combined_conf = sum(r.confidence * w for r, w in zip(sorted_succ, weights)) / total_w

    # needs_replan:任一标记则传播
    needs_replan = any(r.needs_replan for r in results)
    replan_reason = next(
        (r.replan_reason for r in results if r.needs_replan), None
    )

    # tokens 汇总
    total_tokens = sum(r.tokens_used for r in results)

    latency_ms = int((time.time() - start) * 1000)
    logger.info(
        f"Aggregator 多 Agent: results={len(results)}, success={len(success_results)}, "
        f"confidence={combined_conf:.3f}, needs_replan={needs_replan}, "
        f"sources={len(all_sources)}, latency={latency_ms}ms"
    )

    return AgentState(
        final_answer=final_answer,
        sources=all_sources,
        confidence=combined_conf,
        needs_replan=needs_replan,
        replan_reason=replan_reason,
        tokens_used=total_tokens,
        finished_at=datetime.now(),
        total_latency_ms=latency_ms,
    )


def _format_agent_answers(results: list[AgentResult]) -> str:
    """格式化各 Agent 回答供 LLM 汇总"""
    parts = []
    for i, r in enumerate(results, start=1):
        status = "成功" if r.success else f"失败({r.error})"
        answer = r.output.get("answer", "") if r.success else ""
        parts.append(f"[Agent{i} - {r.agent_name} - {status}]\n{answer}")
    return "\n\n".join(parts)


async def _llm_aggregate(question: str, agent_answers: str) -> str:
    """调用 primary 大模型汇总多个 Agent 回答

    多 Agent 结果合并需要理解各回答 + 逻辑整合，用大模型保证质量。
    大模型失败时降级为直接拼接(保证可用)。
    async + final_answer 标签：支持 token 级流式输出。
    """
    try:
        llm = get_primary_llm()
        tpl, pv = get_prompt("aggregator_aggregate")
        logger.debug(f"prompt=aggregator_aggregate v{pv}")
        prompt = tpl.format(question=question, agent_answers=agent_answers)
        resp = await llm.ainvoke(
            [HumanMessage(content=prompt)],
            config={"tags": ["final_answer"]},  # 流式输出标记
        )
        text = resp.content if hasattr(resp, "content") else str(resp)
        return text.strip()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Aggregator 大模型汇总失败，降级拼接： {e}")
        # 降级:直接拼接各 Agent 回答
        return agent_answers


async def _chitchat_reply(message: str, username: str = "") -> str:
    """闲聊场景的人格化回复(小A 话术,按意图/情绪分支;未命中分支用 lite LLM 生成)"""
    msg = message.strip().lower()
    name = username or "同事"
    if any(kw in msg for kw in ["你是谁", "介绍一下", "who are you", "什么助手"]):
        return (
            "我是小A，你的企业知识工作流智能助手～查政策制度、查客户订单、"
            "建跟进任务、发邮件、做数据分析都可以交给我。"
        )
    if any(kw in msg for kw in ["心情", "你好吗", "你还好", "过得怎", "状态怎", "最近怎"]):
        return (
            f"我心情很好呀，随时待命状态满格～{name}，你呢？"
            "要是有什么杂事，尽管丢给我。"
        )
    if any(kw in msg for kw in ["你会什么", "能做什么", "会哪些", "有什么功能", "会干嘛", "能干嘛"]):
        return (
            "我会的还挺多～查公司政策制度、查客户和订单、建跟进任务、"
            "发内外部邮件、做销售数据分析。直接说要做什么就行。"
        )
    if any(kw in msg for kw in ["吃了吗", "吃饭", "周末", "放假", "加班"]):
        return (
            "我是 AI，不用吃饭充电，全天候在线～"
            f"{name}再忙也要记得按时吃饭，工作上的事多交给我。"
        )
    if any(kw in msg for kw in ["累", "心情", "烦", "压力", "焦虑", "难过", "emo", "不开心"]):
        return (
            "辛苦了，先喝口水缓一缓～工作上的杂事尽管交给我："
            "查资料、跑数据、发邮件我都在，需要做什么随时说。"
        )
    if any(kw in msg for kw in ["你好", "hi", "hello", "您好", "在吗", "在么"]):
        return (
            f"你好，{name}！我是小A～查公司政策、客户订单、建跟进任务、"
            "发邮件都可以找我，有什么要帮忙的？"
        )
    if any(kw in msg for kw in ["谢谢", "感谢", "thanks"]):
        return "不客气～还有其他事随时叫我。"
    if any(kw in msg for kw in ["再见", "bye", "拜拜", "下班"]):
        return "好的，回见！有需要随时找小A。"
    # 未命中分支:用 lite LLM(本地 qwen)按小A 人格即兴生成
    generated = await _chitchat_llm_generate(message, name)
    if generated:
        return generated
    return (
        "我在～我是小A，可以帮你查政策、查客户订单、建任务、发邮件、做分析。"
        "直接说要做什么就行，比如「查一下客户 C001」。"
    )


async def _chitchat_llm_generate(message: str, name: str) -> str:
    """闲聊兜底:lite LLM 按小A 人格生成回复;失败返回空串(调用方走固定模板)"""
    prompt = (
        "你是小A，企业员工的工作搭子(企业知识工作流智能助手)，性格亲切、干练。"
        f"现在员工{name}在和你闲聊。\n"
        "要求:\n"
        "1. 像同事一样自然回应，口语化，1-2 句话，不超过 60 字\n"
        "2. 自称小A，可自然带出对方称呼\n"
        "3. 中文标点一律用全角\n"
        "4. 结尾可顺势引导到工作上(查政策、查客户订单、建任务、发邮件)，但不要生硬\n\n"
        f"员工说:{message}\n"
        "你的回复(直接输出回复内容，不要解释):"
    )
    try:
        llm = get_lite_llm()
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        text = (resp.content or "").strip()
        # 去掉可能的引号包裹
        text = text.strip('"“”')
        if text and len(text) <= 120:
            logger.info(f"闲聊 LLM 生成成功: {text[:40]}")
            return text
        logger.warning(f"闲聊 LLM 输出不可用(长度 {len(text)}),走固定模板")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"闲聊 LLM 生成失败,走固定模板: {e}")
    return ""
