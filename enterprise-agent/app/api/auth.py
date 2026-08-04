"""认证 API:登录获取 JWT"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.observability.audit import get_audit_logger
from app.security.jwt_manager import JWTManager
from app.security.rbac import User, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    department: str
    expires_in: int


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录,返回 JWT"""
    # 查询用户(开发环境简化:不校验密码)
    result = await db.execute(
        select(User).where(User.username == req.username, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "用户名不存在或已禁用")

    settings = get_settings()
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user.user_id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    # 审计:登录成功
    await get_audit_logger().log(
        event_type="auth_login", user_id=user.user_id, success=True
    )

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        role=user.role,
        department=user.department,
        expires_in=int(expires_delta.total_seconds()),
    )


@router.get("/me", response_model=dict)
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(user: User = Depends(get_current_user)):
    """刷新 JWT(P0-5:token 即将过期时客户端调用此接口换新 token)

    场景:
    - 客户端检测到 token 即将过期(剩余 < 10 分钟),主动调用 /refresh
    - 审批通过后发起人 token 过期,需重新登录或调用 /refresh(若仍有效)
    - LangGraph interrupt 恢复前检查 token,过期则要求刷新

    策略:
    - 当前 token 仍有效 → 签发新 token,过期时间重置
    - 当前 token 已过期 → 返回 401,要求重新登录
    """
    from app.security.jwt_manager import get_jwt_manager

    jwt_mgr = get_jwt_manager()
    settings = get_settings()

    # 校验当前 token 仍有效(未过期)
    # 注意:get_current_user 依赖已校验签名 + 过期,到这里说明 token 仍有效
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user.user_id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    new_token = jwt_mgr.encode(payload)

    return TokenResponse(
        access_token=new_token,
        user_id=user.user_id,
        role=user.role,
        department=user.department,
        expires_in=int(expires_delta.total_seconds()),
    )
