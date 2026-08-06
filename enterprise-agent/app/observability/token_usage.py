"""Token 用量统一采集(I-07)

设计(design.md 决策 5):
- 统一 chat model 封装(app/rag/llm.py)在构造时挂接 TokenUsageCallbackHandler,
  自动覆盖 planner/analysis/execution/aggregator/knowledge 全部调用方;
- handler 在每次 LLM 调用结束时:① 递增 Prometheus counter(按模型/类型);
  ② 累加进当前请求的累加器(contextvar,随图执行上下文隔离);
- 累加器由 run_graph/run_graph_stream 的 track_token_usage() 建立,
  aggregator 汇总后读总量落 AgentState.tokens_used,API 层再写审计 payload
  并异步回写 sessions.token_count。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
from loguru import logger

from app.observability.metrics import llm_token_usage


class TokenUsageAccumulator:
    """单次对话请求的 token 累加器(contextvar 隔离,线程/任务安全)"""

    def __init__(self) -> None:
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0

    def add(self, prompt: int, completion: int, total: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total


# 当前请求的累加器;None 表示不在 track_token_usage 作用域内(仅计数到 Prometheus)
_current_accumulator: ContextVar[TokenUsageAccumulator | None] = ContextVar(
    "token_usage_accumulator", default=None
)


@contextmanager
def track_token_usage() -> Iterator[TokenUsageAccumulator]:
    """建立请求级 token 采集作用域(图执行入口调用)"""
    accumulator = TokenUsageAccumulator()
    token = _current_accumulator.set(accumulator)
    try:
        yield accumulator
    finally:
        _current_accumulator.reset(token)


def current_token_usage() -> TokenUsageAccumulator | None:
    """获取当前请求累加器(不在采集作用域内返回 None)"""
    return _current_accumulator.get()


def snapshot_total_tokens() -> int:
    """当前累计 total_tokens 快照;不在采集作用域内返回 0"""
    accumulator = _current_accumulator.get()
    return accumulator.total_tokens if accumulator else 0


class TokenUsageCallbackHandler(AsyncCallbackHandler):
    """LangChain 回调:统一采集每次 LLM 调用的 token 用量

    双落地:
    - Prometheus counter(llm_token_usage,labels: model/token_type)——每次调用递增;
    - 请求级累加器(contextvar)——存在时累加,供 aggregator/API 汇总。
    """

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            prompt, completion, total, model = _extract_usage(response)
            if total <= 0:
                return
            llm_token_usage.labels(model=model, token_type="prompt").inc(prompt)
            llm_token_usage.labels(model=model, token_type="completion").inc(completion)
            llm_token_usage.labels(model=model, token_type="total").inc(total)
            accumulator = _current_accumulator.get()
            if accumulator is not None:
                accumulator.add(prompt, completion, total)
        except Exception as e:  # noqa: BLE001 采集失败绝不阻断 LLM 链路
            logger.warning(f"token 用量采集失败(已忽略): {e}")


def _extract_usage(response: LLMResult) -> tuple[int, int, int, str]:
    """从 LLMResult 提取 (prompt, completion, total, model)

    兼容两种口径:
    - OpenAI 兼容端点(ChatOpenAI): response.llm_output["token_usage"]
    - 本地 ChatOllama 等: generation.message.usage_metadata
    """
    llm_output = response.llm_output or {}
    model = str(llm_output.get("model_name") or llm_output.get("model") or "unknown")

    usage = llm_output.get("token_usage")
    if isinstance(usage, dict) and usage.get("total_tokens"):
        return (
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            int(usage.get("total_tokens", 0)),
            model,
        )

    # usage_metadata 口径(LangChain 1.x 标准化字段)
    for generation_list in response.generations or []:
        for generation in generation_list:
            message = getattr(generation, "message", None)
            metadata = getattr(message, "usage_metadata", None)
            if isinstance(metadata, dict) and metadata.get("total_tokens"):
                return (
                    int(metadata.get("input_tokens", 0)),
                    int(metadata.get("output_tokens", 0)),
                    int(metadata.get("total_tokens", 0)),
                    model,
                )
    return 0, 0, 0, model


# 全局单例(无内部状态,实例间共享安全;按请求隔离靠 contextvar)
_handler: TokenUsageCallbackHandler | None = None


def get_token_usage_handler() -> TokenUsageCallbackHandler:
    """获取全局 token 采集回调(挂到统一 chat model 封装)"""
    global _handler
    if _handler is None:
        _handler = TokenUsageCallbackHandler()
    return _handler
