"""Retained audit delivery with stable event IDs and non-deleting replay."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
from typing import Any, Optional
import uuid

from loguru import logger
from sqlalchemy import text

from app.observability.correlation import snapshot
from app.observability.retained import RetainedStore
from app.security.redaction import redact_value


class AuditLogger:
    def __init__(self, local_cache_path: str = 'logs/audit', store: Any = None) -> None:
        self.unretained = 0
        self.store = store or RetainedStore(os.environ.get(
            'OBSERVABILITY_STORE_PATH', local_cache_path + '/retained.sqlite3'))

    async def log(self, event_type: str, session_id: Optional[str] = None,
                  user_id: Optional[str] = None, tool_name: Optional[str] = None,
                  input_summary: Optional[str] = None, output_summary: Optional[str] = None,
                  success: Optional[bool] = None, latency_ms: Optional[int] = None,
                  payload: Optional[dict] = None) -> None:
        record = redact_value({
            'event_id': str(uuid.uuid4()), 'event_type': event_type,
            'session_id': session_id, 'user_id': user_id, 'tool_name': tool_name,
            'input_summary': input_summary or '', 'output_summary': output_summary or '',
            'success': success, 'latency_ms': latency_ms, 'payload': payload,
            'occurred_at': datetime.now(timezone.utc).isoformat(), **snapshot(),
        })
        record['input_summary'] = record['input_summary'][:500]
        record['output_summary'] = record['output_summary'][:500]
        retained = await self._write_local_cache(record)
        try:
            await self._write_database(record)
            if retained:
                await asyncio.to_thread(self.store.acknowledge, record['event_id'])
        except Exception:
            logger.warning('AUDIT_DATABASE_WRITE_FAILED')
            if not retained:
                self.unretained += 1
                logger.error('AUDIT_EVENT_UNRETAINED')

    async def _write_database(self, record: dict[str, Any]) -> None:
        from app.core.database import get_session_factory
        params = {**record, 'payload': json.dumps(record.get('payload'), ensure_ascii=False)}
        params['occurred_at'] = datetime.fromisoformat(record['occurred_at'])
        async with asyncio.timeout(5):
            async with get_session_factory()() as session:
                await session.execute(text("""INSERT INTO audit_logs
                    (event_id,event_type,session_id,user_id,tool_name,input_summary,output_summary,
                     success,latency_ms,payload,occurred_at,request_id,trace_id,task_id)
                    VALUES (:event_id,:event_type,:session_id,:user_id,:tool_name,:input_summary,
                     :output_summary,:success,:latency_ms,CAST(:payload AS JSONB),
                     :occurred_at,:request_id,:trace_id,:task_id)
                    ON CONFLICT (event_id) DO NOTHING"""), params)
                await session.commit()

    async def _write_local_cache(self, record: dict[str, Any]) -> bool:
        try:
            await asyncio.to_thread(self.store.append, 'audit', record['event_id'],
                                    redact_value(record))
            return True
        except Exception:
            logger.error('AUDIT_LOCAL_WRITE_FAILED')
            return False

    async def flush_local_cache(self) -> int:
        """Bounded replay; retain both original events and acknowledgements permanently."""
        try:
            records = await asyncio.to_thread(self.store.pending, 'audit')
        except Exception:
            logger.error('AUDIT_REPLAY_STORE_UNAVAILABLE')
            return 0
        synced = 0
        for item in records:
            try:
                await self._write_database(redact_value(item['body']))
                await asyncio.to_thread(self.store.acknowledge, item['event_id'])
                synced += 1
            except Exception:
                logger.warning('AUDIT_REPLAY_FAILED')
                try:
                    await asyncio.to_thread(self.store.defer, item['event_id'])
                except Exception:
                    logger.error('AUDIT_REPLAY_STORE_UNAVAILABLE')
        return synced

    async def health(self) -> dict[str, Any]:
        try:
            stats = await asyncio.to_thread(self.store.stats)
            return {**stats, 'status': 'healthy' if not self.unretained else 'unhealthy',
                    'unretained': self.unretained}
        except Exception:
            return {'status': 'unhealthy', 'unretained': self.unretained}

    # ============ 便捷方法 ============

    async def log_tool_call(self, **kwargs):
        await self.log(event_type="tool_call", **kwargs)

    async def log_fallback(self, session_id, user_id, error_type, message):
        await self.log(
            event_type="fallback",
            session_id=session_id, user_id=user_id,
            payload={"error_type": error_type, "message": message},
        )

    async def log_saga_rollback_start(self, session_id, failed_step, error):
        await self.log(
            event_type="saga_rollback_start",
            session_id=session_id,
            payload={"failed_step": failed_step, "error": error},
        )

    async def log_saga_rollback_complete(self, session_id, results):
        await self.log(
            event_type="saga_rollback_complete",
            session_id=session_id,
            payload={"results": results},
        )

    async def log_degradation(self, event, detail):
        await self.log(
            event_type="degradation",
            payload={"event": event, "detail": detail},
        )

    async def log_violation(self, user_id, tool_name, reason):
        await self.log(
            event_type="security_violation",
            user_id=user_id, tool_name=tool_name,
            payload={"reason": reason},
            success=False,
        )

    async def log_critical(self, message):
        await self.log(
            event_type="critical",
            payload={"message": message},
            success=False,
        )

    async def log_warning(self, message):
        await self.log(
            event_type="warning",
            payload={"message": message},
        )



_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def init_audit_logger() -> AuditLogger:
    global _audit_logger
    _audit_logger = AuditLogger()
    return _audit_logger
