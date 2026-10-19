"""C10 actual-source lifecycle/failure checks, without installed savers or services."""

from __future__ import annotations

import ast
import asyncio
from contextlib import ExitStack, asynccontextmanager
from copy import deepcopy
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
    result = module(name)
    result.__file__ = str(ROOT / path)
    exec(compile((ROOT / path).read_bytes(), str(ROOT / path), 'exec'), result.__dict__)
    return result


class CheckpointDurabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.access = load('c10_access', 'app/graph/checkpoint_access.py')
        self.settings = SimpleNamespace(
            checkpoint_backend='redis', checkpoint_ttl_days=7,
            app_env='prod', redis_url='redis://synthetic.invalid', postgres_host='synthetic.invalid',
            postgres_port=5432, postgres_user='synthetic', postgres_password="synthetic:@' secret",
            postgres_db='synthetic')
        self.saver = SimpleNamespace(asetup=AsyncMock(), setup=AsyncMock(),
            aget_tuple=AsyncMock(return_value=None), __aexit__=AsyncMock())
        self.redis_factory = Mock(return_value=self.saver)
        self.memory_factory = Mock(return_value=self.saver)
        self.pg_open = Mock()
        self.pg_close = Mock()
        self.make_conninfo = Mock(return_value='synthetic-conninfo')
        self.reset_graph = Mock()
        self.log = Mock()

        @asynccontextmanager
        async def pg_context(info: str):
            self.pg_open(info)
            try:
                yield self.saver
            finally:
                self.pg_close()

        self.pg_context = Mock(side_effect=pg_context)
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.config': module('app.config', get_settings=lambda: self.settings),
            'app.graph.checkpoint_access': self.access,
            'app.graph.graph': module('app.graph.graph', reset_graph=self.reset_graph),
            'loguru': module('loguru', logger=self.log),
            'langgraph.checkpoint.redis.aio': module('langgraph.checkpoint.redis.aio',
                AsyncRedisSaver=self.redis_factory),
            'langgraph.checkpoint.postgres.aio': module('langgraph.checkpoint.postgres.aio',
                AsyncPostgresSaver=SimpleNamespace(from_conn_string=self.pg_context)),
            'langgraph.checkpoint.memory': module('langgraph.checkpoint.memory',
                MemorySaver=self.memory_factory),
            'psycopg.conninfo': module('psycopg.conninfo', make_conninfo=self.make_conninfo),
            'redis.backoff': module('redis.backoff', NoBackoff=Mock()),
            'redis.retry': module('redis.retry', Retry=Mock()),
        }))
        self.cp = load('c10_checkpointer', 'app/graph/checkpointer.py')
        self.history = load('c10_history', 'app/graph/history.py')
        self.c04 = load('c10_c04', 'tests/test_session_ownership.py')
        self.c08 = load('c10_c08', 'tests/test_request_context.py')

    async def asyncTearDown(self) -> None:
        await self.cp.reset_checkpointer()

    async def test_concurrent_initialization_publishes_one_probed_instance(self) -> None:
        results = await asyncio.gather(*(self.cp.get_checkpointer() for _ in range(20)))
        self.assertTrue(all(result == (self.saver, 'redis') for result in results))
        self.redis_factory.assert_called_once()
        self.saver.aget_tuple.assert_awaited_once()
        self.saver.__aexit__.assert_not_awaited()

    async def test_redis_setup_failure_closes_without_fallback(self) -> None:
        self.saver.asetup.side_effect = RuntimeError('PRIVATE_DSN')
        with self.assertRaisesRegex(self.access.CheckpointUnavailable, '^CHECKPOINT_UNAVAILABLE$'):
            await self.cp.get_checkpointer()
        self.saver.__aexit__.assert_awaited_once()
        self.pg_context.assert_not_called()
        self.memory_factory.assert_not_called()
        self.assertIsNone(self.cp.get_checkpointer_backend())
        self.assertNotIn('PRIVATE_DSN', str(self.log.mock_calls))

    async def test_probe_failure_is_not_suppressed_and_later_init_can_retry(self) -> None:
        self.saver.aget_tuple.side_effect = RuntimeError('PRIVATE_DSN')
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.cp.get_checkpointer()
        self.saver.__aexit__.assert_awaited_once()
        self.saver.aget_tuple.side_effect = None
        self.assertEqual((await self.cp.get_checkpointer())[1], 'redis')
        self.assertEqual(self.redis_factory.call_count, 2)

    async def test_initialization_timeout_closes_and_does_not_publish(self) -> None:
        async def hang():
            await asyncio.Event().wait()
        self.saver.asetup.side_effect = hang
        self.cp.INIT_TIMEOUT_SECONDS = .001
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.cp.get_checkpointer()
        self.saver.__aexit__.assert_awaited_once()
        self.assertIsNone(self.cp.get_checkpointer_backend())

    async def test_initialization_cancel_closes_and_preserves_cancel(self) -> None:
        started = asyncio.Event()
        async def hang():
            started.set()
            await asyncio.Event().wait()
        self.saver.asetup.side_effect = hang
        task = asyncio.create_task(self.cp.get_checkpointer())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.saver.__aexit__.assert_awaited_once()
        self.assertIsNone(self.cp.get_checkpointer_backend())

    async def test_cached_runtime_failure_does_not_replace_store_or_retry(self) -> None:
        await self.cp.get_checkpointer()
        self.saver.aget_tuple.side_effect = RuntimeError('PRIVATE_DSN')
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.access.read_checkpoint(self.saver, {})
        self.assertEqual(await self.cp.get_checkpointer(), (self.saver, 'redis'))
        self.redis_factory.assert_called_once()
        self.pg_context.assert_not_called()
        self.memory_factory.assert_not_called()

    async def test_cached_backend_never_switches_on_configuration_change(self) -> None:
        await self.cp.get_checkpointer()
        self.settings.checkpoint_backend = 'postgres'
        self.assertEqual((await self.cp.get_checkpointer())[1], 'redis')
        self.pg_context.assert_not_called()

    async def test_close_is_idempotent_and_invalidates_graph_cache(self) -> None:
        await self.cp.get_checkpointer()
        await self.cp.reset_checkpointer()
        await self.cp.reset_checkpointer()
        self.saver.__aexit__.assert_awaited_once()
        self.reset_graph.assert_called()
        self.assertIsNone(self.cp.get_checkpointer_backend())

    async def test_close_failure_does_not_leak_or_mask(self) -> None:
        await self.cp.get_checkpointer()
        self.saver.__aexit__.side_effect = RuntimeError('PRIVATE_DSN')
        await self.cp.reset_checkpointer()
        self.log.warning.assert_called_with('CHECKPOINT_CLOSE_FAILED')
        self.assertIsNone(self.cp.get_checkpointer_backend())

    async def test_unknown_and_non_dev_memory_denied_before_factory(self) -> None:
        for backend, env in [('unknown', 'dev'), ('memory', 'prod'), ('memory', 'test')]:
            self.settings.checkpoint_backend, self.settings.app_env = backend, env
            with self.assertRaises(self.access.CheckpointUnavailable):
                await self.cp.get_checkpointer()
        self.memory_factory.assert_not_called()
        self.redis_factory.assert_not_called()

    async def test_explicit_dev_memory_warns_and_never_claims_durability(self) -> None:
        self.settings.checkpoint_backend, self.settings.app_env = 'memory', 'dev'
        self.assertEqual((await self.cp.get_checkpointer())[1], 'memory')
        self.log.warning.assert_called_with('CHECKPOINT_MEMORY_NON_DURABLE')
        self.redis_factory.assert_not_called()

    async def test_postgres_context_stays_open_and_runtime_never_runs_ddl(self) -> None:
        self.settings.checkpoint_backend = 'postgres'
        self.assertEqual((await self.cp.get_checkpointer())[1], 'postgres')
        self.pg_open.assert_called_once_with('synthetic-conninfo')
        self.pg_close.assert_not_called()
        self.saver.setup.assert_not_awaited()
        self.saver.asetup.assert_not_awaited()
        self.assertEqual(self.make_conninfo.call_args.kwargs['password'],
                         self.settings.postgres_password)
        await self.cp.reset_checkpointer()
        self.pg_close.assert_called_once()

    async def test_postgres_probe_failure_closes_without_redis_or_memory(self) -> None:
        self.settings.checkpoint_backend = 'postgres'
        self.saver.aget_tuple.side_effect = RuntimeError('PRIVATE_DSN')
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.cp.get_checkpointer()
        self.pg_close.assert_called_once()
        self.redis_factory.assert_not_called()
        self.memory_factory.assert_not_called()

    async def test_postgres_provisioning_uses_setup_and_closes_without_publication(self) -> None:
        self.settings.checkpoint_backend = 'postgres'
        await self.cp.setup_postgres()
        self.saver.setup.assert_awaited_once()
        self.saver.asetup.assert_not_awaited()
        self.pg_close.assert_called_once()
        self.assertIsNone(self.cp.get_checkpointer_backend())

    async def test_provisioning_failure_closes_and_never_publishes(self) -> None:
        self.settings.checkpoint_backend = 'postgres'
        self.saver.setup.side_effect = RuntimeError('PRIVATE_DSN')
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.cp.setup_postgres()
        self.pg_close.assert_called_once()
        self.assertIsNone(self.cp.get_checkpointer_backend())

    def test_cli_without_execute_never_initializes_a_store(self) -> None:
        with patch.object(sys, 'argv', ['checkpointer', 'setup-postgres']), patch('builtins.print'):
            self.assertEqual(self.cp.main(), 2)
        self.pg_context.assert_not_called()

    async def test_wrong_backend_provisioning_rejected(self) -> None:
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.cp.setup_postgres()
        self.pg_context.assert_not_called()

    async def test_redis_ttl_and_connection_bounds_reach_adapter(self) -> None:
        await self.cp.get_checkpointer()
        options = self.redis_factory.call_args.kwargs
        self.assertEqual(options['ttl'], {'default_ttl': 10080, 'refresh_on_read': True})
        self.assertEqual(options['connection_args']['socket_timeout'], 5)
        for days in (0, -1):
            self.settings.checkpoint_ttl_days = days
            self.assertIsNone(self.cp._redis_ttl_config())

    async def test_bounded_read_distinguishes_absence_failure_timeout_and_cancel(self) -> None:
        self.assertIsNone(await self.access.read_checkpoint(self.saver, {}))
        self.saver.aget_tuple.side_effect = RuntimeError('PRIVATE_DSN')
        with self.assertRaisesRegex(self.access.CheckpointUnavailable, '^CHECKPOINT_UNAVAILABLE$'):
            await self.access.read_checkpoint(self.saver, {})
        async def hang(config):
            await asyncio.Event().wait()
        self.saver.aget_tuple.side_effect = hang
        self.access.READ_TIMEOUT_SECONDS = .001
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.access.read_checkpoint(self.saver, {})
        self.saver.aget_tuple.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.access.read_checkpoint(self.saver, {})

    def snapshot(self) -> tuple[Any, Any]:
        user = SimpleNamespace(request_id='new', user_id='a', conversation_id='s',
                               role='salesperson', department='sales')
        return SimpleNamespace(checkpoint={'channel_values': {
            'request_id': 'new', 'answer_request_id': 'new', 'user_input': vars(user),
            'final_answer': 'current answer'}}), user

    def test_final_snapshot_accepts_current_identity_and_serialization_envelope(self) -> None:
        tup, user = self.snapshot()
        self.assertEqual(self.access.completed_state(tup, user)['final_answer'], 'current answer')
        state = tup.checkpoint['channel_values']
        state['user_input'] = {'type': 'constructor', 'kwargs': vars(user)}
        self.assertEqual(self.access.completed_state(tup, user), state)
        state['answer_request_id'] = None  # Explicit plan rejection is a fresh terminal response.
        self.assertEqual(self.access.completed_state(tup, user), state)

    def test_final_snapshot_rejects_missing_old_and_foreign_state(self) -> None:
        tup, user = self.snapshot()
        bad = [None, SimpleNamespace(checkpoint={})]
        for key in ('request_id', 'user_id', 'conversation_id', 'role', 'department'):
            altered = deepcopy(tup)
            altered.checkpoint['channel_values']['user_input'][key] = 'foreign'
            bad.append(altered)
        for key, value in [('request_id', 'old'), ('answer_request_id', 'old'),
                           ('final_answer', ''), ('final_answer', None)]:
            altered = deepcopy(tup)
            altered.checkpoint['channel_values'][key] = value
            bad.append(altered)
        for item in bad:
            with self.assertRaises(self.access.CheckpointUnavailable):
                self.access.completed_state(item, user)

    async def test_history_failure_stops_both_graph_entries_before_model(self) -> None:
        case = self.c08.RequestContextTests()
        case.setUp()
        try:
            cp = SimpleNamespace(alist=Mock(side_effect=RuntimeError('PRIVATE_DSN')))
            graph = SimpleNamespace(ainvoke=AsyncMock(), astream_events=Mock())
            getter = AsyncMock(return_value=(cp, 'redis'))
            with patch.dict(sys.modules, {'app.graph.checkpointer': module(
                    'app.graph.checkpointer', get_checkpointer=getter)}), \
                    patch.object(case.graph, 'build_graph', return_value=graph):
                with self.assertRaises(case.checkpoint_access.CheckpointUnavailable):
                    await case.graph.run_graph(case.user())
                with self.assertRaises(case.checkpoint_access.CheckpointUnavailable):
                    async for _ in case.graph.run_graph_stream(case.user()):
                        pass
                graph.ainvoke.assert_not_awaited()
                graph.astream_events.assert_not_called()
        finally:
            case.doCleanups()

    async def test_runtime_write_error_propagates_without_graph_retry(self) -> None:
        case = self.c08.RequestContextTests()
        case.setUp()
        try:
            graph = SimpleNamespace(ainvoke=AsyncMock(side_effect=RuntimeError('write failed')))
            with patch.dict(sys.modules, {'app.graph.checkpointer': module(
                    'app.graph.checkpointer',
                    get_checkpointer=AsyncMock(return_value=(None, 'redis')))}), \
                    patch.object(case.graph, 'build_graph', return_value=graph):
                with self.assertRaisesRegex(RuntimeError, 'write failed'):
                    await case.graph.run_graph(case.user())
                graph.ainvoke.assert_awaited_once()
        finally:
            case.doCleanups()

    async def test_message_and_history_persistence_errors_return_503(self) -> None:
        case = self.c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            error = case.checkpoint_access.CheckpointUnavailable()
            case.graph.side_effect = error
            case.get_checkpointer.side_effect = error
            for action in ('message', 'history'):
                with self.assertRaises(self.c04.HTTPException) as result:
                    await case.call(action, case.owner)
                self.assertEqual((result.exception.status_code, result.exception.detail),
                                 (503, 'CHECKPOINT_UNAVAILABLE'))
        finally:
            await case.asyncTearDown()

    async def test_stream_missing_stale_and_unreachable_checkpoint_never_emit_final(self) -> None:
        case = self.c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            for kind in ('missing', 'stale', 'unreachable'):
                case.checkpointer.aget_tuple.side_effect = None
                case.checkpointer.aget_tuple.return_value = None
                if kind == 'stale':
                    case.checkpointer.aget_tuple.return_value = self.snapshot()[0]
                elif kind == 'unreachable':
                    case.checkpointer.aget_tuple.side_effect = RuntimeError('PRIVATE_DSN')
                response = await case.call('stream', case.owner)
                events = ''.join([event async for event in response.events])
                self.assertIn('CHECKPOINT_UNAVAILABLE', events)
                self.assertNotIn('"type": "final"', events)
                self.assertNotIn('PRIVATE_DSN', events)
                self.assertEqual(case.chat._update_session_status.await_args.args[1], 'failed')
        finally:
            await case.asyncTearDown()

    async def test_api_startup_failure_closes_database_without_yield(self) -> None:
        await self.check_lifespan(fail=True)

    async def test_api_shutdown_closes_saver_before_database(self) -> None:
        await self.check_lifespan(fail=False)

    async def check_lifespan(self, fail: bool) -> None:
        settings = SimpleNamespace(app_env='prod', embedding_model='remote', reranker_model='remote')
        events = []
        async def init_cp():
            events.append('checkpoint_open')
            if fail:
                raise self.access.CheckpointUnavailable()
        async def close_cp():
            events.append('checkpoint_close')
        async def close_db():
            events.append('database_close')
        deps = {
            'app.rag.model_profile': module(
                'app.rag.model_profile', verify_model_startup=AsyncMock()),
            'app.observability.tracing': module('app.observability.tracing',
                init_tracing=lambda **kw: False, instrument_fastapi=Mock()),
            'app.graph.checkpointer': module('app.graph.checkpointer',
                get_checkpointer=init_cp, reset_checkpointer=close_cp),
            'app.core.database': module('app.core.database', close_db=close_db),
            'app.observability.service': module('app.observability.service', replay_loop=AsyncMock()),
            'app.observability.audit': module('app.observability.audit', init_audit_logger=Mock()),
            'app.tools.base': module('app.tools.base', init_all_tools=Mock()),
            'app.prompts': module('app.prompts', refresh_prompt_cache=AsyncMock(),
                                  sync_prompt_defaults=AsyncMock()),
        }
        tree = ast.parse((ROOT / 'app/main.py').read_text())
        node = next(n for n in tree.body if getattr(n, 'name', None) == 'lifespan')
        ns = dict(asyncio=asyncio, asynccontextmanager=asynccontextmanager, get_settings=lambda: settings,
                  validate_production_settings=lambda _: [], logger=self.log,
                  init_db=AsyncMock(), init_milvus=AsyncMock())
        source = 'from __future__ import annotations\n' + ast.unparse(node)
        exec(compile(source, 'lifespan', 'exec'), ns)
        with patch.dict(sys.modules, deps):
            if fail:
                with self.assertRaises(self.access.CheckpointUnavailable):
                    async with ns['lifespan'](None):
                        self.fail('Startup must not yield on saver failure')
            else:
                async with ns['lifespan'](None):
                    self.assertEqual(events, ['checkpoint_open'])
        self.assertEqual(events, ['checkpoint_open', 'checkpoint_close', 'database_close'])


if __name__ == '__main__':
    sys.dont_write_bytecode = True

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event == 'socket.__new__' and args[1] == 1:
            return  # asyncio wake-up pipes only
        if event.startswith(('socket.', 'subprocess.', 'ctypes.')) or event in {
            'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod',
            'os.chown', 'os.truncate', 'os.utime', 'os.link', 'os.symlink', 'os.exec',
            'os.posix_spawn', 'os.fork', 'os.forkpty', 'os.putenv', 'os.unsetenv',
        }:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                                or isinstance(args[2], int) and args[2] & 3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')

    sys.addaudithook(guard)
    unittest.main(verbosity=2)
