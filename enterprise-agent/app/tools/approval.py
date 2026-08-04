"""审批进度查询工具(QUERY 类)

让发起人能在对话里查询自己发起的审批单进度，
配合「我的审批」页签，构成发起人视角的完整反馈闭环。
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import text

from app.tools.base import BaseTool, ToolCategory, ToolResult


class QueryMyApprovalsSchema(BaseModel):
    """查询我的审批进度入参"""

    status: Optional[str] = Field(
        default=None,
        description="按状态过滤：pending(待审批)/ executed(已执行)/ rejected(已拒绝)，不填返回全部",
    )
    limit: int = Field(default=10, ge=1, le=50, description="返回条数，默认 10")


# 状态中文映射,让 LLM 生成回答时直接用
_STATUS_LABELS = {
    "pending": "待审批",
    "executed": "已批准并执行",
    "approved": "已批准",
    "rejected": "已拒绝",
    "approved_pending_reauth": "已批准，待重新授权恢复执行",
    "timeout": "已超时",
}


class QueryMyApprovalsTool(BaseTool):
    """查询当前用户发起的审批请求进度(QUERY 类，无副作用)"""

    name = "query_my_approvals"
    category = ToolCategory.QUERY
    description = "查询我发起的审批单的进度和结果(待审批/已执行/已拒绝)"
    input_schema = QueryMyApprovalsSchema

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        from app.core.database import get_session_factory

        user_id = context.get("user_id")
        if not user_id:
            return ToolResult(
                success=False,
                tool_name=self.name,
                output={},
                error="缺少用户身份，无法查询审批进度",
            )

        sql = (
            "SELECT approval_id, operation_type, risk_level, summary, status, "
            "approver_id, comment, created_at, decided_at "
            "FROM approval_requests WHERE requester_id = :uid"
        )
        bind: dict[str, Any] = {"uid": user_id}
        if params.get("status"):
            sql += " AND status = :status"
            bind["status"] = params["status"]
        sql += " ORDER BY created_at DESC LIMIT :limit"
        bind["limit"] = params.get("limit", 10)

        # Mock: 模拟 API 调用延迟
        await asyncio.sleep(0.1)

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(text(sql), bind)
            rows = result.fetchall()

        items = [
            {
                "approval_id": r.approval_id,
                "operation_type": r.operation_type,
                "risk_level": r.risk_level,
                "summary": r.summary,
                "status": r.status,
                "status_label": _STATUS_LABELS.get(r.status, r.status),
                "approver_id": r.approver_id,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            }
            for r in rows
        ]

        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"total": len(items), "approvals": items},
        )
