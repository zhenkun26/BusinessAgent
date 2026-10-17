"""C04 offline adversarial tests; injected dependencies are not HTTP/PostgreSQL evidence."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack, nullcontext
from copy import deepcopy
from enum import Enum
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, **attrs: Any) -> ModuleType:
    result = ModuleType(name)
    result.__dict__.update(attrs)
    return result


def load(name: str, path: str) -> ModuleType:
    source = ROOT / path
    target = ModuleType(name)
    target.__file__ = str(source)
    exec(compile(source.read_bytes(), str(source), 'exec'), target.__dict__)
    return target


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class BaseModel:
    """Attribute-only response fake; deliberately not a Pydantic validation emulator."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class Router:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Any] = {}

    def route(self, method: str, path: str, **kwargs: Any) -> Any:
        def register(fn: Any) -> Any:
            self.routes[method, path] = fn
            return fn
        return register

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.route('GET', path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.route('POST', path, **kwargs)


class Role(str, Enum):
    SALESPERSON = 'salesperson'
    MANAGER = 'manager'
    ADMIN = 'admin'


class Result:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row

    def mappings(self) -> Result:
        return self

    def first(self) -> dict[str, Any] | None:
        return self.row


class Database:
    """Small semantic fixture; asserts guards are in SQL but does not execute SQL."""

    def __init__(self) -> None:
        self.rows = {'session-a': dict(session_id='session-a', user_id='a', status='completed',
                                     original_query='A private query', error=None, completed_at=1)}
        self.feedback: list[dict[str, Any]] = []
        self.drafts: list[dict[str, Any]] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_query = False
        self.fail_write = False
        self.fail_commit = False
        self.change_owner_on_update = False
        self.saved = self.snapshot()

    def snapshot(self) -> Any:
        return deepcopy((self.rows, self.feedback, self.drafts))

    async def execute(self, sql: str, params: dict[str, Any]) -> Result:
        self.calls.append((sql, deepcopy(params)))
        if self.fail_query:
            raise RuntimeError('SYNTHETIC_PRIVATE_DATABASE_CREDENTIAL')
        if sql.startswith('SELECT session_id, user_id, status FROM sessions'):
            assert 'WHERE session_id = :sid AND (user_id = :uid OR :admin_override)' in sql
            row = self.rows.get(params['sid'])
            if row and (row['user_id'] == params['uid'] or params['admin_override']):
                return Result(deepcopy(row))
            return Result()
        if self.fail_write:
            raise RuntimeError('SYNTHETIC_PRIVATE_DATABASE_CREDENTIAL')
        if sql.startswith('UPDATE sessions SET'):
            assert 'WHERE session_id = :sid AND user_id = :uid RETURNING session_id' in sql
            row = self.rows.get(params['sid'])
            if self.change_owner_on_update and row:
                row['user_id'] = 'other-owner'
                self.saved = self.snapshot()  # Simulate a separate committed writer.
            if not row or row['user_id'] != params['uid']:
                return Result()
            row.update(status='running', original_query=params['q'], completed_at=None, error=None)
            return Result({'session_id': params['sid']})
        if sql.startswith('INSERT INTO sessions'):
            assert 'ON CONFLICT (session_id) DO NOTHING RETURNING session_id' in sql
            if params['sid'] in self.rows:
                return Result()
            self.rows[params['sid']] = dict(session_id=params['sid'], user_id=params['uid'],
                                            status='running', original_query=params['q'])
            return Result({'session_id': params['sid']})
        if sql.startswith('INSERT INTO user_feedback'):
            self.feedback.append(deepcopy(params))
        elif sql.startswith('INSERT INTO documents'):
            self.drafts.append(deepcopy(params))
        else:
            raise AssertionError('Unexpected SQL in offline fixture')
        return Result()

    async def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError('SYNTHETIC_PRIVATE_DATABASE_CREDENTIAL')
        self.commits += 1
        self.saved = self.snapshot()

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.rows, self.feedback, self.drafts = deepcopy(self.saved)


class SessionOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stack = ExitStack()
        self.db = Database()
        self.owner = self.user('a')
        self.other = self.user('b')
        self.admin = self.user('admin', 'admin')
        self.audit = SimpleNamespace(log=AsyncMock())
        self.checkpoints = {'session-a': {'final_answer': 'PRIVATE_A_ANSWER', 'confidence': 0.9}}
        self.checkpointer = SimpleNamespace(aget_tuple=AsyncMock(side_effect=self.read_checkpoint))
        self.get_checkpointer = AsyncMock(return_value=(self.checkpointer, 'fake'))
        self.graph = AsyncMock(side_effect=self.run_graph)
        self.stream_calls: list[str] = []
        self.responses: list[Any] = []
        deps = {
            'fastapi': module('fastapi', APIRouter=Router, Depends=lambda dependency: None,
                              HTTPException=HTTPException),
            'fastapi.security': module('fastapi.security', HTTPAuthorizationCredentials=SimpleNamespace),
            'fastapi.responses': module('fastapi.responses', StreamingResponse=self.response),
            'loguru': module('loguru', logger=Mock()),
            'pydantic': module('pydantic', BaseModel=BaseModel, Field=lambda default=None, **kw: default),
            'sqlalchemy': module('sqlalchemy', text=lambda query: query),
            'app.config': module('app.config', get_settings=lambda: SimpleNamespace(kb_feedback_auto_draft=True)),
            'app.core.database': module('app.core.database', get_db=AsyncMock()),
            'app.observability.audit': module('app.observability.audit', get_audit_logger=lambda: self.audit),
            'app.prompts': module('app.prompts', reset_prompt_user=Mock(), set_prompt_user=Mock()),
            'app.security.rbac': module('app.security.rbac', User=SimpleNamespace,
                get_current_user=AsyncMock(), AgentRole=Role, security_scheme=Mock()),
            'app.graph.graph': module('app.graph.graph', run_graph=self.graph,
                                       run_graph_stream=self.run_graph_stream),
            'app.graph.state': module('app.graph.state', UserInput=BaseModel),
            'app.graph.checkpointer': module('app.graph.checkpointer',
                get_checkpointer=self.get_checkpointer, get_checkpointer_backend=lambda: 'fake'),
        }
        self.stack.enter_context(patch.dict(sys.modules, deps))
        self.access = load('c04_access', 'app/security/session_access.py')
        self.runtime = load('c04_runtime', 'app/core/runtime_state.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.core.runtime_state': self.runtime}))
        self.cancellation = load('c04_cancellation', 'app/core/cancellation.py')
        self.lease = SimpleNamespace(watch=lambda **kw: nullcontext(), release=AsyncMock())
        self.cancellation.reserve_session = AsyncMock(return_value=self.lease)
        self.cancel_available = True
        self.pending = Mock(done=lambda: False)

        async def cancel(session_id):
            if session_id == 'session-a' and self.cancel_available:
                self.pending.cancel()
                return True
            return False

        self.cancellation.request_cancel = AsyncMock(side_effect=cancel)
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.security.session_access': self.access, 'app.core.cancellation': self.cancellation,
            'app.security.redaction': load('c04_redaction', 'app/security/redaction.py'),
        }))
        self.chat = load('c04_chat', 'app/api/chat.py')
        self.chat._update_session_status = AsyncMock()
        self.chat._writeback_session_tokens = AsyncMock()

    async def asyncTearDown(self) -> None:
        await asyncio.sleep(0)  # Drain in-memory writeback fakes, no runtime DB calls.
        self.stack.close()

    @staticmethod
    def user(user_id: str, role: str = 'salesperson') -> SimpleNamespace:
        return SimpleNamespace(user_id=user_id, username=user_id, role=role, department='dept_sales')

    async def read_checkpoint(self, config: dict[str, Any]) -> Any:
        state = self.checkpoints.get(config['configurable']['thread_id'])
        return SimpleNamespace(checkpoint={'channel_values': deepcopy(state)}, metadata={}) if state else None

    async def run_graph(self, *, user_input: Any, thread_id: str, **kwargs: Any) -> dict:
        state = {'final_answer': 'authorized answer', 'tokens_used': 0}
        self.checkpoints[thread_id] = state
        return state

    async def run_graph_stream(self, user_input: Any, *, thread_id: str) -> Any:
        self.stream_calls.append(thread_id)
        self.checkpoints[thread_id] = {'final_answer': 'authorized stream answer'}
        yield {'type': 'token', 'data': 'authorized stream answer'}

    def response(self, events: Any, **kwargs: Any) -> Any:
        result = SimpleNamespace(events=events, **kwargs)
        self.responses.append(result)
        return result

    async def call(self, action: str, user: Any, sid: Any = 'session-a') -> Any:
        if action == 'history':
            return await self.chat.get_history(sid, user=user, db=self.db)
        req = SimpleNamespace(session_id=sid, message='synthetic message', feedback_type='dislike',
                              comment='synthetic correction', message_id=None)
        if action in ('message', 'stream'):
            fn = self.chat.send_message if action == 'message' else self.chat.stream_message
            return await fn(req, user=user, db=self.db, credentials=SimpleNamespace(credentials='synthetic'))
        fn = self.chat.submit_feedback if action == 'feedback' else self.chat.cancel_message
        return await fn(req, user=user, db=self.db)

    def assert_no_side_effects(self, before: Any, checkpoint_before: Any,
                               *, reservation_allowed: bool = False) -> None:
        self.assertEqual(self.db.snapshot(), before)
        self.assertEqual(self.checkpoints, checkpoint_before)
        self.graph.assert_not_awaited()
        self.get_checkpointer.assert_not_awaited()
        self.checkpointer.aget_tuple.assert_not_awaited()
        self.audit.log.assert_not_awaited()
        self.chat._update_session_status.assert_not_awaited()
        self.chat._writeback_session_tokens.assert_not_awaited()
        self.pending.cancel.assert_not_called()
        if reservation_allowed:
            self.assertEqual(self.cancellation.reserve_session.await_count,
                             self.lease.release.await_count)
        else:
            self.cancellation.reserve_session.assert_not_awaited()
        self.cancellation.request_cancel.assert_not_awaited()
        self.assertEqual(self.responses, [])
        self.assertEqual(self.stream_calls, [])
        self.assertEqual(self.db.commits, 0)

    async def test_foreign_and_missing_ids_are_indistinguishable_for_every_endpoint(self) -> None:
        before, checkpoints = self.db.snapshot(), deepcopy(self.checkpoints)
        for user in (self.other, self.user('manager', 'manager'), self.admin):
            for action in ('message', 'stream', 'history', 'feedback', 'cancel'):
                if user.role == 'admin' and action == 'cancel':
                    continue
                for sid in ('session-a', 'missing'):
                    with self.subTest(user=user.user_id, action=action, sid=sid):
                        with self.assertRaises(HTTPException) as error:
                            await self.call(action, user, sid)
                        self.assertEqual((error.exception.status_code, error.exception.detail),
                                         (404, 'SESSION_NOT_AVAILABLE'))
        self.assertTrue(all(sql.startswith('SELECT ') for sql, _ in self.db.calls))
        self.assert_no_side_effects(before, checkpoints)

    async def test_reverse_user_direction_is_also_denied(self) -> None:
        self.db.rows['session-b'] = dict(session_id='session-b', user_id='b', status='running')
        before, checkpoints = self.db.snapshot(), deepcopy(self.checkpoints)
        for action in ('message', 'stream', 'history', 'feedback', 'cancel'):
            with self.assertRaises(HTTPException) as error:
                await self.call(action, self.owner, 'session-b')
            self.assertEqual(error.exception.status_code, 404)
        self.assert_no_side_effects(before, checkpoints)

    async def test_empty_and_oversized_ids_do_not_create_sessions(self) -> None:
        before, checkpoints = self.db.snapshot(), deepcopy(self.checkpoints)
        for action in ('message', 'stream', 'history', 'feedback', 'cancel'):
            for sid in ('', 'x' * 65):
                with self.assertRaises(HTTPException) as error:
                    await self.call(action, self.owner, sid)
                self.assertEqual((error.exception.status_code, error.exception.detail),
                                 (404, 'SESSION_NOT_AVAILABLE'))
        self.assertEqual(self.db.calls, [])
        self.assert_no_side_effects(before, checkpoints)

    async def test_id_prefix_and_sql_metacharacters_never_grant_ownership(self) -> None:
        for sid in ('sess_b_12345678', "x' OR 1=1 --"):
            self.db.rows[sid] = dict(session_id=sid, user_id='a', status='completed')
            with self.assertRaises(HTTPException):
                await self.call('history', self.other, sid)
            sql, params = self.db.calls[-1]
            self.assertNotIn(sid, sql)
            self.assertEqual(params['sid'], sid)
        self.get_checkpointer.assert_not_awaited()

    async def test_orphan_checkpoint_cannot_be_read_or_adopted(self) -> None:
        self.checkpoints['orphan'] = {'final_answer': 'ORPHAN_PRIVATE'}
        before, checkpoints = self.db.snapshot(), deepcopy(self.checkpoints)
        for action in ('message', 'stream', 'history', 'feedback'):
            with self.assertRaises(HTTPException):
                await self.call(action, self.owner, 'orphan')
        self.assert_no_side_effects(before, checkpoints)

    async def test_database_query_failure_is_safe_and_closed_on_all_endpoints(self) -> None:
        self.db.fail_query = True
        before, checkpoints = self.db.snapshot(), deepcopy(self.checkpoints)
        for action in ('message', 'stream', 'history', 'feedback', 'cancel'):
            with self.assertRaises(HTTPException) as error:
                await self.call(action, self.owner)
            self.assertEqual((error.exception.status_code, error.exception.detail),
                             (503, 'SESSION_ACCESS_UNAVAILABLE'))
        self.assert_no_side_effects(before, checkpoints)

    async def test_write_or_commit_failure_stops_before_graph_or_stream(self) -> None:
        before, checkpoints = self.db.snapshot(), deepcopy(self.checkpoints)
        for stage in ('fail_write', 'fail_commit'):
            setattr(self.db, stage, True)
            for action in ('message', 'stream'):
                for sid in (None, 'session-a'):
                    with self.assertRaises(HTTPException) as error:
                        await self.call(action, self.owner, sid)
                    self.assertEqual((error.exception.status_code, error.exception.detail),
                                     (503, 'SESSION_ACCESS_UNAVAILABLE'))
                    self.assert_no_side_effects(before, checkpoints, reservation_allowed=True)
            setattr(self.db, stage, False)
        self.assertEqual(self.db.rollbacks, 8)

    async def test_owner_message_preserves_identity_and_runs_authorized_thread(self) -> None:
        result = await self.call('message', self.owner)
        self.assertEqual(result.session_id, 'session-a')
        self.assertEqual(self.db.rows['session-a']['user_id'], 'a')
        self.assertEqual(self.db.commits, 1)
        self.assertEqual(self.graph.await_args.kwargs['thread_id'], 'session-a')
        self.assertEqual(self.graph.await_args.kwargs['user_input'].user_id, 'a')
        self.assertFalse(any(sql.startswith('INSERT INTO sessions') for sql, _ in self.db.calls))

    async def test_owner_stream_authorizes_before_response_and_returns_events(self) -> None:
        response = await self.call('stream', self.owner)
        self.assertEqual(self.db.commits, 1)
        self.assertEqual(response.media_type, 'text/event-stream')
        events = [json.loads(chunk.removeprefix('data: ').strip()) async for chunk in response.events]
        self.assertEqual(events[-1]['type'], 'final')
        self.assertEqual(events[-1]['data']['session_id'], 'session-a')
        self.assertEqual(self.stream_calls, ['session-a'])

    async def test_first_message_and_stream_create_bounded_opaque_ids(self) -> None:
        user = self.user('z' * 64)
        response = await self.call('message', user, None)
        self.assertRegex(response.session_id, r'^sess_[0-9a-f]{32}$')
        self.assertEqual(self.db.rows[response.session_id]['user_id'], user.user_id)
        stream = await self.call('stream', user, None)
        events = [json.loads(chunk.removeprefix('data: ').strip()) async for chunk in stream.events]
        sid = events[-1]['data']['session_id']
        self.assertNotEqual(sid, response.session_id)
        self.assertRegex(sid, r'^sess_[0-9a-f]{32}$')
        self.assertEqual(self.db.rows[sid]['user_id'], user.user_id)

    async def test_generated_id_collision_never_adopts_existing_session(self) -> None:
        sid = 'sess_' + 'a' * 32
        self.db.rows[sid] = dict(session_id=sid, user_id='b', status='completed')
        self.db.saved = self.db.snapshot()
        before, checkpoints = self.db.snapshot(), deepcopy(self.checkpoints)
        with patch.object(self.access.uuid, 'uuid4', return_value=SimpleNamespace(hex='a' * 32)):
            for action in ('message', 'stream'):
                with self.assertRaises(HTTPException) as error:
                    await self.call(action, self.owner, None)
                self.assertEqual((error.exception.status_code, error.exception.detail),
                                 (409, 'SESSION_CREATION_CONFLICT'))
        self.assert_no_side_effects(before, checkpoints)

    async def test_lookup_update_race_cannot_overwrite_new_owner(self) -> None:
        self.db.change_owner_on_update = True
        for action in ('message', 'stream'):
            self.db.rows['session-a']['user_id'] = 'a'
            with self.assertRaises(HTTPException) as error:
                await self.call(action, self.owner)
            self.assertEqual((error.exception.status_code, error.exception.detail),
                             (404, 'SESSION_NOT_AVAILABLE'))
            self.assertEqual(self.db.rows['session-a']['user_id'], 'other-owner')
            self.assertEqual(self.db.rows['session-a']['original_query'], 'A private query')
        self.graph.assert_not_awaited()
        self.audit.log.assert_not_awaited()
        self.assertEqual(self.responses, [])
        self.assertEqual(self.db.commits, 0)

    async def test_owner_history_and_checkpoint_miss_use_authorized_metadata(self) -> None:
        result = await self.call('history', self.owner)
        self.assertEqual(result['final_answer'], 'PRIVATE_A_ANSWER')
        self.checkpointer.aget_tuple.side_effect = None
        self.checkpointer.aget_tuple.return_value = None
        result = await self.call('history', self.owner)
        self.assertFalse(result['found'])
        self.assertEqual(result['session_status'], 'completed')
        self.assertEqual(len(self.db.calls), 2)  # No unguarded second lookup.

    async def test_owner_feedback_locks_then_writes_without_session_placeholder(self) -> None:
        result = await self.call('feedback', self.owner)
        self.assertTrue(result['draft_created'])
        self.assertEqual(len(self.db.feedback), 1)
        self.assertEqual(len(self.db.drafts), 1)
        self.assertEqual(self.db.feedback[0]['uid'], 'a')
        self.assertEqual(self.db.feedback[0]['sid'], 'session-a')
        self.assertTrue(self.db.calls[0][0].endswith(' FOR SHARE'))
        self.assertFalse(any(sql.startswith('INSERT INTO sessions') for sql, _ in self.db.calls))
        self.assertEqual(self.db.commits, 1)

    async def test_owner_positive_feedback_does_not_create_draft(self) -> None:
        req = SimpleNamespace(session_id='session-a', feedback_type='like',
                              comment='', message_id=None)
        result = await self.chat.submit_feedback(req, user=self.owner, db=self.db)
        self.assertFalse(result['draft_created'])
        self.assertEqual(len(self.db.feedback), 1)
        self.assertEqual(self.db.drafts, [])
        self.audit.log.assert_not_awaited()

    async def test_ownership_is_reloaded_for_each_history_request(self) -> None:
        await self.call('history', self.owner)
        self.db.rows['session-a']['user_id'] = 'b'
        with self.assertRaises(HTTPException) as error:
            await self.call('history', self.owner)
        self.assertEqual(error.exception.status_code, 404)
        self.get_checkpointer.assert_awaited_once()

    async def test_owner_and_admin_cancel_only_after_authorization(self) -> None:
        for user in (self.owner, self.admin):
            result = await self.call('cancel', user)
            self.assertTrue(result['cancelled'])
            sql, params = self.db.calls[-1]
            self.assertTrue(sql.endswith(' FOR SHARE'))
            self.assertEqual(params['admin_override'], user.role == 'admin')
        self.assertEqual(self.pending.cancel.call_count, 2)
        self.assertEqual(self.audit.log.await_count, 2)

    async def test_admin_missing_session_is_404_and_owner_idle_cancel_is_false(self) -> None:
        with self.assertRaises(HTTPException) as error:
            await self.call('cancel', self.admin, 'missing')
        self.assertEqual((error.exception.status_code, error.exception.detail),
                         (404, 'SESSION_NOT_AVAILABLE'))
        self.cancel_available = False
        result = await self.call('cancel', self.owner)
        self.assertFalse(result['cancelled'])
        self.audit.log.assert_not_awaited()

    async def test_admin_can_continue_read_and_feedback_on_own_session(self) -> None:
        self.db.rows['session-a']['user_id'] = self.admin.user_id
        for action in ('message', 'history', 'feedback'):
            await self.call(action, self.admin)
        stream = await self.call('stream', self.admin)
        events = [event async for event in stream.events]
        self.assertTrue(events)
        self.assertEqual(self.db.feedback[0]['uid'], 'admin')
        self.assertTrue(all(not params['admin_override'] for sql, params in self.db.calls
                            if sql.startswith('SELECT ')))

    def test_real_api_module_registers_all_five_guarded_routes(self) -> None:
        self.assertEqual(set(self.chat.router.routes), {
            ('POST', '/message'), ('POST', '/stream'), ('POST', '/feedback'),
            ('POST', '/cancel'), ('GET', '/history/{session_id}'),
        })


if __name__ == '__main__':
    def offline_guard(event: str, args: Any) -> None:
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.bind',
                     'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'subprocess.Popen'):
            raise RuntimeError('OFFLINE_TEST_SIDE_EFFECT_DENIED')
        if event == 'open' and isinstance(args[1], str) and any(c in args[1] for c in 'wax+'):
            raise RuntimeError('OFFLINE_TEST_SIDE_EFFECT_DENIED')
    sys.dont_write_bytecode = True
    sys.addaudithook(offline_guard)
    unittest.main(verbosity=2)
