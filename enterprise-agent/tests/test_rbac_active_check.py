"""越权修复:get_current_user 回查 users 表,禁用用户旧 token 立即失效"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import get_settings
from app.security.rbac import decode_identity_token, get_current_user

from conftest import FakeResult, FakeRow, FakeSession


def _make_token(role: str = "salesperson", user_id: str = "user_sales_001") -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "username": "测试用户",
            "role": role,
            "department": "dept_sales",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="bearer", credentials=token)


@pytest.mark.asyncio
async def test_should_reject_disabled_user_with_stale_token_when_checking_db(
    monkeypatch,
    fake_session_factory,
):
    """Given 用户已被禁用但持有旧 token, When 访问受保护接口,
    Then 返回 401(禁用即时生效,不再信任 token 内 is_active)"""
    session = FakeSession(
        responses=[
            FakeResult(
                [
                    FakeRow(
                        username="销售员张三",
                        role="salesperson",
                        department="dept_sales",
                        is_active=False,
                    )
                ]
            )
        ]
    )
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )
    monkeypatch.setattr(get_settings(), "auth_check_db", True)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_credentials(_make_token()))

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_should_use_db_role_when_user_active(
    monkeypatch,
    fake_session_factory,
):
    """Given 用户启用且 token 中角色陈旧, When 请求,
    Then 使用数据库最新角色(角色变更即时生效)"""
    session = FakeSession(
        responses=[
            FakeResult(
                [
                    FakeRow(
                        username="销售员张三",
                        role="manager",
                        department="dept_sales",
                        is_active=True,
                    )
                ]
            )
        ]
    )
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )
    monkeypatch.setattr(get_settings(), "auth_check_db", True)

    user = await get_current_user(_credentials(_make_token(role="salesperson")))

    assert user.role == "manager"


@pytest.mark.asyncio
async def test_should_fail_closed_when_db_unavailable(
    monkeypatch,
    fake_session_factory,
):
    """Given 数据库故障, When 请求,
    Then 返回 503,不使用旧 JWT 身份兜底"""
    class BrokenSession(FakeSession):
        async def execute(self, sql, params=None):
            raise RuntimeError("pg down")

    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(BrokenSession()),
    )
    monkeypatch.setattr(get_settings(), "auth_check_db", True)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_credentials(_make_token()))

    assert exc_info.value.status_code == 503


@pytest.mark.parametrize("payload", [
    {"sub": "user_sales_001"},
    {"exp": 4102444800},
    {"sub": "", "exp": 4102444800},
    {"sub": [], "exp": 4102444800},
    {"sub": "x" * 65, "exp": 4102444800},
    {"sub": "user_sales_001", "exp": "4102444800"},
    {"sub": "user_sales_001", "exp": float("nan")},
    {"sub": "user_sales_001", "exp": float("inf")},
    {"sub": "user_sales_001", "exp": True},
    {"sub": "user_sales_001", "exp": 10 ** 100},
    {"sub": "user_sales_001", "exp": 1},
])
def test_should_reject_invalid_claims_with_real_jwt_library(payload):
    settings = get_settings()
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(HTTPException) as caught:
        decode_identity_token(token)
    assert caught.value.status_code == 401


def test_should_verify_signature_even_for_expired_reauth_token():
    settings = get_settings()
    payload = {"sub": "user_sales_001", "exp": 1}
    signed = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert decode_identity_token(signed, allow_expired=True)["sub"] == "user_sales_001"
    forged = jwt.encode(payload, "synthetic-wrong-signing-key", algorithm=settings.jwt_algorithm)
    with pytest.raises(HTTPException) as caught:
        decode_identity_token(forged, allow_expired=True)
    assert caught.value.status_code == 401
