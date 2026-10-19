"""C02 offline contracts. Injected HTTP transport; no provider calls or file cleanup."""

from __future__ import annotations

import ast
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Optional
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c02_helpers", ROOT / "tests/test_model_profile.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
load, module, settings, stubs = helpers.load, helpers.module, helpers.settings, helpers.stubs


class TransportFailure(Exception):
    pass


fake_httpx = module("httpx", Client=Mock(), TransportError=TransportFailure)
with patch.dict(sys.modules, {"httpx": fake_httpx}):
    remote = load("c02_remote_target", "app/rag/remote_models.py")


def search_result_type():
    tree = ast.parse((ROOT / "app/rag/vector_store.py").read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "SearchResult")
    ns = {"dataclass": dataclass, "field": field}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), "SearchResult", "exec"), ns)
    return ns["SearchResult"]


SearchResult = search_result_type()
policy = load('c07_policy_remote_tests', 'app/security/retrieval_policy.py')
retrieval_helpers = load('c07_helpers_remote_tests', 'tests/test_retrieval_authorization.py')
role_stub = module('app.security.rbac', **retrieval_helpers.role_contract())


def candidate(index: int):
    return SearchResult(str(index), "doc", "title", "sample " + str(index), 0.2,
                        "shared_company", "policy", "https://example.invalid/source", 123,
                        ["salesperson"], True)


class RemoteModelsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.client = remote.BailianClient(
            settings().embedding_base_url, "synthetic-key", 30, 2, kind="embedding",
        )

    def test_embedding_batches_are_strings_and_preserve_input_order(self) -> None:
        texts = [str(i) for i in range(23)]
        def reply(suffix, payload):
            self.assertEqual(suffix, "/embeddings")
            self.assertEqual(payload["dimensions"], 1024)
            self.assertEqual(payload["encoding_format"], "float")
            return {"data": [{"index": i, "embedding": [float(text) + 1] * 1024}
                             for i, text in reversed(list(enumerate(payload["input"])))]}
        with patch.object(self.client, "post", side_effect=reply) as post:
            result = self.client.embed(texts, "text-embedding-v4", 1024)
            self.assertEqual([len(c.args[1]["input"]) for c in post.call_args_list], [10, 10, 3])
            self.assertEqual([v[0] for v in result], list(range(1, 24)))

    def test_embedding_empty_and_oversize_never_send(self) -> None:
        with patch.object(self.client, "post") as post:
            self.assertEqual(self.client.embed([], "text-embedding-v4", 1024), [])
            for texts in ([""], ["a", "x" * 8193], ["中" * 2731], [123]):
                with self.assertRaisesRegex(remote.RemoteModelError, "MODEL_INPUT_INVALID"):
                    self.client.embed(texts, "text-embedding-v4", 1024)
            post.assert_not_called()

    def test_embedding_rejects_missing_duplicate_or_invalid_vectors(self) -> None:
        good = {"data": [{"index": 0, "embedding": [1.0] * 1024}]}
        cases = [{}, {"data": []}, {"data": [None]}]
        for index in (-1, 1, True, "0"):
            cases.append({"data": [{"index": index, "embedding": [1.0] * 1024}]})
        for vector in (None, [1], [0.0] * 1024, [float('nan')] * 1024,
                       [float('inf')] * 1024, [True] * 1024, ['1'] * 1024):
            item = deepcopy(good)
            item['data'][0]['embedding'] = vector
            cases.append(item)
        for data in cases:
            with patch.object(self.client, "post", return_value=data):
                with self.assertRaises(remote.RemoteModelError):
                    self.client.embed(["sample"], "text-embedding-v4", 1024)
        with patch.object(self.client, "post", return_value={"data": good['data'] * 2}):
            with self.assertRaises(remote.RemoteModelError):
                self.client.embed(["one", "two"], "text-embedding-v4", 1024)

    def test_rerank_contract_sorts_valid_indices(self) -> None:
        data = {"output": {"results": [{"index": 0, "relevance_score": 0.1},
                                       {"index": 1, "relevance_score": 0.9}]}}
        with patch.object(self.client, "post", return_value=data) as post:
            self.assertEqual(self.client.rerank("q", ["a", "b"], "qwen3-rerank", 9),
                             [(1, 0.9), (0, 0.1)])
            self.assertEqual(post.call_args.args, ("/text-rerank", {
                "model": "qwen3-rerank", "input": {"query": "q", "documents": ["a", "b"]},
                "parameters": {"top_n": 2, "return_documents": False},
            }))

    def test_rerank_rejects_malformed_results(self) -> None:
        rows = [None, {"index": -1, "relevance_score": 0.2},
                {"index": 1, "relevance_score": 0.2}, {"index": True, "relevance_score": 0.2}]
        rows += [{"index": 0, "relevance_score": score}
                 for score in (None, '0.2', True, -1, 1.1, float('nan'), float('inf'))]
        for row in rows:
            with patch.object(self.client, "post", return_value={"output": {"results": [row]}}):
                with self.assertRaises(remote.RemoteModelError):
                    self.client.rerank("q", ["a"], "qwen3-rerank", 1)
        duplicate = {"index": 0, "relevance_score": 0.3}
        for output in ({}, {"results": []}, {"results": [duplicate, duplicate]}):
            with patch.object(self.client, "post", return_value={"output": output}):
                with self.assertRaises(remote.RemoteModelError):
                    self.client.rerank("q", ["a", "b"], "qwen3-rerank", 2)

    def test_rerank_input_limits_never_send(self) -> None:
        with patch.object(self.client, "post") as post:
            self.assertEqual(self.client.rerank("q", [], "qwen3-rerank", 1), [])
            for query, docs, n in [("", ["a"], 1), ("x" * 4001, ["a"], 1),
                                   ("q", ["x" * 4001], 1), ("q", ["a"] * 501, 1),
                                   ("q", ["a"], 0), ("q", ["a"], True)]:
                with self.assertRaises(remote.RemoteModelError):
                    self.client.rerank(query, docs, "qwen3-rerank", n)
            post.assert_not_called()

    def test_http_retries_transient_errors_and_closes_client(self) -> None:
        for first in (TransportFailure("private"), Mock(status_code=408),
                      Mock(status_code=429), Mock(status_code=503)):
            response = Mock(status_code=200)
            response.json.return_value = {"data": []}
            transport = Mock()
            transport.post.side_effect = [first, response]
            manager = Mock()
            manager.__enter__ = Mock(return_value=transport)
            manager.__exit__ = Mock(return_value=False)
            with patch.object(fake_httpx, "Client", return_value=manager) as factory, \
                    patch.object(remote.time, "sleep") as sleep:
                self.assertEqual(self.client.post("/embeddings", {}), {"data": []})
                self.assertEqual(transport.post.call_count, 2)
                factory.assert_called_with(timeout=30, follow_redirects=False)
                self.assertEqual(manager.__exit__.call_count, 2)
                sleep.assert_called_once_with(0.5)

    def test_http_permanent_errors_do_not_retry_or_expose_bodies(self) -> None:
        for status in (301, 400, 401, 403, 404, 422):
            response = Mock(status_code=status, text="SYNTHETIC_SECRET")
            transport = Mock()
            transport.post.return_value = response
            manager = Mock(__enter__=Mock(return_value=transport), __exit__=Mock(return_value=False))
            with patch.object(fake_httpx, "Client", return_value=manager):
                with self.assertRaisesRegex(remote.RemoteModelError, '^MODEL_REMOTE_REJECTED$'):
                    self.client.post("/embeddings", {})
                self.assertEqual(transport.post.call_count, 1)
                response.json.assert_not_called()

    def test_http_retry_exhaustion_and_invalid_json_are_safe(self) -> None:
        for response in (TransportFailure("SYNTHETIC_SECRET"), Mock(status_code=503)):
            transport = Mock()
            transport.post.side_effect = [response] * 3
            manager = Mock(__enter__=Mock(return_value=transport), __exit__=Mock(return_value=False))
            with patch.object(fake_httpx, "Client", return_value=manager), \
                    patch.object(remote.time, "sleep"):
                with self.assertRaisesRegex(remote.RemoteModelError, '^MODEL_REMOTE_UNAVAILABLE$'):
                    self.client.post("/embeddings", {})
                self.assertEqual(transport.post.call_count, 3)
        for body in ([], {"error": "secret"}, {"code": "secret"}, ValueError("secret")):
            response = Mock(status_code=200)
            if isinstance(body, Exception):
                response.json.side_effect = body
            else:
                response.json.return_value = body
            manager = Mock(__enter__=Mock(return_value=Mock(post=Mock(return_value=response))),
                           __exit__=Mock(return_value=False))
            with patch.object(fake_httpx, "Client", return_value=manager):
                with self.assertRaisesRegex(remote.RemoteModelError, '^MODEL_REMOTE_RESPONSE_INVALID$'):
                    self.client.post("/embeddings", {})

    def test_factories_keep_keys_separate_and_preserve_metadata(self) -> None:
        deps = stubs(settings())
        deps['app.rag.remote_models'] = remote
        deps['app.rag.vector_store'] = module('app.rag.vector_store', SearchResult=SearchResult)
        with patch.dict(sys.modules, deps):
            embeddings = load('c02_embedding_factory', 'app/rag/embeddings.py')
            rerankers = load('c02_rerank_factory', 'app/rag/reranker.py')
            embedder = embeddings.EmbeddingService().get_embeddings()
            reranker = rerankers.get_reranker()
            self.assertEqual(embedder._client._api_key, 'synthetic-embedding-key')
            self.assertEqual(reranker._client._api_key, 'synthetic-rerank-key')
            candidates = [candidate(0), candidate(1)]
            with patch.object(reranker._client, 'rerank', return_value=[(1, 0.95)]):
                result = reranker.rerank('query', candidates, 1)[0]
                self.assertEqual(result.chunk_id, '1')
                self.assertEqual(result.source_url, candidates[1].source_url)
                self.assertEqual(result.updated_at, 123)
                self.assertEqual(result.score, 0.95)
                self.assertEqual(candidates[1].score, 0.2)

    async def test_remote_failure_cannot_enter_keyword_fallback(self) -> None:
        tree = ast.parse((ROOT / 'app/rag/degradation.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DegradationChain')
        keyword = SimpleNamespace(_settings=settings(), retrieve_by_keywords=Mock())
        ns = dict(Optional=Optional, DegradationResult=object, time=time, logger=Mock(),
                  KeywordRetriever=lambda: keyword, resolve_scope=policy.resolve_scope,
                  publication_scope=lambda scope: nullcontext(), visible_results=lambda rows: rows,
                  RetrievalAccessError=policy.RetrievalAccessError)
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'degradation', 'exec'), ns)
        primary = Mock()
        primary.retrieve.side_effect = remote.RemoteModelError('MODEL_RERANK_FAILED')
        deps = {'app.rag.model_profile': helpers.profile, 'app.rag.remote_models': remote,
                'app.security.rbac': role_stub}
        with patch.dict(sys.modules, deps):
            with self.assertRaisesRegex(remote.RemoteModelError, '^MODEL_RERANK_FAILED$'):
                await ns['DegradationChain'](primary).run(
                    'query', user_role='salesperson', dept_namespace='dept_sales')
        keyword.retrieve_by_keywords.assert_not_called()

    def test_retriever_does_not_swallow_remote_rerank_failure(self) -> None:
        tree = ast.parse((ROOT / 'app/rag/retriever.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'EnterpriseRAGRetriever')
        ns = dict(Optional=Optional, EnterpriseVectorStore=object, Reranker=object,
                  RetrievalResult=object, SearchResult=SearchResult, time=time, logger=Mock(),
                  get_settings=settings, uses_remote_profile=helpers.profile.uses_remote_profile,
                  traced_span=lambda *a, **kw: nullcontext(), record_span_attributes=Mock(),
                  SearchFilter=lambda **kw: kw, resolve_scope=policy.resolve_scope)
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'retriever', 'exec'), ns)
        store = Mock(search=Mock(return_value=[candidate(0)]))
        ranker = Mock(rerank=Mock(side_effect=ValueError('SYNTHETIC_SECRET')))
        retriever = ns['EnterpriseRAGRetriever'](store, ranker, Mock())
        with patch.dict(sys.modules, {
            'app.rag.remote_models': remote, 'app.security.rbac': role_stub,
            'app.rag.publication_visibility': module('app.rag.publication_visibility',
                visible_results=lambda rows: rows),
        }):
            with self.assertRaisesRegex(remote.RemoteModelError, '^MODEL_RERANK_FAILED$'):
                retriever.retrieve('query', 'salesperson', 'dept_sales', scene='general')


if __name__ == '__main__':
    def deny_network(event, args):
        # asyncio uses a local socketpair for its wake-up pipe; deny external I/O.
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.bind'):
            raise RuntimeError('OFFLINE_TEST_NETWORK_DENIED')
    sys.addaudithook(deny_network)
    unittest.main(verbosity=2)
