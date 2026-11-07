"""Synthetic numeric boundaries; not calibrated confidence or live RAG acceptance."""
from __future__ import annotations

from concurrent.futures import CancelledError
from dataclasses import asdict, replace
from fractions import Fraction
from pathlib import Path
import runpy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from app.core.execution_budget import ExecutionBudgetExceeded
from app.rag.confidence import ConfidenceDecider
from app.rag.score_admission import ScoreAdmissionError, check_result_scores, finite_score
from app.rag.vector_store import ChunkData, InMemoryVectorStore, SearchFilter

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'tests/test_retrieval_authorization.py'))
GENERATE = runpy.run_path(str(ROOT / 'tests/test_rag_trust_boundary.py'))
TIMES = runpy.run_path(str(ROOT / 'tests/test_citation_time.py'))
BAD = [float('nan'), float('inf'), -float('inf'), True, False, '.8', None]
MARKER = 'SYNTHETIC provider text must not become a public failure'


@pytest.mark.parametrize('value', [0, 1, -.5, 1.5, -1e308, 1e308, np.float32(.5),
                                  np.float64(.5), np.int64(1), Fraction(1, 2)])
def test_finite_real_scalars_are_admitted_without_normalization(value):
    assert finite_score(value) == float(value)


@pytest.mark.parametrize('value', [*BAD, np.bool_(True), np.array(.8), [], {}, 1+0j,
                                  10**1000, 'NaN', MARKER])
def test_invalid_values_are_fixed_errors_instead_of_coercion_or_clipping(value):
    with pytest.raises(ScoreAdmissionError, match='^RAG_SCORE_INVALID$'):
        finite_score(value)


def test_opaque_input_is_not_coerced_or_rendered():
    class Opaque:
        def __float__(self):
            raise AssertionError('COERCION_NOT_ALLOWED')

        def __str__(self):
            raise AssertionError('RENDERING_NOT_ALLOWED')

        __repr__ = __str__

    with pytest.raises(ScoreAdmissionError, match='^RAG_SCORE_INVALID$'):
        finite_score(Opaque())


def test_float_conversion_error_is_sanitized():
    class BrokenFloat(float):
        def __float__(self):
            raise ValueError(MARKER)

    with pytest.raises(ScoreAdmissionError, match='^RAG_SCORE_INVALID$') as caught:
        finite_score(BrokenFloat(.8))
    assert MARKER not in str(caught.value)


@pytest.mark.parametrize('error', [ExecutionBudgetExceeded, CancelledError])
def test_numeric_guard_does_not_swallow_interrupts(error):
    class InterruptedFloat(float):
        def __float__(self):
            raise error()

    with pytest.raises(error):
        finite_score(InterruptedFloat(.8))


@pytest.mark.parametrize('value', BAD)
@pytest.mark.parametrize('operation', ['decide', 'combine'])
def test_invalid_confidence_inputs_never_become_high_or_skip_hint(value, operation):
    with pytest.raises(ScoreAdmissionError):
        if operation == 'decide':
            ConfidenceDecider().decide(value)
        else:
            ConfidenceDecider.combine_score(value)


@pytest.mark.parametrize('value', [*BAD[:6]])
@pytest.mark.parametrize('operand', ['self_score', 'weight'])
def test_invalid_weighted_operands_are_rejected(value, operand):
    kwargs = {'retrieval_score': .6, 'llm_self_score': .8, 'retrieval_weight': .6}
    kwargs['llm_self_score' if operand == 'self_score' else 'retrieval_weight'] = value
    with pytest.raises(ScoreAdmissionError):
        ConfidenceDecider.combine_score(**kwargs)


def test_nonfinite_arithmetic_result_is_not_clipped_into_success():
    with pytest.raises(ScoreAdmissionError):
        ConfidenceDecider.combine_score(1e308, 0.0, 1e308)


@pytest.mark.parametrize('retrieval,self_score,weight', [
    (-.5, None, .6), (1.5, None, .6), (.0, .0, .6), (.2, .9, .6),
    (.5, .8, .6), (.9, .0, .6), (.1, .9, .0), (.1, .9, 1.0),
    (np.float32(.7), np.float32(.3), .6), (np.float64(.7), None, .6),
])
def test_accepted_confidence_arithmetic_exactly_matches_the_legacy_formula(
        retrieval, self_score, weight):
    # Compatibility oracle: original formula/operand order, not a recalibration target.
    expected = max(0.0, min(1.0, retrieval)) if self_score is None else max(
        0.0, min(1.0, retrieval * weight + self_score * (1.0 - weight)))
    assert ConfidenceDecider.combine_score(retrieval, self_score, weight) == expected


@pytest.mark.parametrize('score,scene,coverage,action', [
    (-.5, 'policy', 'none', 'reject'), (.199, 'factual', 'none', 'reject'),
    (.2, 'policy', 'partial', 'answer_with_hint'), (.799, 'policy', 'partial', 'answer_with_hint'),
    (.8, 'policy', 'full', 'answer'), (.6, 'factual', 'full', 'answer'),
    (.5, 'inferential', 'full', 'answer'), (.6, 'unknown', 'full', 'answer'),
    (.899, 'policy', 'full', 'answer'), (.9, 'policy', 'high', 'answer_skip_hint'),
    (1.5, 'policy', 'high', 'answer_skip_hint'),
])
def test_finite_scene_threshold_and_boundary_decisions_are_unchanged(
        score, scene, coverage, action):
    decider = ConfidenceDecider()
    result = decider.decide(score, scene)
    assert result.coverage.value == coverage and result.action == action
    assert decider.thresholds == {'policy': .8, 'factual': .6, 'inferential': .5, 'default': .6}
    assert decider.reject_min == .2 and decider.accept_skip == .9


def test_result_admission_rejects_nonfirst_row_without_mutating_input():
    rows = [NS(score=.8), NS(score=float('nan'))]
    with pytest.raises(ScoreAdmissionError):
        check_result_scores(rows)
    assert len(rows) == 2 and rows[0].score == .8


def test_missing_source_score_has_the_same_fixed_failure():
    with pytest.raises(ScoreAdmissionError, match='^RAG_SCORE_INVALID$'):
        check_result_scores([NS(score=.8), NS()])


def test_actual_numpy_memory_search_cannot_promote_nan_similarity_to_one():
    store = InMemoryVectorStore(dim=1)
    store.add_documents([ChunkData('synthetic-chunk', 'synthetic-doc', 'Synthetic',
                                  'Synthetic content', [1.0])])
    with pytest.raises(ScoreAdmissionError):
        store.search([float('nan')], filter=SearchFilter('salesperson', 'dept_sales'))


class Scores:
    def __init__(self, values):
        self.values = values

    def __matmul__(self, query):
        return self.values


class RetrievalNumericalTests(BASE['RetrievalAuthorizationFixture']):
    def memory(self, rows):
        store = self.vs.InMemoryVectorStore(dim=1)
        store._chunks = rows
        store._embeddings = Scores([r.score for r in rows])
        return store

    def search(self, rows, backend, top_k=5):
        self.set_rows(rows)
        store = self.memory(rows) if backend == 'memory' else self.vs.MilvusVectorStore()
        scope = self.vs.SearchFilter('salesperson', 'dept_sales', ['policy'])
        return store.search([1], top_k, scope)

    def retriever_for(self, rows, ranker=None):
        ranker = ranker or self.rerankers.PassthroughReranker()
        store = Mock(search=Mock(return_value=rows))
        embeddings = Mock(embed_query=Mock(return_value=[1]))
        return self.retriever.EnterpriseRAGRetriever(store, ranker, embeddings)

    def test_raw_invalid_scores_fail_entire_authorized_batch_before_top_k(self):
        originals = self.fixture()[:2]
        for backend in ('memory', 'milvus'):
            for bad in BAD:
                with self.subTest(backend=backend, kind=type(bad).__name__):
                    rows = [originals[0], replace(originals[1], score=bad)]
                    with self.assertRaisesRegex(ScoreAdmissionError, '^RAG_SCORE_INVALID$'):
                        self.search(rows, backend, top_k=1)
                    self.assertEqual(len(rows), 2)

    def test_memory_clipping_raw_order_ties_and_milvus_cosine_are_preserved(self):
        original = self.fixture()[0]
        rows = [replace(original, chunk_id=str(i), score=s)
                for i, s in enumerate((1.5, -.5, 2.0, 1.5))]
        before = [asdict(r) for r in rows]
        memory = self.search(rows, 'memory')
        milvus = self.search(rows, 'milvus')
        self.assertEqual([r.chunk_id for r in memory], ['2', '0', '3', '1'])
        self.assertEqual([r.score for r in memory], [1.0, 1.0, 1.0, 0.0])
        self.assertEqual([r.chunk_id for r in milvus], ['0', '1', '2', '3'])
        self.assertEqual([r.score for r in milvus], [1.5, -.5, 2.0, 1.5])
        self.assertEqual([asdict(r) for r in rows], before)

    def test_denied_raw_scores_do_not_influence_allowed_results(self):
        rows = self.fixture()
        rows = [r if i < 2 else replace(r, score=float('nan')) for i, r in enumerate(rows)]
        for backend in ('memory', 'milvus'):
            with self.subTest(backend=backend):
                result = self.search(rows, backend)
                self.assertEqual([r.chunk_id for r in result], ['0', '1'])

    def test_visible_coarse_invalid_score_prevents_reranking(self):
        rows = self.fixture()[:2]
        rows[1] = replace(rows[1], score=float('nan'))
        ranker = Mock(rerank=Mock())
        with self.assertRaises(ScoreAdmissionError):
            self.retriever_for(rows, ranker).retrieve('synthetic', 'salesperson', 'dept_sales')
        ranker.rerank.assert_not_called()

    def test_hidden_or_denied_coarse_scores_are_filtered_before_numeric_admission(self):
        rows = self.fixture()
        hidden = replace(rows[0], chunk_id='hidden', score=float('nan'))
        denied = replace(rows[2], score=float('nan'))
        with patch('app.rag.publication_visibility.visible_results',
                   side_effect=lambda values: [r for r in values if r.chunk_id != 'hidden']):
            result = self.retriever_for([rows[0], hidden, denied]).retrieve(
                'synthetic', 'salesperson', 'dept_sales', scene='general')
        self.assertEqual(result.results, [rows[0]])
        self.assertEqual(result.stage, 'vector')

    def test_invalid_rerank_batch_uses_existing_complete_coarse_fallback(self):
        rows = self.fixture()[:2]
        ranker = self.rerankers.Reranker('cohere')
        ranker.rerank = Mock(return_value=[rows[0], replace(rows[1], score=float('inf'))])
        result = self.retriever_for(rows, ranker).retrieve(
            'synthetic', 'salesperson', 'dept_sales', scene='general')
        self.assertEqual(result.results, rows)
        self.assertEqual(result.stage, 'vector')
        self.assertEqual(result.rerank_status.reason, 'invocation_failed')

    def test_required_remote_invalid_rerank_batch_is_fatal(self):
        rows = self.fixture()[:2]
        ranker = Mock(rerank=Mock(return_value=[replace(rows[0], score=float('nan'))]))
        with patch.object(self.retriever, 'uses_remote_profile', return_value=True):
            with self.assertRaisesRegex(RuntimeError, '^MODEL_RERANK_FAILED$'):
                self.retriever_for(rows, ranker).retrieve(
                    'synthetic', 'salesperson', 'dept_sales', scene='general')

    def test_mutated_coarse_input_cannot_escape_through_failure_fallback(self):
        rows = self.fixture()[:2]
        def mutate(query, values, top_n):
            values[1].score = float('nan')
            raise RuntimeError(MARKER)
        ranker = Mock(rerank=Mock(side_effect=mutate))
        with self.assertRaises(ScoreAdmissionError):
            self.retriever_for(rows, ranker).retrieve(
                'synthetic', 'salesperson', 'dept_sales', scene='general')

    async def test_degradation_does_not_turn_numeric_error_into_empty_success(self):
        primary = Mock(retrieve=Mock(side_effect=ScoreAdmissionError()))
        chain = self.degradation.DegradationChain(primary)
        chain.keyword_retriever.retrieve_by_keywords = AsyncMock(return_value=[])
        with self.assertRaises(ScoreAdmissionError):
            await chain.run('synthetic', 'salesperson', 'dept_sales')
        chain.keyword_retriever.retrieve_by_keywords.assert_not_awaited()

    async def test_selector_checks_injected_primary_and_keyword_batches(self):
        row = replace(self.fixture()[0], score=float('nan'))
        for primary_rows in ([row], []):
            with self.subTest(primary=bool(primary_rows)):
                primary = Mock(retrieve=Mock(return_value=NS(results=primary_rows, latency_ms=0)))
                chain = self.degradation.DegradationChain(primary)
                chain.keyword_retriever.retrieve_by_keywords = AsyncMock(return_value=[row])
                with self.assertRaises(ScoreAdmissionError):
                    await chain.run('synthetic', 'salesperson', 'dept_sales')

    async def test_ordinary_source_failure_and_valid_empty_keep_existing_semantics(self):
        primary = Mock(retrieve=Mock(side_effect=RuntimeError(MARKER)))
        chain = self.degradation.DegradationChain(primary)
        row = self.fixture()[0]
        fallback = self.degradation.KeywordResults([row], 'keyword_scan')
        chain.keyword_retriever.retrieve_by_keywords = AsyncMock(return_value=fallback)
        result = await chain.run('synthetic', 'salesperson', 'dept_sales')
        self.assertEqual(result.results, [row])
        self.assertEqual(result.stage, 'keyword_scan')
        chain.keyword_retriever.retrieve_by_keywords.return_value = []
        empty = await chain.run('synthetic', 'salesperson', 'dept_sales')
        self.assertEqual(empty.stage, 'none')
        self.assertIsNone(empty.error)


class KnowledgeNumericalTests(unittest.IsolatedAsyncioTestCase):
    """Reuse the actual-source fixture without collecting its existing tests twice."""
    setUp = TIMES['CitationTimeTests'].setUp

    async def test_invalid_batches_prevent_generation_including_nonfirst_scores(self):
        for bad in BAD:
            with self.subTest(kind=type(bad).__name__):
                self.owner._generate_answer.reset_mock()
                self.owner.degradation_chain.run.return_value = NS(
                    results=[NS(score=.8), NS(score=bad)], stage='vector', error=None)
                result = await self.ns['run'](self.owner, 'Synthetic query')
                self.assertFalse(result.success)
                self.assertEqual(result.error, 'KNOWLEDGE_SERVICE_FAILED')
                self.assertEqual(result.sources, [])
                self.assertNotIn('未在知识库中找到', result.output['answer'])
                self.owner._generate_answer.assert_not_awaited()

    async def test_model_cannot_mutate_nonfirst_score_and_publish_invalid_sources(self):
        rows = [NS(score=.8), NS(score=.7)]
        self.owner.degradation_chain.run.return_value = NS(results=rows, stage='vector', error=None)
        async def mutate(*args, **kwargs):
            rows[1].score = float('nan')
            return 'synthetic answer', None
        self.owner._generate_answer.side_effect = mutate
        result = await self.ns['run'](self.owner, 'Synthetic query')
        self.assertFalse(result.success)
        self.assertEqual(result.sources, [])
        self.assertEqual(result.error, 'KNOWLEDGE_SERVICE_FAILED')


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', BAD)
async def test_direct_generation_rejects_invalid_nonfirst_score_before_model(bad):
    model = NS(ainvoke=AsyncMock())
    getter = Mock(return_value=model)
    target = GENERATE['function']('app/agents/knowledge.py', '_generate_answer',
        {'get_lite_llm': getter, 'get_prompt': Mock(), 'logger': Mock()}, 'KnowledgeAgent')
    with pytest.raises(ScoreAdmissionError):
        await target(NS(), 'synthetic', [NS(score=.8), NS(score=bad)])
    getter.assert_not_called()
    model.ainvoke.assert_not_awaited()
