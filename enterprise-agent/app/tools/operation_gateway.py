"""Persisted forward action gateway; recovery writes and Saga ownership belong to C13/C14."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from app.core.tool_operations import (
    OperationError, OperationStore, approval_authorized, authorize_action, valid_uuid,
)
from app.tools import reference


async def prepare_calls(plans: list[Any], context: dict, *, partition: str = "direct") -> None:
    from app.config import get_settings
    from app.tools.base import get_tool
    if not any(get_tool(plan.tool).category.value == "action" for plan in plans
               if get_tool(plan.tool)):
        return
    ids = [getattr(plan, "operation_id", None) for plan in plans]
    if any(ids):
        if not all(ids):
            raise OperationError("ACTION_IDENTITY_INCOMPLETE")
        for value in ids:
            valid_uuid(value)
        return  # Gateway loads and verifies each retained ID before use.
    for key in ("user_id", "session_id", "request_id", "execution_slot"):
        if not isinstance(context.get(key), str) or not context[key]:
            raise OperationError("ACTION_SCOPE_REQUIRED")
    calls = []
    for plan in plans:
        tool = get_tool(plan.tool)
        if tool is None:
            raise OperationError("ACTION_TOOL_UNKNOWN")
        params = tool._validate_params(plan.params)
        target = reference.target(tool, get_settings()) if tool.category.value == "action" else {
            "provider": tool._effective_provider()}
        calls.append({"tool": plan.tool, "params": params, "target": target})
    scope = {key: context[key] for key in ("user_id", "session_id", "request_id", "execution_slot")}
    scope["partition"] = partition
    record = await OperationStore().prepare(scope, calls)
    context["execution_calls"] = record["calls"]
    for plan, entry in zip(plans, record["calls"], strict=True):
        plan.operation_id = entry["operation_id"]
        plan.params = entry["params"]


def _result(row: dict, *, data: dict | None = None, error: str | None = None) -> Any:
    from app.tools.base import ToolResult
    name = row["intent"]["tool"]
    evidence = {"operation_id": str(row["operation_id"]), "execution_id": str(row["execution_id"]),
                "outcome": "committed" if data else "unknown"}
    if data is None:
        return ToolResult(False, name, {}, error=error or "ACTION_OUTCOME_UNKNOWN", side_effects=evidence)
    evidence["operation"] = data["operation"]
    output = {key: value for key, value in data.items() if key != "operation"}
    # Until C13, do not let legacy inverse methods overwrite provider state.
    compensation = {"provider": "http", "operation_id": str(row["operation_id"]),
                    "requires_durable_compensation": True}
    return ToolResult(True, name, output, side_effects=evidence, compensation_data=compensation)


async def _reconcile(store: OperationStore, row: dict) -> Any:
    oid = str(row["operation_id"])
    try:
        async with asyncio.timeout(30):
            while True:
                ok, data, error, meta = await reference.request(
                    row["intent"]["target"], "GET", "/operations/" + oid)
                if ok and meta.get("status") == 200:
                    candidate = data.get("result")
                    if candidate is not None:
                        verified = reference.receipt(candidate, row)
                        if data.get("operation") != verified["operation"]:
                            raise OperationError("REFERENCE_RECEIPT_INVALID")
                        await store.finish(oid, "committed", verified)
                        return _result(row, data=verified)
                    operation = data.get("operation", {})
                    if (operation.get("operation_id") != oid
                            or operation.get("run_id") != row["intent"]["target"]["run_id"]
                            or operation.get("request_hash") != reference.fingerprint(row["request"])):
                        break
                    if operation.get("state") != "pending":
                        break
                elif meta.get("status") in {401, 403, 404, 409, 422, 428, 501}:
                    break
                elif error in {"REFERENCE_PROFILE_INVALID", "EXTERNAL_PROTOCOL_INVALID"}:
                    break
                await asyncio.sleep(1)
    except (TimeoutError, TypeError, AttributeError, KeyError):
        pass
    except OperationError as exc:
        if str(exc) == "ACTION_STORE_UNAVAILABLE":
            raise
    await store.finish(oid, "unknown", None)
    return _result(row)


async def invoke_action(tool: Any, params: dict, context: dict) -> Any:
    """Authorization, frozen intent, atomic dispatch, receipt commit, in that order."""
    from app.config import get_settings
    from app.tools.base import ToolResult
    await authorize_action(context, tool.name)
    oid = valid_uuid(context.get("operation_id"))
    store = OperationStore()
    row = await store.load(oid)
    # PostgreSQL UUID columns may be driver UUID instances; wire identities are canonical strings.
    row["operation_id"] = str(row["operation_id"])
    row["execution_id"] = str(row["execution_id"])
    intent = row["intent"]
    if (row["owner_id"] != context.get("user_id") or row["session_id"] != context.get("session_id")
            or intent["tool"] != tool.name or intent["params"] != params
            or intent["target"] != reference.target(tool, get_settings())):
        raise OperationError("ACTION_INTENT_CONFLICT")
    if tool.requires_approval and not approval_authorized(context, row["calls"]):
        raise OperationError("ACTION_APPROVAL_REQUIRED")
    if row["state"] == "committed":
        if intent["target"]["provider"] == "mock":
            return ToolResult(**row["receipt"])
        return _result(row, data=reference.receipt(row["receipt"], row))
    if row["state"] == "rejected":
        return ToolResult(False, tool.name, {}, error="ACTION_REJECTED")
    if row["request"] is None:
        frozen = reference.wire(tool.name, params, context["user_id"]) if (
            intent["target"]["provider"] == "http") else {"mock_params": params}
        if tool.name == "update_ticket" and intent["target"]["provider"] == "http":
            ok, data, error, meta = await reference.request(intent["target"], "GET", frozen["path"], retries=2)
            if (not ok or meta.get("status") != 200 or not isinstance(data.get("ticket"), dict)
                    or data["ticket"].get("ticket_id") != params["ticket_id"]):
                raise OperationError("ACTION_PRECONDITION_UNAVAILABLE")
            frozen["if_match"] = '"' + str(reference.version(data["ticket"].get("version"))) + '"'
        row = await store.freeze(oid, frozen)
        row["operation_id"], row["execution_id"] = oid, str(row["execution_id"])
    if not await store.claim(oid):
        current = await store.load(oid)
        current["operation_id"], current["execution_id"] = oid, str(current["execution_id"])
        if current["state"] == "committed":
            if intent["target"]["provider"] == "mock":
                return ToolResult(**current["receipt"])
            return _result(current, data=reference.receipt(current["receipt"], current))
        if intent["target"]["provider"] == "mock":
            return _result(current, error="MOCK_OUTCOME_UNKNOWN")
        return await _reconcile(store, current)
    if intent["target"]["provider"] == "mock":
        result = await tool._execute(params, context)
        # Mock is an explicit developer demonstration, not restart-safe external evidence.
        await store.finish(oid, "committed" if result.success else "rejected", asdict(result))
        return result
    frozen = row["request"]
    ok, data, error, meta = await reference.request(
        intent["target"], frozen["method"], frozen["path"], body=frozen["body"],
        operation_id=oid, if_match=frozen["if_match"])
    expected_status = 200 if tool.name == "update_ticket" else 201
    if ok and meta.get("status") == expected_status:
        try:
            verified = reference.receipt(data, row)
        except OperationError:
            verified = None
        if verified is not None:
            await store.finish(oid, "committed", verified)
            return _result(row, data=verified)
    if meta.get("status") in {401, 403, 409, 422, 428, 501}:
        # Retain an uncertain claim; HTTP rejection does not prove no earlier in-flight effect.
        await store.finish(oid, "unknown", None)
        return _result(row, error=error or "ACTION_REJECTED")
    return await _reconcile(store, row)
