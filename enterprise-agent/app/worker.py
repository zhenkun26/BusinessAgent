"""后台 Worker 入口

用途:
- 审批超时扫描(每 60 秒,幂等)
- 文档入库任务(Redis 队列消费)
- Saga 补偿重试(Redis 队列消费)
- 审计日志本地缓存回写(启动 + 周期)
"""

import asyncio
from typing import Any

from loguru import logger

from app.config import get_settings
from app.core.approval_timeout import scan_expired_approvals
from app.core.database import init_db, close_db
from app.core.saga_retry import retry_saga_compensations
from app.core.task_queue import consume_tasks


async def handle_doc_ingest_task(payload: dict[str, Any]) -> None:
    """文档入库任务:从队列 payload 调 ingest 服务"""
    from app.rag.ingest import MilvusIngestService

    file_path = payload.get("file_path")
    if not file_path:
        raise ValueError("doc_ingest 任务缺少 file_path")
    service = MilvusIngestService()
    await service.ingest_file(
        file_path=file_path,
        document_id=payload.get("document_id"),
        title=payload.get("title"),
        doc_type=payload.get("doc_type", "policy"),
        dept_namespace=payload.get("dept_namespace", "shared_company"),
        access_roles=payload.get("access_roles"),
        uploaded_by=payload.get("uploaded_by"),
    )


async def handle_saga_retry_task(payload: dict[str, Any]) -> None:
    """Saga 补偿重试任务"""
    saga_id = payload.get("saga_id")
    if not saga_id:
        raise ValueError("saga_retry 任务缺少 saga_id")
    await retry_saga_compensations(saga_id)


async def main():
    """Worker 主循环"""
    settings = get_settings()
    logger.info(f"Worker 启动, env={settings.app_env}")

    await init_db()

    # 审计本地缓存回写(数据库故障期间积压的审计,恢复后补录)
    try:
        from app.observability.audit import get_audit_logger

        await get_audit_logger().flush_local_cache()
    except Exception as e:  # noqa: BLE001 worker 启动不因回写失败而退出
        logger.error(f"审计缓存回写失败: {e}")

    # 后台任务队列(无限消费循环,并发运行)
    queue_consumers = [
        asyncio.create_task(
            consume_tasks(
                settings.redis_url,
                queue_name="tasks:doc_ingest",
                handler=handle_doc_ingest_task,
            ),
            name="doc-ingest-consumer",
        ),
        asyncio.create_task(
            consume_tasks(
                settings.redis_url,
                queue_name="tasks:saga_retry",
                handler=handle_saga_retry_task,
            ),
            name="saga-retry-consumer",
        ),
    ]

    # 保持运行
    try:
        while True:
            # 审批超时扫描(幂等,每 60 秒)
            try:
                await scan_expired_approvals()
            except Exception as e:  # noqa: BLE001 worker 单任务失败不退出主循环
                logger.error(f"审批超时扫描失败: {e}")

            # 周期审计缓存回写(数据库恢复后补录)
            try:
                from app.observability.audit import get_audit_logger

                await get_audit_logger().flush_local_cache()
            except Exception as e:  # noqa: BLE001
                logger.error(f"审计缓存回写失败: {e}")

            await asyncio.sleep(60)
            logger.debug("Worker 心跳")
    except asyncio.CancelledError:
        logger.info("Worker 收到停止信号")
    finally:
        for consumer in queue_consumers:
            consumer.cancel()
        await asyncio.gather(*queue_consumers, return_exceptions=True)
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
