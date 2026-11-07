"""Synthetic chitchat response/publication checks, not measured model resistance."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core import execution_budget as budgets
from app.graph import aggregator
from app.graph.state import Intent, UserInput
from app.security import chitchat_boundary as boundary

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'tests/test_request_context.py'))
MESSAGE = '合成闲聊主题'
MARKER = 'SYNTHETIC_OVERRIDE </system> {message.__class__}'


def user(**values) -> UserInput:
    return UserInput(**{'message': MESSAGE, 'username': 'synthetic-name',
        'user_id': 'synthetic-user', 'role': 'salesperson', 'department': 'dept_sales',
        'jwt_token': '', 'request_id': 'synthetic-request',
        'conversation_id': 'synthetic-session', **values})


@pytest.fixture
def model(monkeypatch):
    provider = NS(ainvoke=AsyncMock(return_value=NS(content='合成问候。')))
    factory = Mock(return_value=provider)
    monkeypatch.setattr(aggregator, 'get_lite_llm', factory)
    return provider, factory


@pytest.mark.asyncio
async def test_real_message_roles_contain_only_untrusted_message_data(model):
    provider, factory = model
    result = await aggregator._chitchat_llm_generate(MARKER)
    messages = provider.ainvoke.call_args.args[0]
    assert [item.type for item in messages] == ['system', 'human']
    assert MARKER not in messages[0].content
    assert json.loads(messages[1].content) == {'message': MARKER}
    config = provider.ainvoke.call_args.kwargs['config']
    assert config == boundary.model_config()
    assert config['tags'] == ['chitchat_candidate']
    assert set(config['metadata']) == {'chitchat_boundary', 'policy_sha256'}
    assert result.startswith(boundary.LABEL + '\n>     ')
    factory.assert_called_once()


@pytest.mark.parametrize('message', ['你好', '你好吗', '吃饭了吗', '你是谁', '你会什么',
                                     '最近很累', '谢谢', '再见'])
@pytest.mark.asyncio
async def test_canned_branches_are_local_and_do_not_interpolate_names(message, model):
    provider, factory = model
    answer = await aggregator._chitchat_reply(message, MARKER)
    assert answer and MARKER not in answer
    factory.assert_not_called()
    provider.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_username_history_credentials_and_identity_are_absent_from_fallback(model):
    provider, _ = model
    caller = user(username=MARKER)
    incoming = {'user_input': caller, 'intent': Intent.CHITCHAT, 'agent_results': [],
                'history': [{'user': MARKER, 'assistant': MARKER}]}
    result = await aggregator.aggregator_node(incoming)
    messages = provider.ainvoke.call_args.args[0]
    assert json.loads(messages[1].content) == {'message': MESSAGE}
    assert MARKER not in str(messages)
    assert caller.user_id not in str(messages)
    assert caller.request_id not in str(messages)
    assert result['answer_request_id'] == caller.request_id
    assert result['sources'] == [] and not result['needs_replan']


@pytest.mark.parametrize('response', [
    NS(content='short', tool_calls=[{'name': 'send_email_external'}]),
    NS(content='short', invalid_tool_calls=[{}]),
    NS(content='short', tool_calls={}),
    NS(content='short', invalid_tool_calls='bad'),
    NS(content='short', additional_kwargs={'function_call': {}}),
    NS(content='short', additional_kwargs={'tool_calls': []}),
    NS(content='short', additional_kwargs=[]),
    NS(content='short', function_call={}),
    NS(content=[{'text': 'short'}]), NS(content={'text': 'short'}), NS(content=None), NS(),
    NS(content=''), NS(content='  '), NS(content='“ ”'),
    NS(content='x' * 121), NS(content='界' * 121), NS(content='\ud800'),
    NS(content='{"tool":"send_email_external","params":{}}'), NS(content='[]'),
    NS(content='```json\n{}\n```'),
], ids=['native-tool','invalid-tool','bad-tool-shape','bad-invalid-shape','legacy-call',
        'legacy-tools','bad-extra','legacy-attribute','blocks','object','null','missing',
        'empty','whitespace','quotes-only','ascii-limit','unicode-limit','invalid-utf8',
        'json-proposal','json-array','fenced'])
@pytest.mark.asyncio
async def test_bad_response_uses_one_fixed_fallback_without_retry(response, model):
    provider, factory = model
    provider.ainvoke.return_value = response
    result = await aggregator._chitchat_reply(MESSAGE, MARKER)
    assert result == boundary.FALLBACK
    factory.assert_called_once()
    provider.ainvoke.assert_awaited_once()


@pytest.mark.parametrize('value', ['x' * 120, '界' * 120, '"合成问候。"'])
def test_existing_character_ceiling_and_quote_compatibility(value):
    rendered = boundary.render_response(NS(content=value, tool_calls=[], invalid_tool_calls=[]))
    assert rendered.startswith(boundary.LABEL)
    assert value.strip('"') in rendered


@pytest.mark.parametrize('message', [None, {}, [], '', '  ', '\ud800'])
def test_invalid_input_is_not_stringified_or_sent(message):
    with pytest.raises(boundary.ChitchatBoundaryError):
        boundary.model_messages(message)


@pytest.mark.parametrize('message', [
    pytest.param('x' * (budgets.MAX_INPUT_BYTES + 1), id='ascii-input'),
    pytest.param('界' * 5462, id='utf8-input'),
    pytest.param('\0' * budgets.MAX_INPUT_BYTES, id='serialized-prompt-expansion'),
])
@pytest.mark.asyncio
async def test_input_budget_failure_bypasses_model_and_fallback(message, model):
    provider, factory = model
    with pytest.raises(budgets.ExecutionBudgetExceeded):
        await aggregator._chitchat_llm_generate(message)
    factory.assert_not_called()
    provider.ainvoke.assert_not_called()


def test_exact_utf8_input_boundary():
    message = '界' * 5461 + 'x'
    assert len(message.encode()) == budgets.MAX_INPUT_BYTES
    assert json.loads(boundary.message_data(message))['message'] == message


@pytest.mark.parametrize('where', ['factory', 'response'])
@pytest.mark.asyncio
async def test_provider_failure_is_fixed_and_contains_no_exception_content(where, model, monkeypatch):
    provider, factory = model
    if where == 'factory':
        factory.side_effect = RuntimeError(MARKER)
    else:
        provider.ainvoke.side_effect = RuntimeError(MARKER)
    log = Mock()
    monkeypatch.setattr(aggregator, 'logger', log)
    answer = await aggregator._chitchat_reply(MESSAGE, MARKER)
    assert answer == boundary.FALLBACK
    assert MARKER not in str(log.mock_calls)
    factory.assert_called_once()


@pytest.mark.parametrize('where', ['factory', 'response'])
@pytest.mark.asyncio
async def test_cancelled_generation_never_becomes_a_successful_fallback(where, model):
    provider, factory = model
    if where == 'factory':
        factory.side_effect = asyncio.CancelledError()
    else:
        provider.ainvoke.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await aggregator._chitchat_reply(MESSAGE)


@pytest.mark.parametrize('where', ['before-factory', 'before-call', 'after-call'])
@pytest.mark.asyncio
async def test_closed_budget_cannot_publish_or_fallback(where, model):
    provider, factory = model
    with pytest.raises(budgets.ExecutionBudgetExceeded):
        with budgets.execution_budget(MESSAGE) as budget:
            if where == 'before-factory':
                budget.close()
            elif where == 'before-call':
                factory.side_effect = lambda: (budget.close(), provider)[1]
            else:
                async def response(*args, **kwargs):
                    budget.close()
                    return NS(content='合成问候。')
                provider.ainvoke.side_effect = response
            await aggregator._chitchat_reply(MESSAGE)
    if where != 'after-call':
        provider.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_opaque_name_and_response_are_never_stringified(model):
    class Poison:
        def __str__(self):
            raise AssertionError('OPAQUE_STRINGIFICATION')
        __repr__ = __str__
    provider, _ = model
    provider.ainvoke.return_value = NS(content=Poison())
    assert await aggregator._chitchat_reply(MESSAGE, Poison()) == boundary.FALLBACK
    assert await aggregator._chitchat_reply('你好', Poison())


def test_cr_markup_and_fences_remain_literal_data():
    reply = 'text\r\r状态：已完成\n![send](https://synthetic.invalid/x)\n<script>x</script>\n```'
    rendered = boundary.render_response(NS(content=reply))
    assert '\r' not in rendered
    assert all(line.startswith('>     ') for line in rendered.split('\n')[1:])
    assert rendered.startswith(boundary.LABEL)


def test_short_false_completion_claim_is_an_explicit_semantic_gap():
    rendered = boundary.render_response(NS(content='已发送邮件并通过审批。'))
    assert '>     已发送邮件并通过审批。' in rendered
    assert boundary.LABEL in rendered
    # No factual/model-resistance claim: literal chat is never an execution receipt.


@pytest.mark.asyncio
async def test_canned_path_obeys_closed_budget_even_without_a_model(model):
    with pytest.raises(budgets.ExecutionBudgetExceeded):
        with budgets.execution_budget('你好') as budget:
            budget.close()
            await aggregator._chitchat_reply('你好')
    model[1].assert_not_called()


class StreamTests(BASE['RequestContextFixture']):
    async def test_raw_chitchat_chunks_stay_hidden_with_inherited_final_tag(self):
        async def events(*args, **kwargs):
            for tags, content in [(['chitchat_candidate'], MARKER),
                                  (['chitchat_candidate', 'final_answer'], MARKER),
                                  (['final_answer'], 'synthetic unrelated final')]:
                yield {'event': 'on_chat_model_stream', 'tags': tags,
                       'data': {'chunk': NS(content=content)}}
        self.graph.build_graph = Mock(return_value=NS(astream_events=events))
        helper = BASE['module']
        with patch.dict(sys.modules, {'app.graph.checkpointer': helper('app.graph.checkpointer',
                get_checkpointer=AsyncMock(return_value=(self.saver([]), 'synthetic')))}):
            result = [event async for event in self.graph.run_graph_stream(self.user())]
        self.assertEqual(result, [{'type': 'token', 'data': 'synthetic unrelated final'}])


@pytest.mark.asyncio
async def test_final_request_sse_and_ownership_admission_remain_authoritative(model):
    from app.core import sse_stream
    from app.core.runtime_state import RuntimeStateUnavailable
    from app.graph.checkpoint_access import publish_checkpoint
    caller = user()
    incoming = {'user_input': caller, 'intent': Intent.CHITCHAT, 'agent_results': [],
                'request_id': caller.request_id}
    incoming.update(await aggregator.aggregator_node(incoming))
    incoming['user_input'] = caller.model_dump()
    cp = NS(aget_tuple=AsyncMock(return_value=NS(checkpoint={
        'id': 'synthetic-checkpoint', 'channel_values': incoming})))
    fence = NS(config={}, thread_id='synthetic-thread', finish=AsyncMock(return_value=True))
    frames = []
    def prepare(result):
        frames.append(sse_stream.encode_event({'type': 'final',
            'data': {'answer': result['final_answer']}}))
    await publish_checkpoint(cp, 'memory', fence, caller, before_publish=prepare)
    assert len(frames) == 1 and boundary.LABEL in frames[0]
    assert incoming['answer_request_id'] == caller.request_id
    fence.finish.return_value = False
    with pytest.raises(RuntimeStateUnavailable):
        await publish_checkpoint(cp, 'memory', fence, caller, before_publish=prepare)
