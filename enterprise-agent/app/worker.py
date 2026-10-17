"""Independent retained-job worker. Full Saga recovery remains blocked on C13."""
from __future__ import annotations

import asyncio
import signal
from typing import Any
import uuid

from loguru import logger

from app.security.redaction import install_log_redaction

install_log_redaction()

from app.config import get_settings, validate_production_settings
from app.core.approval_timeout import scan_expired_approvals
from app.core.database import init_db, close_db
from app.core.knowledge_jobs import handle_knowledge_job
from app.core.task_queue import TaskRejected, consume_tasks


async def handle_doc_ingest_task(payload: dict[str, Any]) -> None:
    """Only database-backed frozen documents; no arbitrary filesystem paths."""
    await handle_knowledge_job(payload)


async def handle_saga_retry_task(payload: dict[str, Any]) -> None:
    """Never replay legacy compensation without C13's durable inverse identity."""
    raise TaskRejected("C13_REQUIRED")


async def maintenance() -> None:
    while True:
        try:
            await scan_expired_approvals()
        except Exception:
            logger.error("WORKER_APPROVAL_SCAN_FAILED")
        # Audit cache flush currently deletes files. Recovery stays with C21.
        await asyncio.sleep(60)


async def main() -> None:
    settings = get_settings()
    violations = validate_production_settings(settings)
    if violations and settings.app_env == "prod":
        raise RuntimeError("WORKER_CONFIGURATION_REJECTED")

    from app.rag.model_profile import verify_model_startup
    from app.observability.audit import init_audit_logger
    from app.tools.base import init_all_tools

    children: list[asyncio.Task] = []
    vector_started = False
    try:
        await verify_model_startup(settings)
        await init_db()
        init_audit_logger()
        init_all_tools()
        if settings.vector_store_provider == "milvus":
            from app.core.milvus_client import init_milvus
            vector_started = True
            await init_milvus()  # Failure prevents all claims; never fall back to memory.
        elif settings.vector_store_provider != "memory" or settings.app_env != "dev":
            raise RuntimeError("WORKER_VECTOR_PROFILE_REJECTED")
        worker_id = str(uuid.uuid4())
        for queue, handler in (("tasks:doc_ingest", handle_doc_ingest_task),
                               ("tasks:saga_retry", handle_saga_retry_task)):
            children.append(asyncio.create_task(
                consume_tasks(queue, handler, worker_id=worker_id), name=queue,
            ))
        children.append(asyncio.create_task(maintenance(), name="worker-maintenance"))
        done, _ = await asyncio.wait(children, return_when=asyncio.FIRST_COMPLETED)
        for child in done:
            if not child.cancelled():
                child.exception()  # Retrieve without logging exception text.
        raise RuntimeError("WORKER_CHILD_STOPPED")
    except asyncio.CancelledError:
        raise
    except Exception:
        raise RuntimeError("WORKER_FAILED") from None
    finally:
        for child in children:
            child.cancel()
        await asyncio.gather(*children, return_exceptions=True)
        try:
            if vector_started:
                from app.core.milvus_client import close_milvus
                await close_milvus()
        finally:
            await close_db()


async def serve() -> None:
    """Convert container SIGTERM into cooperative cancellation and resource closure."""
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    installed = False
    if task is not None:
        try:
            loop.add_signal_handler(signal.SIGTERM, task.cancel)
            installed = True
        except NotImplementedError:  # Development event loops without POSIX signals.
            pass
    try:
        await main()
    finally:
        if installed:
            loop.remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except Exception:
        logger.error("WORKER_FAILED")
        raise SystemExit(1) from None
