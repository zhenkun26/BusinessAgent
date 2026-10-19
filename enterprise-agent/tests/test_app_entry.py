"""应用入口测试:健康检查 / server-owned request IDs / URL 容错 / CORS"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_should_serve_health_and_attach_request_id():
    """Given 应用创建成功, When 请求 /health,
    Then return health and a server-owned X-Request-ID"""
    app = create_app()
    client = TestClient(app)

    resp = client.get("/health", headers={"X-Request-ID": "trace-abc123"})

    assert resp.status_code == 200
    first_id = resp.headers["X-Request-ID"]
    assert UUID(first_id).version == 4
    assert first_id != "trace-abc123"

    resp2 = client.get("/health")
    assert UUID(resp2.headers["X-Request-ID"]).version == 4
    assert resp2.headers["X-Request-ID"] != first_id


def test_should_redirect_markdown_asterisk_url(monkeypatch):
    """Given 用户复制带 ** 的 URL, When 请求 /ui**,
    Then 307 重定向到 /ui(防 404 打不开)"""
    from app.middleware import rate_limit

    monkeypatch.setattr(rate_limit, "_use_redis", False)
    monkeypatch.setattr(rate_limit, "_memory_limiter", rate_limit.InMemoryRateLimiter())
    app = create_app()
    client = TestClient(app, follow_redirects=False)

    resp = client.get("/ui**")

    assert resp.status_code == 307
    assert resp.headers["location"] == "/ui"


def test_should_not_allow_wildcard_cors_in_production():
    """Given 生产模式 CORS 为通配符, When 配置校验,
    Then 应用启动时拒绝(校验函数抛违规项)"""
    from app.config import Settings, validate_production_settings

    settings = Settings(
        app_env="prod",
        jwt_secret_key="x" * 64,
        postgres_password="prod-pg-strong-pass-123456",
        redis_password="prod-redis-strong-pass-123456",
        milvus_password="prod-milvus-strong-pass-123456",
        cors_allow_origins="*",
    )

    violations = validate_production_settings(settings)

    assert any("CORS" in v for v in violations)


@pytest.mark.asyncio
async def test_should_configure_cors_allowlist_when_dev_origins_set(monkeypatch):
    """Given 开发模式显式 CORS 白名单, When 创建应用,
    Then CORS 中间件使用白名单而非通配"""
    monkeypatch.setattr(get_settings(), "cors_allow_origins", "http://a.test")
    app = create_app()
    client = TestClient(app)

    resp = client.options(
        "/health",
        headers={
            "Origin": "http://a.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code in (200, 405)
    allowed = resp.headers.get("access-control-allow-origin")
    assert allowed is None or allowed == "http://a.test"
