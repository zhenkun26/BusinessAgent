"""Saga 补偿重试测试(规格 5.6)"""

from __future__ import annotations

import json

import pytest

from app.core.saga_retry import retry_saga_compensations

from conftest import FakeResult, FakeRow, FakeSession


@pytest.mark.asyncio
async def test_should_mark_saga_compensated_when_all_actions_rollback(
    monkeypatch,
    fake_session_factory,
):
    """Given 失败事务含已执行动作, When 重试补偿,
    Then 调用各工具 compensate 且事务置 compensated"""
    saga_row = FakeRow(
        saga_id="saga_001",
        status="failed",
        executed_actions=[
            {"tool": "create_crm_task", "compensation_data": {"task_id": "CT-1"}},
            {"tool": "send_email_internal", "compensation_data": {"message_id": "INT-1"}},
        ],
        compensation_results=None,
    )
    session = FakeSession(
        responses=[FakeResult([saga_row]), FakeResult(), FakeResult()]
    )
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )
    compensated: list[str] = []

    class FakeTool:
        def __init__(self, tool_name):
            self.name = tool_name

        async def compensate(self, compensation_data):
            compensated.append(self.name)
            from app.tools.base import ToolResult

            return ToolResult(success=True, tool_name=self.name, output={})

    def fake_get_tool(tool_name):
        return FakeTool(tool_name)

    monkeypatch.setattr("app.tools.base.get_tool", fake_get_tool)

    await retry_saga_compensations("saga_001")

    assert compensated == ["create_crm_task", "send_email_internal"]
    update_params = session.executed_params[1]
    assert update_params["status"] == "compensated"


@pytest.mark.asyncio
async def test_should_raise_and_keep_failed_when_compensation_still_fails(
    monkeypatch,
    fake_session_factory,
):
    """Given 补偿动作仍失败, When 重试补偿,
    Then 抛异常(任务队列按退避重试)且状态保持 failed"""
    saga_row = FakeRow(
        saga_id="saga_002",
        status="failed",
        executed_actions=[
            {"tool": "send_email_internal", "compensation_data": {"message_id": "INT-2"}},
        ],
        compensation_results=None,
    )
    session = FakeSession(
        responses=[FakeResult([saga_row]), FakeResult(), FakeResult()]
    )
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )

    class FailingTool:
        name = "send_email_internal"

        async def compensate(self, compensation_data):
            raise RuntimeError("外部系统不可达")

    monkeypatch.setattr(
        "app.tools.base.get_tool", lambda tool_name: FailingTool()
    )

    with pytest.raises(RuntimeError, match="补偿仍有失败"):
        await retry_saga_compensations("saga_002")

    update_params = session.executed_params[1]
    assert update_params["status"] == "failed"
