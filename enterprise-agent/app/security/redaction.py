"""Credential redaction for owned diagnostic and persistence boundaries.

This is a bounded credential policy, not arbitrary-text privacy classification.
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

REDACTED = "[REDACTED]"
_configured_secrets: tuple[str, ...] = ()
_JWT = re.compile(r"(?<![\w-])eyJ[\w-]+\.[\w-]+\.[\w-]+")
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s\"'<>;,]+")
_USERINFO = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@]+@")
_ASSIGNMENT = re.compile(
    r"(?i)([\"']?(?:[\w.-]*(?:password|passwd|secret|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|requester[_-]?token|jwt[_-]?token)|"
    r"token|authorization|cookie|credentials?)[\"']?\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;&}\]]+)"
)


def sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return (any(part in normalized for part in ("password", "passwd", "secret", "apikey"))
            or normalized.endswith(("token", "authorization", "cookie", "credentials", "credential")))


def redact_text(value: str, *, secrets: tuple[str, ...] = ()) -> str:
    """Mask configured values and recognizable credentials before truncating."""
    configured = [v for k, v in os.environ.items() if sensitive_key(k) and len(v) >= 8]
    known = configured + list(_configured_secrets) + [s for s in secrets if s]
    for secret in sorted(set(known), key=len, reverse=True):
        value = value.replace(secret, REDACTED).replace(quote(secret, safe=""), REDACTED)
    value = _BEARER.sub("Bearer " + REDACTED, value)
    value = _JWT.sub(REDACTED, value)
    value = _USERINFO.sub(r"\1" + REDACTED + "@", value)
    return _ASSIGNMENT.sub(lambda match: match[1] + REDACTED, value)


def register_configured_secrets(values: dict[str, Any]) -> None:
    """Include settings loaded from .env, without logging or persisting them."""
    global _configured_secrets
    _configured_secrets = tuple(value for key, value in values.items()
                                if sensitive_key(key) and isinstance(value, str) and value)


def redact_value(value: Any, *, secrets: tuple[str, ...] = (), _depth: int = 0) -> Any:
    """Produce a JSON-safe copy; never stringify opaque objects or exceptions."""
    if _depth > 20:
        return REDACTED
    if isinstance(value, dict):
        return {
            redact_text(str(key), secrets=secrets): REDACTED if sensitive_key(str(key)) else
            redact_value(item, secrets=secrets, _depth=_depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_value(item, secrets=secrets, _depth=_depth + 1) for item in value]
    if isinstance(value, str):
        return redact_text(value, secrets=secrets)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "[UNSUPPORTED]"


def redact_log_record(record: dict[str, Any]) -> None:
    """Do not let tracebacks/diagnostic locals reintroduce redacted credentials."""
    record["exception"] = None
    try:
        record["message"] = redact_text(record["message"])
        record["extra"] = redact_value(record.get("extra", {}))
    except Exception:
        record["message"] = "REDACTION_FAILED"
        record["extra"] = {}


def install_log_redaction() -> None:
    from loguru import logger

    logger.configure(patcher=redact_log_record)
