"""Durable action identities and one-way dispatch claims; no implicit DDL or replay."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
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
    return _approval_scope.get() == (
        context.get("user_id"), context.get("approval_id"), fingerprint(calls))


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
        row = await self._query("""UPDATE tool_operations SET state = 'dispatched'
            WHERE operation_id = :oid AND state = 'prepared' AND request IS NOT NULL
            RETURNING operation_id""", {"oid": operation_id})
        return row is not None

    async def finish(self, operation_id: str, state: str, receipt: dict | None) -> None:
        if state not in {"committed", "rejected", "unknown"}:
            raise OperationError("ACTION_STATE_INVALID")
        safe_payload(receipt)
        row = await self._query("""UPDATE tool_operations
            SET state = :state, receipt = CAST(:receipt AS JSONB), updated_at = NOW()
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
            user = await resolve_active_user(context.get("user_id"), session)
            if (user.role != context.get("role") or
                    not can_use_tool(AgentRole(user.role), tool_name)):
                raise OperationError("ACTION_AUTHORIZATION_DENIED")
    except OperationError:
        raise
    except Exception:
        raise OperationError("ACTION_AUTHORIZATION_DENIED") from None
