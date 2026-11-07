"""F2-01: real JWT verification and in-process ASGI quota/authentication boundaries."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI, Response

from app.middleware import rate_limit
from app.security import rbac

# Synthetic keys used only for offline signing; never application configuration.
SIGNING_KEY = "f201-offline-fixture-" * 4
OTHER_KEY = "f201-wrong-fixture-" * 3


def token(subject: Any = "victim", **claims: Any) -> str:
    payload = {"sub": subject, "exp": 4102444800, **claims}
    return jwt.encode(payload, SIGNING_KEY, algorithm="HS256")


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


@pytest.fixture(autouse=True)
def isolated_identity_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        jwt_secret_key=SIGNING_KEY, jwt_algorithm="HS256", rate_limit_per_minute=2,
        auth_check_db=True, is_dev=False,
    )
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    monkeypatch.setattr(rbac, "get_settings", lambda: settings)
    # Inject only the quota store; real middleware/JWT/account dependencies stay active.
    memory = rate_limit.InMemoryRateLimiter()
    monkeypatch.setattr(rate_limit, "_get_limiter", AsyncMock(return_value=memory))



INVALID_TOKENS = [
    pytest.param(jwt.encode({"sub": "victim", "exp": 4102444800}, "", algorithm="none"), id="unsigned"),
    pytest.param(jwt.encode({"sub": "victim", "exp": 4102444800}, OTHER_KEY, algorithm="HS256"), id="forged"),
    pytest.param(jwt.encode({"sub": "victim", "exp": 4102444800}, SIGNING_KEY, algorithm="HS512"), id="algorithm"),
    pytest.param(token(exp=1), id="expired"),
    pytest.param(token(nbf=4102444800), id="not-yet-valid"),
    pytest.param(jwt.encode({"sub": "victim"}, SIGNING_KEY, algorithm="HS256"), id="missing-exp"),
    pytest.param(jwt.encode({"exp": 4102444800}, SIGNING_KEY, algorithm="HS256"), id="missing-sub"),
    pytest.param(token([]), id="list-sub"),
    pytest.param(token(42), id="numeric-sub"),
    pytest.param(token(""), id="empty-sub"),
    pytest.param(token("   "), id="blank-sub"),
    pytest.param(token("x" * 65), id="long-sub"),
    pytest.param(token(exp="4102444800"), id="string-exp"),
    pytest.param(token(exp=True), id="boolean-exp"),
    pytest.param(token(exp=float("inf")), id="infinite-exp"),
    pytest.param(token(exp=float("nan")), id="nan-exp"),
    pytest.param("not.a.jwt", id="malformed"),
]


@pytest.mark.parametrize("credential", INVALID_TOKENS)
def test_should_not_select_user_when_token_is_untrusted(credential: str) -> None:
    request = SimpleNamespace(headers=bearer(credential))
    assert rate_limit._extract_user_id(request) is None


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_should_accept_verified_identity_with_case_insensitive_scheme(scheme: str) -> None:
    request = SimpleNamespace(headers={"Authorization": f"{scheme} {token()}"})
    assert rate_limit._extract_user_id(request) == "victim"


def test_should_bound_credentials_before_decoding(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even a signed, otherwise valid token cannot create unbounded middleware decode work.
    credential = token(padding="x" * 9000)
    decoder = Mock(side_effect=AssertionError("oversized input must not reach JWT"))
    monkeypatch.setattr(rbac.jwt, "decode", decoder)
    assert rate_limit._extract_user_id(SimpleNamespace(headers=bearer(credential))) is None
    decoder.assert_not_called()


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch, fake_session_factory: Any) -> AsyncIterator[Any]:
    from app.core import database

    row = SimpleNamespace(username="Synthetic", role="salesperson", department="dept_sales",
                          is_active=True)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(fetchone=lambda: row)))
    monkeypatch.setattr(database, "get_session_factory", lambda: fake_session_factory(db))
    app = FastAPI()
    app.middleware("http")(rate_limit.rate_limit_middleware)
    calls: list[str] = []

    @app.get("/limited")
    async def protected(user: rbac.User = Depends(rbac.get_current_user)) -> dict[str, str]:
        calls.append(user.user_id)
        return {"user": user.user_id}

    @app.post("/api/v1/auth/login")
    async def login() -> Response:
        return Response(status_code=401)

    transport = httpx.ASGITransport(app=app, client=("192.0.2.1", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://offline.invalid") as http:
        yield http, db, row, calls


@pytest.mark.asyncio
async def test_should_share_anonymous_quota_when_forged_subjects_rotate(client: Any) -> None:
    http, db, _, calls = client
    statuses = []
    for i in range(3):
        forged = jwt.encode({"sub": f"fake-{i}", "exp": 4102444800}, OTHER_KEY, algorithm="HS256")
        statuses.append((await http.get("/limited", headers=bearer(forged))).status_code)
    assert statuses == [401, 401, 429]
    db.execute.assert_not_awaited()
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("credential", [INVALID_TOKENS[0], INVALID_TOKENS[1], INVALID_TOKENS[3]])
async def test_should_not_consume_victim_quota_with_untrusted_bearer(
    client: Any, credential: str,
) -> None:
    http, db, _, calls = client
    for _ in range(2):
        assert (await http.get("/limited", headers=bearer(credential))).status_code == 401
    assert (await http.get("/limited", headers=bearer(credential))).status_code == 429
    # Same source IP, different trust boundary: a forged sub cannot poison the user bucket.
    response = await http.get("/limited", headers=bearer(token()))
    assert response.status_code == 200
    assert response.json() == {"user": "victim"}
    db.execute.assert_awaited_once()
    assert calls == ["victim"]


@pytest.mark.asyncio
async def test_should_isolate_verified_user_quotas_at_one_source(client: Any) -> None:
    http, _, _, calls = client
    for _ in range(2):
        assert (await http.get("/limited", headers=bearer(token("user-a")))).status_code == 200
    assert (await http.get("/limited", headers=bearer(token("user-a")))).status_code == 429
    assert (await http.get("/limited", headers=bearer(token("user-b")))).status_code == 200
    assert calls == ["user-a", "user-a", "user-b"]


@pytest.mark.asyncio
@pytest.mark.parametrize("signed", [False, True])
async def test_should_keep_login_source_bound_even_when_subjects_rotate(client: Any, signed: bool) -> None:
    http, db, _, calls = client
    statuses = []
    for i in range(11):
        credential = token(f"user-{i}") if signed else jwt.encode(
            {"sub": f"fake-{i}", "exp": 4102444800}, "", algorithm="none",
        )
        response = await http.post("/api/v1/auth/login", headers=bearer(credential))
        statuses.append(response.status_code)
    assert statuses == [401] * 10 + [429]
    assert response.headers["Retry-After"] == "60"
    db.execute.assert_not_awaited()
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status", [("disabled", 401), ("store-down", 503)])
async def test_should_still_enforce_current_identity_after_quota_verification(
    client: Any, failure: str, status: int,
) -> None:
    http, db, row, calls = client
    if failure == "disabled":
        row.is_active = False
    else:
        db.execute.side_effect = ConnectionError("synthetic-private-error")
    response = await http.get("/limited", headers=bearer(token()))
    assert response.status_code == status
    assert "synthetic-private-error" not in response.text
    assert token() not in response.text
    assert calls == []
    db.execute.assert_awaited_once()
