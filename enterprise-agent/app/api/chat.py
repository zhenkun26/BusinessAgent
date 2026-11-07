"""对话 API:用户与 Agent 交互入口(W8 接入 LangGraph + Checkpointer)

P2-2/P2-4 增强:
- sessions 表生命周期:入口置 running,终态落 completed/failed/cancelled
- 用户取消机制:Redis 租约绑定运行标识,/cancel 可由另一 API 进程受理
"""

import asyncio
from collections.abc import AsyncGenerator
import json
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger

from app.security.redaction import redact_text
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_settings
from app.core.cancellation import CancellationLease, SessionBusy, reserve_session, request_cancel
from app.core.execution_budget import ExecutionBudgetExceeded
from app.core.runtime_state import RuntimeStateUnavailable
from app.core.database import get_db
from app.graph.checkpoint_access import (
    CheckpointUnavailable, normalize_sources, publish_checkpoint, read_session_checkpoint,
)
from app.observability.audit import get_audit_logger
from app.prompts import reset_prompt_user, set_prompt_user
from app.security.rbac import User, get_current_user, AgentRole, security_scheme
from app.security.session_access import prepare_chat_session, require_session_access

router = APIRouter()


async def _reserve_chat(session_id: str) -> CancellationLease:
    try:
        return await reserve_session(session_id)
    except SessionBusy:
        raise HTTPException(409, "SESSION_ALREADY_RUNNING") from None
    except RuntimeStateUnavailable:
        raise HTTPException(503, "RUNTIME_STATE_UNAVAILABLE") from None


async def _prepare_owned_run(db, user: User, requested_id: str | None,
                             message: str) -> tuple[str, CancellationLease]:
    if requested_id is not None:
        # Deny foreign sessions before Redis; reserve before changing active-run metadata.
        await require_session_access(db, requested_id, user)
        lease = await _reserve_chat(requested_id)
        try:
            session_id = await prepare_chat_session(
                db, user, requested_id, message, fence=lease.fence)
        except BaseException:
            await lease.release()
            raise
        return session_id, lease
    session_id = await prepare_chat_session(db, user, None, message)
    lease = await _reserve_chat(session_id)
    try:
        await prepare_chat_session(db, user, session_id, message, fence=lease.fence)
        return session_id, lease
    except BaseException:
        await lease.release()
        raise


async def _update_session_status(
    session_id: str, status: str, error: Optional[str] = None, *, fence: Any,
) -> None:
    """Best-effort failure status; stale owners cannot alter successor metadata."""
    try:
        if fence.session_id != session_id:
            raise RuntimeStateUnavailable()
        await fence.finish(status, error=error)
    except Exception:
        logger.warning("SESSION_STATUS_WRITE_FAILED")


async def _abort_chat_start(session_id: str, lease: CancellationLease) -> None:
    """Fail only this fenced run and release it when setup cannot start a producer."""
    try:
        await _update_session_status(
            session_id, "failed", error="CHAT_START_FAILED", fence=lease.fence)
    finally:
        await lease.release()


class ChatRequest(BaseModel):
    """对话请求"""

    message: str = Field(..., description="用户消息", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="已有本人会话 ID；首次对话省略或传 null")


class ChatResponse(BaseModel):
    """对话响应"""

    session_id: str
    answer: str
    sources: list[dict] = Field(default_factory=list, description="检索来源")
    confidence: float = 0.0
    intent: Optional[str] = None
    needs_replan: bool = False
    checkpointer_backend: Optional[str] = None
    latency_ms: int = 0


@router.post("/message", response_model=ChatResponse)
async def send_message(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db=Depends(get_db),
):
    """发送消息并获取 Agent 响应(W8:接入 LangGraph 完整工作流 + Checkpointer)

    - 首次对话:不传 session_id,自动生成(以 conversation_id 作为 thread_id)
    - 多轮对话:传 session_id,LangGraph 从 Checkpointer 恢复历史状态
    - 支持断点恢复:进程重启后同 session_id 可继续
    """
    import time

    # Authorize before graph imports, audits, checkpoint access or task registration.
    req.message = redact_text(req.message)
    session_id, lease = await _prepare_owned_run(db, user, req.session_id, req.message)

    prompt_token = None
    try:
        from app.graph.graph import run_graph
        from app.graph.state import UserInput

        start = time.time()

        # Bearer credentials end at authentication; graph state carries identity only.

        # 审计:对话请求入口
        audit = get_audit_logger()
        await audit.log(
            event_type="chat_request",
            session_id=session_id,
            user_id=user.user_id,
            input_summary=req.message,
        )

        user_input = UserInput(
            message=req.message,
            user_id=user.user_id,
            username=user.username,
            role=AgentRole(user.role),
            department=user.department,
            conversation_id=session_id,
            request_id=str(uuid.uuid4()),
        )

        prompt_token = set_prompt_user(user.user_id)

        async def run_owned():
            async with lease.watch(release_on_exit=False):
                await run_graph(
                    user_input=user_input, thread_id=session_id, use_checkpointer=True,
                )
                from app.graph.checkpointer import get_checkpointer
                cp, backend = await get_checkpointer()
                lease.ensure_active()
                return await publish_checkpoint(cp, backend, lease.fence, user_input)

        task = asyncio.create_task(run_owned())

    except BaseException:
        try:
            await _abort_chat_start(session_id, lease)
        finally:
            if prompt_token is not None:
                reset_prompt_user(prompt_token)
        raise

    try:
        # 调用 LangGraph 工作流(使用显式配置的 Checkpointer 后端)
        final_state = await task

        latency_ms = int((time.time() - start) * 1000)

        # 获取 checkpointer 后端(可观测)
        backend = None
        try:
            from app.graph.checkpointer import get_checkpointer_backend
            backend = get_checkpointer_backend()
        except Exception:
            pass

        # 提取来源
        sources = normalize_sources(final_state.get("sources", []))

        # 审计:对话响应(成功);I-07:token 用量统一采集后落审计 payload
        tokens_used = int(final_state.get("tokens_used", 0) or 0)
        await audit.log(
            event_type="chat_response",
            session_id=session_id,
            user_id=user.user_id,
            success=True,
            latency_ms=latency_ms,
            payload={"confidence": final_state.get("confidence", 0.0), "tokens_used": tokens_used},
        )

        # Checkpoint publication, completed status and tokens already committed atomically.

        return ChatResponse(
            session_id=session_id,
            answer=final_state.get("final_answer", ""),
            sources=sources,
            confidence=final_state.get("confidence", 0.0),
            intent=final_state.get("intent", "").value if hasattr(final_state.get("intent", ""), "value") else str(final_state.get("intent", "")),
            needs_replan=final_state.get("needs_replan", False),
            checkpointer_backend=backend,
            latency_ms=latency_ms,
        )

    except asyncio.CancelledError:
        # P2-2 用户取消(或客户端断连):图任务取消,落 cancelled 终态
        if not task.done():
            task.cancel()
        latency_ms = int((time.time() - start) * 1000)
        logger.info(f"对话已取消: session_id={session_id}, latency={latency_ms}ms")
        await _update_session_status(session_id, "cancelled", fence=lease.fence)
        await audit.log(
            event_type="chat_cancelled",
            session_id=session_id,
            user_id=user.user_id,
            success=True,
            latency_ms=latency_ms,
        )
        # 客户端已断连时响应写不回,尽力返回即可
        return ChatResponse(
            session_id=session_id,
            answer="本次对话已取消。",
            intent="cancelled",
            latency_ms=latency_ms,
        )

    except ExecutionBudgetExceeded:
        await _update_session_status(
            session_id, "failed", error="EXECUTION_BUDGET_EXCEEDED", fence=lease.fence)
        await audit.log(event_type="chat_response", session_id=session_id,
                        user_id=user.user_id, success=False,
                        payload={"error": "EXECUTION_BUDGET_EXCEEDED"})
        raise HTTPException(422, "EXECUTION_BUDGET_EXCEEDED") from None

    except CheckpointUnavailable:
        await _update_session_status(
            session_id, "failed", error="CHECKPOINT_UNAVAILABLE", fence=lease.fence)
        await audit.log(event_type="chat_response", session_id=session_id,
                        user_id=user.user_id, success=False,
                        payload={"error": "CHECKPOINT_UNAVAILABLE"})
        raise HTTPException(503, "CHECKPOINT_UNAVAILABLE") from None

    except RuntimeStateUnavailable:
        await _update_session_status(
            session_id, "failed", error="RUNTIME_STATE_UNAVAILABLE", fence=lease.fence)
        await audit.log(event_type="chat_response", session_id=session_id,
                        user_id=user.user_id, success=False,
                        payload={"error": "RUNTIME_STATE_UNAVAILABLE"})
        raise HTTPException(503, "RUNTIME_STATE_UNAVAILABLE") from None

    except Exception as e:
        # sessions 生命周期:失败置 failed
        await _update_session_status(
            session_id, "failed", error="CHAT_EXECUTION_FAILED", fence=lease.fence)
        # 审计:对话响应(失败)
        await audit.log(
            event_type="chat_response",
            session_id=session_id,
            user_id=user.user_id,
            success=False,
            latency_ms=int((time.time() - start) * 1000),
            payload={"error": "CHAT_EXECUTION_FAILED"},
        )
        raise HTTPException(500, "CHAT_EXECUTION_FAILED") from None

    finally:
        await lease.release()
        reset_prompt_user(prompt_token)


@router.post("/stream")
async def stream_message(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db=Depends(get_db),
):
    """流式对话(SSE):与 /message 同契约,但边生成边推事件

    事件格式(data: <json>\\n\\n):
    - {"type":"progress","node":"planner|agent_executor|aggregator","phase":"start|end","session_id":"sess_xxx"}
    - {"type":"token","data":"<增量文本>"}        Eligible non-RAG generation only.
      Knowledge answers arrive through the accepted final event, without raw draft tokens.
    - {"type":"final","data":{...ChatResponse 字段...}}  结构化结果(来源/置信度等)
    - {"type":"cancelled"} / {"type":"error","data":"..."}

    取消:客户端断开即取消;/chat/cancel 对本端点同样有效。
    """
    import time

    # Reject unauthorized IDs before constructing a StreamingResponse/producer.
    req.message = redact_text(req.message)
    session_id, lease = await _prepare_owned_run(db, user, req.session_id, req.message)

    try:
        from app.api.sse_response import BoundedStreamingResponse
        from app.core.sse_stream import (
            SSEChannel, StreamFailure, bounded_cleanup, encode_event, join_producer, observe_task,
        )

        from app.graph.graph import run_graph_stream
        from app.graph.state import UserInput

        start = time.time()

        audit = get_audit_logger()
        await audit.log(
            event_type="chat_request",
            session_id=session_id,
            user_id=user.user_id,
            input_summary=req.message,
        )
        user_input = UserInput(
            message=req.message,
            user_id=user.user_id,
            username=user.username,
            role=AgentRole(user.role),
            department=user.department,
            conversation_id=session_id,
            request_id=str(uuid.uuid4()),
        )
        channel = SSEChannel()
    except BaseException:
        await _abort_chat_start(session_id, lease)
        raise
    task: asyncio.Task[None] | None = None
    close_task: asyncio.Task[None] | None = None
    producer_started = False

    async def release() -> None:
        await bounded_cleanup(lease.release())

    async def produce() -> None:
        nonlocal producer_started
        producer_started = True
        from contextlib import aclosing
        from app.graph.checkpointer import get_checkpointer

        prompt_token = set_prompt_user(user.user_id)
        published = False
        final: dict = {}
        terminal = encode_event({"type": "error", "data": "CHAT_EXECUTION_FAILED"})
        status, error = "failed", "CHAT_EXECUTION_FAILED"
        try:
            async with lease.watch(release_on_exit=False):
                # Close in the producer's context, including when put() fails or cancels.
                async with aclosing(run_graph_stream(user_input, thread_id=session_id)) as events:
                    async for ev in events:
                        ev = {**ev, "session_id": session_id}
                        await channel.put(ev)

                cp, backend = await get_checkpointer()
                lease.ensure_active()

                def prepare_final(state: dict) -> None:
                    nonlocal terminal, final
                    channel.ensure_open()
                    intent = state.get("intent", "")
                    final = {
                        "session_id": session_id,
                        "answer": state.get("final_answer", ""),
                        "sources": normalize_sources(state.get("sources", [])),
                        "confidence": state.get("confidence", 0.0),
                        "intent": intent.value if hasattr(intent, "value") else str(intent),
                        "needs_replan": state.get("needs_replan", False),
                        "checkpointer_backend": backend,
                        "latency_ms": int((time.time() - start) * 1000),
                    }
                    terminal = encode_event({"type": "final", "data": final})

                state = await publish_checkpoint(
                    cp, backend, lease.fence, user_input, before_publish=prepare_final)
                published = True
                status, error = "completed", None
                channel.finish(terminal)
            await bounded_cleanup(audit.log(
                event_type="chat_response", session_id=session_id, user_id=user.user_id,
                success=True, latency_ms=final["latency_ms"],
                payload={"confidence": final["confidence"],
                         "tokens_used": int(state.get("tokens_used", 0) or 0), "stream": True},
            ))
        except asyncio.CancelledError:
            if not published:
                status, error = "cancelled", None
                terminal = encode_event({"type": "cancelled"})
        except (ExecutionBudgetExceeded, CheckpointUnavailable, RuntimeStateUnavailable,
                StreamFailure) as exc:
            if not published:
                status, error = "failed", str(exc)
                terminal = encode_event({"type": "error", "data": error})
        except Exception:
            logger.warning("CHAT_STREAM_FAILED")
            if not published:
                status, error = "failed", "CHAT_EXECUTION_FAILED"
                terminal = encode_event({"type": "error", "data": error})
        finally:
            # No queue put/sentinel in cleanup, and no failed-state rewrite after commit.
            try:
                if not published:
                    channel.finish(terminal, discard=True)
                    await bounded_cleanup(_update_session_status(
                        session_id, status, error=error, fence=lease.fence))
                    await bounded_cleanup(audit.log(
                        event_type="chat_cancelled" if status == "cancelled" else "chat_response",
                        session_id=session_id, user_id=user.user_id,
                        success=status == "cancelled",
                        latency_ms=int((time.time() - start) * 1000),
                        payload={"error": error, "stream": True},
                    ))
            finally:
                try:
                    await release()
                finally:
                    reset_prompt_user(prompt_token)

    async def close_stream() -> None:
        nonlocal close_task
        if close_task is None:
            cancel_producer = not channel.finished
            if cancel_producer and task is not None and not task.done():
                # Cancel before waking a full-buffer waiter; otherwise STREAM_CLOSED
                # could win the race and misclassify a client disconnect as failure.
                task.cancel()
            channel.close()

            async def close_once() -> None:
                if task is not None:
                    if not await join_producer(task, cancel=False):
                        # Revoke ownership even if provider cleanup ignores cancellation.
                        await release()
                if not producer_started:
                    # Headers or cancellation before the producer's first instruction.
                    await bounded_cleanup(_update_session_status(
                        session_id, "cancelled", fence=lease.fence))
                    await release()

            close_task = asyncio.create_task(close_once())
            observe_task(close_task)
        await asyncio.shield(close_task)

    async def event_gen() -> AsyncGenerator[str, None]:
        nonlocal task
        if channel.closed:
            return
        task = asyncio.create_task(produce())
        observe_task(task)
        try:
            while True:
                frame = await channel.get()
                if frame is None:
                    break
                yield frame
        finally:
            await close_stream()

    try:
        return BoundedStreamingResponse(
            event_gen(), close=close_stream,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except BaseException:
        await _abort_chat_start(session_id, lease)
        raise


class CancelRequest(BaseModel):
    """取消对话请求(P2-2)"""

    session_id: str = Field(..., description="要取消的会话 ID")


@router.post("/cancel")
async def cancel_message(
    req: CancelRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """取消正在进行的对话(P2-2)

    - 仅本人会话可取消(admin 可取消任意会话)
    - cancelled=true 仅表示共享取消信号已受理,不表示已经停止
    - 取消语义:拥有任务的进程轮询后发出 Task cancel,在下一个 await 点生效
      (Agent 内 LLM 调用已 ainvoke 化,LLM 等待期间即可生效)
    - 已执行的工具副作用不撤销(取消 ≠ 回滚)
    """
    await require_session_access(db, req.session_id, user, allow_admin=True, lock=True)

    try:
        cancelled = await request_cancel(req.session_id)
    except RuntimeStateUnavailable:
        raise HTTPException(503, "RUNTIME_STATE_UNAVAILABLE") from None
    if cancelled:
        await get_audit_logger().log(
            event_type="chat_cancel_requested",
            session_id=req.session_id,
            user_id=user.user_id,
        )
    return {"cancelled": cancelled, "session_id": req.session_id}


@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """获取会话历史(W8:从 LangGraph Checkpointer 读取)"""
    row = await require_session_access(db, session_id, user)

    from app.graph.checkpointer import get_checkpointer

    try:
        checkpointer, backend = await get_checkpointer()
        # Only accepted run pointers (or read-only pre-v8 history) are session-visible.
        checkpoint_tuple = await read_session_checkpoint(checkpointer, session_id, backend)
        if checkpoint_tuple is None:
            # Only metadata already authorized by the ownership lookup may be returned.
            return {
                "session_id": session_id,
                "messages": [],
                "found": False,
                "session_status": row["status"],
            }

        # 提取状态快照
        state = checkpoint_tuple.checkpoint.get("channel_values", {})
        metadata = checkpoint_tuple.metadata or {}

        return {
            "session_id": session_id,
            "found": True,
            "checkpointer_backend": backend,
            "checkpoint_id": checkpoint_tuple.checkpoint.get("id"),
            "step": metadata.get("step"),
            "source": metadata.get("source"),
            "intent": str(state.get("intent", "")),
            "final_answer": state.get("final_answer", ""),
            "sources": normalize_sources(state.get("sources", [])),
            "confidence": state.get("confidence", 0.0),
            "subtasks_count": len(state.get("subtasks", [])),
            "agent_results_count": len(state.get("agent_results", [])),
        }

    except CheckpointUnavailable:
        raise HTTPException(503, "CHECKPOINT_UNAVAILABLE") from None
    except Exception:
        raise HTTPException(500, "CHAT_HISTORY_FAILED") from None


class FeedbackRequest(BaseModel):
    """用户反馈请求(P1-5 知识库反馈循环)"""

    session_id: str = Field(..., description="会话 ID")
    feedback_type: Literal["like", "dislike"] = Field(..., description="反馈类型")
    comment: str = Field(default="", description="反馈评论(dislike 时用于生成知识候选)")
    message_id: Optional[str] = Field(default=None, description="关联消息 ID")


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """用户反馈(点赞/点踩)— P1-5 知识库反馈循环

    - 写入 user_feedback 表,用于后续 RAG 优化
    - dislike 且带 comment 且开启 kb_feedback_auto_draft 时,
      自动在 documents 表生成知识候选(status=draft),供运营审核后入库
    """
    # Hold ownership stable until feedback/draft writes commit; never create placeholders.
    await require_session_access(db, req.session_id, user, lock=True)

    # 写入反馈
    await db.execute(
        text(
            "INSERT INTO user_feedback (session_id, user_id, message_id, "
            "feedback_type, comment) "
            "VALUES (:sid, :uid, :mid, :ftype, :comment)"
        ),
        {
            "sid": req.session_id,
            "uid": user.user_id,
            "mid": req.message_id,
            "ftype": req.feedback_type,
            "comment": req.comment,
        },
    )

    # 负反馈闭环:自动生成知识候选(draft),待运营审核
    draft_created = False
    comment = req.comment.strip()
    if (
        req.feedback_type == "dislike"
        and comment
        and get_settings().kb_feedback_auto_draft
    ):
        document_id = f"doc_fb_{uuid.uuid4().hex[:12]}"
        access_roles = ["salesperson", "customer_service", "finance", "manager", "admin"]
        await db.execute(
            text(
                "INSERT INTO documents (document_id, title, doc_type, "
                "dept_namespace, status, access_roles, uploaded_by, content, "
                "source_session_id) "
                "VALUES (:did, :title, 'faq', 'shared_company', 'draft', "
                "CAST(:roles AS JSONB), :uid, :content, :sid)"
            ),
            {
                "did": document_id,
                "title": comment[:50],
                "roles": json.dumps(access_roles),
                "uid": user.user_id,
                "content": comment[:500],
                "sid": req.session_id,
            },
        )
        draft_created = True

        # 审计:负反馈已生成知识候选
        await get_audit_logger().log(
            event_type="feedback_negative",
            session_id=req.session_id,
            user_id=user.user_id,
            payload={"document_id": document_id, "comment": comment[:500]},
        )

    await db.commit()
    return {"status": "received", "user_id": user.user_id, "draft_created": draft_created}
