"""Bounded expiry and read-only evidence reconciliation; never dispatch or replay tools."""
from __future__ import annotations

from sqlalchemy import text
from loguru import logger

from app.core import approval_lifecycle as lifecycle
from app.core.tool_operations import OperationError
from app.core.approval_notify import notify_approval_result


async def scan_expired_approvals() -> int:
    from app.core.database import get_session_factory
    factory = get_session_factory()
    changed = []
    async with factory() as db:
        rows = (await db.execute(text('''SELECT approval_id FROM approval_requests
            WHERE (status IN ('pending', 'approved_pending_reauth') AND
                (expires_at IS NULL OR expires_at <= (clock_timestamp() AT TIME ZONE 'UTC')))
            OR (status = 'executing' AND execution_deadline <= clock_timestamp())
            OR status = 'execution_unknown'
            ORDER BY execution_checked_at NULLS FIRST, approval_id
            LIMIT 100 FOR UPDATE SKIP LOCKED'''))).fetchall()
        for candidate in rows:
            row = await lifecycle.load_locked(db, candidate.approval_id)
            if await lifecycle.expire(db, row):
                changed.append((row, 'timeout'))
            elif row.status in lifecycle.ACTIVE:
                try:
                    state = await lifecycle.observe(db, row)
                except OperationError:
                    state = "execution_unknown"
                if state != row.status:
                    state = await lifecycle.settle(db, row, state)
                    changed.append((row, state))
            await db.execute(text("""UPDATE approval_requests SET
                execution_checked_at = clock_timestamp() WHERE approval_id = :id"""),
                {'id': row.approval_id})
        await db.commit()
    for row, state in changed:
        try:
            async with factory() as db:
                await notify_approval_result(db, row.approval_id, row.requester_id,
                    row.session_id, state, 'Approval state updated; inspect retained execution evidence.')
        except Exception:
            logger.warning('APPROVAL_NOTIFICATION_FAILED')
    return len(changed)
