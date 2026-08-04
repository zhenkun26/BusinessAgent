"""知识候选审核与文档台账 API(知识运营规格 1.4-1.6)"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router
from app.core.database import get_db
from app.security.rbac import get_current_user
from app.security.rbac import User

from conftest import FakeResult, FakeRow, FakeSession


def _make_admin_user() -> User:
    """构造固定管理员用户"""
    return User(
        user_id="user_admin_001",
        username="管理员钱七",
        role="admin",
        department="shared_company",
        is_active=True,
    )


def _build_test_app(session: FakeSession) -> FastAPI:
    """构造仅含 admin 路由的测试应用,覆盖 get_db 与权限依赖"""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def fake_get_db():
        yield session

    async def fake_get_current_user() -> User:
        return _make_admin_user()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_current_user
    return app


@pytest.mark.asyncio
async def test_should_return_draft_candidates_when_querying_candidate_list():
    """Given 存在 draft 知识候选, When 管理员请求候选列表,
    Then 返回候选标题、评论内容、来源会话与提交用户"""
    created = datetime(2026, 8, 1, tzinfo=timezone.utc)
    candidate = FakeRow(
        document_id="doc_fb_abc",
        title="提成比例 2026 年已调整为 8%",
        content="提成比例 2026 年已调整为 8%",
        doc_type="faq",
        dept_namespace="shared_company",
        source_session_id="sess_user_sales_001_x",
        uploaded_by="user_sales_001",
        created_at=created,
    )
    session = FakeSession(responses=[FakeResult([candidate])])
    app = _build_test_app(session)
    client = TestClient(app)

    resp = client.get("/api/v1/admin/knowledge-candidates")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert len(body["data"]) == 1
    assert body["data"][0]["document_id"] == "doc_fb_abc"
    assert body["data"][0]["comment"] == "提成比例 2026 年已调整为 8%"
    assert body["data"][0]["source_session_id"] == "sess_user_sales_001_x"
    assert body["data"][0]["uploaded_by"] == "user_sales_001"


@pytest.mark.asyncio
async def test_should_reject_candidate_with_reason_when_admin_rejects():
    """Given draft 候选, When 管理员拒绝并填写原因,
    Then 状态置 rejected,记录审核人/时间/原因,且 SQL 参数化"""
    candidate = FakeRow(document_id="doc_fb_abc")
    # execute 顺序:查存在性 → 更新状态 → 审计(审计走独立 session,此处补一个空响应)
    session = FakeSession(responses=[FakeResult([candidate]), FakeResult()])
    app = _build_test_app(session)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/admin/knowledge-candidates/doc_fb_abc/reject",
        json={"reject_reason": "内容与现行政策冲突"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "rejected"
    update_sql = session.executed_sql[1]
    assert "status = 'rejected'" in update_sql
    assert "reject_reason" in update_sql
    update_params = session.executed_params[1]
    assert update_params["reason"] == "内容与现行政策冲突"
    assert update_params["reviewer"] == "user_admin_001"


@pytest.mark.asyncio
async def test_should_return_404_when_candidate_not_found():
    """Given 候选不存在, When 管理员拒绝,
    Then 返回 404 且不产生任何状态更新"""
    session = FakeSession(responses=[FakeResult()])
    app = _build_test_app(session)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/admin/knowledge-candidates/doc_missing/reject",
        json={"reject_reason": "不存在"},
    )

    assert resp.status_code == 404
    assert session.commits == 0


@pytest.mark.asyncio
async def test_should_return_paginated_ledger_when_querying_documents():
    """Given 台账有多条文档, When 管理员查询文档台账,
    Then 返回分页数据(limit/offset/total)"""
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    doc_row = FakeRow(
        document_id="doc_policy_sales",
        title="销售政策",
        doc_type="policy",
        dept_namespace="shared_company",
        status="active",
        uploaded_by="user_admin_001",
        reviewed_by=None,
        reviewed_at=None,
        reject_reason=None,
        source_session_id=None,
        created_at=now,
        updated_at=now,
    )
    session = FakeSession(
        responses=[
            FakeResult([doc_row, doc_row]),
            FakeResult([FakeRow(count=2)]),
        ]
    )
    app = _build_test_app(session)
    client = TestClient(app)

    resp = client.get("/api/v1/admin/documents?status=active&limit=20&offset=0")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["total"] == 2
    assert len(body["data"]["items"]) == 2
    assert body["data"]["limit"] == 20
    assert body["data"]["offset"] == 0
    assert "LIMIT" in session.executed_sql[0]
    assert "OFFSET" in session.executed_sql[0]


@pytest.mark.asyncio
async def test_should_approve_candidate_and_ingest_to_vector_store_when_admin_approves(
    monkeypatch,
):
    """Given draft 候选带内容与角色, When 管理员审核通过,
    Then 内容进入向量库、状态置 active、记录审核人,并落审计"""
    candidate = FakeRow(
        document_id="doc_fb_abc",
        title="提成比例 2026 年已调整为 8%",
        content="提成比例 2026 年已调整为 8%,季度阶梯计算。",
        doc_type="faq",
        dept_namespace="shared_company",
        access_roles=["salesperson", "manager", "admin"],
        uploaded_by="user_sales_001",
    )
    # execute 顺序:查候选 → 更新状态(审计走独立 session,补空响应)
    session = FakeSession(responses=[FakeResult([candidate]), FakeResult()])
    app = _build_test_app(session)
    client = TestClient(app)

    ingested: list[dict] = []

    class FakeIngestService:
        """整体打桩:避免实例化真实服务触发 pymilvus/embedding 导入"""

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def ingest_text(self, **kwargs) -> int:
            ingested.append(kwargs)
            return 2

    monkeypatch.setattr("app.rag.ingest.MilvusIngestService", FakeIngestService)

    resp = client.post(
        "/api/v1/admin/knowledge-candidates/doc_fb_abc/approve",
        json={"doc_type": "faq", "dept_namespace": "shared_company"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "active"
    assert body["data"]["chunks"] == 2
    assert len(ingested) == 1
    assert ingested[0]["document_id"] == "doc_fb_abc"
    assert ingested[0]["access_roles"] == ["salesperson", "manager", "admin"]
    update_sql = session.executed_sql[1]
    assert "status = 'active'" in update_sql
    assert "reviewed_by" in update_sql
