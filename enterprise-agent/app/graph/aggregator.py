"""Aggregator 节点：汇总子 Agent 结果(对应 v3 方案 6.3 节 aggregator_node)

输入：AgentState.agent_results(并行执行后的结果列表)
输出：AgentState.final_answer + sources + confidence + needs_replan

策略:
1. 单 Agent 结果：直接采用(不调 LLM)
2. 多 Agent 结果：知识结果保留引用，其余结果按结构化状态确定性组合
3. 失败结果：标记并降低综合置信度
4. needs_replan 传播：任一子 Agent 标记重规划，则整体重规划

闲聊的模型兜底保持独立；结果汇总不调用模型。
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from loguru import logger

from app.agents.knowledge import AgentResult, RetrievalSource
from app.graph.state import AgentState, Intent
from app.observability.token_usage import snapshot_total_tokens
from app.rag.llm import get_lite_llm


async def aggregator_node(state: AgentState) -> AgentState:
    """Bind the answer to its request so inherited snapshots cannot invent turns."""
    result = await _aggregate(state)
    result["answer_request_id"] = (
        state["user_input"].request_id if result.get("final_answer")
        and not result.get("needs_replan") else None
    )
    return result


async def _aggregate(state: AgentState) -> AgentState:
    """Compose results before the existing final-answer publication boundary."""
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
        if r.success and r.agent_name == 'knowledge':
            from app.security.rag_boundary import validate_answer
            validate_answer(final_answer, len(r.sources))
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
            replan_hint=r.replan_hint,
            # I-07:token 统一口径——读请求级累加器(含 planner + agent 全部 LLM 调用)
            tokens_used=snapshot_total_tokens(),
            error=r.error,
            finished_at=datetime.now(),
            total_latency_ms=latency_ms,
        )

    # 4. Multi-result composition never calls a summary model.
    success_results = [r for r in results if r.success]
    has_knowledge = any(r.agent_name == 'knowledge' for r in results)
    if has_knowledge and not success_results:
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

    if has_knowledge:
        from app.security.rag_boundary import compose_knowledge
        final_answer = compose_knowledge(results)
    else:
        from app.security.result_boundary import compose_nonknowledge
        # Validate original checkpoint fields as well: model normalization must not
        # turn malformed success/status data into authoritative completion evidence.
        final_answer = compose_nonknowledge(state['agent_results'])

    # 合并 sources
    all_sources: list[RetrievalSource] = []
    seen_chunk_ids: set[tuple[str, str]] = set()
    for r in success_results:
        for s in r.sources:
            if (s.document_id, s.chunk_id) not in seen_chunk_ids:
                all_sources.append(s)
                seen_chunk_ids.add((s.document_id, s.chunk_id))

    # 综合置信度:成功 Agent 的加权平均(按 confidence 降序加权)
    sorted_succ = sorted(success_results, key=lambda x: x.confidence, reverse=True)
    weights = [1.0 / (i + 1) for i in range(len(sorted_succ))]  # 靠前权重高
    total_w = sum(weights)
    combined_conf = (sum(r.confidence * w for r, w in zip(sorted_succ, weights)) / total_w
                     if total_w else 0.0)

    # needs_replan:任一标记则传播
    needs_replan = bool(success_results) and any(r.needs_replan for r in results)
    replan_reason = next(
        (r.replan_reason for r in results if r.needs_replan), None
    ) if needs_replan else None
    replan_hint = next(
        (r.replan_hint for r in results if r.needs_replan and r.replan_hint), None
    ) if needs_replan else None

    # tokens 汇总(I-07):统一读请求级累加器,覆盖 planner/全部 agent/汇总 LLM 调用
    total_tokens = snapshot_total_tokens()

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
        error='all_agents_failed' if not success_results else None,
        replan_reason=replan_reason,
        replan_hint=replan_hint,
        tokens_used=total_tokens,
        finished_at=datetime.now(),
        total_latency_ms=latency_ms,
    )


async def _chitchat_reply(message: str, username: str = "") -> str:
    """闲聊场景的人格化回复(智多星 话术,按意图/情绪分支;未命中分支用 lite LLM 生成)"""
    from app.security.chitchat_boundary import message_data
    message_data(message)
    # Username is retained in the call signature, never interpolated or sent to a model.
    msg = message.strip().lower()
    if any(kw in msg for kw in ["你是谁", "介绍一下", "who are you", "什么助手"]):
        return (
            "我是智多星，你的企业知识工作流智能助手～查政策制度、查客户订单、"
            "建跟进任务、发邮件、做数据分析都可以交给我。"
        )
    if any(kw in msg for kw in ["心情", "你好吗", "你还好", "过得怎", "状态怎", "最近怎"]):
        return (
            "我心情很好呀，随时待命状态满格～你呢？"
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
            "再忙也要记得按时吃饭，工作上的事多交给我。"
        )
    if any(kw in msg for kw in ["累", "心情", "烦", "压力", "焦虑", "难过", "emo", "不开心"]):
        return (
            "辛苦了，先喝口水缓一缓～工作上的杂事尽管交给我："
            "查资料、跑数据、发邮件我都在，需要做什么随时说。"
        )
    if any(kw in msg for kw in ["你好", "hi", "hello", "您好", "在吗", "在么"]):
        return (
            "你好！我是智多星～查公司政策、客户订单、建跟进任务、"
            "发邮件都可以找我，有什么要帮忙的？"
        )
    if any(kw in msg for kw in ["谢谢", "感谢", "thanks"]):
        return "不客气～还有其他事随时叫我。"
    if any(kw in msg for kw in ["再见", "bye", "拜拜", "下班"]):
        return "好的，回见！有需要随时找智多星。"
    # Unmatched messages use one read-only attempt through the configured lite model.
    generated = await _chitchat_llm_generate(message)
    if generated:
        return generated
    from app.security.chitchat_boundary import FALLBACK
    return FALLBACK


async def _chitchat_llm_generate(message: str) -> str:
    """One read-only attempt; invalid/provider responses use the caller's fixed fallback."""
    from app.core.execution_budget import ExecutionBudgetExceeded, check_execution_budget
    from app.security.chitchat_boundary import model_config, model_messages, render_response

    try:
        messages = model_messages(message)
        llm = get_lite_llm()
        check_execution_budget()
        response = await llm.ainvoke(messages, config=model_config())
        answer = render_response(response)
        logger.info("AGGREGATOR_CHITCHAT_COMPLETED")
        return answer
    except ExecutionBudgetExceeded:
        raise
    except Exception:  # No provider/response content in diagnostics or fallback.
        check_execution_budget()
        logger.warning("AGGREGATOR_CHITCHAT_FAILED")
        return ""
