"""工具 provider 分发测试(规格 5.1:mock/http 开关)"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.tools.base import BaseTool, ToolCategory, ToolResult


class _FakeHttpTool(BaseTool):
    """仅实现 _call_external 的测试工具"""

    name = "fake_http_tool"
    category = ToolCategory.QUERY
    description = "测试用"
    input_schema = None

    async def _execute(self, params, context):
        return ToolResult(
            success=True, tool_name=self.name, output={"source": "mock"}
        )

    async def _call_external(self, params, context):
        return ToolResult(
            success=True, tool_name=self.name, output={"source": "http"}
        )


class _FakeMockOnlyTool(BaseTool):
    """仅实现 Mock _execute、未实现 _call_external 的测试工具"""

    name = "fake_mock_only"
    category = ToolCategory.QUERY
    description = "测试用"
    input_schema = None

    async def _execute(self, params, context):
        return ToolResult(
            success=True, tool_name=self.name, output={"source": "mock"}
        )


class _ScopedHttpTool(_FakeHttpTool):
    """验证业务系统级 provider 开关优先于全局开关。"""

    provider_config_attr = "crm_tool_provider"


@pytest.mark.asyncio
async def test_should_use_mock_execute_when_provider_is_mock(monkeypatch):
    """Given tool_provider=mock, When 调用工具,
    Then 走 _execute(Mock),不发起网络请求"""
    monkeypatch.setattr(get_settings(), "tool_provider", "mock")
    tool = _FakeHttpTool()

    result = await tool.invoke({}, {"role": "admin", "user_id": "u1"}, skip_rbac=True)

    assert result.success is True
    assert result.output["source"] == "mock"


@pytest.mark.asyncio
async def test_should_use_external_adapter_when_provider_is_http(monkeypatch):
    """Given tool_provider=http, When 调用工具,
    Then 走 _call_external(HTTP 适配器)"""
    monkeypatch.setattr(get_settings(), "tool_provider", "http")
    tool = _FakeHttpTool()

    result = await tool.invoke({}, {"role": "admin", "user_id": "u1"}, skip_rbac=True)

    assert result.success is True
    assert result.output["source"] == "http"


@pytest.mark.asyncio
async def test_should_report_missing_adapter_when_http_without_call_external(
    monkeypatch,
):
    """Given provider=http 但工具未实现 _call_external, When 调用,
    Then 返回明确错误而非静默 Mock"""
    monkeypatch.setattr(get_settings(), "tool_provider", "http")
    tool = _FakeMockOnlyTool()

    result = await tool.invoke(
        {},
        {"role": "salesperson", "user_id": "u1"},
        skip_rbac=True,
    )

    assert result.success is False
    assert "未实现真实 API 适配" in (result.error or "")


@pytest.mark.asyncio
async def test_should_respect_tool_provider_override(monkeypatch):
    """Given 全局 mock 但工具 override=http, When 调用,
    Then 以工具级覆盖为准"""
    monkeypatch.setattr(get_settings(), "tool_provider", "mock")
    tool = _FakeHttpTool()
    tool.provider_override = "http"

    result = await tool.invoke({}, {"role": "admin", "user_id": "u1"}, skip_rbac=True)

    assert result.output["source"] == "http"


@pytest.mark.asyncio
async def test_should_use_system_provider_before_global_provider(monkeypatch):
    """Given CRM_TOOL_PROVIDER=http 且全局仍为 mock, When 调用 CRM 工具,
    Then 仅 CRM 走 HTTP,其他系统不受影响"""
    settings = get_settings()
    monkeypatch.setattr(settings, "tool_provider", "mock")
    monkeypatch.setattr(settings, "crm_tool_provider", "http")
    tool = _ScopedHttpTool()

    result = await tool.invoke({}, {"role": "admin", "user_id": "u1"}, skip_rbac=True)

    assert result.success is True
    assert result.output["source"] == "http"


@pytest.mark.asyncio
async def test_should_fall_back_to_global_provider_when_system_provider_empty(monkeypatch):
    """Given CRM_TOOL_PROVIDER 留空且全局为 http, When 调用 CRM 工具,
    Then 保持旧配置兼容并走 HTTP"""
    settings = get_settings()
    monkeypatch.setattr(settings, "tool_provider", "http")
    monkeypatch.setattr(settings, "crm_tool_provider", "")
    tool = _ScopedHttpTool()

    result = await tool.invoke({}, {"role": "admin", "user_id": "u1"}, skip_rbac=True)

    assert result.success is True
    assert result.output["source"] == "http"
