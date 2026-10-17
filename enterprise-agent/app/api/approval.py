"""审批 API(对应 v3 方案 10.3 节,P0-5 + P1-1)"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.core.database import get_db
from app.core.approval_notify import notify_approval_result
from app.observability.audit import get_audit_logger
from app.security.rbac import (
    User, get_current_user, AgentRole, security_scheme, ROLE_TOOLS,
    decode_identity_token, resolve_active_user,
)
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


def _check_requester_token(row: Any, token: str, *, allow_expired: bool = False) -> None:
    payload = decode_identity_token(token, allow_expired=allow_expired)
    if payload["sub"] != row.requester_id:
        raise HTTPException(401, "审批凭据与发起人不匹配")


async def _execute_approval_tools(
    db: Any, row: Any, *, approver_id: str, jwt_token_override: Optional[str] = None,
) -> tuple[bool, str, str]:
    """Reauthorize both participants immediately before requester-context execution."""
    token = row.requester_token if jwt_token_override is None else jwt_token_override
    _check_requester_token(row, token or "")
    requester = await _authorize_approval(db, row, approver_id)

    # Import only after authorization; failures cannot reach tool/audit side effects.
    from app.agents.execution import ToolCallPlan, execute_tool_calls

    context = {
        "user_id": requester.user_id,
        "role": requester.role,
        "dept": requester.department,
        "jwt_token": token,
        "session_id": row.session_id,
        "request_id": f"appr-exec-{row.approval_id}",
        "triggered_by": "approval",
        "approval_id": row.approval_id,
    }
    plans = [ToolCallPlan(tool=tc["tool"], params=tc.get("params", {}),
                          reason=tc.get("reason", "")) for tc in _approval_tool_calls(row)]
    exec_result = await execute_tool_calls(plans, context)
    outputs = getattr(exec_result, "output", None) or getattr(exec_result, "outputs", None) or {}
    error = getattr(exec_result, "error", None)
    if exec_result.success:
        return True, f"工具执行成功: {outputs}", requester.role
    return False, f"工具执行失败: {error or outputs}", requester.role


@router.post("/approval/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str,
    req: ApprovalDecisionRequest,
    approver: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """审批决策 API

    对应 v3 方案 10.3 节 decide_approval_v3:
    - 校验审批人身份
    - 检查发起人 JWT(P0-5)
    - 过期则标记 approved_pending_reauth
    - 有效则恢复图执行
    """
    from sqlalchemy import text

    # 1. 查询审批请求
    result = await db.execute(
        text(
            "SELECT approval_id, session_id, requester_id, operation_type, "
            "risk_level, summary, prefill_payload, approver_roles, status, "
            "requester_token FROM approval_requests WHERE approval_id = :id"
        ),
        {"id": approval_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(404, "审批请求不存在")

    if row.status != "pending":
        raise HTTPException(400, f"审批已处理, 当前状态: {row.status}")

    # Request authentication may predate this transaction; resolve authority again.
    if req.decision == "rejected":
        current_approver = await resolve_active_user(approver.user_id, db, lock=True)
        _check_approver_role(row, current_approver)
    else:
        await _authorize_approval(db, row, approver.user_id)

    jwt_mgr = get_jwt_manager()
    requester_token = row.requester_token or ""
    if req.decision == "approved" and requester_token:
        _check_requester_token(row, requester_token, allow_expired=True)

    if req.decision == "rejected":
        # 直接拒绝,无需执行
        await db.execute(
            text(
                "UPDATE approval_requests SET status = 'rejected', "
                "approver_id = :approver, comment = :comment, "
                "decided_at = NOW() WHERE approval_id = :id"
            ),
            {
                "id": approval_id, "approver": approver.user_id,
                "comment": req.comment,
            },
        )
        await db.commit()

        # 审计:审批决策(拒绝)
        await get_audit_logger().log(
            event_type="approval_decision",
            user_id=approver.user_id,
            session_id=row.session_id,
            payload={
                "approval_id": approval_id,
                "decision": req.decision,
                "new_status": "rejected",
            },
        )
        # 通知发起人:审批已拒绝
        try:
            await notify_approval_result(
                db=db,
                approval_id=approval_id,
                requester_id=row.requester_id,
                session_id=row.session_id,
                result_type="rejected",
                detail=f"审批已拒绝({req.comment or '无意见'}),操作未执行",
            )
        except Exception as e:  # noqa: BLE001 通知失败不影响审批结果返回
            logger.warning(f"审批拒绝通知失败 {approval_id}: {e}")
        return ApprovalResponse(
            approval_id=approval_id, status="rejected",
            message="审批已拒绝, 流程终止",
        )

    # 4. 审批通过:检查发起人 token
    if not requester_token or jwt_mgr.is_expired(requester_token):
        # token 过期:标记等待重新授权
        await db.execute(
            text(
                "UPDATE approval_requests SET status = 'approved_pending_reauth', "
                "approver_id = :approver, comment = :comment, "
                "decided_at = NOW() WHERE approval_id = :id"
            ),
            {
                "id": approval_id, "approver": approver.user_id,
                "comment": req.comment,
            },
        )
        await db.commit()

        # 通知发起人:需重新登录授权后恢复执行
        try:
            await notify_approval_result(
                db=db,
                approval_id=approval_id,
                requester_id=row.requester_id,
                session_id=row.session_id,
                result_type="approved_pending_reauth",
                detail="审批已通过,但需要您重新登录后恢复执行",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"重新授权通知失败 {approval_id}: {e}")
        return ApprovalResponse(
            approval_id=approval_id,
            status="approved_pending_reauth",
            message="审批已通过, 但需发起人重新登录后触发执行",
        )

    # 5. token 有效:尝试刷新(P0-5)
    try:
        refreshed_token = await jwt_mgr.refresh_if_needed(requester_token, min_seconds=600)
    except Exception:
        # 刷新失败:同样走重新授权流程
        await db.execute(
            text(
                "UPDATE approval_requests SET status = 'approved_pending_reauth', "
                "approver_id = :approver, comment = :comment, "
                "decided_at = NOW() WHERE approval_id = :id"
            ),
            {
                "id": approval_id, "approver": approver.user_id,
                "comment": req.comment,
            },
        )
        await db.commit()
        try:
            await notify_approval_result(
                db=db,
                approval_id=approval_id,
                requester_id=row.requester_id,
                session_id=row.session_id,
                result_type="approved_pending_reauth",
                detail="审批已通过,但 token 刷新失败,需要您重新登录后恢复执行",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"重新授权通知失败 {approval_id}: {e}")
        return ApprovalResponse(
            approval_id=approval_id,
            status="approved_pending_reauth",
            message="审批已通过, token 刷新失败, 需发起人重新授权",
        )

    # 6. token 有效:以发起人身份同步执行 prefill_payload 中的工具调用
    exec_success, exec_summary, requester_role = await _execute_approval_tools(
        db, row, approver_id=approver.user_id, jwt_token_override=refreshed_token
    )

    # token 刷新成功则回写,避免下次 resume 用过期 token
    # (refreshed_token 仅当 refresh_if_needed 真正换发了新 token 时与原 token 不同)
    if refreshed_token and refreshed_token != requester_token:
        await db.execute(
            text(
                "UPDATE approval_requests SET requester_token = :token "
                "WHERE approval_id = :id"
            ),
            {"id": approval_id, "token": refreshed_token},
        )

    await db.execute(
        text(
            "UPDATE approval_requests SET status = 'executed', "
            "approver_id = :approver, comment = :comment, "
            "decided_at = NOW() WHERE approval_id = :id"
        ),
        {
            "id": approval_id, "approver": approver.user_id,
            "comment": req.comment,
        },
    )
    await db.commit()

    # 审计:审批决策(明确区分决策者与执行身份)
    # 决策者=approver(审批人),执行身份=requester(发起人,工具层按此角色终审)
    await get_audit_logger().log(
        event_type="approval_decision",
        user_id=approver.user_id,
        session_id=row.session_id,
        payload={
            "approval_id": approval_id,
            "decision": req.decision,
            "new_status": "executed",
            "exec_success": exec_success,
            "decided_by": approver.user_id,        # 决策者:审批人
            "executed_as_user_id": row.requester_id,  # 执行身份:发起人
            "executed_as_role": requester_role,       # 发起人角色(工具层按此终审)
        },
    )

    # 通知发起人:审批已执行
    try:
        await notify_approval_result(
            db=db,
            approval_id=approval_id,
            requester_id=row.requester_id,
            session_id=row.session_id,
            result_type="executed",
            detail=exec_summary[:500],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"审批执行通知失败 {approval_id}: {e}")

    if exec_success:
        message = f"审批已通过, 工具已执行: {exec_summary}"
    else:
        # 执行失败同样记录,状态仍 executed(审批流程已走完),message 注明原因
        message = f"审批已通过, 但工具执行失败: {exec_summary}"

    return ApprovalResponse(
        approval_id=approval_id, status="executed", message=message,
    )


@router.post("/pending-executions/{approval_id}/resume", response_model=ApprovalResponse)
async def resume_pending_execution(
    approval_id: str,
    requester: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db=Depends(get_db),
):
    """发起人重新授权后恢复执行(P0-5)

    用当前登录的发起人身份(新 token)同步执行 prefill_payload 中的工具调用。
    """
    result = await db.execute(
        text(
            "SELECT approval_id, session_id, requester_id, status, "
            "prefill_payload, requester_token, approver_id, approver_roles FROM approval_requests "
            "WHERE approval_id = :id"
        ),
        {"id": approval_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(404, "审批请求不存在")

    if row.requester_id != requester.user_id:
        raise HTTPException(403, "仅原发起人可恢复执行")

    if row.status != "approved_pending_reauth":
        raise HTTPException(400, f"审批状态不允许执行: {row.status}")

    # 用发起人重新登录后的新 token 执行
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "未提供认证凭据")
    new_token = credentials.credentials
    exec_success, exec_summary, requester_role = await _execute_approval_tools(
        db, row, approver_id=row.approver_id, jwt_token_override=new_token
    )

    await db.execute(
        text(
            "UPDATE approval_requests SET status = 'executed', "
            "requester_token = :token "
            "WHERE approval_id = :id"
        ),
        {"id": approval_id, "token": new_token},
    )
    await db.commit()

    # 审计:恢复执行(执行身份=发起人,与 decide 路径一致)
    await get_audit_logger().log(
        event_type="approval_decision",
        user_id=requester.user_id,
        session_id=row.session_id,
        payload={
            "approval_id": approval_id,
            "decision": "resume",
            "new_status": "executed",
            "exec_success": exec_success,
            "decided_by": row.approver_id,  # Revalidated original approver.
            "executed_as_user_id": row.requester_id,
            "executed_as_role": requester_role,
        },
    )

    # 通知发起人:恢复执行完成
    try:
        await notify_approval_result(
            db=db,
            approval_id=approval_id,
            requester_id=row.requester_id,
            session_id=row.session_id,
            result_type="executed",
            detail=exec_summary[:500],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"恢复执行通知失败 {approval_id}: {e}")

    if exec_success:
        message = f"执行已恢复: {exec_summary}"
    else:
        message = f"执行已恢复, 但工具执行失败: {exec_summary}"

    return ApprovalResponse(
        approval_id=approval_id, status="executed", message=message,
    )


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
    事务性:同一 batch_id 内所有决策原子提交(全成功或全回滚)
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
async def batch_decide_approvals(
    req: BatchApprovalRequest,
    approver: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """批量审批决策(P0-6:pending_approvals + batch_id 事务)

    Each item is authorized independently. Successful items may be committed even
    when others fail. External tool effects are not rolled back by the database;
    atomic claiming and execution-state semantics remain C11. Returns a batch ID.
    """
    from sqlalchemy import text

    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    results: list[dict] = []
    succeeded = 0
    failed = 0

    try:
        # 事务开始:批量处理所有决策
        for item in req.approvals:
            try:
                # 查询审批请求
                result = await db.execute(
                    text(
                        "SELECT approval_id, session_id, requester_id, status, "
                        "approver_roles, requester_token, prefill_payload "
                        "FROM approval_requests WHERE approval_id = :id"
                    ),
                    {"id": item.approval_id},
                )
                row = result.fetchone()

                if row is None:
                    failed += 1
                    results.append({
                        "approval_id": item.approval_id,
                        "success": False,
                        "error": "审批请求不存在",
                    })
                    continue

                if row.status != "pending":
                    failed += 1
                    results.append({
                        "approval_id": item.approval_id,
                        "success": False,
                        "error": f"审批已处理,状态: {row.status}",
                    })
                    continue

                if item.decision == "rejected":
                    current_approver = await resolve_active_user(approver.user_id, db, lock=True)
                    _check_approver_role(row, current_approver)
                else:
                    await _authorize_approval(db, row, approver.user_id)

                # 决策处理
                exec_note = ""
                item_result_extra: dict = {}  # executed 路径才填充执行身份
                if item.decision == "rejected":
                    new_status = "rejected"
                else:
                    # approved:检查发起人 token
                    jwt_mgr = get_jwt_manager()
                    requester_token = row.requester_token or ""
                    if requester_token:
                        _check_requester_token(row, requester_token, allow_expired=True)
                    if not requester_token or jwt_mgr.is_expired(requester_token):
                        new_status = "approved_pending_reauth"
                    else:
                        # token 有效:同步执行 prefill_payload 中的工具调用
                        # 执行异常记为该条失败(不抛出,保持批量事务语义)
                        try:
                            exec_success, exec_summary, requester_role = await _execute_approval_tools(
                                db, row, approver_id=approver.user_id
                            )
                            new_status = "executed"
                            if not exec_success:
                                # 执行失败仍记 executed(审批流程已走完),备注注明原因
                                exec_note = f"工具执行失败: {exec_summary}"
                            # 记录单条执行的执行身份(批量场景同样区分决策者与执行身份)
                            item_result_extra = {
                                "executed_as_user_id": row.requester_id,
                                "executed_as_role": requester_role,
                            }
                        except Exception as e:
                            failed += 1
                            results.append({
                                "approval_id": item.approval_id,
                                "success": False,
                                "error": e.detail if isinstance(e, HTTPException) else "审批执行失败",
                                "status_code": e.status_code if isinstance(e, HTTPException) else 500,
                            })
                            continue

                await db.execute(
                    text(
                        "UPDATE approval_requests SET status = :status, "
                        "approver_id = :approver, comment = :comment, "
                        "decided_at = NOW(), batch_id = :batch_id "
                        "WHERE approval_id = :id"
                    ),
                    {
                        "id": item.approval_id,
                        "status": new_status,
                        "approver": approver.user_id,
                        "comment": req.comment,
                        "batch_id": batch_id,
                    },
                )

                succeeded += 1
                item_result = {
                    "approval_id": item.approval_id,
                    "success": True,
                    "new_status": new_status,
                }
                if exec_note:
                    item_result["note"] = exec_note
                if item_result_extra:
                    item_result.update(item_result_extra)
                results.append(item_result)

            except Exception as e:
                failed += 1
                results.append({
                    "approval_id": item.approval_id,
                    "success": False,
                    "error": e.detail if isinstance(e, HTTPException) else "审批处理失败",
                    "status_code": e.status_code if isinstance(e, HTTPException) else 500,
                })

        # Commit accepted items; authorization failures leave their approval unchanged.
        await db.commit()

        # 审计:批量审批决策
        await get_audit_logger().log(
            event_type="approval_decision",
            user_id=approver.user_id,
            payload={
                "batch_id": batch_id,
                "decision": "batch",
                "total": len(req.approvals),
                "succeeded": succeeded,
                "failed": failed,
            },
        )

        return BatchApprovalResponse(
            batch_id=batch_id,
            total=len(req.approvals),
            succeeded=succeeded,
            failed=failed,
            results=results,
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(503, "批量审批事务未完成") from None
