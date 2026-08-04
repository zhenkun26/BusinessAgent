"""认证加固:bcrypt 密码校验(生产开关)"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router
from app.config import get_settings
from app.core.database import get_db
from app.observability.audit import get_audit_logger
from app.security.password import hash_password

from conftest import FakeResult, FakeRow, FakeSession


def _make_user_row(password_hash: str | None) -> FakeRow:
    return FakeRow(
        user_id="user_sales_001",
        username="销售员张三",
        role="salesperson",
        department="dept_sales",
        is_active=True,
        password_hash=password_hash,
    )


def _build_app(session: FakeSession, audit_events: list[dict]) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def fake_get_db():
        yield session

    class FakeAuditLogger:
        async def log(self, **kwargs):
            audit_events.append(kwargs)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_audit_logger] = lambda: FakeAuditLogger()
    return app


@pytest.mark.asyncio
async def test_should_accept_any_password_when_require_password_disabled(
    monkeypatch,
):
    """Given AUTH_REQUIRE_PASSWORD=false(演示默认), When 任意密码登录,
    Then 登录成功签发 token(保持既有演示行为,向后兼容)"""
    monkeypatch.setattr(get_settings(), "auth_require_password", False)
    user_row = _make_user_row(password_hash=hash_password("正确密码"))
    session = FakeSession(responses=[FakeResult([user_row])])
    app = _build_app(session, audit_events := [])
    client = TestClient(app)

    resp = client.post(
        "/login",
        json={"username": "销售员张三", "password": "任意密码都行"},
    )

    assert resp.status_code == 200
    assert resp.json()["role"] == "salesperson"


@pytest.mark.asyncio
async def test_should_reject_wrong_password_when_require_password_enabled(
    monkeypatch,
):
    """Given AUTH_REQUIRE_PASSWORD=true, When 提交错误密码,
    Then 返回统一 401,不签发 token"""
    monkeypatch.setattr(get_settings(), "auth_require_password", True)
    user_row = _make_user_row(password_hash=hash_password("正确密码"))
    session = FakeSession(responses=[FakeResult([user_row])])
    app = _build_app(session, audit_events := [])
    client = TestClient(app)

    resp = client.post(
        "/login",
        json={"username": "销售员张三", "password": "错误密码"},
    )

    assert resp.status_code == 401
    assert "token" not in resp.json()


@pytest.mark.asyncio
async def test_should_return_same_message_when_user_missing_or_password_wrong(
    monkeypatch,
):
    """Given 用户不存在 vs 密码错误, When 分别登录,
    Then 401 文案完全一致(防账号枚举)"""
    monkeypatch.setattr(get_settings(), "auth_require_password", True)

    missing_user_session = FakeSession(responses=[FakeResult([])])
    app_missing = _build_app(missing_user_session, audit_missing := [])
    resp_missing = TestClient(app_missing).post(
        "/login",
        json={"username": "不存在的人", "password": "x"},
    )

    wrong_pw_session = FakeSession(
        responses=[FakeResult([_make_user_row(hash_password("正确密码"))])]
    )
    app_wrong = _build_app(wrong_pw_session, audit_wrong := [])
    resp_wrong = TestClient(app_wrong).post(
        "/login",
        json={"username": "销售员张三", "password": "错误密码"},
    )

    assert resp_missing.status_code == 401
    assert resp_wrong.status_code == 401
    assert resp_missing.json()["detail"] == resp_wrong.json()["detail"]


@pytest.mark.asyncio
async def test_should_accept_correct_password_when_require_password_enabled(
    monkeypatch,
):
    """Given AUTH_REQUIRE_PASSWORD=true 且密码正确, When 登录,
    Then 签发 token"""
    monkeypatch.setattr(get_settings(), "auth_require_password", True)
    user_row = _make_user_row(password_hash=hash_password("正确密码"))
    session = FakeSession(responses=[FakeResult([user_row])])
    app = _build_app(session, audit_events := [])
    client = TestClient(app)

    resp = client.post(
        "/login",
        json={"username": "销售员张三", "password": "正确密码"},
    )

    assert resp.status_code == 200
    assert resp.json()["user_id"] == "user_sales_001"
