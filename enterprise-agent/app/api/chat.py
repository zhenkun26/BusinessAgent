"""对话 API:用户与 Agent 交互入口(W8 接入 LangGraph + Checkpointer)

P2-2/P2-4 增强:
- sessions 表生命周期:入口置 running,终态落 completed/failed/cancelled
- 用户取消机制:run_graph 包成 Task 注册到 cancellation 注册表,/cancel 端点取消
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_settings
from app.core.cancellation import register_task, request_cancel, unregister_task
from app.core.database import get_db
from app.observability.audit import get_audit_logger
from app.prompts import reset_prompt_user, set_prompt_user
from app.security.rbac import User, get_current_user, AgentRole, security_scheme

router = APIRouter()


async def _update_session_status(
    session_id: str, status: str, error: Optional[str] = None
) -> None:
    """更新 sessions 终态(P2-4)

    用独立会话而非请求注入的 db:取消/异常路径上请求会话可能已不可用。
    失败仅告警,不影响主流程。
    """
    try:
        from app.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as s:
            await s.execute(
                text(
                    "UPDATE sessions SET status = :status, "
                    "completed_at = CURRENT_TIMESTAMP, error = :error "
                    "WHERE session_id = :sid"
                ),
                {"status": status, "error": error, "sid": session_id},
            )
            await s.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"sessions 状态更新失败({session_id} → {status}): {e}")


class ChatRequest(BaseModel):
    """对话请求"""

    message: str = Field(..., description="用户消息", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="会话 ID,首次对话不传(复用则断点恢复)")


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

    from app.graph.graph import run_graph
    from app.graph.state import UserInput

    start = time.time()

    # 会话 ID(同时作为 LangGraph thread_id,用于 Checkpointer 断点恢复)
    session_id = req.session_id or f"sess_{user.user_id}_{uuid.uuid4().hex[:8]}"

    # 真实 JWT(审批建单时作为 requester_token 存储,审批通过后恢复执行用)
    jwt_token = credentials.credentials if credentials else ""

    # 审计:对话请求入口
    audit = get_audit_logger()
    await audit.log(
        event_type="chat_request",
        session_id=session_id,
        user_id=user.user_id,
        input_summary=req.message[:500],
    )

    user_input = UserInput(
        message=req.message,
        user_id=user.user_id,
        username=user.username,
        role=AgentRole(user.role),
        department=user.department,
        jwt_token=jwt_token,
        conversation_id=session_id,
        request_id=str(uuid.uuid4()),
    )

    # sessions 生命周期(P2-4):入口置 running;续聊/审批占位行则更新回 running
    await db.execute(
        text(
            "INSERT INTO sessions (session_id, user_id, original_query, status, started_at) "
            "VALUES (:sid, :uid, :q, 'running', CURRENT_TIMESTAMP) "
            "ON CONFLICT (session_id) DO UPDATE "
            "SET status = 'running', original_query = EXCLUDED.original_query, "
            "    completed_at = NULL, error = NULL"
        ),
        {"sid": session_id, "uid": user.user_id, "q": req.message[:500]},
    )
    await db.commit()

    # P2-1:设置 prompt 分流用户(contextvar;create_task 会复制上下文传入图内)
    prompt_token = set_prompt_user(user.user_id)

    # P2-2:run_graph 包成 Task 并注册,/chat/cancel 可中途取消
    task = asyncio.create_task(
        run_graph(
            user_input=user_input,
            thread_id=session_id,  # 同一会话可跨进程恢复
            use_checkpointer=True,
        )
    )
    register_task(session_id, task)

    try:
        # 调用 LangGraph 工作流(自动接入 Checkpointer 三级降级链)
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
        sources = []
        for s in final_state.get("sources", []):
            sources.append(s.model_dump() if hasattr(s, "model_dump") else dict(s))

        # 审计:对话响应(成功)
        await audit.log(
            event_type="chat_response",
            session_id=session_id,
            user_id=user.user_id,
            success=True,
            latency_ms=latency_ms,
            payload={"confidence": final_state.get("confidence", 0.0)},
        )

        # sessions 生命周期:成功置 completed
        await _update_session_status(session_id, "completed")

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
        await _update_session_status(session_id, "cancelled")
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

    except Exception as e:
        # sessions 生命周期:失败置 failed
        await _update_session_status(session_id, "failed", error=str(e)[:500])
        # 审计:对话响应(失败)
        await audit.log(
            event_type="chat_response",
            session_id=session_id,
            user_id=user.user_id,
            success=False,
            latency_ms=int((time.time() - start) * 1000),
            payload={"error": str(e)[:500]},
        )
        raise HTTPException(500, f"Agent 处理失败: {e}")

    finally:
        unregister_task(session_id)
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
    - {"type":"token","data":"<增量文本>"}        仅面向用户的生成(答案/报告/汇总)
    - {"type":"final","data":{...ChatResponse 字段...}}  结构化结果(来源/置信度等)
    - {"type":"cancelled"} / {"type":"error","data":"..."}

    取消:客户端断开即取消;/chat/cancel 对本端点同样有效。
    """
    import time

    from fastapi.responses import StreamingResponse

    from app.graph.graph import run_graph_stream
    from app.graph.state import UserInput

    start = time.time()
    session_id = req.session_id or f"sess_{user.user_id}_{uuid.uuid4().hex[:8]}"
    jwt_token = credentials.credentials if credentials else ""

    audit = get_audit_logger()
    await audit.log(
        event_type="chat_request",
        session_id=session_id,
        user_id=user.user_id,
        input_summary=req.message[:500],
    )
    await db.execute(
        text(
            "INSERT INTO sessions (session_id, user_id, original_query, status, started_at) "
            "VALUES (:sid, :uid, :q, 'running', CURRENT_TIMESTAMP) "
            "ON CONFLICT (session_id) DO UPDATE "
            "SET status = 'running', original_query = EXCLUDED.original_query, "
            "    completed_at = NULL, error = NULL"
        ),
        {"sid": session_id, "uid": user.user_id, "q": req.message[:500]},
    )
    await db.commit()

    user_input = UserInput(
        message=req.message,
        user_id=user.user_id,
        username=user.username,
        role=AgentRole(user.role),
        department=user.department,
        jwt_token=jwt_token,
        conversation_id=session_id,
        request_id=str(uuid.uuid4()),
    )
    queue: asyncio.Queue = asyncio.Queue()

    async def produce():
        """跑图并把事件塞进队列;负责 sessions 终态与响应审计"""
        from app.graph.checkpointer import get_checkpointer

        # 在本任务自己的上下文里 set,finally 里 reset 才不致跨 Context 报错
        prompt_token = set_prompt_user(user.user_id)
        try:
            async for ev in run_graph_stream(user_input, thread_id=session_id):
                # 进度事件携带 session_id,前端首轮即可调 /chat/cancel
                if isinstance(ev, dict):
                    ev.setdefault("session_id", session_id)
                await queue.put(ev)

            # 流结束:从 checkpointer 取最终状态,组装 final 事件
            cp, backend = await get_checkpointer()
            tup = await cp.aget_tuple({"configurable": {"thread_id": session_id}})
            state = tup.checkpoint.get("channel_values", {}) if tup else {}
            latency_ms = int((time.time() - start) * 1000)

            def _unwrap_source(s):
                """checkpoint 里 pydantic 对象可能被 LangChain 序列化成
                {"lc":1,"type":"constructor","kwargs":{...}} 包装,需解包"""
                if hasattr(s, "model_dump"):
                    return s.model_dump()
                if isinstance(s, dict) and isinstance(s.get("kwargs"), dict):
                    return s["kwargs"]
                return dict(s)

            sources = [_unwrap_source(s) for s in state.get("sources", [])]
            intent = state.get("intent", "")
            final = {
                "session_id": session_id,
                "answer": state.get("final_answer", ""),
                "sources": sources,
                "confidence": state.get("confidence", 0.0),
                "intent": intent.value if hasattr(intent, "value") else str(intent),
                "needs_replan": state.get("needs_replan", False),
                "checkpointer_backend": backend,
                "latency_ms": latency_ms,
            }
            await queue.put({"type": "final", "data": final})
            await _update_session_status(session_id, "completed")
            await audit.log(
                event_type="chat_response",
                session_id=session_id,
                user_id=user.user_id,
                success=True,
                latency_ms=latency_ms,
                payload={"confidence": final["confidence"], "stream": True},
            )
        except asyncio.CancelledError:
            await queue.put({"type": "cancelled"})
            await _update_session_status(session_id, "cancelled")
            await audit.log(
                event_type="chat_cancelled",
                session_id=session_id,
                user_id=user.user_id,
                success=True,
                latency_ms=int((time.time() - start) * 1000),
            )
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception(f"流式对话失败: session_id={session_id}, error={e}")
            await queue.put({"type": "error", "data": str(e)[:500]})
            await _update_session_status(session_id, "failed", error=str(e)[:500])
            await audit.log(
                event_type="chat_response",
                session_id=session_id,
                user_id=user.user_id,
                success=False,
                latency_ms=int((time.time() - start) * 1000),
                payload={"error": str(e)[:500], "stream": True},
            )
        finally:
            await queue.put(None)
            unregister_task(session_id)
            reset_prompt_user(prompt_token)

    task = asyncio.create_task(produce())
    register_task(session_id, task)

    async def event_gen():
        try:
            while True:
                ev = await queue.get()
                if ev is None:
                    break
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        finally:
            # 客户端断连(或正常结束):确保生产者任务被收回
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    - 取消语义:asyncio Task cancel,在下一个 await 点生效
      (Agent 内 LLM 调用已 ainvoke 化,LLM 等待期间即可生效)
    - 已执行的工具副作用不撤销(取消 ≠ 回滚)
    """
    row = (
        await db.execute(
            text("SELECT user_id, status FROM sessions WHERE session_id = :sid"),
            {"sid": req.session_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(404, "会话不存在")
    if row["user_id"] != user.user_id and user.role != AgentRole.ADMIN.value:
        raise HTTPException(403, "只能取消本人的会话")

    cancelled = request_cancel(req.session_id)
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
    from app.graph.checkpointer import get_checkpointer

    try:
        checkpointer, backend = await get_checkpointer()
        config = {"configurable": {"thread_id": session_id}}

        # 获取最新 checkpoint
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if checkpoint_tuple is None:
            # P2-4:checkpointer 未命中时回查 sessions 表,返回元信息兜底
            row = (
                await db.execute(
                    text("SELECT status FROM sessions WHERE session_id = :sid"),
                    {"sid": session_id},
                )
            ).mappings().first()
            if row:
                return {
                    "session_id": session_id,
                    "messages": [],
                    "found": False,
                    "session_status": row["status"],
                }
            return {"session_id": session_id, "messages": [], "found": False}

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
            "confidence": state.get("confidence", 0.0),
            "subtasks_count": len(state.get("subtasks", [])),
            "agent_results_count": len(state.get("agent_results", [])),
        }

    except Exception as e:
        raise HTTPException(500, f"读取历史失败: {e}")


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
    # upsert 会话行(chat 不写 sessions 表,user_feedback 外键依赖)
    await db.execute(
        text(
            "INSERT INTO sessions (session_id, user_id, status) "
            "VALUES (:sid, :uid, 'completed') "
            "ON CONFLICT (session_id) DO NOTHING"
        ),
        {"sid": req.session_id, "uid": user.user_id},
    )

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
                "dept_namespace, status, access_roles, uploaded_by) "
                "VALUES (:did, :title, 'faq', 'shared_company', 'draft', "
                "CAST(:roles AS JSONB), :uid)"
            ),
            {
                "did": document_id,
                "title": comment[:50],
                "roles": json.dumps(access_roles),
                "uid": user.user_id,
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
