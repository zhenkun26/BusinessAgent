"""F2-05 synthetic diagnostics and external payload boundaries; no service calls."""
from __future__ import annotations

import ast
from contextlib import ExitStack
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'tests/test_request_context.py'))
HELPERS = runpy.run_path(str(ROOT / 'tests/test_credential_safety.py'))
load, module, function = HELPERS['load'], HELPERS['module'], HELPERS['function']
MARKER = 'SYNTHETIC_BUSINESS_NOTE_7 synthetic-person@example.invalid'
SCOPED = ('graph/graph', 'graph/planner', 'graph/history', 'graph/executor',
          'graph/aggregator', 'graph/dispatcher', 'agents/knowledge', 'agents/execution',
          'rag/degradation', 'rag/retriever', 'rag/llm', 'rag/reranker')


class Poison:
    def __str__(self) -> str:
        raise AssertionError('OPAQUE_STRINGIFICATION')

    def __repr__(self) -> str:
        raise AssertionError('OPAQUE_REPR')


class ManualTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(sys.modules, {
            'app': module('app', __version__='synthetic'),
            'loguru': module('loguru', logger=Mock()),
        }))
        self.target = load('f205_tracing', 'app/observability/tracing.py')
        self.span = Mock(is_recording=lambda: True)
        self.context = Mock(__enter__=Mock(return_value=self.span),
                            __exit__=Mock(return_value=False))
        self.target._tracer = Mock(start_as_current_span=Mock(return_value=self.context))
        self.stack.enter_context(patch.dict(sys.modules, {
            'opentelemetry': module('opentelemetry', trace=SimpleNamespace(
                get_current_span=lambda: self.span)),
        }))

    def test_allowed_metadata_survives_every_helper(self) -> None:
        attrs = {'rag.top_k': 5, 'rag.final.top_score': .8, 'tool.success': False,
                 'rag.scene': 'policy', 'stage': 'coarse'}
        with self.target.traced_span('rag.retrieve', attrs):
            pass
        self.target.record_span_attributes(attrs)
        self.target.record_span_event('rag.no_results', attrs)
        for key, value in attrs.items():
            self.span.set_attribute.assert_any_call(key, value)
        self.span.add_event.assert_called_once_with('rag.no_results', attributes=attrs)

    def test_business_fields_and_unknown_names_are_not_exported(self) -> None:
        attrs = {k: MARKER for k in ('rag.query', 'user_id', 'thread_id', 'task_id',
                 'error', 'tool.name', 'tool.role', 'scope', 'rag.dept_namespace')}
        attrs['nested'] = {'text': MARKER}
        with self.target.traced_span(MARKER, attrs):
            pass
        self.target.record_span_attributes(attrs)
        self.target.record_span_event(MARKER, attrs)
        self.target.record_exception(RuntimeError(MARKER))
        self.assertNotIn(MARKER, str(self.target._tracer.mock_calls))
        self.assertNotIn(MARKER, str(self.span.mock_calls))
        self.span.set_attribute.assert_not_called()
        self.span.record_exception.assert_not_called()
        self.target._tracer.start_as_current_span.assert_called_once_with(
            'application.operation', record_exception=False, set_status_on_exception=False)

    def test_untrusted_tool_name_becomes_fixed_operation(self) -> None:
        with self.target.traced_span('tool.' + MARKER):
            pass
        self.assertEqual(self.target._tracer.start_as_current_span.call_args.args,
                         ('tool.invoke',))

    def test_metadata_types_limits_and_nonfinite_values_fail_closed(self) -> None:
        for value in (MARKER, None, True, [], {}, Poison(), -1, 1e13, 10**1000,
                      float('nan'), float('inf'), -float('inf')):
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(self.target._manual_attributes({'rag.top_k': value}), {})
        for attrs in ({'tool.success': 1}, {'rag.scene': MARKER}, {'stage': 'unknown'},
                      {Poison(): MARKER}, {'rag.top_k': 1, 'content': Poison()}):
            result = self.target._manual_attributes(attrs)
            self.assertEqual(result, {'rag.top_k': 1} if 'rag.top_k' in attrs else {})

    def test_opaque_inputs_are_not_stringified(self) -> None:
        for attrs in (None, [], MARKER, Poison()):
            self.assertEqual(self.target._manual_attributes(attrs), {})
        with self.target.traced_span(Poison(), {'query': Poison()}):
            pass
        self.target.record_span_event(Poison(), {'content': Poison()})
        self.target.record_exception(Poison())

    def test_failure_is_not_swallowed_or_auto_recorded(self) -> None:
        with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
            with self.target.traced_span('rag.retrieve', {'rag.top_k': 5}):
                raise RuntimeError('synthetic failure')
        self.context.__enter__.assert_called_once()
        self.context.__exit__.assert_called_once()
        self.span.record_exception.assert_not_called()

    def test_disabled_tracing_remains_noop(self) -> None:
        self.target._tracer = None
        with self.target.traced_span(Poison(), Poison()) as span:
            self.assertIsNone(span)
        self.target.record_span_attributes(Poison())
        self.target.record_span_event(Poison(), Poison())
        self.target.record_exception(Poison())
        self.span.set_attribute.assert_not_called()


class GraphPrivacyTests(BASE['RequestContextFixture']):
    def assert_private_logs(self) -> None:
        self.assertNotIn(MARKER, str(self.log.mock_calls))
        self.log.exception.assert_not_called()

    def test_actual_replan_keeps_query_but_not_diagnostics(self) -> None:
        user = self.user(username=MARKER, message=MARKER)
        state = self.state(user_input=user, replan_reason=MARKER,
                           replan_hint={'query': MARKER})
        result = self.planner.planner_node(state)
        self.assertEqual(result['subtasks'][0].description, MARKER)
        self.assert_private_logs()

    def test_actual_history_expansion_retains_input_without_logging_it(self) -> None:
        query = '它的折扣呢？'
        expanded = self.history.expand_query_with_history(
            query, [{'user': MARKER, 'assistant': MARKER}])
        self.assertIn(MARKER, expanded)
        self.assertIn(query, expanded)
        self.assert_private_logs()

    async def test_actual_executor_forwards_content_without_logging_failure(self) -> None:
        task = BASE['Task'](task_id=MARKER, task_type=self.kind.KNOWLEDGE,
                            description=MARKER)
        runner = AsyncMock(side_effect=RuntimeError(MARKER))
        self.agent_factory.side_effect = lambda **kwargs: SimpleNamespace(run=runner)
        result = await self.executor.agent_executor_node(self.state(current_subtask=task))
        self.assertFalse(result['agent_results'][0].success)
        self.assertEqual(runner.call_args.args[0], MARKER)
        self.assert_private_logs()

    def test_scoped_diagnostic_calls_cannot_interpolate_business_fields(self) -> None:
        # Evaluate the actual log expressions even for branches not selected by fixtures.
        # Safe operational values are explicit; business-bearing values carry a marker.
        log = Mock()
        unsafe = {name: MARKER for name in ('query', 'message', 'expanded', 'raw', 'text',
                    'reasoning', 'replan_reason', 'replan_query', 'thread_id', 'tid',
                    'approval_id', 'name', 'role', 'tag', 'injection_check')}
        ns = {**unsafe, 'logger': log, 'e': RuntimeError(MARKER),
              'user_input': self.user(username=MARKER, message=MARKER, request_id=MARKER),
              'state': {'replan_reason': MARKER}, 'context': {'role': MARKER},
              'subtask': BASE['Task'](task_id=MARKER, task_type=self.kind.KNOWLEDGE,
                                      description=MARKER),
              'p': SimpleNamespace(tool=MARKER), 'result': SimpleNamespace(agent_name=MARKER),
              's': SimpleNamespace(openai_base_url=MARKER, primary_llm_model=MARKER,
                    lite_llm_model=MARKER, local_llm_model=MARKER, local_llm_base_url=MARKER,
                    reranker_model=MARKER),
              'self': SimpleNamespace(_model_path=MARKER),
              'subtasks': [], 'kept': [], 'sends': [], 'history': [], 'plans': [],
              'results': [], 'success_results': [], 'all_sources': [], 'coarse_results': [],
              'ranked': [], 'r': SimpleNamespace(success=True, confidence=.8),
              'intent': self.intent.KNOWLEDGE_QA, 'backend_tag': 'redis', 'checkpointer': True,
              'replan_count': 1, 'MAX_REPLAN_ROUNDS': 2, 'pv': 1, 'latency_ms': 3,
              'combined_conf': .8, 'needs_replan': False, 'top_score': .8, 'tokens': 1,
              'stage': 'vector', 'ms': 1, 'top_score_str': '0.8', 'coarse_ms': 1, 'total_ms': 2}
        seen = 0
        for name in SCOPED:
            tree = ast.parse((ROOT / 'app' / (name + '.py')).read_text())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'logger'):
                    with self.subTest(module=name, line=node.lineno):
                        self.assertNotEqual(node.func.attr, 'exception')
                        eval(compile(ast.Expression(node), name, 'eval'), ns)
                        self.assertNotIn(MARKER, str(log.mock_calls))
                        log.reset_mock()
                        seen += 1
        self.assertGreater(seen, 50)


class ExternalPayloadPrivacyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.remote = load('f205_remote', 'app/rag/remote_models.py')
        self.sent: list[httpx.Request] = []
        self.real_client = httpx.Client

    def transport(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        if request.url.path.endswith('/embeddings'):
            return httpx.Response(200, json={'data': [{'index': 0, 'embedding': [1., 0.]}]})
        return httpx.Response(200, json={'output': {'results': [
            {'index': 0, 'relevance_score': .9}]}})

    def client(self, kind: str) -> Any:
        path = ('/compatible-mode/v1' if kind == 'embedding'
                else '/api/v1/services/rerank/text-rerank')
        return self.remote.BailianClient('https://dashscope.aliyuncs.com' + path,
                                         'SYNTHETIC_TEST_CREDENTIAL', 10, 0, kind=kind)

    def factory(self, **kwargs: Any) -> httpx.Client:
        return self.real_client(transport=httpx.MockTransport(self.transport), **kwargs)

    def test_credential_redaction_does_not_anonymize_business_content(self) -> None:
        target = load('f205_redaction', 'app/security/redaction.py')
        original = {'content': MARKER, 'password': 'SYNTHETIC_TEST_CREDENTIAL'}
        self.assertEqual(target.redact_value(original),
                         {'content': MARKER, 'password': '[REDACTED]'})
        self.assertEqual(original['password'], 'SYNTHETIC_TEST_CREDENTIAL')

    def test_embedding_text_is_sent_only_in_expected_payload(self) -> None:
        with patch.object(self.remote.httpx, 'Client', side_effect=self.factory):
            self.client('embedding').embed([MARKER], 'text-embedding-v4', 2)
        request = self.sent[0]
        self.assertEqual(json.loads(request.content), {'model': 'text-embedding-v4',
                         'input': [MARKER], 'dimensions': 2, 'encoding_format': 'float'})
        self.assertNotIn(MARKER, str(request.url))
        self.assertEqual(request.headers['Authorization'], 'Bearer SYNTHETIC_TEST_CREDENTIAL')
        self.assertNotIn('SYNTHETIC_TEST_CREDENTIAL', request.content.decode())

    def test_reranker_receives_query_and_chunks_not_source_metadata(self) -> None:
        with patch.object(self.remote.httpx, 'Client', side_effect=self.factory):
            self.client('reranker').rerank(MARKER, [MARKER + ' document'], 'qwen3-rerank', 1)
        payload = json.loads(self.sent[0].content)
        self.assertEqual(payload, {'model': 'qwen3-rerank',
            'input': {'query': MARKER, 'documents': [MARKER + ' document']},
            'parameters': {'top_n': 1, 'return_documents': False}})
        self.assertNotIn(MARKER, str(self.sent[0].url))

    def test_invalid_endpoint_rejected_before_transport(self) -> None:
        for base in ('http://dashscope.aliyuncs.com/compatible-mode/v1',
                     'https://example.invalid/compatible-mode/v1',
                     'https://dashscope.aliyuncs.com/compatible-mode/v1?text=' + MARKER):
            with self.subTest(base=base), patch.object(self.remote.httpx, 'Client') as factory:
                with self.assertRaisesRegex(self.remote.RemoteModelError,
                                            '^MODEL_REMOTE_CONFIG_INVALID$'):
                    self.remote.BailianClient(base, 'synthetic', 10, 0, kind='embedding')
                factory.assert_not_called()

    def test_provider_body_and_redirect_are_not_forwarded(self) -> None:
        for status in (302, 400, 500):
            def respond(request: httpx.Request) -> httpx.Response:
                self.sent.append(request)
                return httpx.Response(status, text=MARKER,
                                      headers={'Location': 'https://example.invalid/leak'})
            with self.subTest(status=status), patch.object(self.remote.httpx, 'Client',
                    side_effect=lambda **kwargs: self.real_client(
                        transport=httpx.MockTransport(respond), **kwargs)):
                before = len(self.sent)
                with self.assertRaises(self.remote.RemoteModelError) as caught:
                    self.client('embedding').embed([MARKER], 'text-embedding-v4', 2)
                self.assertEqual(len(self.sent), before + 1)
                self.assertNotIn(MARKER, str(caught.exception))

    async def test_generation_receives_query_history_and_context(self) -> None:
        # Captures the actual prompt inputs without constructing a model or provider client.
        chain = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=MARKER + ' [来源1]')))
        log = Mock()
        target = function('app/agents/knowledge.py', '_generate_answer',
            {'logger': log, 'get_lite_llm': lambda: chain,
             'get_prompt': lambda name: ('synthetic {query} {context}', 1)}, 'KnowledgeAgent')
        answer, score = await target(SimpleNamespace(), MARKER + ' query',
            [SimpleNamespace(document_id='synthetic-doc', chunk_id='synthetic-chunk',
                title='Synthetic', content=MARKER + ' document', score=.95)],
            history=[{'user': MARKER + ' history', 'assistant': 'synthetic answer'}])
        sent = json.loads(chain.ainvoke.call_args.args[0][1].content)
        self.assertIn(MARKER + ' document', sent['context'][0]['body'])
        self.assertIn(MARKER + ' history', sent['history'][0]['user'])
        self.assertIn(MARKER + ' query', sent['query'])
        self.assertEqual(answer, MARKER + ' [来源1]')
        self.assertNotIn(MARKER, str(log.mock_calls))
