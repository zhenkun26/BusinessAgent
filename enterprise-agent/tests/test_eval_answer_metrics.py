"""C17 actual-source offline tests. No application services, writes or cleanup."""
from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
import io
import json
from pathlib import Path
import runpy
import sys
import time
from types import ModuleType, SimpleNamespace as NS
from typing import Optional
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'tests/test_retrieval_authorization.py'))


def load(name, relative):
    obj = ModuleType(name)
    obj.__file__ = str(ROOT / relative)
    sys.modules[name] = obj
    exec(compile(Path(obj.__file__).read_bytes(), obj.__file__, 'exec'), obj.__dict__)
    return obj


quality = load('c17_quality', 'eval/rag_quality.py')
with patch.dict(sys.modules, {'eval.rag_quality': quality}):
    runner = load('c17_runner', 'eval/run_eval.py')
MANIFEST, CASES = quality.load_corpus(ROOT / 'eval')


def case(**updates):
    return {**deepcopy(CASES[0]), **updates}


def observation(c=None, **updates):
    c = c or case()
    chunk = dict(document_id=c['expected_document_id'], title=c['ground_truth_doc'],
                 chunk_id='chunk', content=' '.join(c['expected_keywords']))
    return quality.Observation(**{'query_id': c['query_id'], 'retrieval_status': 'ok',
        'answer_status': 'ok', 'stage': 'vector', 'chunks': [chunk],
        'answer': chunk['content'] + ' [来源1]', 'sources': [chunk], **updates})


class MetricTests(unittest.TestCase):
    def test_frozen_122_and_six_controls(self):
        self.assertEqual(len(CASES), 128)
        self.assertEqual(sum(c['suite'] == 'primary' for c in CASES), 122)
        report = quality.aggregate_report(CASES, [], {})
        self.assertEqual(report['suites']['primary']['answer_denominator'], 115)
        self.assertEqual(report['suites']['primary']['behavior_denominator'], 7)
        self.assertEqual(report['suites']['supplemental']['answer_denominator'], 2)
        self.assertEqual(report['suites']['supplemental']['behavior_denominator'], 4)
        self.assertEqual(report['total'], 128)

    def test_all_sources_hashes_and_ground_truth_resolve(self):
        self.assertEqual(len(MANIFEST['documents']), 9)
        for c in CASES:
            if c['expected_behavior'] == 'answer':
                self.assertIsNotNone(c['source'])
                self.assertEqual(c['source']['document_id'], c['expected_document_id'])

    def test_changed_dataset_rejected(self):
        read = Path.read_bytes
        with patch.object(Path, 'read_bytes', lambda p: b'changed' if p.name == 'eval_set.json' else read(p)):
            with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                quality.load_corpus(ROOT / 'eval')

    def test_failed_answer_stays_in_denominator(self):
        cases = [case(), case(query_id='other')]
        report = quality.aggregate_report(cases, [observation(), observation(cases[1],
            answer_status='failed', answer=' '.join(cases[1]['expected_keywords']))], {})
        stats = report['suites']['primary']
        self.assertEqual(stats['avg_answer_keyword_coverage'], .5)
        self.assertEqual(stats['answer_denominator'], 2)
        self.assertEqual(stats['success_only_coverage_diagnostic'], 1)
        self.assertEqual(report['mechanical_gate'], 'FAIL')

    def test_skipped_missing_empty_zero_credit(self):
        for status in ('skipped', 'empty', 'blocked'):
            r = quality.score_sample(case(), observation(answer_status=status))
            self.assertEqual(r['answer_keyword_coverage'], 0)
        report = quality.aggregate_report([case()], [], {})
        self.assertEqual(report['samples'][0]['failure_mode'], 'retrieval_not_run')
        self.assertEqual(report['missing_observation_ids'], [case()['query_id']])
        self.assertEqual(report['suites']['primary']['avg_answer_keyword_coverage'], 0)

    def test_duplicate_or_unknown_evidence_rejected(self):
        for observations in ([observation(), observation()], [observation(query_id='unknown')]):
            with self.assertRaisesRegex(ValueError, 'ID_SET'):
                quality.aggregate_report([case()], observations, {})
        with self.assertRaisesRegex(ValueError, 'ID_SET'):
            quality.aggregate_report([case(), case()], [], {})

    def test_title_substring_and_wrong_document_never_count(self):
        for field, value in [('title', case()['ground_truth_doc'] + '其他'), ('document_id', 'other')]:
            obs = observation(); obs.chunks[0][field] = value
            self.assertEqual(quality.score_sample(case(), obs)['first_hit_rank'], 0)

    def test_strict_keywords_no_widening_or_space_normalization(self):
        self.assertEqual(quality.compute_keyword_coverage('24小时 crm', ['24 小时', 'CRM']),
                         (.5, ['CRM'], ['24 小时']))

    def test_citation_index_and_source_identity(self):
        for text in ('answer', '[来源0]', '[来源2]', '[来源1] [来源999]', '[来源1] [来源x]', '[来源' + '9' * 5000 + ']'):
            self.assertEqual(quality.score_sample(case(), observation(answer=text))[
                'citation_reference_check'], 'FAIL')
        self.assertEqual(quality.score_sample(case(), observation(sources=[]))[
            'citation_reference_check'], 'FAIL')
        self.assertEqual(quality.score_sample(case(), observation())['citation_reference_check'], 'PASS')

    def test_refusal_proxy_is_not_semantic_acceptance(self):
        c = case(expected_behavior='refuse', ground_truth_doc='', expected_keywords=[])
        r = quality.score_sample(c, observation(c, answer='无法回答'))
        self.assertTrue(r['behavior_marker_hit'])
        self.assertEqual(r['semantic_review'], 'PENDING')
        self.assertEqual(r['factual_accuracy'], 'NOT_MEASURED')

    def test_retrieval_failure_never_counts_refusal(self):
        c = case(expected_behavior='refuse', expected_keywords=[])
        r = quality.score_sample(c, observation(c, retrieval_status='failed', answer='无法回答'))
        self.assertFalse(r['behavior_marker_hit'])
        self.assertEqual(r['failure_mode'], 'retrieval_failed')

    def test_permission_checks_inspect_chunks_sources_and_final_text(self):
        c = next(c for c in CASES if c.get('forbidden_document_ids'))
        for kwargs in ({'chunks': [{'document_id': c['forbidden_document_ids'][0]}]},
                       {'sources': [{'document_id': c['forbidden_document_ids'][0]}]},
                       {'answer': '无法回答 ' + c['forbidden_keywords'][0]}):
            r = quality.score_sample(c, observation(c, **kwargs))
            self.assertEqual(r['permission_check'], 'FAIL')
        self.assertEqual(quality.score_sample(c, observation(c, answer='无法回答'))[
            'permission_check'], 'PASS')
        self.assertEqual(quality.score_sample(c, observation(c, answer_status='failed'))[
            'permission_check'], 'BLOCKED')

    def test_attribution_does_not_invent_context_assembly_bug(self):
        obs = observation(); obs.chunks[0]['content'] = 'unrelated'
        self.assertEqual(quality.score_sample(case(), obs)['failure_mode'], 'retrieved_context_keyword_gap')
        self.assertEqual(quality.score_sample(case(), observation(answer='[来源1]'))[
            'failure_mode'], 'generation_keyword_gap')
        self.assertEqual(quality.score_sample(case(), observation(answer_status='failed'))[
            'failure_mode'], 'answer_failed')

    def test_per_scene_and_difficulty_keep_failure_denominators(self):
        cs = [case(), case(query_id='other')]
        r = quality.aggregate_report(cs, [observation()], {})
        self.assertEqual(r['by_scene'][cs[0]['scene']]['answer_denominator'], 2)
        self.assertEqual(r['by_difficulty'][cs[0]['difficulty']]['avg_answer_keyword_coverage'], .5)

    def test_numerical_success_still_blocks_quality_and_release(self):
        r = quality.aggregate_report([case()], [observation()], {})
        self.assertEqual(r['mechanical_gate'], 'PASS')
        self.assertEqual(r['quality_acceptance'], 'BLOCKED')
        self.assertFalse(r['release_allowed'])

    def test_primary_and_supplemental_scores_do_not_mix(self):
        cs = [case(), case(query_id='acl', suite='supplemental')]
        r = quality.aggregate_report(cs, [observation()], {})
        self.assertEqual(r['suites']['primary']['avg_answer_keyword_coverage'], 1)
        self.assertEqual(r['suites']['supplemental']['avg_answer_keyword_coverage'], 0)

    def test_report_creation_is_exclusive_and_existing_report_preserved(self):
        path = Mock(spec=Path); path.name = 'new.json'; path.is_symlink.return_value = False
        path.open.side_effect = FileExistsError
        with self.assertRaises(FileExistsError):
            quality.save_report_json({'sample': 'preserved'}, path)
        path.open.assert_called_once_with('x', encoding='utf-8')

    def test_default_cli_is_offline_and_legacy_mutation_flags_reject(self):
        with patch.object(sys, 'argv', ['run_eval']), patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(runner.main(), 2)
            self.assertEqual(json.loads(out.getvalue())['execution'], 'NOT_RUN')
        for arg in ('--ingest', '--recreate'):
            with patch.object(sys, 'argv', ['run_eval', arg]), patch('sys.stderr', new=io.StringIO()):
                with self.assertRaises(SystemExit) as error: runner.main()
                self.assertEqual(error.exception.code, 2)

    def test_published_corpus_requires_exact_content_scope_and_generation(self):
        rows = []
        for d in MANIFEST['documents']:
            row = {**d, 'content': (ROOT / 'eval' / d['path']).read_text(), 'doc_type': 'policy',
                   'uploaded_by': 'fixture', 'source_url': '', 'status': 'active',
                   'state': 'published', 'pending_publication': None, 'active_publication': 'generation'}
            row['published_snapshot'] = deepcopy(row)
            rows.append(row)
        self.assertEqual(len(runner.validate_published_corpus(MANIFEST, rows)), 9)
        for key, val in [('content', 'changed'), ('title', 'changed'), ('access_roles', ['admin']),
                         ('pending_publication', 'new'), ('state', 'indexing')]:
            changed = deepcopy(rows); changed[0][key] = val
            with self.assertRaises(ValueError): runner.validate_published_corpus(MANIFEST, changed)
        with self.assertRaises(ValueError): runner.validate_published_corpus(MANIFEST, rows[:-1])


class PipelineTests(BASE['RetrievalAuthorizationTests']):
    async def test_actual_scan_and_pg_labels(self):
        self.set_rows(self.fixture())
        primary = Mock(retrieve=Mock(return_value=NS(results=[], latency_ms=0)))
        chain = self.degradation.DegradationChain(primary)
        result = await chain.run('policy', 'salesperson', 'dept_sales')
        self.assertEqual(result.stage, 'keyword_scan')
        self.collection.query.side_effect = RuntimeError('unavailable')
        result = await chain.run('policy', 'finance', 'dept_finance')
        self.assertEqual(result.stage, 'pg_fulltext_like')
        self.assertEqual({r.document_id for r in result.results}, {'0', '2'})

    async def test_pg_outage_and_valid_empty_are_distinct(self):
        self.set_rows([])
        chain = self.degradation.DegradationChain(Mock(retrieve=Mock(return_value=NS(results=[], latency_ms=0))))
        self.assertIsNone((await chain.run('policy', 'admin')).error)
        self.db.execute.side_effect = RuntimeError('PRIVATE_SECRET')
        result = await chain.run('policy', 'admin')
        self.assertEqual(result.stage, 'failed')
        self.assertEqual(result.error, 'RETRIEVAL_FALLBACK_UNAVAILABLE')
        self.assertNotIn('PRIVATE_SECRET', repr(result))

    async def test_actual_agent_outage_is_service_failure_not_refusal(self):
        tree = ast.parse((ROOT / 'app/agents/knowledge.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'KnowledgeAgent')
        fn = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'run')
        namespace = dict(Optional=Optional, AgentResult=NS, time=time, logger=self.log,
                         resolve_scope=self.policy.resolve_scope)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<actual-agent>', 'exec'), namespace)
        owner = NS(user_role='admin', user_dept='shared_company', rerank_top_k=5,
                   degradation_chain=NS(run=AsyncMock(return_value=self.degradation.DegradationResult(
                       [], 'failed', 0, 'RETRIEVAL_FALLBACK_UNAVAILABLE'))), _generate_answer=AsyncMock())
        with patch.dict(sys.modules, {'app.graph.history': BASE['module']('app.graph.history',
                            expand_query_with_history=lambda q, h: q)}):
            result = await namespace['run'](owner, 'policy')
        self.assertEqual(result.error, 'KNOWLEDGE_SERVICE_FAILED')
        self.assertNotIn('未在知识库中找到', result.output['answer'])
        owner._generate_answer.assert_not_awaited()

    async def test_evaluator_captures_one_actual_call_and_final_decision(self):
        c = case(); row = self.fixture()[0]
        chain = NS(run=AsyncMock(return_value=self.degradation.DegradationResult([row], 'vector', 3)))
        agent = NS(degradation_chain=chain)
        async def run(query):
            await agent.degradation_chain.run(query=query)
            return NS(error=None, output={'answer': 'final confidence decision'}, sources=[])
        agent.run = run
        result = await runner.evaluate_case(c, agent)
        chain.run.assert_awaited_once()
        self.assertEqual(result.answer, 'final confidence decision')
        self.assertEqual(result.chunks, [asdict(row)])
        self.assertIs(agent.degradation_chain, chain)

    async def test_no_answer_never_fabricates_refusal(self):
        c = case(expected_behavior='refuse', expected_keywords=[])
        agent = NS(degradation_chain=NS(run=AsyncMock(return_value=
            self.degradation.DegradationResult([], 'none', 0))), run=AsyncMock())
        obs = await runner.evaluate_case(c, agent, no_answer=True)
        self.assertEqual(obs.answer_status, 'skipped')
        self.assertEqual(obs.retrieval_status, 'empty')
        self.assertEqual(obs.answer, '')
        self.assertFalse(quality.score_sample(c, obs)['behavior_marker_hit'])
        agent.run.assert_not_awaited()

    async def test_evaluator_exception_and_cancellation(self):
        agent = NS(degradation_chain=NS(run=AsyncMock(side_effect=RuntimeError('PRIVATE_SECRET'))),
                   run=AsyncMock(side_effect=RuntimeError('PRIVATE_SECRET')))
        obs = await runner.evaluate_case(case(), agent)
        self.assertEqual(obs.answer_status, 'failed')
        self.assertNotIn('PRIVATE_SECRET', repr(obs))
        agent.run.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError): await runner.evaluate_case(case(), agent)

    async def test_read_only_milvus_never_creates_or_drops(self):
        tree = ast.parse((ROOT / 'app/core/milvus_client.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'init_milvus')
        client, utility, collection, schema = Mock(), Mock(), Mock(), Mock()
        utility.has_collection.return_value = False
        settings = NS(milvus_uri='isolated', milvus_user='', milvus_password='', milvus_collection='fixture')
        ns = dict(get_settings=lambda: settings, connections=client, utility=utility,
                  Collection=collection, build_knowledge_schema=schema, logger=Mock())
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<milvus>', 'exec'), ns)
        with self.assertRaisesRegex(ValueError, 'CONFLICT'):
            await ns['init_milvus'](True, require_existing=True)
        client.connect.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, 'EXISTING_COLLECTION'):
            await ns['init_milvus'](require_existing=True)
        utility.drop_collection.assert_not_called(); collection.assert_not_called(); schema.assert_not_called()
        utility.has_collection.return_value = True
        await ns['init_milvus'](require_existing=True)
        collection.assert_called_once_with(name='fixture', using='default')
        collection.return_value.create_index.assert_not_called()
        collection.return_value.load.assert_called_once()


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def fixtures(self):
        module = BASE['module']
        config = NS(model_profile='bailian-deepseek-v1', vector_store_provider='milvus',
            embedding_provider='bailian', embedding_model='text-embedding-v4', embedding_dim=1024,
            reranker_provider='bailian', reranker_model='qwen3-rerank', llm_provider='openai_compatible',
            lite_llm_model='deepseek-flash', primary_llm_model='deepseek-v4-pro',
            milvus_collection='isolated', openai_api_key='PRIVATE_SECRET')
        self.init_db, self.close_db = AsyncMock(), AsyncMock()
        self.init_milvus, self.close_milvus = AsyncMock(), AsyncMock()
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def snapshot(): yield
        return {
            'app.security.redaction': module('app.security.redaction', install_log_redaction=Mock()),
            'app.config': module('app.config', get_settings=lambda: config),
            'app.rag.model_profile': module('app.rag.model_profile', PROFILE='bailian-deepseek-v1',
                                            validate_model_profile=lambda s: []),
            'app.core.database': module('app.core.database', init_db=self.init_db, close_db=self.close_db),
            'app.core.milvus_client': module('app.core.milvus_client', init_milvus=self.init_milvus,
                                            close_milvus=self.close_milvus),
            'app.agents.knowledge': module('app.agents.knowledge', KnowledgeAgent=Mock()),
            'app.security.rbac': module('app.security.rbac', AgentRole=lambda r: r),
            'app.prompts': module('app.prompts', DEFAULT_PROMPTS={'knowledge_rag_answer': 'template'},
                get_prompt=lambda name: ('template', 1), request_prompt_snapshot=snapshot,
                set_prompt_user=Mock(), reset_prompt_user=Mock()),
        }

    async def test_preflight_failure_preserves_every_case_and_makes_no_model_call(self):
        modules = self.fixtures()
        with patch.dict(sys.modules, modules), patch.object(runner, 'read_published_corpus',
                AsyncMock(side_effect=ValueError('PRIVATE_SECRET'))), patch.object(
                runner, 'evaluate_case', AsyncMock()) as evaluate:
            report = await runner.execute(MANIFEST, CASES)
        evaluate.assert_not_awaited(); self.init_milvus.assert_not_awaited()
        self.assertEqual(report['total'], 128)
        self.assertEqual(report['mechanical_gate'], 'BLOCKED')
        self.assertNotIn('PRIVATE_SECRET', json.dumps(report))
        self.close_db.assert_awaited_once()

    async def test_runtime_records_prompts_and_continues_after_failed_sample(self):
        modules = self.fixtures(); cs = [case(), case(query_id='next')]
        with patch.dict(sys.modules, modules), patch.object(runner, 'read_published_corpus',
                AsyncMock(return_value={'doc': 'generation'})), patch.object(runner, 'evaluate_case',
                AsyncMock(side_effect=[observation(answer_status='failed'), observation(cs[1])])):
            report = await runner.execute(MANIFEST, cs)
        self.assertEqual(report['suites']['primary']['avg_answer_keyword_coverage'], .5)
        self.assertEqual(report['provenance']['runtime_status'], 'EXECUTED')
        self.assertEqual(report['provenance']['prompts']['knowledge_rag_answer']['version'], 1)
        self.assertNotIn('PRIVATE_SECRET', json.dumps(report))
        self.init_milvus.assert_awaited_once_with(require_existing=True)
        self.close_db.assert_awaited_once(); self.close_milvus.assert_awaited_once()

    async def test_changed_corpus_blocks_even_after_good_sample(self):
        modules = self.fixtures()
        with patch.dict(sys.modules, modules), patch.object(runner, 'read_published_corpus',
                AsyncMock(side_effect=[{'doc': 'v1'}, {'doc': 'v1'}, {'doc': 'v2'}])), patch.object(
                runner, 'evaluate_case', AsyncMock(return_value=observation())):
            report = await runner.execute(MANIFEST, [case()])
        self.assertEqual(report['samples'][0]['answer_keyword_coverage'], 1)
        self.assertEqual(report['mechanical_gate'], 'BLOCKED')
        self.assertEqual(report['quality_acceptance'], 'BLOCKED')


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(cls(name) for cls in (MetricTests, PipelineTests, RuntimeTests)
                              for name in cls.__dict__ if name.startswith('test_'))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    def guard(event, args):
        if event == 'socket.__new__' and args[1] == 1: return
        if event.startswith(('socket.', 'subprocess.', 'ctypes.')) or event in {
            'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod', 'os.chown',
            'os.truncate', 'os.utime', 'os.link', 'os.symlink', 'os.exec', 'os.posix_spawn',
            'os.fork', 'os.forkpty', 'os.putenv', 'os.unsetenv'}:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                or isinstance(args[2], int) and args[2] & 3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
