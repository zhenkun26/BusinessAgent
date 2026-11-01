"""Expire only authenticated new UTC approvals; legacy and claims stay untouched."""
from __future__ import annotations

from sqlalchemy import text
from app.core import approval_deadline as deadline
from app.core.approval_notify import notify_approval_result
from app.observability.audit import get_audit_logger


async def scan_expired_approvals() -> int:
    from app.core.database import get_session_factory
    factory = get_session_factory()
    changed = []
    cursor = ""
    while True:
        async with factory() as db:
            rows = (await db.execute(text(f"SELECT {deadline.COLUMNS} FROM approval_requests "
                "WHERE status IN ('pending', 'approved_pending_reauth') "
                "AND expires_at <= (clock_timestamp() AT TIME ZONE 'UTC') "
                "AND approval_id > :cursor ORDER BY approval_id LIMIT 100 "
                "FOR UPDATE SKIP LOCKED"), {"cursor": cursor})).fetchall()
            if not rows:
                await db.rollback()
                break
            cursor = rows[-1].approval_id  # Advance over invalid/legacy rows too.
            for row in rows:
                if not deadline.verified(row):
                    continue
                result = (await db.execute(text("UPDATE approval_requests SET status = 'timeout', "
                    "decided_at = (clock_timestamp() AT TIME ZONE 'UTC') WHERE approval_id = :id "
                    "AND status IN ('pending', 'approved_pending_reauth') "
                    "AND expires_at <= (clock_timestamp() AT TIME ZONE 'UTC') "
                    "RETURNING approval_id"), {"id": row.approval_id})).fetchone()
                if result is not None:
                    changed.append(row)
                    await db.execute(text("INSERT INTO audit_logs (event_type, session_id, user_id, "
                        "success, payload) VALUES ('approval_timeout', :sid, 'system', FALSE, "
                        "CAST(:payload AS JSONB))"), {"sid": row.session_id,
                        "payload": deadline.canonical({"approval_id": row.approval_id,
                                                       "new_status": "timeout"})})
            await db.commit()
    for row in changed:
        try:
            async with factory() as db:
                await notify_approval_result(db=db, approval_id=row.approval_id,
                    requester_id=row.requester_id, session_id=row.session_id,
                    result_type="timeout", detail="审批期限已过，不能继续执行；请人工核对后续处理。")
        except Exception:
            pass  # Notification failure never releases/replays an approval.
    return len(changed)
