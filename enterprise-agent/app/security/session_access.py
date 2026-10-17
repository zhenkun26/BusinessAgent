"""Persisted session ownership checks shared by chat entry points."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.security.rbac import User


async def require_session_access(
    db: AsyncSession,
    session_id: str,
    user: User,
    *,
    allow_admin: bool = False,
    lock: bool = False,
) -> Mapping[str, Any]:
    """Return authorized metadata, without distinguishing missing and foreign rows."""
    if not isinstance(session_id, str) or not 1 <= len(session_id) <= 64:
        raise HTTPException(404, "SESSION_NOT_AVAILABLE")
    query = (
        "SELECT session_id, user_id, status FROM sessions "
        "WHERE session_id = :sid AND (user_id = :uid OR :admin_override)"
    )
    if lock:
        query += " FOR SHARE"
    try:
        row = (await db.execute(text(query), {
            "sid": session_id,
            "uid": user.user_id,
            "admin_override": allow_admin and user.role == "admin",
        })).mappings().first()
    except Exception:
        raise HTTPException(503, "SESSION_ACCESS_UNAVAILABLE") from None
    if row is None:
        raise HTTPException(404, "SESSION_NOT_AVAILABLE")
    return row


async def prepare_chat_session(
    db: AsyncSession, user: User, requested_id: str | None, message: str,
) -> str:
    """Create a fresh server ID or update only an existing row owned by the caller."""
    if requested_id is not None:
        await require_session_access(db, requested_id, user)
        session_id = requested_id
        query = (
            "UPDATE sessions SET status = 'running', original_query = :q, "
            "completed_at = NULL, error = NULL "
            "WHERE session_id = :sid AND user_id = :uid RETURNING session_id"
        )
    else:
        session_id = f"sess_{uuid.uuid4().hex}"
        query = (
            "INSERT INTO sessions (session_id, user_id, original_query, status, started_at) "
            "VALUES (:sid, :uid, :q, 'running', CURRENT_TIMESTAMP) "
            "ON CONFLICT (session_id) DO NOTHING RETURNING session_id"
        )
    try:
        row = (await db.execute(text(query), {
            "sid": session_id, "uid": user.user_id, "q": message[:500],
        })).mappings().first()
        if row is None:
            if requested_id is not None:
                raise HTTPException(404, "SESSION_NOT_AVAILABLE")
            raise HTTPException(409, "SESSION_CREATION_CONFLICT")
        await db.commit()
    except Exception as exc:
        # Roll back a failed request without exposing driver messages or retrying writes.
        try:
            await db.rollback()
        except Exception:
            pass
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(503, "SESSION_ACCESS_UNAVAILABLE") from None
    return session_id
