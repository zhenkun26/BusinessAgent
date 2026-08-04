"""对话取消注册表(P2-2 用户取消机制)

进程内 session_id → asyncio.Task 注册表:
- /chat/message 把 run_graph 包成 Task 并注册
- /chat/cancel 按 session_id 找到 Task 并 cancel

取消语义:
- asyncio.Task.cancel() 在下一个 await 点生效;P2-2 起 Agent 内 LLM 调用
  已全部 ainvoke 化,取消在 LLM 等待期间即可生效(不再等 HTTP 返回)
- 已执行的工具副作用不撤销(取消 ≠ 回滚);审批类高风险操作有人工兜底,
  Saga 中途取消的补偿留待后续
- 多实例部署时本注册表仅管本进程任务(跨实例取消需共享存储,暂不需要)
"""

import asyncio

from loguru import logger

_tasks: dict[str, asyncio.Task] = {}


def register_task(session_id: str, task: asyncio.Task) -> None:
    _tasks[session_id] = task


def unregister_task(session_id: str) -> None:
    _tasks.pop(session_id, None)


def request_cancel(session_id: str) -> bool:
    """请求取消指定会话;无可取消任务返回 False"""
    task = _tasks.get(session_id)
    if task is None or task.done():
        return False
    logger.info(f"会话取消请求: session_id={session_id}")
    task.cancel()
    return True
