"""外部 HTTP 适配器契约测试(规格 5.2,测试桩服务)"""

from __future__ import annotations

import httpx
import pytest

from app.tools.http_adapter import call_external_api


def _transport(handler):
    """构造 httpx MockTransport 测试桩"""
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_should_return_json_when_external_api_success(monkeypatch):
    """Given 外部系统返回 200 JSON, When 调用适配器,
    Then 返回 (True, data, None) 且携带 Bearer 凭证"""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"customer": {"customer_id": "C001"}})

    original_client = httpx.AsyncClient

    def patched_client(*args, **kwargs):
        return original_client(transport=_transport(handler), **kwargs)

    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", patched_client)

    ok, data, error = await call_external_api(
        "GET",
        "https://crm.internal/api/v1/customers/C001",
        api_token="secret-token",
    )

    assert ok is True
    assert data["customer"]["customer_id"] == "C001"
    assert error is None
    assert captured["authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_should_fail_immediately_on_401_without_retry(monkeypatch):
    """Given 外部系统返回 401, When 调用适配器,
    Then 立即失败且不重试(凭证错误无需退避)"""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(401, json={"detail": "unauthorized"})

    original_client = httpx.AsyncClient

    def patched_client(*args, **kwargs):
        return original_client(transport=_transport(handler), **kwargs)

    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", patched_client)

    ok, data, error = await call_external_api(
        "GET", "https://crm.internal/api/v1/customers/C001", max_retries=3
    )

    assert ok is False
    assert attempts["count"] == 1
    assert "认证失败" in (error or "")


@pytest.mark.asyncio
async def test_should_retry_then_fail_on_5xx(monkeypatch):
    """Given 外部系统连续 5xx, When 调用适配器,
    Then 按重试次数退避后返回失败(服务不可用错误)"""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, json={"detail": "unavailable"})

    original_client = httpx.AsyncClient

    def patched_client(*args, **kwargs):
        return original_client(transport=_transport(handler), **kwargs)

    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", patched_client)
    monkeypatch.setattr("app.tools.http_adapter._backoff", lambda _: _noop())

    async def _noop():
        return None

    ok, data, error = await call_external_api(
        "GET", "https://crm.internal/api/v1/customers/C001", max_retries=2
    )

    assert ok is False
    assert attempts["count"] == 3  # 首次 + 2 次重试
    assert "服务不可用" in (error or "")


@pytest.mark.asyncio
async def test_should_fail_cleanly_on_timeout(monkeypatch):
    """Given 外部系统超时, When 调用适配器,
    Then 返回超时错误而非抛出未处理异常"""
    async def never(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(
        "app.tools.http_adapter.httpx.AsyncClient.request", never
    )
    monkeypatch.setattr("app.tools.http_adapter._backoff", lambda _: _noop())

    async def _noop():
        return None

    ok, data, error = await call_external_api(
        "GET", "https://crm.internal/api/v1/customers/C001", max_retries=1
    )

    assert ok is False
    assert "超时" in (error or "")
