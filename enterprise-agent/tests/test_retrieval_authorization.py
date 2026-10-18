"""C07 actual-source offline contracts; all stores/models are injected, no cleanup."""

from __future__ import annotations

import ast
from contextlib import ExitStack, nullcontext, asynccontextmanager
from dataclasses import asdict, replace
from datetime import datetime, UTC
from enum import Enum
import json
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace
from typing import Any, Optional
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, **attrs: Any) -> ModuleType:
    result = ModuleType(name)
    result.__dict__.update(attrs)
    return result


def load(name: str, path: str) -> ModuleType:
    result = module(name)
    sys.modules[name] = result  # Required for postponed dataclass annotations.
    source = ROOT / path
    exec(compile(source.read_bytes(), str(source), 'exec'), result.__dict__)
    return result


def role_contract() -> dict[str, Any]:
    tree = ast.parse((ROOT / 'app/security/rbac.py').read_text())
    nodes = [node for node in tree.body if (
        isinstance(node, ast.ClassDef) and node.name == 'AgentRole') or (
        isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
        t.id == 'ROLE_NAMESPACES' for t in node.targets))]
    ns = {'Enum': Enum}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<role-contract>', 'exec'), ns)
    return ns


@asynccontextmanager
async def visibility_fixture(scope):
    # C07 isolates ACL behavior. C15 tests the actual PostgreSQL visibility boundary.
    yield


class Scores:
    def __init__(self, size: int):
        self.size = size

    def __matmul__(self, query: Any) -> list[float]:
        return [0.9] * self.size


class RetrievalAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        roles = role_contract()
        self.roles = roles['AgentRole']
        self.policy = load('c07_policy', 'app/security/retrieval_policy.py')
        self.settings = SimpleNamespace(model_profile='legacy', reranker_provider='passthrough')
        self.log = Mock()
        self.collection = Mock()
        self.db = SimpleNamespace(execute=AsyncMock())
        self.session = Mock(__aenter__=AsyncMock(return_value=self.db),
                            __aexit__=AsyncMock(return_value=False))
        self.factory = Mock(return_value=self.session)
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.security.rbac': module('app.security.rbac', **roles),
            'app.security.retrieval_policy': self.policy,
            'app.config': module('app.config', get_settings=lambda: self.settings),
            'loguru': module('loguru', logger=self.log),
            'numpy': module('numpy', array=lambda v, **kw: v, float32=float,
                            linalg=SimpleNamespace(norm=lambda q: 0)),
            'app.core.milvus_client': module('app.core.milvus_client',
                                             get_collection=lambda: self.collection),
            'app.core.database': module('app.core.database',
                                         get_session_factory=lambda: self.factory),
            'sqlalchemy': module('sqlalchemy', text=lambda sql: sql),
            'app.rag.publication_visibility': module('app.rag.publication_visibility',
                visible_results=lambda results: results, publication_scope=visibility_fixture),
            'app.rag.model_profile': module('app.rag.model_profile',
                uses_remote_profile=lambda s: False, validate_model_profile=Mock()),
            'app.rag.remote_models': module('app.rag.remote_models', RemoteModelError=RuntimeError),
            'app.observability.tracing': module('app.observability.tracing',
                traced_span=lambda *a, **kw: nullcontext(), record_span_attributes=Mock(),
                record_span_event=Mock()),
            'app.rag.confidence': module('app.rag.confidence',
                ConfidenceDecider=SimpleNamespace(detect_scene=lambda q: 'general')),
            'app.rag.embeddings': module('app.rag.embeddings', get_embeddings=Mock()),
        }))
        self.vs = load('c07_vector', 'app/rag/vector_store.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.rag.vector_store': self.vs}))
        self.rerankers = load('c07_rerankers', 'app/rag/reranker.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.rag.reranker': self.rerankers}))
        self.retriever = load('c07_retriever', 'app/rag/retriever.py')
        self.degradation = load('c07_degradation', 'app/rag/degradation.py')
        self.keyword = self.degradation.KeywordRetriever()

    def fixture(self) -> list[Any]:
        rows = []
        for i, namespace in enumerate(['shared_company', 'dept_sales', 'dept_finance',
                                       'dept_cs', 'dept_hr', 'restricted_exec']):
            rows.append(self.vs.SearchResult(str(i), str(i), 'title-' + namespace,
                'policy body-' + namespace, .9, namespace, 'policy', 'source-' + namespace, 123,
                [role.value for role in self.roles], True))
        rows += [replace(rows[0], chunk_id='inactive', is_active=False),
                 replace(rows[0], chunk_id='denied', access_roles=[]),
                 replace(rows[0], chunk_id='wrong-type', doc_type='faq')]
        return rows

    def set_rows(self, rows: list[Any]) -> None:
        self.collection.search.return_value = [[SimpleNamespace(score=r.score,
            entity=SimpleNamespace(to_dict=lambda r=r: {'fields': asdict(r)})) for r in rows]]
        self.collection.query.return_value = [asdict(r) for r in rows]
        pg_rows = [SimpleNamespace(**{**asdict(r), 'updated_at': datetime.now(UTC),
                    'status': 'active' if r.is_active else 'inactive', 'rank': r.score})
                   for r in rows]
        self.db.execute.return_value = SimpleNamespace(fetchall=lambda: pg_rows)

    async def paths(self, role: str, dept: str | None, types: list[str] | None) -> list[list[Any]]:
        rows = self.fixture()
        self.set_rows(rows)
        memory = self.vs.InMemoryVectorStore(dim=1)
        memory._chunks = rows
        memory._embeddings = Scores(len(rows))
        f = self.vs.SearchFilter(role, dept, types)
        return [memory.search([1], 20, f), self.vs.MilvusVectorStore().search([1], 20, f),
                self.keyword._scan_via_milvus(['policy'], 20, role, dept, types),
                await self.keyword._fallback_pg_tsvector(['policy'], 20, role, dept, types)]

    async def test_role_department_matrix_matches_all_four_paths(self) -> None:
        matrix = [('salesperson', 'dept_sales', {'shared_company', 'dept_sales'}),
                  ('customer_service', 'dept_cs', {'shared_company', 'dept_cs'}),
                  ('finance', 'dept_finance', {'shared_company', 'dept_finance'}),
                  ('manager', 'dept_sales', {'shared_company', 'dept_sales', 'dept_finance',
                                           'dept_cs', 'dept_hr'}),
                  ('admin', None, {'shared_company', 'dept_sales', 'dept_finance', 'dept_cs',
                                   'dept_hr', 'restricted_exec'})]
        for role, dept, expected in matrix:
            with self.subTest(role=role):
                for result in await self.paths(role, dept, ['policy']):
                    self.assertEqual({r.dept_namespace for r in result}, expected)
                    self.assertTrue(all(r.chunk_id not in {'inactive', 'denied', 'wrong-type'}
                                        for r in result))

    async def test_missing_department_is_shared_only_for_ordinary_roles(self) -> None:
        for role in ('salesperson', 'customer_service', 'finance'):
            for dept in (None, '', 'shared_company'):
                for result in await self.paths(role, dept, ['policy']):
                    self.assertEqual([r.dept_namespace for r in result], ['shared_company'])

    async def test_managers_keep_explicit_cross_department_grant_without_department(self) -> None:
        for result in await self.paths('manager', None, ['policy']):
            self.assertEqual(len(result), 5)
            self.assertNotIn('restricted_exec', [r.dept_namespace for r in result])

    async def test_empty_type_list_is_empty_in_every_backend(self) -> None:
        for result in await self.paths('admin', None, []):
            self.assertEqual(result, [])

    async def test_none_type_list_allows_all_types_but_not_foreign_or_inactive(self) -> None:
        for result in await self.paths('salesperson', 'dept_sales', None):
            self.assertEqual({(r.document_id, r.doc_type) for r in result},
                             {('0', 'policy'), ('1', 'policy'), ('0', 'faq')})

    def test_invalid_role_department_or_inactive_mode_reject_before_models(self) -> None:
        embedding, store, ranker = Mock(), Mock(), Mock()
        retriever = self.retriever.EnterpriseRAGRetriever(store, ranker, embedding)
        for role, dept in [(None, None), ('unknown', None), ('salesperson', 'dept_finance'),
                           ('manager', 'restricted_exec'), ('admin', 'x" or true'),
                           ('salesperson', 'dept_sales\\'), ('finance', '*')]:
            with self.subTest(role=role, dept=dept):
                with self.assertRaises(self.policy.RetrievalAccessError):
                    retriever.retrieve('query', role, dept)
        with self.assertRaises(self.policy.RetrievalAccessError):
            self.vs.SearchFilter('admin', active_only=False).resolve()
        embedding.embed_query.assert_not_called()
        store.search.assert_not_called()
        ranker.rerank.assert_not_called()

    def test_store_requires_explicit_scope_even_when_empty(self) -> None:
        for store in (self.vs.InMemoryVectorStore(), self.vs.MilvusVectorStore()):
            with self.assertRaises(self.policy.RetrievalAccessError):
                store.search([1])
        self.collection.search.assert_not_called()

    def test_literal_roundtrip_preserves_quotes_backslashes_and_operators(self) -> None:
        for value in ['x" or true or "x', "x' or true", 'x\\" or true', '业务_%', '\\', 'a] && x']:
            encoded = self.policy.milvus_literal(value)
            self.assertEqual(json.loads(encoded), value)
            self.assertEqual(self.keyword._escape_milvus_expr_str(value), encoded)
        for invalid in ('', 'x\n', 'x\x00', 'x\x7f', '\ud800', 'x' * 65):
            with self.assertRaises(self.policy.RetrievalAccessError):
                self.policy.milvus_literal(invalid, 64)

    def test_document_id_delete_uses_one_literal_only_in_fake_collection(self) -> None:
        store = self.vs.MilvusVectorStore()
        value = 'x" or is_active == true or "x'
        store.delete_document(value)
        expr = self.collection.delete.call_args.args[0]
        self.assertEqual(json.loads(expr.removeprefix('document_id == ')), value)
        self.collection.reset_mock()
        with self.assertRaises(self.policy.RetrievalAccessError):
            store.delete_document('\n')
        self.collection.delete.assert_not_called()

    def test_all_milvus_search_paths_share_the_expression_and_acl_fields(self) -> None:
        self.set_rows([])
        dtype = 'x" or true or "x'
        f = self.vs.SearchFilter('manager', 'dept_sales', [dtype])
        self.vs.MilvusVectorStore().search([1], filter=f)
        self.keyword._scan_via_milvus(['policy'], 5, 'manager', 'dept_sales', [dtype])
        for call in (self.collection.search.call_args, self.collection.query.call_args):
            self.assertEqual(call.kwargs['expr'], f.resolve().milvus_expression())
            self.assertIn(self.policy.milvus_literal(dtype), call.kwargs['expr'])
            self.assertIn('access_roles', call.kwargs['output_fields'])
            self.assertIn('is_active', call.kwargs['output_fields'])

    async def test_pg_uses_json_bound_values_and_plain_terms(self) -> None:
        self.set_rows([])
        term = "needle%' | !_\\"
        dtype = 'x" or true'
        await self.keyword._fallback_pg_tsvector([term], 5, 'manager', 'dept_sales', [dtype])
        sql, params = self.db.execute.call_args.args
        self.assertNotIn(term, sql)
        self.assertNotIn(dtype, sql)
        self.assertEqual(params['term_0'], term)
        self.assertEqual(json.loads(params['role']), ['manager'])
        self.assertEqual(json.loads(params['doc_types']), [dtype])
        self.assertEqual(len(json.loads(params['namespaces'])), 5)
        self.assertFalse(params['all_namespaces'])
        self.assertIn("plainto_tsquery('simple', :term_0)", sql)
        self.assertIn("ESCAPE '!'", sql)
        self.assertIn('!%', params['kw'])
        self.assertIn('!_', params['kw'])
        self.assertIn("status = 'active'", sql)
        self.assertIn('access_roles @>', sql)

    async def test_invalid_scope_never_opens_keyword_or_pg_store(self) -> None:
        for method in (self.keyword.retrieve_by_keywords, self.keyword._fallback_pg_tsvector):
            with self.assertRaises(self.policy.RetrievalAccessError):
                await method(
                    'policy' if method == self.keyword.retrieve_by_keywords else ['policy'],
                             user_role='salesperson', dept_namespace='dept_finance', top_k=5)
        self.factory.assert_not_called()
        self.collection.query.assert_not_called()

    async def test_pg_failure_returns_no_documents(self) -> None:
        self.db.execute.side_effect = RuntimeError('synthetic DB outage')
        self.assertEqual(await self.keyword._fallback_pg_tsvector(
            ['policy'], 5, 'salesperson', 'dept_sales'), [])

    def test_missing_or_malformed_result_acl_is_denied(self) -> None:
        scope = self.policy.resolve_scope('admin', None)
        good = self.fixture()[0]
        for changed in ({'access_roles': None}, {'access_roles': 'admin'}, {'is_active': 1},
                        {'dept_namespace': '*'}, {'doc_type': ''}, {'doc_type': 'x\n'},
                        {'access_roles': ['salesperson']}):
            self.assertFalse(scope.allows_result(replace(good, **changed)))
        self.assertFalse(scope.allows_result(SimpleNamespace(dept_namespace='shared_company')))

    def test_untrusted_store_results_removed_before_rerank_and_return(self) -> None:
        rows = self.fixture()
        ranker = Mock(rerank=Mock(
            side_effect=lambda query, candidates, **kw: candidates + [rows[2]]))
        retriever = self.retriever.EnterpriseRAGRetriever(Mock(search=Mock(return_value=rows)),
                                                        ranker, Mock())
        result = retriever.retrieve('query', 'salesperson', 'dept_sales', ['policy'])
        self.assertEqual([r.chunk_id for r in ranker.rerank.call_args.args[1]], ['0', '1'])
        self.assertEqual([r.chunk_id for r in result.results], ['0', '1'])
        self.assertNotIn('dept_finance', repr(result))

    async def test_degradation_carries_type_constraints_after_empty_or_failed_primary(self) -> None:
        self.set_rows(self.fixture())
        for fail in (False, True):
            primary = Mock()
            primary.retrieve.return_value = SimpleNamespace(results=[], latency_ms=0)
            if fail:
                primary.retrieve.side_effect = ValueError('synthetic store failure')
            chain = self.degradation.DegradationChain(primary)
            result = await chain.run('policy', 'salesperson', 'dept_sales', ['policy'])
            self.assertEqual([r.chunk_id for r in result.results], ['0', '1'])
            self.assertIn('doc_type in ["policy"]', self.collection.query.call_args.kwargs['expr'])

    async def test_milvus_failure_retains_type_and_role_filters_in_pg(self) -> None:
        self.set_rows(self.fixture())
        self.collection.query.side_effect = RuntimeError('synthetic Milvus outage')
        results = await self.keyword.retrieve_by_keywords(
            'policy', 20, 'finance', 'dept_finance', ['policy'])
        self.assertEqual([r.document_id for r in results], ['0', '2'])
        params = self.db.execute.call_args.args[1]
        self.assertEqual(json.loads(params['role']), ['finance'])
        self.assertEqual(json.loads(params['doc_types']), ['policy'])

    async def test_authorization_failure_never_enters_degradation(self) -> None:
        primary = Mock()
        primary.retrieve.side_effect = self.policy.RetrievalAccessError('RETRIEVAL_ACCESS_DENIED')
        chain = self.degradation.DegradationChain(primary)
        chain.keyword_retriever.retrieve_by_keywords = AsyncMock()
        with self.assertRaises(self.policy.RetrievalAccessError):
            await chain.run('policy', 'salesperson', 'dept_sales')
        chain.keyword_retriever.retrieve_by_keywords.assert_not_awaited()

    def test_invalid_document_type_inputs_reject_without_store_access(self) -> None:
        for types in ('policy', [None], [''], ['x\n'], ['x' * 33], ['policy'] * 33):
            with self.assertRaises(self.policy.RetrievalAccessError):
                self.vs.MilvusVectorStore().search(
                    [1], filter=self.vs.SearchFilter('admin', doc_types=types))
        self.collection.search.assert_not_called()

    def test_every_reranker_preserves_acl_and_source_metadata(self) -> None:
        candidate = self.fixture()[1]
        bailian = object.__new__(self.rerankers.BailianReranker)
        bailian._model = 'synthetic'
        bailian._client = Mock(rerank=Mock(return_value=[(0, .8)]))
        bge = object.__new__(self.rerankers.BgeLocalReranker)
        bge._ce = Mock(predict=Mock(return_value=[1]))
        cohere = object.__new__(self.rerankers.CohereReranker)
        cohere._api_key = 'synthetic'
        cohere._model = 'synthetic'
        llm = object.__new__(self.rerankers.LLMReranker)
        llm._llm = object()
        chain = SimpleNamespace(invoke=lambda params: SimpleNamespace(content='8'))
        class Prompt:
            def __or__(self, other):
                return chain
        with patch.dict(sys.modules, {
            'langchain_cohere': module('langchain_cohere',
                CohereRerank=lambda **kw: SimpleNamespace(
                rerank_documents=lambda docs, query: [{'index': 0, 'relevance_score': .8}])),
            'langchain_core.prompts': module('langchain_core.prompts',
                ChatPromptTemplate=SimpleNamespace(from_messages=lambda messages: Prompt())),
            'app.prompts': module('app.prompts', get_prompt=lambda name: ('synthetic', 'v1')),
        }):
            for reranker in (bailian, bge, cohere, llm, self.rerankers.PassthroughReranker()):
                result = reranker.rerank('policy', [candidate], 1)[0]
                for name in (
                    'access_roles', 'is_active', 'source_url', 'content', 'dept_namespace',
                ):
                    self.assertEqual(getattr(result, name), getattr(candidate, name))

    async def test_generation_and_citations_receive_only_authorized_rows(self) -> None:
        tree = ast.parse((ROOT / 'app/agents/knowledge.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'KnowledgeAgent')
        fn = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'run')
        coverage = SimpleNamespace(NONE=SimpleNamespace(value='none'),
                                   PARTIAL=SimpleNamespace(value='partial'))
        ns = dict(Optional=Optional, AgentResult=SimpleNamespace, RetrievalSource=SimpleNamespace,
                  time=time, datetime=datetime, logger=self.log,
                  resolve_scope=self.policy.resolve_scope,
                  Coverage=coverage, ConfidenceDecider=SimpleNamespace(
                      detect_scene=lambda q: 'general',
                      combine_score=lambda **kw: .9))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<knowledge-run>', 'exec'), ns)
        decision = SimpleNamespace(coverage=SimpleNamespace(value='full'),
                                   threshold_used=.7, reason='test')
        owner = SimpleNamespace(user_role='salesperson', user_dept='dept_sales', rerank_top_k=5,
            degradation_chain=SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(
                results=self.fixture(), stage='vector'))),
            _generate_answer=AsyncMock(return_value=('safe answer', .9)),
            decider=SimpleNamespace(decide=lambda **kw: decision),
            _apply_decision=lambda answer, decision: (answer, ''))
        with patch.dict(sys.modules, {
            'app.graph.history': module('app.graph.history',
                                        expand_query_with_history=lambda q, h: q),
            'app.observability.token_usage': module('app.observability.token_usage',
                                                    snapshot_total_tokens=lambda: 0),
        }):
            result = await ns['run'](owner, 'policy')
        self.assertTrue(result.success)
        sent = owner._generate_answer.call_args.args[1]
        self.assertEqual({r.chunk_id for r in sent}, {'0', '1', 'wrong-type'})
        self.assertNotIn('dept_finance', repr(result))
        self.assertTrue(all(source.namespace in {'dept_sales', 'shared_company'}
                            for source in result.sources))


if __name__ == '__main__':
    sys.dont_write_bytecode = True

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event == 'socket.__new__' and args[1] == 1:
            return  # asyncio local wake-up pipe only.
        if event.startswith(('socket.', 'subprocess.')) or event in {
            'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod',
        }:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                                or isinstance(args[2], int) and args[2] & 3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')

    sys.addaudithook(guard)
    unittest.main(verbosity=2)
