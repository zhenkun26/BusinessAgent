"""多轮对话历史加载(从 Checkpointer 快照链提取最近 N 轮问答)

设计要点:
- 历史来源:checkpointer 的 checkpoint 链(thread_id=conversation_id)
  alist(config) 按时间倒序产出 CheckpointTuple,取 channel_values 中
  含非空 final_answer 的快照,提取 (user_input.message, final_answer) 对
- 加载位置:run_graph / run_graph_stream(async 上下文,与 checkpointer
  同事件循环;planner 是 sync 节点,不能碰 async checkpointer)
- 注入方式:不改 prompt 模板(模板在 prompt_versions 表有 active 版本,
  改 defaults.py 不生效),把历史块拼进现有占位符:
  planner 意图分类拼进 {message} 槽、knowledge 答案生成拼进 {query} 槽
- 异常静默:历史加载失败返回 [],不影响主流程

反序列化注意(产品文档 4.2.3):恢复后 pydantic 模型可能变 dict,
读 channel_values 时 user_input 用 dict/属性双兼容方式访问。
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from loguru import logger


async def load_recent_history(thread_id: str, max_turns: int = 5) -> list[dict]:
    """从 checkpointer 快照链加载最近 N 轮 (user, assistant) 问答对

    Args:
        thread_id: 会话线程 ID(= conversation_id)
        max_turns: 最多取几轮(默认 5)

    Returns:
        [{"user": ..., "assistant": ...}, ...] 按时间正序;失败/无历史返回 []
    """
    try:
        from app.graph.checkpointer import get_checkpointer

        checkpointer, _backend = await get_checkpointer()
        config = {"configurable": {"thread_id": thread_id}}

        tuples = await _list_checkpoints(checkpointer, config)

        pairs: list[tuple[str, str]] = []  # 倒序收集(最新在前)
        seen: set[str] = set()
        for t in tuples:
            checkpoint = getattr(t, "checkpoint", None) or {}
            channel_values = checkpoint.get("channel_values", {}) or {}
            final_answer = channel_values.get("final_answer")
            user_input = channel_values.get("user_input")
            if not final_answer or not user_input:
                continue
            # 反序列化后 user_input 有两种非对象形态,都要兼容:
            # 1) LangChain 序列化信封 {"lc","type":"constructor","kwargs":{...}}
            #    (Redis saver 的 JSON 反序列化不复活自定义 pydantic 类,保留信封原样)
            # 2) 普通 dict
            if isinstance(user_input, dict):
                payload = (
                    user_input.get("kwargs")
                    if user_input.get("type") == "constructor" and isinstance(user_input.get("kwargs"), dict)
                    else user_input
                )
                message = payload.get("message")
            else:
                message = getattr(user_input, "message", None)
            if not message or message in seen:
                continue
            seen.add(message)
            pairs.append((message, final_answer))
            if len(pairs) >= max_turns:
                break

        pairs.reverse()  # 转为时间正序
        history = [{"user": m, "assistant": a} for m, a in pairs]
        if history:
            logger.info(f"多轮历史加载: thread_id={thread_id}, {len(history)} 轮")
        return history
    except Exception as e:  # noqa: BLE001
        logger.warning(f"多轮历史加载失败(忽略,按无历史处理): {type(e).__name__}: {e}")
        return []


async def _list_checkpoints(checkpointer: Any, config: dict) -> list:
    """枚举 checkpoint 链(async/sync saver 双兼容,按时间倒序)"""
    alist = getattr(checkpointer, "alist", None)
    if alist is not None:
        out = []
        async for t in alist(config):
            out.append(t)
        return out
    # 同步 saver(PostgresSaver):list() 放线程里跑
    list_fn = getattr(checkpointer, "list", None)
    if list_fn is None:
        return []
    return await asyncio.to_thread(lambda: list(list_fn(config)))


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
