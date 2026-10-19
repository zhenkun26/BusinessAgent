"""C13 actual-source offline orchestration. SQL doubles do not validate PostgreSQL locking."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = runpy.run_path(str(ROOT / 'tests/test_tool_operation_safety.py'))
Base = BASE['SafetyFixture']


class RecoveryTests(Base):
    def setUp(self):
        super().setUp()
        self.store = self.saga_store.SagaStore()
        self.remote = {}
        self.fail_slot = None
        self.unknown_slot = None
        self.inverse_mode = 'valid'
        self.inverse_writes = []
        self.ref.request = AsyncMock(side_effect=self.provider)

    async def plan(self, names=('create_ticket', 'create_crm_task')):
        params = {'create_ticket': {'title': 'fixture'},
                  'create_crm_task': {'customer_id': 'C1', 'title': 'fixture'},
                  'update_ticket': {'ticket_id': 'T1', 'status': 'closed', 'comment': 'new'},
                  'send_email_internal': {'to': ['employee@reference.invalid'], 'subject': 'test', 'body': 'fixture'},
                  'send_email_external': {'to': ['customer@reference.invalid'], 'subject': 'test', 'body': 'fixture'}}
        plans = []
        for name in names:
            tool = type(self.tool)()
            tool.name = name
            tool.requires_approval = name == 'send_email_external'
            self.base.register_tool(tool)
            plans.append(NS(tool=name, params=params[name], operation_id=None))
        await self.gateway.prepare_calls(plans, self.context)
        coordinator = self.saga.SagaCoordinator(self.context)
        for index, plan in enumerate(plans):
            coordinator.add_step(str(index), plan.tool, plan.params, operation_id=plan.operation_id)
        return plans, coordinator

    async def attach(self, plans):
        definitions = [dict(step_id=str(i), tool=p.tool, params=p.params,
                            operation_id=p.operation_id, action=True, block_on_failure=True)
                       for i, p in enumerate(plans)]
        owner = str(uuid.uuid4())
        run, created = await self.store.prepare(definitions, self.context, owner)
        return str(run['saga_id']), owner, definitions

    def forward_receipt(self, oid):
        data = self.receipt(oid)
        row = self.db.operations[oid]
        name = row['intent']['tool']
        if name == 'update_ticket':
            data['operation']['before'].update(status='open', priority='normal', assignee=None,
                                               comments=[{'comment_id': 'old', 'text': 'retained'}])
            data['ticket']['priority'] = 'normal'
            data['ticket']['assignee'] = None
            data['ticket']['comments'].insert(0, {'comment_id': 'old', 'text': 'retained'})
        return data

    def rejection(self, row, inverse=False):
        req = row['request']
        return {'result': None, 'operation': dict(operation_id=str(row['operation_id']),
            run_id=row['intent']['target']['run_id'], service=row['intent']['target']['service'],
            request_hash=self.ops.fingerprint(req), state='rejected', resource_id=None,
            after_version=None, effect='none', error_code='VERSION_CONFLICT',
            compensates_operation_id=req['compensates_operation_id'] if inverse else None,
            created_at='2026-10-17T00:00:00Z', completed_at='2026-10-17T00:00:01Z')}

    def inverse_receipt(self, step):
        forward = self.db.operations[step['operation_id']]
        original = forward['receipt']['operation']
        name = forward['intent']['tool']
        effect = dict(create_crm_task='deleted', create_ticket='closed', update_ticket='restored',
                      send_email_internal='recalled', send_email_external='recall_requested')[name]
        op = {k: v for k, v in original.items() if k != 'before'}
        op.update(operation_id=step['compensation_id'], effect=effect,
                  request_hash=self.ops.fingerprint(step['compensation_request']),
                  compensates_operation_id=step['operation_id'], after_version=original['after_version']+1)
        if name.startswith('send_email'):
            return dict(message_id=op['resource_id'], receipt_state=effect, operation=op)
        kind, key = ('task', 'task_id') if name == 'create_crm_task' else ('ticket', 'ticket_id')
        obj = {key: op['resource_id'], 'version': op['after_version'], 'status': effect}
        if name == 'create_ticket':obj['closure_reason'] = 'saga_compensation'
        if name == 'update_ticket':
            before = original['before']
            obj.update({k: before[k] for k in ('status', 'priority', 'assignee')})
            comments = deepcopy(forward['receipt']['ticket']['comments'])
            for comment in comments:
                if comment['comment_id'] == 'C1':comment['superseded_by'] = step['compensation_id']
            comments.append({'comment_id': 'inverse-note', 'text': 'restored',
                             'compensates_operation_id': step['operation_id']})
            obj['comments'] = comments
        return {kind: obj, 'operation': op}

    async def provider(self, target, method, path, **kw):
        self.calls.append((method, path, deepcopy(kw)))
        if method == 'GET':
            if path.startswith('/tickets/'):
                return True, {'ticket': {'ticket_id': 'T1', 'version': 1}}, None, {'status': 200}
            oid = path.rsplit('/', 1)[1]
            if oid not in self.remote:return False, None, 'EXTERNAL_HTTP_404', {'status': 404}
            return True, deepcopy(self.remote[oid]), None, {'status': 200}
        oid = kw['operation_id']
        if kw.get('compensates_operation_id'):
            step = next(s for s in self.db.steps.values() if s['compensation_id'] == oid)
            self.assertEqual(step['compensation_state'], 'dispatched')
            self.assertEqual(step['compensation_request']['if_match'], kw['if_match'])
            self.assertEqual(step['operation_id'], kw['compensates_operation_id'])
            self.inverse_writes.append(step['slot'])
            data = self.inverse_receipt(step)
            self.remote[oid] = {'operation': data['operation'], 'result': data}
            if self.inverse_mode == 'rejected':
                row = dict(operation_id=oid, intent=self.db.operations[step['operation_id']]['intent'],
                           request=step['compensation_request'])
                self.remote[oid] = self.rejection(row, True)
                return False, None, 'EXTERNAL_HTTP_409', {'status': 409}
            if self.inverse_mode == 'unknown':
                self.remote.pop(oid)
                return False, None, 'EXTERNAL_TRANSPORT_UNCERTAIN', {}
            if self.inverse_mode == 'loss':return False, None, 'EXTERNAL_TRANSPORT_UNCERTAIN', {}
            if self.inverse_mode == 'invalid':data['operation']['request_hash'] = 'incorrect'
            return True, data, None, {'status': 202 if data['operation']['effect'] == 'recall_requested' else 200}
        self.send_count += 1
        row = self.db.operations[oid]
        if row['slot'] == self.unknown_slot:
            return False, None, 'EXTERNAL_HTTP_409', {'status': 409}
        if row['slot'] == self.fail_slot:
            self.remote[oid] = self.rejection(row)
            return False, None, 'EXTERNAL_HTTP_409', {'status': 409}
        data = self.forward_receipt(oid)
        self.remote[oid] = {'operation': data['operation'], 'result': data}
        return True, data, None, {'status': 200 if row['intent']['tool'] == 'update_ticket' else 201}

    async def test_whole_plan_job_and_inverse_ids_exist_before_first_write(self):
        plans, saga = await self.plan()
        original = self.provider
        async def checked(*args, **kw):
            self.assertEqual(len(self.db.runs), 1)
            self.assertEqual(len(self.db.steps), 2)
            self.assertEqual(len(self.db.jobs), 1)
            self.assertEqual(len({s['compensation_id'] for s in self.db.steps.values()}), 2)
            self.assertTrue(all(s['compensation_id'] not in self.db.operations for s in self.db.steps.values()))
            return await original(*args, **kw)
        self.ref.request.side_effect = checked
        result = await saga.execute()
        self.assertTrue(result.success)
        self.assertEqual(next(iter(self.db.jobs.values()))['state'], 'done')

    async def test_duplicate_plan_does_not_forward_again(self):
        _, saga = await self.plan()
        first = await saga.execute(); second = await saga.execute()
        self.assertTrue(first.success and second.success)
        self.assertEqual(first.saga_id, second.saga_id)
        self.assertEqual(self.send_count, 2)

    async def test_changed_order_owner_or_step_policy_is_rejected(self):
        plans, _ = await self.plan()
        sid, owner, definitions = await self.attach(plans)
        for mode in ('reverse', 'owner', 'policy'):
            changed = deepcopy(definitions); context = dict(self.context)
            if mode == 'reverse':changed.reverse()
            if mode == 'owner':context['user_id'] = 'other'
            if mode == 'policy':changed[0]['block_on_failure'] = False
            with self.subTest(mode=mode), self.assertRaises(self.ops.OperationError):
                await self.store.prepare(changed, context, str(uuid.uuid4()))
        self.ref.request.assert_not_awaited()

    async def test_duplicate_active_run_is_busy_not_success(self):
        plans, saga = await self.plan()
        sid, _, _ = await self.attach(plans)
        result = await saga.execute()
        self.assertFalse(result.success or result.compensated)
        self.assertEqual(result.state, 'forward')
        self.assertEqual(await self.recovery.retry_saga_compensations(sid), 'busy')
        self.ref.request.assert_not_awaited()

    async def test_attached_operation_cannot_bypass_saga_owner(self):
        plans, _ = await self.plan()
        sid, owner, _ = await self.attach(plans)
        tool = self.base.get_tool(plans[0].tool)
        result = await tool.invoke(plans[0].params, dict(self.context, operation_id=plans[0].operation_id))
        self.assertFalse(result.success)
        self.assertEqual(self.send_count, 0)
        self.db.clock += 121
        with self.ops.saga_dispatch(sid, owner):
            self.assertFalse((await tool.invoke(plans[0].params,
                             dict(self.context, operation_id=plans[0].operation_id))).success)
        self.assertEqual(self.send_count, 0)

    async def test_restart_cancels_prepared_forward_without_new_send(self):
        plans, _ = await self.plan()
        sid, _, _ = await self.attach(plans)
        self.db.clock += 121
        self.assertEqual(await self.recovery.retry_saga_compensations(sid), 'compensated')
        self.assertTrue(all(o['state'] == 'rejected' for o in self.db.operations.values()))
        self.ref.request.assert_not_awaited()

    async def test_reverse_compensation_and_no_downstream_forward(self):
        _, saga = await self.plan(('create_ticket', 'create_crm_task', 'create_ticket', 'create_crm_task'))
        self.fail_slot = 2
        result = await saga.execute()
        self.assertTrue(result.compensated)
        self.assertFalse(result.success)
        self.assertEqual(self.send_count, 3)
        self.assertEqual(self.inverse_writes, [1, 0])
        run = await self.store.load(result.saga_id)
        self.assertEqual(run['steps'][3]['result'], None)

    async def test_unknown_original_blocks_all_inverse_writes(self):
        _, saga = await self.plan()
        self.unknown_slot = 1
        result = await saga.execute()
        self.assertEqual(result.state, 'aborting')
        self.assertFalse(result.compensated)
        self.assertEqual(self.inverse_writes, [])
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id), 'aborting')
        self.assertEqual(self.send_count, 2)

    async def test_late_original_receipt_recovered_then_reverse_compensated(self):
        plans, saga = await self.plan()
        self.unknown_slot = 1
        result = await saga.execute()
        oid = plans[1].operation_id
        data = self.forward_receipt(oid)
        self.remote[oid] = {'operation': data['operation'], 'result': data}
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id), 'compensated')
        self.assertEqual(self.inverse_writes, [1, 0])
        self.assertEqual(self.send_count, 2)

    async def test_claim_before_send_gap_remains_unknown(self):
        plans, _ = await self.plan()
        sid, owner, _ = await self.attach(plans)
        oid = plans[0].operation_id
        store = self.ops.OperationStore()
        await store.freeze(oid, self.ref.wire(plans[0].tool, plans[0].params, 'test-user'))
        with self.ops.saga_dispatch(sid, owner):self.assertTrue(await store.claim(oid))
        self.db.clock += 121
        self.assertEqual(await self.recovery.retry_saga_compensations(sid), 'aborting')
        self.assertEqual(self.send_count, 0)
        self.assertEqual(self.inverse_writes, [])

    async def test_lost_inverse_response_uses_original_id_and_sends_once(self):
        _, saga = await self.plan()
        self.fail_slot = 1; self.inverse_mode = 'loss'
        result = await saga.execute()
        self.assertTrue(result.compensated)
        self.assertEqual(self.inverse_writes, [0])
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id), 'compensated')
        self.assertEqual(self.inverse_writes, [0])
        inverse = next(iter(self.db.steps.values()))
        self.assertTrue(any(path.endswith(inverse['compensation_id']) for m,path,k in self.calls if m=='GET'))

    async def test_unknown_inverse_never_rekeys_or_reposts(self):
        _, saga = await self.plan(('create_ticket', 'create_crm_task', 'create_ticket'))
        self.fail_slot = 2; self.inverse_mode = 'unknown'
        result = await saga.execute()
        self.assertFalse(result.compensated)
        self.assertEqual(self.inverse_writes, [1])
        before = deepcopy(list(self.db.steps.values()))
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id), 'aborting')
        self.assertEqual(self.inverse_writes, [1])
        self.assertEqual([s['compensation_id'] for s in before],
                         [s['compensation_id'] for s in self.db.steps.values()])

    async def test_late_inverse_receipt_continues_only_remaining_inverse(self):
        _, saga = await self.plan(('create_ticket', 'create_crm_task', 'create_ticket'))
        self.fail_slot = 2; self.inverse_mode = 'unknown'
        result = await saga.execute()
        step = self.db.steps[(result.saga_id, 1)]
        data = self.inverse_receipt(step)
        self.remote[step['compensation_id']] = {'operation': data['operation'], 'result': data}
        self.inverse_mode = 'valid'
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id), 'compensated')
        self.assertEqual(self.inverse_writes, [1, 0])

    async def test_rejected_inverse_stops_reverse_chain(self):
        _, saga = await self.plan(('create_ticket', 'create_crm_task', 'create_ticket'))
        self.fail_slot = 2; self.inverse_mode = 'rejected'
        result = await saga.execute()
        self.assertEqual(result.state, 'manual')
        self.assertFalse(result.compensated)
        self.assertEqual(self.inverse_writes, [1])
        self.assertEqual(next(iter(self.db.jobs.values()))['state'], 'dead')

    async def test_external_recall_request_is_not_compensated(self):
        _, saga = await self.plan(('send_email_external', 'create_ticket'))
        self.fail_slot = 1
        with self.ops.approved_calls(self.context['user_id'], 'approval', self.context['execution_calls']):
            self.context['approval_id'] = 'approval'
            result = await saga.execute()
        self.assertEqual(result.state, 'manual')
        self.assertFalse(result.compensated)
        self.assertTrue(any(path.endswith('/recall_requests') for m,path,k in self.calls))
        self.assertNotIn('approval_id', self.db.runs[result.saga_id]['context'])

    async def test_internal_recall_is_complete(self):
        _, saga = await self.plan(('send_email_internal', 'create_ticket'))
        self.fail_slot = 1
        result = await saga.execute()
        self.assertTrue(result.compensated)
        self.assertTrue(any(path.endswith('/recall') for m,path,k in self.calls))

    async def test_ticket_restore_uses_server_before_image_and_original_version(self):
        _, saga = await self.plan(('update_ticket', 'create_ticket'))
        self.fail_slot = 1
        result = await saga.execute()
        self.assertTrue(result.compensated)
        request = self.db.steps[(result.saga_id, 0)]['compensation_request']
        self.assertEqual(request['if_match'], '"2"')
        self.assertEqual(set(request['body']), {'restore_operation_id'})

    async def test_inverse_receipt_rejects_wrong_identity_link_version_hash_or_projection(self):
        _, saga = await self.plan()
        self.fail_slot = 1
        result = await saga.execute()
        step = self.db.steps[(result.saga_id,0)]
        forward = await self.ops.OperationStore().load(str(step['operation_id']))
        inverse = dict(operation_id=step['compensation_id'], request=step['compensation_request'])
        for field, value in [('operation_id',str(uuid.uuid4())), ('compensates_operation_id',str(uuid.uuid4())),
                             ('run_id',str(uuid.uuid4())), ('after_version',3), ('request_hash','wrong'),
                             ('service','mail'), ('effect','created'), ('resource_id','other')]:
            data = deepcopy(step['compensation_receipt']);data['operation'][field]=value
            with self.subTest(field=field),self.assertRaises(self.ops.OperationError):
                self.ref.inverse_receipt(data,inverse,forward)
        data=deepcopy(step['compensation_receipt']);data['ticket']['status']='open'
        with self.assertRaises(self.ops.OperationError):self.ref.inverse_receipt(data,inverse,forward)

    async def test_restore_cannot_discard_forward_comment(self):
        _, saga = await self.plan(('update_ticket','create_ticket'));self.fail_slot=1
        result=await saga.execute();step=self.db.steps[(result.saga_id,0)]
        forward=await self.ops.OperationStore().load(step['operation_id'])
        inverse=dict(operation_id=step['compensation_id'],request=step['compensation_request'])
        data=deepcopy(step['compensation_receipt'])
        data['ticket']['comments']=[c for c in data['ticket']['comments'] if c['comment_id']!='C1']
        with self.assertRaises(self.ops.OperationError):self.ref.inverse_receipt(data,inverse,forward)

    async def test_missing_before_image_stops_without_inverse(self):
        plans,saga=await self.plan(('update_ticket','create_ticket'));self.unknown_slot=1
        result=await saga.execute();self.db.operations[plans[0].operation_id]['receipt']['operation']['before'].pop('status')
        row=self.db.operations[plans[1].operation_id];self.remote[plans[1].operation_id]=self.rejection(row)
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id),'manual')
        self.assertEqual(self.inverse_writes,[])

    async def test_current_authority_revocation_blocks_inverse(self):
        plans,saga=await self.plan();self.unknown_slot=1
        result=await saga.execute()
        row=self.db.operations[plans[1].operation_id];self.remote[plans[1].operation_id]=self.rejection(row)
        self.user.role='finance'
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id),'manual')
        self.assertEqual(self.inverse_writes,[])

    async def test_changed_target_blocks_inverse(self):
        plans,saga=await self.plan();self.unknown_slot=1
        result=await saga.execute()
        row=self.db.operations[plans[1].operation_id];self.remote[plans[1].operation_id]=self.rejection(row)
        self.settings.tool_reference_run_id=str(uuid.uuid4())
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id),'manual')
        self.assertEqual(self.inverse_writes,[])

    async def test_stale_owner_cannot_record_finish_or_claim_inverse(self):
        plans,_=await self.plan();sid,owner,_=await self.attach(plans)
        self.db.clock+=121;new=str(uuid.uuid4());self.assertTrue(await self.store.acquire(sid,new))
        for call in (lambda:self.store.record(sid,owner,0,{}),
                     lambda:self.store.finish(sid,owner,'succeeded'),
                     lambda:self.store.inverse_claim(sid,owner,0,{})):
            with self.assertRaisesRegex(self.ops.OperationError,'OWNERSHIP_LOST'):await call()
        self.assertEqual(self.db.runs[sid]['owner_token'],new)

    async def test_legacy_or_missing_journal_never_runs_actions(self):
        for sid in ('legacy-id',str(uuid.uuid4())):
            with self.assertRaises(self.ops.OperationError):await self.recovery.retry_saga_compensations(sid)
        self.ref.request.assert_not_awaited()

    async def test_incomplete_or_changed_journal_cannot_report_compensated(self):
        plans,_=await self.plan();sid,_,_=await self.attach(plans)
        original=deepcopy(self.db.steps)
        for corruption in ('missing','changed','slot'):
            self.db.steps=deepcopy(original)
            if corruption=='missing':self.db.steps.pop((sid,0))
            if corruption=='changed':self.db.steps[(sid,0)]['definition']['params']['title']='changed'
            if corruption=='slot':self.db.steps[(sid,0)]['slot']=99
            self.db.clock+=121
            with self.subTest(corruption=corruption),self.assertRaisesRegex(self.ops.OperationError,'JOURNAL_INVALID'):
                await self.recovery.retry_saga_compensations(sid)
        self.ref.request.assert_not_awaited()

    async def test_sensitive_context_is_not_persisted(self):
        self.context.update(token='synthetic-private', authorization='synthetic-private')
        plans,_=await self.plan();sid,_,_=await self.attach(plans)
        self.assertEqual(set(self.db.runs[sid]['context']),{'user_id','role','session_id'})
        self.assertNotIn('synthetic-private',str(self.db.runs))
        self.assertNotIn('synthetic-private',str(self.db.jobs))

    async def test_mock_restart_does_not_invent_compensation_success(self):
        self.settings.tool_provider='mock'
        plans,_=await self.plan();sid,owner,_=await self.attach(plans)
        with self.ops.saga_dispatch(sid,owner):
            self.assertTrue((await self.base.get_tool(plans[0].tool).invoke(plans[0].params,
                dict(self.context,operation_id=plans[0].operation_id))).success)
        self.db.clock+=121
        self.assertEqual(await self.recovery.retry_saga_compensations(sid),'manual')
        self.assertEqual(self.inverse_writes,[])

    async def test_inverse_header_transport_uses_link_and_no_retry(self):
        calls=self.install_transport([(200,[b'{}'])])
        self.ref.request=self.real_request
        oid,cid=str(uuid.uuid4()),str(uuid.uuid4())
        config=self.ref.target(self.tool,self.settings)
        await self.ref.request(config,'PATCH','/tickets/T1',body={'status':'closed'},
                               operation_id=cid,if_match='"1"',compensates_operation_id=oid)
        self.assertEqual(len(calls),1)
        headers=calls[0][1]['headers']
        self.assertEqual(headers['X-Compensates-Operation'],oid)
        self.assertEqual(headers['Idempotency-Key'],'ba-ref-v1:'+cid)
        self.assertEqual(headers['If-Match'],'"1"')

    async def test_sql_guards_and_atomic_producer_share_transaction(self):
        plans,_=await self.plan();sid,owner,_=await self.attach(plans)
        sql='\n'.join(q for q,a in self.db.sql)
        self.assertIn('FOR UPDATE OF e',sql)
        self.assertIn('INSERT INTO saga_runs',sql)
        self.assertIn('INSERT INTO task_jobs',sql)
        await self.store.abort(sid,owner)
        self.assertEqual(self.db.runs[sid]['state'],'aborting')
        self.assertTrue(all(o['state']=='rejected' for o in self.db.operations.values()))

    async def test_journal_commit_failure_never_starts_forward_io(self):
        _,saga=await self.plan()
        original=self.db.commit
        async def fail():raise RuntimeError('synthetic-secret')
        self.db.commit=fail
        result=await saga.execute()
        self.assertFalse(result.success or result.compensated)
        self.assertEqual(result.error,'SAGA_RECOVERY_REQUIRED')
        self.assertEqual(self.send_count,0)
        self.db.commit=original

    async def test_lost_inverse_commit_ack_recovery_does_not_resend(self):
        _,saga=await self.plan();self.fail_slot=1
        original=self.saga_store.SagaStore.inverse_finish
        async def lost(store,*args):
            await original(store,*args)
            raise self.ops.OperationError('SAGA_STORE_UNAVAILABLE')
        with patch.object(self.saga_store.SagaStore,'inverse_finish',lost):
            result=await saga.execute()
        self.assertFalse(result.compensated)
        self.assertEqual(self.inverse_writes,[0])
        self.db.clock+=121
        self.assertEqual(await self.recovery.retry_saga_compensations(result.saga_id),'compensated')
        self.assertEqual(self.inverse_writes,[0])

    async def test_inverse_claim_before_send_crash_never_sends_on_recovery(self):
        plans,_=await self.plan();sid,owner,_=await self.attach(plans)
        oid=plans[0].operation_id
        with self.ops.saga_dispatch(sid,owner):
            await self.base.get_tool(plans[0].tool).invoke(plans[0].params,dict(self.context,operation_id=oid))
        await self.store.abort(sid,owner)
        row=await self.ops.OperationStore().load(oid)
        frozen=self.ref.inverse_wire(row)
        self.assertTrue(await self.store.inverse_claim(sid,owner,0,frozen))
        self.db.clock+=121
        self.assertEqual(await self.recovery.retry_saga_compensations(sid),'aborting')
        self.assertEqual(self.inverse_writes,[])
        self.assertEqual(self.send_count,1)

    async def test_rejected_receipt_requires_complete_bound_evidence(self):
        plans,_=await self.plan();oid=plans[0].operation_id
        store=self.ops.OperationStore()
        await store.freeze(oid,self.ref.wire(plans[0].tool,plans[0].params,'test-user'))
        row=await store.load(oid);data=self.rejection(row)
        self.assertTrue(self.ref.rejected(data,row))
        for field,value in [('request_hash','wrong'),('resource_id','R1'),('after_version',1),
                            ('operation_id',str(uuid.uuid4())),('effect','created'),('error_code','raw-secret')]:
            changed=deepcopy(data);changed['operation'][field]=value
            with self.subTest(field=field),self.assertRaises(self.ops.OperationError):self.ref.rejected(changed,row)

    async def test_cancellation_retains_job_and_stops_downstream(self):
        _,saga=await self.plan()
        entered=asyncio.Event()
        async def hanging(*a,**kw):
            entered.set()
            await asyncio.Event().wait()
        self.ref.request.side_effect=hanging
        work=asyncio.create_task(saga.execute())
        await entered.wait();work.cancel()
        with self.assertRaises(asyncio.CancelledError):await work
        self.assertEqual(len(self.db.jobs),1)
        self.assertEqual([r['state'] for r in self.db.operations.values()],['dispatched','prepared'])
        self.assertEqual(next(iter(self.db.runs.values()))['state'],'forward')


def load_tests(loader, tests, pattern):
    # Do not count inherited C12 tests twice; that suite runs independently.
    return unittest.TestSuite(RecoveryTests(name) for name in RecoveryTests.__dict__ if name.startswith('test_'))


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
