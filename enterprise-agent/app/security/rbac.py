"""RBAC 权限模型与 JWT 解析"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

security_scheme = HTTPBearer(auto_error=False)


class AgentRole(str, Enum):
    """角色枚举(对应 v3 方案 9.4 节)"""

    SALESPERSON = "salesperson"
    CUSTOMER_SERVICE = "customer_service"
    FINANCE = "finance"
    MANAGER = "manager"
    ADMIN = "admin"


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""

    pass


class User(Base):
    """用户表 ORM"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    department: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sso_issuer: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    sso_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# 各角色可访问的工具(对应 v3 方案 9.4 节 + W7 工具扩展)
# 工具名对应 app/tools/ 下各 Tool.name 属性
# 注:salesperson 开放 send_email_external 用于「员工发起→经理审批」协作闭环,
#     该工具 requires_approval=True,调用必建审批单,不会直接发出
ROLE_TOOLS = {
    AgentRole.SALESPERSON: [
        "query_customer", "query_order", "create_crm_task", "send_email_internal",
        "send_email_external", "query_my_approvals",
    ],
    AgentRole.CUSTOMER_SERVICE: [
        "query_customer", "create_ticket", "update_ticket", "send_email_internal",
        "query_my_approvals",
    ],
    AgentRole.FINANCE: [
        "query_order", "send_email_internal", "query_my_approvals",
    ],
    AgentRole.MANAGER: [
        "query_customer", "query_order", "create_crm_task",
        "create_ticket", "update_ticket",
        "send_email_internal", "send_email_external", "query_my_approvals",
    ],
    AgentRole.ADMIN: [
        "query_customer", "query_order", "create_crm_task",
        "create_ticket", "update_ticket",
        "send_email_internal", "send_email_external", "query_my_approvals",
    ],
}

# 各角色可访问的部门命名空间
ROLE_NAMESPACES = {
    AgentRole.ADMIN: ["*"],  # 全部
    AgentRole.MANAGER: ["dept_sales", "dept_finance", "dept_cs", "dept_hr", "shared_company"],
    AgentRole.SALESPERSON: ["dept_sales", "shared_company"],
    AgentRole.CUSTOMER_SERVICE: ["dept_cs", "shared_company"],
    AgentRole.FINANCE: ["dept_finance", "shared_company"],
}


class UserContext(BaseModel):
    """请求上下文中的用户信息"""

    user_id: str
    username: str
    role: AgentRole
    department: Optional[str] = None


def decode_identity_token(token: str, *, allow_expired: bool = False) -> dict[str, Any]:
    """Verify credentials; expiry relaxation is only for the pending-reauth decision."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"], "verify_exp": not allow_expired},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token 已过期") from None
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
        raise HTTPException(401, "Token 无效") from None
    subject = payload.get("sub")
    expiry = payload.get("exp")
    if (
        not isinstance(subject, str) or not subject.strip() or len(subject) > 64
        or isinstance(expiry, bool) or not isinstance(expiry, (int, float))
        or not 0 <= expiry <= 253402300799
    ):
        raise HTTPException(401, "Token 无效")
    return payload


async def resolve_active_user(user_id: str, db: Any, *, lock: bool = False) -> User:
    """Resolve current identity; never substitute claims or a default role."""
    from sqlalchemy import text

    if not isinstance(user_id, str) or not user_id.strip() or len(user_id) > 64:
        raise HTTPException(401, "用户不存在或已被禁用")
    try:
        row = (await db.execute(
            text("SELECT username, role, department, is_active FROM users "
                 "WHERE user_id = :uid" + (" FOR SHARE" if lock else "")),
            {"uid": user_id},
        )).fetchone()
    except Exception:
        logger.warning("Identity store unavailable; access denied")
        raise HTTPException(503, "身份服务暂不可用") from None
    if row is None or not row.is_active:
        raise HTTPException(401, "用户不存在或已被禁用")
    try:
        role = AgentRole(row.role)
    except (ValueError, TypeError):
        raise HTTPException(401, "账户权限无效") from None
    return User(user_id=user_id, username=row.username or "", role=role.value,
                department=row.department, is_active=True)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> User:
    """Authenticate with signed credentials and fail-closed current identity lookup."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "未提供认证凭据", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_identity_token(credentials.credentials)
    settings = get_settings()
    if not settings.auth_check_db:
        if not settings.is_dev:
            raise HTTPException(503, "认证配置无效")
        try:
            role = AgentRole(payload.get("role"))
        except (ValueError, TypeError):
            raise HTTPException(401, "账户权限无效") from None
        return User(user_id=payload["sub"], username=payload.get("username", ""),
                    role=role.value, department=payload.get("department"), is_active=True)
    try:
        from app.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            return await resolve_active_user(payload["sub"], session)
    except HTTPException:
        raise
    except Exception:
        logger.warning("Identity store unavailable; access denied")
        raise HTTPException(503, "身份服务暂不可用") from None


def get_user_context(user: User = Depends(get_current_user)) -> UserContext:
    """Return identity-only context; credentials remain at the authentication boundary."""
    return UserContext(
        user_id=user.user_id,
        username=user.username,
        role=AgentRole(user.role),
        department=user.department,
    )


def require_roles(*allowed_roles: AgentRole):
    """角色守卫装饰器"""

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if AgentRole(user.role) not in allowed_roles:
            raise HTTPException(403, f"角色 {user.role} 无权限访问此资源")
        return user

    return role_checker


def can_access_namespace(role: AgentRole, namespace: str) -> bool:
    """检查角色是否能访问指定命名空间"""
    allowed = ROLE_NAMESPACES.get(role, [])
    return "*" in allowed or namespace in allowed


def can_use_tool(role: AgentRole, tool_name: str) -> bool:
    """检查角色是否能使用指定工具"""
    allowed = ROLE_TOOLS.get(role, [])
    return tool_name in allowed
