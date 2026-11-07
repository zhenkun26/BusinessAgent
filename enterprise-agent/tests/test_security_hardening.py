"""安全加固专项:日志脱敏 / Milvus 表达式转义 / 审计缓存回写"""

from __future__ import annotations

import json
import sqlite3
from app.observability.retained import RetainedStore

import pytest

from app.security.redaction import REDACTED, redact_text
from app.observability.audit import AuditLogger
from app.rag.degradation import KeywordRetriever

from conftest import FakeResult, FakeRow, FakeSession


def test_should_redact_password_from_redis_url():
    """Given 含密码的 redis URL, When 日志脱敏,
    Then credentials are removed using the shared redaction policy"""
    url = "redis://:V5lOkygYvgaD6ZZ8rmqJAcO7@localhost:6379/0"

    redacted = redact_text(url)

    assert "V5lOkygYvgaD6ZZ8rmqJAcO7" not in redacted
    assert f"redis://{REDACTED}@localhost:6379/0" == redacted


def test_should_escape_quote_and_backslash_in_milvus_expr_value():
    """Given 值含双引号/反斜杠(不可信输入), When Milvus 表达式转义,
    Then 值被安全包裹,不破坏表达式"""
    escaped = KeywordRetriever._escape_milvus_expr_str('dept"sales\\x')

    assert escaped == '"dept\\"sales\\\\x"'
    assert '"' not in escaped[1:-1].replace('\\"', "")


@pytest.mark.asyncio
async def test_should_flush_local_audit_cache_to_db_when_worker_starts(
    monkeypatch, fake_session_factory,
):
    """Replay acknowledges the retained original; it never removes it."""
    async def inline(function, *args):
        return function(*args)
    monkeypatch.setattr("app.observability.audit.asyncio.to_thread", inline)
    db = sqlite3.connect(':memory:', isolation_level=None)
    try:
        store = RetainedStore('unused', connection=db)
        record = {
            "event_id": "00000000-0000-0000-0000-000000000021",
            "occurred_at": "2026-10-18T00:00:00+00:00",
            "event_type": "chat_response", "session_id": "sess_001",
            "user_id": "user_sales_001", "tool_name": None,
            "input_summary": "fixture", "output_summary": "response",
            "success": True, "latency_ms": 10, "payload": {"confidence": 0.9},
            "request_id": None, "trace_id": None, "task_id": None,
        }
        store.append('audit', record['event_id'], record)
        session = FakeSession(responses=[FakeResult(), FakeResult()])
        monkeypatch.setattr("app.core.database.get_session_factory", fake_session_factory(session))
        audit = AuditLogger(store=store)
        assert await audit.flush_local_cache() == 1
        assert store.pending('audit') == []
        assert db.execute('SELECT COUNT(*) FROM retained_events').fetchone()[0] == 1
        assert "INSERT INTO audit_logs" in session.executed_sql[0]
    finally:
        db.close()
