"""Synthetic factory/status contracts; no SDK/model/service acceptance."""
from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
import runpy
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import pytest

from app.core import execution_budget as budgets
from app.rag import reranker as target

ROOT = Path(__file__).resolve().parents[1]
PROFILE = runpy.run_path(str(ROOT / 'tests/test_model_profile.py'))
BASE = runpy.run_path(str(ROOT / 'tests/test_retrieval_authorization.py'))
MARKER = 'SYNTHETIC private-shaped credential and provider text'


@pytest.fixture
def factory(monkeypatch):
    settings = PROFILE['settings'](app_env='dev', model_profile='',
                                   reranker_provider='passthrough', cohere_api_key='',
                                   cohere_rerank_model='synthetic-cohere')
    monkeypatch.setattr(target, 'get_settings', lambda: settings)
    monkeypatch.setattr(target, '_reranker', None)
    log = Mock()
    monkeypatch.setattr(target, 'logger', log)
    constructors = {}
    for provider, name in [('bailian', 'BailianReranker'), ('local_bge', 'BgeLocalReranker'),
                           ('cohere', 'CohereReranker'), ('llm', 'LLMReranker')]:
        constructors[provider] = Mock(return_value=target.Reranker(provider))
        monkeypatch.setattr(target, name, constructors[provider])
    return NS(settings=settings, constructors=constructors, log=log)


@pytest.mark.parametrize('provider', ['bailian', 'local_bge', 'cohere', 'llm', 'passthrough'])
def test_explicit_provider_keeps_concrete_backend_and_same_config_cache(provider, factory):
    factory.settings.reranker_provider = provider
    backend = target.get_reranker()
    assert target.get_reranker() is backend
    assert backend.selection == target.RerankerSelection(
        provider, provider, 'disabled' if provider == 'passthrough' else 'none')
    for name, constructor in factory.constructors.items():
        assert constructor.call_count == int(name == provider)


@pytest.mark.parametrize('key,effective,reason', [('', 'passthrough', 'auto_no_credentials'),
                                               ('synthetic-key', 'cohere', 'none')])
def test_auto_preserves_exact_existing_mapping(key, effective, reason, factory):
    factory.settings.reranker_provider = 'auto'
    factory.settings.cohere_api_key = key
    backend = target.get_reranker()
    assert backend.selection == target.RerankerSelection('auto', effective, reason)
    for name, constructor in factory.constructors.items():
        assert constructor.call_count == int(name == effective)


def test_case_insensitive_legacy_provider_keeps_cache(factory):
    factory.settings.reranker_provider = 'COHERE'
    backend = target.get_reranker()
    factory.settings.reranker_provider = 'cohere'
    assert target.get_reranker() is backend


@pytest.mark.parametrize('provider', ['', 'coher', ' local_bge ', MARKER, None, 1])
@pytest.mark.parametrize('warm', [False, True])
def test_unknown_provider_fails_before_backend_or_cached_reuse(provider, warm, factory):
    cached = target.get_reranker() if warm else None
    factory.settings.reranker_provider = provider
    with pytest.raises(RuntimeError, match='^RERANKER_CONFIGURATION_INVALID$'):
        target.get_reranker()
    assert target._reranker is cached
    for constructor in factory.constructors.values():
        constructor.assert_not_called()
    assert MARKER not in str(factory.log.mock_calls)


@pytest.mark.parametrize('provider', ['local_bge', 'cohere', 'llm', 'auto'])
def test_optional_init_failure_records_reason_and_does_not_retry(provider, factory):
    factory.settings.reranker_provider = provider
    factory.settings.cohere_api_key = 'synthetic-key'
    effective = 'cohere' if provider == 'auto' else provider
    factory.constructors[effective].side_effect = RuntimeError(MARKER)
    backend = target.get_reranker()
    assert isinstance(backend, target.PassthroughReranker)
    assert backend.selection == target.RerankerSelection(
        provider, 'passthrough', 'initialization_failed')
    assert target.get_reranker() is backend
    factory.constructors[effective].assert_called_once()
    assert MARKER not in str(factory.log.mock_calls)


@pytest.mark.parametrize('remote', [False, True])
def test_bailian_init_failure_is_fixed_and_fatal_in_every_profile(remote, factory):
    factory.settings.reranker_provider = 'bailian'
    if remote:
        factory.settings.app_env = 'prod'
        factory.settings.model_profile = 'bailian-deepseek-v1'
    factory.constructors['bailian'].side_effect = RuntimeError(MARKER)
    with pytest.raises(RuntimeError, match='^MODEL_RERANKER_LOAD_FAILED$') as caught:
        target.get_reranker()
    assert target._reranker is None
    assert MARKER not in str(caught.value) + str(factory.log.mock_calls)


def test_invalid_remote_profile_rejects_warm_development_cache(factory):
    cached = target.get_reranker()
    factory.settings.app_env = 'prod'
    with pytest.raises(RuntimeError, match='^MODEL_PROFILE_INVALID$'):
        target.get_reranker()
    assert target._reranker is cached
    factory.constructors['bailian'].assert_not_called()


def test_valid_remote_profile_cannot_reuse_development_cache(factory):
    cached = target.get_reranker()
    factory.settings.app_env = 'prod'
    factory.settings.model_profile = 'bailian-deepseek-v1'
    factory.settings.reranker_provider = 'bailian'
    with pytest.raises(RuntimeError, match='^RERANKER_CONFIGURATION_CHANGED$'):
        target.get_reranker()
    assert target._reranker is cached
    factory.constructors['bailian'].assert_not_called()


def test_remote_profile_is_revalidated_even_with_same_backend(factory):
    factory.settings.app_env = 'prod'
    factory.settings.model_profile = 'bailian-deepseek-v1'
    factory.settings.reranker_provider = 'bailian'
    cached = target.get_reranker()
    factory.settings.embedding_dim = 1536
    with pytest.raises(RuntimeError, match='^MODEL_PROFILE_INVALID$'):
        target.get_reranker()
    assert target._reranker is cached
    factory.constructors['bailian'].assert_called_once()


@pytest.mark.parametrize('provider,field,value', [
    ('passthrough', 'reranker_provider', 'cohere'),
    ('passthrough', 'model_profile', 'other-legacy-profile'),
    ('bailian', 'reranker_model', 'other-model'),
    ('bailian', 'reranker_api_key', MARKER),
    ('bailian', 'reranker_base_url', 'https://synthetic.invalid'),
    ('bailian', 'model_http_timeout_seconds', 11),
    ('bailian', 'model_http_max_retries', 1),
    ('local_bge', 'reranker_model', 'other-model'),
    ('local_bge', 'local_model_device', 'cuda'),
    ('cohere', 'cohere_api_key', MARKER),
    ('cohere', 'cohere_rerank_model', 'other-model'),
    ('auto', 'cohere_api_key', MARKER),
    ('llm', 'local_llm_model', 'other-model'),
    ('llm', 'local_llm_base_url', 'http://synthetic.invalid'),
])
def test_relevant_config_drift_requires_restart_without_replacing_cache(
        provider, field, value, factory):
    factory.settings.reranker_provider = provider
    cached = target.get_reranker()
    calls = sum(c.call_count for c in factory.constructors.values())
    setattr(factory.settings, field, value)
    with pytest.raises(RuntimeError, match='^RERANKER_CONFIGURATION_CHANGED$') as caught:
        target.get_reranker()
    assert target._reranker is cached
    assert sum(c.call_count for c in factory.constructors.values()) == calls
    assert MARKER not in str(caught.value) + str(cached.selection) + str(factory.log.mock_calls)


def test_irrelevant_configuration_does_not_invalidate_backend(factory):
    cached = target.get_reranker()
    factory.settings.local_llm_model = 'unused-model'
    factory.settings.cohere_api_key = MARKER
    assert target.get_reranker() is cached


@pytest.mark.parametrize('provider', ['bailian', 'local_bge', 'cohere', 'llm'])
@pytest.mark.parametrize('error', [budgets.ExecutionBudgetExceeded, CancelledError,
                                  asyncio.CancelledError])
def test_constructor_interrupts_propagate_without_fallback_or_cache(provider, error, factory):
    factory.settings.reranker_provider = provider
    factory.constructors[provider].side_effect = error()
    with pytest.raises(error):
        target.get_reranker()
    assert target._reranker is None
    factory.log.warning.assert_not_called()
    factory.log.info.assert_not_called()


@pytest.mark.parametrize('warm', [False, True])
def test_closed_budget_rejects_even_cached_backend(warm, factory):
    cached = target.get_reranker() if warm else None
    with pytest.raises(budgets.ExecutionBudgetExceeded):
        with budgets.execution_budget('synthetic') as budget:
            budget.close()
            target.get_reranker()
    assert target._reranker is cached
    for constructor in factory.constructors.values():
        constructor.assert_not_called()


@pytest.mark.parametrize('fails', [False, True])
def test_constructor_cannot_close_budget_and_publish_backend_or_fallback(fails, factory):
    factory.settings.reranker_provider = 'cohere'
    def construct():
        budget.close()
        if fails:
            raise RuntimeError(MARKER)
        return target.Reranker('cohere')
    factory.constructors['cohere'].side_effect = construct
    with pytest.raises(budgets.ExecutionBudgetExceeded):
        with budgets.execution_budget('synthetic') as budget:
            target.get_reranker()
    assert target._reranker is None
    factory.log.warning.assert_not_called()


def test_constructor_configuration_drift_cannot_publish_cache(factory):
    factory.settings.reranker_provider = 'cohere'
    def construct():
        factory.settings.cohere_rerank_model = 'changed-during-init'
        return target.Reranker('cohere')
    factory.constructors['cohere'].side_effect = construct
    with pytest.raises(RuntimeError, match='^RERANKER_CONFIGURATION_CHANGED$'):
        target.get_reranker()
    assert target._reranker is None


class RetrievalStatusTests(BASE['RetrievalAuthorizationFixture']):
    def make_retriever(self, ranker):
        originals = self.fixture()
        rows = [originals[1], originals[0], originals[2], originals[-2]]
        store = Mock(search=Mock(return_value=rows))
        embedding = Mock(embed_query=Mock(return_value=[1]))
        return self.retriever.EnterpriseRAGRetriever(store, ranker, embedding), originals

    def test_passthrough_reasons_are_vector_without_success_span_or_attributes(self):
        for requested, reason in [('passthrough', 'disabled'), ('auto', 'auto_no_credentials'),
                                  ('cohere', 'initialization_failed')]:
            with self.subTest(reason=reason):
                ranker = self.rerankers.PassthroughReranker()
                ranker.selection = self.rerankers.RerankerSelection(
                    requested, 'passthrough', reason)
                retriever, originals = self.make_retriever(ranker)
                attrs, events = Mock(), Mock()
                spans = Mock(side_effect=lambda *a, **kw: nullcontext())
                with patch.object(self.retriever, 'record_span_attributes', attrs), \
                     patch.object(self.retriever, 'traced_span', spans), \
                     patch.object(self.retriever, 'record_span_event', events):
                    result = retriever.retrieve(
                        'synthetic', 'salesperson', 'dept_sales', scene='general')
                self.assertEqual(result.stage, 'vector')
                self.assertEqual(result.rerank_status, ranker.selection)
                self.assertEqual(result.results, [originals[1], originals[0]])
                self.assertNotIn('rag.rerank', [c.args[0] for c in spans.call_args_list])
                self.assertFalse(any('rag.rerank.count' in c.args[0] for c in attrs.call_args_list))
                self.assertTrue(any(c.args[0].get('rag.final.stage') == 'vector'
                                    for c in attrs.call_args_list))
                events.assert_not_called()
                self.assertNotIn('RAG 精排', str(self.log.mock_calls))

    def test_successful_scorer_records_rerank_without_changing_sources(self):
        ranker = self.rerankers.Reranker('cohere')
        ranker.rerank = Mock(side_effect=lambda q, rows, top_n: list(reversed(rows)))
        retriever, originals = self.make_retriever(ranker)
        before = [asdict(c) for c in originals]
        attrs, spans = Mock(), Mock(side_effect=lambda *a, **kw: nullcontext())
        with patch.object(self.retriever, 'record_span_attributes', attrs), \
             patch.object(self.retriever, 'traced_span', spans):
            result = retriever.retrieve('synthetic', 'salesperson', 'dept_sales', scene='general')
        self.assertEqual(result.stage, 'rerank')
        self.assertEqual(result.rerank_status, ranker.selection)
        self.assertEqual(result.results, [originals[0], originals[1]])
        self.assertEqual([asdict(c) for c in originals], before)
        self.assertIn('rag.rerank', [c.args[0] for c in spans.call_args_list])
        self.assertTrue(any('rag.rerank.count' in c.args[0] for c in attrs.call_args_list))

    def test_invocation_failure_has_fixed_per_call_state_without_mutating_selection(self):
        ranker = self.rerankers.Reranker('cohere')
        ranker.rerank = Mock(side_effect=RuntimeError(MARKER))
        retriever, originals = self.make_retriever(ranker)
        with patch.object(self.retriever, 'record_span_event') as events:
            result = retriever.retrieve('synthetic', 'salesperson', 'dept_sales', scene='general')
        self.assertEqual(result.stage, 'vector')
        self.assertEqual(result.rerank_status, self.rerankers.RerankerSelection(
            'cohere', 'passthrough', 'invocation_failed'))
        self.assertEqual(ranker.selection.reason, 'none')
        self.assertEqual(result.results, [originals[1], originals[0]])
        events.assert_called_once_with('rag.rerank_failed')
        self.assertNotIn(MARKER, str(self.log.mock_calls))

    def test_required_remote_invocation_failure_remains_fatal(self):
        ranker = self.rerankers.Reranker('bailian')
        ranker.rerank = Mock(side_effect=RuntimeError(MARKER))
        retriever, _ = self.make_retriever(ranker)
        with patch.object(self.retriever, 'uses_remote_profile', return_value=True):
            with self.assertRaisesRegex(RuntimeError, '^MODEL_RERANK_FAILED$'):
                retriever.retrieve('synthetic', 'salesperson', 'dept_sales', scene='general')

    def test_no_candidates_does_not_claim_scoring_or_invoke_backend(self):
        ranker = self.rerankers.Reranker('cohere')
        ranker.rerank = Mock()
        retriever, _ = self.make_retriever(ranker)
        retriever.vector_store.search.return_value = []
        result = retriever.retrieve('synthetic', 'salesperson', 'dept_sales', scene='general')
        self.assertEqual(result.stage, 'vector')
        self.assertIsNone(result.rerank_status)
        ranker.rerank.assert_not_called()

    async def test_primary_route_is_vector_for_both_actual_scoring_and_passthrough(self):
        for scoring in (False, True):
            with self.subTest(scoring=scoring):
                ranker = self.rerankers.Reranker('cohere') if scoring else \
                    self.rerankers.PassthroughReranker()
                if scoring:
                    ranker.rerank = Mock(side_effect=lambda q, rows, top_n: rows[:top_n])
                retriever, _ = self.make_retriever(ranker)
                result = await self.degradation.DegradationChain(retriever).run(
                    'synthetic', 'salesperson', 'dept_sales')
                self.assertEqual(result.stage, 'vector')
                self.assertTrue(result.results)

    def test_invocation_interruptions_are_not_successful_fallback(self):
        for error in (budgets.ExecutionBudgetExceeded, CancelledError, asyncio.CancelledError):
            with self.subTest(error=error):
                ranker = self.rerankers.Reranker('cohere')
                ranker.rerank = Mock(side_effect=error())
                retriever, _ = self.make_retriever(ranker)
                with self.assertRaises(error):
                    retriever.retrieve('synthetic', 'salesperson', 'dept_sales', scene='general')
