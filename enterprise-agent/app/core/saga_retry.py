"""Saga 补偿重试(外部系统接入,规格 5.6)

worker 消费 saga_retry 队列后,读取 saga_transactions 中失败事务的
已执行动作,逐个调用工具 compensate 重试补偿;全部成功则置 compensated。
"""

from __future__ import annotations

import json

from loguru import logger
from sqlalchemy import text


async def retry_saga_compensations(saga_id: str) -> None:
    """重试一次 Saga 补偿

    Args:
        saga_id: saga_transactions.saga_id

    Raises:
        RuntimeError: 事务不存在或补偿仍失败(由任务队列按退避重试)
    """
    from app.core.database import get_session_factory
    from app.tools.base import get_tool

    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT saga_id, status, executed_actions, compensation_results "
                    "FROM saga_transactions WHERE saga_id = :sid"
                ),
                {"sid": saga_id},
            )
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Saga 事务不存在: {saga_id}")
        if row.status != "failed":
            logger.info(f"Saga {saga_id} 状态 {row.status},无需补偿重试")
            return

        executed_actions = row.executed_actions or []
        if isinstance(executed_actions, str):
            executed_actions = json.loads(executed_actions)

        compensation_results: list[dict] = []
        all_success = True
        for action in executed_actions:
            tool_name = action.get("tool") if isinstance(action, dict) else None
            compensation_data = (
                action.get("compensation_data", {}) if isinstance(action, dict) else {}
            )
            if not tool_name:
                continue
            try:
                tool = get_tool(tool_name)
                result = await tool.compensate(compensation_data)
                compensation_results.append(
                    {"tool": tool_name, "success": result.success, "error": result.error}
                )
                all_success = all_success and result.success
            except Exception as e:  # noqa: BLE001 单动作失败不阻断其他补偿
                compensation_results.append(
                    {"tool": tool_name, "success": False, "error": str(e)}
                )
                all_success = False

        new_status = "compensated" if all_success else "failed"
        await session.execute(
            text(
                "UPDATE saga_transactions SET status = :status, "
                "compensation_results = CAST(:results AS JSONB), "
                "completed_at = CASE WHEN :status = 'compensated' "
                "THEN CURRENT_TIMESTAMP ELSE completed_at END "
                "WHERE saga_id = :sid"
            ),
            {
                "status": new_status,
                "results": json.dumps(compensation_results, ensure_ascii=False),
                "sid": saga_id,
            },
        )
        await session.commit()

    if not all_success:
        raise RuntimeError(f"Saga {saga_id} 补偿仍有失败,等待下次重试")
    logger.info(f"Saga {saga_id} 补偿重试完成,已置 compensated")
