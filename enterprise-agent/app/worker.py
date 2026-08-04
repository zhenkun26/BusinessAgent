"""后台 Worker 入口

用途:
- 文档入库任务
- Saga 补偿重试
- 审计日志本地缓存回写
"""

import asyncio

from loguru import logger

from app.config import get_settings
from app.core.database import init_db, close_db


async def main():
    """Worker 主循环"""
    settings = get_settings()
    logger.info(f"Worker 启动, env={settings.app_env}")

    await init_db()

    # TODO W2: 文档入库任务消费
    # TODO: Saga 补偿重试任务

    # 保持运行
    try:
        while True:
            await asyncio.sleep(60)
            logger.debug("Worker 心跳")
    except asyncio.CancelledError:
        logger.info("Worker 收到停止信号")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
