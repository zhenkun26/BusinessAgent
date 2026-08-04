"""RBAC 权限模型与 JWT 解析"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
    jwt_token: str


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> User:
    """FastAPI 依赖:从 JWT 解析当前用户"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    settings = get_settings()

    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token 已过期")
    except jwt.PyJWTError:
        raise HTTPException(401, "Token 无效")

    # 返回简化用户对象(避免每次查库)
    return User(
        user_id=payload["sub"],
        username=payload.get("username", ""),
        role=payload.get("role", "salesperson"),
        department=payload.get("department"),
        is_active=True,
    )


def get_user_context(user: User = Depends(get_current_user)) -> UserContext:
    """获取完整用户上下文(含 jwt_token)"""
    return UserContext(
        user_id=user.user_id,
        username=user.username,
        role=AgentRole(user.role),
        department=user.department,
        jwt_token="",  # 由调用方填充
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
