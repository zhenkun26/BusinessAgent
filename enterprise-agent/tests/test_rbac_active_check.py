"""越权修复:get_current_user 回查 users 表,禁用用户旧 token 立即失效"""

from __future__ import annotations

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import get_settings
from app.security.rbac import get_current_user

from conftest import FakeResult, FakeRow, FakeSession


def _make_token(role: str = "salesperson", user_id: str = "user_sales_001") -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": user_id,
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
async def test_should_fallback_to_jwt_when_db_unavailable(
    monkeypatch,
    fake_session_factory,
):
    """Given 数据库故障, When 请求,
    Then 降级 JWT 校验放行(可用性优先,并告警)"""
    session = FakeSession(responses=[FakeResult([FakeRow()])])

    class BrokenSession(FakeSession):
        async def execute(self, sql, params=None):
            raise RuntimeError("pg down")

    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(BrokenSession()),
    )
    monkeypatch.setattr(get_settings(), "auth_check_db", True)

    user = await get_current_user(_credentials(_make_token()))

    assert user.user_id == "user_sales_001"
