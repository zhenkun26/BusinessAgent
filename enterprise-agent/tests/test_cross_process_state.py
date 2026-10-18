"""C09 offline contracts: separate module instances, shared doubles, no real services."""

from __future__ import annotations

import ast
import asyncio
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import secrets
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urlencode, urlsplit, urlunsplit

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


class RedisFailure(Exception):
    pass


class Store:
    """Atomic command double, not a Lua interpreter or Redis TTL implementation."""
    def __init__(self) -> None:
        self.values = {}
        self.expiry = {}
        self.now = 0
        self.fail = False
        self.options = []
        self.calls = []
        self.closes = 0

    def check(self) -> None:
        if self.fail:
            raise RedisFailure('PRIVATE_CONNECTION_DETAILS')

    def get(self, key: str) -> Any:
        self.check()
        if self.expiry.get(key, float('inf')) <= self.now:
            self.values.pop(key, None)
        return self.values.get(key)

    async def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        if nx and self.get(key) is not None:
            return False
        self.values[key], self.expiry[key] = value, self.now + ex
        self.calls.append(('set', key, ex))
        return True

    async def getdel(self, key: str) -> Any:
        value = self.get(key)
        self.values.pop(key, None)
        self.calls.append(('getdel', key))
        return value

    async def eval(self, script: str, count: int, *args: Any) -> int:
        self.check()
        assert count == 2
        run, cancel, *argv = args
        self.calls.append(('eval', script, args))
        if "local owner" in script:
            owner = self.get(run)
            if owner is None:
                return 0
            await self.set(cancel, owner, nx=False, ex=int(argv[0]))
            return 1
        if "'EXPIRE'" in script:
            if self.get(run) != argv[0]:
                return 0
            self.expiry[run] = self.now + int(argv[1])
            return 2 if self.get(cancel) == argv[0] else 1
        assert "'DEL'" in script
        for key in (run, cancel):
            if self.get(key) == argv[0]:
                self.values.pop(key, None)
        return 1

    async def aclose(self) -> None:
        self.closes += 1

    def from_url(self, url: str, **kwargs: Any) -> Store:
        self.options.append(kwargs)
        return self


class Response:
    def __init__(self, content: Any = None, status_code: int = 200, **kwargs: Any):
        self.content = content
        self.status_code = status_code
        self.headers = {}
        self.cookies = {}
        self.kwargs = kwargs

    def delete_cookie(self, name: str) -> None:
        self.cookies.pop(name, None)

    def set_cookie(self, name: str, value: str, **kwargs: Any) -> None:
        self.cookies[name] = (value, kwargs)


class CrossProcessStateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.store = Store()
        self.log = Mock()
        self.rows = [{'name': 'planner', 'version': 1, 'content': 'v1', 'traffic_weight': 100}]
        self.db_fail = False

        async def execute(query: str) -> Any:
            self.assertIn("WHERE status = 'active' ORDER BY name, version", query)
            if self.db_fail:
                raise RuntimeError('PRIVATE_SQL_DETAILS')
            rows = deepcopy(self.rows)
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))

        self.session = SimpleNamespace(execute=AsyncMock(side_effect=execute))
        self.factory = Mock(return_value=Mock(__aenter__=AsyncMock(return_value=self.session),
                                              __aexit__=AsyncMock(return_value=False)))
        self.stack.enter_context(patch.dict(sys.modules, {
            'loguru': module('loguru', logger=self.log),
            'redis.asyncio': module('redis.asyncio', Redis=self.store),
            'redis.exceptions': module('redis.exceptions', RedisError=RedisFailure),
            'redis.backoff': module('redis.backoff', NoBackoff=lambda: None),
            'redis.retry': module('redis.retry', Retry=lambda backoff, retries: retries),
            'app.config': module('app.config', get_settings=lambda: SimpleNamespace(
                redis_url='redis://synthetic.invalid/0')),
            'sqlalchemy': module('sqlalchemy', text=lambda s: s),
            'app.core.database': module('app.core.database', get_session_factory=lambda: self.factory),
            'app.prompts.defaults': module('app.prompts.defaults', DEFAULT_PROMPTS={'planner': 'default'}),
        }))
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.security.oidc': load('c19_oidc', 'app/security/oidc.py')}))
        self.runtime_a = load('c09_runtime_a', 'app/core/runtime_state.py')
        self.runtime_b = load('c09_runtime_b', 'app/core/runtime_state.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.core.runtime_state': self.runtime_a}))
        self.cancel_a = load('c09_cancel_a', 'app/core/cancellation.py')
        self.cancel_b = load('c09_cancel_b', 'app/core/cancellation.py')
        self.cancel_a.POLL_SECONDS = self.cancel_b.POLL_SECONDS = .001
        self.prompts_a = load('c09_prompts_a', 'app/prompts/registry.py')
        self.prompts_b = load('c09_prompts_b', 'app/prompts/registry.py')
        self.c04 = load('c09_c04', 'tests/test_session_ownership.py')

    async def owned(self, lease: Any, entered: asyncio.Event) -> None:
        async with lease.watch():
            entered.set()
            await asyncio.Event().wait()

    async def test_other_worker_cancel_reaches_owner(self) -> None:
        lease = await self.cancel_a.reserve_session('session')
        entered = asyncio.Event()
        task = asyncio.create_task(self.owned(lease, entered))
        await entered.wait()
        self.assertTrue(await self.cancel_b.request_cancel('session'))
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        self.assertIsNone(self.store.get(lease.keys[0]))
        self.assertFalse(await self.cancel_b.request_cancel('session'))

    async def test_parallel_registration_has_one_owner(self) -> None:
        outcomes = await asyncio.gather(self.cancel_a.reserve_session('session'),
            self.cancel_b.reserve_session('session'), return_exceptions=True)
        self.assertEqual(sum(isinstance(x, (self.cancel_a.SessionBusy,
                                            self.cancel_b.SessionBusy)) for x in outcomes), 1)

    async def test_expiry_and_late_cleanup_cannot_touch_new_run(self) -> None:
        old = await self.cancel_a.reserve_session('session')
        await self.cancel_b.request_cancel('session')
        self.store.now += 31
        new = await self.cancel_b.reserve_session('session')
        await old.release()
        self.assertEqual(self.store.get(new.keys[0]), new.token)
        status = await self.store.eval(self.cancel_a.POLL_SCRIPT, 2, *new.keys, new.token, 30)
        self.assertEqual(status, 1)

    async def test_lost_lease_aborts_instead_of_cancelling_new_owner(self) -> None:
        old = await self.cancel_a.reserve_session('session')
        self.store.now += 31
        new = await self.cancel_b.reserve_session('session')
        entered = asyncio.Event()
        with self.assertRaises(self.runtime_a.RuntimeStateUnavailable):
            await asyncio.wait_for(self.owned(old, entered), 1)
        self.assertEqual(self.store.get(new.keys[0]), new.token)

    async def test_heartbeat_renews_only_matching_owner(self) -> None:
        lease = await self.cancel_a.reserve_session('session')
        self.store.now = 29
        self.assertEqual(await self.store.eval(self.cancel_a.POLL_SCRIPT, 2,
                         *lease.keys, lease.token, 30), 1)
        self.assertEqual(self.store.expiry[lease.keys[0]], 59)
        self.assertEqual(await self.store.eval(self.cancel_a.POLL_SCRIPT, 2,
                         *lease.keys, 'old', 30), 0)
        self.assertEqual(self.store.expiry[lease.keys[0]], 59)

    async def test_store_outage_denies_start_and_cancel(self) -> None:
        self.store.fail = True
        for operation in (self.cancel_a.reserve_session, self.cancel_b.request_cancel):
            with self.assertRaises(self.runtime_a.RuntimeStateUnavailable) as exc:
                await operation('session')
            self.assertEqual(str(exc.exception), 'RUNTIME_STATE_UNAVAILABLE')
        self.assertEqual(self.store.values, {})

    async def test_store_outage_aborts_owner_with_unavailable_not_cancelled(self) -> None:
        lease = await self.cancel_a.reserve_session('session')
        entered = asyncio.Event()
        task = asyncio.create_task(self.owned(lease, entered))
        await entered.wait()
        self.store.fail = True
        with self.assertRaises(self.runtime_a.RuntimeStateUnavailable):
            await asyncio.wait_for(task, 1)
        self.assertNotIn('PRIVATE_CONNECTION_DETAILS', str(self.log.mock_calls))

    async def test_nested_operation_cannot_turn_observed_cancel_into_success(self) -> None:
        lease = await self.cancel_a.reserve_session('session')
        await self.cancel_b.request_cancel('session')
        async def swallowing():
            async with lease.watch():
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    pass
            return 'incorrect success'
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(swallowing(), 1)

    async def test_disconnect_releases_only_owned_lease(self) -> None:
        lease = await self.cancel_a.reserve_session('session')
        other = await self.cancel_b.reserve_session('other')
        entered = asyncio.Event()
        task = asyncio.create_task(self.owned(lease, entered))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(self.store.get(lease.keys[0]))
        self.assertEqual(self.store.get(other.keys[0]), other.token)

    async def test_runtime_client_timeouts_close_and_hashed_keys(self) -> None:
        lease = await self.cancel_a.reserve_session('private-session')
        self.assertNotIn('private-session', repr(self.store.values))
        self.assertEqual(lease.keys[0].split('{')[1].split('}')[0],
                         lease.keys[1].split('{')[1].split('}')[0])
        self.assertEqual(self.store.options[0]['socket_timeout'], 2)
        self.assertEqual(self.store.options[0]['socket_connect_timeout'], 2)
        self.assertFalse(self.store.options[0]['retry_on_timeout'])
        self.assertEqual(self.store.options[0]['retry'], 0)
        self.assertEqual(self.store.closes, 1)

    async def test_sso_callback_other_worker_consumes_once(self) -> None:
        state, nonce = await self.runtime_a.register_sso_state()
        self.assertNotIn(state, repr(self.store.values.keys()))
        results = await asyncio.gather(self.runtime_b.consume_sso_state(state),
                                       self.runtime_a.consume_sso_state(state))
        self.assertEqual(results.count(nonce), 1)
        self.assertEqual(results.count(None), 1)

    async def test_sso_expired_missing_and_malformed_deny(self) -> None:
        state, _ = await self.runtime_a.register_sso_state()
        self.store.now = 600
        self.assertIsNone(await self.runtime_b.consume_sso_state(state))
        self.assertIsNone(await self.runtime_b.consume_sso_state(secrets.token_urlsafe(32)))
        before = len(self.store.options)
        for bad in ['', 'short', 'x' * 1000, '../state', 'x' * 42 + '\n']:
            self.assertIsNone(await self.runtime_b.consume_sso_state(bad))
        self.assertEqual(len(self.store.options), before)

    async def test_sso_store_failure_never_falls_back_to_memory(self) -> None:
        self.store.fail = True
        with self.assertRaises(self.runtime_a.RuntimeStateUnavailable):
            await self.runtime_a.register_sso_state()
        with self.assertRaises(self.runtime_b.RuntimeStateUnavailable):
            await self.runtime_b.consume_sso_state('a' * 43)
        self.assertEqual(self.store.values, {})

    def auth_functions(self) -> dict:
        settings = SimpleNamespace(sso_authorize_url='https://idp.example.test/auth',
            sso_client_id='test', sso_redirect_uri='https://app.example.test/callback',
            sso_scopes='openid', is_dev=False, sso_issuer='https://idp.example.test')
        ns = dict(secrets=secrets, _SSO_STATE_TTL_SECONDS=600, _require_sso_config=Mock(),
            _register_sso_state=self.runtime_a.register_sso_state,
            _consume_sso_state=self.runtime_b.consume_sso_state,
            RuntimeStateUnavailable=self.runtime_b.RuntimeStateUnavailable,
            get_settings=lambda: settings, HTTPException=self.c04.HTTPException,
            JSONResponse=Response, RedirectResponse=Response, Depends=lambda x: None,
            get_db=Mock(), get_audit_logger=lambda: SimpleNamespace(log=AsyncMock()),
            _exchange_sso_code=AsyncMock(return_value={'id_token': 'synthetic'}),
            _verify_id_token=AsyncMock(return_value={'sub': 'test'}),
            _find_or_provision_sso_user=AsyncMock(return_value=(SimpleNamespace(user_id='u'), False)),
            _issue_token=Mock(return_value=SimpleNamespace(model_dump=lambda: {'user_id': 'u'})),
            urlencode=urlencode, urlsplit=urlsplit, urlunsplit=urlunsplit)
        # Both process module exception types represent the same application class in production.
        ns['RuntimeStateUnavailable'] = (self.runtime_a.RuntimeStateUnavailable,
                                         self.runtime_b.RuntimeStateUnavailable)
        tree = ast.parse((ROOT / 'app/api/auth.py').read_text())
        selected = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                '_sso_error', '_append_query', 'sso_login', 'sso_callback',
            }:
                node.decorator_list = []
                selected.append(ast.unparse(node))
        exec(compile('from __future__ import annotations\n'+'\n'.join(selected),
                     '<actual-auth-functions>', 'exec'), ns)
        return ns

    async def test_sso_http_cookie_mismatch_does_not_consume_even_on_idp_error(self) -> None:
        ns = self.auth_functions()
        state, nonce = await self.runtime_a.register_sso_state()
        request = SimpleNamespace(cookies={'sso_state': 'wrong'}, headers={})
        result = await ns['sso_callback'](request, state=state, error='denied', db=None)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(await self.runtime_b.consume_sso_state(state), nonce)
        ns['_exchange_sso_code'].assert_not_awaited()

    async def test_sso_http_matching_cookie_success_then_replay_denied(self) -> None:
        ns = self.auth_functions()
        state, _ = await self.runtime_a.register_sso_state(verifier='v' * 43)
        request = SimpleNamespace(cookies={'sso_state': state}, headers={})
        first = await ns['sso_callback'](request, code='code', state=state, db=None)
        second = await ns['sso_callback'](request, code='code', state=state, db=None)
        self.assertEqual((first.status_code, second.status_code), (200, 400))
        self.assertEqual(ns['_exchange_sso_code'].await_count, 1)
        self.assertEqual(first.headers['Cache-Control'], 'no-store')

    async def test_sso_http_outage_returns_503_without_token_exchange(self) -> None:
        ns = self.auth_functions()
        self.store.fail = True
        login = await ns['sso_login']()
        request = SimpleNamespace(cookies={'sso_state': 'a' * 43}, headers={})
        callback = await ns['sso_callback'](request, code='code', state='a' * 43, db=None)
        self.assertEqual((login.status_code, callback.status_code), (503, 503))
        ns['_exchange_sso_code'].assert_not_awaited()
        ns['_issue_token'].assert_not_called()

    async def test_sso_login_cookie_matches_shared_state_and_idp_error_consumes_once(self) -> None:
        ns = self.auth_functions()
        login = await ns['sso_login']()
        state, options = login.cookies['sso_state']
        self.assertEqual(options['max_age'], 600)
        self.assertTrue(options['httponly'] and options['secure'])
        request = SimpleNamespace(cookies={'sso_state': state}, headers={})
        error = await ns['sso_callback'](request, error='denied', state=state, db=None)
        self.assertEqual(error.status_code, 401)
        self.assertIsNone(await self.runtime_a.consume_sso_state(state))
        ns['_exchange_sso_code'].assert_not_awaited()

    async def test_prompt_activation_visible_on_next_worker_request(self) -> None:
        self.prompts_b._cache = {'planner': [dict(self.rows[0])]}
        async with self.prompts_a.request_prompt_snapshot():
            self.assertEqual(self.prompts_a.get_prompt('planner'), ('v1', 1))
            self.rows[0].update(version=2, content='v2')
            async with self.prompts_b.request_prompt_snapshot():
                self.assertEqual(self.prompts_b.get_prompt('planner'), ('v2', 2))
            self.assertEqual(self.prompts_a.get_prompt('planner'), ('v1', 1))
        self.assertIsNone(self.prompts_a._request_prompts.get())

    async def test_prompt_snapshot_reaches_child_tasks_and_threads(self) -> None:
        async with self.prompts_a.request_prompt_snapshot():
            async def child():
                return self.prompts_a.get_prompt('planner')
            self.assertEqual(await asyncio.create_task(child()), ('v1', 1))
            self.assertEqual(await asyncio.to_thread(self.prompts_a.get_prompt, 'planner'), ('v1', 1))

    async def test_prompt_outage_never_uses_old_cache(self) -> None:
        self.prompts_a._cache = {'planner': [dict(self.rows[0])]}
        self.db_fail = True
        with self.assertRaises(self.prompts_a.PromptSnapshotUnavailable) as exc:
            async with self.prompts_a.request_prompt_snapshot():
                self.fail('No execution after snapshot failure')
        self.assertEqual(str(exc.exception), 'PROMPT_SNAPSHOT_UNAVAILABLE')
        self.assertIsNone(self.prompts_a._request_prompts.get())

    async def test_both_actual_graph_entries_abort_before_models_when_prompt_db_fails(self) -> None:
        c08 = load('c09_c08', 'tests/test_request_context.py')
        case = c08.RequestContextTests()
        case.setUp()
        try:
            graph = SimpleNamespace(ainvoke=AsyncMock(), astream_events=Mock())
            case.graph.build_graph = Mock(return_value=graph)
            case.graph.request_prompt_snapshot = self.prompts_a.request_prompt_snapshot
            case.history.load_recent_history = AsyncMock(return_value=[])
            getter = AsyncMock(return_value=(object(), 'fake'))
            self.db_fail = True
            with patch.dict(sys.modules, {'app.graph.checkpointer': module(
                    'app.graph.checkpointer', get_checkpointer=getter)}):
                with self.assertRaises(self.prompts_a.PromptSnapshotUnavailable):
                    await case.graph.run_graph(case.user())
                with self.assertRaises(self.prompts_a.PromptSnapshotUnavailable):
                    _ = [event async for event in case.graph.run_graph_stream(case.user())]
            graph.ainvoke.assert_not_awaited()
            graph.astream_events.assert_not_called()
        finally:
            case.doCleanups()

    async def test_prompt_weights_and_defaults_follow_snapshot(self) -> None:
        self.rows = [dict(self.rows[0], traffic_weight=0),
                     dict(self.rows[0], version=2, content='v2', traffic_weight=100)]
        async with self.prompts_a.request_prompt_snapshot():
            self.assertEqual(self.prompts_a.get_prompt('planner', 'user'), ('v2', 2))
        self.rows = []
        async with self.prompts_a.request_prompt_snapshot():
            self.assertEqual(self.prompts_a.get_prompt('planner'), ('default', 0))

    async def test_prompt_context_restored_after_error_and_explicit_developer_mode(self) -> None:
        with self.assertRaises(ValueError):
            async with self.prompts_a.request_prompt_snapshot():
                raise ValueError('stop')
        self.assertIsNone(self.prompts_a._request_prompts.get())
        self.db_fail = True
        async with self.prompts_a.request_prompt_snapshot(enabled=False):
            self.assertEqual(self.prompts_a.get_prompt('planner'), ('default', 0))

    async def test_local_cache_refresh_replaces_atomically(self) -> None:
        old = {'planner': [dict(self.rows[0])]}
        self.prompts_a._cache = old
        self.rows[0].update(version=2, content='v2')
        await self.prompts_a.refresh_prompt_cache()
        self.assertEqual(old['planner'][0]['content'], 'v1')
        self.assertEqual(self.prompts_a.get_prompt('planner'), ('v2', 2))

    async def test_chat_busy_before_metadata_change_graph_or_stream(self) -> None:
        for action in ('message', 'stream'):
            case = self.c04.SessionOwnershipTests()
            await case.asyncSetUp()
            try:
                before = case.db.snapshot()
                case.cancellation.reserve_session.side_effect = case.cancellation.SessionBusy()
                with self.assertRaises(self.c04.HTTPException) as exc:
                    await case.call(action, case.owner)
                self.assertEqual(exc.exception.status_code, 409)
                self.assertEqual(case.db.snapshot(), before)
                case.graph.assert_not_awaited()
                self.assertEqual(case.responses, [])
            finally:
                await case.asyncTearDown()

    async def test_chat_reservation_and_cancel_outage_return_503(self) -> None:
        for action in ('message', 'stream', 'cancel'):
            case = self.c04.SessionOwnershipTests()
            await case.asyncSetUp()
            try:
                case.cancellation.reserve_session.side_effect = case.runtime.RuntimeStateUnavailable()
                case.cancellation.request_cancel.side_effect = case.runtime.RuntimeStateUnavailable()
                with self.assertRaises(self.c04.HTTPException) as exc:
                    await case.call(action, case.owner)
                self.assertEqual((exc.exception.status_code, exc.exception.detail),
                                 (503, 'RUNTIME_STATE_UNAVAILABLE'))
                case.graph.assert_not_awaited()
            finally:
                await case.asyncTearDown()

    async def test_message_lease_loss_reports_failure_not_user_cancel(self) -> None:
        case = self.c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            case.graph.side_effect = case.runtime.RuntimeStateUnavailable()
            with self.assertRaises(self.c04.HTTPException) as exc:
                await case.call('message', case.owner)
            self.assertEqual(exc.exception.status_code, 503)
            case.chat._update_session_status.assert_awaited_with(
                'session-a', 'failed', error='RUNTIME_STATE_UNAVAILABLE')
            case.lease.release.assert_awaited_once()
        finally:
            await case.asyncTearDown()

    async def test_stream_lease_loss_emits_error_not_cancelled(self) -> None:
        case = self.c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            async def broken(*args, **kwargs):
                raise case.runtime.RuntimeStateUnavailable()
                yield  # Keep the asynchronous-generator interface.
            sys.modules['app.graph.graph'].run_graph_stream = broken
            response = await case.call('stream', case.owner)
            events = [event async for event in response.events]
            self.assertIn('RUNTIME_STATE_UNAVAILABLE', str(events))
            self.assertNotIn('cancelled', str(events))
        finally:
            await case.asyncTearDown()


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
