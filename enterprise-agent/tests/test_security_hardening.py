"""安全加固专项:日志脱敏 / Milvus 表达式转义 / 审计缓存回写"""

from __future__ import annotations

import json
import os

import pytest

from app.graph.checkpointer import _redact_url
from app.observability.audit import AuditLogger
from app.rag.degradation import KeywordRetriever

from conftest import FakeResult, FakeRow, FakeSession


def test_should_redact_password_from_redis_url():
    """Given 含密码的 redis URL, When 日志脱敏,
    Then 密码被替换为 ***"""
    url = "redis://:V5lOkygYvgaD6ZZ8rmqJAcO7@localhost:6379/0"

    redacted = _redact_url(url)

    assert "V5lOkygYvgaD6ZZ8rmqJAcO7" not in redacted
    assert "redis://:***@localhost:6379/0" == redacted


def test_should_escape_quote_and_backslash_in_milvus_expr_value():
    """Given 值含双引号/反斜杠(不可信输入), When Milvus 表达式转义,
    Then 值被安全包裹,不破坏表达式"""
    escaped = KeywordRetriever._escape_milvus_expr_str('dept"sales\\x')

    assert escaped == '"dept\\"sales\\\\x"'
    assert '"' not in escaped[1:-1].replace('\\"', "")


@pytest.mark.asyncio
async def test_should_flush_local_audit_cache_to_db_when_worker_starts(
    monkeypatch,
    fake_session_factory,
    tmp_path,
):
    """Given PG 故障期间积压的本地审计缓存, When worker 启动回写,
    Then 逐条写入 PG 并删除缓存文件"""
    cache_dir = tmp_path / "audit"
    cache_dir.mkdir()
    record = {
        "event_type": "chat_response",
        "session_id": "sess_001",
        "user_id": "user_sales_001",
        "tool_name": None,
        "input_summary": "你好",
        "output_summary": "回答",
        "success": True,
        "latency_ms": 10,
        "payload": {"confidence": 0.9},
    }
    (cache_dir / "1000_chat_response.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )

    session = FakeSession(responses=[FakeResult(), FakeResult()])
    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(session),
    )
    logger = AuditLogger(local_cache_path=str(cache_dir))

    synced = await logger.flush_local_cache()

    assert synced == 1
    assert list(cache_dir.iterdir()) == []
    assert "INSERT INTO audit_logs" in session.executed_sql[0]
