"""Shared, token-bound cancellation leases. Cancellation is not rollback."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
import uuid

from loguru import logger

from app.core.runtime_state import RuntimeStateUnavailable, runtime_client, state_key

LEASE_SECONDS = 30
POLL_SECONDS = 0.5

# Compare-and-renew, signal and release are indivisible on the shared store.
POLL_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('EXPIRE', KEYS[1], ARGV[2])
if redis.call('GET', KEYS[2]) == ARGV[1] then return 2 end
return 1
"""
CANCEL_SCRIPT = """
local owner = redis.call('GET', KEYS[1])
if not owner then return 0 end
redis.call('SET', KEYS[2], owner, 'EX', ARGV[1])
return 1
"""
RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then redis.call('DEL', KEYS[1]) end
if redis.call('GET', KEYS[2]) == ARGV[1] then redis.call('DEL', KEYS[2]) end
return 1
"""


class SessionBusy(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SESSION_ALREADY_RUNNING")


class CancellationLease:
    def __init__(self, session_id: str, token: str) -> None:
        self.keys = (state_key("run", session_id), state_key("cancel", session_id))
        self.token = token
        self.failed = False
        self.cancel_requested = False

    async def _watch(self, owner: asyncio.Task) -> None:
        try:
            async with runtime_client() as client:
                while True:
                    status = await client.eval(POLL_SCRIPT, 2, *self.keys,
                                               self.token, LEASE_SECONDS)
                    if status != 1:
                        self.failed = status != 2
                        self.cancel_requested = status == 2
                        owner.cancel()
                        return
                    await asyncio.sleep(POLL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.failed = True
            owner.cancel()

    @asynccontextmanager
    async def watch(self, *, release_on_exit: bool = True) -> AsyncIterator[None]:
        owner = asyncio.current_task()
        assert owner is not None
        watcher = asyncio.create_task(self._watch(owner))
        try:
            yield
            # A nested operation may catch CancelledError; do not report success afterwards.
            if self.failed:
                raise RuntimeStateUnavailable()
            if self.cancel_requested:
                raise asyncio.CancelledError()
        except asyncio.CancelledError:
            if self.failed:
                raise RuntimeStateUnavailable() from None
            raise
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            if release_on_exit:
                await self.release()

    async def release(self) -> None:
        try:
            async with runtime_client() as client:
                await client.eval(RELEASE_SCRIPT, 2, *self.keys, self.token)
        except RuntimeStateUnavailable:
            # Expiry bounds an unreachable lease; never mask the original result.
            logger.warning("RUNTIME_STATE_RELEASE_FAILED")


async def reserve_session(session_id: str) -> CancellationLease:
    lease = CancellationLease(session_id, uuid.uuid4().hex)
    async with runtime_client() as client:
        acquired = await client.set(lease.keys[0], lease.token, nx=True, ex=LEASE_SECONDS)
    if not acquired:
        raise SessionBusy()
    return lease


async def request_cancel(session_id: str) -> bool:
    """Return signal acceptance, not confirmation that work has stopped."""
    async with runtime_client() as client:
        return bool(await client.eval(CANCEL_SCRIPT, 2,
            state_key("run", session_id), state_key("cancel", session_id), LEASE_SECONDS))
