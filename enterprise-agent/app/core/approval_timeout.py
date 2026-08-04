"""审批超时扫描(审批生命周期闭环)

后台 worker 每 60 秒执行一次幂等扫描:
    UPDATE approval_requests SET status='timeout', decided_at=NOW()
    WHERE status='pending' AND expires_at IS NOT NULL AND expires_at < NOW()

幂等保证:UPDATE 带 status='pending' 条件,已处理的单(executed/rejected/
approved_pending_reauth)天然不受影响;同一单只可能被流转一次。
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import text

from app.core.approval_notify import notify_approval_result
from app.observability.audit import get_audit_logger


async def scan_expired_approvals() -> int:
    """扫描并流转超时审批单

    Returns:
        本次流转为 timeout 的审批单数量(0 表示无超时单)
    """
    from app.core.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                "UPDATE approval_requests SET status = 'timeout', "
                "decided_at = NOW(), comment = '审批超时,自动流转' "
                "WHERE status = 'pending' AND expires_at IS NOT NULL "
                "AND expires_at < NOW() "
                "RETURNING approval_id, session_id, requester_id"
            )
        )
        affected = result.fetchall()
        await session.commit()

    for row in affected:
        approval_id = row.approval_id
        # 审计:超时流转(操作者标记为系统)
        await get_audit_logger().log(
            event_type="approval_timeout",
            session_id=row.session_id,
            user_id="system",
            output_summary=f"审批单 {approval_id} 超时自动流转",
            success=True,
            payload={"approval_id": approval_id, "operator": "system"},
        )
        # 通知发起人
        try:
            async with factory() as notify_session:
                await notify_approval_result(
                    db=notify_session,
                    approval_id=approval_id,
                    requester_id=row.requester_id,
                    session_id=row.session_id,
                    result_type="timeout",
                    detail="审批单已超时,操作未执行;如需继续请联系审批人重新发起",
                )
        except Exception as e:  # noqa: BLE001 通知失败不阻断扫描
            logger.warning(f"审批超时通知失败 {approval_id}: {e}")

    if affected:
        logger.info(f"审批超时扫描: {len(affected)} 条已流转为 timeout")
    return len(affected)
