"""FastAPI 主应用入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.api import chat, approval, auth, prompts
from app.core.database import init_db
from app.core.milvus_client import init_milvus
from app.middleware.rate_limit import rate_limit_middleware
from app.observability.metrics import metrics_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期:启动时初始化资源, 关闭时清理"""
    settings = get_settings()
    logger.info(f"启动 Hello,小A 服务, env={settings.app_env}")

    # 初始化 OpenTelemetry tracing(启动早期,捕获后续所有 span)
    from app.observability.tracing import init_tracing, instrument_fastapi
    tracing_enabled = init_tracing(service_name="enterprise-agent")
    if tracing_enabled:
        instrument_fastapi(app)
    logger.info(f"OpenTelemetry tracing: {'已启用' if tracing_enabled else '未启用'}")

    # 初始化数据库连接池
    await init_db()
    logger.info("数据库连接池已就绪")

    # 初始化审计日志器(写 PG,失败本地兜底;需在 init_db 之后)
    from app.observability.audit import init_audit_logger
    init_audit_logger()
    logger.info("审计日志器已初始化")

    # 初始化 Milvus(集合不存在则创建;memory 后端跳过)
    try:
        await init_milvus()
        logger.info("Milvus 已就绪")
    except Exception as e:
        logger.warning(f"Milvus 初始化失败(可能用 memory 后端): {e}")

    # 初始化工具注册表(W7 ExecutionAgent 用)
    try:
        from app.tools.base import init_all_tools
        init_all_tools()
        logger.info("工具注册表已初始化")
    except Exception as e:
        logger.warning(f"工具初始化失败: {e}")

    # Prompt 版本管理(P2-1):同步代码默认版本 + 加载 active 缓存
    # 表不存在(未跑 migration)时降级代码默认,不影响启动
    from app.prompts import refresh_prompt_cache, sync_prompt_defaults
    await sync_prompt_defaults()
    await refresh_prompt_cache()

    yield

    # 清理资源
    from app.core.database import close_db
    await close_db()
    logger.info("应用已关闭")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Hello，小A——企业知识工作流 Agent",
        description="基于 LangChain + LangGraph + Milvus 的企业级多 Agent 系统",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 中间件(顺序:后注册的先执行)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_dev else ["https://your-frontend.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 指标采集中间件
    app.middleware("http")(metrics_middleware)

    # 限流中间件(Redis 优先,内存降级;async/await 无回调)
    app.middleware("http")(rate_limit_middleware)

    # 路由
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
    app.include_router(chat.router, prefix="/api/v1/chat", tags=["对话"])
    app.include_router(approval.router, prefix="/api/v1", tags=["审批"])
    app.include_router(prompts.router, prefix="/api/v1", tags=["Prompt管理"])

    # 前端静态页(单文件 SPA,访问 /ui)
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

    # 健康检查
    @app.get("/health", tags=["运维"])
    async def health():
        return {"status": "healthy", "version": "0.1.0"}

    @app.get("/ready", tags=["运维"])
    async def ready():
        from app.core.database import check_db_health
        from app.core.milvus_client import check_milvus_health
        from app.graph.checkpointer import get_checkpointer_backend
        from app.tools.base import list_tools

        checkpointer_backend = get_checkpointer_backend() or "未初始化"
        return {
            "db": await check_db_health(),
            "milvus": await check_milvus_health(),
            "checkpointer": checkpointer_backend,
            "tools_count": len(list_tools()),
        }

    @app.get("/metrics", tags=["运维"], include_in_schema=False)
    async def metrics():
        """Prometheus 指标导出(metrics_middleware 采集的请求指标)"""
        from fastapi import Response
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_dev,
        log_level=settings.log_level.lower(),
    )
