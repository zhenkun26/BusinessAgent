"""Conservative retained-journal recovery. Never replay a claimed write or legacy action."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
import uuid

from app.core.saga_store import SagaStore, TERMINAL
from app.core.tool_operations import OperationError, OperationStore, authorize_action, valid_uuid
from app.tools import reference


async def guarded(store: SagaStore, saga_id: str, owner: str,
                  work: Callable[[], Awaitable[Any]]) -> Any:
    """Lease loss cancels local work; it cannot retract an already sent HTTP request."""
    async def keep_lease() -> None:
        while True:
            await asyncio.sleep(20)
            await store.renew(saga_id, owner)

    execution = asyncio.create_task(work())
    renewal = asyncio.create_task(keep_lease())
    try:
        done, _ = await asyncio.wait((execution, renewal), return_when=asyncio.FIRST_COMPLETED)
        if renewal in done:
            await renewal
        return await execution
    finally:
        execution.cancel()
        renewal.cancel()
        await asyncio.gather(execution, renewal, return_exceptions=True)


async def validate_target(row: dict, context: dict) -> None:
    from app.config import get_settings
    from app.tools.base import get_tool
    name = row['intent']['tool']
    await authorize_action(context, name)
    tool = get_tool(name)
    if tool is None or reference.target(tool, get_settings()) != row['intent']['target']:
        raise OperationError('SAGA_TARGET_CHANGED')


async def reconcile_forward(operations: OperationStore, row: dict, context: dict) -> dict:
    if row['state'] in {'committed', 'rejected'}:
        return row
    await validate_target(row, context)
    if row['intent']['target']['provider'] != 'http' or row['request'] is None:
        return row
    ok, data, _, meta = await reference.request(
        row['intent']['target'], 'GET', '/operations/' + str(row['operation_id']))
    if ok and meta.get('status') == 200:
        try:
            if reference.rejected(data, row):
                await operations.finish(str(row['operation_id']), 'rejected', data)
            elif data.get('result') is not None:
                receipt = reference.receipt(data['result'], row)
                if data.get('operation') != receipt['operation']:
                    raise OperationError('REFERENCE_RECEIPT_INVALID')
                await operations.finish(str(row['operation_id']), 'committed', receipt)
        except OperationError as exc:
            if str(exc).startswith('ACTION_'):
                raise
    return await operations.load(str(row['operation_id']))


async def compensate_step(store: SagaStore, saga_id: str, owner: str,
                           step: dict, forward: dict, context: dict) -> str:
    await validate_target(forward, context)
    if forward['intent']['target']['provider'] != 'http':
        raise OperationError('SAGA_MOCK_RECOVERY_UNSUPPORTED')
    frozen = reference.inverse_wire(forward)
    cid = str(step['compensation_id'])
    inverse = {'operation_id': cid, 'intent': forward['intent'], 'request': frozen}
    state = step['compensation_state']
    if step['compensation_request'] is not None and step['compensation_request'] != frozen:
        raise OperationError('SAGA_INVERSE_CONFLICT')
    if state == 'committed':
        verified = reference.inverse_receipt(step['compensation_receipt'], inverse, forward)
        return 'manual' if verified['operation']['effect'] == 'recall_requested' else 'committed'
    if state == 'rejected':
        return 'manual'
    claimed = await store.inverse_claim(saga_id, owner, step['slot'], frozen)
    if claimed:
        # Claim and exact wire intent have committed before the one permitted write.
        ok, data, _, meta = await reference.request(
            forward['intent']['target'], frozen['method'], frozen['path'], body=frozen['body'],
            operation_id=cid, if_match=frozen['if_match'],
            compensates_operation_id=frozen['compensates_operation_id'])
        status = 202 if forward['intent']['tool'] == 'send_email_external' else 200
        if ok and meta.get('status') == status:
            try:
                verified = reference.inverse_receipt(data, inverse, forward)
            except OperationError:
                verified = None
            if verified is not None:
                await store.inverse_finish(saga_id, owner, step['slot'], 'committed', verified)
                return 'manual' if status == 202 else 'committed'
    # A claim-before-send crash is also uncertain. 404 does not authorize another send.
    ok, data, _, meta = await reference.request(
        forward['intent']['target'], 'GET', '/operations/' + cid)
    if ok and meta.get('status') == 200:
        try:
            if reference.rejected(data, inverse, inverse=True):
                await store.inverse_finish(saga_id, owner, step['slot'], 'rejected', data)
                return 'manual'
            verified = reference.inverse_receipt(data['result'], inverse, forward)
            if data.get('operation') != verified['operation']:
                raise OperationError('REFERENCE_RECEIPT_INVALID')
        except (OperationError, KeyError, TypeError):
            verified = None
        if verified is not None:
            await store.inverse_finish(saga_id, owner, step['slot'], 'committed', verified)
            return 'manual' if verified['operation']['effect'] == 'recall_requested' else 'committed'
    await store.inverse_finish(saga_id, owner, step['slot'], 'unknown', None)
    return 'unknown'


async def recover_owned(store: SagaStore, saga_id: str, owner: str) -> str:
    """Reconcile ALL original effects before starting ANY inverse; then reverse order."""
    try:
        await store.abort(saga_id, owner)
        run = await store.load(saga_id)
        operations = OperationStore()
        committed = []
        unresolved = False
        for step in run['steps']:
            if not step['definition']['action']:
                continue
            row = await operations.load(str(step['operation_id']))
            row['operation_id'] = str(row['operation_id'])
            row = await reconcile_forward(operations, row, run['context'])
            if row['state'] == 'committed':
                if row['intent']['target']['provider'] == 'http':
                    reference.receipt(row['receipt'], row)
                committed.append((step, row))
            elif row['state'] != 'rejected':
                unresolved = True
        if unresolved:
            await store.release(saga_id, owner)
            return 'aborting'
        for step, row in reversed(committed):
            outcome = await compensate_step(store, saga_id, owner, step, row, run['context'])
            if outcome == 'unknown':
                await store.release(saga_id, owner)
                return 'aborting'
            if outcome != 'committed':
                await store.finish(saga_id, owner, 'manual', 'SAGA_MANUAL_REQUIRED')
                return 'manual'
        await store.finish(saga_id, owner, 'compensated')
        return 'compensated'
    except OperationError as exc:
        if str(exc) in {'SAGA_STORE_UNAVAILABLE', 'ACTION_STORE_UNAVAILABLE', 'SAGA_OWNERSHIP_LOST'}:
            raise
        await store.finish(saga_id, owner, 'manual', 'SAGA_MANUAL_REQUIRED')
        return 'manual'


async def retry_saga_compensations(saga_id: str) -> str:
    """New UUID journal only; legacy free-form records are never executed."""
    saga_id = valid_uuid(saga_id)
    store = SagaStore()
    run = await store.load(saga_id)
    if run['state'] in TERMINAL:
        return run['state']
    owner = str(uuid.uuid4())
    if not await store.acquire(saga_id, owner):
        return 'busy'
    return await guarded(store, saga_id, owner, lambda: recover_owned(store, saga_id, owner))
