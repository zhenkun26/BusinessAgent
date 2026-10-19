"""C21 actual-source/memory verification. Never starts application, listeners or disk stores."""
from __future__ import annotations

import ast
import asyncio
from contextlib import ExitStack, asynccontextmanager
from datetime import datetime, timezone
import hashlib
import http.server
import json
import io
from pathlib import Path
import sqlite3
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]


def module(name, **attrs):
    m = ModuleType(name); m.__dict__.update(attrs); return m


def load(name, path):
    m = module(name); m.__file__ = str(ROOT/path); sys.modules[name] = m
    exec(compile((ROOT/path).read_bytes(), str(ROOT/path), 'exec'), m.__dict__)
    return m


class Metric:
    def __init__(self, *args, **kwargs):
        self.values=[]; self.label={}
    def labels(self, **kwargs):
        self.label=kwargs; return self
    def observe(self, value): self.values.append((dict(self.label),value))
    def set(self, value): self.observe(value)
    def inc(self): self.observe(1)


class Base:
    def prepare(self):
        self.stack=ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(sys.modules, {
            'loguru':module('loguru',logger=Mock()),
            'sqlalchemy':module('sqlalchemy',text=lambda s:s),
            'prometheus_client':module('prometheus_client',Counter=Metric,Gauge=Metric,Histogram=Metric,
                                      CONTENT_TYPE_LATEST='text/plain',generate_latest=lambda:b'fixture'),
            'httpx':module('httpx'),
        }))
        self.correlation=load('app.observability.correlation','app/observability/correlation.py')
        self.retained=load('app.observability.retained','app/observability/retained.py')
        self.db=sqlite3.connect(':memory:',isolation_level=None)
        self.addCleanup(self.db.close)
        self.store=self.retained.RetainedStore('unused',connection=self.db)
        self.metrics=load('app.observability.metrics','app/observability/metrics.py')
        self.monitor=load('app.observability.monitor','app/observability/monitor.py')
        self.ready=load('app.observability.readiness','app/observability/readiness.py')


class StoreTests(Base, unittest.TestCase):
    def setUp(self): self.prepare()
    def test_append_duplicate_is_one_retained_row(self):
        for _ in range(3): self.store.append('audit','id',{'v':1})
        self.assertEqual(len(self.store.pending('audit')),1)
    def test_conflicting_identity_never_overwrites(self):
        self.store.append('audit','id',{'v':1})
        with self.assertRaises(ValueError):self.store.append('audit','id',{'v':2})
        self.assertEqual(self.store.pending('audit')[0]['body'],{'v':1})
    def test_acknowledgement_retains_body_and_identity(self):
        self.store.append('audit','id',{'v':1}); self.store.acknowledge('id')
        self.assertEqual(self.store.pending('audit'),[])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM retained_events').fetchone()[0],1)
    def test_acknowledgement_is_idempotent(self):
        self.store.append('audit','id',{});self.store.acknowledge('id')
        first=self.db.execute('SELECT acknowledged FROM retained_events').fetchone()[0]
        self.store.acknowledge('id');self.assertEqual(first,self.db.execute('SELECT acknowledged FROM retained_events').fetchone()[0])
    def test_deferred_poison_does_not_starve_other_events(self):
        self.store.append('audit','bad',{});self.store.append('audit','good',{})
        self.store.defer('bad');self.assertEqual([v['event_id'] for v in self.store.pending('audit')],['good'])
    def test_pending_batch_is_bounded(self):
        for i in range(110):self.store.append('audit',str(i),{})
        self.assertEqual(len(self.store.pending('audit',10000)),100)
    def test_pending_age_includes_deferred_events(self):
        self.store.append('audit','id',{});self.store.defer('id')
        self.assertEqual(self.store.stats()['pending'],1)
    def test_oversized_record_rejected(self):
        with self.assertRaises(ValueError):self.store.append('audit','id',{'v':'x'*262145})
    def test_unknown_channel_rejected(self):
        with self.assertRaises(ValueError):self.store.append('unknown','id',{})
    def test_initial_healthy_has_no_resolution_event(self):
        self.store.observe('api',False);self.assertEqual(self.store.pending('alert'),[])
    def test_repeated_failure_has_one_transition(self):
        self.store.observe('api',True);self.store.observe('api',True)
        self.assertEqual(len(self.store.pending('alert')),1)
    def test_fault_and_recovery_are_ordered_retained_events(self):
        self.store.observe('api',True);self.store.observe('api',False)
        self.assertEqual([v['body']['state'] for v in self.store.pending('alert')],['firing','resolved'])
    def test_reopen_store_preserves_pending_and_conditions(self):
        self.store.observe('api',True)
        other=self.retained.RetainedStore('unused',connection=self.db)
        other.observe('api',True);self.assertEqual(len(other.pending('alert')),1)
    def test_schema_identity_and_artifact_checksums(self):
        d=json.loads((ROOT/'deploy/schema_manifest.json').read_text())
        self.assertEqual(d['migrations'][-1]['version'],7)
        for m in d['migrations']:
            self.assertEqual(hashlib.sha256((ROOT/'deploy'/m['file']).read_bytes()).hexdigest(),m['sha256'])
        self.assertTrue(d['indexes']['idx_audit_event_id'])
    def test_sqlite_recipe_has_no_delete_or_wal_lifecycle(self):
        source=(ROOT/'app/observability/retained.py').read_text()
        for bad in ('os.remove','unlink(', 'DELETE FROM', 'VACUUM', 'journal_mode=WAL'):
            self.assertNotIn(bad,source)
        self.assertIn('journal_mode=PERSIST',source);self.assertIn('synchronous=FULL',source)
    def test_receiver_contract_rejects_unknown_or_sensitive_fields(self):
        good={'event_id':str(uuid.uuid4()),'condition':'worker','state':'firing'}
        self.assertEqual(self.monitor.validate_alert(good),good)
        for bad in ({**good,'token':'secret'},{**good,'state':'success'},{**good,'event_id':'bad'}):
            with self.assertRaises((ValueError,TypeError)):self.monitor.validate_alert(bad)
    def test_route_templates_and_unknown_paths_have_bounded_labels(self):
        self.assertEqual(self.metrics.route_label({'route':NS(path='/sessions/{id}')}),'/sessions/{id}')
        for path in ('/random/a','/random/b'):
            self.assertEqual(self.metrics.route_label({'path':path}),'__unmatched__')
        self.assertEqual(self.metrics.route_label({'path':'/ui/vendor/private.js'}),'/ui/{asset}')
    def test_packaged_migrations_and_all_process_scrapes(self):
        self.assertIn('COPY deploy/*.sql ./deploy/',(ROOT/'Dockerfile.prod').read_text())
        scrape=(ROOT/'deploy/prometheus-dual-api.yml').read_text()
        for endpoint in ('api:8000','api2:8000','worker:8001'):self.assertIn(endpoint,scrape)
    def test_legacy_import_uses_stable_identity_and_redacts_before_truncation(self):
        load('app.security.redaction','app/security/redaction.py')
        legacy=load('c21_legacy','app/observability/legacy_audit.py')
        raw=json.dumps({'event_type':'fixture','timestamp':'2026-01-01T00:00:00',
                        'input_summary':'Bearer SYNTHETIC_SECRET','payload':{'password':'SYNTHETIC_SECRET'}}).encode()
        digest=hashlib.sha256(raw).hexdigest()
        record=legacy.record_from_legacy('original.json',raw,digest)
        self.assertEqual(record,legacy.record_from_legacy('original.json',raw,digest))
        self.assertNotIn('SYNTHETIC_SECRET',str(record))
        with self.assertRaises(ValueError):legacy.record_from_legacy('original.json',raw,'0'*64)
    def test_no_deletion_calls_in_new_runtime_modules(self):
        for path in ('audit.py','retained.py','monitor.py','receiver.py','service.py'):
            tree=ast.parse((ROOT/'app/observability'/path).read_text())
            bad=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                 and n.func.attr in ('unlink','remove','rmtree','rmdir')]
            self.assertEqual(bad,[])


class AsyncTests(Base, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.prepare()
        async def inline(fn,*args,**kwargs):return fn(*args,**kwargs)
        self.stack.enter_context(patch.object(asyncio,'to_thread',inline))
        redaction=load('app.security.redaction','app/security/redaction.py')
        self.audit_module=load('app.observability.audit','app/observability/audit.py')
        self.audit=self.audit_module.AuditLogger(store=self.store)
        self.pg=NS(execute=AsyncMock(),commit=AsyncMock())
        @asynccontextmanager
        async def session():yield self.pg
        self.stack.enter_context(patch.dict(sys.modules,{'app.core.database':module('app.core.database',get_session_factory=lambda:session)}))
    async def test_audit_has_stable_id_and_original_time(self):
        await self.audit.log('fixture')
        params=self.pg.execute.call_args.args[1]
        self.assertEqual(str(uuid.UUID(params['event_id'])),params['event_id'])
        self.assertIsInstance(params['occurred_at'],datetime)
        self.assertIn('ON CONFLICT (event_id) DO NOTHING',self.pg.execute.call_args.args[0])
    async def test_database_outage_retains_audit(self):
        self.pg.execute.side_effect=RuntimeError('SECRET')
        await self.audit.log('fixture',payload={'token':'SECRET'})
        self.assertEqual(self.store.stats()['pending'],1)
        self.assertNotIn('SECRET',str(self.store.pending('audit')))
    async def test_ambiguous_commit_replays_same_id(self):
        self.pg.commit.side_effect=RuntimeError('lost acknowledgement')
        await self.audit.log('fixture');first=self.pg.execute.call_args.args[1]['event_id']
        self.pg.commit.side_effect=None
        self.assertEqual(await self.audit.flush_local_cache(),1)
        self.assertEqual(first,self.pg.execute.call_args.args[1]['event_id'])
        self.assertEqual(self.store.stats()['pending'],0)
    async def test_receipt_failure_keeps_event_pending(self):
        with patch.object(self.store,'acknowledge',side_effect=OSError('full')):
            await self.audit.log('fixture')
        self.assertEqual(self.store.stats()['pending'],1)
        self.assertEqual(await self.audit.flush_local_cache(),1)
    async def test_double_storage_failure_is_visible_not_success(self):
        self.pg.execute.side_effect=RuntimeError()
        with patch.object(self.store,'append',side_effect=OSError()):await self.audit.log('fixture')
        self.assertEqual((await self.audit.health())['status'],'unhealthy')
        self.assertEqual(self.audit.unretained,1)
    async def test_correlated_audit_context_is_reset(self):
        rt=self.correlation.request_id.set('request-1');tt=self.correlation.task_id.set(str(uuid.uuid4()))
        try:
            await self.audit.log('fixture')
            params=self.pg.execute.call_args.args[1];self.assertEqual(params['request_id'],'request-1')
            self.assertEqual(params['task_id'],self.correlation.task_id.get())
        finally:self.correlation.request_id.reset(rt);self.correlation.task_id.reset(tt)
        self.assertIsNone(self.correlation.snapshot()['request_id'])
    async def test_audit_health_fails_for_unwritable_store(self):
        with patch.object(self.store,'stats',side_effect=OSError()):
            self.assertEqual((await self.audit.health())['status'],'unhealthy')
    async def test_probe_sanitizes_dependency_exceptions(self):
        async def broken():raise RuntimeError('postgres://secret@private')
        name,value=await self.ready.probe('db',broken)
        self.assertEqual(value,{'status':'unhealthy'})
    async def test_probe_timeout_is_unhealthy(self):
        async def timeout():raise TimeoutError()
        self.assertEqual((await self.ready.probe('redis',timeout))[1]['status'],'unhealthy')
    async def test_probe_preserves_cancellation(self):
        async def cancelled():raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):await self.ready.probe('db',cancelled)
    async def test_worker_heartbeat_requires_both_queues(self):
        self.stack.enter_context(patch.dict(sys.modules,{'app.core.task_queue':module('app.core.task_queue',QUEUES=('one','two'))}))
        self.pg.execute.return_value=NS(scalars=lambda:NS(all=lambda:['one']))
        self.assertEqual((await self.ready.worker_observation())['status'],'unhealthy')
        self.pg.execute.return_value=NS(scalars=lambda:NS(all=lambda:['one','two']))
        self.assertEqual((await self.ready.worker_observation())['status'],'healthy')
        self.assertIn('75 seconds',self.pg.execute.call_args.args[0])
    async def request(self,app,receive=None):
        sent=[]
        async def send(message):sent.append(message)
        scope={'type':'http','method':'GET','path':'/records/secret', 'route':NS(path='/records/{id}')}
        await self.metrics.MetricsMiddleware(app)(scope,receive or AsyncMock(),send)
        return sent
    async def test_asgi_stream_duration_finishes_on_last_body_not_background_work(self):
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':200})
            await send({'type':'http.response.body','body':b'x','more_body':True})
            await send({'type':'http.response.body','body':b'end'})
        with patch.object(self.metrics.time,'perf_counter',side_effect=[10,11,15]):
            sent=await self.request(app)
        self.assertEqual(self.metrics.http_request_latency.values[-1][1],5)
        self.assertEqual(self.metrics.http_response_start.values[-1][1],1)
        self.assertEqual(self.metrics.http_outcomes.values[-1][0]['outcome'],'complete')
        self.assertIn(b'x-request-id',dict(sent[0]['headers']))
        self.assertEqual(self.correlation.request_id.get(),'')
    async def test_asgi_exception_before_headers_is_recorded(self):
        async def app(scope,receive,send):raise RuntimeError('secret')
        with self.assertRaises(RuntimeError):await self.request(app)
        self.assertEqual(self.metrics.http_outcomes.values[-1][0]['outcome'],'aborted')
        self.assertEqual(self.metrics.http_request_latency.values[-1][0]['status'],'500')
        self.assertEqual(self.correlation.request_id.get(),'')
    async def test_asgi_disconnect_does_not_claim_complete(self):
        async def app(scope,receive,send):await receive()
        await self.request(app,AsyncMock(return_value={'type':'http.disconnect'}))
        self.assertEqual(self.metrics.http_outcomes.values[-1][0]['outcome'],'disconnected')
    async def test_monitor_retains_firing_and_resolution_receipts(self):
        active=True;receipts=[]
        async def remote(client,method,url,**kw):
            if method=='GET':return (503,{'status':'unavailable'}) if active else (200,{'status':'ready'})
            receipts.append(kw['json']);return 200,{'event_id':kw['json']['event_id'],'status':'retained'}
        monitor=self.monitor.Monitor(self.store,None,'x'*32,('api',))
        with patch.object(self.monitor,'bounded_json',remote):
            await monitor.tick();active=False;await monitor.tick()
        self.assertEqual([r['state'] for r in receipts],['firing','resolved'])
        self.assertEqual(self.store.pending('alert'),[])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM retained_events WHERE channel='alert'").fetchone()[0],2)
    async def test_lost_alert_ack_retries_same_identity_before_recovery(self):
        calls=[];active=True
        async def remote(client,method,url,**kw):
            if method=='GET':return (503,{'status':'unavailable'}) if active else (200,{'status':'ready'})
            calls.append(kw['json'])
            if len(calls)==1:raise TimeoutError()
            return 200,{'event_id':kw['json']['event_id'],'status':'retained'}
        monitor=self.monitor.Monitor(self.store,None,'x'*32,('api',))
        with patch.object(self.monitor,'bounded_json',remote):
            await monitor.tick();active=False;await monitor.tick()
        self.assertEqual(calls[0]['event_id'],calls[1]['event_id'])
        self.assertEqual([r['state'] for r in calls],['firing','firing','resolved'])
    async def test_forged_alert_ack_remains_pending(self):
        async def remote(client,method,url,**kw):return (503,{}) if method=='GET' else (200,{'status':'retained'})
        with patch.object(self.monitor,'bounded_json',remote):
            await self.monitor.Monitor(self.store,None,'x'*32,('worker',)).tick()
        self.assertEqual(len(self.store.pending('alert')),1)
    async def test_healthy_with_old_audit_backlog_is_a_fault(self):
        async def remote(client,method,url,**kw):
            if method=='GET':return 200,{'status':'ready','components':{'audit':{'oldest_seconds':61}}}
            raise TimeoutError()
        with patch.object(self.monitor,'bounded_json',remote):
            await self.monitor.Monitor(self.store,None,'x'*32,('api',)).tick()
        self.assertEqual(self.store.pending('alert')[0]['body']['state'],'firing')

    async def test_required_dependencies_merge_to_unavailable_and_recover(self):
        @asynccontextmanager
        async def redis(): yield NS(ping=AsyncMock(return_value=True))
        tool_names = ('query_customer','query_order','create_crm_task','create_ticket',
                      'update_ticket','send_email_internal','send_email_external','query_my_approvals')
        deps = {
            'app.config': module('app.config',get_settings=lambda:NS(vector_store_provider='milvus',app_env='prod')),
            'app.core.database': module('app.core.database',check_db_health=AsyncMock(return_value={'status':'healthy'})),
            'app.core.runtime_state': module('app.core.runtime_state',runtime_client=redis),
            'app.observability.audit': module('app.observability.audit',get_audit_logger=lambda:self.audit),
            'app.tools.base': module('app.tools.base',list_tools=lambda:[{'name':n} for n in tool_names]),
            'app.core.milvus_client': module('app.core.milvus_client',get_collection=lambda:NS(name='fixture')),
            'pymilvus': module('pymilvus',utility=NS(has_collection=lambda *a,**k:True)),
            'app.graph': module('app.graph',checkpointer=NS(_checkpointer_instance=object())),
            'app.graph.checkpoint_access': module('app.graph.checkpoint_access',read_checkpoint=AsyncMock()),
        }
        with patch.dict(sys.modules,deps), patch.object(self.ready,'worker_observation',AsyncMock(return_value={'status':'healthy'})):
            original=self.ready.probe
            for failed in ('db','redis','milvus','checkpointer','tools','workers','audit'):
                async def failed_probe(name, operation):
                    return (name,{'status':'unhealthy'}) if name==failed else await original(name,operation)
                with patch.object(self.ready,'probe',failed_probe):
                    result=await self.ready.collect_readiness()
                    self.assertEqual(result['status'],'unavailable',failed)
                    self.assertEqual(result['components'][failed]['status'],'unhealthy')
            self.assertEqual((await self.ready.collect_readiness())['status'],'ready')
            worker=await self.ready.collect_readiness(worker=True)
            self.assertNotIn('checkpointer',worker['components'])
    async def test_ready_http_status_and_liveness_are_distinct(self):
        tree=ast.parse((ROOT/'app/main.py').read_text())
        create=next(n for n in tree.body if getattr(n,'name',None)=='create_app')
        fn=next(n for n in create.body if getattr(n,'name',None)=='ready');fn.decorator_list=[]
        ns={'JSONResponse':lambda body,status_code:NS(body=body,status_code=status_code)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'ready','exec'),ns)
        for state,code in [('ready',200),('unavailable',503)]:
            with patch.object(self.ready,'collect_readiness',AsyncMock(return_value={'status':state})):
                self.assertEqual((await ns['ready']()).status_code,code)
        health=next(n for n in create.body if getattr(n,'name',None)=='health')
        self.assertNotIn('collect_readiness',ast.unparse(health))
    async def test_worker_observation_server_preserves_supervisor_signals_and_closes(self):
        service=load('c21_service','app/observability/service.py')
        closed=AsyncMock()
        class Server:
            def __init__(self, config): self.started=True
            async def serve(self):
                with self.capture_signals(): raise asyncio.CancelledError
            async def shutdown(self): await closed()
        with patch.dict(sys.modules, {'uvicorn':module('uvicorn',Server=Server,Config=Mock())}):
            with self.assertRaises(asyncio.CancelledError):
                await service.serve_worker_observations('worker')
        closed.assert_awaited_once()
    async def test_tracing_is_registered_before_application_start(self):
        tree=ast.parse((ROOT/'app/main.py').read_text())
        create=next(n for n in tree.body if getattr(n,'name',None)=='create_app')
        lifespan=next(n for n in tree.body if getattr(n,'name',None)=='lifespan')
        self.assertIn('instrument_fastapi(app)',ast.unparse(create))
        self.assertNotIn('instrument_fastapi(app)',ast.unparse(lifespan))
        self.assertIn('init_tracing(',ast.unparse(lifespan))

    async def test_actual_receiver_retains_duplicate_once_and_rejects_unauthorized(self):
        receiver=load('c21_receiver','app/observability/receiver.py').Receiver
        obj=receiver.__new__(receiver);obj.store=self.store;obj.token='t'*32;obj.path='/alerts'
        obj.reply=Mock()
        body={'event_id':str(uuid.uuid4()),'condition':'api','state':'firing'}
        encoded=json.dumps(body).encode()
        obj.headers={'Content-Length':str(len(encoded)),'Authorization':'Bearer '+'t'*32}
        for _ in range(2):obj.rfile=io.BytesIO(encoded);obj.do_POST()
        self.assertEqual(obj.reply.call_args.args[0],200)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM retained_events WHERE channel='receipt'").fetchone()[0],1)
        obj.headers['Authorization']='Bearer wrong';obj.do_POST()
        self.assertEqual(obj.reply.call_args.args[0],401)
    async def test_receiver_rejects_large_and_unexpected_payloads(self):
        receiver=load('c21_receiver','app/observability/receiver.py').Receiver
        obj=receiver.__new__(receiver);obj.store=self.store;obj.token='t'*32;obj.path='/alerts';obj.reply=Mock()
        obj.headers={'Authorization':'Bearer '+'t'*32,'Content-Length':'9999'};obj.rfile=io.BytesIO(b'')
        obj.do_POST();self.assertEqual(obj.reply.call_args.args[0],400)
    async def test_bounded_observation_transport_rejects_large_response(self):
        class Response:
            status_code=200
            async def aiter_bytes(self):yield b'x'*65537
        @asynccontextmanager
        async def stream(*args,**kwargs):yield Response()
        with self.assertRaises(ValueError):await self.monitor.bounded_json(NS(stream=stream),'GET','http://fixture')


if __name__=='__main__':
    sys.dont_write_bytecode=True
    def guard(event,args):
        if event=='socket.__new__' and args[1]==1:return
        if event=='sqlite3.connect' and args[0]!=':memory:':raise RuntimeError('DISK_DB_DENIED')
        if event.startswith(('socket.','subprocess.')) or event in {'os.remove','os.rmdir','os.rename','os.mkdir','os.chmod','os.system'}:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event=='open' and ((isinstance(args[1],str) and any(c in args[1] for c in 'wax+')) or (isinstance(args[2],int) and args[2]&3)):
            raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
