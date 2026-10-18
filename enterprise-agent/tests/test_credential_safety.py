"""C06 offline credential markers; no real network, database, logs or cleanup."""

from __future__ import annotations

import ast
from contextlib import ExitStack, nullcontext
from datetime import datetime
from enum import Enum
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'SYNTHETIC_C06_PRIVATE_CREDENTIAL_123456'
JWT_MARKER = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzeW50aGV0aWMifQ.synthetic_signature'


def module(name: str, **attrs: Any) -> ModuleType:
    result = ModuleType(name)
    result.__dict__.update(attrs)
    return result


def load(name: str, path: str) -> ModuleType:
    result = module(name)
    source = ROOT / path
    result.__file__ = str(source)
    exec(compile(source.read_bytes(), str(source), 'exec'), result.__dict__)
    return result


def function(path: str, name: str, namespace: dict[str, Any], owner: str = '') -> Any:
    source = ROOT / path
    tree = ast.parse(source.read_text())
    if owner:
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace[name]


class MemoryFile(io.StringIO):
    def close(self) -> None:
        pass  # Inspect only the in-memory sink after the application closes it.


class DiagnosticSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.redaction = load('c06_redaction', 'app/security/redaction.py')
        self.log = Mock()
        self.db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
        session = Mock(__aenter__=AsyncMock(return_value=self.db),
                       __aexit__=AsyncMock(return_value=False))
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.security.redaction': self.redaction,
            'loguru': module('loguru', logger=self.log),
            'sqlalchemy': module('sqlalchemy', text=lambda s: s),
            'app.core.database': module('app.core.database', get_session_factory=lambda: lambda: session),
        }))
        self.audit = load('c06_audit', 'app/observability/audit.py').AuditLogger()

    def assert_safe(self, value: Any) -> None:
        text = str(value)
        self.assertNotIn(MARKER, text)
        self.assertNotIn(JWT_MARKER, text)

    def test_nested_credentials_and_configured_values_are_redacted_without_mutation(self) -> None:
        original = {'Authorization': 'Bearer ' + MARKER, 'nested': [
            {'api_key': MARKER, 'password': MARKER, 'requester_token': JWT_MARKER}],
            'answer': 'Bearer ' + MARKER, 'url': 'https://u:' + MARKER + '@example.invalid',
            'token_count': 17, 'text': JWT_MARKER}
        self.assert_safe(self.redaction.redact_value(original))
        self.assertEqual(original['nested'][0]['api_key'], MARKER)
        self.assertEqual(self.redaction.redact_value(original)['token_count'], 17)
        with patch.dict(self.redaction.os.environ, {'C06_API_KEY': MARKER}):
            self.assert_safe(self.redaction.redact_text('echo: ' + MARKER))

    def test_assignments_quotes_url_queries_and_bearer_are_redacted(self) -> None:
        for text in (f'password={MARKER}', f'{{"api_key": "{MARKER}"}}',
                     f"{{'jwt_token': '{JWT_MARKER}'}}", f'?access_token={MARKER}&page=1',
                     f'Authorization: Bearer {MARKER}', f'cookie="{MARKER}"'):
            with self.subTest(shape=text.split('=')[0][:20]):
                self.assert_safe(self.redaction.redact_text(text))

    def test_log_patcher_suppresses_exception_objects_and_locals(self) -> None:
        record = {'message': 'Bearer ' + MARKER, 'extra': {'requester_token': JWT_MARKER},
                  'exception': RuntimeError(MARKER)}
        self.redaction.redact_log_record(record)
        self.assert_safe(record)
        self.assertIsNone(record['exception'])
        self.redaction.install_log_redaction()
        self.log.configure.assert_called_once_with(patcher=self.redaction.redact_log_record)

    def test_log_redaction_failure_is_closed(self) -> None:
        record = {'message': object(), 'exception': RuntimeError(MARKER), 'extra': {}}
        self.redaction.redact_log_record(record)
        self.assertEqual(record['message'], 'REDACTION_FAILED')
        self.assertIsNone(record['exception'])

    def test_dotenv_loaded_credentials_are_registered_without_serializing_settings(self) -> None:
        self.redaction.register_configured_secrets({'deepseek_api_key': MARKER,
                                                    'auth_require_password': True})
        self.assert_safe(self.redaction.redact_text('provider echo: ' + MARKER))
        source = (ROOT / 'app/config.py').read_text()
        self.assertIn('register_configured_secrets(settings.model_dump())', source)

    async def test_public_request_and_validation_failures_use_fixed_errors(self) -> None:
        tree = ast.parse((ROOT / 'app/main.py').read_text())
        create_app = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                          and n.name == 'create_app')
        namespace = {'JSONResponse': SimpleNamespace, 'logger': self.log}
        for name, expected in (('safe_request_errors', 500), ('safe_validation_error', 422)):
            node = next(n for n in create_app.body if isinstance(n, ast.AsyncFunctionDef)
                        and n.name == name)
            node.decorator_list = []  # Execute handler body without creating an HTTP server.
            exec(compile(ast.Module(body=[node], type_ignores=[]), 'app/main.py', 'exec'), namespace)
            arg = AsyncMock(side_effect=RuntimeError(MARKER)) if expected == 500 else RuntimeError(MARKER)
            result = await namespace[name](None, arg)
            self.assertEqual(result.status_code, expected)
            self.assert_safe(vars(result))
        self.assert_safe(self.log.mock_calls)

    def test_sqlalchemy_diagnostics_hide_bind_values(self) -> None:
        source = (ROOT / 'app/core/database.py').read_text()
        self.assertIn('echo=False', source)
        self.assertIn('hide_parameters=True', source)

    async def test_audit_database_redacts_before_truncation(self) -> None:
        await self.audit.log('synthetic', input_summary='x' * 490 + ' Bearer ' + MARKER,
            output_summary=JWT_MARKER, payload={'nested': {'password': MARKER}})
        self.assert_safe(self.db.execute.await_args.args[1])
        self.assertLessEqual(len(self.db.execute.await_args.args[1]['input_summary']), 500)
        self.db.commit.assert_awaited_once()

    async def test_database_failure_passes_only_sanitized_record_to_fallback(self) -> None:
        self.db.execute.side_effect = RuntimeError(MARKER)
        self.audit._write_local_cache = AsyncMock()
        await self.audit.log('synthetic', payload={'token': MARKER}, output_summary=JWT_MARKER)
        self.assert_safe(self.audit._write_local_cache.await_args.args[0])
        self.assert_safe(self.log.mock_calls)

    async def test_local_cache_write_and_replay_sanitize_in_memory(self) -> None:
        globals_ = self.audit._write_local_cache.__func__.__globals__
        fake_os = SimpleNamespace(makedirs=Mock(), listdir=lambda _: ['synthetic.json'],
            remove=Mock(), path=SimpleNamespace(isdir=lambda _: True, join=lambda *parts: '/'.join(parts)))
        with patch.dict(globals_, {'os': fake_os}):
            sink = MemoryFile()
            with patch('builtins.open', return_value=sink):
                await self.audit._write_local_cache({'event_type': 'synthetic', 'password': MARKER})
            self.assert_safe(sink.getvalue())
            legacy = {'event_type': 'synthetic', 'input_summary': 'Bearer ' + MARKER,
                      'payload': {'token': JWT_MARKER}}
            with patch('builtins.open', return_value=MemoryFile(json.dumps(legacy))):
                self.assertEqual(await self.audit.flush_local_cache(), 1)
            self.assert_safe(self.db.execute.await_args.args[1])
            # The removal target is a Mock; no filesystem was accessed or deleted.
            fake_os.remove.assert_called_once_with('logs/audit/synthetic.json')

    async def test_http_errors_never_return_body_or_url_credentials(self) -> None:
        for status in (400, 401, 403, 422, 503):
            adapter = self.http_adapter(status, {'password': MARKER}, MARKER)
            ok, data, error = await adapter.call_external_api(
                'POST', 'https://user:' + MARKER + '@example.invalid/path?token=' + MARKER,
                api_token=MARKER, max_retries=0)
            self.assertFalse(ok)
            self.assertIsNone(data)
            self.assert_safe(error)
            self.assert_safe(self.log.mock_calls)

    async def test_http_success_redacts_provider_echo_without_changing_business_ids(self) -> None:
        adapter = self.http_adapter(200, {'access_token': MARKER, 'echo': MARKER, 'id': 'order-1'}, '')
        ok, data, error = await adapter.call_external_api('GET', 'https://example.invalid', api_token=MARKER)
        self.assertTrue(ok)
        self.assertEqual(data['id'], 'order-1')
        self.assert_safe(data)
        self.assertIsNone(error)

    def http_adapter(self, status: int, payload: Any, body: str) -> ModuleType:
        async def chunks():
            yield json.dumps(payload).encode()
        response = SimpleNamespace(status_code=status, headers={}, aiter_bytes=chunks)
        response_context = Mock(__aenter__=AsyncMock(return_value=response),
                                __aexit__=AsyncMock(return_value=False))
        client = SimpleNamespace(stream=lambda *a, **kw: response_context)
        context = Mock(__aenter__=AsyncMock(return_value=client), __aexit__=AsyncMock(return_value=False))
        self.stack.enter_context(patch.dict(sys.modules, {
            'httpx': module('httpx', AsyncClient=lambda **kw: context,
                            TimeoutException=TimeoutError, HTTPError=ConnectionError),
            'app.config': module('app.config', get_settings=lambda: SimpleNamespace(
                external_timeout_seconds=1, external_max_retries=0)),
        }))
        return load('c06_http', 'app/tools/http_adapter.py')

    async def test_approval_creation_never_persists_context_credentials(self) -> None:
        namespace = dict(Any=Any, ToolCallPlan=Any, uuid=uuid, json=json, logger=self.log,
            get_tool=lambda _: SimpleNamespace(risk_level='high'),
            get_audit_logger=lambda: SimpleNamespace(log=AsyncMock()),
            redact_text=self.redaction.redact_text, redact_value=self.redaction.redact_value)
        create = function('app/agents/execution.py', '_create_approval_request', namespace, 'ExecutionAgent')
        async def prepare(plans, context, **kwargs):
            context['execution_calls'] = [{'tool': p.tool, 'params': p.params} for p in plans]
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.tools.operation_gateway': module('app.tools.operation_gateway', prepare_calls=prepare)}))
        owner = SimpleNamespace(_build_approval_summary=lambda *args: 'synthetic approval')
        await create(owner, [SimpleNamespace(tool='send_email_external', params={'subject': 'safe subject'}, reason='')],
                     {'user_id': 'r', 'session_id': 's', 'jwt_token': JWT_MARKER}, 'synthetic query')
        for call in self.db.execute.await_args_list:
            self.assertNotIn('requester_token', call.args[0])
            self.assert_safe(call.args[1])

    async def test_chat_and_stream_errors_do_not_leak_credentials(self) -> None:
        harness = load('c06_chat_fixture', 'tests/test_session_ownership.py')
        case = harness.SessionOwnershipTests('test_owner_message_preserves_identity_and_runs_authorized_thread')
        await case.asyncSetUp()
        try:
            case.graph.side_effect = RuntimeError(MARKER)
            req = SimpleNamespace(session_id='session-a', message='Bearer ' + MARKER)
            with self.assertRaises(harness.HTTPException) as caught:
                await case.chat.send_message(req, user=case.owner, db=case.db,
                                            credentials=SimpleNamespace(credentials=JWT_MARKER))
            self.assertEqual(caught.exception.status_code, 500)
            self.assert_safe(str(caught.exception))
            self.assert_safe(case.db.snapshot())
            self.assert_safe(vars(case.graph.await_args.kwargs['user_input']))
            self.assertNotIn('jwt_token', vars(case.graph.await_args.kwargs['user_input']))

            async def broken_stream(*args: Any, **kwargs: Any) -> Any:
                raise RuntimeError(MARKER)
                yield {}  # Async-generator shape; no event is emitted.

            sys.modules['app.graph.graph'].run_graph_stream = broken_stream
            response = await case.call('stream', case.owner)
            events = [event async for event in response.events]
            self.assert_safe(events)
            self.assertIn('CHAT_EXECUTION_FAILED', str(events))
            self.assert_safe(case.audit.log.await_args_list)
            self.assert_safe(case.chat._update_session_status.await_args_list)
        finally:
            await case.asyncTearDown()

    def test_checkpoint_input_has_no_credential_field_and_masks_pasted_tokens(self) -> None:
        tree = ast.parse((ROOT / 'app/graph/state.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'UserInput')
        self.assertNotIn('jwt_token', [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)])
        make = function('app/graph/state.py', 'make_initial_state', dict(
            UserInput=Any, AgentState=dict, datetime=datetime, redact_text=self.redaction.redact_text))
        user = SimpleNamespace(message='Bearer ' + MARKER, request_id='r1')
        user.model_copy = lambda update: SimpleNamespace(message=update['message'], request_id='r1')
        state = make(user)
        self.assert_safe(vars(state['user_input']))
        self.assertNotIn('jwt_token', vars(state['user_input']))

    async def test_tool_gateway_sanitizes_returned_results(self) -> None:
        class Role(str, Enum):
            SALESPERSON = 'salesperson'
        result = SimpleNamespace(success=True, output={'token': MARKER, 'id': 'safe'},
                                 error='Bearer ' + MARKER, side_effects={'password': MARKER}, latency_ms=0)
        audit = SimpleNamespace(log_tool_call=AsyncMock())
        namespace = dict(Any=Any, ToolResult=SimpleNamespace, time=SimpleNamespace(time=lambda: 1),
            AgentRole=Role, ToolCategory=SimpleNamespace(ACTION='action'),
            can_use_tool=lambda *args: True, logger=self.log,
            traced_span=lambda *args, **kw: nullcontext(), record_span_attributes=Mock(),
            record_span_event=Mock(), get_audit_logger=lambda: audit,
            redact_value=self.redaction.redact_value)
        invoke = function('app/tools/base.py', 'invoke', namespace, 'BaseTool')
        owner = SimpleNamespace(name='synthetic', category=SimpleNamespace(value='query'),
            _validate_params=lambda p: p, _check_injection=lambda p: None,
            _effective_provider=lambda: 'mock', _execute=AsyncMock(return_value=result))
        returned = await invoke(owner, {'password': MARKER}, {'role': 'salesperson'})
        self.assert_safe(vars(returned))
        self.assert_safe(audit.log_tool_call.await_args.kwargs)

    async def test_compensation_failure_does_not_leak_into_agent_results(self) -> None:
        class OperationError(RuntimeError):
            pass
        store = SimpleNamespace(abort=AsyncMock(side_effect=OperationError(MARKER)), finish=AsyncMock())
        recover = function('app/core/saga_retry.py', 'recover_owned',
                           dict(SagaStore=Any, OperationError=OperationError, OperationStore=Mock()))
        state = await recover(store, 'synthetic-saga', 'synthetic-owner')
        self.assertEqual(state, 'manual')
        self.assert_safe(store.finish.await_args.args)
        self.assertEqual(store.finish.await_args.args[-1], 'SAGA_MANUAL_REQUIRED')
        self.assert_safe(self.log.mock_calls)

    def test_tracing_does_not_export_exception_message(self) -> None:
        with patch.dict(sys.modules, {'app': module('app', __version__='synthetic')}):
            target = load('c06_tracing', 'app/observability/tracing.py')
        target._tracer = object()
        span = Mock(is_recording=lambda: True)
        trace = SimpleNamespace(get_current_span=lambda: span)
        with patch.dict(sys.modules, {'opentelemetry': module('opentelemetry', trace=trace)}):
            target.record_span_attributes({'authorization': MARKER})
            target.record_span_event('synthetic', {'token': JWT_MARKER})
            target.record_exception(RuntimeError(MARKER))
        self.assert_safe(span.mock_calls)
        span.record_exception.assert_not_called()

    def test_span_context_enters_once_and_disables_raw_exception_capture(self) -> None:
        with patch.dict(sys.modules, {'app': module('app', __version__='synthetic')}):
            target = load('c06_tracing', 'app/observability/tracing.py')
        span = Mock()
        context = Mock(__enter__=Mock(return_value=span), __exit__=Mock(return_value=False))
        target._tracer = Mock(start_as_current_span=Mock(return_value=context))
        with self.assertRaises(RuntimeError):
            with target.traced_span('synthetic', {'token': MARKER}):
                raise RuntimeError('synthetic')
        context.__enter__.assert_called_once()
        context.__exit__.assert_called_once()
        self.assert_safe(span.mock_calls)
        kwargs = target._tracer.start_as_current_span.call_args.kwargs
        self.assertFalse(kwargs['record_exception'])
        self.assertFalse(kwargs['set_status_on_exception'])

    def test_api_and_worker_install_log_redaction_before_other_app_imports(self) -> None:
        for name in ('app/main.py', 'app/worker.py'):
            source = (ROOT / name).read_text()
            self.assertLess(source.index('install_log_redaction()'), source.index('from app.config'))


if __name__ == '__main__':
    sys.dont_write_bytecode = True

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event == 'socket.__new__' and args[1] == 1:
            return
        if event.startswith(('socket.', 'subprocess.')) or event in {
            'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod',
        }:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                                or isinstance(args[2], int) and args[2] & 3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')

    sys.addaudithook(guard)
    unittest.main(verbosity=2)
