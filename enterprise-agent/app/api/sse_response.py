"""Bound actual ASGI sends and clean up even before the first body iteration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping

import anyio
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse
from starlette.types import Message, Receive, Scope, Send

from app.core.sse_stream import SEND_TIMEOUT_SECONDS, STREAM_SECONDS


class BoundedStreamingResponse(StreamingResponse):
    def __init__(self, content: AsyncGenerator[str, None], *, close: Callable[[], Awaitable[None]],
                 headers: Mapping[str, str] | None = None) -> None:
        super().__init__(content, media_type='text/event-stream', headers=headers)
        self._close_stream = close
        self._stream = content

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def bounded_send(message: Message) -> None:
            async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                await send(message)

        try:
            async with asyncio.timeout(STREAM_SECONDS):
                await super().__call__(scope, receive, bounded_send)
        except (TimeoutError, OSError, ClientDisconnect):
            # An already-started or stalled transport cannot promise an error frame.
            pass
        finally:
            # Starlette's disconnect cancel scope must not cancel our own cleanup.
            with anyio.CancelScope(shield=True):
                await self._close_stream()
                await self._stream.aclose()
