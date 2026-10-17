"""Bounded JSON transport. Reads can retry; mutations are always single-attempt."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional
import uuid

import httpx

from app.security.redaction import redact_value
from app.config import get_settings


def _object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _invalid_number(value: str) -> None:
    raise ValueError("unsupported number")


async def call_external_api(
    method: str, url: str, *, api_token: Optional[str] = None,
    json_body: Optional[dict] = None, extra_headers: Optional[dict[str, str]] = None,
    timeout_seconds: Optional[float] = None, max_retries: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> tuple[bool, Any, Optional[str]]:
    """Return strict JSON plus bounded status metadata, never exception/body text."""
    settings = get_settings()
    timeout = min(float(timeout_seconds or settings.external_timeout_seconds), 5.0)
    if timeout <= 0:
        return False, None, "EXTERNAL_TIMEOUT_INVALID"
    method = method.upper()
    read = method in {"GET", "HEAD"}
    retries = min(2, max(0, max_retries if max_retries is not None
                         else settings.external_max_retries)) if read else 0
    headers = {"Accept": "application/json", **(extra_headers or {})}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    last_error = "EXTERNAL_UNAVAILABLE"
    for attempt in range(1, retries + 2):
        if meta is not None:
            meta.clear()
            meta.update(attempts=attempt)
        headers["X-Request-Id"] = str(uuid.uuid4())
        retryable = False
        try:
            # httpx phase timeouts alone do not bound a drip response or DNS/connect lifecycle.
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                    async with client.stream(method, url, headers=headers, json=json_body) as response:
                        status = response.status_code
                        if meta is not None:
                            meta.update(status=status, profile=response.headers.get(
                                "X-Reference-Profile", ""))
                        if status == 429 or (status >= 500 and status != 501):
                            retryable = read
                        if not 200 <= status < 300:
                            last_error = f"EXTERNAL_HTTP_{status}"
                        else:
                            body = bytearray()
                            async for chunk in response.aiter_bytes():
                                body.extend(chunk)
                                if len(body) > 65536:
                                    raise ValueError("oversize")
                            data = json.loads(body.decode("utf-8"), object_pairs_hook=_object,
                                              parse_float=_invalid_number,
                                              parse_constant=_invalid_number)
                            if not isinstance(data, dict):
                                raise ValueError("object required")
                            return True, redact_value(data, secrets=(api_token or "",)), None
        except (httpx.HTTPError, TimeoutError):
            last_error = "EXTERNAL_TRANSPORT_UNCERTAIN"
            retryable = read
        except (ValueError, UnicodeError, RecursionError):
            last_error = "EXTERNAL_PROTOCOL_INVALID"
        if not retryable or attempt > retries:
            return False, None, last_error
        await asyncio.sleep(2 ** (attempt - 1))
    return False, None, last_error
