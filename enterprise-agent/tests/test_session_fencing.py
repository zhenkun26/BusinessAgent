"""C10 deterministic stale-writer tests; SQL doubles are not PostgreSQL acceptance."""
from __future__ import annotations

import asyncio
from contextlib import ExitStack, asynccontextmanager
from copy import deepcopy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, **values: Any) -> ModuleType:
    result = ModuleType(name)
    result.__dict__.update(values)
    return result


def load(name: str, path: str) -> ModuleType:
    result = module(name)
    result.__file__ = str(ROOT / path)
    exec(compile((ROOT / path).read_bytes(), str(ROOT / path), "exec"), result.__dict__)
    return result


class Rows:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def mappings(self) -> Rows:
        return self

    def first(self) -> dict | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict]:
        return self.rows


class Store:
    """Transactional semantic double with an explicit clock; does not parse/execute SQL."""
    def __init__(self) -> None:
        self.now = 0
        self.owners: dict[str, tuple[str | None, int | None]] = {}
        self.sessions: dict[str, dict] = {}
        self.published: list[dict] = []
        self.lock = asyncio.Lock()
        self.fail_commit = False
        self.lose_ack = False
        self.expire_on_insert = False
        self.calls: list[str] = []

    def live(self, p: dict) -> bool:
        owner, deadline = self.owners.get(p['sid'], (None, None))
        return owner == p['owner'] and deadline is not None and deadline > self.now

    @asynccontextmanager
    async def transaction(self):
        async with self.lock:
            before = deepcopy((self.owners, self.sessions, self.published))
            try:
                yield self
                if self.fail_commit:
                    raise RuntimeError('SYNTHETIC_COMMIT_FAILURE')
            except BaseException:
                self.owners, self.sessions, self.published = before
                raise
            if self.lose_ack:
                raise RuntimeError('SYNTHETIC_COMMIT_ACK_LOST')

    async def execute(self, statement: str, p: dict) -> Rows:
        sql = ' '.join(statement.split())
        self.calls.append(sql)
        row = {'session_id': p['sid']}
        if sql.startswith('INSERT INTO session_write_fences'):
            assert 'ON CONFLICT (session_id) DO UPDATE' in sql
            assert 'lease_until <= clock_timestamp()' in sql
            owner, deadline = self.owners.get(p['sid'], (None, None))
            if owner is not None and deadline > self.now:
                return Rows([])
            self.owners[p['sid']] = (p['owner'], self.now + p['lease'])
            self.sessions.setdefault(p['sid'], {'status': 'running', 'tokens': 0})
            return Rows([row])
        if sql.startswith('UPDATE session_write_fences SET lease_until'):
            assert 'owner_token = CAST(:owner AS uuid)' in sql
            assert 'lease_until > clock_timestamp()' in sql
            if not self.live(p):
                return Rows([])
            self.owners[p['sid']] = (p['owner'], self.now + p['lease'])
            return Rows([row])
        if sql.startswith('SELECT session_id FROM session_write_fences'):
            assert 'FOR UPDATE' in sql and 'lease_until > clock_timestamp()' in sql
            return Rows([row] if self.live(p) else [])
        if sql.startswith('INSERT INTO session_checkpoint_publications'):
            assert not any(x['sid'] == p['sid'] and x['owner'] == p['owner']
                           for x in self.published)
            self.published.append(deepcopy(p))
            if self.expire_on_insert:
                self.now += 31
            return Rows([])
        if sql.startswith('UPDATE sessions SET status'):
            assert 'EXISTS' in sql and 'owner_token = CAST(:owner AS uuid)' in sql
            assert 'lease_until > clock_timestamp()' in sql and '+ :tokens' in sql
            if not self.live(p):
                return Rows([])
            self.sessions[p['sid']]['status'] = p['status']
            self.sessions[p['sid']]['tokens'] += p['tokens']
            return Rows([row])
        if sql.startswith('UPDATE session_write_fences SET owner_token = NULL'):
            assert 'owner_token = CAST(:owner AS uuid)' in sql
            if self.owners.get(p['sid'], (None, None))[0] == p['owner']:
                self.owners[p['sid']] = (None, None)
            return Rows([])
        if sql.startswith('SELECT backend, thread_id'):
            assert 'ORDER BY publication_id DESC LIMIT :limit' in sql
            return Rows([deepcopy(r) for r in reversed(self.published)
                         if r['sid'] == p['sid']][:p['limit']])
        raise AssertionError('Unexpected SQL')


class SessionFencingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.runtime = load('fence_runtime', 'app/core/runtime_state.py')
        self.stack.enter_context(patch.dict(sys.modules, {
            'sqlalchemy': module('sqlalchemy', text=lambda value: value),
            'app.core.runtime_state': self.runtime,
        }))
        self.fencing = load('c10_fencing', 'app/core/session_fencing.py')
        self.real_transaction = self.fencing.transaction
        self.store = Store()
        self.fencing.transaction = self.store.transaction
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.core.session_fencing': self.fencing,
        }))
        self.access = load('fence_access', 'app/graph/checkpoint_access.py')
        self.a = self.fencing.SessionFence('session', 'a'*32)
        self.b = self.fencing.SessionFence('session', 'b'*32)

    def pointer(self, fence: Any, checkpoint: str = 'final') -> dict:
        return {'backend': 'redis', 'thread_id': fence.thread_id,
                'checkpoint_ns': '', 'checkpoint_id': checkpoint}

    def snapshot(self, checkpoint: str = 'final') -> tuple[Any, Any]:
        user = SimpleNamespace(request_id='request', user_id='u', conversation_id='session',
                               role='salesperson', department='sales')
        return SimpleNamespace(checkpoint={'id': checkpoint, 'channel_values': {
            'user_input': vars(user), 'request_id': user.request_id,
            'final_answer': 'accepted', 'tokens_used': 10}}), user

    async def test_live_owner_rejects_overlap(self) -> None:
        self.assertTrue(await self.a.claim())
        self.assertFalse(await self.b.claim())
        self.assertEqual(self.store.owners['session'][0], self.a.token)

    async def test_expired_owner_cannot_renew_even_without_successor(self) -> None:
        await self.a.claim()
        self.store.now = 30
        self.assertFalse(await self.a.renew())
        self.assertFalse(await self.a.finish('failed'))

    async def test_old_release_and_renew_do_not_affect_successor(self) -> None:
        await self.a.claim()
        self.store.now = 31
        self.assertTrue(await self.b.claim())
        await self.a.release()
        self.assertFalse(await self.a.renew())
        self.assertEqual(self.store.owners['session'][0], self.b.token)

    async def test_delayed_raw_write_cannot_replace_successor_publication(self) -> None:
        raw = {}
        started, resume = asyncio.Event(), asyncio.Event()
        async def old_write():
            started.set()
            await resume.wait()
            raw[self.a.thread_id] = 'late-old'
        await self.a.claim()
        old = asyncio.create_task(old_write())
        await started.wait()
        self.store.now = 31
        await self.b.claim()
        raw[self.b.thread_id] = 'new-answer'
        self.assertTrue(await self.b.finish(
            'completed', tokens=12, publication=self.pointer(self.b)))
        resume.set()
        await old
        self.assertFalse(await self.a.finish(
            'completed', tokens=900, publication=self.pointer(self.a)))
        self.assertEqual(raw[self.store.published[-1]['thread_id']], 'new-answer')
        self.assertEqual(self.store.sessions['session'], {'status': 'completed', 'tokens': 12})

    async def test_all_late_terminal_states_are_rejected(self) -> None:
        await self.a.claim()
        self.store.now = 31
        await self.b.claim()
        for status in ('failed', 'cancelled', 'completed'):
            with self.subTest(status=status):
                self.assertFalse(await self.a.finish(status, tokens=999,
                    publication=self.pointer(self.a) if status == 'completed' else None))
        self.assertEqual(self.store.sessions['session'], {'status': 'running', 'tokens': 0})
        self.assertEqual(self.store.published, [])

    async def test_expiry_between_lock_and_status_rolls_back_publication(self) -> None:
        await self.a.claim()
        self.store.expire_on_insert = True
        with self.assertRaises(self.runtime.RuntimeStateUnavailable):
            await self.a.finish('completed', tokens=10, publication=self.pointer(self.a))
        self.assertEqual(self.store.published, [])
        self.assertEqual(self.store.sessions['session']['tokens'], 0)

    async def test_commit_failure_rolls_back_head_status_and_tokens(self) -> None:
        await self.a.claim()
        self.store.fail_commit = True
        with self.assertRaises(RuntimeError):
            await self.a.finish('completed', tokens=10, publication=self.pointer(self.a))
        self.assertEqual(self.store.published, [])
        self.assertEqual(self.store.sessions['session']['status'], 'running')
        self.assertFalse(self.a.finished)

    async def test_lost_commit_ack_does_not_allow_failure_overwrite(self) -> None:
        await self.a.claim()
        self.store.lose_ack = True
        with self.assertRaises(RuntimeError):
            await self.a.finish('completed', tokens=10, publication=self.pointer(self.a))
        self.store.lose_ack = False
        self.assertFalse(await self.a.finish('failed'))
        self.assertEqual(self.store.sessions['session'], {'status': 'completed', 'tokens': 10})
        self.assertEqual(len(self.store.published), 1)

    async def test_repeated_finish_never_counts_tokens_twice(self) -> None:
        await self.a.claim()
        self.assertTrue(await self.a.finish(
            'completed', tokens=10, publication=self.pointer(self.a)))
        self.assertFalse(await self.a.finish(
            'completed', tokens=10, publication=self.pointer(self.a)))
        self.assertEqual(self.store.sessions['session']['tokens'], 10)

    async def test_other_session_has_independent_ownership(self) -> None:
        await self.a.claim()
        other = self.fencing.SessionFence('other', 'c'*32)
        self.assertTrue(await other.claim())
        self.assertNotEqual(self.a.thread_id, other.thread_id)
        self.assertTrue(await self.a.renew())

    async def test_foreign_thread_backend_and_missing_id_cannot_publish(self) -> None:
        await self.a.claim()
        for field, value in [('thread_id', self.b.thread_id), ('backend', 'unknown'),
                             ('checkpoint_id', ''), ('checkpoint_ns', 'foreign')]:
            with self.subTest(field=field):
                p = self.pointer(self.a); p[field] = value
                with self.assertRaises(self.runtime.RuntimeStateUnavailable):
                    await self.a.finish('completed', publication=p)
        self.assertEqual(self.store.published, [])

    async def test_context_absent_foreign_finished_and_reset_fail_closed(self) -> None:
        for sid in ('session', 'other'):
            with self.assertRaises(self.runtime.RuntimeStateUnavailable):
                self.fencing.active_fence(sid)
        with self.a.scope():
            self.assertIs(self.fencing.active_fence('session'), self.a)
            with self.assertRaises(self.runtime.RuntimeStateUnavailable):
                self.fencing.active_fence('other')
            self.a.finished = True
            with self.assertRaises(self.runtime.RuntimeStateUnavailable):
                self.fencing.active_fence('session')
        self.assertIsNone(self.fencing._current.get())

    async def test_publish_reads_physical_thread_and_freezes_exact_id(self) -> None:
        await self.a.claim()
        item, user = self.snapshot()
        cp = SimpleNamespace(aget_tuple=AsyncMock(return_value=item))
        state = await self.access.publish_checkpoint(cp, 'redis', self.a, user)
        cp.aget_tuple.assert_awaited_once_with(self.a.config)
        self.assertEqual(state['final_answer'], 'accepted')
        self.assertEqual(self.store.published[-1]['checkpoint_id'], 'final')

    async def test_final_read_after_takeover_never_publishes_old_run(self) -> None:
        await self.a.claim()
        item, user = self.snapshot()
        async def read(config):
            self.store.now = 31
            await self.b.claim()
            return item
        with self.assertRaises(self.runtime.RuntimeStateUnavailable):
            await self.access.publish_checkpoint(
                SimpleNamespace(aget_tuple=read), 'redis', self.a, user)
        self.assertEqual(self.store.published, [])

    async def test_publication_reads_exact_id_not_latest_or_orphan(self) -> None:
        await self.a.claim()
        await self.a.finish('completed', publication=self.pointer(self.a))
        item, _ = self.snapshot()
        cp = SimpleNamespace(aget_tuple=AsyncMock(return_value=item))
        self.assertIs(await self.access.read_session_checkpoint(cp, 'session', 'redis'), item)
        self.assertEqual(cp.aget_tuple.await_args.args[0]['configurable'], {
            'thread_id': self.a.thread_id, 'checkpoint_ns': '', 'checkpoint_id': 'final'})

    async def test_missing_mismatched_backend_and_wrong_id_fail_without_fallback(self) -> None:
        await self.a.claim()
        await self.a.finish('completed', publication=self.pointer(self.a))
        for backend, item in [('postgres', self.snapshot()[0]), ('redis', None),
                              ('redis', self.snapshot('other-id')[0])]:
            cp = SimpleNamespace(aget_tuple=AsyncMock(return_value=item))
            with self.assertRaises(self.access.CheckpointUnavailable):
                await self.access.read_session_checkpoint(cp, 'session', backend)
            self.assertLessEqual(cp.aget_tuple.await_count, 1)

    async def test_pre_v8_history_is_read_only_and_no_publication_is_invented(self) -> None:
        item, _ = self.snapshot()
        cp = SimpleNamespace(aget_tuple=AsyncMock(return_value=item))
        self.assertIs(await self.access.read_session_checkpoint(cp, 'session', 'redis'), item)
        cp.aget_tuple.assert_awaited_once_with({'configurable': {'thread_id': 'session'}})
        self.assertEqual(self.store.published, [])

    async def test_adapter_sanitizes_database_errors_without_retry(self) -> None:
        from unittest.mock import Mock
        factory = Mock(side_effect=RuntimeError('PRIVATE_DSN'))
        with patch.dict(sys.modules, {'app.core.database': module('app.core.database',
                get_session_factory=lambda: factory)}):
            # Synchronous factory failure before any context is entered.
            with self.assertRaisesRegex(self.runtime.RuntimeStateUnavailable,
                                        '^RUNTIME_STATE_UNAVAILABLE$'):
                async with self.real_transaction():
                    self.fail('must not enter')
        factory.assert_called_once_with()

    async def test_publication_history_has_one_aggregate_timeout(self) -> None:
        async def stalled(*args):
            await asyncio.Event().wait()
        with patch.object(self.fencing, 'publications', stalled), \
                patch.object(self.access, 'READ_TIMEOUT_SECONDS', 0.01):
            with self.assertRaises(self.access.CheckpointUnavailable):
                await self.access.published_checkpoints(None, 'session', 'redis')

    async def test_api_message_has_no_success_when_publication_is_rejected(self) -> None:
        c04 = load('fence_message_c04', 'tests/test_session_ownership.py')
        case = c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            async def reject(*args, **kw):
                raise case.runtime.RuntimeStateUnavailable()
            case.chat.publish_checkpoint = reject
            with self.assertRaises(c04.HTTPException) as caught:
                await case.call('message', case.owner)
            self.assertEqual(caught.exception.status_code, 503)
            self.assertEqual(caught.exception.detail, 'RUNTIME_STATE_UNAVAILABLE')
        finally:
            await case.asyncTearDown()

    async def test_stale_owner_cannot_start_or_change_session_metadata(self) -> None:
        c04 = load('fence_start_c04', 'tests/test_session_ownership.py')
        case = c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            before = case.db.snapshot()
            fence = SimpleNamespace(session_id='session-a', token='a'*32,
                                    lock_owner=AsyncMock(return_value=False))
            with self.assertRaises(c04.HTTPException) as caught:
                await case.access.prepare_chat_session(case.db, case.owner,
                    'session-a', 'late replacement', fence=fence)
            self.assertEqual(caught.exception.status_code, 503)
            self.assertEqual(case.db.snapshot(), before)
        finally:
            await case.asyncTearDown()

    async def test_pg_claim_refusal_releases_only_new_redis_token(self) -> None:
        c09 = load('fence_admission_c09', 'tests/test_cross_process_state.py')
        case = c09.CrossProcessStateFixture()
        case.setUp()
        try:
            case.cancel_a.SessionFence = self.fencing.SessionFence
            await self.a.claim()
            with self.assertRaises(case.cancel_a.SessionBusy):
                await case.cancel_a.reserve_session('session')
            self.assertEqual(self.store.owners['session'][0], self.a.token)
            self.store.now = 31
            lease = await case.cancel_a.reserve_session('session')
            self.assertEqual(self.store.owners['session'][0], lease.token)
            await lease.release()
        finally:
            case.doCleanups()

    async def test_pg_expiry_cancels_work_even_when_redis_renews(self) -> None:
        c09 = load('fence_heartbeat_c09', 'tests/test_cross_process_state.py')
        case = c09.CrossProcessStateFixture()
        case.setUp()
        try:
            case.cancel_a.SessionFence = self.fencing.SessionFence
            lease = await case.cancel_a.reserve_session('session')
            self.store.now = 31
            entered = asyncio.Event()
            task = asyncio.create_task(case.owned(lease, entered))
            with self.assertRaises(case.runtime_a.RuntimeStateUnavailable):
                await asyncio.wait_for(task, 1)
            self.assertTrue(lease.failed)
        finally:
            case.doCleanups()

    async def test_swallowed_cancellation_cannot_publish_success(self) -> None:
        c04 = load('fence_cancel_c04', 'tests/test_session_ownership.py')
        case = c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            lease = case.cancellation.CancellationLease('session', 'a'*32)
            lease.cancel_requested = True
            case.lease.ensure_active = lease.ensure_active
            result = await case.call('message', case.owner)
            self.assertEqual(result.intent, 'cancelled')
            case.lease.fence.finish.assert_not_awaited()
        finally:
            await case.asyncTearDown()

    async def test_api_stream_has_no_final_when_publication_is_rejected(self) -> None:
        c04 = load('fence_c04', 'tests/test_session_ownership.py')
        case = c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            response = await case.call('stream', case.owner)
            case.lease.fence.finish.return_value = False
            output = ''.join([event async for event in response.events])
            self.assertNotIn('"type": "final"', output)
            self.assertIn('RUNTIME_STATE_UNAVAILABLE', output)
        finally:
            await case.asyncTearDown()

    async def test_graph_entries_reject_unowned_persistence(self) -> None:
        c08 = load('fence_c08', 'tests/test_request_context.py')
        case = c08.RequestContextTests()
        case.setUp()
        try:
            with patch.dict(sys.modules, {
                'app.core.session_fencing': self.fencing,
                'app.graph.checkpointer': module('app.graph.checkpointer',
                    get_checkpointer=AsyncMock(return_value=(None, 'memory'))),
            }), patch.object(case.graph, 'build_graph') as build:
                with self.assertRaises(self.runtime.RuntimeStateUnavailable):
                    await case.graph.run_graph(case.user())
                with self.assertRaises(self.runtime.RuntimeStateUnavailable):
                    _ = [event async for event in case.graph.run_graph_stream(case.user())]
                self.assertFalse(build.return_value.ainvoke.called)
                self.assertFalse(build.return_value.astream_events.called)
        finally:
            case.doCleanups()

    async def test_both_graph_entries_write_only_the_owned_physical_thread(self) -> None:
        from unittest.mock import Mock
        c08 = load('fence_graph_c08', 'tests/test_request_context.py')
        case = c08.RequestContextFixture()
        case.setUp()
        captured = []
        async def invoke(state, *, config):
            captured.append(config)
            return state
        async def events(state, *, config, version):
            captured.append(config)
            yield {'event': 'on_chain_end', 'metadata': {'langgraph_node': 'plan_rejected'}}
        try:
            fence = self.fencing.SessionFence('session-a', 'd'*32)
            with patch.dict(sys.modules, {
                'app.core.session_fencing': self.fencing,
                'app.graph.checkpointer': module('app.graph.checkpointer',
                    get_checkpointer=AsyncMock(return_value=(case.saver([]), 'redis'))),
            }), patch.object(case.graph, 'build_graph', Mock(return_value=SimpleNamespace(
                    ainvoke=invoke, astream_events=events))), fence.scope():
                await case.graph.run_graph(case.user())
                _ = [event async for event in case.graph.run_graph_stream(case.user())]
            self.assertEqual(captured, [fence.config, fence.config])
            self.assertNotEqual(fence.thread_id, 'session-a')
        finally:
            case.doCleanups()

    async def test_history_combines_accepted_turns_with_read_only_legacy(self) -> None:
        from unittest.mock import Mock
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.graph.checkpoint_access': self.access,
        }))
        history = load('fence_history', 'app/graph/history.py')
        with patch.dict(sys.modules, {
            'app.graph.checkpoint_access': self.access,
            'app.core.session_fencing': self.fencing,
        }), patch.object(history, 'logger', Mock()):
            items = {}
            for fence, request in [(self.a, 'old'), (self.b, 'new')]:
                await fence.claim()
                item, user = self.snapshot(request)
                values = item.checkpoint['channel_values']
                values.update(request_id=request, answer_request_id=request,
                              final_answer='answer-'+request)
                values['user_input'].update(request_id=request, message='question-'+request)
                items[request] = item
                await fence.finish('completed', publication=self.pointer(fence, request))
            legacy = deepcopy(items['old'])
            legacy.checkpoint['channel_values'].update(request_id='legacy',
                answer_request_id='legacy', final_answer='legacy-answer')
            legacy.checkpoint['channel_values']['user_input'].update(
                request_id='legacy', message='legacy-question')
            async def alist(config, limit):
                self.assertEqual(config, {'configurable': {'thread_id': 'session'}})
                yield legacy
            async def get(config):
                return items[config['configurable']['checkpoint_id']]
            cp = SimpleNamespace(aget_tuple=get, alist=alist)
            _, current = self.snapshot()
            result = await history.load_recent_history('session', checkpointer=cp,
                                                       user_input=current, backend='redis')
            self.assertEqual([row['assistant'] for row in result],
                             ['legacy-answer', 'answer-old', 'answer-new'])


if __name__ == '__main__':
    sys.dont_write_bytecode = True

    def guard(event: str, args: tuple) -> None:
        if event == 'socket.__new__' and args[1] == 1:
            return
        if event.startswith(('socket.', 'subprocess.', 'ctypes.')) or event in {
            'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod',
            'os.chown', 'os.truncate', 'os.utime', 'os.link', 'os.symlink',
        }:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                                or isinstance(args[2], int) and args[2] & 3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')

    # loguru is substituted before importing actual-source runtime helpers.
    sys.modules['loguru'] = module('loguru', logger=SimpleNamespace(warning=lambda *a: None))
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
