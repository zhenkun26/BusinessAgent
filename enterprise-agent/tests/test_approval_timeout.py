"""Approval deadline scanning through the real lifecycle SQL with queued results."""
from __future__ import annotations

import json
import pytest
from app.core.approval_timeout import scan_expired_approvals
from conftest import FakeResult, FakeRow, FakeSession


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "approved_pending_reauth"])
async def test_should_expire_unclaimed_requests_atomically(monkeypatch, fake_session_factory, status):
    row = FakeRow(approval_id="appr_expired_001", session_id="sess_x",
                  requester_id="user_sales_001", approver_id=None, execution_id=None,
                  status=status)
    session = FakeSession(responses=[FakeResult([row]), FakeResult([row]), FakeResult([row])])
    monkeypatch.setattr("app.core.database.get_session_factory", fake_session_factory(session))
    notified = []

    async def notify(*args):
        assert session.commits == 1
        notified.append(args)

    monkeypatch.setattr("app.core.approval_timeout.notify_approval_result", notify)
    assert await scan_expired_approvals() == 1
    assert "FOR UPDATE SKIP LOCKED" in session.executed_sql[0]
    assert "status IN ('pending', 'approved_pending_reauth')" in session.executed_sql[2]
    assert "expires_at IS NULL OR expires_at <=" in session.executed_sql[2]
    assert "INSERT INTO audit_logs" in session.executed_sql[3]
    event = json.loads(session.executed_params[3]["payload"])
    assert event["new_status"] == "timeout"
    assert notified[0][1:5] == (row.approval_id, row.requester_id, row.session_id, "timeout")


@pytest.mark.asyncio
async def test_should_commit_empty_scan_without_notification(monkeypatch, fake_session_factory):
    session = FakeSession(responses=[FakeResult([])])
    monkeypatch.setattr("app.core.database.get_session_factory", fake_session_factory(session))

    async def unexpected(*args):
        raise AssertionError("No notification without a transition")

    monkeypatch.setattr("app.core.approval_timeout.notify_approval_result", unexpected)
    assert await scan_expired_approvals() == 0
    assert session.commits == 1
    assert len(session.executed_sql) == 1
