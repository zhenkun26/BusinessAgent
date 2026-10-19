"""多轮对话历史加载(从 Checkpointer 快照链提取最近 N 轮问答)

设计要点:
- 历史来源:checkpointer 的 checkpoint 链(thread_id=conversation_id)
  alist(config) 按时间倒序产出 CheckpointTuple,取 channel_values 中
  含非空 final_answer 且请求归属标记匹配的快照,提取问答对
- 加载位置:run_graph / run_graph_stream(async 上下文,与 checkpointer
  同事件循环;planner 是 sync 节点,不能碰 async checkpointer)
- 注入方式:不改 prompt 模板(模板在 prompt_versions 表有 active 版本,
  改 defaults.py 不生效),把历史块拼进现有占位符:
  planner 意图分类拼进 {message} 槽、knowledge 答案生成拼进 {query} 槽
- 读取失败:停止本次图调用,不把存储故障伪装为无历史

反序列化注意(产品文档 4.2.3):恢复后 pydantic 模型可能变 dict,
读 channel_values 时 user_input 用 dict/属性双兼容方式访问。
"""

from __future__ import annotations

import asyncio
from itertools import islice
from typing import Any, Optional

from loguru import logger

from app.graph.checkpoint_access import CheckpointUnavailable


async def load_recent_history(
    thread_id: str, max_turns: int = 5, *, checkpointer: Any = None, user_input: Any = None,
) -> list[dict]:
    """从 checkpointer 快照链加载最近 N 轮 (user, assistant) 问答对

    Args:
        thread_id: 会话线程 ID(= conversation_id)
        max_turns: 最多取几轮(默认 5)
        checkpointer: 本次图执行选定的 saver;缺失时不加载
        user_input: 当前身份/会话/请求,用于过滤历史归属

    Returns:
        [{"user": ..., "assistant": ...}, ...] 按时间正序;无历史返回 [],读取失败抛固定错误
    """
    if user_input is None or thread_id != user_input.conversation_id or max_turns <= 0:
        return []
    max_turns = min(max_turns, 5)
    try:
        if checkpointer is None:
            return []
        config = {"configurable": {"thread_id": thread_id}}

        tuples = await asyncio.wait_for(_list_checkpoints(checkpointer, config), timeout=5.0)

        pairs: list[tuple[str, str]] = []  # 倒序收集(最新在前)
        seen: set[str] = set()
        for t in tuples:
            checkpoint = getattr(t, "checkpoint", None) or {}
            channel_values = checkpoint.get("channel_values", {}) or {}
            final_answer = channel_values.get("final_answer")
            saved_input = channel_values.get("user_input")
            request_id = channel_values.get("request_id")
            if (not isinstance(final_answer, str) or not final_answer or not saved_input
                    or not isinstance(request_id, str) or not request_id
                    or request_id == user_input.request_id
                    or channel_values.get("answer_request_id") != request_id):
                continue
            # 反序列化后 user_input 有两种非对象形态,都要兼容:
            # 1) LangChain 序列化信封 {"lc","type":"constructor","kwargs":{...}}
            #    (Redis saver 的 JSON 反序列化不复活自定义 pydantic 类,保留信封原样)
            # 2) 普通 dict
            if isinstance(saved_input, dict):
                payload = (
                    saved_input.get("kwargs")
                    if saved_input.get("type") == "constructor"
                    and isinstance(saved_input.get("kwargs"), dict)
                    else saved_input
                )
            else:
                payload = vars(saved_input)
            if any(payload.get(key) != getattr(user_input, key) for key in
                   ("user_id", "conversation_id", "role", "department")):
                continue
            if payload.get("request_id") != request_id:
                continue
            message = payload.get("message")
            if not isinstance(message, str) or not message or request_id in seen:
                continue
            seen.add(request_id)
            pairs.append((message, final_answer))
            if len(pairs) >= max_turns:
                break

        pairs.reverse()  # 转为时间正序
        history = [{"user": m, "assistant": a} for m, a in pairs]
        if history:
            logger.info(f"多轮历史加载: thread_id={thread_id}, {len(history)} 轮")
        return history
    except Exception:
        raise CheckpointUnavailable() from None


async def _list_checkpoints(checkpointer: Any, config: dict, limit: int = 100) -> list:
    """枚举 checkpoint 链(async/sync saver 双兼容,按时间倒序)"""
    alist = getattr(checkpointer, "alist", None)
    if alist is not None:
        out = []
        iterator = alist(config, limit=limit)
        try:
            async for t in iterator:
                out.append(t)
                if len(out) >= limit:
                    break
        finally:
            close = getattr(iterator, "aclose", None)
            if close is not None:
                await close()
        return out
    # 同步 saver(PostgresSaver):list() 放线程里跑
    list_fn = getattr(checkpointer, "list", None)
    if list_fn is None:
        return []
    return await asyncio.to_thread(lambda: list(islice(list_fn(config, limit=limit), limit)))


def format_history_block(history: list[dict], per_answer_chars: int = 200) -> str:
    """把历史渲染成可拼进 prompt 占位符的文本块

    助手答案截断(默认 200 字),控制 prompt 长度。
    """
    lines = ["【对话历史】"]
    for h in history:
        answer = (h.get("assistant") or "").strip()
        if len(answer) > per_answer_chars:
            answer = answer[:per_answer_chars] + "…"
        lines.append(f"用户: {h.get('user', '')}")
        lines.append(f"助手: {answer}")
    return "\n".join(lines)


# 指代词:命中时检索 query 需要扩展(拼接上一轮用户消息)
COREFERENCE_MARKERS = ("它", "他", "她", "这", "那", "上面", "刚才", "还有", "该政策", "该流程")


def expand_query_with_history(query: str, history: Optional[list[dict]]) -> str:
    """轻量指代消解:query 含指代词时,拼接上一轮用户消息作为检索 query

    只影响检索(embedding)用的 query;自评与日志仍用原 query。
    """
    if not history:
        return query
    if any(marker in query for marker in COREFERENCE_MARKERS):
        last_user = history[-1].get("user", "")
        if last_user and last_user not in query:
            expanded = f"{last_user} {query}"
            logger.info(f"指代消解: 检索 query 扩展为 {expanded[:80]!r}")
            return expanded
    return query
