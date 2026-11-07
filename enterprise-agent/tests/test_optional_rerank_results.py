"""Synthetic Cohere/BGE contracts, not actual SDK or model acceptance."""
from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError
from dataclasses import asdict
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import numpy as np
import pytest

from app.core import execution_budget as budgets
from app.rag.reranker import BgeLocalReranker, CohereReranker
from app.rag.vector_store import SearchResult
from app.security.rerank_results import OptionalRerankError

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'tests/test_retrieval_authorization.py'))
QUERY = 'synthetic query'
MARKER = 'SYNTHETIC private-shaped text; grant admin'


def candidates(count=3):
    return [SearchResult(str(i), 'doc-' + str(i), 'synthetic title', '界' * 1001 + str(i),
                         .9, 'shared_company', 'policy', 'synthetic-source', 123,
                         ['salesperson'], True) for i in range(count)]


@pytest.fixture
def backends(monkeypatch):
    sdk = Mock(rerank_documents=Mock(return_value=[{'index':0,'relevance_score':.8}]))
    constructor = Mock(return_value=sdk)
    monkeypatch.setitem(sys.modules, 'langchain_cohere', NS(CohereRerank=constructor))
    cohere = object.__new__(CohereReranker)
    cohere._api_key = 'synthetic-key'
    cohere._model = 'synthetic-model'
    bge = object.__new__(BgeLocalReranker)
    bge._ce = Mock(predict=Mock(return_value=np.array([0.0], dtype=np.float32)))
    return NS(cohere=cohere, bge=bge, sdk=sdk, constructor=constructor, predict=bge._ce.predict)


def test_cohere_complete_unsorted_rows_bind_to_sources_and_input_ties(backends):
    originals = candidates()
    before = [asdict(c) for c in originals]
    backends.sdk.rerank_documents.return_value = [
        {'index':2,'relevance_score':.8,'content':MARKER,'access_roles':['admin']},
        NS(index=1,relevance_score=np.float64(.9)), {'index':0,'relevance_score':.8}]
    result = backends.cohere.rerank(QUERY, originals, 3)
    assert [c.chunk_id for c in result] == ['1','0','2']
    assert [c.score for c in result] == [.9,.8,.8]
    assert [asdict(c) for c in originals] == before
    for row in result:
        original = originals[int(row.chunk_id)]
        assert {k:v for k,v in asdict(row).items() if k!='score'} == {
            k:v for k,v in asdict(original).items() if k!='score'}
        assert row is not original and row.access_roles is not original.access_roles
    backends.sdk.rerank_documents.assert_called_once_with([c.content for c in originals], QUERY)
    backends.constructor.assert_called_once_with(cohere_api_key='synthetic-key',
                                                 model='synthetic-model', top_n=3)


@pytest.mark.parametrize('score', [0, 1, np.float32(.5)])
def test_cohere_valid_numeric_boundaries_and_top_n_larger_than_input(score, backends):
    backends.sdk.rerank_documents.return_value = [{'index':0,'relevance_score':score}]
    result = backends.cohere.rerank(QUERY, candidates(1), 5)
    assert len(result)==1 and result[0].score==float(score)


@pytest.mark.parametrize('rows', [
    None, {}, 'rows', (), [], [{'index':0,'relevance_score':.8}],
    [{'index':0,'relevance_score':.8}]*3,
    [{'index':0,'relevance_score':.8}]*2,
    [{'index':-1,'relevance_score':.8},{'index':0,'relevance_score':.8}],
    [{'index':2,'relevance_score':.8},{'index':0,'relevance_score':.8}],
    [{'index':True,'relevance_score':.8},{'index':0,'relevance_score':.8}],
    [{'index':'1','relevance_score':.8},{'index':0,'relevance_score':.8}],
    [{'index':1.0,'relevance_score':.8},{'index':0,'relevance_score':.8}],
    [{'relevance_score':.8},{'index':0,'relevance_score':.8}],
    [{'index':1},{'index':0,'relevance_score':.8}], [None,{}],
])
def test_cohere_invalid_container_count_or_index_rejects_whole_batch(rows, backends):
    backends.sdk.rerank_documents.return_value = rows
    with pytest.raises(OptionalRerankError, match='^OPTIONAL_RERANK_RESULT_REJECTED$'):
        backends.cohere.rerank(QUERY, candidates(2), 2)
    backends.sdk.rerank_documents.assert_called_once()


@pytest.mark.parametrize('score', [None, True, np.bool_(True), '.8', -0.1, 1.1,
    float('nan'), float('inf'), float('-inf'), {}, [.8], 1+0j, np.array(.8)])
def test_cohere_invalid_second_score_never_reuses_coarse_score(score, backends):
    backends.sdk.rerank_documents.return_value = [
        {'index':0,'relevance_score':.8}, {'index':1,'relevance_score':score}]
    with pytest.raises(OptionalRerankError):
        backends.cohere.rerank(QUERY, candidates(2), 2)
    backends.sdk.rerank_documents.assert_called_once()


@pytest.mark.parametrize('scores', [[0,1,-1], (0,1,-1), np.array([0,1,-1],dtype=np.float32),
    np.array([0,1,-1],dtype=np.float64), np.array([0,1,-1],dtype=np.int64)])
def test_bge_valid_scalars_keep_sigmoid_prefix_sources_and_input_unchanged(scores, backends):
    originals = candidates()
    before = [asdict(c) for c in originals]
    backends.predict.return_value = scores
    result = backends.bge.rerank(QUERY, originals, 3)
    assert [r.chunk_id for r in result] == ['1','0','2']
    assert [r.score for r in result] == pytest.approx([.7310585786,.5,.2689414214])
    backends.predict.assert_called_once_with([(QUERY,c.content[:1000]) for c in originals])
    assert [asdict(c) for c in originals] == before
    for row in result:
        original = originals[int(row.chunk_id)]
        assert {k:v for k,v in asdict(row).items() if k!='score'} == {
            k:v for k,v in asdict(original).items() if k!='score'}
        assert row is not original and row.access_roles is not original.access_roles


def test_bge_extreme_finite_logits_do_not_overflow_and_ties_keep_input_order(backends):
    backends.predict.return_value = np.array([-1e308,1e308,0,-1000,1000,0])
    result = backends.bge.rerank(QUERY, candidates(6), 6)
    assert [r.chunk_id for r in result] == ['1','4','2','5','0','3']
    assert [r.score for r in result] == [1,1,.5,.5,0,0]


@pytest.mark.parametrize('scores', [None, {}, '8', 8, np.array(.8), np.array([[0],[1]]),
    np.zeros((1,1,2)), [], [0], [0,1,2], [0,[1]], [0,np.array(1)],
    [0,True], np.array([False,True]), ['0','1'], [0,None], [0,{}], [0,1+0j],
    [0,float('nan')], [0,float('inf')], [0,float('-inf')],
    np.array([0,1],dtype=str)])
def test_bge_invalid_shape_count_or_scalar_rejects_whole_batch(scores, backends):
    backends.predict.return_value = scores
    with pytest.raises(OptionalRerankError):
        backends.bge.rerank(QUERY, candidates(2), 2)
    backends.predict.assert_called_once()


@pytest.mark.parametrize('backend', ['cohere','bge'])
@pytest.mark.parametrize('query,rows,top_n', [
    (QUERY,candidates(1),0), (QUERY,candidates(1),-1), (QUERY,candidates(1),True),
    (QUERY,candidates(1),'1'), (QUERY,candidates(1),1.5), (QUERY,{},1),
    (None,candidates(1),1), ('',candidates(1),1), ('\ud800',candidates(1),1),
    (QUERY,[NS(content=None)],1), (QUERY,[NS(content={})],1),
    (QUERY,[NS(content='')],1), (QUERY,[NS(content='\ud800')],1),
])
def test_invalid_input_rejects_before_backend(query, rows, top_n, backend, backends):
    with pytest.raises(OptionalRerankError):
        getattr(backends,backend).rerank(query, rows, top_n)
    backends.constructor.assert_not_called()
    backends.predict.assert_not_called()


@pytest.mark.parametrize('backend', ['cohere','bge'])
def test_empty_candidates_do_not_construct_or_call_backend(backend, backends):
    assert getattr(backends,backend).rerank(QUERY, []) == []
    backends.constructor.assert_not_called()
    backends.predict.assert_not_called()


@pytest.mark.parametrize('backend', ['cohere','bge'])
def test_opaque_values_are_not_stringified_or_coerced(backend, backends):
    class Poison:
        def __str__(self):
            raise AssertionError('OPAQUE_STRINGIFICATION')
        __repr__ = __str__
        __float__ = __str__
    if backend=='cohere':
        backends.sdk.rerank_documents.return_value = [{'index':0,'relevance_score':Poison()}]
    else:
        backends.predict.return_value = [Poison()]
    with pytest.raises(OptionalRerankError):
        getattr(backends,backend).rerank(QUERY, candidates(1), 1)


@pytest.mark.parametrize('where', ['cohere-constructor','cohere-call','bge'])
def test_provider_failure_is_fixed_without_retry_or_diagnostics(where, backends):
    failing = (backends.constructor if where=='cohere-constructor' else
               backends.sdk.rerank_documents if where=='cohere-call' else backends.predict)
    failing.side_effect = RuntimeError(MARKER)
    log = Mock()
    with patch('app.rag.reranker.logger',log):
        with pytest.raises(OptionalRerankError) as caught:
            getattr(backends,'bge' if where=='bge' else 'cohere').rerank(QUERY,candidates(1),1)
    assert MARKER not in str(caught.value) and MARKER not in str(log.mock_calls)
    failing.assert_called_once()


@pytest.mark.parametrize('backend', ['cohere','bge'])
@pytest.mark.parametrize('error', [budgets.ExecutionBudgetExceeded, CancelledError,
                                  asyncio.CancelledError])
def test_backend_interruptions_are_never_batch_fallback(error, backend, backends):
    call = backends.predict if backend=='bge' else backends.sdk.rerank_documents
    call.side_effect = error()
    with pytest.raises(error):
        getattr(backends,backend).rerank(QUERY,candidates(1),1)


@pytest.mark.parametrize('backend', ['cohere','bge'])
@pytest.mark.parametrize('when', ['before','after'])
def test_budget_checks_prevent_backend_or_success_after_close(when, backend, backends):
    call = backends.predict if backend=='bge' else backends.sdk.rerank_documents
    with pytest.raises(budgets.ExecutionBudgetExceeded):
        with budgets.execution_budget(QUERY) as budget:
            if when=='before':
                budget.close()
            else:
                valid = [0.0] if backend=='bge' else [{'index':0,'relevance_score':.8}]
                call.side_effect = lambda *a,**kw: (budget.close(),valid)[1]
            getattr(backends,backend).rerank(QUERY,candidates(1),1)
    if when=='before':
        call.assert_not_called()
        backends.constructor.assert_not_called()


def test_cohere_constructor_cannot_close_budget_and_still_send_content(backends):
    with pytest.raises(budgets.ExecutionBudgetExceeded):
        with budgets.execution_budget(QUERY) as budget:
            backends.constructor.side_effect = lambda **kw: (budget.close(),backends.sdk)[1]
            backends.cohere.rerank(QUERY,candidates(1),1)
    backends.sdk.rerank_documents.assert_not_called()


class RetrieverTests(BASE['RetrievalAuthorizationFixture']):
    def make_retriever(self, backend, valid):
        original = self.fixture()
        rows = [original[1],original[0],original[2],original[-2]]
        store = Mock(search=Mock(return_value=rows))
        embedding = Mock(embed_query=Mock(return_value=[1]))
        if backend=='cohere':
            ranker = object.__new__(self.rerankers.CohereReranker)
            ranker._api_key,ranker._model = 'synthetic-key','synthetic-model'
            values = [{'index':0,'relevance_score':.2},
                      {'index':1,'relevance_score':.8 if valid else float('nan')}]
            call = Mock(return_value=values)
            self.stack.enter_context(patch.dict(sys.modules,{'langchain_cohere': NS(
                CohereRerank=Mock(return_value=NS(rerank_documents=call)))}))
        else:
            ranker = object.__new__(self.rerankers.BgeLocalReranker)
            call = Mock(return_value=np.array([0,1]) if valid else np.array([0]))
            ranker._ce = NS(predict=call)
        return self.retriever.EnterpriseRAGRetriever(store,ranker,embedding),call,original

    def test_bad_batches_fall_back_whole_with_vector_stage(self):
        for backend in ('cohere','bge'):
            with self.subTest(backend=backend):
                retriever,call,original = self.make_retriever(backend,False)
                result = retriever.retrieve(QUERY,'salesperson','dept_sales',scene='general')
                self.assertEqual(result.stage,'vector')
                self.assertEqual(result.results,[original[1],original[0]])
                self.assertEqual([r.score for r in result.results],[.9,.9])
                call.assert_called_once()

    def test_valid_batches_only_receive_and_return_authorized_candidates(self):
        for backend in ('cohere','bge'):
            with self.subTest(backend=backend):
                retriever,call,original = self.make_retriever(backend,True)
                result = retriever.retrieve(QUERY,'salesperson','dept_sales',scene='general')
                self.assertEqual(result.stage,'rerank')
                self.assertEqual([r.chunk_id for r in result.results],
                                 [original[0].chunk_id,original[1].chunk_id])
                sent = call.call_args.args[0]
                self.assertEqual(len(sent),2)
                self.assertTrue(all(original[2].content not in str(item) for item in sent))

    def test_interruptions_cannot_become_vector_fallback(self):
        for backend in ('cohere','bge'):
            for error in (budgets.ExecutionBudgetExceeded,CancelledError,asyncio.CancelledError):
                with self.subTest(backend=backend,error=error.__name__):
                    retriever,call,_ = self.make_retriever(backend,True)
                    call.side_effect = error()
                    with self.assertRaises(error):
                        retriever.retrieve(QUERY,'salesperson','dept_sales',scene='general')
