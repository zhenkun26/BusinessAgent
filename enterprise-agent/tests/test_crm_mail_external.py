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
    settings = get_settings()
    monkeypatch.setattr(settings, "tool_reference_profile", "business-reference-v1")
    monkeypatch.setattr(settings, "tool_reference_run_id", "00000000-0000-4000-8000-000000000001")
    monkeypatch.setattr(settings, "tool_reference_principal", "test-principal")
    monkeypatch.setattr(settings, "crm_api_token", "synthetic")
    original_handler = handler
    def profiled(request):
        response = original_handler(request)
        response.headers["X-Reference-Profile"] = "business-reference-v1"
        return response
    handler = profiled
    original_client = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return original_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    async def _noop_backoff(attempt: int) -> None:
        return None

    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", patched_client)
    monkeypatch.setattr("app.tools.http_adapter.asyncio.sleep", _noop_backoff)
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: _RecordingAuditLogger())


@pytest.mark.asyncio
async def test_crm_queries_keep_mock_output_shape_in_http_mode(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "crm_tool_provider", "http")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/customers/C001"):
            return httpx.Response(200, json={"customer": {"customer_id": "C001", "level": "VIP", "version": 1}})
        return httpx.Response(
            200,
            json={"order": {"order_id": "ORD-2026-001", "status": "completed", "items": [], "version": 1, "customer_id": "C001", "amount_minor": 1234, "currency": "CNY"}},
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
    assert customer.output == {"customer": {"customer_id": "C001", "level": "VIP", "version": 1}}
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
    assert result.error == "REFERENCE_READ_INVALID"
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
    assert attempts == 3
    assert result.error == "REFERENCE_READ_INVALID"
    assert "secret-timeout" not in (result.error or "")


def test_external_mail_remains_high_risk_and_does_not_fake_http_recall():
    tool = SendEmailExternalTool()
    assert tool.requires_approval is True
    assert tool.risk_level == "high"

    result = asyncio.run(tool.compensate({"message_id": "MSG-9002", "provider": "http"}))

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error == "DURABLE_COMPENSATION_REQUIRED"


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


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,params", [
    (CreateCrmTaskTool(), {"customer_id": "C001", "title": "test"}),
    (SendEmailInternalTool(), {"to": ["employee@reference.invalid"], "subject": "test", "body": "test"}),
    (SendEmailExternalTool(), {"to": ["customer@reference.invalid"], "subject": "test", "body": "test"}),
])
async def test_actions_require_persisted_identity_even_with_skip_rbac(monkeypatch, tool, params):
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.tools.operation_gateway.authorize_action", AsyncMock())
    tool.provider_override = "http"
    result = await tool.invoke(params, {"role": "admin", "user_id": "test"}, skip_rbac=True)
    assert result.success is False
    assert result.error == "ACTION_IDENTITY_INVALID"


@pytest.mark.asyncio
async def test_crm_inverse_is_not_sent_without_durable_compensation(monkeypatch):
    tool = CreateCrmTaskTool()
    tool.provider_override = "http"
    def forbidden(*args, **kwargs):
        raise AssertionError("No inverse HTTP dispatch")
    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", forbidden)
    result = await tool.compensate({"provider": "http", "task_id": "T1"})
    assert result.success is False
    assert result.error == "DURABLE_COMPENSATION_REQUIRED"
