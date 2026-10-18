"""C11 actual-source offline tests. Doubles do not establish SQL/JWT/browser acceptance."""
from __future__ import annotations

import asyncio
import ast
from copy import deepcopy
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch
import uuid

ROOT=Path(__file__).resolve().parents[1]
BASE=runpy.run_path(str(ROOT/'tests/test_runtime_authorization.py'))
Base=BASE['RuntimeAuthorizationTests'];Database=BASE['Database'];Model=BASE['Model']
HTTPException=BASE['HTTPException'];load=BASE['load'];module=BASE['module']


class ManyDatabase(Database):
    def __init__(self):
        super().__init__()
        self.rows={'a1':self.row}
        self.saved_rows=deepcopy(self.rows)
        self.fail_commit=False
        self.fail_audit=False

    async def execute(self,sql,params=None):
        if self.fail_audit and 'INSERT INTO audit_logs' in sql:raise RuntimeError('synthetic-secret')
        if params and params.get('id') in self.rows:self.row=self.rows[params['id']]
        if 'LIMIT 100 FOR UPDATE SKIP LOCKED' in sql:
            self.queries.append((sql, params or {}))
            candidates=[deepcopy(r) for r in self.rows.values() if (
                r.status in ('pending','approved_pending_reauth') and not r.live
                or r.status in ('executing','execution_unknown'))]
            return NS(fetchall=lambda:candidates[:100])
        return await super().execute(sql,params)

    async def commit(self):
        await super().commit()
        self.saved_rows=deepcopy(self.rows)
        if self.fail_commit:raise RuntimeError('synthetic-commit-ack-loss')

    async def rollback(self):
        await super().rollback()
        self.rows=deepcopy(self.saved_rows);self.row=self.rows['a1']


class ApprovalTests(Base):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db=ManyDatabase()
        self.lifecycle.observe=self.original_observe
        self.timeout=load('c11_timeout','app/core/approval_timeout.py')
        self.execute.side_effect=self.complete
        self.eid='00000000-0000-4000-8000-000000000002'

    async def complete(self,*args):
        self.db.operations=[dict(operation_id='00000000-0000-4000-8000-000000000001',
            execution_id=self.eid,state='committed',intent={'target':{'provider':'mock'}},
            request={},receipt={'success':True})]
        return Model(success=True,output={})

    async def ready(self):
        self.db.row.status='approved_pending_reauth'
        await self.db.commit()

    async def resume(self,aid='a1'):
        return await self.approval.resume_pending_execution(aid,requester=Model(user_id='requester'),
            credentials=self.credentials(),db=self.db)

    async def decide(self,decision='approved',aid='a1'):
        return await self.approval.decide_approval(aid,Model(decision=decision,comment=''),
            approver=Model(user_id='approver'),db=self.db)

    async def test_approved_is_not_executed_and_repeat_decision_conflicts(self):
        result=await self.decide()
        self.assertEqual(result.status,'approved_pending_reauth')
        self.execute.assert_not_awaited()
        with self.assertRaises(HTTPException) as caught:await self.decide('rejected')
        self.assertEqual(caught.exception.status_code,409)
        self.assertEqual(self.db.row.status,'approved_pending_reauth')
        self.assertEqual(len(self.db.events),1)

    async def test_expired_pending_decision_is_timeout_not_approved(self):
        self.db.row.live=False;await self.db.commit()
        with self.assertRaises(HTTPException):await self.decide()
        self.assertEqual(self.db.row.status,'timeout')
        self.assertEqual(self.db.events[-1]['new_status'],'timeout')
        self.assertEqual(self.notify.await_args.kwargs['result_type'], 'timeout')
        self.execute.assert_not_awaited()

    async def test_expired_approved_request_cannot_claim(self):
        await self.ready();self.db.row.live=False;await self.db.commit()
        with self.assertRaises(HTTPException):await self.resume()
        self.assertEqual(self.db.row.status,'timeout')
        self.assertIsNone(self.db.row.execution_claim)
        self.assertEqual(self.notify.await_args.kwargs['result_type'], 'timeout')
        self.execute.assert_not_awaited()

    async def test_deadline_crossing_during_authorization_prevents_decision(self):
        original=self.approval._authorize_approval
        async def crossed(*args):
            result=await original(*args);self.db.row.live=False;return result
        with patch.object(self.approval,'_authorize_approval',crossed):
            with self.assertRaises(HTTPException):await self.decide()
        self.execute.assert_not_awaited()
        self.assertEqual(self.db.row.status,'pending')

    async def test_deadline_crossing_during_binding_prevents_claim(self):
        await self.ready()
        async def crossed(*args):self.db.row.live=False;return self.eid
        self.lifecycle.bind_execution.side_effect=crossed
        with self.assertRaises(HTTPException):await self.resume()
        self.execute.assert_not_awaited()
        self.assertIsNone(self.db.row.execution_claim)

    async def test_claim_is_committed_before_tool_and_repeat_is_readonly(self):
        await self.ready()
        async def checked(*args):
            self.assertEqual(self.db.saved_rows['a1'].status,'executing')
            self.assertIsNotNone(self.db.saved_rows['a1'].execution_claim)
            return await self.complete(*args)
        self.execute.side_effect=checked
        self.assertEqual((await self.resume()).status,'executed')
        owner=self.db.row.execution_claim
        self.assertEqual((await self.resume()).status,'executed')
        self.assertEqual(self.db.row.execution_claim,owner)
        self.execute.assert_awaited_once()
        self.assertEqual([e['new_status'] for e in self.db.events],['executing','executed'])

    async def test_overlapping_resumes_dispatch_only_once(self):
        await self.ready();entered=asyncio.Event();release=asyncio.Event()
        async def blocked(*args):
            entered.set();await release.wait();return await self.complete(*args)
        self.execute.side_effect=blocked
        first=asyncio.create_task(self.resume());await entered.wait()
        second=await self.resume()
        self.assertEqual(second.status,'executing')
        release.set();self.assertEqual((await first).status,'executed')
        self.execute.assert_awaited_once()

    async def test_claim_commit_ack_loss_never_invokes_tools(self):
        await self.ready();self.db.fail_commit=True
        with self.assertRaises(HTTPException):await self.resume()
        self.execute.assert_not_awaited();self.db.fail_commit=False
        self.assertEqual((await self.resume()).status,'executing')
        self.execute.assert_not_awaited()

    async def test_cancellation_retains_claim_without_replay(self):
        await self.ready();entered=asyncio.Event()
        async def blocked(*args):entered.set();await asyncio.Event().wait()
        self.execute.side_effect=blocked
        work=asyncio.create_task(self.resume());await entered.wait();work.cancel()
        with self.assertRaises(asyncio.CancelledError):await work
        self.assertEqual((await self.resume()).status,'executing')
        self.execute.assert_awaited_once()

    async def test_success_flag_without_receipt_is_unknown(self):
        await self.ready();self.execute.side_effect=None
        self.execute.return_value=Model(success=True,output={'message':'not evidence'})
        self.assertEqual((await self.resume()).status,'execution_unknown')
        self.assertEqual((await self.resume()).status,'execution_unknown')
        self.execute.assert_awaited_once()

    async def test_failed_unclaimed_operations_report_failed(self):
        await self.ready()
        async def failed(*args):
            self.db.operations=[{'state':'prepared'}]
            return Model(success=False,error='synthetic-secret')
        self.execute.side_effect=failed
        result=await self.resume()
        self.assertEqual(result.status,'execution_failed')
        self.assertNotIn('synthetic-secret',result.message)
        self.assertEqual(self.db.events[-1]['new_status'],'execution_failed')

    async def test_uncertain_dispatched_operation_is_unknown(self):
        await self.ready()
        async def failed(*args):
            self.db.operations=[{'state':'unknown'}]
            raise RuntimeError('synthetic-secret')
        self.execute.side_effect=failed
        self.assertEqual((await self.resume()).status,'execution_unknown')
        self.assertNotIn('synthetic-secret',str(self.db.events))

    async def test_saga_outcome_matrix_does_not_confuse_compensation_with_success(self):
        for saga,state in [('succeeded','executed'),('compensated','compensated'),
                           ('manual','compensation_failed'),('aborting','execution_unknown'),
                           ('forward','execution_unknown')]:
            with self.subTest(saga=saga):
                self.db.row.execution_id=self.eid;self.db.saga=Model(state=saga)
                self.assertEqual(await self.lifecycle.observe(self.db,self.db.row),state)

    async def test_finished_prepared_is_failure_but_crashed_prepared_is_unknown(self):
        self.db.row.execution_id=self.eid;self.db.operations=[{'state':'prepared'}]
        self.assertEqual(await self.lifecycle.observe(self.db,self.db.row),'execution_unknown')
        self.assertEqual(await self.lifecycle.observe(self.db,self.db.row,finished=True),'execution_failed')

    async def test_multiple_committed_actions_without_saga_are_not_certified(self):
        self.db.row.execution_id=self.eid;self.db.operations=[{'state':'committed'}]*2
        self.assertEqual(await self.lifecycle.observe(self.db,self.db.row),'execution_unknown')

    async def test_wrong_execution_claim_cannot_finalize(self):
        await self.ready();await self.resume()
        current=deepcopy(self.db.row);current.execution_claim=str(uuid.uuid4())
        self.assertEqual(await self.lifecycle.settle(self.db,current,'compensation_failed'),'executed')
        self.assertEqual(self.db.row.status,'executed')

    async def test_audit_failure_rolls_back_decision(self):
        self.db.fail_audit=True
        with self.assertRaises(HTTPException):await self.decide()
        self.assertEqual(self.db.row.status,'pending');self.assertEqual(self.db.events,[])
        self.notify.assert_not_awaited()

    async def test_audit_failure_before_claim_prevents_tool(self):
        await self.ready();self.db.fail_audit=True
        with self.assertRaises(HTTPException):await self.resume()
        self.execute.assert_not_awaited();self.assertIsNone(self.db.row.execution_claim)

    async def test_notification_failure_cannot_relabel_committed_outcome(self):
        self.notify.side_effect=RuntimeError('synthetic-secret')
        self.assertEqual((await self.decide()).status,'approved_pending_reauth')
        self.assertEqual(self.db.row.status,'approved_pending_reauth')
        self.assertNotIn('synthetic-secret',str(self.logger.mock_calls))

    async def test_empty_and_malformed_calls_never_claim(self):
        for calls in ([],None,[{}],[{'tool':'send_email_external','params':[]} ]):
            await self.ready();self.db.row.prefill_payload={'tool_calls':calls};await self.db.commit()
            with self.assertRaises(HTTPException):await self.resume()
            self.assertIsNone(self.db.row.execution_claim)
        self.execute.assert_not_awaited()

    async def test_duplicate_batch_id_rejected_before_sql(self):
        items=[Model(approval_id='a1',decision='approved')]*2
        with self.assertRaises(HTTPException):
            await self.approval.batch_decide_approvals(Model(approvals=items,comment=''),Model(user_id='approver'),self.db)
        self.assertEqual(self.db.queries,[])

    async def test_batch_rolls_back_earlier_accepted_member(self):
        second=deepcopy(self.db.row);second.approval_id='a2';second.approver_roles=['finance']
        self.db.rows['a2']=second;await self.db.commit()
        req=Model(approvals=[Model(approval_id=aid,decision='approved') for aid in ('a1','a2')],comment='')
        result=await self.approval.batch_decide_approvals(req,Model(user_id='approver'),self.db)
        self.assertEqual((result.succeeded,result.failed),(0,2))
        self.assertTrue(all(r.status=='pending' for r in self.db.rows.values()))
        self.assertEqual(self.db.events,[]);self.notify.assert_not_awaited()

    async def test_batch_locks_sorted_ids_and_commits_all_decisions(self):
        second=deepcopy(self.db.row);second.approval_id='a2';self.db.rows['a2']=second;await self.db.commit()
        req=Model(approvals=[Model(approval_id=aid,decision='approved') for aid in ('a2','a1')],comment='')
        result=await self.approval.batch_decide_approvals(req,Model(user_id='approver'),self.db)
        self.assertEqual((result.succeeded,result.failed),(2,0))
        ids=[p['id'] for q,p in self.db.queries if 'FROM approval_requests' in q]
        self.assertEqual(ids[:2],['a1','a2']);self.execute.assert_not_awaited()

    async def test_timeout_scanner_expires_approved_and_preserves_terminal(self):
        self.db.row.status='approved_pending_reauth';self.db.row.live=False;await self.db.commit()
        self.assertEqual(await self.timeout.scan_expired_approvals(),1)
        self.assertEqual(self.db.row.status,'timeout')
        self.assertEqual(await self.timeout.scan_expired_approvals(),0)
        self.execute.assert_not_awaited()

    async def test_scanner_recovers_saga_status_without_forward_execution(self):
        await self.ready();self.db.row.status='execution_unknown';self.db.row.execution_id=self.eid
        self.db.row.execution_claim=str(uuid.uuid4());self.db.saga=Model(state='compensated');await self.db.commit()
        self.assertEqual(await self.timeout.scan_expired_approvals(),1)
        self.assertEqual(self.db.row.status,'compensated');self.execute.assert_not_awaited()

    async def test_expired_execution_is_unknown_and_keeps_claim(self):
        await self.ready();self.db.row.status='executing';self.db.row.execution_id=self.eid
        owner=str(uuid.uuid4());self.db.row.execution_claim=owner;await self.db.commit()
        self.assertEqual(await self.timeout.scan_expired_approvals(),1)
        self.assertEqual(self.db.row.status,'execution_unknown');self.assertEqual(self.db.row.execution_claim,owner)
        self.assertEqual((await self.resume()).status,'execution_unknown');self.execute.assert_not_awaited()

    async def test_exact_plan_binding_owner_session_and_identity_matrix(self):
        oid='00000000-0000-4000-8000-000000000001'
        call=dict(tool='send_email_external',params={},target={'provider':'mock'},operation_id=oid)
        calls=[call];row=self.db.row
        record=dict(owner_id=row.requester_id,session_id=row.session_id,calls=calls,intent=call,execution_id=self.eid)
        backend=NS(load=AsyncMock(return_value=record))
        with patch.object(self.lifecycle,'OperationStore',return_value=backend):
            self.assertEqual(await self.original_bind(row,calls),self.eid)
            for field,value in [('owner_id','other'),('session_id','other'),('calls',[]),('intent',{})]:
                backend.load.return_value={**record,field:value}
                with self.subTest(field=field),self.assertRaises(self.operations.OperationError):
                    await self.original_bind(row,calls)

    async def test_notification_without_receipt_is_not_reported_delivered(self):
        notification=load('c11_notify','app/core/approval_notify.py')
        db=NS(execute=AsyncMock(return_value=NS(fetchone=lambda:NS(email='synthetic@company.internal'))))
        notification._send_internal_mail=AsyncMock(side_effect=RuntimeError('synthetic-secret'))
        await notification.notify_approval_result(db,'a1','requester','s1','execution_failed','safe')
        event=self.audit.log.await_args.kwargs
        self.assertFalse(event['success']);self.assertEqual(event['payload']['delivery'],'unavailable')
        self.assertNotIn('synthetic-secret',str(self.logger.mock_calls))

    async def test_notification_mock_receipt_is_not_real_delivery(self):
        notification=load('c11_notify','app/core/approval_notify.py')
        db=NS(execute=AsyncMock(return_value=NS(fetchone=lambda:NS(email='synthetic@company.internal'))))
        notification._send_internal_mail=AsyncMock(return_value='mock-message')
        await notification.notify_approval_result(db,'a1','requester','s1','executed','safe')
        event=self.audit.log.await_args.kwargs
        self.assertEqual(event['payload']['delivery'],'mock_recorded')
        self.assertEqual(event['payload']['channel'],'mock_internal_mail')

    async def test_unknown_provider_cannot_certify_success(self):
        await self.complete()
        self.db.row.execution_id = self.eid
        self.db.operations[0]['intent']['target']['provider'] = 'untrusted'
        self.assertEqual(await self.lifecycle.observe(self.db, self.db.row), 'execution_unknown')

    async def test_http_evidence_uses_actual_strict_receipt_validation(self):
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.tools.http_adapter': module('app.tools.http_adapter', call_external_api=AsyncMock())}))
        reference = load('c11_reference', 'app/tools/reference.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.tools.reference': reference}))
        await self.complete()
        self.db.row.execution_id = self.eid
        operation = self.db.operations[0]
        operation['intent'] = dict(tool='send_email_internal', target=dict(
            provider='http', run_id='synthetic', service='mail'))
        operation['request'] = {'body': {'to': ['employee@reference.invalid'], 'cc': []}}
        operation['receipt'] = dict(message_id='mail_1', receipt_state='captured', recipients=1,
            operation=dict(operation_id=operation['operation_id'], run_id='synthetic',
                service='mail', request_hash=self.operations.fingerprint(operation['request']),
                state='committed', compensates_operation_id=None, resource_id='mail_1',
                after_version=1, created_at='2026-10-17T00:00:00Z',
                completed_at='2026-10-17T00:00:00Z', effect='captured'))
        self.assertEqual(await self.lifecycle.observe(self.db, self.db.row), 'executed')
        operation['receipt']['operation']['request_hash'] = 'wrong'
        with self.assertRaises(self.operations.OperationError):
            await self.lifecycle.observe(self.db, self.db.row)

    async def test_expiry_commit_failure_returns_fixed_store_error(self):
        self.db.row.live = False
        await self.db.commit()
        self.db.fail_commit = True
        with self.assertRaises(HTTPException) as caught:
            await self.decide()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail, 'APPROVAL_STORE_UNAVAILABLE')
        self.execute.assert_not_awaited()

    async def test_conversation_status_labels_preserve_failure_and_unknown(self):
        tree = ast.parse((ROOT / 'app/tools/approval.py').read_text())
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == '_STATUS_LABELS'
                                  for t in n.targets))
        labels = ast.literal_eval(assignment.value)
        self.assertEqual(labels['executed'], '执行成功')
        for state in self.lifecycle.OUTCOMES | self.lifecycle.ACTIVE:
            self.assertIn(state, labels)
            if state != 'executed':
                self.assertNotEqual(labels[state], labels['executed'])

    async def test_scanner_sql_is_bounded_fair_and_never_reclaims(self):
        self.db.row.live=False;await self.db.commit();await self.timeout.scan_expired_approvals()
        sql=' '.join(q for q,p in self.db.queries)
        self.assertIn('LIMIT 100 FOR UPDATE SKIP LOCKED',sql)
        self.assertIn('ORDER BY execution_checked_at NULLS FIRST',sql)
        self.assertIn('execution_checked_at = clock_timestamp()',sql)
        self.assertNotIn('execution_claim = NULL',sql)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(ApprovalTests(name) for name in ApprovalTests.__dict__ if name.startswith('test_'))


if __name__=='__main__':
    sys.dont_write_bytecode=True
    def guard(event,args):
        if event=='socket.__new__' and args[1]==1:return
        if event.startswith(('socket.','subprocess.','ctypes.')) or event in {
            'os.remove','os.rmdir','os.rename','os.system','os.mkdir','os.chmod','os.chown',
            'os.truncate','os.utime','os.link','os.symlink','os.exec','os.posix_spawn',
            'os.fork','os.forkpty','os.putenv','os.unsetenv'}:raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event=='open' and (isinstance(args[1],str) and any(c in args[1] for c in 'wax+')
                             or isinstance(args[2],int) and args[2]&3):raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
