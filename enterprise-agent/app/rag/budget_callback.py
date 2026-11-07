"""Enforce graph model reservations before LangChain reaches provider I/O."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage

from app.core.execution_budget import MAX_OUTPUT_TOKENS, current_budget


class ExecutionBudgetCallback(BaseCallbackHandler):
    raise_error = True
    run_inline = True

    def on_chat_model_start(
        self, serialized: dict[str, Any], messages: list[list[BaseMessage]], **kwargs: Any,
    ) -> None:
        budget = current_budget()
        if budget is None:
            return
        budget.check()
        params = kwargs.get("invocation_params") or {}
        # Both router providers use explicit bounded output options. Reject call-time
        # overrides that would silently enlarge the reserved completion envelope.
        limits = [params[key] for key in ("max_tokens", "max_completion_tokens", "num_predict")
                  if params.get(key) is not None]
        if any(key in params and params[key] is None
               for key in ("max_tokens", "max_completion_tokens", "num_predict")):
            budget.reject()
        if "options" in params:
            options = params["options"]
            value = options.get("num_predict") if isinstance(options, dict) else None
            if (isinstance(value, bool) or not isinstance(value, int)
                    or not 0 < value <= MAX_OUTPUT_TOKENS):
                budget.reject()
        for value in limits:
            if (isinstance(value, bool) or not isinstance(value, int)
                    or not 0 < value <= MAX_OUTPUT_TOKENS):
                budget.reject()
        if params.get("n", 1) != 1:
            budget.reject()
        extra = params.get("extra_body") or {}
        if any(key in extra for key in ("max_tokens", "max_completion_tokens", "num_predict", "n")):
            budget.reject()
        for batch in messages:
            payload = json.dumps([m.model_dump(mode="json") for m in batch],
                                 ensure_ascii=False, separators=(",", ":"))
            budget.reserve_model(len(payload.encode("utf-8")))


_handler = ExecutionBudgetCallback()


def get_execution_budget_handler() -> ExecutionBudgetCallback:
    return _handler
