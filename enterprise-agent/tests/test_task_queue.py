"""C14 actual-source tests with SQL orchestration doubles, not database acceptance."""
from __future__ import annotations

import asyncio
import ast
from contextlib import ExitStack, asynccontextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]


def module(name, **attrs):
    value = ModuleType(name)
    value.__dict__.update(attrs)
    return value


def load(name, path):
    value = module(name)
    value.__file__ = str(ROOT / path)
    sys.modules[name] = value
    exec(compile((ROOT / path).read_bytes(), value.__file__, 'exec'), value.__dict__)
    return value


class Database:
    """Model SQL effects explicitly. Does not execute/validate PostgreSQL SQL or locks."""
    def __init__(self):
        self.jobs = {}
        self.docs = {'doc1': dict(document_id='doc1', title='Synthetic', content='Example',
            access_roles=['admin'], uploaded_by='synthetic-user', status='draft',
            doc_type='faq', dept_namespace='shared_company')}
        self.clock = 100
        self.commits = 0
        self.rollbacks = 0
        self.fail_sql = None
        self.fail_commit = False
        self.queries = []
        self.heartbeats = []

    @asynccontextmanager
    async def session(self):
        yield self

    async def commit(self):
        self.commits += 1
        if self.fail_commit:
            # Simulate commit succeeded but the acknowledgement was lost.
            raise RuntimeError('SYNTHETIC_SECRET')

    async def rollback(self):
        self.rollbacks += 1

    async def execute(self, sql, p):
        self.queries.append((sql, deepcopy(p)))
        if self.fail_sql and self.fail_sql in sql:
            raise RuntimeError('SYNTHETIC_SECRET')
        rows = []
        if 'INSERT INTO task_jobs' in sql:
            if not any(j['scope_key'] == p['scope'] for j in self.jobs.values()):
                j = dict(task_id=p['tid'], queue_name=p['queue'], scope_key=p['scope'],
                    payload=json.loads(p['payload']), payload_hash=p['hash'], state='pending',
                    attempts=0, owner_token=None, lease_until=None, available_at=self.clock,
                    error_code=None, created_at=self.clock, updated_at=self.clock)
                self.jobs[j['task_id']] = j
        elif 'SELECT * FROM task_jobs WHERE scope_key' in sql:
            rows = [j for j in self.jobs.values() if j['scope_key'] == p['scope']]
        elif 'WITH expired AS' in sql:
            assert 'FOR UPDATE SKIP LOCKED' in sql and "j.state = 'running'" in sql
            for j in self.jobs.values():
                if j['queue_name'] == p['queue'] and j['state'] in ('leased','running') and j['lease_until'] <= self.clock:
                    error = 'TASK_OUTCOME_UNKNOWN' if j['state']=='running' else 'TASK_LEASE_EXHAUSTED'
                    dead = j['state']=='running' or j['attempts'] >= p['max']
                    j.update(state='dead' if dead else 'pending', error_code=error if dead else None,
                        owner_token=None, lease_until=None, available_at=self.clock+min(300,5*2**(j['attempts']-1)))
        elif 'WITH candidate AS' in sql:
            assert 'FOR UPDATE SKIP LOCKED' in sql and 'attempts < :max' in sql
            candidates = [j for j in self.jobs.values() if j['queue_name']==p['queue'] and j['state']=='pending'
                and j['available_at']<=self.clock and j['attempts']<p['max']]
            if candidates:
                j=candidates[0]
                j.update(state='leased', attempts=j['attempts']+1, owner_token=p['owner'], lease_until=self.clock+p['lease'])
                rows=[j]
        elif 'UPDATE task_jobs SET' in sql:
            assert 'owner_token = :owner' in sql and 'lease_until > clock_timestamp()' in sql
            j=self.jobs[p['tid']]
            source=p.get('source','running')
            if j['owner_token']==p['owner'] and j['state']==source and j['lease_until']>self.clock:
                if 'target' in p:
                    j.update(state=p['target'],error_code=p['error'])
                    if p['target']!='running':j['lease_until']=None
                else:j['lease_until']=self.clock+p['lease']
                rows=[{'task_id':p['tid']}]
        elif 'INSERT INTO task_consumers' in sql:
            self.heartbeats.append(deepcopy(p))
        elif 'FROM documents WHERE document_id' in sql:
            if p['did'] in self.docs:rows=[self.docs[p['did']]]
        elif "UPDATE documents SET status = 'queued'" in sql:
            self.docs[p['did']].update(status='queued',reviewed_by=p['reviewer'])
        elif 'INSERT INTO audit_logs' in sql:
            assert 'knowledge_publication_queued' in sql
        elif 'FROM task_jobs WHERE task_id' in sql:
            rows=[j for j in self.jobs.values() if j['task_id']==p['tid']]
        elif 'FROM task_jobs' in sql and 'ORDER BY' in sql:
            rows=[j for j in self.jobs.values() if p['state'] is None or j['state']==p['state']]
        elif 'FROM task_consumers' in sql:
            rows=[]
        else:
            raise AssertionError(sql)
        rows=deepcopy(rows)
        return NS(returns_rows=True,mappings=lambda:NS(first=lambda:rows[0] if rows else None,all=lambda:rows))


class QueueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.db=Database()
        self.settings=NS(app_env='dev',vector_store_provider='milvus')
        self.resolve=AsyncMock(return_value=NS(role='admin'))
        self.ingest=AsyncMock(return_value=2)
        self.service=Mock(return_value=NS(ingest_text=self.ingest))
        self.init_db=AsyncMock();self.close_db=AsyncMock()
        self.init_milvus=AsyncMock();self.close_milvus=AsyncMock()
        self.init_tools=Mock();self.init_audit=Mock();self.verify=AsyncMock()
        self.logger=Mock()
        self.stack.enter_context(patch.dict(sys.modules,{
            'app':module('app'),'app.core':module('app.core'),'app.security':module('app.security'),
            'app.rag':module('app.rag'),'app.tools':module('app.tools'),
            'sqlalchemy':module('sqlalchemy',text=lambda s:s),
            'loguru':module('loguru',logger=self.logger),
            'app.config':module('app.config',get_settings=lambda:self.settings,validate_production_settings=lambda s:[]),
            'app.core.database':module('app.core.database',get_session_factory=lambda:self.db.session,
                init_db=self.init_db,close_db=self.close_db),
            'app.security.rbac':module('app.security.rbac',AgentRole=NS(ADMIN='admin'),resolve_active_user=self.resolve),
            'app.rag.ingest':module('app.rag.ingest',MilvusIngestService=self.service),
            'app.rag.model_profile':module('app.rag.model_profile',verify_model_startup=self.verify),
            'app.observability.audit':module('app.observability.audit',init_audit_logger=self.init_audit),
            'app.tools.base':module('app.tools.base',init_all_tools=self.init_tools),
            'app.core.milvus_client':module('app.core.milvus_client',init_milvus=self.init_milvus,close_milvus=self.close_milvus),
            'app.core.approval_timeout':module('app.core.approval_timeout',scan_expired_approvals=AsyncMock()),
        }))
        redaction=load('app.security.redaction','app/security/redaction.py')
        redaction.install_log_redaction=Mock()
        self.ops=load('app.core.tool_operations','app/core/tool_operations.py')
        self.queue=load('app.core.task_queue','app/core/task_queue.py')
        self.knowledge=load('app.core.knowledge_jobs','app/core/knowledge_jobs.py')
        self.worker=load('app.worker','app/worker.py')
        self.store=self.queue.TaskStore(self.db.session)

    async def enqueue(self):
        return await self.queue.enqueue_task(self.db,'tasks:doc_ingest','test:1',{'document_id':'doc1'})

    async def claim(self):
        await self.enqueue()
        return await self.store.claim('tasks:doc_ingest')

    async def publish(self,**changes):
        options=dict(document_id='doc1',reviewer='admin1',doc_type='faq',dept_namespace='shared_company')
        options.update(changes)
        return await self.knowledge.queue_knowledge_approval(self.db,**options)

    def route(self,name):
        tree=ast.parse((ROOT/'app/api/admin.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
        fn.decorator_list=[]
        tree=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),fn],type_ignores=[])
        class HTTPError(Exception):
            def __init__(self,status_code,detail):self.status_code=status_code;self.detail=detail
        scope=dict(uuid=uuid,text=lambda s:s,Query=lambda **kw:kw.get('default'),Depends=lambda f:None,
            require_roles=lambda *a:None,AgentRole=NS(ADMIN='admin'),get_db=lambda:None,
            HTTPException=HTTPError,_envelope=lambda data,**kw:dict(data=data,**kw))
        exec(compile(ast.fix_missing_locations(tree),'admin.py','exec'),scope)
        return scope[name],HTTPError

    async def test_enqueue_same_scope_retains_id_and_has_no_implicit_commit(self):
        first=await self.enqueue();second=await self.enqueue()
        self.assertEqual(first['task_id'],second['task_id']);self.assertEqual(self.db.commits,0)

    async def test_changed_replay_conflicts(self):
        await self.enqueue()
        with self.assertRaises(self.queue.TaskRejected):
            await self.queue.enqueue_task(self.db,'tasks:doc_ingest','test:1',{'document_id':'doc2'})

    async def test_invalid_queue_scope_or_payload_denied(self):
        for q,s,p in [('unknown','x',{}),('tasks:doc_ingest','',{}),('tasks:doc_ingest','x',[])]:
            with self.assertRaises(self.queue.TaskRejected):await self.queue.enqueue_task(self.db,q,s,p)
        self.assertFalse(self.db.jobs)

    async def test_credentials_never_persist(self):
        with self.assertRaises(Exception):
            await self.queue.enqueue_task(self.db,'tasks:doc_ingest','x',{'access_token':'synthetic-secret'})
        self.assertFalse(self.db.jobs)

    async def test_two_claimers_only_one_owner(self):
        await self.enqueue()
        a,b=await asyncio.gather(self.store.claim('tasks:doc_ingest'),self.store.claim('tasks:doc_ingest'))
        self.assertEqual(sum(x is not None for x in (a,b)),1)

    async def test_claim_before_dispatch_expires_to_delayed_same_job(self):
        job=await self.claim();self.db.clock+=121
        await self.store.recover('tasks:doc_ingest')
        self.assertIsNone(await self.store.claim('tasks:doc_ingest'))
        self.db.clock+=5;again=await self.store.claim('tasks:doc_ingest')
        self.assertEqual(again['task_id'],job['task_id'])
        self.assertNotEqual(again['owner_token'],job['owner_token'])
        self.assertEqual(again['attempts'],2)

    async def test_exhausted_claims_are_retained_dead(self):
        job=await self.claim();self.db.jobs[job['task_id']]['attempts']=4;self.db.clock+=121
        await self.store.recover('tasks:doc_ingest')
        self.assertEqual(self.db.jobs[job['task_id']]['error_code'],'TASK_LEASE_EXHAUSTED')
        self.assertIsNone(await self.store.claim('tasks:doc_ingest'))

    async def test_running_crash_is_unknown_never_replayed(self):
        job=await self.claim();await self.store.transition(job,'running');self.db.clock+=121
        await self.store.recover('tasks:doc_ingest')
        self.assertEqual(self.db.jobs[job['task_id']]['error_code'],'TASK_OUTCOME_UNKNOWN')
        self.assertIsNone(await self.store.claim('tasks:doc_ingest'))

    async def test_stale_owner_and_expired_owner_cannot_dispatch_or_ack(self):
        job=await self.claim();wrong={**job,'owner_token':str(uuid.uuid4())}
        self.assertFalse(await self.store.transition(wrong,'running'))
        self.db.clock+=121
        self.assertFalse(await self.store.transition(job,'running'))
        self.assertFalse(await self.store.renew(job))

    async def test_old_owner_cannot_finish_reclaimed_job(self):
        old=await self.claim();self.db.clock+=121;await self.store.recover('tasks:doc_ingest')
        self.db.clock+=5;new=await self.store.claim('tasks:doc_ingest')
        await self.store.transition(new,'running')
        self.assertFalse(await self.store.transition(old,'done'))
        self.assertTrue(await self.store.transition(new,'done'))

    async def test_success_finishes_retained_row(self):
        job=await self.claim();handler=AsyncMock()
        await self.queue.execute_claim(self.store,job,handler,'worker')
        handler.assert_awaited_once_with(job['payload'])
        self.assertEqual(self.db.jobs[job['task_id']]['state'],'done')
        self.assertIsNone(await self.store.claim('tasks:doc_ingest'))

    async def test_handler_failure_is_dead_once_and_diagnostics_safe(self):
        job=await self.claim();handler=AsyncMock(side_effect=RuntimeError('SYNTHETIC_SECRET'))
        await self.queue.execute_claim(self.store,job,handler,'worker')
        self.assertEqual(self.db.jobs[job['task_id']]['error_code'],'TASK_OUTCOME_UNKNOWN')
        handler.assert_awaited_once();self.assertNotIn('SYNTHETIC_SECRET',json.dumps(self.db.jobs))

    async def test_fixed_terminal_reason_retained(self):
        job=await self.claim()
        await self.queue.execute_claim(self.store,job,AsyncMock(side_effect=self.queue.TaskRejected('C13_REQUIRED')),'worker')
        self.assertEqual(self.db.jobs[job['task_id']]['error_code'],'C13_REQUIRED')

    async def test_corrupt_payload_never_reaches_handler(self):
        job=await self.claim();job['payload']['document_id']='changed';handler=AsyncMock()
        await self.queue.execute_claim(self.store,job,handler,'worker')
        handler.assert_not_awaited();self.assertEqual(self.db.jobs[job['task_id']]['state'],'dead')

    async def test_dispatch_commit_response_loss_never_invokes_handler(self):
        job=await self.claim();self.db.fail_commit=True;handler=AsyncMock()
        with self.assertRaises(self.queue.QueueUnavailable):
            await self.queue.execute_claim(self.store,job,handler,'worker')
        handler.assert_not_awaited();self.assertEqual(self.db.jobs[job['task_id']]['state'],'running')

    async def test_completion_commit_loss_never_replays(self):
        job=await self.claim()
        async def handler(payload):self.db.fail_commit=True
        with self.assertRaises(self.queue.QueueUnavailable):
            await self.queue.execute_claim(self.store,job,handler,'worker')
        self.db.fail_commit=False
        self.assertEqual(self.db.jobs[job['task_id']]['state'],'done')
        self.assertIsNone(await self.store.claim('tasks:doc_ingest'))

    async def test_shutdown_cancels_handler_leaves_running_for_reconciliation(self):
        job=await self.claim();started=asyncio.Event();cancelled=asyncio.Event()
        async def handler(payload):
            started.set()
            try:await asyncio.Event().wait()
            finally:cancelled.set()
        task=asyncio.create_task(self.queue.execute_claim(self.store,job,handler,'worker'))
        await started.wait();task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        self.assertTrue(cancelled.is_set());self.assertEqual(self.db.jobs[job['task_id']]['state'],'running')

    async def test_lease_loss_cancels_execution_without_success(self):
        job=await self.claim();handler=AsyncMock(side_effect=lambda p:None)
        async def block(payload):await asyncio.Event().wait()
        with patch.object(self.queue,'HEARTBEAT_SECONDS',0.001),patch.object(self.store,'renew',new=AsyncMock(return_value=False)):
            with self.assertRaises(self.queue.QueueUnavailable):
                await self.queue.execute_claim(self.store,job,block,'worker')
        self.assertEqual(self.db.jobs[job['task_id']]['state'],'running')

    async def test_reconnect_backoff_is_bounded_and_consumer_resumes(self):
        store=NS(recover=AsyncMock(side_effect=[self.queue.QueueUnavailable('x')]*7+[None]),
            claim=AsyncMock(return_value=None),heartbeat=AsyncMock())
        delays=[]
        async def sleep(delay):
            delays.append(delay)
            if len(delays)==8:raise asyncio.CancelledError()
        with patch.object(self.queue.asyncio,'sleep',new=sleep):
            with self.assertRaises(asyncio.CancelledError):await self.queue.consume_tasks('tasks:doc_ingest',AsyncMock(),store=store)
        self.assertEqual(delays,[1,2,4,8,16,30,30,1]);store.heartbeat.assert_awaited_once()

    async def test_store_errors_are_safe(self):
        self.db.fail_sql='WITH candidate'
        with self.assertRaisesRegex(self.queue.QueueUnavailable,'^TASK_STORE_UNAVAILABLE$'):
            await self.store.claim('tasks:doc_ingest')

    async def test_producer_queues_document_and_reuses_job(self):
        first=await self.publish();second=await self.publish()
        self.assertEqual(first['task_id'],second['task_id']);self.assertEqual(self.db.docs['doc1']['status'],'queued')
        self.assertEqual(self.db.commits,0);self.assertNotIn('content',first['payload'])
        audits=[params for sql,params in self.db.queries if 'INSERT INTO audit_logs' in sql]
        self.assertEqual(len(audits),1)
        self.assertEqual(json.loads(audits[0]['payload'])['phase'],'queued')
        with self.assertRaises(self.queue.TaskRejected):await self.publish(doc_type='policy')

    async def test_producer_rejects_non_draft_and_invalid_acl(self):
        for state in ('active','rejected','queued'):
            self.db.docs['doc1']['status']=state
            with self.assertRaises(self.queue.TaskRejected):await self.publish()
        self.db.docs['doc1'].update(status='draft',access_roles=[])
        with self.assertRaises(self.queue.TaskRejected):await self.publish()
        self.assertFalse(self.db.jobs)

    async def test_enqueue_failure_prevents_document_transition(self):
        self.db.fail_sql='INSERT INTO task_jobs'
        with self.assertRaises(RuntimeError):await self.publish()
        self.assertEqual(self.db.docs['doc1']['status'],'draft')

    async def test_worker_ingests_frozen_text_with_explicit_acl(self):
        job=await self.publish();await self.worker.handle_doc_ingest_task(job['payload'])
        self.ingest.assert_awaited_once()
        self.assertEqual(self.ingest.call_args.kwargs['access_roles'],['admin'])
        self.resolve.assert_awaited_once()

    async def test_changed_document_or_revoked_reviewer_never_ingests(self):
        job=await self.publish();self.db.docs['doc1']['content']='changed'
        with self.assertRaises(self.queue.TaskRejected):await self.worker.handle_doc_ingest_task(job['payload'])
        self.db.docs['doc1']['content']='Example';self.resolve.return_value=NS(role='manager')
        with self.assertRaises(self.queue.TaskRejected):await self.worker.handle_doc_ingest_task(job['payload'])
        self.ingest.assert_not_awaited()

    async def test_empty_ingestion_is_not_success(self):
        job=await self.publish();self.ingest.return_value=0
        with self.assertRaisesRegex(self.queue.TaskRejected,'TASK_EMPTY_RESULT'):
            await self.worker.handle_doc_ingest_task(job['payload'])

    async def test_file_path_and_legacy_saga_fail_closed(self):
        with self.assertRaises(self.queue.TaskRejected):await self.worker.handle_doc_ingest_task({'file_path':'/private/example'})
        with self.assertRaisesRegex(self.queue.TaskRejected,'C13_REQUIRED'):
            await self.worker.handle_saga_retry_task({'saga_id':'example'})
        self.service.assert_not_called()

    async def test_route_commits_queued_job_not_active_success(self):
        route,_=self.route('approve_knowledge_candidate')
        result=await route('doc1',NS(doc_type='faq',dept_namespace='shared_company'),NS(user_id='admin1'),self.db)
        self.assertEqual(result['data']['status'],'pending');self.assertEqual(self.db.commits,1)
        self.ingest.assert_not_awaited()

    async def test_route_commit_failure_reports_unavailable_and_rolls_back(self):
        route,error=self.route('approve_knowledge_candidate');self.db.fail_commit=True
        with self.assertRaises(error) as caught:
            await route('doc1',NS(doc_type='faq',dept_namespace='shared_company'),NS(user_id='admin1'),self.db)
        self.assertEqual(caught.exception.status_code,503);self.assertEqual(self.db.rollbacks,1)
        self.assertEqual(caught.exception.detail,'TASK_STORE_UNAVAILABLE')

    async def test_route_replay_after_lost_commit_response_returns_original(self):
        route,error=self.route('approve_knowledge_candidate');self.db.fail_commit=True
        args=('doc1',NS(doc_type='faq',dept_namespace='shared_company'),NS(user_id='admin1'),self.db)
        with self.assertRaises(error):await route(*args)
        tid=next(iter(self.db.jobs));self.db.fail_commit=False
        result=await route(*args);self.assertEqual(result['data']['task_id'],tid);self.assertEqual(len(self.db.jobs),1)

    async def test_status_projection_omits_payload_and_owner(self):
        job=await self.enqueue();route,_=self.route('get_task_job')
        response=await route(uuid.UUID(job['task_id']),NS(),self.db)
        self.assertNotIn('payload',response['data']);self.assertNotIn('owner_token',response['data'])
        self.assertEqual(response['data']['state'],'pending')

    async def test_missing_job_returns_not_found(self):
        route,error=self.route('get_task_job')
        with self.assertRaises(error) as caught:await route(uuid.uuid4(),NS(),self.db)
        self.assertEqual(caught.exception.status_code,404)

    async def test_job_routes_require_admin_and_approval_is_202(self):
        tree=ast.parse((ROOT/'app/api/admin.py').read_text())
        names={'approve_knowledge_candidate','list_task_jobs','get_task_job','list_task_consumers'}
        for fn in tree.body:
            if isinstance(fn,ast.AsyncFunctionDef) and fn.name in names:
                self.assertIn('require_roles(AgentRole.ADMIN)',ast.unparse(fn.args))
                if fn.name=='approve_knowledge_candidate':self.assertIn('status_code=202',ast.unparse(fn.decorator_list[0]))

    async def test_worker_initializes_before_consumers_and_supervises_exit(self):
        events=[]
        self.init_tools.side_effect=lambda:events.append('tools')
        self.init_milvus.side_effect=lambda:events.append('milvus')
        async def consumer(*args,**kwargs):events.append('consumer')
        with patch.object(self.worker,'consume_tasks',new=consumer):
            with self.assertRaisesRegex(RuntimeError,'WORKER_FAILED'):await self.worker.main()
        self.assertEqual(events[:2],['tools','milvus']);self.init_audit.assert_called_once()
        self.close_milvus.assert_awaited_once();self.close_db.assert_awaited_once()

    async def test_worker_partial_startup_failure_never_claims(self):
        self.init_milvus.side_effect=RuntimeError('SYNTHETIC_SECRET')
        with patch.object(self.worker,'consume_tasks',new=AsyncMock()) as consume:
            with self.assertRaisesRegex(RuntimeError,'^WORKER_FAILED$'):await self.worker.main()
            consume.assert_not_awaited()
        self.close_milvus.assert_awaited_once();self.close_db.assert_awaited_once()

    async def test_worker_tool_init_failure_closes_database(self):
        self.init_tools.side_effect=RuntimeError('synthetic')
        with self.assertRaises(RuntimeError):await self.worker.main()
        self.close_db.assert_awaited_once();self.init_milvus.assert_not_awaited()

    async def test_worker_model_failure_closes_partial_resources(self):
        self.verify.side_effect=RuntimeError('synthetic')
        with self.assertRaises(RuntimeError):await self.worker.main()
        self.close_db.assert_awaited_once();self.init_db.assert_not_awaited()

    async def test_worker_memory_is_dev_only(self):
        self.settings.vector_store_provider='memory';self.settings.app_env='prod'
        with patch.object(self.worker,'consume_tasks',new=AsyncMock()) as consume:
            with self.assertRaises(RuntimeError):await self.worker.main()
            consume.assert_not_awaited()

    async def test_worker_cancellation_closes_children_and_resources(self):
        started=asyncio.Event();stopped=[]
        async def consumer(*args,**kwargs):
            started.set()
            try:await asyncio.Event().wait()
            finally:stopped.append(True)
        with patch.object(self.worker,'consume_tasks',new=consumer):
            task=asyncio.create_task(self.worker.main());await started.wait();task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        self.assertEqual(len(stopped),2);self.close_db.assert_awaited_once()

    async def test_sigterm_wrapper_registers_cancellation_and_releases_handler(self):
        loop=Mock();task=Mock()
        with patch.object(self.worker.asyncio,'get_running_loop',return_value=loop), \
             patch.object(self.worker.asyncio,'current_task',return_value=task), \
             patch.object(self.worker,'main',new=AsyncMock(side_effect=asyncio.CancelledError())):
            with self.assertRaises(asyncio.CancelledError):await self.worker.serve()
        loop.add_signal_handler.assert_called_once_with(self.worker.signal.SIGTERM,task.cancel)
        loop.remove_signal_handler.assert_called_once_with(self.worker.signal.SIGTERM)

    async def test_dead_job_listing_is_queryable_and_redacted(self):
        job=await self.claim()
        await self.queue.execute_claim(self.store,job,AsyncMock(side_effect=RuntimeError('synthetic')),'worker')
        route,_=self.route('list_task_jobs')
        response=await route('dead',20,0,NS(),self.db)
        self.assertEqual(len(response['data']['items']),1)
        self.assertEqual(response['data']['items'][0]['error_code'],'TASK_OUTCOME_UNKNOWN')
        self.assertNotIn('payload',response['data']['items'][0])

    async def test_claim_ack_loss_keeps_uninvoked_job_recoverable(self):
        await self.enqueue();self.db.fail_commit=True
        with self.assertRaises(self.queue.QueueUnavailable):await self.store.claim('tasks:doc_ingest')
        job=next(iter(self.db.jobs.values()))
        self.assertEqual(job['state'],'leased')
        self.db.fail_commit=False;self.db.clock+=121
        await self.store.recover('tasks:doc_ingest')
        self.assertEqual(job['state'],'pending')

    async def test_worker_never_flushes_deleting_audit_cache(self):
        source=(ROOT/'app/worker.py').read_text()
        self.assertNotIn('flush_local_cache(',source)


if __name__ == '__main__':
    sys.dont_write_bytecode=True
    def guard(event,args):
        if event=='socket.__new__' and args[1]==1:return
        if event.startswith(('socket.','subprocess.','ctypes.')) or event in {
            'os.remove','os.rmdir','os.rename','os.system','os.mkdir','os.chmod','os.chown',
            'os.truncate','os.utime','os.link','os.symlink','os.exec','os.posix_spawn',
            'os.fork','os.forkpty','os.putenv','os.unsetenv'}:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event=='open' and (isinstance(args[1],str) and any(c in args[1] for c in 'wax+')
                             or isinstance(args[2],int) and args[2]&3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
