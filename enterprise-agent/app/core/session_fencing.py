"""Database-clock ownership and append-only publication of isolated checkpoint runs.

Raw saver writes are isolated, not cancelled atomically across stores. Only the
publication transaction makes a checkpoint and terminal metadata session-visible.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
import hashlib
from typing import Any, AsyncIterator, Iterator

from sqlalchemy import text

from app.core.runtime_state import RuntimeStateUnavailable

LEASE_SECONDS = 30
_current: ContextVar[SessionFence | None] = ContextVar("session_write_fence", default=None)


@asynccontextmanager
async def transaction() -> AsyncIterator[Any]:
    from app.core.database import get_session_factory

    try:
        async with asyncio.timeout(10):
            async with get_session_factory()() as db:
                async with db.begin():
                    await db.execute(text("SET LOCAL lock_timeout = '5s'"))
                    await db.execute(text("SET LOCAL statement_timeout = '5s'"))
                    yield db
    except RuntimeStateUnavailable:
        raise
    except Exception:
        raise RuntimeStateUnavailable() from None


async def query(db: Any, sql: str, params: dict[str, Any]) -> Any:
    return (await db.execute(text(sql), params)).mappings()


class SessionFence:
    def __init__(self, session_id: str, token: str) -> None:
        self.session_id = session_id
        self.token = token
        self.thread_id = "c10_" + hashlib.sha256(session_id.encode()).hexdigest() + "_" + token
        self.finished = False
        self._lock = asyncio.Lock()

    @property
    def params(self) -> dict[str, Any]:
        return {"sid": self.session_id, "owner": self.token, "lease": LEASE_SECONDS}

    @property
    def config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id, "checkpoint_ns": ""}}

    @contextmanager
    def scope(self) -> Iterator[None]:
        token = _current.set(self)
        try:
            yield
        finally:
            _current.reset(token)

    async def claim(self) -> bool:
        async with transaction() as db:
            row = (await query(db, """INSERT INTO session_write_fences
                (session_id, owner_token, lease_until)
                VALUES (:sid, CAST(:owner AS uuid),
                        clock_timestamp() + :lease * interval '1 second')
                ON CONFLICT (session_id) DO UPDATE SET owner_token = EXCLUDED.owner_token,
                lease_until = clock_timestamp() + :lease * interval '1 second'
                WHERE session_write_fences.owner_token IS NULL
                   OR session_write_fences.lease_until <= clock_timestamp()
                RETURNING session_id""", self.params)).first()
        return row is not None

    async def renew(self) -> bool:
        async with self._lock:
            if self.finished:
                return True
            async with transaction() as db:
                row = (await query(db, """UPDATE session_write_fences
                    SET lease_until = clock_timestamp() + :lease * interval '1 second'
                    WHERE session_id = :sid AND owner_token = CAST(:owner AS uuid)
                      AND lease_until > clock_timestamp() RETURNING session_id""",
                    self.params)).first()
            return row is not None

    async def lock_owner(self, db: Any) -> bool:
        return (await query(db, """SELECT session_id FROM session_write_fences
            WHERE session_id = :sid AND owner_token = CAST(:owner AS uuid)
              AND lease_until > clock_timestamp() FOR UPDATE""", self.params)).first() is not None

    async def finish(self, status: str, *, error: str | None = None, tokens: int = 0,
                     publication: dict[str, str] | None = None) -> bool:
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError("SESSION_STATUS_INVALID")
        if (status == "completed") != (publication is not None):
            raise RuntimeStateUnavailable()
        async with self._lock:
            async with transaction() as db:
                if not await self.lock_owner(db):
                    return False
                if publication is not None:
                    if (publication.get("thread_id") != self.thread_id
                            or not publication.get("checkpoint_id")
                            or publication.get("backend") not in {"redis", "postgres", "memory"}
                            or publication.get("checkpoint_ns") != ""):
                        raise RuntimeStateUnavailable()
                    await query(db, """INSERT INTO session_checkpoint_publications
                        (session_id, owner_token, backend, thread_id, checkpoint_ns, checkpoint_id)
                        VALUES (:sid, CAST(:owner AS uuid), :backend, :thread_id,
                                :checkpoint_ns, :checkpoint_id)""",
                        dict(self.params, **publication))
                row = (await query(db, """UPDATE sessions SET status = :status,
                    completed_at = CURRENT_TIMESTAMP, error = :error,
                    token_count = COALESCE(token_count, 0) + :tokens
                    WHERE session_id = :sid AND EXISTS
                      (SELECT 1 FROM session_write_fences WHERE session_id = :sid
                       AND owner_token = CAST(:owner AS uuid) AND lease_until > clock_timestamp())
                    RETURNING session_id""", dict(self.params, status=status, error=error,
                        tokens=max(0, tokens) if status == "completed" else 0))).first()
                if row is None:
                    raise RuntimeStateUnavailable()  # Also rolls back the publication.
                await query(db, """UPDATE session_write_fences SET owner_token = NULL,
                    lease_until = NULL WHERE session_id = :sid
                    AND owner_token = CAST(:owner AS uuid)""", self.params)
            self.finished = True
            return True

    async def release(self) -> None:
        async with transaction() as db:
            await query(db, """UPDATE session_write_fences SET owner_token = NULL,
                lease_until = NULL WHERE session_id = :sid
                AND owner_token = CAST(:owner AS uuid)""", self.params)


def active_fence(session_id: str) -> SessionFence:
    fence = _current.get()
    if fence is None or fence.session_id != session_id or fence.finished:
        raise RuntimeStateUnavailable()
    return fence


async def publications(session_id: str, limit: int = 100) -> list[dict[str, Any]]:
    async with transaction() as db:
        rows = (await query(db, """SELECT backend, thread_id, checkpoint_ns, checkpoint_id
            FROM session_checkpoint_publications WHERE session_id = :sid
            ORDER BY publication_id DESC LIMIT :limit""",
            {"sid": session_id, "limit": min(max(limit, 1), 100)})).all()
        return [dict(row) for row in rows]
