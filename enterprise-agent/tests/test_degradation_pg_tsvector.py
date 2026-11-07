"""检索降级链第三级:PostgreSQL tsvector 检索(知识运营规格 1.3)"""

from __future__ import annotations

from datetime import datetime, timezone

import json

import pytest

from app.rag.degradation import KeywordRetriever
from app.rag.publication_visibility import publication_scope
from app.core.knowledge_publication import snapshot
from app.security.retrieval_policy import resolve_scope

from conftest import FakeResult, FakeRow, FakeSession


def _make_keyword_retriever() -> KeywordRetriever:
    """构造不依赖真实配置的 KeywordRetriever(测试不触碰 settings)"""
    retriever = object.__new__(KeywordRetriever)
    retriever._settings = None  # type: ignore[attr-defined]
    return retriever


@pytest.mark.asyncio
async def test_should_return_pg_rows_with_namespace_and_role_filters_when_milvus_fails(
    monkeypatch,
    fake_session_factory,
):
    """Given Milvus 关键词扫描抛异常, When 走 PG tsvector 降级,
    Then 返回按 ts_rank 排序的结果,且 SQL 强制命名空间与角色过滤"""
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    fake_row = FakeRow(
        document_id="doc_fb_abc",
        chunk_id="pub_abc_0000",
        uploaded_by=None,
        title="提成比例已调整为 8%",
        content="2026 年起提成比例调整为 8%,季度阶梯计算。",
        dept_namespace="shared_company",
        doc_type="faq",
        source_url="",
        updated_at=now,
        rank=0.75,
        access_roles=["salesperson"],
        status="active",
    )
    chunk = {key: getattr(fake_row, key) for key in (
        "chunk_id", "document_id", "title", "content", "dept_namespace", "doc_type",
        "source_url", "access_roles")}
    chunk["is_active"] = True
    published = FakeRow(**vars(fake_row), published_snapshot=snapshot(vars(fake_row)),
                        chunks=[chunk])
    session = FakeSession(responses=[FakeResult([published]), FakeResult([fake_row])])
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )

    retriever = _make_keyword_retriever()

    def raise_milvus_error(*args, **kwargs):
        raise RuntimeError("milvus down")

    monkeypatch.setattr(retriever, "_scan_via_milvus", raise_milvus_error)

    scope = resolve_scope("salesperson", "dept_sales")
    async with publication_scope(scope):
        results = await retriever.retrieve_by_keywords(
            query="提成比例 2026 调整为 8%", top_k=5,
            user_role="salesperson", dept_namespace="dept_sales",
        )

    assert len(results) == 1
    assert results[0].document_id == "doc_fb_abc"
    assert results[0].score == 0.75
    sql_text = session.executed_sql[1]
    assert "dept_namespace IN" in sql_text
    assert "jsonb_array_elements_text" in sql_text
    assert "access_roles" in sql_text
    assert "status = 'active'" in sql_text
    params = session.executed_params[1]
    assert json.loads(params["namespaces"]) == ["dept_sales", "shared_company"]
    assert '"salesperson"' in params["role"]


@pytest.mark.asyncio
async def test_should_report_unavailable_when_pg_query_fails(monkeypatch, fake_session_factory):
    """Given PG 查询抛异常, When 降级到 PG tsvector,
    Then fail explicitly; an unavailable store is not an empty search result"""

    class BrokenSession(FakeSession):
        async def execute(self, sql, params=None):
            raise RuntimeError("pg down")

    session = BrokenSession()
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )
    retriever = _make_keyword_retriever()

    def raise_milvus_error(*args, **kwargs):
        raise RuntimeError("milvus down")

    monkeypatch.setattr(retriever, "_scan_via_milvus", raise_milvus_error)

    with pytest.raises(RuntimeError, match="^RETRIEVAL_DATABASE_UNAVAILABLE$"):
        await retriever.retrieve_by_keywords(
            query="预算冻结线", top_k=5, user_role="finance", dept_namespace="dept_finance",
        )


@pytest.mark.asyncio
async def test_should_return_empty_when_keywords_empty(monkeypatch):
    """Given 关键词提取为空(纯停用词), When 调用关键词检索,
    Then 直接返回空列表且不访问 Milvus/PG"""
    retriever = _make_keyword_retriever()
    called: list[bool] = []

    async def should_not_be_called(*args, **kwargs):
        called.append(True)
        return []

    monkeypatch.setattr(retriever, "_scan_via_milvus", should_not_be_called)

    results = await retriever.retrieve_by_keywords(
        query="的 了 是",
        top_k=5,
        user_role="admin",
        dept_namespace="shared_company",
    )

    assert results == []
    assert called == []
