"""Offline C02 contract tests; adapters are fakes, never model/runtime acceptance."""
from __future__ import annotations

import ast
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile = load('model_profile_test_target', 'app/rag/model_profile.py')


def settings(**changes: Any) -> SimpleNamespace:
    fields = dict(
        app_env='prod', model_profile='bailian-deepseek-v1', embedding_provider='bailian',
        embedding_dim=1024, reranker_provider='bailian', local_model_device='cpu',
        llm_provider='openai_compatible', openai_api_key='synthetic-llm-key',
        openai_base_url='https://api.deepseek.com/v1', primary_llm_model='deepseek-v4-pro',
        lite_llm_model='deepseek-flash', hf_home='/data/hf_cache',
        embedding_model='text-embedding-v4', reranker_model='qwen3-rerank',
        embedding_api_key='synthetic-embedding-key', reranker_api_key='synthetic-rerank-key',
        embedding_base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
        reranker_base_url='https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank',
        milvus_collection=profile.COLLECTION, model_startup_probes_enabled=True,
        model_http_timeout_seconds=30, model_http_max_retries=2,
        primary_llm_temperature=0.2, primary_llm_max_tokens=2048,
        local_llm_model='unused', local_llm_base_url='http://unused.invalid/v1',
    )
    fields.update(changes)
    return SimpleNamespace(**fields)


def module(name: str, **attrs: Any) -> ModuleType:
    result = ModuleType(name)
    result.__dict__.update(attrs)
    return result


def stubs(config: SimpleNamespace) -> dict[str, ModuleType]:
    return {
        'app.config': module('app.config', get_settings=lambda: config),
        'app.rag.model_profile': profile,
        'loguru': module('loguru', logger=Mock()),
        'langchain_core.language_models': module('langchain_core.language_models', BaseChatModel=object),
        'langchain_core.embeddings': module('langchain_core.embeddings', Embeddings=object),
        'app.observability.token_usage': module('app.observability.token_usage',
                                                get_token_usage_handler=lambda: None),
    }


class ModelProfileTests(unittest.IsolatedAsyncioTestCase):
    def test_profile_contract_rejects_independent_invalid_fields(self) -> None:
        self.assertEqual(profile.validate_model_profile(settings()), [])
        changes = dict(model_profile='', embedding_provider='mock', embedding_dim=1536,
                       reranker_provider='passthrough', llm_provider='local', openai_api_key='',
                       embedding_api_key='', reranker_api_key='', primary_llm_model='',
                       lite_llm_model='deepseek-v4-flash', embedding_model='BAAI/bge-m3',
                       reranker_model='BAAI/bge-reranker-large',
                       openai_base_url='https://u:p@example.invalid/v1',
                       embedding_base_url='https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
                       reranker_base_url='http://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank',
                       milvus_collection='enterprise_knowledge', model_http_max_retries=3,
                       model_http_timeout_seconds=0)
        for field, value in changes.items():
            with self.subTest(field=field):
                errors = profile.validate_model_profile(settings(**{field: value}))
                self.assertTrue(errors)
                self.assertTrue(all(code.startswith('MODEL_') for code in errors))

    def test_endpoints_reject_credentials_redirect_domains_and_query(self) -> None:
        for value in ('https://dashscope.aliyuncs.com.evil.invalid/compatible-mode/v1',
                      'https://dashscope.aliyuncs.com:bad/compatible-mode/v1',
                      'https://dashscope.aliyuncs.com/compatible-mode/v1?key=private',
                      'https://dashscope.aliyuncs.com/compatible-mode/v1#private'):
            self.assertIn('MODEL_CONFIG_EMBEDDING_BASE_URL',
                          profile.validate_model_profile(settings(embedding_base_url=value)))
        self.assertEqual(profile.validate_model_profile(settings(
            embedding_base_url='https://workspace-123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
        )), [])

    async def test_disabled_paid_probes_never_call_adapters(self) -> None:
        with patch.object(profile, '_probe_remote_models') as remote, \
                patch.object(profile, '_probe_llms', new_callable=AsyncMock) as llms:
            with self.assertRaisesRegex(RuntimeError, '^MODEL_STARTUP_PROBES_NOT_AUTHORIZED$'):
                await profile.verify_model_startup(settings(model_startup_probes_enabled=False))
            remote.assert_not_called()
            llms.assert_not_awaited()

    async def test_development_does_not_probe(self) -> None:
        with patch.object(profile, '_probe_remote_models') as local, \
                patch.object(profile, '_probe_llms', new_callable=AsyncMock) as llms:
            await profile.verify_model_startup(settings(app_env='dev'))
            local.assert_not_called()
            llms.assert_not_awaited()

    async def test_invalid_config_stops_before_probes(self) -> None:
        with patch.object(profile, '_probe_remote_models') as local:
            with self.assertRaisesRegex(RuntimeError, 'MODEL_PROFILE_INVALID'):
                await profile.verify_model_startup(settings(model_profile=''))
            local.assert_not_called()

    async def test_probes_pass_and_errors_are_redacted(self) -> None:
        with patch.object(Path, 'is_dir', return_value=True), \
                patch.object(profile, '_probe_remote_models') as local, \
                patch.object(profile, '_probe_llms', new_callable=AsyncMock) as llms:
            await profile.verify_model_startup(settings())
            local.assert_called_once_with(1024)
            llms.assert_awaited_once()
            local.side_effect = ImportError('SYNTHETIC_SECRET')
            with self.assertRaisesRegex(RuntimeError, '^MODEL_REMOTE_STARTUP_FAILED$'):
                await profile.verify_model_startup(settings())
            local.side_effect = None
            llms.side_effect = TimeoutError('SYNTHETIC_SECRET')
            with self.assertRaisesRegex(RuntimeError, '^MODEL_LLM_STARTUP_FAILED$'):
                await profile.verify_model_startup(settings())

    def test_vector_dimension_finite_and_nonzero(self) -> None:
        profile._check_vector([1.0]*1024, 1024)
        for vector in ([1.0], [0.0]*1024, [float('nan')]*1024, [float('inf')]*1024):
            with self.assertRaises(ValueError):
                profile._check_vector(vector, 1024)

    def test_remote_probe_exercises_actual_search_result_contract(self) -> None:
        # Compile only the real dataclass; importing vector_store would require numpy.
        tree = ast.parse((ROOT/'app/rag/vector_store.py').read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'SearchResult')
        ns = {'dataclass': dataclass, 'field': field}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), '<SearchResult>', 'exec'), ns)
        embeddings = Mock()
        embeddings.embed_query.return_value = [1.0]*1024
        embeddings.embed_documents.return_value = [[1.0]*1024]
        class FakeBailian:
            def rerank(self, query: str, candidates: list[Any], top_n: int) -> list[Any]:
                return candidates[:top_n]
        deps = {
            'app.rag.embeddings': module('app.rag.embeddings', get_embeddings=lambda: embeddings),
            'app.rag.reranker': module('app.rag.reranker', BailianReranker=FakeBailian,
                                       get_reranker=FakeBailian),
            'app.rag.vector_store': module('app.rag.vector_store', SearchResult=ns['SearchResult']),
        }
        with patch.dict(sys.modules, deps):
            profile._probe_remote_models(1024)
            embeddings.embed_query.assert_called_once()
            embeddings.embed_documents.assert_called_once()
            embeddings.embed_documents.return_value = []
            with self.assertRaises(ValueError):
                profile._probe_remote_models(1024)

    async def test_llm_probe_requires_primary_and_lite_nonempty_response(self) -> None:
        primary, lite = Mock(), Mock()
        primary.ainvoke = AsyncMock(return_value=SimpleNamespace(content='OK'))
        lite.ainvoke = AsyncMock(return_value=SimpleNamespace(content='OK'))
        router = SimpleNamespace(get_primary=lambda: primary, get_cloud_lite=lambda: lite)
        with patch.dict(sys.modules, {'app.rag.llm': module('app.rag.llm',
                                                          get_llm_router=lambda: router)}):
            await profile._probe_llms()
            primary.ainvoke.assert_awaited_once()
            lite.ainvoke.assert_awaited_once()
            lite.ainvoke.return_value = SimpleNamespace(content='')
            with self.assertRaises(ValueError):
                await profile._probe_llms()
            primary.ainvoke.side_effect = TimeoutError('synthetic timeout')
            with self.assertRaises(TimeoutError):
                await profile._probe_llms()

    def test_production_llm_routes_never_construct_ollama(self) -> None:
        config = settings()
        deps = stubs(config)
        chat = Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
        deps['langchain_openai'] = module('langchain_openai', ChatOpenAI=chat)
        with patch.dict(sys.modules, deps):
            llm = load('profile_llm_test', 'app/rag/llm.py')
            router = llm.LLMRouter()
            with patch.object(router, '_get_local_chat_model', side_effect=AssertionError):
                self.assertEqual(router.get_primary().model, 'deepseek-v4-pro')
                self.assertEqual(router.get_lite().model, 'deepseek-flash')
                self.assertIs(router.get_local(), router.get_lite())
                self.assertEqual(router.get_lite().extra_body, {'thinking': {'type': 'disabled'}})
            config.openai_api_key = ''
            with self.assertRaises(RuntimeError):
                llm.LLMRouter().get_primary()
            with self.assertRaises(RuntimeError):
                llm.LLMRouter().get_lite()

    def test_reranker_failure_is_fatal_only_in_production(self) -> None:
        config = settings()
        deps = stubs(config)
        deps['app.rag.vector_store'] = module('app.rag.vector_store', SearchResult=object)
        with patch.dict(sys.modules, deps):
            rerank = load('profile_reranker_test', 'app/rag/reranker.py')
            with patch.object(rerank, 'BailianReranker', side_effect=ImportError('private')):
                with self.assertRaisesRegex(RuntimeError, '^MODEL_RERANKER_LOAD_FAILED$'):
                    rerank.get_reranker()
                self.assertIsNone(rerank._reranker)
                config.app_env = 'dev'
                config.model_profile = ''
                config.reranker_provider = 'passthrough'
                self.assertIsInstance(rerank.get_reranker(), rerank.PassthroughReranker)

    def test_remote_development_routes_skip_ollama(self) -> None:
        config = settings(app_env='dev', openai_base_url='https://api.deepseek.com:443/v1')
        deps = stubs(config)
        deps['langchain_openai'] = module('langchain_openai', ChatOpenAI=lambda **kw: SimpleNamespace(**kw))
        with patch.dict(sys.modules, deps):
            target = load('remote_dev_llm_test', 'app/rag/llm.py')
            router = target.LLMRouter()
            with patch.object(router, '_get_local_chat_model', side_effect=AssertionError):
                self.assertEqual(router.get_lite().model, 'deepseek-flash')
                self.assertEqual(router.get_primary().model, 'deepseek-v4-pro')
                self.assertIs(router.get_local(), router.get_lite())
                self.assertEqual(router.get_lite().extra_body, {'thinking': {'type': 'disabled'}})
                self.assertEqual(router.get_primary().extra_body, {'thinking': {'type': 'disabled'}})

    def test_legacy_development_keeps_local_route(self) -> None:
        config = settings(app_env='dev', model_profile='')
        deps = stubs(config)
        deps['langchain_openai'] = module('langchain_openai', ChatOpenAI=Mock())
        with patch.dict(sys.modules, deps):
            target = load('legacy_dev_llm_test', 'app/rag/llm.py')
            router = target.LLMRouter()
            local = object()
            with patch.object(router, '_get_local_chat_model', return_value=local):
                self.assertIs(router.get_lite(), local)

    async def test_api_and_worker_stop_before_database_on_failed_probe(self) -> None:
        # Execute each real entry function, stopping at the injected failing probe.
        for source, name in [('app/main.py','lifespan'), ('app/worker.py','main')]:
            with self.subTest(source=source):
                tree = ast.parse((ROOT/source).read_text())
                fn = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                          and node.name == name)
                database = AsyncMock()
                ns = dict(asynccontextmanager=asynccontextmanager, FastAPI=object,
                          get_settings=settings, logger=Mock(), init_db=database,
                          validate_production_settings=lambda config: [])
                exec(compile(ast.Module(body=[fn], type_ignores=[]), source, 'exec'), ns)
                guard = AsyncMock(side_effect=RuntimeError('MODEL_PROBE_FAILED'))
                with patch.dict(sys.modules, {'app.rag.model_profile':
                                               module('app.rag.model_profile',
                                                      verify_model_startup=guard)}):
                    with self.assertRaisesRegex(RuntimeError, 'MODEL_PROBE_FAILED'):
                        if name == 'lifespan':
                            async with ns[name](object()):
                                self.fail('startup must fail')
                        else:
                            await ns[name]()
                database.assert_not_awaited()
                guard.assert_awaited_once()

    def test_build_and_dependency_contract(self) -> None:
        docker = (ROOT/'Dockerfile.prod').read_text()
        self.assertIn('ARG INSTALL_ML=0', docker)
        self.assertNotIn('then \\\n      --mount', docker)
        self.assertIn('-c requirements-prod.txt -r requirements-ml.txt', docker)
        self.assertIn('RUN /opt/venv/bin/pip check', docker)
        self.assertIn('INSTALL_ML=0', (ROOT.parent/'.github/workflows/ci.yml').read_text())
        for filename in ('pyproject.toml','requirements.txt','deploy/requirements-prod.txt'):
            content = (ROOT/filename).read_text()
            for dependency in ('langgraph-checkpoint-postgres', 'psycopg', 'psycopg-pool'):
                self.assertIn(dependency, content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
