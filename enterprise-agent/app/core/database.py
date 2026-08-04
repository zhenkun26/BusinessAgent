"""PostgreSQL 异步连接池管理"""

from typing import Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_db():
    """初始化数据库连接池"""
    global _engine, _session_factory
    settings = get_settings()

    _engine = create_async_engine(
        settings.postgres_dsn,
        echo=settings.is_dev,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )

    # 测试连接
    async with _engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("PostgreSQL 连接池已创建")


async def close_db():
    """关闭数据库连接池"""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("PostgreSQL 连接池已关闭")


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取会话工厂(用于依赖注入)"""
    if _session_factory is None:
        raise RuntimeError("数据库未初始化,请先调用 init_db()")
    return _session_factory


async def get_db() -> AsyncSession:
    """FastAPI 依赖:获取数据库会话"""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def check_db_health() -> dict:
    """健康检查"""
    try:
        if _engine is None:
            return {"status": "unhealthy", "reason": "未初始化"}
        async with _engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}
