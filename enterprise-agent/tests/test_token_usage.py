"""I-07:token 用量统一采集测试

覆盖:
- TokenUsageCallbackHandler 两种口径提取(llm_output.token_usage / usage_metadata)
- 请求级累加器(contextvar)与 Prometheus counter 落地
- aggregator 汇总后 tokens_used 取自统一累加器
- Token totals commit with owned checkpoint publication; failures block success
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app.agents.knowledge import AgentResult
from app.graph.checkpoint_access import publish_checkpoint
from app.core.runtime_state import RuntimeStateUnavailable
from app.graph.aggregator import aggregator_node
from app.graph.state import Intent, UserInput
from app.observability.metrics import llm_token_usage
from app.observability.token_usage import (
    TokenUsageCallbackHandler,
    snapshot_total_tokens,
    track_token_usage,
)


def _make_user_input() -> UserInput:
    return UserInput(
        message="测试",
        user_id="user_sales_001",
        username="销售员张三",
        role="salesperson",
        department="dept_sales",
        jwt_token="",
        conversation_id="sess_token_test",
        request_id="req_token_test",
    )


def _llm_result_via_llm_output(total: int = 120) -> LLMResult:
    """OpenAI 兼容口径:llm_output.token_usage"""
    return LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={
            "model_name": "deepseek-v4-flash",
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": total,
            },
        },
    )


def _llm_result_via_usage_metadata(total: int = 60) -> LLMResult:
    """LangChain 1.x 标准口径:message.usage_metadata"""
    message = AIMessage(
        content="答案",
        usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": total},
    )
    return LLMResult(generations=[[ChatGeneration(message=message)]], llm_output=None)


@pytest.mark.asyncio
async def test_should_accumulate_tokens_from_llm_output_token_usage():
    """Given LLMResult 带 llm_output.token_usage, When 回调 on_llm_end,
    Then 累加器按 prompt/completion/total 正确累加"""
    handler = TokenUsageCallbackHandler()
    with track_token_usage() as acc:
        await handler.on_llm_end(_llm_result_via_llm_output())
        assert acc.prompt_tokens == 100
        assert acc.completion_tokens == 20
        assert acc.total_tokens == 120
    # 作用域外快照归零
    assert snapshot_total_tokens() == 0


@pytest.mark.asyncio
async def test_should_accumulate_tokens_from_usage_metadata():
    """Given LLMResult 带 message.usage_metadata, When 回调 on_llm_end,
    Then 同样被统一通道采集(本地 ChatOllama 口径)"""
    handler = TokenUsageCallbackHandler()
    with track_token_usage() as acc:
        await handler.on_llm_end(_llm_result_via_usage_metadata())
        assert acc.prompt_tokens == 50
        assert acc.completion_tokens == 10
        assert acc.total_tokens == 60


@pytest.mark.asyncio
async def test_should_increment_prometheus_counter_on_llm_end():
    """Given 一次 LLM 调用结束, When 回调触发,
    Then Prometheus counter 按 model/token_type 递增"""
    handler = TokenUsageCallbackHandler()
    before = llm_token_usage.labels(
        model="deepseek-v4-flash", token_type="total"
    )._value.get()
    await handler.on_llm_end(_llm_result_via_llm_output(total=120))
    after = llm_token_usage.labels(model="deepseek-v4-flash", token_type="total")._value.get()
    assert after - before == 120


@pytest.mark.asyncio
async def test_should_ignore_llm_result_without_usage():
    """Given LLMResult 无任何用量字段, When 回调触发, Then 不累计不报错"""
    handler = TokenUsageCallbackHandler()
    empty = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="x"))]], llm_output=None
    )
    with track_token_usage() as acc:
        await handler.on_llm_end(empty)
        assert acc.total_tokens == 0


@pytest.mark.asyncio
async def test_should_set_aggregator_tokens_from_unified_accumulator():
    """Given 采集作用域内已有 LLM token 消耗, When aggregator 单结果直通,
    Then tokens_used 取自统一累加器(不再依赖子 Agent 自报字段)"""
    handler = TokenUsageCallbackHandler()
    state = {
        "user_input": _make_user_input(),
        "intent": Intent.KNOWLEDGE_QA,
        "agent_results": [
            AgentResult(
                agent_name="knowledge",
                success=True,
                confidence=0.8,
                output={"answer": "现有知识库未覆盖该情形，无法根据现有片段回答。"},
                tokens_used=0,  # 旧口径已废弃,aggregator 不再读它
            )
        ],
    }
    with track_token_usage():
        await handler.on_llm_end(_llm_result_via_llm_output(total=88))
        result = await aggregator_node(state)
    assert result["tokens_used"] == 88


def publication_fixture(tokens: int):
    user = _make_user_input()
    state = {'request_id': user.request_id, 'user_input': vars(user),
             'final_answer': 'synthetic answer', 'tokens_used': tokens}
    cp = SimpleNamespace(aget_tuple=AsyncMock(return_value=SimpleNamespace(
        checkpoint={'id': 'final-id', 'channel_values': state})))
    fence = SimpleNamespace(config={'configurable': {'thread_id': 'physical-run'}},
                            thread_id='physical-run', finish=AsyncMock(return_value=True))
    return user, state, cp, fence


@pytest.mark.asyncio
async def test_tokens_commit_with_owned_checkpoint():
    user, state, cp, fence = publication_fixture(120)
    assert await publish_checkpoint(cp, 'postgres', fence, user) == state
    fence.finish.assert_awaited_once_with('completed', tokens=120, publication={
        'backend': 'postgres', 'thread_id': 'physical-run',
        'checkpoint_ns': '', 'checkpoint_id': 'final-id'})


@pytest.mark.asyncio
async def test_token_commit_failure_blocks_final_success():
    user, _, cp, fence = publication_fixture(120)
    fence.finish.side_effect = RuntimeStateUnavailable()
    with pytest.raises(RuntimeStateUnavailable):
        await publish_checkpoint(cp, 'postgres', fence, user)
    fence.finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_zero_tokens_still_require_checkpoint_publication():
    user, _, cp, fence = publication_fixture(0)
    await publish_checkpoint(cp, 'postgres', fence, user)
    assert fence.finish.await_args.kwargs['tokens'] == 0
    assert fence.finish.await_args.kwargs['publication']['checkpoint_id'] == 'final-id'
