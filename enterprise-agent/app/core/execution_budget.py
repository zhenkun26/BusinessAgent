"""Request-owned admission limits; no provider billing or hard I/O deadline claim."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from threading import Lock

MAX_PLAN_TASKS = 4
MAX_REQUEST_TASKS = 12
MAX_ACTIVE_TASKS = 2
MAX_MODEL_CALLS = 16
MAX_PROMPT_BYTES = 64 * 1024
MAX_TOTAL_PROMPT_BYTES = 256 * 1024
MAX_OUTPUT_TOKENS = 1024
MAX_INPUT_BYTES = 16 * 1024
ADMISSION_SECONDS = 120


class ExecutionBudgetExceeded(RuntimeError):
    """Fixed public failure; never includes prompt, user content or provider details."""

    def __init__(self) -> None:
        super().__init__("EXECUTION_BUDGET_EXCEEDED")


class ExecutionBudget:
    def __init__(self) -> None:
        self.calls = 0
        self.prompt_bytes = 0
        self.tasks = 0
        self.deadline = time.monotonic() + ADMISSION_SECONDS
        self.closed = False
        self.lock = Lock()
        self.slots = asyncio.Semaphore(MAX_ACTIVE_TASKS)

    def _check_locked(self) -> None:
        if self.closed or time.monotonic() >= self.deadline:
            self.closed = True
            raise ExecutionBudgetExceeded()

    def check(self) -> None:
        with self.lock:
            self._check_locked()

    def reject(self) -> None:
        with self.lock:
            self.closed = True
        raise ExecutionBudgetExceeded()

    def close(self) -> None:
        with self.lock:
            self.closed = True

    def reserve_model(self, prompt_bytes: int) -> None:
        with self.lock:
            self._check_locked()
            if (prompt_bytes > MAX_PROMPT_BYTES or self.calls >= MAX_MODEL_CALLS
                    or self.prompt_bytes + prompt_bytes > MAX_TOTAL_PROMPT_BYTES):
                self.closed = True
                raise ExecutionBudgetExceeded()
            self.calls += 1
            self.prompt_bytes += prompt_bytes

    def reserve_tasks(self, count: int) -> None:
        with self.lock:
            self._check_locked()
            if self.tasks + count > MAX_REQUEST_TASKS:
                self.closed = True
                raise ExecutionBudgetExceeded()
            self.tasks += count


_current: ContextVar[ExecutionBudget | None] = ContextVar("execution_budget", default=None)


def current_budget() -> ExecutionBudget | None:
    return _current.get()


def check_execution_budget() -> None:
    budget = current_budget()
    if budget is not None:
        budget.check()


def check_task_count(count: int) -> None:
    if count > MAX_PLAN_TASKS:
        budget = current_budget()
        if budget is not None:
            budget.reject()
        raise ExecutionBudgetExceeded()


@contextmanager
def execution_budget(message: str) -> Iterator[ExecutionBudget]:
    budget = ExecutionBudget()
    token = _current.set(budget)
    try:
        if len(message.encode("utf-8")) > MAX_INPUT_BYTES:
            budget.reject()
        yield budget
        budget.check()
    finally:
        budget.close()
        _current.reset(token)


@asynccontextmanager
async def execution_slot() -> AsyncIterator[None]:
    budget = current_budget()
    if budget is None:
        yield
        return
    budget.check()
    async with budget.slots:
        budget.check()
        yield
        budget.check()


def truncate_context(text: str, byte_limit: int) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= byte_limit:
        return text
    marker = "…[truncated]"
    return raw[:byte_limit - len(marker.encode("utf-8"))].decode("utf-8", errors="ignore") + marker


def bounded_history(history: list[dict]) -> list[dict]:
    """Copy only eligible caller-supplied turns; never changes authorization or storage."""
    return [{**turn, "user": truncate_context(turn.get("user") or "", 2000),
             "assistant": truncate_context(turn.get("assistant") or "", 800)}
            for turn in history[-5:]]
