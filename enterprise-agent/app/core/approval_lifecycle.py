"""Approval state transitions and retained evidence. No execution retry or token storage."""
from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import text
from app.core import approval_deadline as deadline

from app.core.tool_operations import OperationError, OperationStore, canonical, valid_uuid

UNCLAIMED = {'pending', 'approved_pending_reauth'}
ACTIVE = {'executing', 'execution_unknown'}
OUTCOMES = {'executed', 'execution_failed', 'compensated', 'compensation_failed', 'execution_unknown'}


async def load_locked(db: Any, approval_id: str) -> Any:
    return (await db.execute(text('''SELECT approval_id, session_id, requester_id,
        operation_type, risk_level, summary, created_at, approval_contract,
        prefill_payload, approver_roles, approver_id, status, expires_at, execution_id,
        execution_claim, execution_deadline, execution_error,
        (expires_at IS NOT NULL AND expires_at > (clock_timestamp() AT TIME ZONE 'UTC')) AS live
        FROM approval_requests WHERE approval_id = :id FOR UPDATE'''),
        {'id': approval_id})).fetchone()


async def event(db: Any, row: Any, actor: str, state: str) -> None:
    from app.observability.correlation import snapshot
    await db.execute(text('''INSERT INTO audit_logs
        (event_type, session_id, user_id, success, payload)
        VALUES ('approval_transition', :sid, :uid, :success, CAST(:payload AS JSONB))'''), {
            'sid': row.session_id, 'uid': actor, 'success': state == 'executed',
            'payload': canonical({**snapshot(), 'approval_id': row.approval_id, 'new_status': state,
                'decided_by': row.approver_id, 'execution_id': str(row.execution_id) if
                row.execution_id else None, 'execution_authorization': 'requester_confirmation_required'})})


async def expire(db: Any, row: Any) -> bool:
    if row.status not in UNCLAIMED or not deadline.verified(row):
        return False
    changed = (await db.execute(text('''UPDATE approval_requests SET status = 'timeout'
        WHERE approval_id = :id AND status IN ('pending', 'approved_pending_reauth')
        AND expires_at <= (clock_timestamp() AT TIME ZONE 'UTC')
        RETURNING approval_id'''), {'id': row.approval_id})).fetchone()
    if changed is not None:
        await event(db, row, 'system', 'timeout')
    return changed is not None


async def bind_execution(row: Any, calls: list[dict]) -> str:
    """Only the exact complete persisted plan owned by this requester/session is usable."""
    store = OperationStore()
    execution_id = None
    for call in calls:
        record = await store.load(valid_uuid(call.get('operation_id')))
        if (record['owner_id'] != row.requester_id or record['session_id'] != row.session_id
                or record['calls'] != calls or record['intent'] != call):
            raise OperationError('APPROVAL_PLAN_CONFLICT')
        eid = str(record['execution_id'])
        if execution_id is not None and eid != execution_id:
            raise OperationError('APPROVAL_PLAN_CONFLICT')
        execution_id = eid
    if execution_id is None or len({c['operation_id'] for c in calls}) != len(calls):
        raise OperationError('APPROVAL_PLAN_CONFLICT')
    return execution_id


async def claim(db: Any, row: Any, execution_id: str) -> str | None:
    deadline.require_contract(row)
    owner = str(uuid.uuid4())
    changed = (await db.execute(text('''UPDATE approval_requests SET status = 'executing',
        execution_id = :eid, execution_claim = :claim,
        execution_deadline = clock_timestamp() + interval '5 minutes', execution_error = NULL
        WHERE approval_id = :id AND status = 'approved_pending_reauth'
        AND execution_claim IS NULL AND expires_at > (clock_timestamp() AT TIME ZONE 'UTC')
        RETURNING approval_id'''), {'id': row.approval_id, 'eid': execution_id,
                                    'claim': owner})).fetchone()
    if changed is None:
        return None
    current = await load_locked(db, row.approval_id)
    await event(db, current, row.requester_id, 'executing')
    return owner


async def observe(db: Any, row: Any, *, finished: bool = False) -> str:
    """Read durable evidence only; never invoke tools or query an external provider."""
    if row.execution_id is None or not deadline.verified(row):
        return 'execution_unknown'
    result = await db.execute(text('''SELECT operation_id, execution_id, intent, request,
        state, receipt FROM tool_operations WHERE execution_id = :eid ORDER BY slot'''),
        {'eid': str(row.execution_id)})
    rows = result.mappings().all()
    try:
        calls = deadline.payload(row)['tool_calls']
        expected = {str(c['operation_id']): c for c in calls}
        if not calls or len(expected) != len(calls) or len(rows) != len(calls):
            return 'execution_unknown'
        if {str(r['operation_id']) for r in rows} != set(expected):
            return 'execution_unknown'
        for retained in rows:
            if (retained['intent'] != expected[str(retained['operation_id'])]
                    or str(retained['execution_id']) != str(row.execution_id)):
                return 'execution_unknown'
    except (KeyError, TypeError, ValueError):
        return 'execution_unknown'
    if all(r['state'] == 'committed' for r in rows):
        for retained in rows:
            operation = dict(retained)
            if operation['intent']['target']['provider'] == 'http':
                from app.tools.reference import receipt
                operation['operation_id'] = str(operation['operation_id'])
                receipt(operation['receipt'], operation)
            elif (operation['intent']['target']['provider'] != 'mock'
                  or not isinstance(operation['receipt'], dict)
                  or operation['receipt'].get('success') is not True):
                return 'execution_unknown'
        return 'executed'
    if rows and (all(r['state'] == 'rejected' for r in rows)
                 or finished and all(r['state'] in {'prepared', 'rejected'} for r in rows)):
        return 'execution_failed'
    return 'execution_unknown'


async def settle(db: Any, row: Any, state: str) -> str:
    if state not in OUTCOMES:
        raise OperationError('APPROVAL_STATE_INVALID')
    if row.status != 'executing':
        return row.status  # New evidence never releases an existing human hold.
    if state in {'compensated', 'compensation_failed'}:
        state = 'execution_unknown'
    changed = (await db.execute(text('''UPDATE approval_requests SET
        status = CASE WHEN :status = 'executed' AND
            (execution_deadline IS NULL OR execution_deadline <= clock_timestamp())
            THEN 'execution_unknown' ELSE :status END,
        execution_error = CASE WHEN :status = 'executed' AND
            (execution_deadline IS NULL OR execution_deadline <= clock_timestamp())
            THEN 'APPROVAL_EXECUTION_UNKNOWN' ELSE :error END WHERE approval_id = :id AND execution_claim = :claim
        AND status = 'executing' AND status <> :status
        RETURNING approval_id'''), {'id': row.approval_id, 'claim': str(row.execution_claim),
        'status': state, 'error': None if state == 'executed' else 'APPROVAL_' + state.upper()})).fetchone()
    current = await load_locked(db, row.approval_id)
    if changed is not None:
        await event(db, current, row.requester_id, current.status)
    return current.status
