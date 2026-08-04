"""后台 Worker 入口

用途:
- 文档入库任务
- Saga 补偿重试
- 审计日志本地缓存回写
"""

import asyncio

from loguru import logger

from app.config import get_settings
from app.core.approval_timeout import scan_expired_approvals
from app.core.database import init_db, close_db


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

    # 保持运行
    try:
        while True:
            # 审批超时扫描(幂等,每 60 秒)
            try:
                await scan_expired_approvals()
            except Exception as e:  # noqa: BLE001 worker 单任务失败不退出主循环
                logger.error(f"审批超时扫描失败: {e}")

            await asyncio.sleep(60)
            logger.debug("Worker 心跳")
    except asyncio.CancelledError:
        logger.info("Worker 收到停止信号")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
