"""认证 API:本地密码登录与企业 OIDC SSO。"""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.runtime_state import (
    RuntimeStateUnavailable, SSO_STATE_TTL_SECONDS as _SSO_STATE_TTL_SECONDS,
    register_sso_state as _register_sso_state, consume_sso_state as _consume_sso_state,
)
from app.observability.audit import get_audit_logger
from app.security.jwt_manager import get_jwt_manager
from app.security.password import hash_password, verify_password
from app.security.rbac import AgentRole, User, get_current_user

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


def _issue_token(user: User) -> TokenResponse:
    """按既有本地登录口径签发本系统 JWT。"""
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": user.user_id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "exp": now + expires_delta,
        "iat": now,
    }
    token = get_jwt_manager().encode(payload)
    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
        role=user.role,
        department=user.department or "",
        expires_in=int(expires_delta.total_seconds()),
    )


def _sso_error(status_code: int, detail: str) -> JSONResponse:
    """返回不泄露令牌内容的 SSO 错误，并清除一次性状态 Cookie。"""
    response = JSONResponse(status_code=status_code, content={"detail": detail})
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.delete_cookie("sso_state")
    return response


def _require_sso_config() -> None:
    """检查 SSO 是否显式启用且配置完整。"""
    settings = get_settings()
    if not settings.sso_enabled:
        raise HTTPException(503, "企业 SSO 尚未启用，请使用本地密码登录")
    required = (
        "sso_issuer",
        "sso_client_id",
        "sso_client_secret",
        "sso_authorize_url",
        "sso_token_url",
        "sso_jwks_url",
        "sso_redirect_uri",
    )
    if any(not getattr(settings, name).strip() for name in required):
        raise HTTPException(503, "企业 SSO 配置不完整，请联系管理员")
    from app.security.oidc import OIDCError, configuration
    try:
        configuration(settings)
    except OIDCError as exc:
        raise HTTPException(exc.status, exc.code) from None


def _append_query(url: str, params: dict[str, str]) -> str:
    """在保留已有查询参数的前提下构造授权地址。"""
    parsed = urlsplit(url)
    query = parsed.query
    extra = urlencode(params)
    query = f"{query}&{extra}" if query else extra
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


async def _exchange_sso_code(code: str, verifier: str) -> dict:
    from app.security.oidc import OIDCError, exchange
    try:
        return await exchange(get_settings(), code, verifier)
    except OIDCError as exc:
        raise HTTPException(exc.status, exc.code) from None


async def _verify_id_token(id_token: str, expected_nonce: str) -> dict:
    from app.security.oidc import OIDCError, verify
    try:
        return await verify(get_settings(), id_token, expected_nonce)
    except OIDCError as exc:
        raise HTTPException(exc.status, exc.code) from None


def _claim_text(claims: dict, name: str, max_length: int) -> str:
    """读取并限制不可信 OIDC claim，避免把任意对象写入用户字段。"""
    value = claims.get(name)
    if isinstance(value, list):
        value = value[0] if value else ""
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


async def _find_or_provision_sso_user(
    db: AsyncSession, claims: dict
) -> tuple[User, bool]:
    """按 issuer/sub 查找用户，未命中时以最低默认角色创建。"""
    settings = get_settings()
    from app.security.oidc import OIDCError, exact_text
    try:
        issuer = exact_text(settings.sso_issuer, 512)
        subject = exact_text(claims.get("sub"), 255)
        if claims.get("iss") != issuer:
            raise OIDCError()
    except OIDCError:
        raise HTTPException(401, "SSO_IDENTITY_INVALID") from None
    identity_hash = hashlib.sha256(json.dumps([issuer, subject], ensure_ascii=False,
                                  separators=(",", ":")).encode()).hexdigest()
    result = await db.execute(
        select(User).where(User.sso_issuer == issuer, User.sso_subject == subject)
    )
    user = result.scalar_one_or_none()
    if user is not None:
        if not user.is_active:
            raise HTTPException(401, "用户不存在或已被禁用")
        return user, False

    try:
        if settings.sso_default_role != "salesperson":
            raise ValueError
        role = AgentRole.SALESPERSON.value
    except ValueError:
        raise HTTPException(503, "SSO 默认角色配置无效，请联系管理员")
    email = _claim_text(claims, "email", 255) or None
    username = (
        _claim_text(claims, "preferred_username", 128)
        or _claim_text(claims, "email", 128)
        or _claim_text(claims, "name", 128)
        or f"sso_{identity_hash[:16]}"
    )
    # 用户名可能与本地账号冲突；不覆盖既有本地账号。
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        suffix = identity_hash[:8]
        username = f"{username[:119]}_{suffix}"
    department = (
        settings.sso_default_department
        or None
    )
    user = User(
        user_id=f"sso_{identity_hash[:24]}",
        username=username,
        email=email,
        role=role,
        department=department,
        # 现有 users.password_hash 在生产 schema 中为 NOT NULL；随机不可知密码
        # 保证 SSO 账号不能被本地密码路径意外登录。
        password_hash=hash_password(secrets.token_urlsafe(32)),
        sso_issuer=issuer,
        sso_subject=subject,
        is_active=True,
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(User).where(User.sso_issuer == issuer, User.sso_subject == subject)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(503, "SSO 用户映射冲突，请稍后重试")
        if not user.is_active:
            raise HTTPException(401, "用户不存在或已被禁用")
        return user, False
    return user, True


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录,返回 JWT

    认证策略:
    - AUTH_REQUIRE_PASSWORD=false(演示默认):保留"密码任意"兼容,仅校验用户存在与启用
    - AUTH_REQUIRE_PASSWORD=true(生产):校验 bcrypt 密码;错误/缺失统一 401,
      文案与"用户不存在"一致,防止账号枚举
    """
    # 查询用户(启用/禁用均查询,统一 401 文案防枚举)
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    user = result.scalar_one_or_none()

    settings = get_settings()
    auth_ok = user is not None and user.is_active
    if auth_ok and (settings.auth_require_password or getattr(user, "sso_subject", None)):
        auth_ok = verify_password(req.password, user.password_hash or "")
    if not auth_ok:
        # 统一文案:不区分"用户不存在"与"密码错误"
        raise HTTPException(401, "用户名或密码错误")

    # 审计:登录成功
    await get_audit_logger().log(
        event_type="auth_login", user_id=user.user_id, success=True
    )
    return _issue_token(user)


@router.get("/sso/login")
async def sso_login():
    """跳转企业 IdP，使用授权码流程开始 SSO。"""
    _require_sso_config()
    settings = get_settings()
    try:
        from app.security.oidc import challenge
        verifier = secrets.token_urlsafe(32)
        state, nonce = await _register_sso_state(verifier=verifier)
    except RuntimeStateUnavailable:
        return _sso_error(503, "RUNTIME_STATE_UNAVAILABLE")
    redirect_url = _append_query(
        settings.sso_authorize_url,
        {
            "response_type": "code",
            "client_id": settings.sso_client_id,
            "redirect_uri": settings.sso_redirect_uri,
            "scope": settings.sso_scopes.strip() or "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge(verifier),
            "code_challenge_method": "S256",
        },
    )
    response = RedirectResponse(url=redirect_url, status_code=307)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.set_cookie(
        "sso_state",
        state,
        max_age=_SSO_STATE_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/sso/callback", response_model=TokenResponse)
async def sso_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """处理 IdP 回调、验证 ID Token 并签发本系统 JWT。"""
    try:
        _require_sso_config()
    except HTTPException as exc:
        return _sso_error(exc.status_code, str(exc.detail))

    cookie_state = request.cookies.get("sso_state")
    if (not state or not (code or error) or not cookie_state
            or not secrets.compare_digest(state.encode(), cookie_state.encode())):
        return _sso_error(400, "SSO 回调状态无效，请重新发起登录")
    try:
        binding = await _consume_sso_state(state, with_verifier=True)
    except RuntimeStateUnavailable:
        return _sso_error(503, "RUNTIME_STATE_UNAVAILABLE")
    if binding is None:
        return _sso_error(400, "SSO 登录已过期，请重新发起登录")
    if error:
        await get_audit_logger().log(
            event_type="auth_sso_login", success=False, payload={"reason": "idp_error"}
        )
        return _sso_error(401, "企业 IdP 认证未完成，请使用本地密码登录")

    try:
        token_payload = await _exchange_sso_code(code, binding["verifier"])
        claims = await _verify_id_token(token_payload["id_token"], binding["nonce"])
        user, provisioned = await _find_or_provision_sso_user(db, claims)
    except HTTPException as exc:
        await get_audit_logger().log(
            event_type="auth_sso_login", success=False, payload={"reason": str(exc.detail)}
        )
        return _sso_error(exc.status_code, str(exc.detail))

    if provisioned:
        await get_audit_logger().log(
            event_type="user_sso_provisioned",
            user_id=user.user_id,
            success=True,
            payload={
                "issuer": get_settings().sso_issuer,
                "subject_sha256": hashlib.sha256(user.sso_subject.encode()).hexdigest(),
            },
        )
    await get_audit_logger().log(
        event_type="auth_sso_login",
        user_id=user.user_id,
        success=True,
        payload={"issuer": get_settings().sso_issuer, "provisioned": provisioned},
    )
    token_response = _issue_token(user)
    if "text/html" in request.headers.get("accept", ""):
        # 供浏览器直接跳转的 SSO 入口使用；令牌只在 HTTPS 响应体中短暂交给
        # 当前页面，不放入 URL，随后立即回到 /ui。
        browser_payload = {**token_response.model_dump(), "username": user.username}
        payload = json.dumps(browser_payload, ensure_ascii=False)
        payload = (
            payload.replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029")
        )
        response = HTMLResponse(
            content=(
                "<!doctype html><meta charset='utf-8'>"
                "<title>SSO 登录成功</title><p>登录成功，正在返回智多星…</p>"
                f"<script>const d={payload};"
                "sessionStorage.setItem('ea_sso_once',JSON.stringify(d));"
                "location.replace('/ui');</script>"
            )
        )
    else:
        response = JSONResponse(content=token_response.model_dump())
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.delete_cookie("sso_state")
    return response


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
    expire = datetime.now(UTC) + expires_delta

    payload = {
        "sub": user.user_id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    new_token = jwt_mgr.encode(payload)

    return TokenResponse(
        access_token=new_token,
        user_id=user.user_id,
        role=user.role,
        department=user.department,
        expires_in=int(expires_delta.total_seconds()),
    )
