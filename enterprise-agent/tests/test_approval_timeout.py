"""Trusted expiry and retained-evidence scanning; no real database is claimed."""
from unittest.mock import AsyncMock
import pytest
from app.core import approval_timeout as scanner
from conftest import FakeResult, FakeRow, FakeSession

@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['pending', 'approved_pending_reauth'])
async def test_verified_expiry_commits_audit_before_notification(monkeypatch, fake_session_factory, status):
    row = FakeRow(approval_id='a1', session_id='s', requester_id='u', status=status)
    session = FakeSession(responses=[FakeResult([row]), FakeResult([row])])
    monkeypatch.setattr('app.core.database.get_session_factory', fake_session_factory(session))
    monkeypatch.setattr(scanner.deadline, 'verified', lambda row: True)
    monkeypatch.setattr(scanner, 'record_held_evidence', AsyncMock())
    notified = []
    async def notify(**kwargs):
        assert session.commits >= 1
        notified.append(kwargs)
    monkeypatch.setattr(scanner, 'notify_approval_result', notify)
    assert await scanner.scan_expired_approvals() == 1
    assert "status IN ('pending', 'approved_pending_reauth')" in session.executed_sql[1]
    assert 'expires_at IS NULL OR' not in session.executed_sql[1]
    assert 'approval_timeout' in session.executed_sql[2]
    assert notified[0]['result_type'] == 'timeout'

@pytest.mark.asyncio
async def test_legacy_is_skipped_and_cursor_advances(monkeypatch, fake_session_factory):
    row = FakeRow(approval_id='a1', session_id='s', requester_id='u')
    session = FakeSession(responses=[FakeResult([row]), FakeResult([])])
    monkeypatch.setattr('app.core.database.get_session_factory', fake_session_factory(session))
    monkeypatch.setattr(scanner.deadline, 'verified', lambda row: False)
    monkeypatch.setattr(scanner, 'record_held_evidence', AsyncMock())
    notify = AsyncMock()
    monkeypatch.setattr(scanner, 'notify_approval_result', notify)
    assert await scanner.scan_expired_approvals() == 0
    assert session.executed_params[1]['cursor'] == 'a1'
    assert not any(sql.lstrip().startswith('UPDATE ') for sql in session.executed_sql)
    notify.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['executing', 'execution_unknown'])
async def test_late_success_is_evidence_not_release(monkeypatch, fake_session_factory, status):
    from app.core import approval_lifecycle as lifecycle
    row = FakeRow(approval_id='a1', session_id='s', status=status)
    session = FakeSession(responses=[FakeResult([row])])
    load = AsyncMock(return_value=row)
    observe = AsyncMock(return_value='executed')
    settle = AsyncMock(return_value='execution_unknown')
    monkeypatch.setattr(lifecycle, 'load_locked', load)
    monkeypatch.setattr(lifecycle, 'observe', observe)
    monkeypatch.setattr(lifecycle, 'settle', settle)
    await scanner.record_held_evidence(fake_session_factory(session)())
    if status == 'executing':
        settle.assert_awaited_once_with(session, row, 'execution_unknown')
    else:
        settle.assert_not_awaited()
    import json
    evidence = json.loads(session.executed_params[1]['payload'])
    assert evidence['observed_outcome'] == 'executed'
    assert evidence['human_review_required'] is True
    assert evidence['automatic_release'] is False
    assert session.commits == 1
