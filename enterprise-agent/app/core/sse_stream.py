"""Single-event-loop SSE admission, independent terminals and bounded task joins."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Coroutine
import json
from typing import Any

from loguru import logger

MAX_QUEUED_EVENTS = 64
MAX_BUFFER_BYTES = 256 * 1024
MAX_EVENT_BYTES = 64 * 1024
BUFFER_WAIT_SECONDS = 5.0
SEND_TIMEOUT_SECONDS = 5.0
STREAM_SECONDS = 180.0
CLEANUP_SECONDS = 5.0


class StreamFailure(RuntimeError):
    """Only code-owned, fixed failure codes may be passed here."""


def encode_event(event: dict[str, Any]) -> str:
    frame = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    if len(frame.encode('utf-8')) > MAX_EVENT_BYTES:
        raise StreamFailure('STREAM_EVENT_TOO_LARGE')
    return frame


class SSEChannel:
    """One producer/consumer, with no awaits between capacity checks and mutation."""

    def __init__(self) -> None:
        self.frames: deque[tuple[str, int]] = deque()
        self.buffer_bytes = 0
        self.changed = asyncio.Event()
        self.terminal: str | None = None
        self.finished = False
        self.closed = False

    def ensure_open(self) -> None:
        if self.closed or self.finished:
            raise StreamFailure('STREAM_CLOSED')

    async def put(self, event: dict[str, Any]) -> None:
        self.ensure_open()
        frame = encode_event(event)
        size = len(frame.encode('utf-8'))
        try:
            async with asyncio.timeout(BUFFER_WAIT_SECONDS):
                while True:
                    self.ensure_open()
                    if (len(self.frames) < MAX_QUEUED_EVENTS
                            and self.buffer_bytes + size <= MAX_BUFFER_BYTES):
                        self.frames.append((frame, size))
                        self.buffer_bytes += size
                        self.changed.set()
                        return
                    self.changed.clear()
                    await self.changed.wait()
        except TimeoutError:
            raise StreamFailure('STREAM_BACKPRESSURE_TIMEOUT') from None

    def finish(self, terminal: str, *, discard: bool = False) -> None:
        # Terminal frames have already been encoded/validated before publication.
        if self.closed or self.finished:
            return
        if len(terminal.encode('utf-8')) > MAX_EVENT_BYTES:
            raise StreamFailure('STREAM_EVENT_TOO_LARGE')
        if discard:
            self.frames.clear()
            self.buffer_bytes = 0
        self.terminal = terminal
        self.finished = True
        self.changed.set()

    async def get(self) -> str | None:
        while True:
            if self.closed:
                return None
            if self.frames:
                frame, size = self.frames.popleft()
                self.buffer_bytes -= size
                self.changed.set()
                return frame
            if self.terminal is not None:
                frame, self.terminal = self.terminal, None
                return frame
            if self.finished:
                return None
            self.changed.clear()
            await self.changed.wait()

    def close(self) -> None:
        self.closed = True
        self.frames.clear()
        self.buffer_bytes = 0
        self.terminal = None
        self.changed.set()


# Retain cancellation-resistant tasks until completion and consume late exceptions.
_pending: set[asyncio.Task[Any]] = set()


def observe_task(task: asyncio.Task[Any]) -> None:
    _pending.add(task)

    def done(completed: asyncio.Task[Any]) -> None:
        _pending.discard(completed)
        if not completed.cancelled() and completed.exception() is not None:
            logger.warning('STREAM_BACKGROUND_TASK_FAILED')

    task.add_done_callback(done)


async def bounded_cleanup(work: Coroutine[Any, Any, Any]) -> None:
    task = asyncio.create_task(work)
    observe_task(task)
    try:
        done, _ = await asyncio.wait({task}, timeout=CLEANUP_SECONDS)
        if not done:
            task.cancel()
            logger.warning('STREAM_CLEANUP_TIMEOUT')
    except BaseException:
        task.cancel()
        raise


async def join_producer(task: asyncio.Task[Any], *, cancel: bool = True) -> bool:
    if cancel and not task.done():
        task.cancel()
    done, _ = await asyncio.wait({task}, timeout=CLEANUP_SECONDS)
    if not done:
        # The observer retains it; cancellation is cooperative, never a forced kill.
        task.cancel()
        logger.warning('STREAM_PRODUCER_STOP_TIMEOUT')
    return bool(done)
