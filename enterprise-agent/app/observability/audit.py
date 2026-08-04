"""审计日志器(P1-10 容错设计,对应 v3 方案 12.4 节)"""

import json
import os
import time
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import text


class AuditLogger:
    """审计日志器

    特性(P1-10):
    - PostgreSQL 写入失败不阻塞业务
    - 本地缓存兜底
    - 连续失败触发告警

    存储方式:复用 app.core.database 的 SQLAlchemy async 会话工厂,
    与全项目 DB 访问方式保持一致(不再依赖 asyncpg pool)。
    """

    def __init__(
        self,
        local_cache_path: str = "logs/audit",
        max_failures_before_alert: int = 5,
    ):
        self.local_cache = local_cache_path
        self.max_failures = max_failures_before_alert
        self.consecutive_failures = 0

    async def log(
        self,
        event_type: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        success: Optional[bool] = None,
        latency_ms: Optional[int] = None,
        payload: Optional[dict] = None,
    ):
        """写入审计日志(失败不阻塞业务)"""
        record = {
            "event_type": event_type,
            "session_id": session_id,
            "user_id": user_id,
            "tool_name": tool_name,
            "input_summary": (input_summary or "")[:500],
            "output_summary": (output_summary or "")[:500],
            "success": success,
            "latency_ms": latency_ms,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 尝试写入 PG(SQLAlchemy async session;未初始化或写失败则走本地兜底)
        try:
            from app.core.database import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO audit_logs (event_type, session_id, user_id, "
                        "tool_name, input_summary, output_summary, success, "
                        "latency_ms, payload) "
                        "VALUES (:event_type, :session_id, :user_id, :tool_name, "
                        ":input_summary, :output_summary, :success, :latency_ms, "
                        "CAST(:payload AS JSONB))"
                    ),
                    {
                        "event_type": record["event_type"],
                        "session_id": record["session_id"],
                        "user_id": record["user_id"],
                        "tool_name": record["tool_name"],
                        "input_summary": record["input_summary"],
                        "output_summary": record["output_summary"],
                        "success": record["success"],
                        "latency_ms": record["latency_ms"],
                        "payload": (
                            json.dumps(record["payload"], ensure_ascii=False)
                            if record["payload"] is not None
                            else None
                        ),
                    },
                )
                await session.commit()
            self.consecutive_failures = 0
            return
        except Exception as e:
            logger.warning(f"审计日志写入 PG 失败: {e}")
            self.consecutive_failures += 1

        # 兜底:写本地缓存
        await self._write_local_cache(record)

        # 连续失败告警
        if self.consecutive_failures >= self.max_failures:
            await self._send_alert(
                f"审计日志连续失败 {self.consecutive_failures} 次"
            )
            self.consecutive_failures = 0  # 重置避免重复告警

    async def _write_local_cache(self, record: dict):
        """本地缓存兜底"""
        try:
            os.makedirs(self.local_cache, exist_ok=True)
            filename = (
                f"{self.local_cache}/{int(time.time())}_"
                f"{record['event_type']}.json"
            )
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"审计日志本地缓存写入失败: {e}")

    async def _send_alert(self, message: str):
        """告警(实际接入告警系统)"""
        logger.error(f"[AUDIT ALERT] {message}")

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


# 全局单例
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def init_audit_logger() -> AuditLogger:
    """初始化审计日志器(应用启动时调用,init_db 之后)"""
    global _audit_logger
    _audit_logger = AuditLogger()
    return _audit_logger
