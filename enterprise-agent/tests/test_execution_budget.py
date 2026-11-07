"""F2-03 admission tests: real callbacks/framework, synthetic providers and stores."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from app.core import execution_budget as budgets
from app.core.execution_budget import ExecutionBudgetExceeded
from app.rag.budget_callback import get_execution_budget_handler


def model() -> FakeListChatModel:
    return FakeListChatModel(responses=['ok'], callbacks=[get_execution_budget_handler()])


def test_input_boundary_and_scope_cleanup() -> None:
    with budgets.execution_budget('x' * budgets.MAX_INPUT_BYTES) as budget:
        assert budgets.current_budget() is budget
    assert budget.closed and budgets.current_budget() is None
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('界' * 5462):
            pytest.fail('oversized input admitted')
    assert budgets.current_budget() is None


@pytest.mark.parametrize('resource', ['calls', 'single_prompt', 'total_prompt', 'tasks'])
def test_limits_at_boundary_and_latched_failure(resource: str) -> None:
    budget = budgets.ExecutionBudget()
    if resource == 'calls':
        for _ in range(16):
            budget.reserve_model(1)
        action = lambda: budget.reserve_model(1)
    elif resource == 'single_prompt':
        budget.reserve_model(65536)
        action = lambda: budget.reserve_model(65537)
    elif resource == 'total_prompt':
        for _ in range(4):
            budget.reserve_model(65536)
        action = lambda: budget.reserve_model(1)
    else:
        budget.reserve_tasks(12)
        action = lambda: budget.reserve_tasks(1)
    with pytest.raises(ExecutionBudgetExceeded):
        action()
    with pytest.raises(ExecutionBudgetExceeded):
        budget.check()


def test_atomic_model_reservations_under_parallel_threads() -> None:
    budget = budgets.ExecutionBudget()
    def reserve(_: int) -> bool:
        try:
            budget.reserve_model(100)
            return True
        except ExecutionBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(40)))
    assert sum(results) == budget.calls == 16
    assert budget.prompt_bytes == 1600


def test_deadline_and_inherited_context_cannot_reopen(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Mock(return_value=10.0)
    monkeypatch.setattr(budgets.time, 'monotonic', clock)
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('q') as budget:
            context = copy_context()
            clock.return_value = 130.0
            budget.reserve_tasks(1)
    clock.return_value = 11.0
    with pytest.raises(ExecutionBudgetExceeded):
        context.run(budgets.check_execution_budget)
    with budgets.execution_budget('another') as fresh:
        assert fresh.calls == fresh.tasks == fresh.prompt_bytes == 0


def test_history_is_bounded_visible_and_does_not_mutate_input() -> None:
    history = [{'user': str(i) + '界' * 3000, 'assistant': '😀' * 1000} for i in range(8)]
    out = budgets.bounded_history(history)
    assert len(out) == 5 and out[0]['user'].startswith('3')
    for turn in out:
        assert len(turn['user'].encode()) <= 2000
        assert len(turn['assistant'].encode()) <= 800
        assert turn['user'].endswith('[truncated]')
    assert len(history[0]['user']) == 3001


@pytest.mark.parametrize('async_call', [False, True])
@pytest.mark.asyncio
async def test_real_langchain_callback_blocks_provider_before_call(async_call: bool) -> None:
    llm = model()
    llm.responses = ['first', 'second', 'third']
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('q') as budget:
            if async_call:
                assert (await llm.ainvoke('hello')).content == 'first'
            else:
                assert llm.invoke('hello').content == 'first'
            assert budget.calls == 1
            if async_call:
                await llm.ainvoke('界' * 30000)
            else:
                llm.invoke('界' * 30000)
    assert llm.i == 1  # the excessive prompt never reached the fake provider


@pytest.mark.parametrize('options', [dict(max_tokens=1025), dict(max_tokens=-1),
    dict(max_completion_tokens=2048), dict(max_tokens=None), dict(n=2),
    dict(options={}), dict(options={'num_predict': -1}),
    dict(extra_body={'max_tokens': 9000})])
def test_output_overrides_cannot_expand_budget(options: dict) -> None:
    llm = model()
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('q'):
            llm.invoke('hello', **options)


@pytest.mark.asyncio
async def test_failed_calls_count_and_request_isolation() -> None:
    async def run() -> int:
        with budgets.execution_budget('q') as budget:
            llm = model()
            for _ in range(16):
                await llm.ainvoke('hello')
            return budget.calls
    assert await asyncio.gather(run(), run()) == [16, 16]
    llm = model()
    with budgets.execution_budget('q') as budget:
        with pytest.raises(ValueError):
            fail_after_reserve(llm)
        assert budget.calls == 1


def fail_after_reserve(llm: FakeListChatModel) -> None:
    llm.responses = []
    try:
        llm.invoke('hello')
    except IndexError as exc:
        raise ValueError('synthetic provider failure') from exc


@pytest.mark.asyncio
async def test_two_slots_cancel_waiter_and_release_on_failure() -> None:
    with budgets.execution_budget('q') as budget:
        entered = asyncio.Event()
        release = asyncio.Event()
        active = peak = 0
        async def work() -> None:
            nonlocal active, peak
            async with budgets.execution_slot():
                active += 1
                peak = max(peak, active)
                if active == 2:
                    entered.set()
                try:
                    await release.wait()
                finally:
                    active -= 1
        tasks = [asyncio.create_task(work()) for _ in range(4)]
        await asyncio.wait_for(entered.wait(), 1)
        tasks[3].cancel()
        with pytest.raises(asyncio.CancelledError):
            await tasks[3]
        release.set()
        await asyncio.gather(*tasks[:3])
        assert peak == 2 and active == 0
        assert budget.slots._value == 2


def test_raw_plan_refused_before_dedup_and_send() -> None:
    from app.graph.planner import _build_subtasks_from_llm
    from app.graph.dispatcher import route_after_planner
    from app.graph.state import Intent
    raw = [{'type': 'execution', 'desc': 'same'}] * 5
    with pytest.raises(ExecutionBudgetExceeded):
        _build_subtasks_from_llm(raw)
    with pytest.raises(ExecutionBudgetExceeded):
        route_after_planner({'intent': Intent.CHITCHAT, 'subtasks': raw})
    assert len(_build_subtasks_from_llm(raw[:4])) == 4


@pytest.mark.asyncio
async def test_planner_and_executor_do_not_convert_budget_failure_to_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.graph import planner, executor
    from app.graph.state import SubTask, TaskType
    llm = model()
    monkeypatch.setattr(planner, 'get_local_llm', lambda: llm)
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('q'):
            planner._quick_chitchat_check('界' * 30000)
    agent = SimpleNamespace(run=AsyncMock(side_effect=budgets.check_execution_budget))
    def closed_agent(*args: object) -> SimpleNamespace:
        budgets.current_budget().close()
        return agent
    monkeypatch.setattr(executor, '_get_agent', closed_agent)
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('q'):
            await executor.agent_executor_node({'user_input': SimpleNamespace(),
                'current_subtask': SubTask(task_id='one', task_type=TaskType.KNOWLEDGE,
                                          description='q')})


@pytest.mark.asyncio
async def test_dispatch_counts_replans_and_executor_uses_real_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.graph import dispatcher, executor
    from app.graph.state import Intent, SubTask, TaskType, UserInput
    from app.security.rbac import AgentRole
    user = UserInput(message='q', user_id='u', username='u', role=AgentRole.SALESPERSON,
                     conversation_id='s', request_id='r')
    tasks = [SubTask(task_id=str(i), task_type=TaskType.KNOWLEDGE, description='q')
             for i in range(4)]
    state = dict(user_input=user, request_id='r', intent=Intent.MULTI_TASK, subtasks=tasks)
    peak = active = 0
    entered, release = asyncio.Event(), asyncio.Event()
    async def run(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 2:
            entered.set()
        await release.wait()
        active -= 1
        return SimpleNamespace(agent_name='knowledge', success=True, confidence=1)
    monkeypatch.setattr(executor, '_get_agent', lambda *args: SimpleNamespace(run=run))
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('q') as budget:
            sends = dispatcher.route_after_planner(state)
            jobs = [asyncio.create_task(executor.agent_executor_node(send.arg)) for send in sends]
            await asyncio.wait_for(entered.wait(), 1)
            assert peak == 2
            release.set()
            await asyncio.gather(*jobs)
            dispatcher.route_after_planner(state)
            dispatcher.route_after_planner(state)
            assert budget.tasks == 12
            dispatcher.route_after_planner(state)


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
async def test_graph_entry_owns_budget_and_closes_late_context(
    monkeypatch: pytest.MonkeyPatch, stream: bool,
) -> None:
    from app.graph import graph
    seen = []
    async def invoke(*args: object, **kwargs: object) -> dict:
        seen.append((budgets.current_budget(), copy_context()))
        budgets.current_budget().reserve_model(1)
        return {'final_answer': 'answer'}
    async def events(*args: object, **kwargs: object):
        await invoke()
        yield {'type': 'progress'}
    monkeypatch.setattr(graph, '_run_graph', invoke)
    monkeypatch.setattr(graph, '_run_graph_stream', events)
    user = SimpleNamespace(message='q')
    if stream:
        gen = graph.run_graph_stream(user)
        await anext(gen)
        await gen.aclose()
    else:
        await graph.run_graph(user)
    assert seen[0][0].calls == 1 and seen[0][0].closed
    assert budgets.current_budget() is None
    with pytest.raises(ExecutionBudgetExceeded):
        seen[0][1].run(budgets.check_execution_budget)


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
async def test_graph_entry_rejects_input_before_store_or_graph(
    monkeypatch: pytest.MonkeyPatch, stream: bool,
) -> None:
    from app.graph import graph
    backend = Mock()
    monkeypatch.setattr(graph, 'build_graph', backend)
    with pytest.raises(ExecutionBudgetExceeded):
        if stream:
            async for _ in graph.run_graph_stream(SimpleNamespace(message='x' * 16385)):
                pytest.fail('unexpected stream output')
        else:
            await graph.run_graph(SimpleNamespace(message='x' * 16385), use_checkpointer=False)
    backend.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
async def test_api_budget_error_never_publishes_success(stream: bool) -> None:
    import sys
    from unittest.mock import patch
    from test_session_ownership import SessionOwnershipTests, HTTPException
    case = SessionOwnershipTests()
    await case.asyncSetUp()
    try:
        publish = AsyncMock()
        case.chat.publish_checkpoint = publish
        if stream:
            async def fail_stream(*args: object, **kwargs: object):
                raise ExecutionBudgetExceeded()
                yield  # async-generator protocol
            with patch.object(sys.modules['app.graph.graph'], 'run_graph_stream', fail_stream):
                response = await case.call('stream', case.owner)
                events = ''.join([event async for event in response.events])
            assert 'EXECUTION_BUDGET_EXCEEDED' in events
            assert '"type": "final"' not in events
        else:
            case.graph.side_effect = ExecutionBudgetExceeded()
            with pytest.raises(HTTPException) as error:
                await case.call('message', case.owner)
            assert (error.value.status_code, error.value.detail) == (
                422, 'EXECUTION_BUDGET_EXCEEDED')
        publish.assert_not_awaited()
        assert case.chat._update_session_status.await_args.args[1] == 'failed'
    finally:
        await case.asyncTearDown()


@pytest.mark.asyncio
async def test_tool_and_approval_guards_run_before_any_service_access() -> None:
    from app.tools.base import BaseTool
    from app.agents.execution import ExecutionAgent
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('q') as budget:
            budget.close()
            await BaseTool.invoke(None, {}, {})
    with pytest.raises(ExecutionBudgetExceeded):
        with budgets.execution_budget('q') as budget:
            budget.close()
            await ExecutionAgent._create_approval_request(None, [], {}, 'q')


@pytest.mark.asyncio
async def test_real_langgraph_propagates_request_budget_into_sync_and_async_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.graph import graph, executor
    from app.graph.state import Intent, SubTask, TaskType, UserInput
    from app.security.rbac import AgentRole
    seen = []
    llm = model()
    def plan(state: dict) -> dict:
        seen.append(budgets.current_budget())
        llm.invoke('synthetic classification')
        return {'intent': Intent.MULTI_TASK, 'subtasks': [
            SubTask(task_id=str(i), task_type=TaskType.KNOWLEDGE, description='q')
            for i in range(4)]}
    async def run(*args: object, **kwargs: object) -> SimpleNamespace:
        seen.append(budgets.current_budget())
        await llm.ainvoke('synthetic answer')
        return SimpleNamespace(agent_name='knowledge', success=True, confidence=1)
    async def aggregate(state: dict) -> dict:
        seen.append(budgets.current_budget())
        return {'final_answer': 'done'}
    monkeypatch.setattr(graph, 'planner_node', plan)
    monkeypatch.setattr(graph, 'aggregator_node', aggregate)
    monkeypatch.setattr(graph, '_compiled_graphs', {})
    monkeypatch.setattr(executor, '_get_agent', lambda *args: SimpleNamespace(run=run))
    user = UserInput(message='q', user_id='u', username='u', role=AgentRole.SALESPERSON,
                     conversation_id='s', request_id='r')
    result = await graph.run_graph(user, use_checkpointer=False)
    assert result['final_answer'] == 'done'
    assert len(seen) == 6 and all(b is seen[0] for b in seen)
    assert seen[0].calls == 5 and seen[0].tasks == 4 and seen[0].closed
    assert budgets.current_budget() is None


def test_router_caps_outputs_and_installs_guard_on_each_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.rag import llm
    from test_model_profile import settings
    config = settings(primary_llm_max_tokens=8192)
    monkeypatch.setattr(llm, 'get_settings', lambda: config)
    factory = Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(llm, 'ChatOpenAI', factory)
    router = llm.LLMRouter()
    for item in (router.get_primary(), router.get_lite(), router.get_local()):
        assert item.max_tokens == 1024 and item.max_retries == 2
        assert get_execution_budget_handler() in item.callbacks
    import langchain_ollama
    monkeypatch.setattr(langchain_ollama, 'ChatOllama', factory)
    local = router._get_local_chat_model(max_tokens=8192)
    assert local.num_predict == 1024
    assert get_execution_budget_handler() in local.callbacks


@pytest.mark.parametrize('provider', ['openai', 'ollama'])
def test_actual_provider_invocation_parameters_accept_router_output_cap(provider: str) -> None:
    if provider == 'openai':
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(api_key='synthetic-not-a-credential', model='synthetic', max_tokens=1024)
    else:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model='synthetic', num_predict=1024, validate_model_on_init=False)
    with budgets.execution_budget('q') as budget:
        get_execution_budget_handler().on_chat_model_start(
            {}, [[HumanMessage(content='q')]], invocation_params=llm._get_invocation_params())
        assert budget.calls == 1
