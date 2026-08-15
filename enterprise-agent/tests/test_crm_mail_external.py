"""CRM/邮件真实路径的本地 HTTP 契约回归测试。

测试只使用 httpx.MockTransport，不连接真实 CRM、邮件系统或生产凭证。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.config import get_settings
from app.tools.base import ToolResult
from app.tools.crm import CreateCrmTaskTool, QueryCustomerTool, QueryOrderTool
from app.tools.mail import SendEmailExternalTool, SendEmailInternalTool

HttpHandler = Callable[[httpx.Request], httpx.Response]


class _RecordingAuditLogger:
    async def log_tool_call(self, **kwargs: Any) -> None:
        return None

    async def log(self, **kwargs: Any) -> None:
        return None

    async def log_violation(self, **kwargs: Any) -> None:
        return None


def _patch_http_transport(monkeypatch: pytest.MonkeyPatch, handler: HttpHandler) -> None:
    original_client = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return original_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    async def _noop_backoff(attempt: int) -> None:
        return None

    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", patched_client)
    monkeypatch.setattr("app.tools.http_adapter._backoff", _noop_backoff)
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: _RecordingAuditLogger())


@pytest.mark.asyncio
async def test_crm_create_reuses_idempotency_key_across_http_retry(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tool_provider", "mock")
    monkeypatch.setattr(settings, "crm_tool_provider", "http")
    keys: list[str | None] = []
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        keys.append(request.headers.get("Idempotency-Key"))
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"task": {"task_id": "CT-9001"}})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateCrmTaskTool()
    result = await tool.invoke(
        {"customer_id": "C001", "title": "季度回访"},
        {
            "role": "admin",
            "user_id": "u1",
            "request_id": "req-crm-001",
            "tool_call_index": 2,
        },
        skip_rbac=True,
    )

    assert result.success is True
    assert attempts == 2
    assert keys[0] == keys[1] == "crm-task-req-crm-001-2"
    assert result.side_effects["idempotency_key"] == keys[0]
    assert result.side_effects["external_attempts"] == 2
    assert result.compensation_data["provider"] == "http"


@pytest.mark.asyncio
async def test_crm_queries_keep_mock_output_shape_in_http_mode(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "crm_tool_provider", "http")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/customers/C001"):
            return httpx.Response(200, json={"customer": {"customer_id": "C001", "level": "VIP"}})
        return httpx.Response(
            200,
            json={"order": {"order_id": "ORD-2026-001", "status": "completed", "items": []}},
        )

    _patch_http_transport(monkeypatch, handler)
    customer = await QueryCustomerTool().invoke(
        {"customer_id": "C001"}, {"role": "admin"}, skip_rbac=True
    )
    order = await QueryOrderTool().invoke(
        {"order_id": "ORD-2026-001", "include_items": True},
        {"role": "admin"},
        skip_rbac=True,
    )

    assert customer.success is True
    assert customer.output == {"customer": {"customer_id": "C001", "level": "VIP"}}
    assert customer.side_effects["external_attempts"] == 1
    assert order.success is True
    assert order.output["order"]["order_id"] == "ORD-2026-001"


@pytest.mark.asyncio
async def test_crm_query_returns_structured_auth_failure_without_retry(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "crm_tool_provider", "http")
    monkeypatch.setattr(settings, "external_max_retries", 3)
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"detail": "secret-token-invalid"})

    _patch_http_transport(monkeypatch, handler)
    result = await QueryCustomerTool().invoke(
        {"customer_id": "C001"}, {"role": "admin"}, skip_rbac=True
    )

    assert result.success is False
    assert attempts == 1
    assert "认证失败" in (result.error or "")
    assert "secret-token-invalid" not in (result.error or "")


@pytest.mark.asyncio
async def test_crm_query_converts_timeout_to_structured_failure(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "crm_tool_provider", "http")
    monkeypatch.setattr(settings, "external_max_retries", 1)
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.TimeoutException("token=secret-timeout")

    _patch_http_transport(monkeypatch, handler)
    result = await QueryOrderTool().invoke(
        {"order_id": "ORD-2026-001"}, {"role": "admin"}, skip_rbac=True
    )

    assert result.success is False
    assert attempts == 2
    assert "超时" in (result.error or "")
    assert "secret-timeout" not in (result.error or "")


@pytest.mark.asyncio
async def test_crm_create_compensation_calls_delete_endpoint(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "crm_tool_provider", "http")
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(204)

    _patch_http_transport(monkeypatch, handler)
    result = await CreateCrmTaskTool().compensate(
        {"task_id": "CT-9001", "action": "delete", "provider": "http"}
    )

    assert result.success is True
    assert captured == {
        "method": "DELETE",
        "url": f"{settings.crm_api_base}/crm_tasks/CT-9001",
    }


@pytest.mark.asyncio
async def test_mail_http_path_preserves_contract_and_attempts(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tool_provider", "mock")
    monkeypatch.setattr(settings, "mail_tool_provider", "http")
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message_id": "MSG-9001"})

    _patch_http_transport(monkeypatch, handler)
    result = await SendEmailInternalTool().invoke(
        {
            "to": ["team@company.internal"],
            "subject": "演练通知",
            "body": "仅用于本地契约测试",
        },
        {"role": "admin", "user_id": "u1"},
        skip_rbac=True,
    )

    assert result.success is True
    assert result.output == {"message_id": "MSG-9001", "recipients": 1}
    assert captured["body"]["scope"] == "internal"
    assert result.side_effects["external_attempts"] == 1
    assert result.compensation_data["provider"] == "http"


@pytest.mark.asyncio
async def test_mail_http_failure_is_structured_and_does_not_expose_token(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mail_tool_provider", "http")
    monkeypatch.setattr(settings, "mail_api_token", "mail-secret-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "mail-secret-token invalid"})

    _patch_http_transport(monkeypatch, handler)
    result = await SendEmailInternalTool().invoke(
        {
            "to": ["team@company.internal"],
            "subject": "失败测试",
            "body": "不应泄露认证信息",
        },
        {"role": "admin", "user_id": "u1"},
        skip_rbac=True,
    )

    assert result.success is False
    assert "认证失败" in (result.error or "")
    assert "mail-secret-token" not in (result.error or "")


def test_external_mail_remains_high_risk_and_does_not_fake_http_recall():
    tool = SendEmailExternalTool()
    assert tool.requires_approval is True
    assert tool.risk_level == "high"

    result = asyncio.run(tool.compensate({"message_id": "MSG-9002", "provider": "http"}))

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert "不能伪造" in (result.error or "")


@pytest.mark.asyncio
async def test_external_mail_keeps_rbac_boundary_before_http_call(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mail_tool_provider", "http")
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"message_id": "MSG-should-not-send"})

    _patch_http_transport(monkeypatch, handler)
    result = await SendEmailExternalTool().invoke(
        {
            "to": ["customer@example.com"],
            "subject": "报价",
            "body": "未经审批的外发测试",
        },
        {"role": "customer_service", "user_id": "u-cs"},
    )

    assert result.success is False
    assert "无权" in (result.error or "")
    assert calls == 0
