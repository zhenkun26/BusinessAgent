"""审批超时自动流转(审批生命周期规格 2.1-2.4)"""

from __future__ import annotations

import pytest

from app.core.approval_timeout import scan_expired_approvals

from conftest import FakeResult, FakeRow, FakeSession


@pytest.mark.asyncio
async def test_should_timeout_only_pending_expired_approvals_when_scanning(
    monkeypatch,
    fake_session_factory,
):
    """Given 存在超过 expires_at 的 pending 审批单,
    When 执行超时扫描,
    Then 仅将 pending+过期 的单流转为 timeout,记系统审计并通知发起人"""
    timed_out = FakeRow(
        approval_id="appr_expired_001",
        session_id="sess_x",
        requester_id="user_sales_001",
    )
    session = FakeSession(responses=[FakeResult([timed_out])])
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )

    audit_events: list[dict] = []

    class FakeAuditLogger:
        async def log(self, **kwargs):
            audit_events.append(kwargs)

    monkeypatch.setattr(
        "app.core.approval_timeout.get_audit_logger",
        lambda: FakeAuditLogger(),
    )
    notified: list[dict] = []

    async def fake_notify(**kwargs):
        notified.append(kwargs)

    monkeypatch.setattr(
        "app.core.approval_timeout.notify_approval_result",
        fake_notify,
    )

    count = await scan_expired_approvals()

    assert count == 1
    update_sql = session.executed_sql[0]
    assert "status = 'timeout'" in update_sql
    assert "status = 'pending'" in update_sql  # 幂等护栏:仅处理 pending
    assert "expires_at IS NOT NULL" in update_sql
    assert "expires_at < NOW()" in update_sql
    assert "RETURNING" in update_sql
    # 系统审计 + 发起人通知
    assert audit_events[0]["event_type"] == "approval_timeout"
    assert audit_events[0]["user_id"] == "system"
    assert notified[0]["approval_id"] == "appr_expired_001"
    assert notified[0]["result_type"] == "timeout"
    assert notified[0]["requester_id"] == "user_sales_001"


@pytest.mark.asyncio
async def test_should_return_zero_when_no_expired_approvals(
    monkeypatch,
    fake_session_factory,
):
    """Given 没有过期审批单, When 执行超时扫描,
    Then 返回 0 且不产生审计与通知"""
    session = FakeSession(responses=[FakeResult([])])
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )
    audit_events: list[dict] = []

    class FakeAuditLogger:
        async def log(self, **kwargs):
            audit_events.append(kwargs)

    monkeypatch.setattr(
        "app.core.approval_timeout.get_audit_logger",
        lambda: FakeAuditLogger(),
    )

    count = await scan_expired_approvals()

    assert count == 0
    assert audit_events == []
