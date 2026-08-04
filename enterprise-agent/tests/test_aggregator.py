"""Aggregator 汇总逻辑测试(规格 6.4:单结果直通/needs_replan 传播)"""

from __future__ import annotations

import pytest

from app.agents.knowledge import AgentResult
from app.graph.aggregator import aggregator_node
from app.graph.state import Intent, UserInput


def _make_user_input(message: str = "测试") -> UserInput:
    return UserInput(
        message=message,
        user_id="user_sales_001",
        username="销售员张三",
        role="salesperson",
        department="dept_sales",
        jwt_token="",
        conversation_id="sess_agg_test",
        request_id="req_agg_test",
    )


@pytest.mark.asyncio
async def test_should_pass_through_single_result_without_llm(monkeypatch):
    """Given 单 Agent 成功结果, When 汇总,
    Then 直接采用(不调 LLM),needs_replan 原样透传"""
    llm_called: list[bool] = []

    async def should_not_call(*args, **kwargs):
        llm_called.append(True)
        return "不应调用"

    monkeypatch.setattr("app.graph.aggregator._llm_aggregate", should_not_call)
    state = {
        "user_input": _make_user_input(),
        "intent": Intent.KNOWLEDGE_QA,
        "agent_results": [
            AgentResult(
                agent_name="knowledge",
                success=True,
                confidence=0.78,
                output={"answer": "根据销售政策…[来源1]"},
                needs_replan=False,
            )
        ],
    }

    result = await aggregator_node(state)

    assert result["final_answer"] == "根据销售政策…[来源1]"
    assert result["needs_replan"] is False
    assert llm_called == []


@pytest.mark.asyncio
async def test_should_propagate_replan_flag_from_single_result():
    """Given 知识 Agent 标记 needs_replan=true(部分覆盖),
    When 汇总,
    Then 整体 needs_replan=true 且带原因(触发图回边)"""
    state = {
        "user_input": _make_user_input(),
        "intent": Intent.KNOWLEDGE_QA,
        "agent_results": [
            AgentResult(
                agent_name="knowledge",
                success=True,
                confidence=0.52,
                output={"answer": "以下内容可能不完整…", "coverage": "partial"},
                needs_replan=True,
                replan_reason="low_confidence_partial",
                replan_hint={"query": "补充检索", "stage": "vector"},
            )
        ],
    }

    result = await aggregator_node(state)

    assert result["needs_replan"] is True
    assert result["replan_reason"] == "low_confidence_partial"
    assert result["replan_hint"] == {"query": "补充检索", "stage": "vector"}
