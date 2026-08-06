"""工单工具真实提供方接入测试(ticket-system-integration)

覆盖:
- 幂等键:格式 ticket-{request_id}-{uuid},HTTP 重试间键稳定,头确实发出
- 补偿真实化:创建补偿关闭外部工单/更新补偿恢复旧值/失败交 worker 重试
- 审计:真实调用结果(幂等键/重试次数/补偿动作)入审计,DB 不可用时本地缓存回写
- Mock 通道回归:tool_provider=mock 不触网,行为零变更
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

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
    monkeypatch.setattr("app.tools.http_adapter._backoff", _noop_backoff)


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


# ============ 4.1 幂等键 ============


@pytest.mark.asyncio
async def test_should_send_stable_idempotency_key_across_http_retries(monkeypatch):
    """Given provider=http 且首次请求 503, When 创建工单触发重试,
    Then 重试携带相同 Idempotency-Key 且请求体一致,键记入 side_effects"""
    monkeypatch.setattr(get_settings(), "tool_provider", "http")
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: _RecordingAuditLogger())
    keys: list[Optional[str]] = []
    bodies: list[bytes] = []
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        keys.append(request.headers.get("Idempotency-Key"))
        bodies.append(request.content)
        if attempts["count"] == 1:
            return httpx.Response(503, json={"detail": "unavailable"})
        return httpx.Response(200, json={"ticket": {"ticket_id": "TK-9001", "status": "open"}})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateTicketTool()

    result = await tool.invoke(
        {"title": "客户反馈登录异常", "customer_id": "C001", "priority": "high"},
        {"role": "admin", "user_id": "u1", "request_id": "req001"},
        skip_rbac=True,
    )

    assert result.success is True
    assert attempts["count"] == 2  # 首次 503 + 1 次重试成功
    assert keys[0] is not None and keys[0] == keys[1]  # 重试间幂等键稳定
    assert bodies[0] == bodies[1]  # 重试请求体无差异
    assert result.side_effects["idempotency_key"] == keys[0]
    assert result.side_effects["external_attempts"] == 2


@pytest.mark.asyncio
async def test_should_build_idempotency_key_from_request_id(monkeypatch):
    """Given 同一 request_id 的两次创建, When 调用,
    Then 幂等键均以 ticket-{request_id}- 为前缀,uuid 后缀区分不同建单"""
    monkeypatch.setattr(get_settings(), "tool_provider", "http")
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: _RecordingAuditLogger())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ticket": {"ticket_id": "TK-9002"}})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateTicketTool()
    context = {"role": "admin", "user_id": "u1", "request_id": "req001"}

    first = await tool.invoke({"title": "工单甲"}, context, skip_rbac=True)
    second = await tool.invoke({"title": "工单乙"}, context, skip_rbac=True)

    key_first = first.side_effects["idempotency_key"]
    key_second = second.side_effects["idempotency_key"]
    assert key_first.startswith("ticket-req001-")
    assert key_second.startswith("ticket-req001-")
    assert key_first != key_second  # 后缀区分同一请求内的不同建单动作


@pytest.mark.asyncio
async def test_should_generate_idempotency_key_when_request_id_missing(monkeypatch):
    """Given context 无 request_id, When 创建工单, Then 仍生成合法幂等键"""
    monkeypatch.setattr(get_settings(), "tool_provider", "http")
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: _RecordingAuditLogger())
    keys: list[Optional[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers.get("Idempotency-Key"))
        return httpx.Response(200, json={"ticket": {"ticket_id": "TK-9003"}})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateTicketTool()

    result = await tool.invoke(
        {"title": "无 request_id 场景"},
        {"role": "admin", "user_id": "u1"},
        skip_rbac=True,
    )

    assert result.success is True
    assert keys[0] is not None and keys[0].startswith("ticket-")


# ============ 4.2 补偿真实化 ============


@pytest.mark.asyncio
async def test_should_close_external_ticket_when_create_compensation(monkeypatch):
    """Given provider=http 的创建补偿, When compensate,
    Then PATCH 外部系统关闭工单并标注 saga_compensation,补偿动作入审计"""
    audit = _RecordingAuditLogger()
    monkeypatch.setattr("app.tools.ticket.get_audit_logger", lambda: audit)
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ticket": {"ticket_id": "TK-9101"}})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateTicketTool()
    tool.provider_override = "http"

    result = await tool.compensate({"ticket_id": "TK-9101", "action": "close"})

    assert result.success is True
    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/tickets/TK-9101")
    assert captured["body"] == {"status": "closed", "closure_reason": "saga_compensation"}
    assert audit.events[0]["event_type"] == "saga_compensation"
    assert audit.events[0]["success"] is True
    assert audit.events[0]["payload"]["action"] == "close"
    assert audit.events[0]["payload"]["ticket_id"] == "TK-9101"


@pytest.mark.asyncio
async def test_should_restore_old_values_when_update_compensation(monkeypatch):
    """Given provider=http 的更新补偿, When compensate,
    Then PATCH 外部系统恢复 old_values,补偿动作入审计"""
    audit = _RecordingAuditLogger()
    monkeypatch.setattr("app.tools.ticket.get_audit_logger", lambda: audit)
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ticket": {"ticket_id": "TK-9102"}})

    _patch_http_transport(monkeypatch, handler)
    tool = UpdateTicketTool()
    tool.provider_override = "http"
    old_values = {"status": "open", "priority": "high"}

    result = await tool.compensate(
        {"ticket_id": "TK-9102", "action": "restore", "old_values": old_values}
    )

    assert result.success is True
    assert captured["url"].endswith("/tickets/TK-9102")
    assert captured["body"] == old_values
    assert audit.events[0]["payload"]["action"] == "restore"


@pytest.mark.asyncio
async def test_should_not_call_network_when_update_compensation_without_old_values(
    monkeypatch,
):
    """Given 更新补偿无 old_values, When compensate, Then 不发网络请求直接成功"""
    monkeypatch.setattr("app.tools.ticket.get_audit_logger", lambda: _RecordingAuditLogger())
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={})

    _patch_http_transport(monkeypatch, handler)
    tool = UpdateTicketTool()
    tool.provider_override = "http"

    result = await tool.compensate(
        {"ticket_id": "TK-9103", "action": "restore", "old_values": {}}
    )

    assert result.success is True
    assert calls["count"] == 0


@pytest.mark.asyncio
async def test_should_return_failure_when_compensation_http_5xx(monkeypatch):
    """Given 外部系统持续 5xx, When 创建补偿,
    Then 退避重试耗尽后返回 success=False(交 worker 重试)且失败入审计"""
    monkeypatch.setattr(get_settings(), "external_max_retries", 2)
    audit = _RecordingAuditLogger()
    monkeypatch.setattr("app.tools.ticket.get_audit_logger", lambda: audit)
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, json={"detail": "unavailable"})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateTicketTool()
    tool.provider_override = "http"

    result = await tool.compensate({"ticket_id": "TK-9104", "action": "close"})

    assert result.success is False
    assert attempts["count"] == 3  # 首次 + 2 次重试
    assert "服务不可用" in (result.error or "")
    assert audit.events[0]["success"] is False
    assert audit.events[0]["payload"]["attempts"] == 3


# ============ 2.3 补偿失败由 worker 退避重试(工单场景)============


@pytest.mark.asyncio
async def test_should_raise_for_worker_retry_when_ticket_compensation_fails(
    monkeypatch,
    fake_session_factory,
):
    """Given 失败 Saga 含 create_ticket 补偿动作且外部系统 5xx,
    When worker 重试补偿, Then 抛异常(任务队列按退避重排)且状态保持 failed"""
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

    with pytest.raises(RuntimeError, match="补偿仍有失败"):
        await retry_saga_compensations("saga_ticket_001")

    update_params = session.executed_params[-1]
    assert update_params["status"] == "failed"
    assert "create_ticket" in update_params["results"]


@pytest.mark.asyncio
async def test_should_mark_compensated_when_ticket_compensation_succeeds(
    monkeypatch,
    fake_session_factory,
):
    """Given 失败 Saga 含 create_ticket 补偿动作且外部系统恢复,
    When worker 重试补偿, Then 真实关闭外部工单且事务置 compensated"""
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

    await retry_saga_compensations("saga_ticket_002")

    assert closed["url"].endswith("/tickets/TK-9202")
    assert closed["body"]["closure_reason"] == "saga_compensation"
    update_params = session.executed_params[-1]
    assert update_params["status"] == "compensated"
    results = json.loads(update_params["results"])
    assert results == [{"tool": "create_ticket", "success": True, "error": None}]


# ============ 3.1 真实调用结果入审计 ============


@pytest.mark.asyncio
async def test_should_write_idempotency_key_and_attempts_to_audit(monkeypatch):
    """Given provider=http 创建工单成功, When invoke,
    Then 审计 payload 含 provider/side_effects(幂等键 + 重试次数)"""
    monkeypatch.setattr(get_settings(), "tool_provider", "http")
    audit = _RecordingAuditLogger()
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: audit)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ticket": {"ticket_id": "TK-9301"}})

    _patch_http_transport(monkeypatch, handler)
    tool = CreateTicketTool()

    result = await tool.invoke(
        {"title": "审计字段验证"},
        {"role": "admin", "user_id": "u1", "request_id": "req002"},
        skip_rbac=True,
    )

    assert result.success is True
    assert len(audit.tool_calls) == 1
    record = audit.tool_calls[0]
    assert record["tool_name"] == "create_ticket"
    assert record["success"] is True
    assert record["payload"]["provider"] == "http"
    side_effects = record["payload"]["side_effects"]
    assert side_effects["idempotency_key"].startswith("ticket-req002-")
    assert side_effects["external_attempts"] == 1
    assert side_effects["created_ticket_id"] == "TK-9301"


# ============ 3.2 审计本地缓存回写(工单场景)============


@pytest.mark.asyncio
async def test_should_cache_and_resync_audit_when_db_unavailable(
    monkeypatch,
    tmp_path,
    fake_session_factory,
):
    """Given 数据库不可用, When 写工单调用审计,
    Then 写本地缓存;数据库恢复后 flush 回写并删除缓存文件"""
    audit = AuditLogger(local_cache_path=str(tmp_path))

    def broken_factory() -> Any:
        raise RuntimeError("database is down")

    monkeypatch.setattr("app.core.database.get_session_factory", broken_factory)
    await audit.log_tool_call(
        tool_name="create_ticket",
        success=True,
        payload={"provider": "http", "idempotency_key": "ticket-req003-abcd1234"},
    )

    cached_files = list(tmp_path.glob("*.json"))
    assert len(cached_files) == 1
    record = json.loads(cached_files[0].read_text(encoding="utf-8"))
    assert record["event_type"] == "tool_call"
    assert record["tool_name"] == "create_ticket"
    assert record["payload"]["idempotency_key"] == "ticket-req003-abcd1234"

    # 数据库恢复:worker 周期调用 flush_local_cache 回写
    session = FakeSession()
    monkeypatch.setattr(
        "app.core.database.get_session_factory", fake_session_factory(session)
    )
    synced = await audit.flush_local_cache()

    assert synced == 1
    assert list(tmp_path.glob("*.json")) == []  # 回写成功即删除(标记已同步)
    insert_params = session.executed_params[0]
    assert insert_params["tool_name"] == "create_ticket"
    assert "ticket-req003-abcd1234" in insert_params["payload"]


# ============ 4.3 Mock 通道回归(零变更,不触网)============


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
    created = await create_tool.invoke(
        {"title": "Mock 通道回归工单", "priority": "high"}, context, skip_rbac=True
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
    updated = await update_tool.invoke(
        {"ticket_id": "TK-EXIST002", "status": "in_progress"}, context, skip_rbac=True
    )
    assert updated.success is True
    assert _mock_tickets["TK-EXIST002"]["status"] == "in_progress"
    assert updated.compensation_data["old_values"] == {"status": "open"}

    # 更新补偿:恢复内存旧值
    restored = await update_tool.compensate(updated.compensation_data)
    assert restored.success is True
    assert _mock_tickets["TK-EXIST002"]["status"] == "open"
