"""LangGraph 主图组装(对应 v3 方案 6.3 节)

图结构(LangGraph Send API 正确用法):
    START
      ↓
    planner
      ↓ (route_after_planner 条件边)
    ├─ "aggregator" (闲聊/无子任务) → aggregator → END
    └─ list[Send("agent_executor", sub_state)] (多子任务,并行 fan-out)
         ↓
       agent_executor (并行 N 个)
         ↓
       aggregator → END

关键点:
- Send 用在条件边函数返回值,不是节点返回值
- 条件边返回 list[Send] 时,LangGraph 自动并行执行
- add_conditional_edges 第三参数指定可路由目标节点

W6 增强: 接入 Checkpointer 支持断点恢复
- build_graph(checkpointer=...) 编译时注入 checkpointer
- run_graph 传入 thread_id,跨进程状态恢复
- 默认 thread_id = conversation_id(同一会话可恢复)
"""

from __future__ import annotations

from typing import Optional

from langgraph.graph import END, START, StateGraph
from loguru import logger

from app.graph.aggregator import aggregator_node
from app.graph.dispatcher import route_after_planner
from app.graph.executor import agent_executor_node
from app.graph.planner import planner_node
from app.graph.state import AgentState, UserInput, make_initial_state

# 编译后的图缓存:按 checkpointer backend 区分
# {"none": graph(无checkpointer), "redis": graph(redis), "memory": graph(memory), ...}
_compiled_graphs: dict[str, object] = {}


def build_graph(checkpointer: Optional[object] = None, backend_tag: str = "none"):
    """构建并编译 LangGraph

    Args:
        checkpointer: Checkpointer 实例(None 表示不启用断点恢复,用于测试)
        backend_tag: checkpointer 后端标识(用于缓存键),如 "redis"/"postgres"/"memory"/"none"

    返回编译后的 CompiledGraph,可重复 invoke。
    同一 backend_tag 只编译一次(缓存)。
    """
    if backend_tag in _compiled_graphs:
        return _compiled_graphs[backend_tag]

    g = StateGraph(AgentState)

    # 添加节点
    g.add_node("planner", planner_node)
    g.add_node("agent_executor", agent_executor_node)
    g.add_node("aggregator", aggregator_node)

    # 边:START → planner
    g.add_edge(START, "planner")

    # 条件路由:planner → aggregator(闲聊) 或 agent_executor(fan-out)
    # route_after_planner 返回 "aggregator" 或 list[Send]
    # 第三参数 path_map 指定可路由的目标节点(含 Send 目标)
    g.add_conditional_edges(
        "planner",
        route_after_planner,
        ["agent_executor", "aggregator"],
    )

    # agent_executor → aggregator
    g.add_edge("agent_executor", "aggregator")

    # aggregator → END
    g.add_edge("aggregator", END)

    compiled = g.compile(checkpointer=checkpointer) if checkpointer else g.compile()
    _compiled_graphs[backend_tag] = compiled
    logger.info(f"LangGraph 主图编译完成(backend={backend_tag}, checkpointer={'on' if checkpointer else 'off'})")
    return compiled


async def run_graph(
    user_input: UserInput,
    thread_id: Optional[str] = None,
    use_checkpointer: bool = True,
) -> AgentState:
    """运行图(异步入口,W6 增强:支持 thread_id 断点恢复)

    Args:
        user_input: 用户输入
        thread_id: 断点恢复线程 ID;None 时用 conversation_id(同一会话可恢复)
        use_checkpointer: 是否启用 checkpointer(True 走三级降级链;False 纯内存执行,用于测试)

    Returns:
        最终状态(含 final_answer, sources, confidence 等)
    """
    config = None
    backend_tag = "none"

    if use_checkpointer:
        from app.graph.checkpointer import get_checkpointer

        checkpointer, backend_tag = await get_checkpointer()
        graph = build_graph(checkpointer=checkpointer, backend_tag=backend_tag)

        # thread_id 默认用 conversation_id,保证同一会话可跨进程恢复
        tid = thread_id or user_input.conversation_id
        config = {"configurable": {"thread_id": tid}}

        # 多轮上下文:从 checkpoint 链加载最近历史(ainvoke 前,只含历史轮次)
        from app.graph.history import load_recent_history

        history = await load_recent_history(tid)

        logger.info(
            f"运行 LangGraph(checkpointer={backend_tag}, thread_id={tid}): "
            f"request_id={user_input.request_id}, user={user_input.username}, "
            f"message={user_input.message[:80]!r}"
        )
    else:
        graph = build_graph()
        history = []
        logger.info(
            f"运行 LangGraph(无 checkpointer): request_id={user_input.request_id}, "
            f"user={user_input.username}, message={user_input.message[:80]!r}"
        )

    initial_state = make_initial_state(user_input)
    initial_state["history"] = history
    final_state = await graph.ainvoke(initial_state, config=config)
    return final_state


def run_graph_sync(user_input: UserInput) -> AgentState:
    """运行图(同步入口,便于非 async 上下文调用)"""
    import asyncio

    return asyncio.run(run_graph(user_input))


async def run_graph_stream(
    user_input: UserInput,
    thread_id: Optional[str] = None,
    use_checkpointer: bool = True,
):
    """流式运行图(SSE 用):async generator,产出进度/token 事件

    事件类型:
    - {"type": "progress", "node": "planner|agent_executor|aggregator", "phase": "start|end"}
    - {"type": "token", "data": "<增量文本>"}  ← 仅带 final_answer 标签的生成调用
      (knowledge 答案 / analysis 报告 / aggregator 汇总;planner 分类/自评等中间调用不推)

    最终状态不在本生成器返回,由调用方在流结束后用 aget_state 取
    (checkpointer 快照即最终 AgentState)。
    """
    if not use_checkpointer:
        # 流式入口面向 API,强制走 checkpointer(便于取最终状态)
        raise ValueError("run_graph_stream 要求 use_checkpointer=True")

    from app.graph.checkpointer import get_checkpointer

    checkpointer, backend_tag = await get_checkpointer()
    graph = build_graph(checkpointer=checkpointer, backend_tag=backend_tag)
    tid = thread_id or user_input.conversation_id
    config = {"configurable": {"thread_id": tid}}
    logger.info(
        f"流式运行 LangGraph(checkpointer={backend_tag}, thread_id={tid}): "
        f"request_id={user_input.request_id}, user={user_input.username}"
    )

    initial_state = make_initial_state(user_input)

    # 多轮上下文:从 checkpoint 链加载最近历史(astream_events 前,只含历史轮次)
    from app.graph.history import load_recent_history

    initial_state["history"] = await load_recent_history(tid)

    watched_nodes = ("planner", "agent_executor", "aggregator")
    last_progress: Optional[tuple] = None

    async for ev in graph.astream_events(initial_state, config=config, version="v2"):
        kind = ev.get("event", "")
        node = ev.get("metadata", {}).get("langgraph_node")

        if kind in ("on_chain_start", "on_chain_end") and node in watched_nodes:
            phase = "start" if kind.endswith("_start") else "end"
            # astream_events 对同一节点会发 chain/runnable 两组事件,去重
            if (node, phase) != last_progress:
                last_progress = (node, phase)
                yield {"type": "progress", "node": node, "phase": phase}
        elif kind == "on_chat_model_stream" and "final_answer" in ev.get("tags", []):
            chunk = ev.get("data", {}).get("chunk")
            text = getattr(chunk, "content", None) if chunk is not None else None
            if text:
                yield {"type": "token", "data": text}


def reset_graph():
    """重置编译后的图缓存(checkpointer 变更/测试用)"""
    _compiled_graphs.clear()
    logger.info("LangGraph 主图缓存已清空")
