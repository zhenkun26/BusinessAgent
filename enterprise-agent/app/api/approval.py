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
from app.core import approval_deadline as deadline
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
        not isinstance(role, str) or role not in {"manager", "admin"} for role in roles
    ):
        raise HTTPException(403, "审批权限配置无效")
    if approver.role not in roles:
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


async def _lock_approval(db: Any, approval_id: str, actor: User, *, resume=False):
    """Lock all participant identities before the row; verify the unlocked snapshot."""
    before = await deadline.load(db, approval_id)
    if before is None:
        raise HTTPException(404, "审批请求不存在")
    deadline.require_contract(before)
    if resume and before.requester_id != actor.user_id:
        raise HTTPException(403, "仅原发起人可恢复执行")
    participants = {before.requester_id, actor.user_id}
    if resume:
        if not before.approver_id:
            raise HTTPException(403, "APPROVAL_APPROVER_REQUIRED")
        participants.add(before.approver_id)
    users = await deadline.lock_users(db, *participants)
    row = await lifecycle.load_locked(db, approval_id)
    if (row is None or row.requester_id != before.requester_id
            or row.approver_id != before.approver_id
            or deadline.canonical(deadline.payload(row)) != deadline.canonical(deadline.payload(before))
            or deadline.canonical(deadline.contract(row)) != deadline.canonical(deadline.contract(before))):
        raise HTTPException(409, "APPROVAL_CHANGED")
    await _authorize_locked(db, row, users, row.approver_id if resume else actor.user_id)
    return row


async def _authorize_locked(db: Any, row: Any, users: dict, approver_id: str) -> User:
    deadline.require_contract(row)
    requester = users[row.requester_id]
    _check_approver_role(row, users[approver_id])
    allowed = ROLE_TOOLS[AgentRole(requester.role)]
    if any(call["tool"] not in allowed for call in _approval_tool_calls(row)):
        raise HTTPException(403, "发起人无权调用审批工具")
    await deadline.guard_owner(db, row.requester_id, exclude=row.approval_id)
    return requester


def _check_requester_token(row: Any, token: str) -> None:
    payload = decode_identity_token(token)
    if payload["sub"] != row.requester_id:
        raise HTTPException(401, "审批凭据与发起人不匹配")


async def _execute_approval_tools(
    db: Any, row: Any, *, approver_id: str, requester_token: str,
) -> tuple[bool, str, str]:
    """Issue the paired server capability only for a confirmed durable claim."""
    from app.agents.execution import ToolCallPlan, execute_tool_calls
    from app.core.tool_operations import committed_approval_dispatch
    users = await deadline.lock_users(db, row.requester_id, approver_id)
    current = await lifecycle.load_locked(db, row.approval_id)
    if (current is None or current.status != "executing"
            or not current.execution_claim or current.execution_claim != row.execution_claim
            or current.execution_id != row.execution_id or current.approver_id != approver_id
            or deadline.canonical(deadline.payload(current)) != deadline.canonical(deadline.payload(row))
            or deadline.canonical(deadline.contract(current)) != deadline.canonical(deadline.contract(row))):
        raise HTTPException(409, "APPROVAL_CLAIM_CONFLICT")
    requester = await _authorize_locked(db, current, users, approver_id)
    _check_requester_token(current, requester_token)
    calls = _approval_tool_calls(current)
    if str(current.execution_id) != await lifecycle.bind_execution(current, calls):
        raise HTTPException(409, "APPROVAL_PLAN_CONFLICT")
    context = {"user_id": requester.user_id, "role": requester.role,
        "dept": requester.department, "session_id": current.session_id,
        "request_id": f"appr-exec-{current.approval_id}", "execution_slot": "approval",
        "triggered_by": "approval", "approval_id": current.approval_id}
    plans = [ToolCallPlan(tool=c["tool"], params=c.get("params", {}),
                         operation_id=c["operation_id"]) for c in calls]
    await db.commit()  # An uncertain acknowledgment cannot mint dispatch authority.
    with committed_approval_dispatch(current, calls):
        result = await execute_tool_calls(plans, context)
    return result.success, "最终状态以持久回执为准", requester.role


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
    deadline.require_contract(row)
    if row.status != "pending":
        raise HTTPException(409, "APPROVAL_ALREADY_DECIDED")
    if not row.live:
        await lifecycle.expire(db, row)
        raise HTTPException(409, "APPROVAL_EXPIRED")
    state = "rejected" if decision == "rejected" else "approved_pending_reauth"
    changed = (await db.execute(text("""UPDATE approval_requests SET status = :status,
        approver_id = :approver, comment = :comment, decided_at = (clock_timestamp() AT TIME ZONE 'UTC'), batch_id = :batch_id
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
        row = await _lock_approval(db, approval_id, approver)
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
        row = await _lock_approval(db, approval_id, requester, resume=True)
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
        row = await lifecycle.load_locked(db, approval_id)
        await db.commit()  # An uncertain acknowledgment never reaches tool invocation.
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_CLAIM_UNCONFIRMED") from None

    execution_uncertain = False
    try:
        success, _, _ = await _execute_approval_tools(db, row, approver_id=row.approver_id,
                                      requester_token=credentials.credentials)
        execution_uncertain = not success
    except Exception:
        execution_uncertain = True
        await db.rollback()
        logger.warning("APPROVAL_EXECUTION_UNCONFIRMED")
    # Cancellation deliberately leaves the retained executing claim for observation.
    try:
        current = await lifecycle.load_locked(db, approval_id)
        deadline.require_contract(current)
        if (deadline.canonical(deadline.payload(current)) != deadline.canonical(deadline.payload(row))
                or deadline.canonical(deadline.contract(current)) != deadline.canonical(deadline.contract(row))):
            raise OperationError("APPROVAL_SNAPSHOT_CHANGED")
        if str(current.execution_claim) != owner:
            raise OperationError("APPROVAL_CLAIM_CONFLICT")
        try:
            state = ("execution_unknown" if execution_uncertain else
                     await lifecycle.observe(db, current, finished=True))
        except OperationError:
            state = "execution_unknown"
        state = await lifecycle.settle(db, current, state)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_RESULT_UNCONFIRMED") from None
    await _notify_committed(db, current, state)
    return ApprovalResponse(approval_id=approval_id, status=state, message=STATUS_MESSAGES[state])


@router.get("/approval/{approval_id}/evidence")
async def approval_evidence(approval_id: str, actor: User = Depends(get_current_user),
                            db=Depends(get_db)):
    """Read-only, payload-free durable evidence. Reading never releases a hold."""
    row = await deadline.load(db, approval_id)
    if row is None:
        raise HTTPException(404, "审批请求不存在")
    current_actor = await resolve_active_user(actor.user_id, db)
    if actor.user_id not in {row.requester_id, row.approver_id}:
        _check_approver_role(row, current_actor)
    operations = (await db.execute(text("""SELECT o.operation_id, o.execution_id,
        o.intent, o.request, o.state, o.receipt, o.updated_at FROM tool_operations o
        JOIN approval_requests a ON a.execution_id = o.execution_id
        WHERE a.approval_id = :id ORDER BY o.slot"""), {"id": approval_id})).mappings().all()
    items = []
    for operation in operations:
        record = dict(operation)
        verified = False
        if record.get("receipt") is not None:
            try:
                record["operation_id"] = str(record["operation_id"])
                record["execution_id"] = str(record["execution_id"])
                if record["intent"]["target"]["provider"] == "http":
                    from app.tools.reference import receipt
                    receipt(record["receipt"], record)
                    verified = True
                else:
                    verified = (record["intent"]["target"]["provider"] == "mock"
                                and isinstance(record["receipt"], dict)
                                and record["receipt"].get("success") is True)
            except (OperationError, KeyError, TypeError, ValueError):
                verified = False
        observed = record.get("updated_at")
        items.append({"operation_id": str(record["operation_id"]), "state": record["state"],
            "receipt_present": record.get("receipt") is not None, "receipt_verified": verified,
            "observed_at": observed.isoformat() if observed else None})
    return {"approval_id": approval_id, "status": row.status,
            **deadline.review_fields(row), "operations": items,
            "automatic_release": False, "automatic_retry": False}


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
            "summary, created_at, batch_id, status, requester_id, prefill_payload, "
            "approver_roles, expires_at, approval_contract FROM approval_requests "
            "WHERE status = 'pending' AND approver_roles ? :role "
            "ORDER BY created_at DESC LIMIT 50"
        ),
        {"role": approver.role},
    )
    rows = result.fetchall()

    return {
        "pending_count": len(rows),
        "items": [
            {
                **deadline.review_fields(r),
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
            "approver_id, comment, batch_id, created_at, decided_at, requester_id, "
            "session_id, prefill_payload, approver_roles, expires_at, approval_contract "
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
                **deadline.review_fields(r),
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
            "requester_id, comment, batch_id, created_at, decided_at, session_id, "
            "prefill_payload, approver_roles, expires_at, approval_contract "
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
                **deadline.review_fields(r),
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
        before = {aid: await deadline.load(db, aid) for aid in sorted(ids)}
        if any(row is None for row in before.values()):
            raise HTTPException(404, "审批请求不存在")
        users = await deadline.lock_users(db, approver.user_id,
                                         *(row.requester_id for row in before.values()))
        locked = {aid: await lifecycle.load_locked(db, aid) for aid in sorted(ids)}
        for aid, row in locked.items():
            original = before[aid]
            if (row is None or row.requester_id != original.requester_id
                    or deadline.canonical(deadline.payload(row)) != deadline.canonical(deadline.payload(original))
                    or deadline.canonical(deadline.contract(row)) != deadline.canonical(deadline.contract(original))):
                raise HTTPException(409, "APPROVAL_CHANGED")
            await _authorize_locked(db, row, users, approver.user_id)
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
