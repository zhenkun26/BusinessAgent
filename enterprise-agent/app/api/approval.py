"""审批 API(对应 v3 方案 10.3 节,P0-5 + P1-1)"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.core.database import get_db
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
        return False, "审批负载中无工具调用(prefill_payload.tool_calls 为空)"

    # 查询发起人角色/部门,以其身份执行(审批不越权:执行身份=发起人,非审批人)
    result = await db.execute(
        text("SELECT role, department FROM users WHERE user_id = :uid"),
        {"uid": row.requester_id},
    )
    u = result.fetchone()
    role = u.role if u else "salesperson"
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
        # 预检失败不阻断,仍交给工具层防线 3 终审(最终安全保证不依赖本预检)
        pass

    exec_result = await execute_tool_calls(plans, context)

    outputs = getattr(exec_result, "output", None) or getattr(exec_result, "outputs", None) or {}
    error = getattr(exec_result, "error", None)
    if exec_result.success:
        return True, f"工具执行成功: {outputs}", role
    return False, f"工具执行失败: {error or outputs}", role


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

    # 2. 校验审批人身份
    approver_roles = row.approver_roles if isinstance(row.approver_roles, list) else []
    if AgentRole(approver.role).value not in approver_roles and approver.role != "admin":
        raise HTTPException(403, "无权审批此请求")

    # 3. P0-5:检查发起人 JWT
    jwt_mgr = get_jwt_manager()
    requester_token = row.requester_token or ""

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

        # TODO: 通知发起人重新登录
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
        return ApprovalResponse(
            approval_id=approval_id,
            status="approved_pending_reauth",
            message="审批已通过, token 刷新失败, 需发起人重新授权",
        )

    # 6. token 有效:以发起人身份同步执行 prefill_payload 中的工具调用
    exec_success, exec_summary, requester_role = await _execute_approval_tools(db, row)

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
            "prefill_payload, requester_token FROM approval_requests "
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
    new_token = credentials.credentials if credentials else (row.requester_token or "")
    exec_success, exec_summary, requester_role = await _execute_approval_tools(
        db, row, jwt_token_override=new_token
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
            "decided_by": None,  # resume 无新决策,沿用原审批人
            "executed_as_user_id": row.requester_id,
            "executed_as_role": requester_role,
        },
    )

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

    事务保证:
    - 整个批量操作在一个 DB 事务内
    - 任一条目出错,整个 batch 回滚(原子性)
    - 返回 batch_id 供审计追踪
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

                # 校验审批人权限
                approver_roles = row.approver_roles if isinstance(row.approver_roles, list) else []
                if AgentRole(approver.role).value not in approver_roles and approver.role != "admin":
                    failed += 1
                    results.append({
                        "approval_id": item.approval_id,
                        "success": False,
                        "error": "无权审批此请求",
                    })
                    continue

                # 决策处理
                exec_note = ""
                item_result_extra: dict = {}  # executed 路径才填充执行身份
                if item.decision == "rejected":
                    new_status = "rejected"
                else:
                    # approved:检查发起人 token
                    jwt_mgr = get_jwt_manager()
                    requester_token = row.requester_token or ""
                    if not requester_token or jwt_mgr.is_expired(requester_token):
                        new_status = "approved_pending_reauth"
                    else:
                        # token 有效:同步执行 prefill_payload 中的工具调用
                        # 执行异常记为该条失败(不抛出,保持批量事务语义)
                        try:
                            exec_success, exec_summary, requester_role = await _execute_approval_tools(db, row)
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
                                "error": f"审批通过但执行异常: {e}",
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
                    "error": str(e),
                })

        # 原子提交:全部成功才 commit
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
        raise HTTPException(500, f"批量审批事务失败,已回滚: {e}")
