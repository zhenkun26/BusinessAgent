"""应用入口测试:健康检查 / X-Request-ID 透传 / URL 容错 / CORS"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_should_serve_health_and_attach_request_id():
    """Given 应用创建成功, When 请求 /health,
    Then 返回 healthy 且响应携带 X-Request-ID(透传/生成)"""
    app = create_app()
    client = TestClient(app)

    resp = client.get("/health", headers={"X-Request-ID": "trace-abc123"})

    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "trace-abc123"

    resp2 = client.get("/health")
    assert resp2.headers.get("X-Request-ID")  # 未透传时自动生成


def test_should_redirect_markdown_asterisk_url():
    """Given 用户复制带 ** 的 URL, When 请求 /ui**,
    Then 307 重定向到 /ui(防 404 打不开)"""
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
