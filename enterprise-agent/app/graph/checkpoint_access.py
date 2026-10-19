"""Bounded checkpoint reads and safe final-state validation."""

from __future__ import annotations

import asyncio
from typing import Any

READ_TIMEOUT_SECONDS = 5


class CheckpointUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("CHECKPOINT_UNAVAILABLE")


async def read_checkpoint(checkpointer: Any, config: dict) -> Any:
    try:
        return await asyncio.wait_for(checkpointer.aget_tuple(config), READ_TIMEOUT_SECONDS)
    except Exception:
        raise CheckpointUnavailable() from None


def completed_state(checkpoint_tuple: Any, user_input: Any) -> dict:
    """Reject absent, intermediate or foreign snapshots; never invent a final answer."""
    checkpoint = getattr(checkpoint_tuple, "checkpoint", None)
    state = checkpoint.get("channel_values") if isinstance(checkpoint, dict) else None
    if not isinstance(state, dict):
        raise CheckpointUnavailable()
    saved = state.get("user_input")
    if isinstance(saved, dict):
        if saved.get("type") == "constructor" and isinstance(saved.get("kwargs"), dict):
            saved = saved["kwargs"]
    else:
        saved = vars(saved) if hasattr(saved, "__dict__") else {}
    if (state.get("request_id") != user_input.request_id
            or state.get("answer_request_id") not in (None, user_input.request_id)
            or not isinstance(state.get("final_answer"), str) or not state["final_answer"]
            or any(saved.get(key) != getattr(user_input, key) for key in
                   ("request_id", "user_id", "conversation_id", "role", "department"))):
        raise CheckpointUnavailable()
    return state
