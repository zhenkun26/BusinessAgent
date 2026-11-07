"""Retained PostgreSQL jobs. Queue ownership never implies external-write fencing."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
from typing import Any
import uuid

from loguru import logger
from sqlalchemy import text

from app.core.tool_operations import canonical, fingerprint, safe_payload

QUEUES = ("tasks:doc_ingest", "tasks:saga_retry")
LEASE_SECONDS = 120
HEARTBEAT_SECONDS = 20
MAX_ATTEMPTS = 4
SAFE_ERRORS = frozenset({
    "TASK_OUTCOME_UNKNOWN", "TASK_LEASE_EXHAUSTED", "TASK_INPUT_INVALID",
    "TASK_DOCUMENT_CHANGED", "TASK_AUTHORIZATION_DENIED", "TASK_EMPTY_RESULT", "C13_REQUIRED",
    "SAGA_MANUAL_REQUIRED", "SAGA_RECOVERY_PENDING",
})


class QueueUnavailable(RuntimeError):
    """A store outcome cannot be proven; no handler replay is implied."""


class TaskRejected(RuntimeError):
    """Fixed terminal reason, without secrets or raw provider diagnostics."""

    def __init__(self, code: str) -> None:
        super().__init__(code if code in SAFE_ERRORS else "TASK_OUTCOME_UNKNOWN")


class TaskDeferred(RuntimeError):
    """Saga-only reconciliation may safely run again within the retained attempt budget."""


def validate_job(queue_name: str, scope: str, payload: dict[str, Any]) -> str:
    if queue_name not in QUEUES or not isinstance(scope, str) or not 1 <= len(scope) <= 128:
        raise TaskRejected("TASK_INPUT_INVALID")
    if not isinstance(payload, dict):
        raise TaskRejected("TASK_INPUT_INVALID")
    safe_payload(payload)
    return fingerprint({"queue": queue_name, "payload": payload})


async def enqueue_task(session: Any, queue_name: str, scope: str,
                       payload: dict[str, Any]) -> dict[str, Any]:
    """Caller owns the transaction: commit together with the business transition."""
    from app.observability.correlation import snapshot
    correlation = snapshot()
    digest = validate_job(queue_name, scope, payload)
    await session.execute(text("""INSERT INTO task_jobs
        (task_id, queue_name, scope_key, payload, payload_hash, originating_request_id, originating_trace_id)
        VALUES (:tid, :queue, :scope, CAST(:payload AS JSONB), :hash, :request_id, :trace_id)
        ON CONFLICT (scope_key) DO NOTHING"""), {
            "tid": str(uuid.uuid4()), "queue": queue_name, "scope": scope,
            "payload": canonical(payload), "hash": digest,
            "request_id": correlation["request_id"], "trace_id": correlation["trace_id"],
        })
    row = (await session.execute(text("SELECT * FROM task_jobs WHERE scope_key = :scope"),
                                 {"scope": scope})).mappings().first()
    if row is None or row["payload_hash"] != digest or row["queue_name"] != queue_name:
        raise TaskRejected("TASK_DOCUMENT_CHANGED")
    return dict(row)


class TaskStore:
    def __init__(self, factory: Any = None) -> None:
        if factory is None:
            from app.core.database import get_session_factory
            factory = get_session_factory()
        self.factory = factory

    async def query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            async with asyncio.timeout(10):
                async with self.factory() as session:
                    result = await session.execute(text(sql), params)
                    rows = [dict(row) for row in result.mappings().all()] if result.returns_rows else []
                    await session.commit()
                    return rows
        except Exception:
            raise QueueUnavailable("TASK_STORE_UNAVAILABLE") from None

    async def recover(self, queue_name: str) -> None:
        # Only the durable Saga handler can reconcile a running task without replaying writes.
        await self.query("""WITH expired AS (
            SELECT task_id FROM task_jobs WHERE queue_name = :queue
            AND state IN ('leased', 'running') AND lease_until <= clock_timestamp()
            ORDER BY lease_until LIMIT 100 FOR UPDATE SKIP LOCKED
        ) UPDATE task_jobs j SET
            state = CASE WHEN (j.state = 'running' AND :queue <> 'tasks:saga_retry') OR attempts >= :max THEN 'dead'
                         ELSE 'pending' END,
            error_code = CASE WHEN j.state = 'running' AND :queue <> 'tasks:saga_retry' THEN 'TASK_OUTCOME_UNKNOWN'
                         WHEN attempts >= :max THEN 'TASK_LEASE_EXHAUSTED' ELSE NULL END,
            available_at = clock_timestamp() + LEAST(300, 5 * power(2, attempts - 1))
                           * interval '1 second',
            owner_token = NULL, lease_until = NULL, updated_at = clock_timestamp()
            FROM expired WHERE j.task_id = expired.task_id""",
            {"queue": queue_name, "max": MAX_ATTEMPTS})

    async def claim(self, queue_name: str) -> dict[str, Any] | None:
        rows = await self.query("""WITH candidate AS (
            SELECT task_id FROM task_jobs WHERE queue_name = :queue AND state = 'pending'
            AND available_at <= clock_timestamp() AND attempts < :max
            ORDER BY available_at, created_at, task_id LIMIT 1 FOR UPDATE SKIP LOCKED
        ) UPDATE task_jobs j SET state = 'leased', attempts = attempts + 1,
            owner_token = :owner, lease_until = clock_timestamp() + :lease * interval '1 second',
            updated_at = clock_timestamp() FROM candidate
            WHERE j.task_id = candidate.task_id RETURNING j.*""", {
                "queue": queue_name, "max": MAX_ATTEMPTS,
                "owner": str(uuid.uuid4()), "lease": LEASE_SECONDS,
            })
        return rows[0] if rows else None

    async def transition(self, job: dict[str, Any], target: str,
                         *, error_code: str | None = None) -> bool:
        if target not in {"running", "done", "dead"}:
            raise ValueError("TASK_STATE_INVALID")
        if error_code is not None and error_code not in SAFE_ERRORS:
            raise ValueError("TASK_ERROR_INVALID")
        source = "leased" if target == "running" else "running"
        rows = await self.query("""UPDATE task_jobs SET state = :target, error_code = :error,
            updated_at = clock_timestamp(),
            lease_until = CASE WHEN :target = 'running' THEN lease_until ELSE NULL END
            WHERE task_id = :tid AND owner_token = :owner AND state = :source
            AND lease_until > clock_timestamp() RETURNING task_id""", {
                "tid": job["task_id"], "owner": job["owner_token"], "source": source,
                "target": target, "error": error_code,
            })
        return bool(rows)

    async def defer(self, job: dict[str, Any]) -> bool:
        if job['queue_name'] != 'tasks:saga_retry':
            return await self.transition(job, 'dead', error_code='TASK_OUTCOME_UNKNOWN')
        rows = await self.query("""UPDATE task_jobs SET
            state = CASE WHEN attempts >= :max THEN 'dead' ELSE 'pending' END,
            error_code = CASE WHEN attempts >= :max THEN 'TASK_LEASE_EXHAUSTED'
                             ELSE 'SAGA_RECOVERY_PENDING' END,
            owner_token = NULL, lease_until = NULL,
            available_at = clock_timestamp() + 30 * interval '1 second',
            updated_at = clock_timestamp()
            WHERE task_id = :tid AND owner_token = :owner AND state = 'running'
            AND lease_until > clock_timestamp() RETURNING task_id""", {
                'tid': job['task_id'], 'owner': job['owner_token'], 'max': MAX_ATTEMPTS})
        return bool(rows)

    async def renew(self, job: dict[str, Any]) -> bool:
        rows = await self.query("""UPDATE task_jobs SET
            lease_until = clock_timestamp() + :lease * interval '1 second',
            updated_at = clock_timestamp()
            WHERE task_id = :tid AND owner_token = :owner AND state = 'running'
            AND lease_until > clock_timestamp() RETURNING task_id""", {
                "tid": job["task_id"], "owner": job["owner_token"], "lease": LEASE_SECONDS,
            })
        return bool(rows)

    async def heartbeat(self, worker_id: str, queue_name: str) -> None:
        await self.query("""INSERT INTO task_consumers (worker_id, queue_name, last_seen)
            VALUES (:worker, :queue, clock_timestamp())
            ON CONFLICT (worker_id, queue_name) DO UPDATE SET last_seen = EXCLUDED.last_seen""",
            {"worker": worker_id, "queue": queue_name})


async def execute_claim(store: TaskStore, job: dict[str, Any],
                        handler: Callable[[dict[str, Any]], Awaitable[None]],
                        worker_id: str) -> None:
    if not await store.transition(job, "running"):
        return

    async def keep_lease() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            if not await store.renew(job):
                raise QueueUnavailable("TASK_LEASE_LOST")
            await store.heartbeat(worker_id, job["queue_name"])

    async def invoke() -> None:
        payload = job["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if validate_job(job["queue_name"], job["scope_key"], payload) != job["payload_hash"]:
            raise TaskRejected("TASK_INPUT_INVALID")
        from app.observability.correlation import request_id, task_id
        from app.observability.audit import get_audit_logger
        from app.observability.tracing import traced_span
        rt = request_id.set(job.get('originating_request_id') or '')
        tt = task_id.set(str(job['task_id']))
        audit = get_audit_logger()
        details = {'queue': job['queue_name'], 'scope': job['scope_key'],
                   'originating_trace_id': job.get('originating_trace_id')}
        try:
            with traced_span('worker.task', {'task_id': str(job['task_id']), **details}):
                await audit.log('worker_task_started', payload=details)
                try:
                    async with asyncio.timeout(300):
                        await handler(payload)
                except BaseException:
                    await audit.log('worker_task_interrupted', payload=details, success=False)
                    raise
                else:
                    await audit.log('worker_task_handler_returned', payload=details, success=True)
        finally:
            task_id.reset(tt)
            request_id.reset(rt)

    execution = asyncio.create_task(invoke())
    renewal = asyncio.create_task(keep_lease())
    try:
        done, _ = await asyncio.wait((execution, renewal), return_when=asyncio.FIRST_COMPLETED)
        if renewal in done:
            await renewal  # Propagate store/ownership loss; leave the job for recovery.
        try:
            await execution
        except TaskDeferred:
            await store.defer(job)
        except TaskRejected as exc:
            await store.transition(job, "dead", error_code=str(exc))
        except Exception:
            if job["queue_name"] == "tasks:saga_retry":
                await store.defer(job)
            else:
                await store.transition(job, "dead", error_code="TASK_OUTCOME_UNKNOWN")
        else:
            if not await store.transition(job, "done"):
                raise QueueUnavailable("TASK_LEASE_LOST")
    finally:
        execution.cancel()
        renewal.cancel()
        await asyncio.gather(execution, renewal, return_exceptions=True)


async def consume_tasks(queue_name: str, handler: Callable[[dict[str, Any]], Awaitable[None]],
                        *, store: TaskStore | None = None, worker_id: str | None = None) -> None:
    if queue_name not in QUEUES:
        raise ValueError("TASK_QUEUE_INVALID")
    store = store or TaskStore()
    worker_id = worker_id or str(uuid.uuid4())
    failures = 0
    while True:
        try:
            await store.recover(queue_name)
            job = await store.claim(queue_name)
            await store.heartbeat(worker_id, queue_name)
            if job is not None:
                await execute_claim(store, job, handler, worker_id)
            failures = 0
            await asyncio.sleep(1)
        except QueueUnavailable:
            failures += 1
            logger.warning("TASK_STORE_UNAVAILABLE")
            await asyncio.sleep(min(30, 2 ** min(failures - 1, 5)))


def task_metadata(row: Any) -> dict[str, Any]:
    """Explicit projection keeps payloads, credentials and ownership out of APIs."""
    fields = ("task_id", "queue_name", "state", "attempts", "error_code", "created_at", "updated_at")
    result = {key: row[key] for key in fields}
    result["task_id"] = str(result["task_id"])
    return result
