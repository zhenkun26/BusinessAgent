"""C08 actual-source offline checks; framework, stores and models are doubles."""

from __future__ import annotations

import ast
import asyncio
from contextlib import ExitStack, nullcontext
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, **attrs: Any) -> ModuleType:
    result = ModuleType(name)
    result.__dict__.update(attrs)
    return result


def load(name: str, path: str) -> ModuleType:
    result = module(name)
    source = ROOT / path
    exec(compile(source.read_bytes(), str(source), 'exec'), result.__dict__)
    return result


def extract(path: str, names: set[str], namespace: dict) -> dict:
    tree = ast.parse((ROOT / path).read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                                   ast.AsyncFunctionDef)) and n.name in names]
    source = 'from __future__ import annotations\n' + '\n'.join(ast.unparse(n) for n in nodes)
    exec(compile(source, path, 'exec'), namespace)
    return namespace


class Record(SimpleNamespace):
    def model_copy(self, *, update: dict) -> Record:
        return Record(**{**vars(self), **update})


class Task(Record):
    def __init__(self, **kwargs: Any):
        super().__init__(**{'depends_on': [], 'priority': 0, **kwargs})


class Result(Record):
    def __init__(self, **kwargs: Any):
        super().__init__(**{'agent_name': 'fake', 'success': True, 'confidence': .8,
                           'output': {'answer': 'answer'}, 'sources': [], 'error': None,
                           'needs_replan': False, 'replan_reason': None, 'replan_hint': None,
                           **kwargs})


class FakeGraph:
    def __init__(self, schema: Any):
        self.nodes = {}
        self.edges = []
        self.routes = {}

    def add_node(self, name: str, fn: Any) -> None:
        self.nodes[name] = fn

    def add_edge(self, start: str, end: str) -> None:
        self.edges.append((start, end))

    def add_conditional_edges(self, node: str, fn: Any, targets: list) -> None:
        self.routes[node] = (fn, targets)

    def compile(self, **kwargs: Any) -> FakeGraph:
        return self


class RequestContextTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        ns = extract('app/graph/state.py', {'Intent', 'TaskType', 'make_initial_state'},
                     dict(Enum=Enum, datetime=datetime, AgentState=dict, redact_text=lambda s: s))
        self.intent, self.kind = ns['Intent'], ns['TaskType']
        self.make = ns['make_initial_state']
        self.log = Mock()
        self.policy = load('c08_policy', 'app/graph/plan_policy.py')
        self.agent_factory = Mock(side_effect=lambda **kw: Record(
            **kw, run=AsyncMock(return_value=Result())))
        self.llm = Mock()
        self.primary = Mock(return_value=self.llm)
        self.stack.enter_context(patch.dict(sys.modules, {
            'loguru': module('loguru', logger=self.log),
            'langchain_core.messages': module('langchain_core.messages',
                HumanMessage=Record, SystemMessage=Record),
            'langgraph.types': module('langgraph.types',
                Send=lambda node, arg: Record(node=node, arg=arg)),
            'langgraph.graph': module('langgraph.graph', END='end', START='start',
                                      StateGraph=FakeGraph),
            'app.graph.state': module('app.graph.state', AgentState=dict, UserInput=Record,
                SubTask=Task, Intent=self.intent, TaskType=self.kind, make_initial_state=self.make),
            'app.graph.plan_policy': self.policy,
            'app.agents.analysis': module('app.agents.analysis', AnalysisAgent=self.agent_factory),
            'app.agents.execution': module('app.agents.execution', ExecutionAgent=self.agent_factory),
            'app.agents.knowledge': module('app.agents.knowledge', AgentResult=Result,
                RetrievalSource=Record, KnowledgeAgent=self.agent_factory),
            'app.rag.llm': module('app.rag.llm', get_primary_llm=self.primary,
                get_lite_llm=Mock(), get_local_llm=Mock(), get_cloud_lite_llm=Mock()),
            'app.prompts': module('app.prompts', get_prompt=lambda name: ('{message}', 1),
                                   request_prompt_snapshot=lambda **kw: nullcontext()),
            'app.observability.token_usage': module('app.observability.token_usage',
                track_token_usage=nullcontext, snapshot_total_tokens=lambda: 0),
        }))
        self.executor = load('c08_executor', 'app/graph/executor.py')
        self.dispatch = load('c08_dispatch', 'app/graph/dispatcher.py')
        self.planner = load('c08_planner', 'app/graph/planner.py')
        self.checkpoint_access = load('c08_checkpoint_access', 'app/graph/checkpoint_access.py')
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.graph.checkpoint_access': self.checkpoint_access,
        }))
        self.history = load('c08_history', 'app/graph/history.py')
        self.aggregator = load('c08_aggregator', 'app/graph/aggregator.py')
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.graph.executor': self.executor, 'app.graph.dispatcher': self.dispatch,
            'app.graph.planner': self.planner, 'app.graph.history': self.history,
            'app.graph.aggregator': self.aggregator,
        }))
        self.graph = load('c08_graph', 'app/graph/graph.py')

    def user(self, **kw: Any) -> Record:
        return Record(**{'user_id': 'user-a', 'username': 'A', 'role': 'salesperson',
                         'department': 'dept_sales', 'conversation_id': 'session-a',
                         'request_id': 'request-new', 'message': 'same question', **kw})

    def state(self, **kw: Any) -> dict:
        return {**self.make(self.user()), 'intent': self.intent.MULTI_TASK,
                'history': [{'user': 'policy', 'assistant': 'old answer'}],
                'subtasks': [Task(task_id='t1', task_type=self.kind.KNOWLEDGE,
                                  description='what about that?'),
                             Task(task_id='t2', task_type=self.kind.EXECUTION,
                                  description='independent write')], **kw}

    def snapshot(self, request: str, **kw: Any) -> Record:
        values = {'user_input': vars(self.user(request_id=request)), 'request_id': request,
                  'answer_request_id': request, 'final_answer': 'answer-' + request, **kw}
        return Record(checkpoint={'channel_values': values})

    def saver(self, rows: list) -> Record:
        async def alist(config: dict, limit: int):
            self.assertEqual(config, {'configurable': {'thread_id': 'session-a'}})
            self.assertEqual(limit, 100)
            for row in rows:
                yield row
        return Record(alist=alist)

    async def history_for(self, rows: list, **kw: Any) -> list:
        return await self.history.load_recent_history('session-a', checkpointer=self.saver(rows),
                                                      user_input=self.user(), **kw)

    def test_fresh_agents_for_every_type_and_dispatch(self) -> None:
        for kind in self.kind:
            with self.subTest(kind=kind):
                first = self.executor._get_agent(kind, self.user())
                second = self.executor._get_agent(kind, self.user())
                self.assertIsNot(first, second)

    async def test_overlapping_requests_keep_current_context(self) -> None:
        arrived = 0
        barrier = asyncio.Event()
        observed = []

        def factory(**context: Any) -> Record:
            async def run(query: str) -> Result:
                nonlocal arrived
                arrived += 1
                if arrived == 2:
                    barrier.set()
                await asyncio.wait_for(barrier.wait(), timeout=1)
                observed.append((query, dict(context)))
                return Result()
            return Record(run=run)

        self.agent_factory.side_effect = factory
        users = [self.user(request_id='r1'), self.user(conversation_id='session-b',
                 request_id='r2')]
        states = [self.state(user_input=u, request_id=u.request_id,
                   current_subtask=Task(task_id='t', task_type=self.kind.EXECUTION,
                                        description=u.request_id)) for u in users]
        await asyncio.gather(*(self.executor.agent_executor_node(s) for s in states))
        self.assertEqual(len(observed), 2)
        for query, ctx in observed:
            expected = users[0 if query == 'r1' else 1]
            self.assertEqual(ctx['conversation_id'], expected.conversation_id)
            self.assertEqual(ctx['request_id'], expected.request_id)
            self.assertEqual(ctx['user_role'], expected.role)
            self.assertNotIn('jwt_token', ctx)

    def test_refreshed_identity_never_reuses_old_agent(self) -> None:
        old = self.executor._get_agent(self.kind.EXECUTION, self.user())
        new = self.executor._get_agent(self.kind.EXECUTION, self.user(
            role='manager', department='dept_hr', request_id='refreshed'))
        self.assertEqual(old.user_role, 'salesperson')
        self.assertEqual(new.user_role, 'manager')
        self.assertEqual(new.user_dept, 'dept_hr')
        self.assertEqual(new.request_id, 'refreshed')

    async def test_execution_run_forwards_request_to_tool_context(self) -> None:
        execute = AsyncMock(side_effect=RuntimeError('stop after capturing tool context'))
        ns = extract('app/agents/execution.py', {'ExecutionAgent'}, dict(
            time=time, uuid=uuid, logger=self.log, _ensure_tools=Mock(), AgentResult=Result,
            ROLE_TOOLS={'salesperson': ['lookup']}, get_tool=lambda name: None,
            execute_tool_calls=execute))
        agent = ns['ExecutionAgent']('salesperson', 'dept_sales', user_id='u',
                                    conversation_id='c', request_id='r')
        agent._parse_tool_calls = AsyncMock(return_value=[Record(tool='lookup', params={})])
        await agent.run('lookup')
        self.assertEqual(execute.await_args.args[1], {'user_id': 'u', 'role': 'salesperson',
            'dept': 'dept_sales', 'session_id': 'c', 'request_id': 'r', 'execution_slot': 'direct'})
        # The same current context reaches approval creation, not only direct tools.
        ns['get_tool'] = lambda name: Record(requires_approval=True, _validate_params=Mock())
        agent._parse_tool_calls = AsyncMock(return_value=[Record(
            tool='lookup', params={}, reason='requested')])
        agent._create_approval_request = AsyncMock(return_value='approval-test')
        result = await agent.run('request approval')
        self.assertTrue(result.success)
        self.assertEqual(agent._create_approval_request.await_args.args[1],
                         execute.await_args.args[1])
        self.assertNotEqual(ns['ExecutionAgent']('salesperson').request_id,
                            ns['ExecutionAgent']('salesperson').request_id)

    async def test_history_reaches_knowledge_with_isolated_copies(self) -> None:
        state = self.state()
        sends = self.dispatch.route_after_planner(state)
        self.assertEqual([s.node for s in sends], ['agent_executor'] * 2)
        await self.executor.agent_executor_node(sends[0].arg)
        # Capture a fresh instance to inspect the real executor's invocation.
        agent = Record(run=AsyncMock(return_value=Result()))
        self.agent_factory.side_effect = lambda **kw: agent
        await self.executor.agent_executor_node(sends[0].arg)
        self.assertEqual(agent.run.await_args.kwargs['history'], state['history'])
        sends[0].arg['history'][0]['assistant'] = 'changed'
        sends[0].arg['user_input'].conversation_id = 'changed'
        sends[0].arg['current_subtask'].description = 'changed'
        self.assertEqual(sends[1].arg['history'], state['history'])
        self.assertEqual(state['user_input'].conversation_id, 'session-a')
        self.assertEqual(state['subtasks'][0].description, 'what about that?')

    def test_no_history_and_chitchat_paths(self) -> None:
        self.assertEqual(self.dispatch.route_after_planner(self.state(
            intent=self.intent.CHITCHAT)), 'aggregator')
        sends = self.dispatch.route_after_planner(self.state(history=None))
        self.assertEqual(sends[0].arg['history'], [])

    def test_initial_state_clears_previous_request_outputs(self) -> None:
        old = dict(final_answer='stale', answer_request_id='old', sources=['old'],
                   error='old', plan_error='old', replan_reason='old', agent_results=['old'])
        old.update(self.make(self.user()))
        self.assertEqual(old['final_answer'], '')
        self.assertEqual(old['sources'], [])
        self.assertEqual(old['agent_results'], [])
        for key in ('answer_request_id', 'error', 'plan_error', 'replan_reason'):
            self.assertIsNone(old[key])

    async def test_aggregator_binds_answer_and_excludes_replanning(self) -> None:
        state = self.state(intent=self.intent.KNOWLEDGE_QA, agent_results=[Result()])
        result = await self.aggregator.aggregator_node(state)
        self.assertEqual(result['answer_request_id'], 'request-new')
        state['agent_results'][0].needs_replan = True
        self.assertIsNone((await self.aggregator.aggregator_node(state))['answer_request_id'])

    async def test_repeated_questions_are_distinct_turns(self) -> None:
        history = await self.history_for([self.snapshot('r2'), self.snapshot('r2'),
                                          self.snapshot('r1')])
        self.assertEqual(history, [{'user': 'same question', 'assistant': 'answer-r1'},
                                   {'user': 'same question', 'assistant': 'answer-r2'}])

    async def test_stale_legacy_and_current_answers_excluded(self) -> None:
        rows = [self.snapshot('r1', answer_request_id=None),
                self.snapshot('r2', answer_request_id='r1'), self.snapshot('request-new'),
                self.snapshot('r3', user_input=vars(self.user(request_id='foreign')))]
        self.assertEqual(await self.history_for(rows), [])

    async def test_foreign_or_changed_authorization_history_excluded(self) -> None:
        for field, value in [('user_id', 'B'), ('conversation_id', 'B'),
                             ('role', 'admin'), ('department', 'dept_hr')]:
            with self.subTest(field=field):
                row = self.snapshot('r1', user_input=vars(self.user(request_id='r1',
                                                                  **{field: value})))
                self.assertEqual(await self.history_for([row]), [])

    async def test_object_and_serialized_envelope_history(self) -> None:
        user = self.user(request_id='r1')
        for saved in [user, {'type': 'constructor', 'kwargs': vars(user)}]:
            self.assertEqual(len(await self.history_for([
                self.snapshot('r1', user_input=saved)])), 1)

    async def test_history_limit_and_failure_are_bounded(self) -> None:
        rows = [self.snapshot(str(i)) for i in range(120)]
        self.assertEqual(len(await self.history_for(rows, max_turns=200)), 5)
        self.assertEqual(await self.history_for(rows, max_turns=0), [])
        cp = Record(alist=Mock(side_effect=RuntimeError('unavailable')))
        with self.assertRaises(self.checkpoint_access.CheckpointUnavailable):
            await self.history.load_recent_history('session-a',
                checkpointer=cp, user_input=self.user())
        self.assertEqual(len(await self.history._list_checkpoints(self.saver(rows),
            {'configurable': {'thread_id': 'session-a'}})), 100)

    async def test_synchronous_history_and_missing_identity(self) -> None:
        cp = Record(list=lambda config, limit: iter([self.snapshot('r1')]))
        history = await self.history.load_recent_history('session-a', checkpointer=cp,
                                                        user_input=self.user())
        self.assertEqual(len(history), 1)
        self.assertEqual(await self.history.load_recent_history('session-a', checkpointer=cp), [])
        self.assertEqual(await self.history.load_recent_history('other', checkpointer=cp,
                                                               user_input=self.user()), [])

    def test_dependency_types_reject_before_parser_discards_incomplete_task(self) -> None:
        for value in [['t1'], ['missing'], ['t2'], None, '', {}, 0, False]:
            with self.subTest(value=value), self.assertRaises(self.policy.PlanRejected):
                self.planner._build_subtasks_from_llm([{'type': 'execution',
                                                        'depends_on': value}])

    def test_independent_parser_and_dedup_still_work(self) -> None:
        tasks = self.planner._build_subtasks_from_llm([
            {'type': 'execution', 'desc': '创建 C001 任务', 'depends_on': []},
            {'type': 'execution', 'desc': '创建 C001 任务并通知'}])
        self.assertEqual(len(self.planner._dedup_subtasks(tasks)), 1)
        tasks[0].depends_on = ['t2']
        with self.assertRaises(self.policy.PlanRejected):
            self.planner._dedup_subtasks(tasks)

    def test_dependency_rejection_is_not_swallowed_by_decomposition_fallback(self) -> None:
        self.llm.invoke.return_value = Record(content=json.dumps({'subtasks': [
            {'type': 'knowledge', 'desc': 'lookup'},
            {'type': 'execution', 'desc': 'write', 'depends_on': ['t1']}]}))
        with self.assertRaises(self.policy.PlanRejected):
            self.planner._decompose_tasks('lookup then write')
        prompt = self.llm.invoke.call_args.args[0][0].content
        self.assertIn('overrides any earlier independence instruction', prompt)

    def test_planner_routes_rejection_without_execution_or_replan(self) -> None:
        self.planner._quick_chitchat_check = lambda message: False
        self.planner._invoke_classify = lambda *args: {'intent': 'multi_task'}
        self.llm.invoke.return_value = Record(content='{"subtasks":[{"depends_on":["t1"]}]}')
        state = self.state()
        state.update(self.planner.planner_node(state))
        self.assertEqual(self.dispatch.route_after_planner(state), 'plan_rejected')
        rejected = self.dispatch.plan_rejected_node(state)
        self.assertEqual(rejected['agent_results'], [])
        self.assertEqual(rejected['sources'], [])
        self.assertIn('分别提交', rejected['final_answer'])
        self.assertFalse(rejected['needs_replan'])
        self.assertGreaterEqual(rejected['finished_at'], state['started_at'])
        self.assertGreaterEqual(rejected['total_latency_ms'], 0)
        self.agent_factory.assert_not_called()
        self.assertEqual(self.llm.invoke.call_count, 1)  # decomposition only

    def test_dispatch_rejects_whole_plan_before_any_send_even_chitchat(self) -> None:
        state = self.state()
        state['subtasks'][1].depends_on = ['t1']
        for intent in [self.intent.MULTI_TASK, self.intent.CHITCHAT]:
            state['intent'] = intent
            with patch.object(self.dispatch, 'Send', side_effect=AssertionError('no send')):
                self.assertEqual(self.dispatch.route_after_planner(state), 'plan_rejected')

    def test_replan_uses_same_request_and_history_without_model_calls(self) -> None:
        state = self.state(replan_reason='partial', replan_hint={'query': 'refined'})
        state.update(self.planner.planner_node(state))
        self.assertEqual(state['replan_count'], 1)
        send = self.dispatch.route_after_planner(state)[0]
        self.assertEqual(send.arg['current_subtask'].description, 'refined')
        self.assertEqual(send.arg['history'], state['history'])
        self.assertEqual(send.arg['request_id'], 'request-new')
        self.primary.assert_not_called()

    def test_graph_rejection_is_terminal_and_replan_cap_unchanged(self) -> None:
        graph = self.graph.build_graph()
        self.assertIn('plan_rejected', graph.routes['planner'][1])
        self.assertIn(('plan_rejected', 'end'), graph.edges)
        self.assertNotIn('plan_rejected', graph.routes)
        self.assertEqual(self.graph.route_after_aggregator({'needs_replan': True}), 'planner')
        self.assertEqual(self.graph.route_after_aggregator(
            {'needs_replan': True, 'replan_count': 2}), 'end')

    def test_replaced_saver_cannot_reuse_graph_for_old_history_store(self) -> None:
        first, second = object(), object()
        graph = self.graph.build_graph(first, 'same-backend')
        self.assertIs(graph, self.graph.build_graph(first, 'same-backend'))
        self.assertIsNot(graph, self.graph.build_graph(second, 'same-backend'))

    async def test_both_graph_entries_use_invocation_saver_and_history(self) -> None:
        cp = self.saver([self.snapshot('r1')])
        getter = AsyncMock(return_value=(cp, 'fake'))
        captured = []
        async def invoke(state: dict, **kwargs: Any) -> dict:
            captured.append(state)
            return state
        async def events(state: dict, **kwargs: Any):
            captured.append(state)
            yield {'event': 'on_chain_end', 'metadata': {'langgraph_node': 'plan_rejected'}}
        self.graph.build_graph = Mock(return_value=Record(ainvoke=invoke, astream_events=events))
        with patch.dict(sys.modules, {'app.graph.checkpointer': module(
                'app.graph.checkpointer', get_checkpointer=getter)}):
            await self.graph.run_graph(self.user())
            events_out = [event async for event in self.graph.run_graph_stream(self.user())]
        self.assertEqual(getter.await_count, 2)  # exactly one acquisition per entry
        self.assertEqual(len(captured), 2)
        for state in captured:
            self.assertEqual(state['history'][0]['assistant'], 'answer-r1')
            self.assertEqual(state['final_answer'], '')
        self.assertEqual(events_out[0]['node'], 'plan_rejected')


if __name__ == '__main__':
    sys.dont_write_bytecode = True

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event == 'socket.__new__' and args[1] == 1:
            return  # asyncio wake-up pipe only
        if event.startswith(('socket.', 'subprocess.')) or event in {
            'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod',
        }:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                                or isinstance(args[2], int) and args[2] & 3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')

    sys.addaudithook(guard)
    unittest.main(verbosity=2)
