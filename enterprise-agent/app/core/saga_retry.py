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
    """Inspect a historical inverse receipt, never claim or send an inverse.

    The compatibility entry point deliberately cannot authorize new work. Existing
    inverse IDs, requests and receipts remain in the journal for human review.
    Even verified historical completion does not release the manual hold.
    """
    if step.get('compensation_state') == 'committed':
        frozen = reference.inverse_wire(forward)
        if step.get('compensation_request') != frozen:
            raise OperationError('SAGA_INVERSE_CONFLICT')
        inverse = {'operation_id': str(step['compensation_id']),
                   'intent': forward['intent'], 'request': frozen}
        reference.inverse_receipt(step['compensation_receipt'], inverse, forward)
    return 'manual'


async def recover_owned(store: SagaStore, saga_id: str, owner: str) -> str:
    """Stop unclaimed work and persist a human hold without any provider I/O.

    Unknown/dispatched originals and historical inverses retain their evidence and
    identity. Neither retries nor later receipts authorize forward or inverse work.
    The durable manual state/error plus existing step/operation journals are the
    review record; only an explicitly designed human-resolution flow may release it.
    """
    try:
        await store.abort(saga_id, owner)
        await store.finish(saga_id, owner, 'manual', 'SAGA_MANUAL_REQUIRED')
    except Exception as exc:
        # An unconfirmed transition cannot be reported as a durable manual hold.
        # Preserve the retained recovery job and expose only fixed diagnostics.
        code = 'SAGA_OWNERSHIP_LOST' if (
            isinstance(exc, OperationError) and str(exc) == 'SAGA_OWNERSHIP_LOST'
        ) else 'SAGA_STORE_UNAVAILABLE'
        raise OperationError(code) from None
    return 'manual'


async def retry_saga_compensations(saga_id: str) -> str:
    """Compatibility job name: hold abandoned UUID journals, never compensate."""
    saga_id = valid_uuid(saga_id)
    store = SagaStore()
    run = await store.load(saga_id)
    if run['state'] in TERMINAL:
        return run['state']
    owner = str(uuid.uuid4())
    if not await store.acquire(saga_id, owner):
        return 'busy'
    return await guarded(store, saga_id, owner, lambda: recover_owned(store, saga_id, owner))
