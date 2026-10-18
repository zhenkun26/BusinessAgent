"""C15 actual-source contracts. SQL/vector/models are doubles, not runtime acceptance."""
from __future__ import annotations

import asyncio
import ast
from contextlib import asynccontextmanager, nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'tests/test_task_queue.py'))
Base, Database, load, module = (BASE[k] for k in ('QueueTests', 'Database', 'load', 'module'))


def result(rows):
    rows = deepcopy(rows)
    return NS(mappings=lambda: NS(first=lambda: rows[0] if rows else None, all=lambda: rows),
              fetchone=lambda: NS(**rows[0]) if rows else None,
              fetchall=lambda: [NS(**r) for r in rows])


class PublicationDatabase(Database):
    def __init__(self):
        super().__init__()
        self.publications = {}
        self.audits = []
        self.docs['doc1'].update(source_url='', active_publication=None, pending_publication=None)
        self.saved = self.copy()
        self.fail_after_commit = False
        self.fail_on = None

    def copy(self):
        return deepcopy((self.docs, self.publications, self.jobs, self.audits))

    @asynccontextmanager
    async def session(self):
        self.saved = self.copy()
        try:
            yield self
        except BaseException:
            await self.rollback()
            raise

    async def commit(self):
        self.commits += 1
        self.saved = self.copy()
        if self.fail_after_commit:
            raise RuntimeError('SYNTHETIC_STORE_SECRET')

    async def rollback(self):
        self.rollbacks += 1
        self.docs, self.publications, self.jobs, self.audits = deepcopy(self.saved)

    async def execute(self, sql, p=None):
        p = p or {}
        sql = ' '.join(sql.split())
        self.queries.append((sql, deepcopy(p)))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError('SYNTHETIC_STORE_SECRET')
        rows = []
        if 'p.snapshot AS published_snapshot' in sql:
            rows = [dict(d, published_snapshot=self.publications[d['active_publication']]['snapshot'],
                         chunks=self.publications[d['active_publication']]['chunks'])
                    for d in self.docs.values() if d['status'] == 'active' and d.get('active_publication')
                    and not d.get('pending_publication')]
        elif 'jsonb_to_recordset' in sql:
            rows = [dict(c, status='active', rank=1.0, updated_at=datetime.now(timezone.utc))
                    for d in self.docs.values() if d['status'] == 'active' and d.get('active_publication')
                    for c in self.publications[d['active_publication']]['chunks']]
        elif 'INSERT INTO documents' in sql:
            self.docs.setdefault(p['did'], dict(document_id=p['did'], title=p['title'], status='importing'))
        elif 'FROM documents WHERE document_id' in sql:
            rows = [self.docs[p['did']]] if p['did'] in self.docs else []
        elif 'SELECT status FROM documents' in sql:
            rows = [dict(status=self.docs[p['did']]['status'])] if p['did'] in self.docs else []
        elif 'SELECT * FROM knowledge_publications' in sql:
            rows = [r for r in self.publications.values() if r['document_id'] == p['did']
                    and r['input_hash'] == p['hash']]
        elif 'INSERT INTO knowledge_publications' in sql:
            self.publications[p['pid']] = dict(publication_id=p['pid'], document_id=p['did'],
                input_hash=p['hash'], source_hash=p['source'], snapshot=json.loads(p['snapshot']),
                chunks=json.loads(p['chunks']), reviewer=p['reviewer'], state='staging', error_code=None)
        elif "UPDATE documents SET status = 'indexing'" in sql:
            self.docs[p['did']].update(status='indexing', pending_publication=p['pid'])
        elif "UPDATE knowledge_publications SET state = 'published'" in sql:
            self.publications[p['pid']].update(state='published', error_code=None)
        elif 'UPDATE documents SET title' in sql:
            doc = self.docs[p['document_id']]
            assert doc['status'] == 'indexing' and doc['pending_publication'] == p['pid']
            doc.update({k: p[k] for k in ('title', 'content', 'doc_type', 'dept_namespace',
                                        'source_url', 'uploaded_by')})
            doc.update(status='active', active_publication=p['pid'], pending_publication=None,
                       access_roles=json.loads(p['roles']), content_hash=p['hash'])
            rows = [doc]
        elif "UPDATE documents SET status = 'rejected'" in sql:
            doc = self.docs[p['did']]
            if doc['status'] == 'draft':
                doc.update(status='rejected', reject_reason=p['reason'])
                rows = [doc]
        elif "UPDATE documents SET status = 'inactive'" in sql:
            self.docs[p['did']].update(status='inactive', pending_publication=None)
        elif 'UPDATE knowledge_publications SET error_code' in sql:
            pub = self.publications[p['pid']]
            if pub['state'] == 'staging': pub['error_code'] = 'KNOWLEDGE_INDEX_UNCONFIRMED'
        elif 'UPDATE documents SET ingest_error' in sql:
            pass
        elif 'INSERT INTO audit_logs' in sql:
            self.audits.append(json.loads(p['payload']))
        else:
            return await super().execute(sql, p)
        return result(rows)


class PublicationTests(Base):
    def setUp(self):
        super().setUp()
        self.db = PublicationDatabase()
        self.settings.embedding_provider = 'mock'
        self.settings.embedding_model = 'synthetic'
        self.settings.embedding_dim = 2
        self.publication = load('app.core.knowledge_publication', 'app/core/knowledge_publication.py')
        self.policy = load('app.security.retrieval_policy', 'app/security/retrieval_policy.py')
        self.visibility = load('app.rag.publication_visibility', 'app/rag/publication_visibility.py')
        self.scope = self.policy.RetrievalScope('admin', None, None)
        self.index = {}
        self.fail_index = False
        self.partial = False
        self.embed = Mock(embed_documents=lambda texts: [[1.0, 0.0] for t in texts])
        self.vector = NS(add_documents=Mock(side_effect=self.write_index))
        self.loader = NS(split_documents=lambda docs: [NS(page_content=t)
                         for doc in docs for t in doc.page_content.split('|')])
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.rag.document_loader': module('app.rag.document_loader', DocumentLoader=lambda **kw: self.loader),
            'app.rag.embeddings': module('app.rag.embeddings', get_embeddings=lambda: self.embed),
            'app.rag.vector_store': module('app.rag.vector_store', ChunkData=NS,
                EnterpriseVectorStore=object, get_vector_store=lambda: self.vector),
            'langchain_core.documents': module('langchain_core.documents', Document=NS),
        }))
        self.ingestion = load('c15_ingest', 'app/rag/ingest.py').MilvusIngestService(self.vector)
        self.data = dict(document_id='import1', title='Synthetic', content='alpha|beta',
                         doc_type='faq', dept_namespace='shared_company', access_roles=['admin'],
                         uploaded_by=None, source_url='')

    def write_index(self, chunks, partition):
        for chunk in chunks[:1] if self.partial else chunks:
            self.index[chunk.chunk_id] = chunk
        if self.fail_index:
            raise RuntimeError('SYNTHETIC_VECTOR_SECRET')
        return 1 if self.partial else len(chunks)

    async def ingest_data(self, **changes):
        return await self.ingestion.ingest_text(**{**self.data, **changes})

    async def visible(self):
        async with self.visibility.publication_scope(self.scope):
            return self.visibility.visible_results(list(self.index.values()))

    async def test_success_stages_before_index_and_activates_after_complete_write(self):
        def checked(chunks, partition):
            self.assertEqual(self.db.docs['import1']['status'], 'indexing')
            self.assertTrue(self.db.publications)
            return self.write_index(chunks, partition)
        self.vector.add_documents.side_effect = checked
        self.assertEqual(await self.ingest_data(), 2)
        self.assertEqual(len(await self.visible()), 2)
        self.assertEqual(len(self.db.audits), 1)

    async def test_repeat_identical_publication_performs_no_second_embedding_or_write(self):
        await self.ingest_data()
        self.embed.embed_documents = Mock(side_effect=AssertionError('No embedding on replay'))
        self.assertEqual(await self.ingest_data(), 2)
        self.assertEqual(len(self.db.publications), 1)
        self.vector.add_documents.assert_called_once()

    async def test_partial_vector_write_is_invisible_and_retry_reuses_ids(self):
        self.partial = True
        with self.assertRaises(self.queue.TaskRejected): await self.ingest_data()
        original = set(next(iter(self.db.publications.values()))['chunks'][i]['chunk_id'] for i in range(2))
        self.assertEqual(await self.visible(), [])
        self.partial = False
        await self.ingest_data()
        self.assertEqual(set(self.index), original)
        self.assertEqual(len(await self.visible()), 2)

    async def test_index_response_loss_remains_hidden_until_same_generation_retry(self):
        self.fail_index = True
        with self.assertRaises(RuntimeError): await self.ingest_data()
        ids = set(self.index)
        self.assertEqual(await self.visible(), [])
        self.fail_index = False
        await self.ingest_data()
        self.assertEqual(set(self.index), ids)

    async def test_ledger_failure_rolls_back_activation_and_audit(self):
        self.db.fail_on = 'INSERT INTO audit_logs'
        with self.assertRaises(RuntimeError): await self.ingest_data()
        self.assertEqual(await self.visible(), [])
        self.assertTrue(all(p['state'] == 'staging' for p in self.db.publications.values()))
        self.db.fail_on = None
        await self.ingest_data()
        self.assertEqual(len(await self.visible()), 2)

    async def test_prepare_commit_response_loss_prevents_vector_io(self):
        self.db.fail_after_commit = True
        with self.assertRaises(RuntimeError): await self.ingest_data()
        self.vector.add_documents.assert_not_called()
        self.db.fail_after_commit = False
        await self.ingest_data()
        self.assertEqual(len(self.db.publications), 1)

    async def test_activation_commit_response_loss_does_not_rewrite_current_version(self):
        def lose(chunks, partition):
            self.db.fail_after_commit = True
            return self.write_index(chunks, partition)
        self.vector.add_documents.side_effect = lose
        with self.assertRaises(RuntimeError): await self.ingest_data()
        self.db.fail_after_commit = False
        self.assertEqual(await self.ingest_data(), 2)
        self.vector.add_documents.assert_called_once()

    async def test_update_hides_old_generation_and_keeps_old_vectors(self):
        await self.ingest_data()
        old = set(self.index)
        await self.ingest_data(content='new')
        self.assertTrue(old.issubset(self.index))
        self.assertEqual([r.content for r in await self.visible()], ['new'])
        with self.assertRaises(self.queue.TaskRejected): await self.ingest_data()

    async def test_conflicting_update_while_indexing_is_rejected(self):
        self.fail_index = True
        with self.assertRaises(RuntimeError): await self.ingest_data()
        self.fail_index = False
        with self.assertRaises(self.queue.TaskRejected): await self.ingest_data(content='different')
        self.assertEqual(len(self.db.publications), 1)

    async def test_concurrent_same_plan_shares_generation_and_chunk_keys(self):
        results = await asyncio.gather(self.ingest_data(), self.ingest_data())
        self.assertEqual(results, [2, 2])
        self.assertEqual(len(self.db.publications), 1)
        self.assertEqual(len(self.index), 2)

    async def test_source_change_between_write_and_activation_fails_closed(self):
        def changed(chunks, partition):
            self.db.docs['import1']['title'] = 'changed outside publication'
            return self.write_index(chunks, partition)
        self.vector.add_documents.side_effect = changed
        with self.assertRaises(self.queue.TaskRejected): await self.ingest_data()
        self.assertEqual(await self.visible(), [])

    async def test_deactivation_blocks_late_writer_and_retains_vectors(self):
        def disabled(chunks, partition):
            self.db.docs['import1'].update(status='inactive', pending_publication=None)
            return self.write_index(chunks, partition)
        self.vector.add_documents.side_effect = disabled
        with self.assertRaises(self.queue.TaskRejected): await self.ingest_data()
        self.assertEqual(len(self.index), 2)
        self.assertEqual(await self.visible(), [])
        with self.assertRaises(self.queue.TaskRejected): await self.ingest_data()

    async def test_deactivation_route_is_idempotent_and_atomic(self):
        await self.ingest_data()
        route, _ = self.route('deactivate_knowledge_document')
        await route('import1', NS(user_id='admin1'), self.db)
        audits = len(self.db.audits)
        await route('import1', NS(user_id='admin1'), self.db)
        self.assertEqual(len(self.db.audits), audits)
        self.assertEqual(await self.visible(), [])

    async def test_direct_import_cannot_activate_rejected_or_draft_candidate(self):
        for state in ('draft', 'rejected', 'queued', 'inactive'):
            self.db.docs['doc1']['status'] = state
            with self.assertRaises(self.queue.TaskRejected): await self.ingest_data(document_id='doc1')
        self.vector.add_documents.assert_not_called()

    async def test_approval_job_publishes_exact_source_and_rechecks_reviewer(self):
        job = await self.publish()
        self.stack.enter_context(patch.dict(sys.modules, {'app.rag.ingest': module('app.rag.ingest',
            MilvusIngestService=lambda: self.ingestion)}))
        await self.knowledge.handle_knowledge_job(job['payload'])
        self.assertEqual(self.db.docs['doc1']['status'], 'active')
        self.assertEqual(self.resolve.await_count, 2)

    async def test_title_only_candidate_replay_keeps_same_publication(self):
        self.db.docs['doc1']['content'] = None
        job = await self.publish()
        self.stack.enter_context(patch.dict(sys.modules, {'app.rag.ingest': module('app.rag.ingest',
            MilvusIngestService=lambda: self.ingestion)}))
        await self.knowledge.handle_knowledge_job(job['payload'])
        await self.knowledge.handle_knowledge_job(job['payload'])
        self.assertEqual(len(self.db.publications), 1)
        self.vector.add_documents.assert_called_once()

    async def test_revoked_reviewer_at_activation_leaves_index_hidden(self):
        job = await self.publish()
        def revoked(chunks, partition):
            self.resolve.return_value = NS(role='manager')
            return self.write_index(chunks, partition)
        self.vector.add_documents.side_effect = revoked
        with self.assertRaises(self.queue.TaskRejected):
            await self.ingestion.ingest_text(document_id='doc1', title='Synthetic', content='Example',
                access_roles=['admin'], uploaded_by='synthetic-user', publication_approval=job['payload'])
        self.assertEqual(await self.visible(), [])

    async def test_explicit_dead_job_retry_retains_payload_and_original_job(self):
        job = await self.publish()
        self.db.jobs[job['task_id']]['state'] = 'dead'
        first = await self.knowledge.retry_knowledge_task(self.db, job['task_id'], 'admin2')
        second = await self.knowledge.retry_knowledge_task(self.db, job['task_id'], 'admin2')
        self.assertEqual(first['task_id'], second['task_id'])
        self.assertEqual(first['payload'], job['payload'])
        self.assertEqual(self.db.jobs[job['task_id']]['state'], 'dead')

    async def test_retry_rejects_running_or_changed_document(self):
        job = await self.publish()
        with self.assertRaises(self.queue.TaskRejected):
            await self.knowledge.retry_knowledge_task(self.db, job['task_id'], 'admin2')
        self.db.jobs[job['task_id']]['state'] = 'dead'
        self.db.docs['doc1']['content'] = 'changed'
        with self.assertRaises(self.queue.TaskRejected):
            await self.knowledge.retry_knowledge_task(self.db, job['task_id'], 'admin2')

    async def test_empty_acl_invalid_namespace_empty_chunks_and_oversize_fail_before_index(self):
        for changes in ({'access_roles': []}, {'access_roles': None}, {'dept_namespace': 'invalid'},
                        {'content': ''}, {'title': 'x' * 513}, {'source_url': 'x' * 1025}):
            with self.subTest(changes=changes), self.assertRaises(Exception):
                await self.ingest_data(**changes)
        self.vector.add_documents.assert_not_called()

    async def test_wrong_embedding_count_never_writes(self):
        self.embed.embed_documents = Mock(return_value=[])
        with self.assertRaises(self.queue.TaskRejected): await self.ingest_data()
        self.vector.add_documents.assert_not_called()
        self.assertEqual(await self.visible(), [])

    async def test_visibility_denies_without_request_snapshot_and_resets_after_scope(self):
        await self.ingest_data()
        with self.assertRaises(self.policy.RetrievalAccessError):
            self.visibility.visible_results(list(self.index.values()))
        self.assertEqual(len(await self.visible()), 2)
        with self.assertRaises(self.policy.RetrievalAccessError): self.visibility.visible_results([])

    async def test_visibility_drops_forged_content_metadata_duplicates_and_legacy_ids(self):
        await self.ingest_data()
        good = next(iter(self.index.values()))
        async with self.visibility.publication_scope(self.scope):
            bad = [NS(**{**vars(good), key: value}) for key, value in (
                ('content', 'unapproved'), ('document_id', 'foreign'), ('access_roles', ['salesperson']),
                ('dept_namespace', 'dept_finance'), ('chunk_id', 'legacy_chunk_0000'))]
            self.assertEqual(self.visibility.visible_results([*bad, good, good]), [good])

    async def test_visibility_current_metadata_drift_or_acl_denies(self):
        await self.ingest_data()
        self.db.docs['import1']['access_roles'] = ['salesperson']
        self.assertEqual(await self.visible(), [])

    async def test_visibility_database_outage_never_uses_cached_snapshot(self):
        await self.ingest_data()
        await self.visible()
        self.db.fail_on = 'p.snapshot AS published_snapshot'
        with self.assertRaisesRegex(self.policy.RetrievalAccessError, 'KNOWLEDGE_VISIBILITY_UNAVAILABLE'):
            await self.visible()

    async def test_visibility_snapshot_limit_fails_closed(self):
        self.db.execute = AsyncMock(return_value=result([{}] * 1001))
        with self.assertRaises(self.policy.RetrievalAccessError): await self.visible()

    async def test_rejection_is_conditional_and_blocks_later_approval(self):
        route, error = self.route('reject_knowledge_candidate')
        await route('doc1', NS(reject_reason='synthetic reason'), NS(user_id='admin1'), self.db)
        self.assertEqual(self.db.docs['doc1']['status'], 'rejected')
        with self.assertRaises(self.queue.TaskRejected): await self.publish()
        with self.assertRaises(error):
            await route('doc1', NS(reject_reason='again'), NS(user_id='admin1'), self.db)

    async def test_publication_cannot_substitute_approved_content(self):
        job = await self.publish()
        with self.assertRaises(self.queue.TaskRejected):
            await self.ingestion.ingest_text(document_id='doc1', title='Synthetic', content='substituted',
                access_roles=['admin'], uploaded_by='synthetic-user', publication_approval=job['payload'])
        self.vector.add_documents.assert_not_called()

    def retrieval_stack(self):
        self.policy.resolve_scope = lambda *args, **kwargs: self.scope
        self.collection = Mock()
        self.stack.enter_context(patch.dict(sys.modules, {
            'numpy': module('numpy', ndarray=object),
            'app.core.milvus_client': module('app.core.milvus_client', get_collection=lambda: self.collection),
            'app.rag.reranker': module('app.rag.reranker', Reranker=object, get_reranker=Mock()),
            'app.rag.confidence': module('app.rag.confidence',
                ConfidenceDecider=NS(detect_scene=lambda query: 'general')),
            'app.observability.tracing': module('app.observability.tracing',
                traced_span=lambda *a, **kw: nullcontext(), record_span_attributes=Mock(),
                record_span_event=Mock()),
            'app.rag.model_profile': module('app.rag.model_profile', uses_remote_profile=lambda s: False),
            'app.rag.remote_models': module('app.rag.remote_models', RemoteModelError=RuntimeError),
        }))
        vs = load('app.rag.vector_store', 'app/rag/vector_store.py')
        retriever = load('c15_retriever', 'app/rag/retriever.py')
        degradation = load('c15_degradation', 'app/rag/degradation.py')
        self.ranker = Mock(rerank=Mock(side_effect=lambda query, rows, top_n: rows))
        self.embed.embed_query = Mock(return_value=[1.0, 0.0])
        self.primary_store = Mock(search=lambda **kwargs: [NS(**vars(c), score=1.0)
                                                         for c in self.index.values()])
        self.primary = retriever.EnterpriseRAGRetriever(self.primary_store, self.ranker, self.embed)
        return vs, degradation.DegradationChain(self.primary)

    async def test_actual_chain_removes_stale_chunks_before_reranker(self):
        await self.ingest_data()
        await self.ingest_data(content='current')
        _, chain = self.retrieval_stack()
        answer = await chain.run('current', 'admin')
        self.assertEqual([r.content for r in answer.results], ['current'])
        self.assertEqual([r.content for r in self.ranker.rerank.call_args.args[1]], ['current'])

    async def test_actual_chain_database_failure_stops_before_models(self):
        _, chain = self.retrieval_stack()
        self.db.fail_on = 'p.snapshot AS published_snapshot'
        with self.assertRaises(self.policy.RetrievalAccessError): await chain.run('query', 'admin')
        self.embed.embed_query.assert_not_called()
        self.ranker.rerank.assert_not_called()

    async def test_actual_keyword_path_filters_old_generation(self):
        await self.ingest_data()
        await self.ingest_data(content='current')
        _, chain = self.retrieval_stack()
        self.primary_store.search = Mock(return_value=[])
        self.collection.query.return_value = [vars(c) for c in self.index.values()]
        answer = await chain.run('current', 'admin')
        self.assertEqual([r.content for r in answer.results], ['current'])

    async def test_empty_vector_and_keyword_scan_fall_back_to_published_pg_chunks(self):
        await self.ingest_data(content='current')
        _, chain = self.retrieval_stack()
        self.primary_store.search = Mock(return_value=[])
        self.collection.query.return_value = []
        answer = await chain.run('current', 'admin')
        self.assertEqual([r.content for r in answer.results], ['current'])
        sql = ' '.join(q for q, p in self.db.queries)
        self.assertIn('p.publication_id = d.active_publication', sql)
        self.assertIn('jsonb_to_recordset(p.chunks)', sql)

    async def test_actual_milvus_upsert_checks_receipt_and_never_falls_back_partition(self):
        await self.ingest_data()
        vs, _ = self.retrieval_stack()
        chunks = list(self.index.values())
        store = vs.MilvusVectorStore()
        self.collection.has_partition.return_value = True
        self.collection.upsert.return_value = NS(upsert_count=len(chunks), primary_keys=list(self.index))
        self.assertEqual(store.add_documents(chunks), len(chunks))
        self.collection.insert.assert_not_called()
        self.assertEqual(self.collection.upsert.call_args.kwargs['timeout'], 30)
        self.collection.upsert.return_value = NS(upsert_count=1, primary_keys=list(self.index)[:1])
        with self.assertRaises(ValueError): store.add_documents(chunks)
        self.collection.has_partition.return_value = False
        self.collection.upsert.reset_mock()
        with self.assertRaises(ValueError): store.add_documents(chunks)
        self.collection.upsert.assert_not_called()

    async def test_visibility_contexts_do_not_leak_between_concurrent_requests(self):
        await self.ingest_data()
        entered = asyncio.Event()
        release = asyncio.Event()
        async def admitted():
            async with self.visibility.publication_scope(self.scope):
                entered.set()
                await release.wait()
                return len(self.visibility.visible_results(list(self.index.values())))
        first = asyncio.create_task(admitted())
        await entered.wait()
        self.db.docs['import1']['status'] = 'inactive'
        self.assertEqual(await self.visible(), [])
        release.set()
        self.assertEqual(await first, 2)  # Snapshot admission, not retroactive revocation.

    async def test_cancellation_retains_invisible_generation_for_reconciliation(self):
        self.embed.embed_documents = Mock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError): await self.ingest_data()
        self.assertEqual(self.db.docs['import1']['status'], 'indexing')
        self.assertEqual(await self.visible(), [])

    async def test_new_routes_are_admin_only_and_status_has_no_content(self):
        tree = ast.parse((ROOT / 'app/api/admin.py').read_text())
        for fn in tree.body:
            if isinstance(fn, ast.AsyncFunctionDef) and fn.name in {
                    'retry_knowledge_publication', 'deactivate_knowledge_document', 'list_knowledge_publications'}:
                self.assertIn('require_roles(AgentRole.ADMIN)', ast.unparse(fn.args))
                if fn.name == 'list_knowledge_publications':
                    self.assertNotIn('p.snapshot', ast.unparse(fn))
                    self.assertNotIn('p.chunks,', ast.unparse(fn))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(PublicationTests(name) for name in PublicationTests.__dict__
                              if name.startswith('test_'))


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
