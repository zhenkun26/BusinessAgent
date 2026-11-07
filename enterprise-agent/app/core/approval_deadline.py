"""Server-owned UTC contracts and one-way dispatch; never promote legacy rows."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
import json
from typing import Any, Iterator

from fastapi import HTTPException
from sqlalchemy import text

from app.config import get_settings

VERSION = "utc-human-v2"
TERMINAL = frozenset({"executed", "rejected", "timeout"})
WAITING = frozenset({"pending", "approved_pending_reauth"})
ACTIVE = frozenset({"executing", "execution_unknown"})
HOLD = "APPROVAL_HUMAN_REVIEW_REQUIRED"
COLUMNS = ("approval_id, session_id, requester_id, operation_type, risk_level, summary, "
           "prefill_payload, approver_roles, status, approver_id, "
           "created_at, expires_at, approval_contract")
_dispatch: ContextVar[bool] = ContextVar("approval_dispatch", default=False)


def in_approval_dispatch() -> bool:
    return _dispatch.get()


@contextmanager
def dispatch_scope() -> Iterator[None]:
    """Set by the API only after a confirmed persisted claim; never by model fields."""
    token = _dispatch.set(True)
    try:
        yield
    finally:
        _dispatch.reset(token)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def payload(row: Any) -> dict[str, Any]:
    value = row.prefill_payload
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("invalid payload")
    return value


def targets_for(calls: list[dict[str, Any]]) -> list[dict[str, str]]:
    from app.tools.base import get_tool
    from app.agents.execution import _ensure_tools
    _ensure_tools()
    settings = get_settings()
    targets = []
    for call in calls:
        tool = get_tool(call["tool"])
        if tool is None:
            raise ValueError("unknown tool")
        provider = tool._effective_provider()
        attr = getattr(tool, "provider_config_attr", "") or ""
        base_attr = attr.replace("_tool_provider", "_api_base")
        endpoint = getattr(settings, base_attr, "") if provider == "http" else ""
        if provider not in {"mock", "http"} or provider == "http" and not endpoint:
            raise ValueError("unbound provider")
        targets.append({"tool": tool.name, "provider": provider, "endpoint": endpoint})
    return targets


def _body(row: Any, targets: Any) -> dict[str, Any]:
    created, expires = row.created_at, row.expires_at
    if (not isinstance(created, datetime) or not isinstance(expires, datetime)
            or created.tzinfo is not None or expires.tzinfo is not None
            or expires - created != timedelta(hours=24)):
        raise ValueError("invalid UTC timestamps")
    calls = payload(row).get("tool_calls")
    if (not isinstance(calls, list) or not calls or any(
            not isinstance(c, dict) or not isinstance(c.get("tool"), str)
            or not isinstance(c.get("params", {}), dict) for c in calls)):
        raise ValueError("invalid plan")
    roles = row.approver_roles
    if (not isinstance(roles, list) or not roles
            or any(r not in {"manager", "admin"} for r in roles)):
        raise ValueError("invalid approvers")
    identity = {name: getattr(row, name) for name in (
        "approval_id", "session_id", "requester_id", "operation_type", "risk_level")}
    if any(not isinstance(v, str) or not v for v in identity.values()):
        raise ValueError("invalid identity")
    return {**identity, "version": VERSION,
            "created_at": created.isoformat(timespec="microseconds"),
            "expires_at": expires.isoformat(timespec="microseconds"),
            "tool_calls": calls, "approver_roles": roles, "targets": targets}


def build_contract(row: Any) -> dict[str, Any]:
    """Writer-only INSERT metadata; never accept a client/model contract or upgrade old rows."""
    # Round-trip to detach the snapshot from mutable tool parameters.
    return json.loads(canonical(_body(row, targets_for(payload(row)["tool_calls"]))))


def contract(row: Any) -> dict[str, Any] | None:
    value = getattr(row, "approval_contract", None)
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else None


def verified(row: Any) -> bool:
    try:
        saved = contract(row)
        if saved is None:
            return False
        current = _body(row, targets_for(payload(row)["tool_calls"]))
        return canonical(saved) == canonical(current)
    except (HTTPException, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return False


def require_contract(row: Any) -> None:
    if not verified(row):
        raise HTTPException(409, HOLD)


def review_fields(row: Any) -> dict[str, Any]:
    held = row.status not in TERMINAL and (row.status not in WAITING or not verified(row))
    return {"human_review_required": held,
            "review_message": ("暂停自动执行及重提；请由有权限的人核对。AI仅提供建议。"
                               if held else "")}


async def load(db: Any, approval_id: str, *, locked: bool = False) -> Any:
    return (await db.execute(text(f"SELECT {COLUMNS} FROM approval_requests "
        "WHERE approval_id = :id" + (" FOR UPDATE" if locked else "")),
        {"id": approval_id})).fetchone()


async def lock_users(db: Any, *user_ids: str) -> dict[str, Any]:
    """Stable user lock order serializes creation/claim without schema additions."""
    users = {}
    for uid in sorted(set(user_ids)):
        row = (await db.execute(text("SELECT user_id, role, department, is_active FROM users "
            "WHERE user_id = :uid FOR UPDATE"), {"uid": uid})).fetchone()
        if row is None or row.is_active is not True:
            raise HTTPException(403, "APPROVAL_ACTIVE_USER_REQUIRED")
        from app.security.rbac import AgentRole
        try:
            AgentRole(row.role)
        except (ValueError, TypeError):
            raise HTTPException(403, "APPROVAL_ACTIVE_USER_REQUIRED") from None
        users[uid] = row
    return users


async def guard_owner(db: Any, user_id: str, *, exclude: str | None = None) -> None:
    rows = (await db.execute(text(f"SELECT {COLUMNS} FROM approval_requests "
        "WHERE requester_id = :uid AND (status IS NULL OR status NOT IN ('executed', 'rejected', 'timeout'))"),
        {"uid": user_id})).fetchall()
    for row in rows:
        if row.approval_id == exclude:
            continue
        if row.status not in WAITING or not verified(row):
            raise HTTPException(409, HOLD)


async def require_live(db: Any, row: Any) -> None:
    require_contract(row)
    now = (await db.execute(text(
        "SELECT clock_timestamp() AT TIME ZONE 'UTC' AS approval_now"))).fetchone()
    if now is None or row.expires_at <= now.approval_now:
        raise HTTPException(409, "APPROVAL_EXPIRED")


async def transition(db: Any, row: Any, actor: str, state: str, comment: str = "") -> None:
    require_contract(row)
    changed = (await db.execute(text("UPDATE approval_requests SET status = :state, "
        "approver_id = :actor, comment = :comment, decided_at = (clock_timestamp() AT TIME ZONE 'UTC') "
        "WHERE approval_id = :id AND status = :old "
        "AND expires_at > (clock_timestamp() AT TIME ZONE 'UTC') RETURNING approval_id"),
        {"state": state, "actor": actor, "comment": comment, "id": row.approval_id,
         "old": row.status})).fetchone()
    if changed is None:
        raise HTTPException(409, "APPROVAL_STATE_OR_DEADLINE_CHANGED")
    await db.execute(text("INSERT INTO audit_logs (event_type, session_id, user_id, success, "
        "payload) VALUES ('approval_transition', :sid, :uid, FALSE, CAST(:payload AS JSONB))"),
        {"sid": row.session_id, "uid": actor, "payload": canonical({
            "approval_id": row.approval_id, "new_status": state,
            "contract": VERSION, "ai_decision": False})})
    await db.commit()  # If acknowledgment is uncertain, caller MUST NOT dispatch.
