"""管理员运营 API(知识库运营 + 用户生命周期,仅 admin 角色可用)

提供:
- GET  /admin/knowledge-candidates            待审核知识候选列表(draft)
- POST /admin/knowledge-candidates/{id}/approve  审核通过 → 向量入库 + 置 active
- POST /admin/knowledge-candidates/{id}/reject   审核拒绝 → 置 rejected + 拒绝原因
- GET  /admin/documents                      文档台账列表(分页,支持状态过滤)
- GET  /admin/users                          用户列表(分页,角色/状态过滤)
- POST /admin/users                          创建用户(用户名唯一,密码 bcrypt 哈希)
- PATCH /admin/users/{id}                    调整角色/部门/禁用(即时生效 + 审计)

统一响应信封:{ "code": 0, "data": ..., "message": "success" }
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.observability.audit import get_audit_logger
from app.security.rbac import AgentRole, User, require_roles
from app.security.password import hash_password


router = APIRouter(prefix="/admin", tags=["admin"])


class RejectRequest(BaseModel):
    """拒绝知识候选的请求体"""

    reject_reason: str = Field(min_length=1, max_length=500, description="拒绝原因")


class ApproveRequest(BaseModel):
    """审核通过知识候选的请求体(可选覆盖入库参数)"""

    doc_type: str = Field(default="faq", description="入库文档类型")
    dept_namespace: str = Field(default="shared_company", description="入库命名空间")


class CreateUserRequest(BaseModel):
    """创建用户请求体"""

    username: str = Field(min_length=1, max_length=128, description="登录用户名(唯一)")
    role: AgentRole = Field(description="角色:salesperson/customer_service/finance/manager/admin")
    department: Optional[str] = Field(default=None, max_length=64, description="部门命名空间")
    email: Optional[str] = Field(default=None, max_length=255, description="邮箱")
    initial_password: str = Field(min_length=8, max_length=72, description="初始密码(≥8 字符)")


class UpdateUserRequest(BaseModel):
    """更新用户请求体(至少提供一个字段)"""

    role: Optional[AgentRole] = Field(default=None, description="新角色")
    department: Optional[str] = Field(default=None, max_length=64, description="新部门(传空串清空)")
    is_active: Optional[bool] = Field(default=None, description="禁用/启用")


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


# ============ 用户生命周期(4.4-4.5) ============


@router.get("/users")
async def list_users(
    role: Optional[str] = Query(default=None, description="按角色过滤"),
    is_active: Optional[bool] = Query(default=None, description="按启用状态过滤"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles(AgentRole.ADMIN)),
    db=Depends(get_db),
):
    """用户列表(分页,支持角色/状态过滤)"""
    where_clause = "WHERE 1=1"
    params: dict = {"limit": limit, "offset": offset}
    if role:
        where_clause += " AND role = :role"
        params["role"] = role
    if is_active is not None:
        where_clause += " AND is_active = :is_active"
        params["is_active"] = is_active

    rows = (
        await db.execute(
            text(
                "SELECT user_id, username, email, role, department, is_active, "
                "created_at, updated_at "
                f"FROM users {where_clause} "
                "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
    ).fetchall()
    total = (
        await db.execute(
            text(f"SELECT count(*) FROM users {where_clause}"), params
        )
    ).scalar()
    items = [
        {
            "user_id": r.user_id,
            "username": r.username,
            "email": r.email,
            "role": r.role,
            "department": r.department,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    return _envelope(
        {"items": items, "total": total, "limit": limit, "offset": offset}
    )


@router.post("/users")
async def create_user(
    req: CreateUserRequest,
    user: User = Depends(require_roles(AgentRole.ADMIN)),
    db=Depends(get_db),
):
    """创建用户:用户名唯一(重复 409),密码只存 bcrypt 哈希"""
    user_id = f"user_{req.role.value}_{uuid.uuid4().hex[:8]}"
    password_hash = hash_password(req.initial_password)
    try:
        await db.execute(
            text(
                "INSERT INTO users (user_id, username, email, role, department, "
                "password_hash, is_active) "
                "VALUES (:user_id, :username, :email, :role, :department, "
                ":password_hash, true)"
            ),
            {
                "user_id": user_id,
                "username": req.username,
                "email": req.email,
                "role": req.role.value,
                "department": req.department,
                "password_hash": password_hash,
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, f"用户名已存在: {req.username}")

    await get_audit_logger().log(
        event_type="user_created",
        user_id=user.user_id,
        output_summary=f"创建用户 {req.username}({req.role.value})",
        success=True,
        payload={"created_user_id": user_id, "username": req.username, "role": req.role.value},
    )
    return _envelope(
        {
            "user_id": user_id,
            "username": req.username,
            "role": req.role.value,
            "department": req.department,
            "is_active": True,
        },
        message="用户创建成功",
    )


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    user: User = Depends(require_roles(AgentRole.ADMIN)),
    db=Depends(get_db),
):
    """调整用户角色/部门/启用状态(即时生效,记录旧值新值审计)"""
    if not any([req.role is not None, req.department is not None, req.is_active is not None]):
        raise HTTPException(422, "至少提供一个更新字段: role/department/is_active")

    row = (
        await db.execute(
            text("SELECT user_id, username, role, department, is_active FROM users WHERE user_id = :uid"),
            {"uid": user_id},
        )
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"用户不存在: {user_id}")

    old_values = {
        "role": row.role,
        "department": row.department,
        "is_active": row.is_active,
    }
    new_role = req.role.value if req.role is not None else row.role
    new_department = req.department if req.department is not None else row.department
    new_is_active = req.is_active if req.is_active is not None else row.is_active

    await db.execute(
        text(
            "UPDATE users SET role = :role, department = :department, "
            "is_active = :is_active, updated_at = CURRENT_TIMESTAMP "
            "WHERE user_id = :uid"
        ),
        {
            "role": new_role,
            "department": new_department,
            "is_active": new_is_active,
            "uid": user_id,
        },
    )
    await db.commit()

    new_values = {
        "role": new_role,
        "department": new_department,
        "is_active": new_is_active,
    }
    await get_audit_logger().log(
        event_type="user_updated",
        user_id=user.user_id,
        output_summary=f"更新用户 {row.username}",
        success=True,
        payload={
            "target_user_id": user_id,
            "operator": user.user_id,
            "old_values": old_values,
            "new_values": new_values,
        },
    )
    return _envelope(
        {
            "user_id": user_id,
            "username": row.username,
            "old_values": old_values,
            "new_values": new_values,
        },
        message="用户更新成功",
    )
