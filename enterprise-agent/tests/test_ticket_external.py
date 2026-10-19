"""C12 ticket rejection contracts and retained audit/worker regressions.

Durable forward identity/receipt success cases run in test_tool_operation_safety.
The audit-cache pytest case uses filesystem cleanup and is NOT in the safe entry.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest

from app.config import get_settings
from app.core.saga_retry import retry_saga_compensations
from app.observability.audit import AuditLogger
from app.tools.ticket import CreateTicketTool, UpdateTicketTool, _mock_tickets

from conftest import FakeResult, FakeRow, FakeSession

HttpHandler = Callable[[httpx.Request], httpx.Response]


def _patch_http_transport(monkeypatch: pytest.MonkeyPatch, handler: HttpHandler) -> None:
    """Mock httpx 层:注入 MockTransport 桩并取消退避等待"""
    original_client = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return original_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    async def _noop_backoff(attempt: int) -> None:
        return None

    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", patched_client)
    monkeypatch.setattr("app.tools.http_adapter.asyncio.sleep", _noop_backoff)


class _RecordingAuditLogger:
    """记录审计调用的测试桩(替代真实 AuditLogger)"""

    def __init__(self) -> None:
        self.tool_calls: list[dict] = []
        self.events: list[dict] = []

    async def log_tool_call(self, **kwargs: Any) -> None:
        self.tool_calls.append(kwargs)

    async def log(self, **kwargs: Any) -> None:
        self.events.append(kwargs)

    async def log_violation(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


# ============ 2.3 Legacy Saga IDs cannot authorize C13 recovery ============


@pytest.mark.asyncio
async def test_should_raise_for_worker_retry_when_ticket_compensation_fails(
    monkeypatch,
    fake_session_factory,
):
    """Given 失败 Saga 含 create_ticket 补偿动作且外部系统 5xx,
    When its legacy ID is supplied, Then recovery rejects before reading or executing it"""
    saga_row = FakeRow(
        saga_id="saga_ticket_001",
        status="failed",
        executed_actions=[
            {
                "tool": "create_ticket",
                "compensation_data": {"ticket_id": "TK-9201", "action": "close"},
            }
        ],
        compensation_results=None,
    )
    session = FakeSession(responses=[FakeResult([saga_row])])
    monkeypatch.setattr(
        "app.core.database.get_session_factory", fake_session_factory(session)
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "unavailable"})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateTicketTool()
    tool.provider_override = "http"
    monkeypatch.setattr("app.tools.base.get_tool", lambda tool_name: tool)

    with pytest.raises(RuntimeError, match="ACTION_IDENTITY_INVALID"):
        await retry_saga_compensations("saga_ticket_001")

    assert session.executed_params == []


@pytest.mark.asyncio
async def test_worker_cannot_report_compensated_without_durable_inverse(
    monkeypatch,
    fake_session_factory,
):
    """A healthy endpoint cannot replace a durable linked compensation intent."""
    saga_row = FakeRow(
        saga_id="saga_ticket_002",
        status="failed",
        executed_actions=[
            {
                "tool": "create_ticket",
                "compensation_data": {"ticket_id": "TK-9202", "action": "close"},
            }
        ],
        compensation_results=None,
    )
    session = FakeSession(responses=[FakeResult([saga_row])])
    monkeypatch.setattr(
        "app.core.database.get_session_factory", fake_session_factory(session)
    )
    closed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        closed["url"] = str(request.url)
        closed["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ticket": {"ticket_id": "TK-9202"}})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateTicketTool()
    tool.provider_override = "http"
    monkeypatch.setattr("app.tools.base.get_tool", lambda tool_name: tool)

    with pytest.raises(RuntimeError, match="ACTION_IDENTITY_INVALID"):
        await retry_saga_compensations("saga_ticket_002")
    assert closed == {}
    assert session.executed_params == []


# ============ 3.2 审计本地缓存回写(工单场景)============


@pytest.mark.asyncio
async def test_should_cache_and_resync_audit_when_db_unavailable(
    monkeypatch, fake_session_factory,
):
    """PG recovery acknowledges an immutable retained event; no file cleanup."""
    import sqlite3
    from app.observability.retained import RetainedStore
    async def inline(function, *args):
        return function(*args)
    monkeypatch.setattr("app.observability.audit.asyncio.to_thread", inline)
    db = sqlite3.connect(':memory:', isolation_level=None)
    try:
        store = RetainedStore('unused', connection=db)
        audit = AuditLogger(store=store)
        def broken_factory() -> Any:
            raise RuntimeError("database is down")
        monkeypatch.setattr("app.core.database.get_session_factory", broken_factory)
        await audit.log_tool_call(tool_name="create_ticket", success=True,
            payload={"provider": "http", "idempotency_key": "ticket-req003-abcd1234"})
        pending = store.pending('audit')
        assert len(pending) == 1
        record = pending[0]['body']
        assert record['event_type'] == 'tool_call'
        assert record['tool_name'] == 'create_ticket'
        assert record['payload']['idempotency_key'] == 'ticket-req003-abcd1234'
        session = FakeSession()
        monkeypatch.setattr("app.core.database.get_session_factory", fake_session_factory(session))
        assert await audit.flush_local_cache() == 1
        assert store.pending('audit') == []
        assert db.execute('SELECT COUNT(*) FROM retained_events').fetchone()[0] == 1
        params = session.executed_params[0]
        assert params['event_id'] == record['event_id']
        assert params['tool_name'] == 'create_ticket'
        assert 'ticket-req003-abcd1234' in params['payload']
    finally:
        db.close()


# ============ Mock implementation regression (gateway covered by C12) ============


@pytest.mark.asyncio
async def test_should_not_call_network_when_provider_is_mock(monkeypatch):
    """Given tool_provider=mock, When 创建/更新/补偿全流程,
    Then 不发起任何网络请求,Mock 行为与既有契约一致"""
    monkeypatch.setattr(get_settings(), "tool_provider", "mock")
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: _RecordingAuditLogger())

    def _forbidden_client(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("mock 提供方不得发起网络请求")

    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", _forbidden_client)
    context = {"role": "admin", "user_id": "user_cs_001"}

    # 创建:Mock 生成 TK- 前缀工单并写入内存存储
    create_tool = CreateTicketTool()
    created = await create_tool._execute(
        {"title": "Mock 通道回归工单", "priority": "high"}, context
    )
    assert created.success is True
    ticket_id = created.output["ticket"]["ticket_id"]
    assert ticket_id.startswith("TK-")
    assert _mock_tickets[ticket_id]["status"] == "open"
    assert created.compensation_data == {"ticket_id": ticket_id, "action": "close"}
    assert "idempotency_key" not in created.side_effects  # Mock 通道无幂等键

    # 创建补偿:关闭内存工单并标注原因
    closed = await create_tool.compensate(created.compensation_data)
    assert closed.success is True
    assert _mock_tickets[ticket_id]["status"] == "closed"
    assert _mock_tickets[ticket_id]["closure_reason"] == "saga_compensation"

    # 更新:Mock 记录旧值供回滚
    update_tool = UpdateTicketTool()
    updated = await update_tool._execute(
        {"ticket_id": "TK-EXIST002", "status": "in_progress"}, context
    )
    assert updated.success is True
    assert _mock_tickets["TK-EXIST002"]["status"] == "in_progress"
    assert updated.compensation_data["old_values"] == {"status": "open"}

    # 更新补偿:恢复内存旧值
    restored = await update_tool.compensate(updated.compensation_data)
    assert restored.success is True
    assert _mock_tickets["TK-EXIST002"]["status"] == "open"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", [CreateTicketTool(), UpdateTicketTool()])
@pytest.mark.parametrize("data", [{}, {"ticket_id": "T1", "old_values": {"status": "open"}}])
async def test_http_compensation_requires_persistent_linked_intent(monkeypatch, tool, data):
    tool.provider_override = "http"
    def forbidden(*args, **kwargs):
        raise AssertionError("No HTTP inverse is allowed before C13")
    monkeypatch.setattr("app.tools.http_adapter.httpx.AsyncClient", forbidden)
    result = await tool.compensate(data)
    assert result.success is False
    assert result.error == "DURABLE_COMPENSATION_REQUIRED"


@pytest.mark.asyncio
async def test_ticket_cannot_invent_operation_id_from_request_or_index(monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.tools.operation_gateway.authorize_action", AsyncMock())
    tool = CreateTicketTool()
    tool.provider_override = "http"
    result = await tool.invoke({"title": "test"},
        {"role": "admin", "user_id": "u1", "request_id": "r1", "tool_call_index": 0})
    assert result.success is False
    assert result.error == "ACTION_IDENTITY_INVALID"
