"""Durable action identities and one-way dispatch claims; no implicit DDL or replay."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import asyncio
import hashlib
import json
from typing import Any, Iterator
import uuid

from app.security.redaction import redact_value


class OperationError(RuntimeError):
    """Safe fixed error code; never include request bodies or database exceptions."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def safe_payload(value: Any) -> None:
    if redact_value(value) != value:
        raise OperationError("ACTION_CREDENTIAL_CONTENT_REJECTED")
    if len(canonical(value).encode("utf-8")) > 65536:
        raise OperationError("ACTION_PAYLOAD_TOO_LARGE")


def valid_uuid(value: Any) -> str:
    try:
        parsed = uuid.UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError
        return value
    except (ValueError, TypeError, AttributeError):
        raise OperationError("ACTION_IDENTITY_INVALID") from None


_approval_scope: ContextVar[tuple[str, str, str] | None] = ContextVar(
    "tool_approval_scope", default=None)


@contextmanager
def approved_calls(user_id: str, approval_id: str, calls: list[dict]) -> Iterator[None]:
    """Internal capability issued after fresh JWT and current participant checks."""
    token = _approval_scope.set((user_id, approval_id, fingerprint(calls)))
    try:
        yield
    finally:
        _approval_scope.reset(token)


def approval_authorized(context: dict, calls: list[dict]) -> bool:
    from app.core.approval_deadline import in_approval_dispatch
    return _committed_approval.get() is not None and in_approval_dispatch() and _approval_scope.get() == (
        context.get("user_id"), context.get("approval_id"), fingerprint(calls))


_committed_approval: ContextVar[Any] = ContextVar("committed_approval", default=None)
_action_context: ContextVar[dict | None] = ContextVar("action_context", default=None)


@contextmanager
def committed_approval_dispatch(row: Any, calls: list[dict]) -> Iterator[None]:
    """Paired capability issued only after the API confirms the claim commit."""
    from app.core import approval_deadline as deadline
    deadline.require_contract(row)
    if (row.status != "executing" or not row.execution_claim or not row.execution_id
            or canonical(calls) != canonical(deadline.payload(row)["tool_calls"])):
        raise OperationError("APPROVAL_COMMITTED_CLAIM_REQUIRED")
    valid_uuid(str(row.execution_claim))
    valid_uuid(str(row.execution_id))
    if not calls or len({valid_uuid(c.get("operation_id")) for c in calls}) != len(calls):
        raise OperationError("APPROVAL_PLAN_CONFLICT")
    token = _committed_approval.set(row)
    try:
        with deadline.dispatch_scope(), approved_calls(row.requester_id, row.approval_id, calls):
            yield
    finally:
        _committed_approval.reset(token)


@contextmanager
def action_dispatch(context: dict) -> Iterator[None]:
    token = _action_context.set(context)
    try:
        yield
    finally:
        _action_context.reset(token)


async def guard_action_owner(db: Any, user_id: str) -> None:
    """Unknown/rejected/in-flight effects stop new work, including new request IDs."""
    from sqlalchemy import text
    from app.core import approval_deadline as deadline
    approval = _committed_approval.get()
    await deadline.guard_owner(db, user_id, exclude=(approval.approval_id if approval else None))
    held = (await db.execute(text("""SELECT o.operation_id FROM tool_operations o
        JOIN tool_executions e USING (execution_id)
        WHERE e.owner_id = :uid AND o.state IN ('dispatched', 'unknown', 'rejected')
        LIMIT 1"""), {"uid": user_id})).fetchone()
    saga_scope = _saga_scope.get() or ("", "")
    saga_hold = (await db.execute(text("""SELECT s.saga_id FROM saga_runs s
        JOIN tool_executions e ON e.execution_id = s.saga_id
        WHERE e.owner_id = :uid AND s.state IN ('forward', 'manual', 'aborting', 'compensated')
        AND (s.state <> 'forward' OR s.saga_id::text <> :sid
             OR s.owner_token::text <> :owner OR s.lease_until IS NULL
             OR s.lease_until <= clock_timestamp())
        LIMIT 1"""), {"uid": user_id, "sid": saga_scope[0], "owner": saga_scope[1]})).fetchone()
    if held is not None or saga_hold is not None:
        raise OperationError("ACTION_HUMAN_REVIEW_REQUIRED")


_saga_scope: ContextVar[tuple[str, str] | None] = ContextVar('saga_dispatch_scope', default=None)


@contextmanager
def saga_dispatch(saga_id: str, owner: str) -> Iterator[None]:
    """Internal capability; never accepted from request/queue payloads."""
    token = _saga_scope.set((saga_id, owner))
    try:
        yield
    finally:
        _saga_scope.reset(token)


class OperationStore:
    """Short independent transactions, committed before any external side effect."""

    def __init__(self) -> None:
        from app.core.database import get_session_factory
        self.factory = get_session_factory()

    async def _query(self, sql: str, args: dict) -> dict | None:
        from sqlalchemy import text
        try:
            async with self.factory() as session:
                result = await session.execute(text(sql), args)
                row = result.mappings().first() if result.returns_rows else None
                await session.commit()
                return dict(row) if row is not None else None
        except Exception:
            raise OperationError("ACTION_STORE_UNAVAILABLE") from None

    async def prepare(self, scope: dict, calls: list[dict]) -> dict:
        safe_payload(calls)
        scope_key = fingerprint(scope)
        plan_hash = fingerprint(calls)
        execution_id = str(uuid.uuid4())
        entries = [{**call, "operation_id": str(uuid.uuid4())} for call in calls]
        # The entire plan is inserted once: conflicting requests cannot replace IDs.
        await self._query("""INSERT INTO tool_executions
            (execution_id, scope_key, plan_hash, owner_id, session_id, calls)
            VALUES (:eid, :scope, :hash, :owner, :sid, CAST(:calls AS JSONB))
            ON CONFLICT (scope_key) DO NOTHING""", {
                "eid": execution_id, "scope": scope_key, "hash": plan_hash,
                "owner": scope["user_id"], "sid": scope["session_id"],
                "calls": canonical(entries)})
        row = await self._query("SELECT * FROM tool_executions WHERE scope_key = :scope",
                                {"scope": scope_key})
        if row is None or row["plan_hash"] != plan_hash:
            raise OperationError("ACTION_PLAN_CONFLICT")
        # Idempotent materialization recovers a crash after plan persistence.
        for index, entry in enumerate(row["calls"]):
            await self._query("""INSERT INTO tool_operations
                (operation_id, execution_id, slot, intent, state)
                VALUES (:oid, :eid, :slot, CAST(:intent AS JSONB), 'prepared')
                ON CONFLICT (operation_id) DO NOTHING""", {
                    "oid": entry["operation_id"], "eid": row["execution_id"], "slot": index,
                    "intent": canonical(entry)})
        return row

    async def load(self, operation_id: str) -> dict:
        valid_uuid(operation_id)
        row = await self._query("""SELECT o.*, e.owner_id, e.session_id, e.calls
            FROM tool_operations o JOIN tool_executions e USING (execution_id)
            WHERE operation_id = :oid""", {"oid": operation_id})
        if row is None:
            raise OperationError("ACTION_IDENTITY_UNKNOWN")
        return row

    async def freeze(self, operation_id: str, request: dict) -> dict:
        safe_payload(request)
        await self._query("""UPDATE tool_operations SET request = CAST(:request AS JSONB)
            WHERE operation_id = :oid AND state = 'prepared' AND request IS NULL""",
            {"oid": operation_id, "request": canonical(request)})
        row = await self.load(operation_id)
        # A concurrent precondition read can differ. Always use the winning frozen request.
        if row["request"] is None:
            raise OperationError("ACTION_REQUEST_NOT_FROZEN")
        return row

    async def claim(self, operation_id: str) -> bool:
        from sqlalchemy import text
        try:
            async with asyncio.timeout(10):
                async with self.factory() as session:
                    from app.core import approval_deadline as deadline
                    from app.core import approval_lifecycle as lifecycle
                    from app.security.rbac import AgentRole, can_use_tool
                    context = _action_context.get()
                    if context is None:
                        raise OperationError("ACTION_DISPATCH_CONTEXT_REQUIRED")
                    approval = _committed_approval.get()
                    participants = [context.get("user_id", "")]
                    if approval is not None:
                        participants.append(approval.approver_id)
                    users = await deadline.lock_users(session, *participants)
                    user = users[context["user_id"]]
                    if user.role != context.get("role"):
                        raise OperationError("ACTION_AUTHORIZATION_DENIED")
                    if approval is not None:
                        current = await lifecycle.load_locked(session, approval.approval_id)
                        deadline.require_contract(current)
                        await deadline.require_live(session, current)
                        lease = (await session.execute(text("""SELECT
                            (CAST(:deadline AS TIMESTAMPTZ) IS NOT NULL AND
                             CAST(:deadline AS TIMESTAMPTZ) > clock_timestamp()) AS execution_live"""),
                            {"deadline": current.execution_deadline})).fetchone()
                        if lease is None or lease.execution_live is not True:
                            raise OperationError("APPROVAL_EXECUTION_EXPIRED")
                        if (current.status != "executing" or current.execution_claim != approval.execution_claim
                                or current.execution_id != approval.execution_id
                                or current.approver_id != approval.approver_id
                                or users[approval.approver_id].role not in current.approver_roles
                                or canonical(deadline.payload(current)) != canonical(deadline.payload(approval))):
                            raise OperationError("APPROVAL_CLAIM_CONFLICT")
                    await guard_action_owner(session, user.user_id)
                    record = await self.load(operation_id)
                    if (record["owner_id"] != user.user_id
                            or not can_use_tool(AgentRole(user.role), record["intent"]["tool"])):
                        raise OperationError("ACTION_AUTHORIZATION_DENIED")
                    if approval is not None and (str(record["execution_id"]) != str(approval.execution_id)
                            or canonical(record["calls"]) != canonical(deadline.payload(approval)["tool_calls"])
                            or canonical(record["intent"]) not in [canonical(c) for c in record["calls"]]
                            or record["intent"].get("operation_id") != operation_id):
                        raise OperationError("APPROVAL_PLAN_CONFLICT")
                    # Serialize Saga attachment and dispatch using the execution row.
                    await session.execute(text("""SELECT e.execution_id FROM tool_executions e
                        JOIN tool_operations o USING (execution_id) WHERE o.operation_id = :oid
                        FOR UPDATE OF e"""), {'oid': operation_id})
                    run = (await session.execute(text("""SELECT s.*,
                        (s.lease_until > clock_timestamp()) AS lease_live FROM saga_runs s
                        JOIN tool_operations o ON o.execution_id = s.saga_id
                        WHERE o.operation_id = :oid FOR UPDATE OF s"""),
                        {'oid': operation_id})).mappings().first()
                    if run is not None and (run['state'] != 'forward' or not run['lease_live']
                            or _saga_scope.get() != (str(run['saga_id']), str(run['owner_token']))):
                        raise OperationError('SAGA_DISPATCH_DENIED')
                    result = await session.execute(text("""UPDATE tool_operations SET state = 'dispatched'
                        WHERE operation_id = :oid AND state = 'prepared' AND request IS NOT NULL
                        RETURNING operation_id"""), {'oid': operation_id})
                    claimed = result.mappings().first() is not None
                    await session.commit()
                    return claimed
        except OperationError:
            raise
        except Exception:
            raise OperationError('ACTION_STORE_UNAVAILABLE') from None

    async def finish(self, operation_id: str, state: str, receipt: dict | None) -> None:
        if state not in {"committed", "rejected", "unknown"}:
            raise OperationError("ACTION_STATE_INVALID")
        safe_payload(receipt)
        row = await self._query("""UPDATE tool_operations
            SET state = CASE WHEN state = 'unknown' THEN 'unknown' ELSE :state END,
                receipt = CASE WHEN CAST(:receipt AS JSONB) = 'null'::jsonb THEN receipt
                               ELSE CAST(:receipt AS JSONB) END, updated_at = NOW()
            WHERE operation_id = :oid AND state IN ('dispatched', 'unknown')
            RETURNING operation_id""", {
                "oid": operation_id, "state": state, "receipt": canonical(receipt)})
        if row is None:
            current = await self.load(operation_id)
            if (current["state"] != "committed" or
                    (state == "committed" and current["receipt"] != receipt)):
                raise OperationError("ACTION_STATE_CONFLICT")


async def authorize_action(context: dict, tool_name: str) -> None:
    """Check the current user, not a role/header supplied by the model or caller."""
    from app.core.database import get_session_factory
    from app.security.rbac import AgentRole, can_use_tool, resolve_active_user
    try:
        async with get_session_factory()() as session:
            user = await resolve_active_user(context.get("user_id"), session, lock=True)
            await guard_action_owner(session, user.user_id)
            if (user.role != context.get("role") or
                    not can_use_tool(AgentRole(user.role), tool_name)):
                raise OperationError("ACTION_AUTHORIZATION_DENIED")
    except OperationError:
        raise
    except Exception:
        raise OperationError("ACTION_AUTHORIZATION_DENIED") from None
