"""OIDC SSO 流程的离线回归测试，不连接真实 IdP 或数据库。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.auth as auth_api
from app.config import get_settings
from app.core.database import get_db
from app.security.rbac import User


class _FakeAuditLogger:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def log(self, **kwargs):
        self.events.append(kwargs)


class _FakeDb:
    pass


def _build_app(audit: _FakeAuditLogger) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_api.router)

    async def fake_get_db():
        yield _FakeDb()

    app.dependency_overrides[get_db] = fake_get_db
    return app


def _enable_sso(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    for name, value in {
        "sso_enabled": True,
        "sso_issuer": "https://idp.example.test",
        "sso_client_id": "zhiduoxing",
        "sso_client_secret": "test-secret",
        "sso_authorize_url": "https://idp.example.test/authorize",
        "sso_token_url": "https://idp.example.test/token",
        "sso_jwks_url": "https://idp.example.test/jwks",
        "sso_redirect_uri": "http://testserver/sso/callback",
        "sso_scopes": "openid profile email",
        "sso_department_claim": "department",
        "sso_default_role": "salesperson",
        "sso_default_department": "dept_sales",
    }.items():
        monkeypatch.setattr(settings, name, value)


def test_should_redirect_to_idp_with_state_and_nonce_when_sso_enabled(monkeypatch):
    _enable_sso(monkeypatch)
    audit = _FakeAuditLogger()
    monkeypatch.setattr(auth_api, "get_audit_logger", lambda: audit)
    auth_api._sso_states.clear()

    response = TestClient(_build_app(audit)).get("/sso/login", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers["location"]
    assert "response_type=code" in location
    assert "client_id=zhiduoxing" in location
    assert "state=" in location
    assert "nonce=" in location
    assert "sso_state=" in response.headers["set-cookie"]


def test_should_return_explicit_unavailable_message_when_sso_is_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "sso_enabled", False)

    response = TestClient(_build_app(_FakeAuditLogger())).get("/sso/login")

    assert response.status_code == 503
    assert "本地密码登录" in response.json()["detail"]


@pytest.mark.asyncio
async def test_should_reject_callback_when_state_cookie_does_not_match(monkeypatch):
    _enable_sso(monkeypatch)
    audit = _FakeAuditLogger()
    monkeypatch.setattr(auth_api, "get_audit_logger", lambda: audit)
    auth_api._sso_states.clear()
    state, _ = auth_api._register_sso_state()

    response = TestClient(_build_app(audit)).get(
        f"/sso/callback?code=one-time-code&state={state}",
        cookies={"sso_state": "different-state"},
    )

    assert response.status_code == 400
    assert "状态无效" in response.json()["detail"]


@pytest.mark.asyncio
async def test_should_map_existing_sso_user_and_issue_local_jwt(monkeypatch):
    _enable_sso(monkeypatch)
    audit = _FakeAuditLogger()
    monkeypatch.setattr(auth_api, "get_audit_logger", lambda: audit)
    auth_api._sso_states.clear()
    state, nonce = auth_api._register_sso_state()
    user = User(
        user_id="user_sales_001",
        username="销售员张三",
        role="salesperson",
        department="dept_sales",
        is_active=True,
        sso_issuer="https://idp.example.test",
        sso_subject="sub-001",
    )
    async def fake_exchange(code):
        return {"id_token": "opaque-test-token"}

    async def fake_verify(token, expected_nonce):
        return {"sub": "sub-001", "nonce": nonce}

    async def fake_find(db, claims):
        return user, False

    monkeypatch.setattr(auth_api, "_exchange_sso_code", fake_exchange)
    monkeypatch.setattr(auth_api, "_verify_id_token", fake_verify)
    monkeypatch.setattr(auth_api, "_find_or_provision_sso_user", fake_find)

    response = TestClient(_build_app(audit)).get(
        f"/sso/callback?code=one-time-code&state={state}",
        cookies={"sso_state": state},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "user_sales_001"
    assert body["role"] == "salesperson"
    assert any(event["event_type"] == "auth_sso_login" for event in audit.events)


@pytest.mark.asyncio
async def test_should_audit_first_sso_provisioning_without_logging_idp_token(monkeypatch):
    _enable_sso(monkeypatch)
    audit = _FakeAuditLogger()
    monkeypatch.setattr(auth_api, "get_audit_logger", lambda: audit)
    auth_api._sso_states.clear()
    state, nonce = auth_api._register_sso_state()
    user = SimpleNamespace(
        user_id="sso_123",
        username="new-user",
        role="salesperson",
        department="dept_sales",
        is_active=True,
        sso_subject="sub-new",
    )
    id_token = "do-not-log-this-token"
    async def fake_exchange(code):
        return {"id_token": id_token}

    async def fake_verify(token, expected_nonce):
        return {"sub": "sub-new", "nonce": nonce}

    async def fake_find(db, claims):
        return user, True

    monkeypatch.setattr(auth_api, "_exchange_sso_code", fake_exchange)
    monkeypatch.setattr(auth_api, "_verify_id_token", fake_verify)
    monkeypatch.setattr(auth_api, "_find_or_provision_sso_user", fake_find)

    response = TestClient(_build_app(audit)).get(
        f"/sso/callback?code=one-time-code&state={state}",
        cookies={"sso_state": state},
    )

    assert response.status_code == 200
    assert any(event["event_type"] == "user_sso_provisioned" for event in audit.events)
    assert all(id_token not in str(event) for event in audit.events)
