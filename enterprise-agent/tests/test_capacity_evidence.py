"""C23 actual-source tests with memory-only evidence and injected I/O; never real load."""
from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capacity import contract as c, runner as r
from reference_service.contract import canonical
from reference_service.service import Credential, Service
from reference_service.store import Store


def plan():
    value = json.loads((ROOT / 'eval/capacity-plan.example.json').read_text())
    value['candidate'].update(commit='a'*40, application_image='fixture/app@sha256:'+'a'*64,
                             reference_image='fixture/ref@sha256:'+'b'*64,
                             capacity_image='fixture/capacity@sha256:'+'e'*64, schema_sha256='c'*64)
    value['environment'].update(os='linux-amd64', cpu='synthetic-cpu', cores=8, memory_gib=32,
                                storage='synthetic-ssd', evidence_sha256='d'*64)
    value['models']['quota_cost_review_sha256'] = 'e'*64
    value['dataset'].update(manifest_sha256='f'*64, documents=9, chunks=100, orders=2,
        reference_run_id=str(uuid4()), mail_store_id=str(uuid4()), mail_fixture_sha256='a'*64)
    value['actors']['isolation_review_sha256'] = 'b'*64
    value['oracles']['qa'].update(required_text=['return-policy'], source_ids=['doc-1'])
    return value


def record(slot, offset, kind):
    names = (['stream', 'evidence', 'decide', 'resume', 'evidence', 'mail_ledger']
             if kind == 'approval' else ['stream'])
    return {'slot':slot, 'kind':kind, 'start_ms':offset*1000, 'elapsed_ms':1000,
            'ttft_ms':100, 'outcome':'OBSERVED', 'oracle_sha256':'c'*64,
            'phases':[{'name':name, 'status':200, 'complete':True, 'elapsed_ms':100}
                      for name in names]}


def all_records(p):
    return [record(*slot) for slot in c.schedule(p)]


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.p = plan()

    def test_template_is_not_executable(self):
        with self.assertRaises(ValueError):c.validate(c.read_json(ROOT/'eval/capacity-plan.example.json'))

    def test_frozen_schedule_covers_30_minutes_exact_mix(self):
        c.validate(self.p)
        slots=c.schedule(self.p)
        self.assertEqual(len(slots),360)
        self.assertEqual([sum(k==kind for _,_,k in slots) for kind in c.KINDS],[216,72,72])
        self.assertEqual(slots[-1][1],1795)

    def test_changed_plan_changes_approval_digest(self):
        other=deepcopy(self.p);other['workload']['concurrency']=4
        self.assertNotEqual(c.digest(other),c.digest(self.p))

    def test_invalid_frozen_fields_are_rejected(self):
        for group,key,value in [('candidate','commit','main'),('environment','cores',True),
            ('environment','memory_gib',float('nan')),('environment','os','macos'),
            ('workload','duration_seconds',600),('workload','interval_seconds',0),
            ('workload','cycle',['qa']),('workload','concurrency',9),
            ('workload','min_samples_per_kind',1000),('workload','drain_seconds',1),
            ('models','quota_cost_review_sha256',None),('actors','rate_limit_per_minute',300)]:
            with self.subTest(key=key):
                p=deepcopy(self.p);p[group][key]=value
                with self.assertRaises(ValueError):c.validate(p)

    def test_unknown_fields_and_relaxed_thresholds_denied(self):
        p=deepcopy(self.p);p['baseline']['p95_ms']=2001
        with self.assertRaises(ValueError):c.validate(p)
        self.p['token']='do-not-persist'
        with self.assertRaises(ValueError):c.validate(self.p)

    def test_unresolved_oracle_rejected(self):
        self.p['oracles']['qa']['required_text']=['REPLACE_ME']
        with self.assertRaises(ValueError):c.validate(self.p)

    def test_json_duplicate_and_nan_denied(self):
        for raw in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
            with self.assertRaises(ValueError):c.strict_json(raw)

    def test_percentiles_are_nearest_rank_including_boundaries(self):
        self.assertEqual(c.percentile(list(range(1,101)),95),95)
        self.assertEqual(c.percentile(list(range(1,101)),99),99)
        self.assertIsNone(c.percentile([],99))

    def test_synthetic_success_never_runtime_acceptance(self):
        result=c.summarize(self.p,all_records(self.p),completed=True,evidence_kind='synthetic')
        self.assertEqual(result['measurement_status'],'OBSERVED')
        self.assertEqual(result['acceptance_status'],'BLOCKED')
        self.assertFalse(result['release_allowed'])
        self.assertEqual(set(result['runtime_cases'].values()),{'BLOCKED'})
        self.assertEqual(result['queue_latency'],'NOT_OBSERVED')

    def test_no_observations_is_not_zero_error_success(self):
        report=c.summarize(self.p,[],completed=False,evidence_kind='runtime')
        self.assertEqual(report['acceptance_status'],'FAIL')
        self.assertEqual(report['business']['qa']['error_rate'],1)
        self.assertIsNone(report['business']['qa']['p99_ms'])

    def test_missing_records_stay_in_denominator(self):
        rows=all_records(self.p);rows.pop()
        result=c.summarize(self.p,rows,completed=True,evidence_kind='runtime')
        self.assertEqual(result['business']['approval']['scheduled'],72)
        self.assertEqual(result['business']['approval']['missing'],1)
        self.assertEqual(result['acceptance_status'],'FAIL')

    def test_duplicate_wrong_kind_or_unknown_slot_rejected(self):
        rows=all_records(self.p)
        for bad in ([*rows,rows[0]], [dict(rows[0],slot=99999)], [dict(rows[0],kind='approval')]):
            with self.assertRaises(ValueError):c.summarize(self.p,bad,completed=True,evidence_kind='synthetic')

    def test_bad_phase_and_nan_timing_rejected(self):
        row=record(0,0,'qa')
        for bad in (dict(row,elapsed_ms=float('nan')),dict(row,phases=[]),
                    dict(row,ttft_ms=2000),dict(row,oracle_sha256=None),
                    dict(row,phases=[dict(row['phases'][0],status=429)])):
            with self.assertRaises(ValueError):c.validate_record(bad)

    def test_threshold_equality_latency_passes_error_equality_fails(self):
        self.p['workload'].update(duration_seconds=3000,interval_seconds=3)
        rows=all_records(self.p)
        for row in rows:row['elapsed_ms']=2000
        before=c.summarize(self.p,rows,completed=True,evidence_kind='runtime')
        self.assertEqual(before['measurement_status'],'OBSERVED')
        victim=next(row for row in rows if row['kind']=='analysis')
        victim.update(outcome='HTTP_ERROR',oracle_sha256=None)
        after=c.summarize(self.p,rows,completed=True,evidence_kind='runtime')
        self.assertEqual(after['business']['analysis']['error_rate'],.005)
        self.assertEqual(after['measurement_status'],'FAIL')

    def test_429_is_separate_but_still_failure(self):
        row=record(0,0,'qa');row.update(outcome='HTTP_ERROR',oracle_sha256=None)
        row['phases'][0].update(status=429,complete=False)
        report=c.summarize(self.p,[row],completed=False,evidence_kind='runtime')
        self.assertEqual(report['http_phases']['qa:stream']['rate_limited'],1)
        self.assertEqual(report['http_phases']['qa:stream']['censored'],1)
        self.assertEqual(report['http_phases']['qa:stream']['samples'],0)

    def test_late_success_rejected_and_drops_retained(self):
        row=record(0,0,'qa');row['start_ms']=1001
        with self.assertRaises(ValueError):c.summarize(self.p,[row],completed=True,evidence_kind='runtime')
        result=c.summarize(self.p,[r.dropped(0,'qa')],completed=False,evidence_kind='runtime')
        self.assertEqual(result['business']['qa']['outcomes']['DROPPED'],1)

    def test_early_termination_and_missing_ttft_never_pass(self):
        rows=all_records(self.p)
        for row in rows:row['ttft_ms']=None
        result=c.summarize(self.p,rows,completed=False,evidence_kind='runtime')
        self.assertEqual(result['measurement_status'],'BLOCKED')
        self.assertEqual(result['business']['qa']['ttft_missing'],216)
        self.assertEqual(result['acceptance_status'],'BLOCKED')

    def test_full_workflow_baseline_cannot_be_replaced_by_ttft(self):
        rows=all_records(self.p)
        for row in rows:row['elapsed_ms']=6000
        result=c.summarize(self.p,rows,completed=True,evidence_kind='runtime')
        self.assertEqual(result['business']['qa']['ttft']['p99_ms'],100)
        self.assertEqual(result['business']['qa']['historical_baseline'],'FAIL')


class StreamTests(unittest.TestCase):
    def test_split_unicode_crlf_and_first_nonempty_token(self):
        parser=r.SSE()
        parser.feed(b'data: {"type":"progress"}\r\n\r\n',10)
        parser.feed(b'data: {"type":"token","data":""}\n\n',20)
        chunk='data: {"type":"token","data":"你好"}\r\n\r\n'.encode()
        for piece in (chunk[:33],chunk[33:35],chunk[35:]):parser.feed(piece,30)
        parser.feed(b'data: {"type":"final","data":{"answer":"ok"}}\n\n',100)
        self.assertEqual(parser.finish()['answer'],'ok')
        self.assertEqual(parser.first_token_ms,30)

    def test_final_is_not_token(self):
        parser=r.SSE();parser.feed(b'data: {"type":"final","data":{}}\n\n',100)
        parser.finish();self.assertIsNone(parser.first_token_ms)

    def test_unterminated_or_error_stream_is_failure(self):
        for raw in (b'data: {"type":"error"}\n\n',b'data: {"type":"cancelled"}\n\n',
                    b'data: {"type":"final","data":{}}',b'data: {}\n\n'):
            with self.assertRaises((ValueError,r.MeasurementError)):
                parser=r.SSE();parser.feed(raw,10);parser.finish()

    def test_duplicate_final_and_oversized_event_denied(self):
        parser=r.SSE();frame=b'data: {"type":"final","data":{}}\n\n'
        parser.feed(frame,10)
        with self.assertRaises(ValueError):parser.feed(frame,20)
        with self.assertRaises(ValueError):r.SSE().feed(b'a'*(1024*1024+1),0)


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.p=plan()

    def test_nonempty_answer_without_intent_or_sources_fails(self):
        data={'answer':'return-policy','needs_replan':False,'intent':'knowledge_qa',
              'sources':[{'document_id':'doc-1'}]}
        self.assertEqual(len(r.answer_oracle(self.p,'qa',data)),64)
        for key,value in [('sources',[]),('intent','chitchat'),('needs_replan',True),('answer','')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                r.answer_oracle(self.p,'qa',dict(data,**{key:value}))

    def test_analysis_uses_real_intent_and_frozen_markers(self):
        data={'answer':'HTTP 参考 CRM 合计 CNY：1,300.49 订单数 2','needs_replan':False,
              'intent':'data_analysis'}
        self.assertEqual(len(r.answer_oracle(self.p,'analysis',data)),64)
        with self.assertRaises(ValueError):r.answer_oracle(self.p,'analysis',dict(data,answer='1,300.48'))

    def reference(self):
        db=sqlite3.connect(':memory:',isolation_level=None);self.addCleanup(db.close)
        store=Store(db,'mail',self.p['dataset']['mail_store_id'],initialize=True)
        run=self.p['dataset']['reference_run_id']
        store.provision({'run_id':run,'principal':'application','users':['requester','approver'],
                         'fixture':'baseline','external_recall_supported':True})
        token='synthetic-token-for-memory-test-000000'
        service=Service(store,{token:Credential('application',frozenset({'read','write'}))},'o'*32)
        oid=str(uuid4())
        body={'scope':'external','to':['customer@reference.invalid'],'subject':'capacity-reference',
              'body':'synthetic','cc':[],'attachments':[]}
        response=service.handle('POST','/api/v1/send',{'authorization':'Bearer '+token,
            'x-reference-run-id':run,'x-request-id':str(uuid4()),'accept':'application/json',
            'content-type':'application/json','idempotency-key':'ba-ref-v1:'+oid},canonical(body).encode())
        self.assertEqual(response.status,201)
        ledger=store.evidence(run);self.p['dataset']['mail_fixture_sha256']=ledger['fixture_hash']
        op=ledger['operations'][0]['operation']
        app={'approvals':[{'approval_id':'approval','requester_id':'requester','approver_id':'approver',
                          'status':'executed'}],
             'operations':[dict(op,tool='send_email_external')],
             'audit':[{'success':True,'tool_name':'send_email_external'}],'jobs':[],'steps':[]}
        return app,ledger

    def test_actual_independent_store_receipt_is_required(self):
        app,ledger=self.reference()
        self.assertEqual(len(r.evidence_oracle(self.p,app,ledger,'requester','approver','approval')),64)

    def test_receipt_wrong_identity_duplicate_effect_and_recipient_refused(self):
        app,ledger=self.reference()
        cases=[]
        wrong=deepcopy(ledger);wrong['store_id']=str(uuid4());cases.append((app,wrong))
        wrong=deepcopy(ledger);wrong['operations'][0]['operation']['request_hash']='0'*64;cases.append((app,wrong))
        wrong=deepcopy(ledger);next(x for x in wrong['resources'] if x['kind']=='messages')['value']['to']=['employee@reference.invalid'];cases.append((app,wrong))
        wrong=deepcopy(ledger);wrong['attempts']+=deepcopy(wrong['attempts']);cases.append((app,wrong))
        wrong=deepcopy(app);wrong['approvals'][0]['status']='executing';cases.append((wrong,ledger))
        wrong=deepcopy(app);wrong['audit']=[];cases.append((wrong,ledger))
        for a,l in cases:
            with self.assertRaises(ValueError):r.evidence_oracle(self.p,a,l,'requester','approver','approval')


class RunnerTests(unittest.TestCase):
    def test_no_execute_or_bad_digest_never_constructs_client(self):
        p=plan()
        for flags in ([],['--execute','--approved-plan-sha256','bad','--output','/no-write']):
            with patch.object(r,'read_json',return_value=p),patch.object(sys,'argv',['capacity','--plan','fake',*flags]),\
                    patch.object(r,'Transport') as client,patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(r.main(),2);client.assert_not_called()

    def test_empty_or_shared_identity_preflight_stops(self):
        w=r.Workload(plan(),Mock(),{})
        with self.assertRaises(ValueError):w.preflight()
        w.transport.request.assert_not_called()

    def test_late_slot_does_not_call_application(self):
        w=r.Workload(plan(),Mock(),{})
        with patch.object(r.time,'monotonic',return_value=10):row=w.flow(0,0,'qa',0)
        self.assertEqual(row['outcome'],'DROPPED');w.transport.request.assert_not_called()

    def test_secret_exception_is_reduced_to_code(self):
        t=Mock()
        def fail(*args,**kwargs):
            kwargs['measurement'].update(status=0,complete=False,elapsed_ms=1)
            raise OSError('private-token-and-user-content')
        t.request.side_effect=fail
        w=r.Workload(plan(),t,{});w.tokens={'REQUESTER_0':'secret'}
        with patch.object(r.time,'monotonic',return_value=0):row=w.flow(0,0,'qa',0)
        self.assertEqual(row['outcome'],'TRANSPORT_ERROR')
        self.assertNotIn('private',c.canonical(row));self.assertNotIn('secret',c.canonical(row))

    def test_interruption_prevents_next_approval_mutation(self):
        w=r.Workload(plan(),Mock(),{});w.tokens={'REQUESTER_0':'secret'};w.stop.set()
        with patch.object(r.time,'monotonic',return_value=0):row=w.flow(0,0,'approval',0)
        self.assertEqual(row['outcome'],'INTERRUPTED');w.transport.request.assert_not_called()

    def test_scheduler_preserves_full_window_and_all_slots(self):
        clock=NS(now=0.0)
        def sleep(seconds):clock.now+=seconds
        class Pool:
            def __init__(self,**kwargs):pass
            def submit(self,fn,slot,offset,kind,origin):
                return NS(done=lambda:True,result=lambda:record(slot,offset,kind))
            def shutdown(self,**kwargs):pass
        w=r.Workload(plan(),Mock(),{});rows=[]
        with patch.object(r,'ThreadPoolExecutor',Pool),patch.object(r.time,'monotonic',lambda:clock.now),\
                patch.object(r.time,'sleep',sleep):
            self.assertTrue(r.collect(w.plan,w,rows.append))
        self.assertEqual(clock.now,1800);self.assertEqual(len(rows),360)
        self.assertEqual(len({row['slot'] for row in rows}),360)

    def test_busy_lane_drops_arrivals_and_never_retries(self):
        clock=NS(now=0.0);submitted=[]
        class Pool:
            def __init__(self,**kwargs):self.done=False
            def submit(self,fn,slot,offset,kind,origin):
                submitted.append(slot)
                return NS(done=lambda:self.done,result=lambda:record(slot,offset,kind))
            def shutdown(self,**kwargs):self.done=True
        w=r.Workload(plan(),Mock(),{});rows=[]
        with patch.object(r,'ThreadPoolExecutor',Pool),patch.object(r.time,'monotonic',lambda:clock.now),\
                patch.object(r.time,'sleep',lambda seconds:setattr(clock,'now',clock.now+seconds)):
            self.assertFalse(r.collect(w.plan,w,rows.append))
        self.assertEqual(len(submitted),3)
        self.assertEqual(sum(row['outcome']=='DROPPED' for row in rows),357)
        self.assertEqual(len(rows),360)

    def test_redirect_not_followed_and_raw_response_not_read(self):
        transport=r.Transport.__new__(r.Transport)
        transport.timeout=5;transport.targets={'app':('nginx',443)};transport.tls=object()
        connection=Mock();response=Mock(status=302);connection.getresponse.return_value=response
        with patch.object(r.http.client,'HTTPSConnection',return_value=connection):
            metric={}
            with self.assertRaises(r.MeasurementError):
                transport.request('app','GET','/ready',None,measurement=metric)
        self.assertEqual(metric['status'],302);response.read1.assert_not_called()
        connection.close.assert_called_once()

    def test_https_hostname_and_certificate_checks_are_enabled(self):
        tls=Mock()
        with patch.object(r.ssl,'create_default_context',return_value=tls) as factory:
            transport=r.Transport(5)
        self.assertIs(transport.tls,tls);factory.assert_called_once()
        self.assertEqual(transport.targets['app'],('nginx',443))

    def test_request_body_is_explicit_utf8(self):
        # Checked at source level as fake transport tests otherwise hide HTTP encoding behavior.
        source=(ROOT/'capacity/runner.py').read_text()
        self.assertIn("canonical(body).encode('utf-8')",source)


class AdditionalTests(unittest.TestCase):
    def test_legacy_missing_or_nonboolean_thresholds_never_pass(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('legacy_report',ROOT/'eval/render_load_report.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        value={'metrics':{}}
        self.assertFalse(module.legacy_threshold_status(value,0))
        for endpoint in ('health','chat'):
            for metric, names in (('duration',('p(95)<2000','p(99)<5000')),('failed',('rate<0.005',))):
                value['metrics'][f'http_req_{metric}{{endpoint:{endpoint}}}']={
                    'thresholds':{key:{'ok':True} for key in names}}
        self.assertTrue(module.legacy_threshold_status(value,0))
        value['metrics']['http_req_duration{endpoint:chat}']['thresholds']['p(99)<5000']['ok']='true'
        self.assertFalse(module.legacy_threshold_status(value,0))
        self.assertFalse(module.legacy_threshold_status(value,1))

    def test_drain_completions_not_counted_as_steady_throughput(self):
        p=plan();rows=all_records(p);rows[-1]['elapsed_ms']=6000
        report=c.summarize(p,rows,completed=True,evidence_kind='runtime')
        self.assertEqual(report['business']['approval']['completed_in_drain'],1)
        self.assertEqual(report['business']['approval']['completed_in_window'],71)

    def test_stream_transport_measures_token_and_full_response_separately(self):
        transport=r.Transport.__new__(r.Transport)
        transport.timeout=5;transport.targets={'app':('nginx',443)};transport.tls=object()
        connection=Mock();response=Mock(status=200)
        response.getheader.return_value='text/event-stream; charset=utf-8'
        response.read1.side_effect=[b'data: {"type":"token","data":"a"}\n\n',
            b'data: {"type":"final","data":{"answer":"a"}}\n\n',b'']
        connection.getresponse.return_value=response
        metric={}
        with patch.object(r.http.client,'HTTPSConnection',return_value=connection):
            data,ttft=transport.request('app','POST','/api/v1/chat/stream','transient',
                                       {'message':'合成'},stream=True,measurement=metric)
        self.assertEqual(data['answer'],'a');self.assertIsNotNone(ttft)
        self.assertLessEqual(ttft,metric['elapsed_ms']);self.assertTrue(metric['complete'])
        self.assertIsInstance(connection.request.call_args.args[2],bytes)

    def test_total_response_limit_and_read_deadline(self):
        transport=r.Transport.__new__(r.Transport)
        transport.timeout=5;transport.targets={'app':('nginx',443)};transport.tls=object()
        connection=Mock();response=Mock(status=200)
        response.read1.side_effect=[b'x'*(8*1024*1024+1)]
        connection.getresponse.return_value=response
        with patch.object(r.http.client,'HTTPSConnection',return_value=connection):
            with self.assertRaises(ValueError):transport.request('app','GET','/ready',None)
        with patch.object(r.http.client,'HTTPSConnection',return_value=connection),\
                patch.object(r.time,'monotonic',side_effect=[0,6,6]):
            with self.assertRaises(TimeoutError):transport.request('app','GET','/ready',None)

    def test_preflight_checks_current_identity_and_empty_bound_run(self):
        p=plan();counter={'index':-1};calls=[]
        def request(target,method,path,token,body=None,**kwargs):
            calls.append(path)
            if path.endswith('/login'):
                counter['index']+=1
                return {'access_token':str(counter['index'])},None
            if path.endswith('/me'):
                return {'user_id':'u'+token,'role':'admin' if token=='0' else 'manager'},None
            if path.endswith('/reference-profile'):
                return {'data':{'status':'CONFIGURED','run_id':p['dataset']['reference_run_id'],
                                'principal':'application'}},None
            if path=='/ready':return {'status':'ready'},None
            return {'run_id':p['dataset']['reference_run_id'],'store_id':p['dataset']['mail_store_id'],
                    'fixture_hash':p['dataset']['mail_fixture_sha256'],'principal':'application',
                    'operations':[],'schema':'reference-store-v1','service':'mail'},None
        env={'CAPACITY_OPERATOR_TOKEN':'o'*32}
        for actor in ['ADMIN','APPROVER','REQUESTER_0','REQUESTER_1','REQUESTER_2']:
            env['CAPACITY_'+actor+'_USERNAME']=actor;env['CAPACITY_'+actor+'_PASSWORD']='private'
        workload=r.Workload(p,NS(request=request),env);workload.preflight()
        self.assertEqual(len(workload.ids),5)
        self.assertEqual(sum(path.endswith('/login') for path in calls),5)
        self.assertFalse(any('/chat/' in path for path in calls))

    def test_flow_records_exact_application_sequence_without_business_retry(self):
        helper=OracleTests();helper.setUp()
        try:
            app,ledger=helper.reference();p=helper.p
            pending=deepcopy(app);pending['approvals'][0].update(status='pending',
                operation_type='send_email_external',requester_id='requester')
            calls=[];evidence_reads=0
            def request(target,method,path,token,body=None,**kwargs):
                nonlocal evidence_reads
                calls.append((target,method,path,token,body))
                kwargs['measurement'].update(status=200,complete=True,elapsed_ms=100)
                if path.endswith('/stream'):return {'session_id':'session'},10
                if '/reference-evidence/' in path:
                    evidence_reads+=1
                    return {'data':pending if evidence_reads==1 else app},None
                if path.endswith('/decide'):return {'status':'approved_pending_reauth'},None
                if path.endswith('/resume'):return {'status':'executed'},None
                return ledger,None
            workload=r.Workload(p,NS(request=request),{})
            workload.tokens={'REQUESTER_0':'requester-token','APPROVER':'approver-token','ADMIN':'admin-token'}
            workload.ids={'REQUESTER_0':'requester','APPROVER':'approver'}
            with patch.object(r.time,'monotonic',side_effect=[0,1]):row=workload.flow(0,0,'approval',0)
            self.assertEqual(row['outcome'],'OBSERVED');c.validate_record(row)
            self.assertEqual([x['name'] for x in row['phases']],
                ['stream','evidence','decide','resume','evidence','mail_ledger'])
            self.assertEqual(calls[2][3],'approver-token');self.assertEqual(calls[3][3],'requester-token')
            self.assertNotIn('session_id',calls[0][4])
        finally:helper.doCleanups()


if __name__ == '__main__':
    sys.dont_write_bytecode=True
    def guard(event,args):
        if event=='sqlite3.connect' and args[0]!=':memory:':raise RuntimeError('DISK_DB_DENIED')
        if event.startswith(('socket.','subprocess.')) or event in {
            'os.remove','os.rmdir','os.rename','os.mkdir','os.chmod','os.system','os.link','os.symlink'}:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event=='open' and ((isinstance(args[1],str) and any(c in args[1] for c in 'wax+'))
            or (isinstance(args[2],int) and args[2]&3)):
            raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
