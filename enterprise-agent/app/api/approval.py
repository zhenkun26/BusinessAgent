"""审批 API(对应 v3 方案 10.3 节,P0-5 + P1-1)"""

import json
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.database import get_db
from app.core import approval_deadline as deadline
from app.core.approval_notify import notify_approval_result
from app.observability.audit import get_audit_logger
from app.security.rbac import User, get_current_user, AgentRole, security_scheme
from app.security.jwt_manager import get_jwt_manager

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    """审批决策请求"""

    decision: Literal["approved", "rejected"]
    comment: str = ""


class ApprovalResponse(BaseModel):
    approval_id: str
    status: str
    message: str


async def _execute_approval_tools(db, row, jwt_token_override: Optional[str] = None) -> tuple[bool, str, str]:
    """审批批准后,以发起人身份同步执行 prefill_payload 中的工具调用

    Args:
        db: 数据库会话
        row: approval_requests 行(需含 prefill_payload/requester_id/requester_token/session_id)
        jwt_token_override: 覆盖用 token(resume 场景用发起人重新登录后的新 token)

    Returns:
        (success, 结果摘要, 发起人角色)——角色返回供调用方审计记录"执行身份"
    """
    # 函数内 import,避免循环依赖(execution → tools → audit → database)
    from app.agents.execution import ToolCallPlan, execute_tool_calls

    payload = row.prefill_payload
    if isinstance(payload, str):
        payload = json.loads(payload)
    tool_calls = (payload or {}).get("tool_calls", [])
    if not tool_calls:
        return False, "审批负载无工具调用", ""

    # 查询发起人角色/部门,以其身份执行(审批不越权:执行身份=发起人,非审批人)
    result = await db.execute(
        text("SELECT role, department, is_active FROM users WHERE user_id = :uid"),
        {"uid": row.requester_id},
    )
    u = result.fetchone()
    if u is None or u.is_active is not True:
        return False, "发起人已停用或不存在，需人工核对", ""
    deadline.require_contract(row)
    role = u.role
    dept = (u.department if u else None) or "shared_company"

    context = {
        "user_id": row.requester_id,
        "role": role,
        "dept": dept,
        "jwt_token": jwt_token_override or row.requester_token or "",
        "session_id": row.session_id,
        "request_id": f"appr-exec-{row.approval_id}",
        # 审批触发标记:工具层审计/tracing 据此区分"主动调用"与"审批触发调用"
        # 主动调用时无这两个字段;审批触发时带,可串联回审批单
        "triggered_by": "approval",
        "approval_id": row.approval_id,
    }

    plans = [
        ToolCallPlan(
            tool=tc["tool"],
            params=tc.get("params", {}),
            reason=tc.get("reason", ""),
        )
        for tc in tool_calls
    ]

    # 执行前显式 RBAC 预检(防御性):pending 期间发起人角色可能被管理员调整,
    # 若新角色已无该工具权限,提前失败并记 security_violation 审计,
    # 而非等到工具层防线 3 拒绝——审计语义更清晰("审批后权限被收回")
    try:
        from app.security.rbac import ROLE_TOOLS, AgentRole
        allowed = ROLE_TOOLS.get(AgentRole(role), [])
        denied = [p.tool for p in plans if p.tool not in allowed]
        if denied:
            await get_audit_logger().log_violation(
                user_id=row.requester_id,
                tool_name=",".join(denied),
                reason=(
                    f"审批 {row.approval_id} 触发执行时,发起人角色 {role} "
                    f"已无权限调用 {denied}(权限可能在 pending 期间被调整)"
                ),
            )
            return False, f"发起人角色 {role} 无权调用工具 {denied}", role
    except Exception:
        return False, "权限核验失败，需人工核对", ""

    exec_result = await execute_tool_calls(plans, context)

    outputs = getattr(exec_result, "output", None) or getattr(exec_result, "outputs", None) or {}
    error = getattr(exec_result, "error", None)
    if exec_result.success:
        return True, f"工具执行成功: {outputs}", role
    return False, f"工具执行失败: {error or outputs}", role


async def _prepare(db, approval_id: str, actor: User, *, resume: bool = False):
    """Current human identity, owner hold and row contract, under stable user locks."""
    row = await deadline.load(db, approval_id)
    if row is None:
        raise HTTPException(404, "审批请求不存在")
    owner = row.requester_id
    if resume and owner != actor.user_id:
        raise HTTPException(403, "仅原发起人可恢复执行")
    users = await deadline.lock_users(db, owner, actor.user_id)
    row = await deadline.load(db, approval_id, locked=True)
    if row is None or row.requester_id != owner:
        raise HTTPException(409, "APPROVAL_CHANGED")
    deadline.require_contract(row)
    if not resume and users[actor.user_id].role not in row.approver_roles:
        raise HTTPException(403, "无权审批此请求")
    expected = "approved_pending_reauth" if resume else "pending"
    if row.status != expected:
        raise HTTPException(409, deadline.HOLD if row.status in deadline.ACTIVE
                            else "APPROVAL_ALREADY_DECIDED")
    from app.security.rbac import ROLE_TOOLS
    allowed = ROLE_TOOLS.get(AgentRole(users[owner].role), [])
    if any(c["tool"] not in allowed for c in deadline.payload(row)["tool_calls"]):
        raise HTTPException(403, "发起人当前无权执行审批工具")
    await deadline.guard_owner(db, owner, exclude=approval_id)
    await deadline.require_live(db, row)
    return row


async def _notify_committed(db, row, state: str, message: str) -> None:
    try:
        await notify_approval_result(db=db, approval_id=row.approval_id,
            requester_id=row.requester_id, session_id=row.session_id,
            result_type=state, detail=message)
    except Exception:
        await db.rollback()


async def _dispatch_claimed(db, row, token: str) -> ApprovalResponse:
    """Claim has already committed. No exception/unknown path releases it."""
    try:
        with deadline.dispatch_scope():
            success, summary, role = await _execute_approval_tools(db, row, token)
    except Exception:
        success, summary, role = False, "结果不明，请由有权限的人核对；AI不能决定重试。", ""
        await db.rollback()
    # Cancellation/BaseException escapes with the committed executing state retained.
    state = "executed" if success else "execution_unknown"
    try:
        changed = (await db.execute(text("UPDATE approval_requests SET status = :state "
            "WHERE approval_id = :id AND status = 'executing' "
            "AND prefill_payload = CAST(:snapshot AS JSONB) "
            "AND approval_contract = CAST(:contract AS JSONB) RETURNING approval_id"),
            {"state": state, "id": row.approval_id,
             "snapshot": deadline.canonical(deadline.payload(row)),
             "contract": deadline.canonical(deadline.contract(row))})).fetchone()
        if changed is None:
            raise RuntimeError("approval outcome state changed")
        await db.execute(text("INSERT INTO audit_logs (event_type, session_id, user_id, "
            "success, payload) VALUES ('approval_outcome', :sid, :uid, :success, "
            "CAST(:payload AS JSONB))"), {"sid": row.session_id, "uid": row.requester_id,
            "success": bool(success), "payload": deadline.canonical({
                "approval_id": row.approval_id, "status": state})})
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_RESULT_UNCONFIRMED_NO_RETRY") from None
    await _notify_committed(db, row, state,
        "工具返回成功。" if success else "暂停执行和重提，需人工核对；AI仅建议。")
    return ApprovalResponse(approval_id=row.approval_id, status=state,
        message=("工具返回成功，已保存结果。" if success else
                 "结果尚未确认，暂停执行和重提，需人工核对。AI仅提供建议。"))


@router.post("/approval/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(approval_id: str, req: ApprovalDecisionRequest,
    approver: User = Depends(get_current_user), db=Depends(get_db)):
    """Authenticated human decision; no legacy release or model approval endpoint."""
    try:
        row = await _prepare(db, approval_id, approver)
        if req.decision == "rejected":
            await deadline.transition(db, row, approver.user_id, "rejected", req.comment)
            await _notify_committed(db, row, "rejected", "审批已拒绝。")
            return ApprovalResponse(approval_id=approval_id, status="rejected", message="审批已拒绝")
        token = row.requester_token or ""
        mgr = get_jwt_manager()
        try:
            identity = mgr.decode(token)
            if identity.get("sub") != row.requester_id:
                raise ValueError("wrong requester")
            token = await mgr.refresh_if_needed(token, min_seconds=600)
        except Exception:
            await deadline.transition(db, row, approver.user_id,
                                      "approved_pending_reauth", req.comment)
            await _notify_committed(db, row, "approved_pending_reauth", "请原发起人确认，期限不延长。")
            return ApprovalResponse(approval_id=approval_id, status="approved_pending_reauth",
                                    message="待原发起人重新授权，原审批期限不延长。")
        await deadline.transition(db, row, approver.user_id, "executing", req.comment)
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_CLAIM_UNCONFIRMED_NO_DISPATCH") from None
    return await _dispatch_claimed(db, row, token)


@router.post("/pending-executions/{approval_id}/resume", response_model=ApprovalResponse)
async def resume_pending_execution(approval_id: str,
    requester: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme), db=Depends(get_db)):
    try:
        row = await _prepare(db, approval_id, requester, resume=True)
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "未提供认证凭据")
        token = credentials.credentials
        try:
            if get_jwt_manager().decode(token).get("sub") != row.requester_id:
                raise ValueError("wrong requester")
        except Exception:
            raise HTTPException(401, "审批凭据与发起人不匹配") from None
        # Recheck the actual original approver, not a caller-supplied role.
        if not row.approver_id:
            raise HTTPException(403, "APPROVAL_APPROVER_REQUIRED")
        # Avoid taking another user lock out of order: finish this read transaction;
        # reacquire all participant locks in canonical order and re-read the row.
        owner_id, approver_id = row.requester_id, row.approver_id
        payload_snapshot = deadline.canonical(deadline.payload(row))
        contract_snapshot = deadline.canonical(deadline.contract(row))
        await db.rollback()
        users = await deadline.lock_users(db, owner_id, approver_id)
        row = await deadline.load(db, approval_id, locked=True)
        if (row is None or row.requester_id != owner_id or owner_id != requester.user_id
                or row.approver_id != approver_id
                or deadline.canonical(deadline.payload(row)) != payload_snapshot
                or deadline.canonical(deadline.contract(row)) != contract_snapshot):
            raise HTTPException(409, "APPROVAL_CHANGED")
        deadline.require_contract(row)
        if row.status != "approved_pending_reauth":
            raise HTTPException(409, "APPROVAL_ALREADY_CLAIMED")
        if users[row.approver_id].role not in row.approver_roles:
            raise HTTPException(403, "原审批人当前无审批权限")
        from app.security.rbac import ROLE_TOOLS
        if any(c["tool"] not in ROLE_TOOLS.get(AgentRole(users[row.requester_id].role), [])
               for c in deadline.payload(row)["tool_calls"]):
            raise HTTPException(403, "发起人当前无权执行审批工具")
        await deadline.guard_owner(db, row.requester_id, exclude=approval_id)
        await deadline.require_live(db, row)
        await deadline.transition(db, row, row.approver_id, "executing")
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(503, "APPROVAL_CLAIM_UNCONFIRMED_NO_DISPATCH") from None
    return await _dispatch_claimed(db, row, token)


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
    每项独立领取并提交；可能部分完成，外部效果不随数据库回滚。
    """

    approvals: list[BatchApprovalItem] = Field(
        ..., min_length=1, max_length=50, description="批量决策列表(最多 50 条)"
    )
    comment: str = Field(default="", description="统一备注")


class BatchApprovalResponse(BaseModel):
    """批量审批响应"""

    batch_id: str
    total: int
    succeeded: int
    failed: int
    results: list[dict] = Field(default_factory=list)


@router.post("/approvals/batch-decide", response_model=BatchApprovalResponse)
async def batch_decide_approvals(req: BatchApprovalRequest,
    approver: User = Depends(get_current_user), db=Depends(get_db)):
    """Each item commits independently. External effects cannot be rolled back as a batch."""
    ids = [item.approval_id for item in req.approvals]
    if len(set(ids)) != len(ids):
        raise HTTPException(400, "APPROVAL_DUPLICATE_BATCH_ID")
    results = []
    for index, item in enumerate(req.approvals):
        uncertain = False
        try:
            result = await decide_approval(item.approval_id,
                ApprovalDecisionRequest(decision=item.decision, comment=req.comment), approver, db)
            ok = result.status != "execution_unknown"
            uncertain = not ok
            results.append({"approval_id": item.approval_id, "success": ok,
                            "new_status": result.status, "message": result.message})
        except HTTPException as exc:
            results.append({"approval_id": item.approval_id, "success": False,
                            "error": exc.detail})
            uncertain = exc.status_code >= 500
        if uncertain:
            results.extend({"approval_id": rest.approval_id, "success": False,
                            "error": "NOT_ATTEMPTED_HUMAN_REVIEW_REQUIRED"}
                           for rest in req.approvals[index + 1:])
            break
    succeeded = sum(item["success"] for item in results)
    return BatchApprovalResponse(batch_id="batch_" + uuid.uuid4().hex[:12], total=len(results),
        succeeded=succeeded, failed=len(results)-succeeded, results=results)
