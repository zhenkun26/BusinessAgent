"""Shared ephemeral coordination; no credentials or process-local fallback."""

from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import json
import re
import secrets
from typing import AsyncIterator, Any

from loguru import logger

SSO_STATE_TTL_SECONDS = 600
KEY_PREFIX = "businessagent:runtime:v1:"


class RuntimeStateUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("RUNTIME_STATE_UNAVAILABLE")


def state_key(kind: str, identifier: str) -> str:
    """Hash identifiers and keep keys for one session in the same Redis hash slot."""
    digest = hashlib.sha256(identifier.encode()).hexdigest()
    return f"{KEY_PREFIX}{{{digest}}}:{kind}"


@asynccontextmanager
async def runtime_client() -> AsyncIterator[Any]:
    from redis.asyncio import Redis
    from redis.exceptions import RedisError
    from redis.backoff import NoBackoff
    from redis.retry import Retry
    from app.config import get_settings

    client = None
    try:
        client = Redis.from_url(
            get_settings().redis_url, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2, retry_on_timeout=False,
            retry=Retry(NoBackoff(), 0),
        )
        yield client
    except (RedisError, ValueError):
        raise RuntimeStateUnavailable() from None
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                logger.warning("RUNTIME_STATE_CLOSE_FAILED")


async def register_sso_state(*, verifier: str | None = None) -> tuple[str, str]:
    if verifier is not None and not re.fullmatch(r"[A-Za-z0-9_~.-]{43,128}", verifier):
        raise RuntimeStateUnavailable()
    async with runtime_client() as client:
        for _ in range(3):
            state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            value = json.dumps({"nonce": nonce, "verifier": verifier}) if verifier else nonce
            if await client.set(state_key("sso", state), value,
                                nx=True, ex=SSO_STATE_TTL_SECONDS):
                return state, nonce
    raise RuntimeStateUnavailable()


async def consume_sso_state(
    state: str, *, with_verifier: bool = False,
) -> str | dict[str, str] | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", state):
        return None
    async with runtime_client() as client:
        nonce = await client.getdel(state_key("sso", state))
    if not isinstance(nonce, str):
        return None
    if nonce.startswith('{'):
        try:
            binding = json.loads(nonce)
            if (not isinstance(binding, dict) or set(binding) != {'nonce', 'verifier'}
                    or not re.fullmatch(r'[A-Za-z0-9_-]{43}', binding['nonce'])
                    or not re.fullmatch(r'[A-Za-z0-9_~.-]{43,128}', binding['verifier'])):
                return None
            return binding if with_verifier else binding['nonce']
        except (ValueError, TypeError, KeyError):
            return None
    if with_verifier or not re.fullmatch(r"[A-Za-z0-9_-]{43}", nonce):
        return None
    return nonce
