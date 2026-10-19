"""Business-reference-v1 wire mapping and strict forward/inverse receipt checks."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from urllib.parse import urlsplit

from app.core.tool_operations import OperationError, fingerprint, safe_payload, valid_uuid
from app.tools.http_adapter import call_external_api

PROFILE = "business-reference-v1"
SERVICES = {"query_customer": "crm", "query_order": "crm", "create_crm_task": "crm", "create_ticket": "ticket", "update_ticket": "ticket",
            "send_email_internal": "mail", "send_email_external": "mail"}
RECIPIENTS = {"employee@reference.invalid", "manager@reference.invalid", "customer@reference.invalid"}


def resource_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise OperationError("REFERENCE_RESOURCE_INVALID")
    return value


def version(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise OperationError("REFERENCE_VERSION_INVALID")
    return value


def target(tool: Any, settings: Any) -> dict:
    provider = tool._effective_provider()
    if provider == "mock":
        return {"provider": "mock"}
    service = SERVICES.get(tool.name)
    if provider != "http" or service is None:
        raise OperationError("ACTION_PROVIDER_UNSUPPORTED")
    if settings.tool_reference_profile != PROFILE:
        raise OperationError("ACTION_PROVIDER_CONTRACT_REQUIRED")
    run_id = valid_uuid(settings.tool_reference_run_id)
    principal = resource_id(settings.tool_reference_principal)
    endpoint = getattr(settings, f"{service}_api_base").rstrip("/")
    parsed = urlsplit(endpoint)
    if (parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/api/v1" or not parsed.hostname
            or parsed.scheme not in {"http", "https"}):
        raise OperationError("REFERENCE_ENDPOINT_INVALID")
    if parsed.scheme == "http" and parsed.hostname != f"reference-{service}":
        raise OperationError("REFERENCE_HTTPS_REQUIRED")
    if not getattr(settings, f"{service}_api_token"):
        raise OperationError("REFERENCE_SERVICE_CREDENTIAL_REQUIRED")
    return {"provider": provider, "profile": PROFILE, "service": service,
            "endpoint": endpoint, "run_id": run_id, "principal": principal}


def wire(tool_name: str, params: dict, user_id: str) -> dict:
    """Resolve defaults before hashing. Never mutate a caller's parameter dictionary."""
    body = dict(params)
    path = "/send"
    method = "POST"
    if tool_name == "create_crm_task":
        path = "/crm_tasks"
        body = {"customer_id": resource_id(params["customer_id"]), "title": params["title"],
                "description": params.get("description", ""), "priority": params.get("priority", 1),
                "assignee": resource_id(params.get("assignee") or user_id),
                "due_date": params.get("due_date")}
    elif tool_name == "create_ticket":
        path = "/tickets"
        body = {"title": params["title"], "description": params.get("description", ""),
                "customer_id": params.get("customer_id"), "priority": params.get("priority", "normal"),
                "category": params.get("category", "general")}
    elif tool_name == "update_ticket":
        method, path = "PATCH", "/tickets/" + resource_id(params["ticket_id"])
        body = {key: params[key] for key in ("status", "priority", "assignee", "comment")
                if key in params}
        if not body:
            raise OperationError("REFERENCE_EMPTY_UPDATE")
    elif tool_name in {"send_email_internal", "send_email_external"}:
        body = {"scope": "internal" if tool_name.endswith("internal") else "external",
                "to": params["to"], "subject": params["subject"], "body": params["body"],
                "cc": params.get("cc") or [], "attachments": params.get("attachments") or []}
        recipients = body["to"] + body["cc"]
        allowed = RECIPIENTS if body["scope"] == "external" else RECIPIENTS - {"customer@reference.invalid"}
        if (not set(recipients) <= allowed or len(body["cc"]) > 50
                or len(body["to"]) != len(set(body["to"]))
                or any(item != "fixture-brief-v1" for item in body["attachments"])):
            raise OperationError("REFERENCE_MAIL_TARGET_REJECTED")
    else:
        raise OperationError("REFERENCE_TOOL_UNSUPPORTED")
    # Validate normalized wire values as well as the public Pydantic envelope.
    if "title" in body and (not isinstance(body["title"], str) or not 1 <= len(body["title"]) <= 200):
        raise OperationError("REFERENCE_PAYLOAD_INVALID")
    if tool_name.startswith("send_email") and not body["subject"]:
        raise OperationError("REFERENCE_PAYLOAD_INVALID")
    if tool_name == "create_crm_task":
        if type(body["priority"]) is not int or not 0 <= body["priority"] <= 5:
            raise OperationError("REFERENCE_PAYLOAD_INVALID")
        if body["due_date"] is not None:
            from datetime import date
            if date.fromisoformat(body["due_date"]).isoformat() != body["due_date"]:
                raise OperationError("REFERENCE_PAYLOAD_INVALID")
    if tool_name in {"create_ticket", "update_ticket"}:
        if "priority" in body and body["priority"] not in {"low", "normal", "high", "urgent"}:
            raise OperationError("REFERENCE_PAYLOAD_INVALID")
        if "status" in body and body["status"] not in {"open", "in_progress", "resolved", "closed"}:
            raise OperationError("REFERENCE_PAYLOAD_INVALID")
        if body.get("customer_id") is not None:
            resource_id(body["customer_id"])
        if body.get("assignee") is not None:
            resource_id(body["assignee"])
        if "comment" in body and (not isinstance(body["comment"], str) or not body["comment"]):
            raise OperationError("REFERENCE_PAYLOAD_INVALID")
    safe_payload(body)
    return {"profile": PROFILE, "method": method, "path": path, "body": body,
            "if_match": None, "compensates_operation_id": None}


async def request(target_config: dict, method: str, path: str, *, body: dict | None = None,
                  operation_id: str | None = None, if_match: str | None = None,
                  compensates_operation_id: str | None = None, retries: int = 0) -> tuple[bool, Any, str | None, dict]:
    from app.config import get_settings
    settings = get_settings()
    token = getattr(settings, f"{target_config['service']}_api_token")
    headers = {"X-Reference-Run-Id": target_config["run_id"], "Accept": "application/json"}
    if method != "GET":
        headers["Content-Type"] = "application/json"
    if operation_id:
        headers["Idempotency-Key"] = "ba-ref-v1:" + valid_uuid(operation_id)
    if compensates_operation_id:
        headers["X-Compensates-Operation"] = valid_uuid(compensates_operation_id)
    if if_match:
        headers["If-Match"] = if_match
    meta: dict = {}
    ok, data, error = await call_external_api(
        method, target_config["endpoint"] + path, api_token=token, json_body=body,
        extra_headers=headers, timeout_seconds=5, max_retries=retries, meta=meta)
    if meta.get("profile") != PROFILE:
        return False, None, "REFERENCE_PROFILE_INVALID", meta
    return ok, data, error, meta


def _timestamp(value: Any) -> None:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise OperationError("REFERENCE_RECEIPT_INVALID") from None


def receipt(data: Any, row: dict) -> dict:
    """Require a complete matching committed receipt, including business identity."""
    try:
        safe_payload(data)
        operation = data["operation"]
        intent, frozen = row["intent"], row["request"]
        expected = {"operation_id": row["operation_id"], "run_id": intent["target"]["run_id"],
                    "service": intent["target"]["service"], "request_hash": fingerprint(frozen),
                    "state": "committed", "compensates_operation_id": None}
        if any(operation[key] != value for key, value in expected.items()):
            raise ValueError
        rid = resource_id(operation["resource_id"])
        after = version(operation["after_version"])
        _timestamp(operation["created_at"])
        _timestamp(operation["completed_at"])
        name = intent["tool"]
        common = set(expected) | {"resource_id", "after_version", "created_at", "completed_at", "effect"}
        if set(operation) != common | ({"before"} if name == "update_ticket" else set()):
            raise ValueError
        if name.startswith("send_email"):
            if set(data) != {"message_id", "receipt_state", "recipients", "operation"}:
                raise ValueError
            if (data["message_id"] != rid or data["receipt_state"] != "captured"
                    or operation["effect"] != "captured" or after != 1
                    or type(data["recipients"]) is not int
                    or data["recipients"] != len(set(frozen["body"]["to"] + frozen["body"]["cc"]))):
                raise ValueError
        else:
            kind, key = ("task", "task_id") if name == "create_crm_task" else ("ticket", "ticket_id")
            if set(data) != {kind, "operation"}:
                raise ValueError
            obj = data[kind]
            allowed = ({"task_id", "customer_id", "title", "description", "priority", "assignee",
                        "due_date", "status", "version", "created_by", "created_at"} if kind == "task" else
                       {"ticket_id", "title", "description", "customer_id", "priority", "category",
                        "status", "assignee", "comments", "version", "created_by", "created_at"})
            if set(obj) - allowed:
                raise ValueError
            for field, value in frozen["body"].items():
                if field != "comment" and obj[field] != value:
                    raise ValueError
            if "comment" in frozen["body"]:
                comments = obj["comments"]
                if not isinstance(comments, list) or not any(
                    isinstance(item, dict) and item.get("text") == frozen["body"]["comment"]
                    and resource_id(item.get("comment_id")) for item in comments):
                    raise ValueError
            if obj[key] != rid or version(obj["version"]) != after:
                raise ValueError
            if name == "update_ticket":
                before = operation["before"]
                if (rid != intent["params"]["ticket_id"] or operation["effect"] != "updated"
                        or after != int(frozen["if_match"].strip('"')) + 1
                        or before["ticket_id"] != rid or version(before["version"]) != after - 1):
                    raise ValueError
            elif after != 1 or obj["status"] != "open" or operation["effect"] != "created":
                raise ValueError
        return data
    except (KeyError, ValueError, TypeError, AttributeError, OperationError):
        raise OperationError("REFERENCE_RECEIPT_INVALID") from None


async def query(tool: Any, params: dict, context: dict) -> Any:
    from app.config import get_settings
    from app.tools.base import ToolResult
    try:
        config = target(tool, get_settings())
        if tool.name == "query_customer":
            rid = resource_id(params["customer_id"])
            fields = params.get("fields")
            allowed = {"name", "contact", "phone", "email", "industry", "level"}
            if fields is not None and (not isinstance(fields, list) or not set(fields) <= allowed):
                raise OperationError("REFERENCE_PROJECTION_INVALID")
            path = "/customers/" + rid + ("?fields=" + ",".join(fields) if fields else "")
            envelope, key = "customer", "customer_id"
        else:
            rid = resource_id(params["order_id"])
            path = "/orders/" + rid + "?include_items=" + ("1" if params.get("include_items") else "0")
            envelope, key = "order", "order_id"
        ok, data, error, meta = await request(config, "GET", path, retries=2)
        if not ok or meta.get("status") != 200:
            raise OperationError(error or "REFERENCE_READ_INVALID")
        obj = data[envelope]
        if obj[key] != rid:
            raise ValueError
        version(obj["version"])
        if envelope == "customer":
            if not set(obj) <= allowed | {key, "version"}:
                raise ValueError
            if fields and not set(obj) <= set(fields) | {key, "version"}:
                raise ValueError
            if any(not isinstance(value, str) for k, value in obj.items() if k != "version"):
                raise ValueError
        else:
            if (type(obj["amount_minor"]) is not int or obj["amount_minor"] < 0
                    or not re.fullmatch(r"[A-Z]{3}", obj["currency"])
                    or obj["status"] not in {"pending", "completed", "cancelled", "refunded"}):
                raise ValueError
            resource_id(obj["customer_id"])
            if not params.get("include_items") and "items" in obj:
                raise ValueError
            if params.get("include_items"):
                for item in obj["items"]:
                    if (type(item["qty"]) is not int or item["qty"] < 1
                            or type(item["price_minor"]) is not int or item["price_minor"] < 0
                            or not isinstance(item["sku"], str) or not isinstance(item["name"], str)):
                        raise ValueError
            obj = {**obj, "amount": obj["amount_minor"] / 100}
        return ToolResult(True, tool.name, {envelope: obj})
    except (OperationError, KeyError, TypeError, ValueError):
        return ToolResult(False, tool.name, {}, error="REFERENCE_READ_INVALID")


def rejected(data: Any, row: dict, *, inverse: bool = False) -> bool:
    """Only a complete retained provider rejection proves a known no-effect outcome."""
    try:
        safe_payload(data)
        op = data['operation']
        if op.get('state') != 'rejected':
            return False
        expected = {'operation_id': str(row['operation_id']),
                    'run_id': row['intent']['target']['run_id'],
                    'service': row['intent']['target']['service'],
                    'request_hash': fingerprint(row['request']), 'state': 'rejected',
                    'compensates_operation_id': row['request']['compensates_operation_id'] if inverse else None,
                    'resource_id': None, 'after_version': None, 'effect': 'none'}
        if (set(data) != {'operation', 'result'} or data['result'] is not None
                or set(op) != set(expected) | {'created_at', 'completed_at', 'error_code'}
                or any(op[k] != v for k, v in expected.items())
                or op['error_code'] not in {'VERSION_CONFLICT', 'VALIDATION_REJECTED',
                                           'AUTHORIZATION_DENIED', 'UNSUPPORTED'}):
            raise ValueError
        _timestamp(op['created_at'])
        _timestamp(op['completed_at'])
        return True
    except (KeyError, TypeError, ValueError, AttributeError, OperationError):
        raise OperationError('REFERENCE_RECEIPT_INVALID') from None


def inverse_wire(row: dict) -> dict:
    forward = receipt(row['receipt'], row)
    op = forward['operation']
    rid = resource_id(op['resource_id'])
    name = row['intent']['tool']
    if name == 'create_crm_task':
        method, path, body = 'DELETE', '/crm_tasks/' + rid, None
    elif name == 'create_ticket':
        method, path, body = 'PATCH', '/tickets/' + rid, {
            'status': 'closed', 'closure_reason': 'saga_compensation'}
    elif name == 'update_ticket':
        before = op['before']
        # Require restore evidence, not just a version and ID. Comments are append-only.
        for key in ('status', 'priority', 'assignee', 'comments'):
            if key not in before:
                raise OperationError('REFERENCE_BEFORE_IMAGE_REQUIRED')
        if (before['status'] not in {'open', 'in_progress', 'resolved', 'closed'}
                or before['priority'] not in {'low', 'normal', 'high', 'urgent'}
                or not isinstance(before['comments'], list)):
            raise OperationError('REFERENCE_BEFORE_IMAGE_REQUIRED')
        if before['assignee'] is not None:
            resource_id(before['assignee'])
        method, path, body = 'PATCH', '/tickets/' + rid, {
            'restore_operation_id': str(row['operation_id'])}
    elif name in {'send_email_internal', 'send_email_external'}:
        method, body = 'POST', {}
        suffix = '/recall' if name.endswith('internal') else '/recall_requests'
        path = '/messages/' + rid + suffix
    else:
        raise OperationError('REFERENCE_TOOL_UNSUPPORTED')
    return {'profile': PROFILE, 'method': method, 'path': path, 'body': body,
            'if_match': '"' + str(version(op['after_version'])) + '"',
            'compensates_operation_id': str(row['operation_id'])}


def inverse_receipt(data: Any, inverse: dict, forward: dict) -> dict:
    try:
        safe_payload(data)
        op = data['operation']
        original = receipt(forward['receipt'], forward)['operation']
        name = forward['intent']['tool']
        effect = {'create_crm_task': 'deleted', 'create_ticket': 'closed',
                  'update_ticket': 'restored', 'send_email_internal': 'recalled',
                  'send_email_external': 'recall_requested'}[name]
        expected = {'operation_id': str(inverse['operation_id']),
                    'run_id': forward['intent']['target']['run_id'],
                    'service': forward['intent']['target']['service'],
                    'request_hash': fingerprint(inverse['request']), 'state': 'committed',
                    'compensates_operation_id': str(forward['operation_id']),
                    'resource_id': original['resource_id'],
                    'after_version': original['after_version'] + 1, 'effect': effect}
        if (set(op) != set(expected) | {'created_at', 'completed_at'}
                or any(op[k] != v for k, v in expected.items())):
            raise ValueError
        version(op['after_version'])
        _timestamp(op['created_at'])
        _timestamp(op['completed_at'])
        if name.startswith('send_email'):
            if (set(data) != {'message_id', 'receipt_state', 'operation'}
                    or data['message_id'] != op['resource_id'] or data['receipt_state'] != effect):
                raise ValueError
        else:
            kind, key = ('task', 'task_id') if name == 'create_crm_task' else ('ticket', 'ticket_id')
            if set(data) != {kind, 'operation'}:
                raise ValueError
            obj = data[kind]
            if obj[key] != op['resource_id'] or version(obj['version']) != op['after_version']:
                raise ValueError
            if name == 'update_ticket':
                before = original['before']
                for field in ('status', 'priority', 'assignee'):
                    if obj[field] != before[field]:
                        raise ValueError
                comments = obj['comments']
                forward_comments = forward['receipt']['ticket'].get('comments', [])
                if (not isinstance(comments, list) or any(c not in comments for c in before['comments'])
                        or not any(isinstance(c, dict)
                                   and c.get('compensates_operation_id') == str(forward['operation_id'])
                                   for c in comments)):
                    raise ValueError
                before_ids = {c['comment_id'] for c in before['comments']}
                for original_comment in forward_comments:
                    matches = [c for c in comments if c.get('comment_id') == original_comment['comment_id']]
                    if (len(matches) != 1 or matches[0].get('text') != original_comment.get('text')
                            or (original_comment['comment_id'] not in before_ids
                                and matches[0].get('superseded_by') != str(inverse['operation_id']))):
                        raise ValueError
            elif obj['status'] != effect:
                raise ValueError
            if name == 'create_ticket' and obj['closure_reason'] != 'saga_compensation':
                raise ValueError
        return data
    except (KeyError, ValueError, TypeError, AttributeError, OperationError):
        raise OperationError('REFERENCE_RECEIPT_INVALID') from None
