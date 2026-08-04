"""审批结果通知(审批生命周期规格 2.3)"""

from __future__ import annotations

import pytest

from app.core.approval_notify import notify_approval_result

from conftest import FakeResult, FakeRow, FakeSession


@pytest.mark.asyncio
async def test_should_send_internal_mail_and_audit_when_notifying_requester(
    monkeypatch,
):
    """Given 发起人存在邮箱, When 审批结果通知发起人,
    Then 发送内部邮件(Mock 落库)并落 approval_notification 审计"""
    requester = FakeRow(
        email="zhangsan@example.com",
        username="销售员张三",
    )
    db = FakeSession(responses=[FakeResult([requester])])

    audit_events: list[dict] = []

    class FakeAuditLogger:
        async def log(self, **kwargs):
            audit_events.append(kwargs)

    monkeypatch.setattr(
        "app.core.approval_notify.get_audit_logger",
        lambda: FakeAuditLogger(),
    )

    async def fake_send_mail(**kwargs):
        return "msg_notify_001"

    monkeypatch.setattr(
        "app.core.approval_notify._send_internal_mail",
        fake_send_mail,
    )

    await notify_approval_result(
        db=db,
        approval_id="appr_001",
        requester_id="user_sales_001",
        session_id="sess_001",
        result_type="executed",
        detail="工具执行成功: message_id=EXT-123",
    )

    assert audit_events[0]["event_type"] == "approval_notification"
    assert audit_events[0]["user_id"] == "user_sales_001"
    payload = audit_events[0]["payload"]
    assert payload["approval_id"] == "appr_001"
    assert payload["result_type"] == "executed"
    assert payload["message_id"] == "msg_notify_001"
    assert payload["channel"] == "internal_mail"


@pytest.mark.asyncio
async def test_should_still_audit_when_requester_email_missing(monkeypatch):
    """Given 发起人无邮箱(查询为空), When 通知发起人,
    Then 跳过邮件发送但仍落审计(通知通道缺失可观测,不静默)"""
    db = FakeSession(responses=[FakeResult([])])
    audit_events: list[dict] = []

    class FakeAuditLogger:
        async def log(self, **kwargs):
            audit_events.append(kwargs)

    monkeypatch.setattr(
        "app.core.approval_notify.get_audit_logger",
        lambda: FakeAuditLogger(),
    )
    send_called: list[bool] = []

    async def should_not_send(**kwargs):
        send_called.append(True)
        return "msg"

    monkeypatch.setattr(
        "app.core.approval_notify._send_internal_mail",
        should_not_send,
    )

    await notify_approval_result(
        db=db,
        approval_id="appr_002",
        requester_id="user_missing",
        session_id=None,
        result_type="timeout",
        detail="审批超时",
    )

    assert send_called == []
    assert audit_events[0]["event_type"] == "approval_notification"
    assert audit_events[0]["payload"]["message_id"] is None
