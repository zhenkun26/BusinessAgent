"""管理员运营 API(知识库运营闭环,仅 admin 角色可用)

提供:
- GET  /admin/knowledge-candidates            待审核知识候选列表(draft)
- POST /admin/knowledge-candidates/{id}/approve  审核通过 → 向量入库 + 置 active
- POST /admin/knowledge-candidates/{id}/reject   审核拒绝 → 置 rejected + 拒绝原因
- GET  /admin/documents                      文档台账列表(分页,支持状态过滤)

统一响应信封:{ "code": 0, "data": ..., "message": "success" }
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.database import get_db
from app.observability.audit import get_audit_logger
from app.security.rbac import AgentRole, User, require_roles


router = APIRouter(prefix="/admin", tags=["admin"])


class RejectRequest(BaseModel):
    """拒绝知识候选的请求体"""

    reject_reason: str = Field(min_length=1, max_length=500, description="拒绝原因")


class ApproveRequest(BaseModel):
    """审核通过知识候选的请求体(可选覆盖入库参数)"""

    doc_type: str = Field(default="faq", description="入库文档类型")
    dept_namespace: str = Field(default="shared_company", description="入库命名空间")


def _envelope(data, message: str = "success", code: int = 0) -> dict:
    """统一响应信封"""
    return {"code": code, "data": data, "message": message}


@router.get("/knowledge-candidates")
async def list_knowledge_candidates(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles(AgentRole.ADMIN)),
    db=Depends(get_db),
):
    """列出待审核知识候选(status=draft)"""
    rows = (
        await db.execute(
            text(
                "SELECT document_id, title, content, doc_type, dept_namespace, "
                "source_session_id, uploaded_by, created_at "
                "FROM documents WHERE status = 'draft' "
                "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {"limit": limit, "offset": offset},
        )
    ).fetchall()
    candidates = [
        {
            "document_id": r.document_id,
            "title": r.title,
            "comment": r.content or "",
            "doc_type": r.doc_type,
            "dept_namespace": r.dept_namespace,
            "source_session_id": r.source_session_id,
            "uploaded_by": r.uploaded_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return _envelope(candidates)


@router.post("/knowledge-candidates/{document_id}/approve")
async def approve_knowledge_candidate(
    document_id: str,
    req: ApproveRequest,
    user: User = Depends(require_roles(AgentRole.ADMIN)),
    db=Depends(get_db),
):
    """审核通过:内容进入向量库并将候选置为 active"""
    row = (
        await db.execute(
            text(
                "SELECT document_id, title, content, doc_type, dept_namespace, "
                "access_roles, uploaded_by FROM documents "
                "WHERE document_id = :did"
            ),
            {"did": document_id},
        )
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"知识候选不存在: {document_id}")
    if row.access_roles is None:
        raise HTTPException(409, "知识候选缺少 access_roles,无法入库")

    # 向量入库(复用 ingest 服务;失败抛 502 由全局异常兜底)
    from app.rag.ingest import MilvusIngestService

    service = MilvusIngestService()
    count = await service.ingest_text(
        document_id=document_id,
        title=row.title,
        content=row.content or row.title,
        doc_type=req.doc_type or row.doc_type or "faq",
        dept_namespace=req.dept_namespace or row.dept_namespace or "shared_company",
        access_roles=row.access_roles,
        uploaded_by=row.uploaded_by or user.user_id,
    )

    # 台账置 active + 审核信息
    await db.execute(
        text(
            "UPDATE documents SET status = 'active', reviewed_by = :reviewer, "
            "reviewed_at = CURRENT_TIMESTAMP, ingest_error = NULL, "
            "updated_at = CURRENT_TIMESTAMP WHERE document_id = :did"
        ),
        {"reviewer": user.user_id, "did": document_id},
    )
    await db.commit()

    await get_audit_logger().log(
        event_type="knowledge_approved",
        user_id=user.user_id,
        input_summary=f"审核通过知识候选 {document_id}",
        output_summary=f"已入库 {count} chunks",
        success=True,
        payload={"document_id": document_id, "chunks": count},
    )
    return _envelope(
        {
            "document_id": document_id,
            "status": "active",
            "chunks": count,
        },
        message="审核通过,已入库",
    )


@router.post("/knowledge-candidates/{document_id}/reject")
async def reject_knowledge_candidate(
    document_id: str,
    req: RejectRequest,
    user: User = Depends(require_roles(AgentRole.ADMIN)),
    db=Depends(get_db),
):
    """审核拒绝:记录拒绝原因并置为 rejected,内容不进入向量库"""
    row = (
        await db.execute(
            text("SELECT document_id FROM documents WHERE document_id = :did"),
            {"did": document_id},
        )
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"知识候选不存在: {document_id}")

    await db.execute(
        text(
            "UPDATE documents SET status = 'rejected', reject_reason = :reason, "
            "reviewed_by = :reviewer, reviewed_at = CURRENT_TIMESTAMP, "
            "updated_at = CURRENT_TIMESTAMP WHERE document_id = :did"
        ),
        {"reason": req.reject_reason, "reviewer": user.user_id, "did": document_id},
    )
    await db.commit()

    await get_audit_logger().log(
        event_type="knowledge_rejected",
        user_id=user.user_id,
        input_summary=f"拒绝知识候选 {document_id}",
        output_summary=req.reject_reason,
        success=True,
        payload={"document_id": document_id, "reject_reason": req.reject_reason},
    )
    return _envelope(
        {"document_id": document_id, "status": "rejected"},
        message="已拒绝",
    )


@router.get("/documents")
async def list_documents(
    status: Optional[str] = Query(default=None, description="状态过滤:draft/active/rejected"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles(AgentRole.ADMIN)),
    db=Depends(get_db),
):
    """文档台账列表(真实数据,分页)"""
    where_clause = "WHERE 1=1"
    params: dict = {"limit": limit, "offset": offset}
    if status:
        where_clause += " AND status = :status"
        params["status"] = status

    rows = (
        await db.execute(
            text(
                "SELECT document_id, title, doc_type, dept_namespace, status, "
                "uploaded_by, reviewed_by, reviewed_at, reject_reason, "
                "source_session_id, created_at, updated_at "
                f"FROM documents {where_clause} "
                "ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
    ).fetchall()

    total = (
        await db.execute(
            text(f"SELECT count(*) FROM documents {where_clause}"), params
        )
    ).scalar()

    items = [
        {
            "document_id": r.document_id,
            "title": r.title,
            "doc_type": r.doc_type,
            "dept_namespace": r.dept_namespace,
            "status": r.status,
            "uploaded_by": r.uploaded_by,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "reject_reason": r.reject_reason,
            "source_session_id": r.source_session_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    return _envelope(
        {"items": items, "total": total, "limit": limit, "offset": offset}
    )
