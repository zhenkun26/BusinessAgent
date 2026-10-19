"""审批 API(对应 v3 方案 10.3 节,P0-5 + P1-1)"""

import json
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core import approval_lifecycle as lifecycle
from app.core.tool_operations import OperationError
from app.security.redaction import redact_text

from app.core.database import get_db
from app.core.approval_notify import notify_approval_result
from app.security.rbac import (
    User, get_current_user, AgentRole, security_scheme, ROLE_TOOLS,
    decode_identity_token, resolve_active_user,
)

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    """审批决策请求"""

    decision: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=1000)


class ApprovalResponse(BaseModel):
    approval_id: str
    status: str
    message: str


def _check_approver_role(row: Any, approver: User) -> None:
    roles = row.approver_roles
    if not isinstance(roles, list) or not roles or any(
        not isinstance(role, str) or role not in {r.value for r in AgentRole} for role in roles
    ):
        raise HTTPException(403, "审批权限配置无效")
    if approver.role != "admin" and approver.role not in roles:
        raise HTTPException(403, "无权审批此请求")


def _approval_tool_calls(row: Any) -> list[dict[str, Any]]:
    try:
        payload = row.prefill_payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        calls = payload.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError
        for call in calls:
            if (not isinstance(call, dict) or not isinstance(call.get("tool"), str)
                    or not isinstance(call.get("params", {}), dict)):
                raise ValueError
        return calls
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "审批工具负载无效") from None


async def _authorize_approval(db: Any, row: Any, approver_id: str) -> User:
    """Lock current identities in stable order for the caller's transaction."""
    if not isinstance(approver_id, str) or not approver_id.strip():
        raise HTTPException(403, "缺少原审批人授权")
    if not isinstance(row.requester_id, str) or not row.requester_id.strip():
        raise HTTPException(401, "审批发起人无效")
    users: dict[str, User] = {}
    for user_id in sorted({row.requester_id, approver_id}):
        users[user_id] = await resolve_active_user(user_id, db, lock=True)
    requester = users[row.requester_id]
    _check_approver_role(row, users[approver_id])
    allowed = ROLE_TOOLS[AgentRole(requester.role)]
    if any(call["tool"] not in allowed for call in _approval_tool_calls(row)):
        raise HTTPException(403, "发起人无权调用审批工具")
    return requester


def _check_requester_token(row: Any, token: str) -> None:
    payload = decode_identity_token(token)
    if payload["sub"] != row.requester_id:
        raise HTTPException(401, "审批凭据与发起人不匹配")


async def _execute_approval_tools(
    db: Any, row: Any, *, approver_id: str, requester_token: str,
) -> tuple[bool, str, str]:
    """Reauthorize both participants immediately before requester-context execution."""
    requester = await _authorize_approval(db, row, approver_id)
    _check_requester_token(row, requester_token)

    # Import only after authorization; failures cannot reach tool/audit side effects.
    from app.agents.execution import ToolCallPlan, execute_tool_calls

    context = {
        "user_id": requester.user_id,
        "role": requester.role,
        "dept": requester.department,
        "session_id": row.session_id,
        "request_id": f"appr-exec-{row.approval_id}",
        "triggered_by": "approval",
        "approval_id": row.approval_id,
    }
    plans = [ToolCallPlan(tool=tc["tool"], params=tc.get("params", {}),
                          reason=tc.get("reason", ""), operation_id=tc.get("operation_id"))
             for tc in _approval_tool_calls(row)]
    # Legacy approvals without persisted identities require a new approval, never fresh IDs here.
    from app.core.tool_operations import OperationError, approved_calls, valid_uuid
    try:
        for plan in plans:
            valid_uuid(plan.operation_id)
    except OperationError:
        raise HTTPException(409, "APPROVAL_ACTION_IDENTITY_REQUIRED") from None
    # Release participant locks before external work; the execution claim already committed.
    await db.commit()
    with approved_calls(requester.user_id, row.approval_id, _approval_tool_calls(row)):
        exec_result = await execute_tool_calls(plans, context)
    if exec_result.success:
        return True, "工具返回成功；最终状态以持久回执为准", requester.role
    return False, "工具执行未完成；请核对持久执行状态", requester.role


STATUS_MESSAGES = {
    "approved_pending_reauth": "审批已通过，待发起人确认执行",
    "rejected": "审批已拒绝，操作未执行",
    "timeout": "审批已过期，操作未领取",
    "executing": "执行已领取，正在处理；重复确认不会重复执行",
    "executed": "已由持久记录确认执行成功",
    "execution_failed": "执行失败，未确认产生成功动作",
    "compensated": "执行失败，已补偿所有确认成功的步骤",
    "compensation_failed": "补偿未完成，需要人工核对",
    "execution_unknown": "执行结果尚未确认，请勿重新发起相同操作",
}


async def _notify_committed(db: Any, row: Any, state: str) -> None:
    try:
        await notify_approval_result(db=db, approval_id=row.approval_id,
            requester_id=row.requester_id, session_id=row.session_id,
            result_type=state, detail=STATUS_MESSAGES.get(state, "请查询审批状态"))
    except Exception:
        logger.warning("APPROVAL_NOTIFICATION_FAILED")
        # Notification queries must not leave a failed transaction in a reused batch session.
        try:
            await db.rollback()
        except Exception:
            logger.warning("APPROVAL_NOTIFICATION_SESSION_UNAVAILABLE")


async def _decide_locked(db: Any, row: Any, approver_id: str, decision: str,
                         comment: str, batch_id: str | None = None) -> str:
    if row is None:
        raise HTTPException(404, "审批请求不存在")
    if decision == "rejected":
        _check_approver_role(row, await resolve_active_user(approver_id, db, lock=True))
    else:
        await _authorize_approval(db, row, approver_id)
    if row.status != "pending":
        raise HTTPException(409, "APPROVAL_ALREADY_DECIDED")
    if not row.live:
        await lifecycle.expire(db, row)
        raise HTTPException(409, "APPROVAL_EXPIRED")
    state = "rejected" if decision == "rejected" else "approved_pending_reauth"
    changed = (await db.execute(text("""UPDATE approval_requests SET status = :status,
        approver_id = :approver, comment = :comment, decided_at = NOW(), batch_id = :batch_id
        WHERE approval_id = :id AND status = 'pending'
        AND expires_at > (clock_timestamp() AT TIME ZONE 'UTC') RETURNING approval_id"""), {
            "id": row.approval_id, "status": state, "approver": approver_id,
            "comment": redact_text(comment), "batch_id": batch_id})).fetchone()
    if changed is None:
        raise HTTPException(409, "APPROVAL_STATE_CONFLICT")
    current = await lifecycle.load_locked(db, row.approval_id)
    await lifecycle.event(db, current, approver_id, state)
    return state


@router.post("/approval/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str, req: ApprovalDecisionRequest,
    approver: User = Depends(get_current_user), db=Depends(get_db),
):
    """Conditional decision only; execution requires a separate requester confirmation."""
    try:
        row = await lifecycle.load_locked(db, approval_id)
        state = await _decide_locked(db, row, approver.user_id, req.decision, req.comment)
        await db.commit()
    except HTTPException as exc:
        if exc.detail == "APPROVAL_EXPIRED":
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                raise HTTPException(503, "APPROVAL_STORE_UNAVAILABLE") from None
            await _notify_committed(db, row, "timeout")
        else:
            await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_STORE_UNAVAILABLE") from None
    await _notify_committed(db, row, state)
    return ApprovalResponse(approval_id=approval_id, status=state, message=STATUS_MESSAGES[state])


@router.post("/pending-executions/{approval_id}/resume", response_model=ApprovalResponse)
async def resume_pending_execution(
    approval_id: str, requester: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme), db=Depends(get_db),
):
    """Commit a one-way claim before I/O. An unknown claim is never reclaimed."""
    try:
        row = await lifecycle.load_locked(db, approval_id)
        if row is None:
            raise HTTPException(404, "审批请求不存在")
        if row.requester_id != requester.user_id:
            raise HTTPException(403, "仅原发起人可恢复执行")
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "未提供认证凭据")
        _check_requester_token(row, credentials.credentials)
        if row.status in lifecycle.ACTIVE | lifecycle.OUTCOMES:
            await db.commit()
            return ApprovalResponse(approval_id=approval_id, status=row.status,
                                    message=STATUS_MESSAGES[row.status])
        if row.status != "approved_pending_reauth":
            raise HTTPException(409, "APPROVAL_NOT_EXECUTABLE")
        await _authorize_approval(db, row, row.approver_id)
        if not row.live:
            await lifecycle.expire(db, row)
            await db.commit()
            await _notify_committed(db, row, "timeout")
            raise HTTPException(409, "APPROVAL_EXPIRED")
        try:
            execution_id = await lifecycle.bind_execution(row, _approval_tool_calls(row))
        except OperationError:
            raise HTTPException(409, "APPROVAL_ACTION_IDENTITY_REQUIRED") from None
        owner = await lifecycle.claim(db, row, execution_id)
        if owner is None:
            raise HTTPException(409, "APPROVAL_STATE_CONFLICT")
        await db.commit()  # An uncertain acknowledgment never reaches tool invocation.
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_CLAIM_UNCONFIRMED") from None

    try:
        await _execute_approval_tools(db, row, approver_id=row.approver_id,
                                      requester_token=credentials.credentials)
    except Exception:
        await db.rollback()
        logger.warning("APPROVAL_EXECUTION_UNCONFIRMED")
    # Cancellation deliberately leaves the retained executing claim for observation.
    try:
        current = await lifecycle.load_locked(db, approval_id)
        if str(current.execution_claim) != owner:
            raise OperationError("APPROVAL_CLAIM_CONFLICT")
        try:
            state = await lifecycle.observe(db, current, finished=True)
        except OperationError:
            state = "execution_unknown"
        state = await lifecycle.settle(db, current, state)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_RESULT_UNCONFIRMED") from None
    await _notify_committed(db, current, state)
    return ApprovalResponse(approval_id=approval_id, status=state, message=STATUS_MESSAGES[state])


@router.get("/approvals/pending")
async def list_pending_approvals(
    approver: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """查询待我审批的请求"""
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT approval_id, session_id, operation_type, risk_level, "
            "summary, created_at, batch_id FROM approval_requests "
            "WHERE status = 'pending' AND expires_at > (clock_timestamp() AT TIME ZONE 'UTC') AND (approver_roles ? :role OR :role = 'admin') "
            "ORDER BY created_at DESC LIMIT 50"
        ),
        {"role": approver.role},
    )
    rows = result.fetchall()

    return {
        "pending_count": len(rows),
        "items": [
            {
                "approval_id": r.approval_id,
                "session_id": r.session_id,
                "operation_type": r.operation_type,
                "risk_level": r.risk_level,
                "summary": r.summary,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "batch_id": r.batch_id,
            }
            for r in rows
        ],
    }


@router.get("/approvals/mine")
async def list_my_approvals(
    requester: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """查询我发起的审批请求(发起人视角的进度跟踪)

    与 /approvals/pending(审批人视角)互补:让发起人能看到自己单子的
    状态流转(pending → executed / rejected / approved_pending_reauth)。
    """
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT approval_id, operation_type, risk_level, summary, status, "
            "approver_id, comment, batch_id, created_at, decided_at "
            "FROM approval_requests WHERE requester_id = :uid "
            "ORDER BY created_at DESC LIMIT 50"
        ),
        {"uid": requester.user_id},
    )
    rows = result.fetchall()

    return {
        "total": len(rows),
        "items": [
            {
                "approval_id": r.approval_id,
                "operation_type": r.operation_type,
                "risk_level": r.risk_level,
                "summary": r.summary,
                "status": r.status,
                "approver_id": r.approver_id,
                "comment": r.comment,
                "batch_id": r.batch_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            }
            for r in rows
        ],
    }


@router.get("/approvals/handled")
async def list_handled_approvals(
    requester: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """查询我经手审批过的请求(审批人视角的历史记录)

    与 /approvals/mine(发起人视角)互补:审批人批准/拒绝后,单子从
    /approvals/pending 队列消失,这里按 approver_id 留痕,便于追溯"我批过什么"。
    """
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT approval_id, operation_type, risk_level, summary, status, "
            "requester_id, comment, batch_id, created_at, decided_at "
            "FROM approval_requests WHERE approver_id = :uid "
            "ORDER BY decided_at DESC LIMIT 50"
        ),
        {"uid": requester.user_id},
    )
    rows = result.fetchall()

    return {
        "total": len(rows),
        "items": [
            {
                "approval_id": r.approval_id,
                "operation_type": r.operation_type,
                "risk_level": r.risk_level,
                "summary": r.summary,
                "status": r.status,
                "requester_id": r.requester_id,
                "comment": r.comment,
                "batch_id": r.batch_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            }
            for r in rows
        ],
    }


# ============ 批量审批(P0-6)============


class BatchApprovalItem(BaseModel):
    """批量审批中的单条决策"""

    approval_id: str
    decision: Literal["approved", "rejected"]


class BatchApprovalRequest(BaseModel):
    """批量审批请求(对应 v3 方案 P0-6)

    场景:审批人一次性处理多个待审请求(如早上一并处理昨晚积压的审批)
    事务性:整批决策原子提交；不执行工具；重复 ID 在写入前拒绝
    """

    approvals: list[BatchApprovalItem] = Field(
        ..., min_length=1, max_length=50, description="批量决策列表(最多 50 条)"
    )
    comment: str = Field(default="", max_length=1000, description="统一备注")


class BatchApprovalResponse(BaseModel):
    """批量审批响应"""

    batch_id: str
    total: int
    succeeded: int
    failed: int
    results: list[dict] = Field(default_factory=list)


@router.post("/approvals/batch-decide", response_model=BatchApprovalResponse)
async def batch_decide_approvals(
    req: BatchApprovalRequest,
    approver: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """All decisions commit together; a failing member rolls the whole batch back."""
    batch_id = "batch_" + uuid.uuid4().hex
    ids = [item.approval_id for item in req.approvals]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "APPROVAL_DUPLICATE_ID")
    records = []
    try:
        locked = {aid: await lifecycle.load_locked(db, aid) for aid in sorted(ids)}
        for item in req.approvals:
            row = locked[item.approval_id]
            state = await _decide_locked(db, row, approver.user_id, item.decision,
                                         req.comment, batch_id)
            records.append((row, state))
        await db.commit()
    except HTTPException as exc:
        await db.rollback()
        return BatchApprovalResponse(batch_id=batch_id, total=len(ids), succeeded=0,
            failed=len(ids), results=[{"approval_id": aid, "success": False,
                "error": "APPROVAL_BATCH_ROLLED_BACK", "status_code": exc.status_code} for aid in ids])
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_BATCH_UNCONFIRMED") from None
    for row, state in records:
        await _notify_committed(db, row, state)
    return BatchApprovalResponse(batch_id=batch_id, total=len(ids), succeeded=len(ids), failed=0,
        results=[{"approval_id": row.approval_id, "success": True, "new_status": state}
                 for row, state in records])
