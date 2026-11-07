"""Real handlers with transaction doubles. No PostgreSQL/provider acceptance claimed."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app.api import approval
try:
    from app.core import approval_deadline as deadline
except ImportError:
    deadline = None  # Identical handler controls can run on the unfixed baseline.
NOW = datetime(2026, 11, 1, 12)

class Result:
    def __init__(self, rows=()): self.rows = list(rows)
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return self.rows

class Store:
    def __init__(self, rows):
        self.rows = {r.approval_id: deepcopy(r) for r in rows}
        self.users = {x.user_id: x for x in [
            NS(user_id='owner', role='salesperson', department='sales', is_active=True),
            NS(user_id='manager', role='manager', department='sales', is_active=True)]}
        self.now = NOW
        self.locks = {uid: asyncio.Lock() for uid in self.users}

class Session:
    def __init__(self, store, fail=None):
        self.store, self.fail = store, fail
        self.pending, self.held, self.sql = {}, [], []
        self.commits = 0
    async def execute(self, query, params=None):
        sql, p = str(query), params or {}; self.sql.append((sql, p))
        if 'FROM users' in sql:
            uid = p['uid']
            if 'FOR UPDATE' in sql and uid not in self.held:
                await self.store.locks[uid].acquire(); self.held.append(uid)
            return Result([deepcopy(self.store.users[uid])]) if uid in self.store.users else Result()
        if 'AS approval_now' in sql: return Result([NS(approval_now=self.store.now)])
        if sql.startswith('SELECT') and 'FROM approval_requests' in sql:
            rows = deepcopy(list({**self.store.rows, **self.pending}.values()))
            for r in rows: r.live = r.expires_at > self.store.now
            if 'id' in p: rows = [r for r in rows if r.approval_id == p['id']]
            if 'uid' in p:
                rows = [r for r in rows if r.requester_id == p['uid']
                        and r.status not in {'executed', 'rejected', 'timeout'}
                        and (r.status is not None or 'status IS NULL' in sql)]
            return Result(deepcopy(rows))
        if sql.startswith('UPDATE approval_requests'):
            row = deepcopy(self.pending.get(p['id'], self.store.rows[p['id']]))
            if "SET status = 'executing'" in sql:
                if row.status != 'approved_pending_reauth' or row.expires_at <= self.store.now or row.execution_claim: return Result()
                row.status='executing'; row.execution_id=p['eid']; row.execution_claim=p['claim']
                row.execution_deadline=NOW+timedelta(minutes=5)
                self.pending[row.approval_id]=row
                return Result([row])
            if 'execution_claim = :claim' in sql and (row.status != 'executing' or str(row.execution_claim) != p['claim']): return Result()
            if 'old' in p and (row.status != p['old'] or row.expires_at <= self.store.now): return Result()
            state = p.get('state', p.get('status'))
            if state is None:
                state = next((s for s in ['executed', 'rejected', 'approved_pending_reauth']
                              if "status = '" + s + "'" in sql), row.status)
            if 'snapshot' in p and row.status != 'executing': return Result()
            import json
            if ('prefill_payload = CAST(:snapshot AS JSONB)' in sql
                    and row.prefill_payload != json.loads(p['snapshot'])):
                return Result()
            if ('approval_contract = CAST(:contract AS JSONB)' in sql
                    and row.approval_contract != json.loads(p['contract'])):
                return Result()
            if state == 'executed' and self.fail == 'outcome-update':
                self.fail = None; raise RuntimeError('synthetic outcome persistence failure')
            row.status = state
            row.approver_id = p.get('actor', p.get('approver', row.approver_id))
            self.pending[row.approval_id] = row
            return Result([NS(approval_id=row.approval_id)])
        return Result()
    async def commit(self):
        self.commits += 1
        if self.fail == 'claim-before':
            self.fail = None; raise RuntimeError('synthetic unconfirmed commit')
        self.store.rows.update(self.pending); self.pending = {}; self.release()
        if self.fail == 'claim-after':
            self.fail = None; raise RuntimeError('synthetic lost commit acknowledgment')
    def release(self):
        for uid in self.held: self.store.locks[uid].release()
        self.held = []
    async def rollback(self): self.pending = {}; self.release()

@pytest.fixture
def setup(monkeypatch):
    if deadline:
        monkeypatch.setattr(deadline, 'targets_for', lambda calls: [
            {'tool': c['tool'], 'provider': 'mock', 'endpoint': ''} for c in calls])
    monkeypatch.setattr(approval, 'notify_approval_result', AsyncMock())
    monkeypatch.setattr(approval, 'decode_identity_token', lambda _: {'sub':'owner'})
    monkeypatch.setattr(approval.lifecycle, 'bind_execution', AsyncMock(return_value='00000000-0000-4000-8000-000000000002'))
    monkeypatch.setattr(approval.lifecycle, 'observe', AsyncMock(return_value='executed'))
    effect = AsyncMock(return_value=(True, 'synthetic only', 'salesperson'))
    monkeypatch.setattr(approval, '_execute_approval_tools', effect)
    return effect

def record(route='decide', expired=False, trusted=True, aid='approval-one'):
    created = NOW - timedelta(hours=48 if expired else 1)
    r = NS(approval_id=aid, session_id='session-one', requester_id='owner',
        status='approved_pending_reauth' if route == 'resume' else 'pending',
        approver_id='manager' if route == 'resume' else None,
        approver_roles=['manager', 'admin'], operation_type='send_email_external',
        risk_level='high', summary='synthetic only', requester_token='synthetic-token',
        execution_id=None, execution_claim=None, execution_deadline=None, execution_error=None,
        created_at=created, expires_at=created + timedelta(hours=24),
        prefill_payload={'tool_calls': [{'tool': 'send_email_external', 'params': {
            'to': ['recipient@example.invalid'], 'subject': 'Synthetic', 'body': 'Never sent'},
            'operation_id': '00000000-0000-4000-8000-000000000001',
            'reason': 'synthetic regression'}]})
    if trusted:
        r.approval_contract = (deadline.build_contract(r) if deadline else
            {'version': 'utc-human-v2'})
    else:
        r.approval_contract = None
    return r

async def invoke(route, db, aid='approval-one'):
    if route == 'decide':
        return await approval.decide_approval(aid,
            approval.ApprovalDecisionRequest(decision='approved'),
            approver=NS(user_id='manager', role='manager'), db=db)
    if route == 'resume':
        return await approval.resume_pending_execution(aid,
            requester=NS(user_id='owner', role='salesperson'),
            credentials=NS(scheme='Bearer', credentials='synthetic-token'), db=db)
    return await approval.batch_decide_approvals(approval.BatchApprovalRequest(
        approvals=[{'approval_id': aid, 'decision': 'approved'}]),
        approver=NS(user_id='manager', role='manager'), db=db)

async def attempt(route, db, aid='approval-one'):
    try: return await invoke(route, db, aid)
    except (HTTPException, RuntimeError): return None

@pytest.mark.asyncio
@pytest.mark.parametrize('route', ['decide', 'resume', 'batch'])
@pytest.mark.parametrize('expired', [True, False], ids=['expired', 'live-control'])
async def test_expired_approval_cannot_dispatch(route, expired, setup):
    await attempt(route, Session(Store([record(route, expired)])))
    assert setup.await_count == (1 if not expired and route == 'resume' else 0)

@pytest.mark.asyncio
@pytest.mark.parametrize('route', ['decide', 'resume', 'batch'])
async def test_persist_failure_cannot_dispatch_again(route, setup):
    store = Store([record(route)])
    if route != 'resume': await attempt(route, Session(store))
    await attempt('resume', Session(store, fail='outcome-update'))
    assert setup.await_count == 1
    await attempt(route, Session(store))
    assert setup.await_count == 1
    assert store.rows['approval-one'].status in {'executing', 'execution_unknown'}

@pytest.mark.asyncio
@pytest.mark.parametrize('route', ['decide', 'resume', 'batch'])
@pytest.mark.parametrize('damage', ['legacy', 'malformed', 'version', 'plan', 'roles', 'time', 'id'])
async def test_untrusted_approval_held_unchanged(route, damage, setup):
    r = record(route)
    if damage == 'legacy': r.approval_contract = None
    elif damage == 'malformed': r.approval_contract = {'version': deadline.VERSION}
    elif damage == 'version': r.approval_contract['version'] = 'utc-pretend'
    elif damage == 'plan': r.prefill_payload['tool_calls'][0]['params']['to'] = ['changed@example.invalid']
    elif damage == 'roles': r.approver_roles = ['salesperson']
    elif damage == 'time': r.expires_at += timedelta(hours=1)
    elif damage == 'id': r.session_id = 'copied-session'
    store = Store([r]); before = deepcopy(store.rows)
    await attempt(route, Session(store))
    assert setup.await_count == 0 and store.rows == before

@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['claim-before', 'claim-after'])
async def test_uncertain_claim_commit_never_dispatches(failure, setup):
    store = Store([record('resume')]); await attempt('resume', Session(store, fail=failure))
    assert setup.await_count == 0
    if failure == 'claim-after':
        await attempt('resume', Session(store))
        assert setup.await_count == 0 and store.rows['approval-one'].status == 'executing'

@pytest.mark.asyncio
async def test_two_concurrent_requests_dispatch_once_in_transaction_double(setup):
    store = Store([record('resume')])
    await asyncio.gather(attempt('resume', Session(store)), attempt('resume', Session(store)))
    assert setup.await_count == 1

@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['pending', 'executing', 'execution_unknown', 'approved', None])
async def test_owner_hold_blocks_other_trusted_approval(state, setup):
    held = record(trusted=False, aid='legacy'); held.status = state
    store = Store([held, record()]); before = deepcopy(store.rows)
    await attempt('decide', Session(store))
    assert setup.await_count == 0 and store.rows == before

@pytest.mark.asyncio
async def test_expiry_during_binding_prevents_claim(monkeypatch, setup):
    store = Store([record('resume')])
    async def bind(*args):
        store.now = store.rows['approval-one'].expires_at
        return '00000000-0000-4000-8000-000000000002'
    monkeypatch.setattr(approval.lifecycle, 'bind_execution', bind)
    await attempt('resume', Session(store))
    assert setup.await_count == 0 and store.rows['approval-one'].status == 'approved_pending_reauth'

@pytest.mark.asyncio
async def test_failed_tool_and_cancellation_retain_hold(setup):
    for error in [RuntimeError('uncertain'), asyncio.CancelledError()]:
        store = Store([record('resume')]); setup.reset_mock(); setup.side_effect = error
        try: await attempt('resume', Session(store))
        except asyncio.CancelledError: pass
        assert store.rows['approval-one'].status in {'executing', 'execution_unknown'}
        await attempt('decide', Session(store)); assert setup.await_count == 1

@pytest.mark.parametrize('forged', [None, {}, {'version': 'utc-human-v2'}, {'version': 'utc-human-v1'}])
def test_payload_marker_cannot_upgrade_legacy_contract(forged, setup):
    r = record(trusted=False)
    r.prefill_payload['deadline_contract'] = forged
    r.prefill_payload['approval_contract'] = deadline.build_contract(r)
    before = deepcopy(r)
    assert not deadline.verified(r) and r == before


def test_contract_snapshot_detached_from_plan_and_identity(setup):
    r = record(); snapshot = deepcopy(r.approval_contract)
    r.prefill_payload['tool_calls'][0]['params']['body'] = 'mutated plan'
    assert r.approval_contract == snapshot and not deadline.verified(r)
    clone = record(aid='another-approval'); clone.approval_contract = snapshot
    assert not deadline.verified(clone)

@pytest.mark.asyncio
async def test_writer_uses_db_clock_and_cannot_clone_old_hold(monkeypatch, setup):
    from app.agents.execution import ExecutionAgent, ToolCallPlan
    from app.core import database
    from app.agents import execution
    store = Store([]); db = Session(store); captured = []
    original = db.execute
    async def execute(query, params=None):
        if str(query).startswith('INSERT INTO approval_requests'):
            captured.append(params.copy())
        return await original(query, params)
    db.execute = execute
    class Factory:
        def __call__(self): return self
        async def __aenter__(self): return db
        async def __aexit__(self, *args): await db.rollback()
    monkeypatch.setattr(database, 'get_session_factory', lambda: Factory())
    monkeypatch.setattr(execution, 'get_audit_logger', lambda: NS(log=AsyncMock()))
    plan = ToolCallPlan(tool='send_email_external', params={
        'to': ['recipient@example.invalid'], 'subject': 'synthetic', 'body': 'not sent'})
    from app.tools import operation_gateway
    async def prepare(plans, context, **kwargs):
        context['execution_calls'] = [{'tool':p.tool,'params':p.params,
            'operation_id':'00000000-0000-4000-8000-000000000001'} for p in plans]
    monkeypatch.setattr(operation_gateway, 'prepare_calls', prepare)
    execution._ensure_tools()
    agent = object.__new__(ExecutionAgent)
    context = {'user_id': 'owner', 'session_id': 'session-one',
               'deadline_contract': {'version': 'client-forged'},
               'approval_contract': {'version': 'client-forged'}}
    await agent._create_approval_request([plan], context, 'synthetic')
    assert len(captured) == 1
    p = captured[0]
    assert p['created'] == NOW and p['expires'] - p['created'] == timedelta(hours=24)
    import json
    row = NS(approval_id=p['aid'], session_id=p['sid'], requester_id=p['uid'],
        operation_type=p['op'], risk_level=p['risk'], approver_roles=json.loads(p['roles']),
        created_at=p['created'], expires_at=p['expires'], prefill_payload=json.loads(p['payload']),
        approval_contract=json.loads(p['contract']))
    assert 'approval_contract' not in row.prefill_payload
    assert 'deadline_contract' not in row.prefill_payload
    assert deadline.verified(row)
    store.rows['legacy'] = record(trusted=False, aid='legacy')
    with pytest.raises(HTTPException):
        await agent._create_approval_request([plan], context, 'different query cannot clear hold')
    assert len(captured) == 1

@pytest.mark.asyncio
async def test_scanner_progresses_past_100_untrusted_rows(monkeypatch, setup):
    from app.core import approval_timeout, database
    rows = [record(expired=True, trusted=False, aid=f'a{i:03}') for i in range(101)]
    rows.append(record(expired=True, aid='z-signed'))
    rows.append(record(expired=True, aid='z-claimed')); rows[-1].status = 'executing'
    store = Store(rows); original = deepcopy(store.rows); db = Session(store)
    execute = db.execute
    async def paged(query, params=None):
        sql, p = str(query), params or {}
        if sql.startswith('SELECT') and 'SKIP LOCKED' in sql and 'cursor' not in p:
            return Result()
        if sql.startswith('SELECT') and 'SKIP LOCKED' in sql:
            selected = sorted((r for r in store.rows.values()
                if r.approval_id > p['cursor'] and r.status in {'pending','approved_pending_reauth'}
                and r.expires_at <= store.now), key=lambda r:r.approval_id)[:100]
            return Result(deepcopy(selected))
        if sql.startswith('UPDATE approval_requests') and "status = 'timeout'" in sql:
            db.pending[p['id']] = deepcopy(store.rows[p['id']]); db.pending[p['id']].status = 'timeout'
            return Result([NS(approval_id=p['id'])])
        return await execute(query, params)
    db.execute = paged
    class Factory:
        def __call__(self): return self
        async def __aenter__(self): return db
        async def __aexit__(self,*args): await db.rollback()
    monkeypatch.setattr(database, 'get_session_factory', lambda: Factory())
    monkeypatch.setattr(approval_timeout,'notify_approval_result',AsyncMock())
    assert await approval_timeout.scan_expired_approvals() == 1
    assert store.rows['z-signed'].status == 'timeout'
    assert all(store.rows[k] == v for k,v in original.items() if k!='z-signed')
    assert await approval_timeout.scan_expired_approvals() == 0

@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['timeout','status500','network','redirect'])
async def test_approval_scope_never_retries_mutations(monkeypatch, failure):
    import httpx
    from app.tools import http_adapter
    attempts = []
    def transport(request):
        attempts.append(request)
        if failure == 'timeout': raise httpx.ReadTimeout('synthetic')
        if failure == 'network': raise httpx.ReadError('synthetic')
        if failure == 'redirect': return httpx.Response(302, json={'message_id': 'not-a-receipt'})
        return httpx.Response(500)
    client = httpx.AsyncClient
    monkeypatch.setattr(http_adapter.httpx,'AsyncClient', lambda **kw:
        client(transport=httpx.MockTransport(transport),**kw))
    with deadline.dispatch_scope():
        ok,_,_ = await http_adapter.call_external_api('POST','https://service.example.invalid/action',max_retries=9)
    assert not ok and len(attempts)==1
    assert not deadline.in_approval_dispatch()

@pytest.mark.asyncio
async def test_approval_uses_durable_fail_stop_coordinator(monkeypatch):
    from app.agents import execution
    from app.tools import operation_gateway
    from app.tools.base import ToolResult
    monkeypatch.setattr(execution,'_ensure_tools',lambda:None)
    prepare=AsyncMock()
    monkeypatch.setattr(operation_gateway,'prepare_calls',prepare)
    saga=AsyncMock(return_value=ToolResult(False,'synthetic',{}))
    monkeypatch.setattr(execution,'_invoke_saga',saga)
    plans=[execution.ToolCallPlan(tool=f'synthetic-{i}',params={}) for i in range(3)]
    result=await execution.execute_tool_calls(plans,{})
    assert not result.success
    prepare.assert_awaited_once(); saga.assert_awaited_once()

@pytest.mark.asyncio
async def test_model_context_cannot_approve_external_mail(monkeypatch):
    from app.tools.mail import SendEmailExternalTool
    tool=SendEmailExternalTool(); effect=AsyncMock()
    monkeypatch.setattr(tool,'_execute',effect)
    result=await tool.invoke({'to':['recipient@example.invalid'],'subject':'test','body':'test'},
        {'role':'admin','triggered_by':'approval','admin':True,'approval_id':'claimed-by-model'})
    assert not result.success and result.error=='APPROVAL_COMMITTED_CLAIM_REQUIRED'
    effect.assert_not_awaited()

@pytest.mark.asyncio
async def test_batch_decides_only_and_never_dispatches(setup):
    store=Store([record(),record(aid='approval-two')])
    setup.return_value=(False,'unknown','salesperson')
    req=approval.BatchApprovalRequest(approvals=[{'approval_id':a,'decision':'approved'}
        for a in ['approval-one','approval-two']])
    result=await approval.batch_decide_approvals(req,NS(user_id='manager',role='manager'),Session(store))
    assert setup.await_count==0
    assert result.succeeded==2
    assert all(r.status=='approved_pending_reauth' for r in store.rows.values())

@pytest.mark.asyncio
@pytest.mark.parametrize('identity',['owner','manager'])
async def test_disabled_current_participant_cannot_dispatch(identity,setup):
    store=Store([record()]); store.users[identity].is_active=False
    await attempt('decide',Session(store)); assert setup.await_count==0

@pytest.mark.asyncio
async def test_direct_action_prepares_before_gateway_without_cross_transaction_lock(monkeypatch,setup):
    from app.agents import execution
    from app.core import database
    from app.tools.base import ToolResult
    store=Store([]); db=Session(store)
    class Factory:
        def __call__(self): return self
        async def __aenter__(self): return db
        async def __aexit__(self,*args): await db.rollback()
    monkeypatch.setattr(database,'get_session_factory',lambda:Factory())
    monkeypatch.setattr(execution,'_ensure_tools',lambda:None)
    monkeypatch.setattr(execution,'get_tool',lambda name:NS(category=NS(value='action')))
    async def effect(*args):
        assert not store.locks['owner'].locked()
        prepared.assert_awaited_once()
        return ToolResult(success=True,tool_name='synthetic',output={})
    monkeypatch.setattr(execution,'_invoke_single',effect)
    from app.tools import operation_gateway
    prepared=AsyncMock()
    monkeypatch.setattr(operation_gateway,'prepare_calls',prepared)
    await execution.execute_tool_calls([execution.ToolCallPlan(tool='synthetic',params={})],{'user_id':'owner'})
    assert not store.locks['owner'].locked()

@pytest.mark.parametrize('change', ['none', 'endpoint', 'provider', 'override'])
def test_actual_target_binding_detects_configuration_drift(monkeypatch, change):
    from app import config
    from app.agents import execution
    from app.tools import base
    from app.tools.mail import SendEmailExternalTool
    settings = NS(mail_tool_provider='http',
                  tool_provider='mock', mail_api_base='https://mail.example.invalid')
    monkeypatch.setattr(deadline, 'get_settings', lambda: settings)
    monkeypatch.setattr(config, 'get_settings', lambda: settings)
    monkeypatch.setattr(execution, '_ensure_tools', lambda: None)
    tool = SendEmailExternalTool()
    monkeypatch.setattr(base, 'get_tool', lambda name: tool)
    row = record()
    assert deadline.verified(row)
    if change == 'endpoint': settings.mail_api_base += '/other'
    if change == 'provider': settings.mail_tool_provider = 'mock'
    if change == 'override': tool.provider_override = 'mock'
    assert deadline.verified(row) is (change == 'none')

@pytest.mark.asyncio
@pytest.mark.parametrize('receipt', [None, '', ' ', 123, 'synthetic-message-id'])
async def test_approved_mail_requires_positive_receipt(monkeypatch, receipt):
    from app.tools import mail
    effect = AsyncMock()
    monkeypatch.setattr(mail.SendEmailExternalTool, '_execute', effect)
    # A generic message_id, even a nonempty one, cannot substitute for a durable
    # operation receipt and server-issued committed approval capability.
    result = await mail.SendEmailExternalTool().invoke(
        {'to':['recipient@example.invalid'],'subject':'test','body':'test'},
        {'role':'salesperson','receipt':{'message_id':receipt}})
    assert not result.success and result.error == 'APPROVAL_COMMITTED_CLAIM_REQUIRED'
    effect.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['requester_id', 'approver_id', 'payload', 'contract'])
async def test_resume_rechecks_identity_and_contract_after_relocking(field, setup):
    store = Store([record('resume')]); db = Session(store)
    execute = db.execute
    changed = False
    async def change_during_lock(query, params=None):
        nonlocal changed
        result = await execute(query, params)
        if 'FROM users' in str(query) and not changed:
            changed = True
            row = store.rows['approval-one']
            if field == 'payload': row.prefill_payload['tool_calls'][0]['params']['body'] = 'changed'
            elif field == 'contract': row.approval_contract = {'version':'forged'}
            else: setattr(row, field, 'another-person')
        return result
    db.execute = change_during_lock
    await attempt('resume', db)
    setup.assert_not_awaited()
    assert store.rows['approval-one'].status == 'approved_pending_reauth'

@pytest.mark.asyncio
async def test_batch_stops_after_result_persistence_503(setup):
    store = Store([record(), record(aid='approval-two')])
    request = approval.BatchApprovalRequest(approvals=[{'approval_id': aid, 'decision':'approved'}
        for aid in ['approval-one', 'approval-two']])
    with pytest.raises(HTTPException) as caught:
        await approval.batch_decide_approvals(request,
            NS(user_id='manager', role='manager'), Session(store, fail='claim-before'))
    assert caught.value.status_code == 503 and setup.await_count == 0
    assert all(row.status == 'pending' for row in store.rows.values())

@pytest.mark.asyncio
async def test_dispatch_scope_isolated_and_restored_on_cancellation():
    entered, release = asyncio.Event(), asyncio.Event()
    async def scoped():
        try:
            with deadline.dispatch_scope():
                assert deadline.in_approval_dispatch()
                entered.set()
                await release.wait()
        finally:
            assert not deadline.in_approval_dispatch()
    task = asyncio.create_task(scoped())
    await asyncio.wait_for(entered.wait(), timeout=2)
    assert not deadline.in_approval_dispatch()
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert not deadline.in_approval_dispatch()

@pytest.mark.parametrize('replacement', [True, 1.0, '1'])
def test_contract_comparison_rejects_json_type_changes(replacement, setup):
    row = record()
    row.prefill_payload['tool_calls'][0]['params']['amount'] = 1
    row.approval_contract = deadline.build_contract(row)
    row.prefill_payload['tool_calls'][0]['params']['amount'] = replacement
    assert not deadline.verified(row)


def test_unknown_contract_fields_are_not_accepted(setup):
    row = record()
    row.approval_contract['human_approved'] = True
    assert not deadline.verified(row)


@pytest.mark.asyncio
async def test_uninstalled_schema_fails_without_dispatch(setup):
    store = Store([record()]); db = Session(store)
    async def missing_column(*args, **kwargs):
        raise RuntimeError('synthetic UndefinedColumn approval_contract')
    db.execute = missing_column
    response = await attempt('decide', db)
    assert response is None and setup.await_count == 0
    assert store.rows['approval-one'].status == 'pending'


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', ['payload', 'contract'])
@pytest.mark.parametrize('weaken_predicate', [False, True], ids=['guard', 'negative-control'])
async def test_outcome_cas_detects_snapshot_drift(changed, weaken_predicate, setup, monkeypatch):
    store = Store([record('resume')]); db = Session(store)
    execute = db.execute
    if weaken_predicate:
        monkeypatch.setattr(deadline, 'require_contract', lambda row: None)
        monkeypatch.setattr(deadline, 'canonical', lambda value: 'weakened-control')
    async def effect(*args, **kwargs):
        row = store.rows['approval-one']
        if changed == 'payload':
            row.prefill_payload['tool_calls'][0]['params']['body'] = 'concurrent change'
        else:
            # Fault injection only: actual DB trigger should forbid this corruption.
            row.approval_contract['risk_level'] = 'low'
        return True, 'synthetic', 'salesperson'
    setup.side_effect = effect
    if weaken_predicate:
        result = await invoke('resume', db)
        assert result.status == 'executed'  # Removing both guards reproduces the bad outcome.
    else:
        with pytest.raises(HTTPException) as exc:
            await invoke('resume', db)
        assert exc.value.status_code == 503
        assert store.rows['approval-one'].status == 'executing'
    assert setup.await_count == 1
