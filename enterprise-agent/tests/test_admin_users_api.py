"""用户生命周期管理 API 测试(规格 4.4-4.6)"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router
from app.core.database import get_db
from app.security.rbac import User, get_current_user

from conftest import FakeResult, FakeRow, FakeSession


def _build_app(
    monkeypatch,
    session: FakeSession,
    audit_events: list[dict],
) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def fake_get_db():
        yield session

    async def fake_get_current_user() -> User:
        return User(
            user_id="user_admin_001",
            username="管理员钱七",
            role="admin",
            department="shared_company",
            is_active=True,
        )

    class FakeAuditLogger:
        async def log(self, **kwargs):
            audit_events.append(kwargs)

    monkeypatch.setattr(
        "app.api.admin.get_audit_logger", lambda: FakeAuditLogger()
    )
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_current_user
    return app


@pytest.mark.asyncio
async def test_should_return_409_when_username_duplicated(monkeypatch):
    """Given 用户名已存在, When 管理员创建同名校,
    Then 返回 409 且不创建用户"""
    from sqlalchemy.exc import IntegrityError

    class DuplicateSession(FakeSession):
        async def execute(self, sql, params=None):
            self.executed_sql.append(str(sql))
            self.executed_params.append(params or {})
            raise IntegrityError("dup", {}, Exception("duplicate key"))

    session = DuplicateSession()
    app = _build_app(monkeypatch, session, audit_events := [])
    client = TestClient(app)

    resp = client.post(
        "/api/v1/admin/users",
        json={
            "username": "销售员张三",
            "role": "salesperson",
            "department": "dept_sales",
            "initial_password": "StrongPass123!",
        },
    )

    assert resp.status_code == 409
    assert "已存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_should_create_user_with_hashed_password_when_admin_creates(monkeypatch):
    """Given 管理员创建用户, When 请求成功,
    Then 密码以 bcrypt 哈希入库(SQL 不出现明文)并落审计"""
    session = FakeSession(responses=[FakeResult()])
    app = _build_app(monkeypatch, session, audit_events := [])
    client = TestClient(app)

    resp = client.post(
        "/api/v1/admin/users",
        json={
            "username": "新同事",
            "role": "finance",
            "department": "dept_finance",
            "email": "new@example.com",
            "initial_password": "InitialPass123!",
        },
    )

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["role"] == "finance"
    assert body["is_active"] is True
    insert_sql = session.executed_sql[0]
    assert "INSERT INTO users" in insert_sql
    params = session.executed_params[0]
    assert params["password_hash"].startswith("$2b$")
    assert "InitialPass123!" not in insert_sql
    assert audit_events[0]["event_type"] == "user_created"


@pytest.mark.asyncio
async def test_should_update_user_and_record_old_new_values_when_admin_patches(
    monkeypatch,
):
    """Given 用户存在, When 管理员禁用/改角色,
    Then 更新生效且审计记录操作者、旧值、新值"""
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    existing = FakeRow(
        user_id="user_sales_001",
        username="销售员张三",
        role="salesperson",
        department="dept_sales",
        is_active=True,
    )
    session = FakeSession(responses=[FakeResult([existing]), FakeResult()])
    app = _build_app(monkeypatch, session, audit_events := [])
    client = TestClient(app)

    resp = client.patch(
        "/api/v1/admin/users/user_sales_001",
        json={"role": "manager", "is_active": False},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["old_values"]["role"] == "salesperson"
    assert data["new_values"]["role"] == "manager"
    assert data["new_values"]["is_active"] is False
    update_params = session.executed_params[0]
    assert update_params["uid"] == "user_sales_001"
    assert audit_events[0]["event_type"] == "user_updated"
    payload = audit_events[0]["payload"]
    assert payload["operator"] == "user_admin_001"
    assert payload["old_values"]["role"] == "salesperson"
    assert payload["new_values"]["role"] == "manager"


@pytest.mark.asyncio
async def test_should_return_404_when_updating_missing_user(monkeypatch):
    """Given 用户不存在, When 管理员更新,
    Then 返回 404 且不产生更新"""
    session = FakeSession(responses=[FakeResult()])
    app = _build_app(monkeypatch, session, audit_events := [])
    client = TestClient(app)

    resp = client.patch(
        "/api/v1/admin/users/user_missing",
        json={"is_active": False},
    )

    assert resp.status_code == 404
