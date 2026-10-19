"""Best-effort post-commit notifications; mock receipts never prove real delivery."""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy import text

from app.observability.audit import get_audit_logger


async def notify_approval_result(
    db,
    approval_id: str,
    requester_id: str,
    session_id: Optional[str],
    result_type: str,
    detail: str,
) -> None:
    """向发起人发送审批结果通知(内部邮件 + 审计)

    Args:
        db: 数据库会话(用于查询发起人邮箱)
        approval_id: 审批单号
        requester_id: 发起人 user_id
        session_id: 关联会话(审计用)
        result_type: 结果类型 executed / rejected / timeout / approved_pending_reauth
        detail: 结果说明(如执行摘要或超时说明)
    """
    requester_email = None
    try:
        row = (
            await db.execute(
                text("SELECT email, username FROM users WHERE user_id = :uid"),
                {"uid": requester_id},
            )
        ).fetchone()
        requester_email = row.email if row else None
    except Exception:  # noqa: BLE001 邮箱查询失败不阻断通知流程
        logger.warning("APPROVAL_NOTIFICATION_LOOKUP_FAILED")

    message_id = None
    delivery = "unavailable"
    if requester_email:
        try:
            message_id = await _send_internal_mail(
                requester_email=requester_email,
                approval_id=approval_id,
                result_type=result_type,
                detail=detail,
            )
            delivery = "mock_recorded"
        except Exception:  # noqa: BLE001 邮件失败不阻断主流程
            logger.warning("APPROVAL_NOTIFICATION_TRANSPORT_UNAVAILABLE")

    await get_audit_logger().log(
        event_type="approval_notification",
        session_id=session_id,
        user_id=requester_id,
        output_summary=f"Approval notification: {delivery}",
        success=message_id is not None,
        payload={
            "approval_id": approval_id,
            "result_type": result_type,
            "detail": detail[:500],
            "message_id": message_id,
            "channel": "mock_internal_mail",
            "delivery": delivery,
        },
    )


async def _send_internal_mail(
    requester_email: str,
    approval_id: str,
    result_type: str,
    detail: str,
) -> str:
    """复用内部邮件工具(Mock)发送通知,返回 message_id

    Mock writes memory only. HTTP notification delivery remains unavailable until
    a durable system-notification identity and independent receipt are implemented.
    """
    from app.tools.mail import SendEmailInternalTool

    tool = SendEmailInternalTool()
    if tool._effective_provider() != "mock":
        raise RuntimeError("APPROVAL_NOTIFICATION_TRANSPORT_UNSUPPORTED")
    subject = f"【审批通知】{approval_id} - {result_type}"
    body = f"您发起的审批单 {approval_id} 已进入 {result_type} 状态。\n详情:{detail}"
    tool_result = await tool._execute(  # noqa: SLF001 通知内部直接调用,不经过 RBAC
        params={
            "to": [requester_email],
            "subject": subject,
            "body": body,
        },
        context={
            "user_id": "system",
            "role": "admin",
            "dept": "shared_company",
            "session_id": None,
            "request_id": f"notify-{approval_id}",
        },
    )
    if not tool_result.success:
        raise RuntimeError(tool_result.error or "内部邮件发送失败")
    message_id = tool_result.output.get("message_id")
    if not isinstance(message_id, str) or not message_id:
        raise RuntimeError("APPROVAL_NOTIFICATION_RECEIPT_REQUIRED")
    return message_id
