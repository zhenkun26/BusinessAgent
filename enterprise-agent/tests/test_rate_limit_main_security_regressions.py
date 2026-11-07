"""Synthetic quota-identity attacks; no database, network or real credentials."""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import Response

from app.middleware import rate_limit
from app.security import rbac

KEY = "synthetic-quota-test-signing-key-00000000000000"
WRONG_KEY = "synthetic-forged-token-signing-key-000000000000"


@pytest.fixture(autouse=True)
def isolated_quota(monkeypatch):
    settings = SimpleNamespace(
        rate_limit_per_minute=2, jwt_secret_key=KEY, jwt_algorithm="HS256", is_dev=False)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    monkeypatch.setattr(rbac, "get_settings", lambda: settings)
    memory = rate_limit.InMemoryRateLimiter()
    monkeypatch.setattr(rate_limit, "_get_limiter", AsyncMock(return_value=memory))



def token(subject="alice", *, key=KEY, algorithm="HS256", **claims):
    return jwt.encode({"sub": subject, "exp": int(time.time()) + 300, **claims},
                      key, algorithm=algorithm)


def request(bearer=None, *, path="/limited", ip="192.0.2.10", forwarded=None):
    headers = {"Authorization": f"Bearer {bearer}"} if bearer is not None else {}
    if forwarded:
        headers["X-Forwarded-For"] = forwarded
    return SimpleNamespace(url=SimpleNamespace(path=path), headers=headers,
                           client=SimpleNamespace(host=ip) if ip else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [WRONG_KEY, KEY])
async def test_login_rotation_stays_in_same_ip_bucket(key):
    endpoint = AsyncMock(side_effect=lambda _: Response(status_code=401))
    responses = [await rate_limit.rate_limit_middleware(
        request(token(f"synthetic-{index}", key=key), path="/api/v1/auth/login"), endpoint)
        for index in range(20)]
    assert [response.status_code for response in responses] == [401] * 10 + [429] * 10
    assert endpoint.await_count == 10


@pytest.mark.asyncio
async def test_login_does_not_parse_any_bearer(monkeypatch):
    def forbidden(_):
        raise AssertionError("login must not parse bearer identity")
    monkeypatch.setattr(rate_limit, "_extract_user_id", forbidden)
    response = await rate_limit.rate_limit_middleware(
        request("malformed", path="/api/v1/auth/login/"),
        AsyncMock(return_value=Response(status_code=401)))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_forged_subjects_on_other_routes_share_ip_bucket():
    endpoint = AsyncMock(side_effect=lambda _: Response(status_code=401))
    statuses = [(await rate_limit.rate_limit_middleware(
        request(token(f"forged-{i}", key=WRONG_KEY)), endpoint)).status_code
        for i in range(4)]
    assert statuses == [401, 401, 429, 429]


@pytest.mark.asyncio
async def test_verified_users_keep_independent_quotas_and_ip_changes_do_not_reset_user():
    endpoint = AsyncMock(side_effect=lambda _: Response(status_code=200))
    statuses = []
    for sub, ip in [("alice", "192.0.2.10"), ("alice", "192.0.2.11"),
                    ("alice", "192.0.2.12"), ("bob", "192.0.2.10")]:
        statuses.append((await rate_limit.rate_limit_middleware(
            request(token(sub), ip=ip), endpoint)).status_code)
    assert statuses == [200, 200, 429, 200]


@pytest.mark.parametrize("kind", ["forged", "expired", "missing_exp", "missing_sub",
    "future_nbf", "wrong_algorithm", "unsigned", "malformed", "large_token",
    "empty_subject", "blank_subject", "long_subject", "numeric_subject",
    "boolean_exp", "string_exp", "infinite_exp"])
def test_invalid_identity_never_selects_user_bucket(kind):
    values = {
        "forged": lambda: token(key=WRONG_KEY),
        "expired": lambda: token(exp=int(time.time()) - 60),
        "missing_exp": lambda: jwt.encode({"sub": "alice"}, KEY, algorithm="HS256"),
        "missing_sub": lambda: jwt.encode({"exp": int(time.time()) + 300}, KEY, algorithm="HS256"),
        "future_nbf": lambda: token(nbf=int(time.time()) + 300),
        "wrong_algorithm": lambda: token(algorithm="HS384"),
        "unsigned": lambda: token(key="", algorithm="none"),
        "malformed": lambda: "not.a.token",
        "large_token": lambda: token(padding="x" * 9000),
        "empty_subject": lambda: token(""),
        "blank_subject": lambda: token("   "),
        "long_subject": lambda: token("x" * 65),
        "numeric_subject": lambda: token(42),
        "boolean_exp": lambda: token(exp=True),
        "string_exp": lambda: token(exp=str(int(time.time()) + 300)),
        "infinite_exp": lambda: token(exp=float("inf")),
    }
    assert rate_limit._extract_user_id(request(values[kind]())) is None


@pytest.mark.asyncio
async def test_forwarded_headers_do_not_reset_connection_ip_quota():
    endpoint = AsyncMock(side_effect=lambda _: Response(status_code=401))
    statuses = [(await rate_limit.rate_limit_middleware(
        request(forwarded=f"198.51.100.{i}"), endpoint)).status_code for i in range(4)]
    assert statuses == [401, 401, 429, 429]


def test_valid_signed_token_is_a_positive_control():
    assert rate_limit._extract_user_id(request(token())) == "alice"


@pytest.mark.parametrize("scheme", ["bearer", "bEaReR"])
def test_bearer_scheme_matches_authentication_case_handling(scheme):
    candidate = request()
    candidate.headers["Authorization"] = f"{scheme} {token()}"
    assert rate_limit._extract_user_id(candidate) == "alice"


@pytest.mark.asyncio
async def test_missing_connection_address_uses_shared_unknown_bucket():
    endpoint = AsyncMock(side_effect=lambda _: Response(status_code=401))
    statuses = [(await rate_limit.rate_limit_middleware(request(ip=None), endpoint)).status_code
                for _ in range(3)]
    assert statuses == [401, 401, 429]
