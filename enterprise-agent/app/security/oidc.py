"""Bounded RS256 OIDC profile. No network or crypto work at import time."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import ssl
import time
from typing import Any
from urllib.parse import urlsplit


class OIDCError(Exception):
    def __init__(self, code: str = 'SSO_IDENTITY_INVALID', status: int = 401) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


def exact_text(value: Any, limit: int) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise OIDCError()
    return value


def https_url(value: Any) -> str:
    exact_text(value, 2048)
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or '\\' in value or any(c.isspace() for c in value)
                or url.port is not None and not 1 <= url.port <= 65535):
            raise ValueError
    except ValueError:
        raise OIDCError('SSO_CONFIGURATION_INVALID', 503) from None
    return value


def configuration(settings: Any) -> None:
    try:
        for field in ('sso_issuer', 'sso_authorize_url', 'sso_token_url', 'sso_jwks_url',
                      'sso_redirect_uri'):
            https_url(getattr(settings, field))
        exact_text(settings.sso_issuer, 512)
        exact_text(settings.sso_client_id, 255)
        if (len(settings.sso_client_secret) < 32 or settings.sso_default_role != 'salesperson'
                or 'openid' not in settings.sso_scopes.split()):
            raise ValueError
        department = settings.sso_default_department
        if department and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', department):
            raise ValueError
    except (AttributeError, ValueError, TypeError, OIDCError):
        raise OIDCError('SSO_CONFIGURATION_INVALID', 503) from None


def challenge(verifier: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_~.-]{43,128}', verifier):
        raise OIDCError()
    proof = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(proof).rstrip(b'=').decode()


def strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in items:
            if key in output:
                raise ValueError
            output[key] = value
        return output

    def invalid(value: str) -> None:
        raise ValueError

    try:
        value = json.loads(raw.decode(), object_pairs_hook=pairs, parse_constant=invalid)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise OIDCError() from None


def b64(value: Any) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise OIDCError()
    try:
        return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    except ValueError:
        raise OIDCError() from None


def token_parts(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(token, str) or len(token) > 16384 or token.count('.') != 2:
        raise OIDCError()
    head, body, signature = token.split('.')
    header, claims = strict_json(b64(head)), strict_json(b64(body))
    b64(signature)
    if (header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', header['kid'])
            or set(header) - {'alg', 'kid', 'typ'} or header.get('typ', 'JWT') != 'JWT'):
        raise OIDCError()
    return header, claims


def select_key(jwks: dict[str, Any], kid: str) -> dict[str, Any]:
    keys = jwks.get('keys')
    if not isinstance(keys, list) or not 1 <= len(keys) <= 10:
        raise OIDCError()
    candidates = [key for key in keys if isinstance(key, dict) and key.get('kid') == kid]
    if len(candidates) != 1:
        raise OIDCError()
    key = candidates[0]
    if (key.get('kty') != 'RSA' or key.get('use', 'sig') != 'sig'
            or key.get('alg', 'RS256') != 'RS256'
            or key.get('key_ops', ['verify']) != ['verify']
            or set(key) & {'d', 'p', 'q', 'dp', 'dq', 'qi', 'oth', 'k'}):
        raise OIDCError()
    modulus = b64(key.get('n'))
    if not 2048 <= int.from_bytes(modulus, 'big').bit_length() <= 4096:
        raise OIDCError()
    if int.from_bytes(b64(key.get('e')), 'big') != 65537:
        raise OIDCError()
    return key


def validate_claims(claims: dict[str, Any], settings: Any, nonce: str) -> dict[str, Any]:
    exact_text(claims.get('sub'), 255)
    exact_text(nonce, 128)
    if claims.get('iss') != settings.sso_issuer or claims.get('nonce') != nonce:
        raise OIDCError()
    aud = claims.get('aud')
    if isinstance(aud, str):
        audiences = [aud]
    elif isinstance(aud, list) and aud and all(isinstance(a, str) for a in aud):
        audiences = aud
    else:
        raise OIDCError()
    if (settings.sso_client_id not in audiences or len(set(audiences)) != len(audiences)
            or (len(audiences) > 1 or 'azp' in claims)
            and claims.get('azp') != settings.sso_client_id):
        raise OIDCError()
    if (any(type(claims.get(key)) is not int for key in ('iat', 'exp'))
            or claims['iat'] > time.time() + 30 or claims['exp'] <= time.time() - 30
            or claims['exp'] <= claims['iat']):
        raise OIDCError()
    return claims


async def fetch(settings: Any, url: str, form: dict[str, str] | None = None) -> dict[str, Any]:
    import httpx

    https_url(url)
    try:
        context = ssl.create_default_context(cafile=settings.sso_ca_bundle or None)
        async with asyncio.timeout(10):
            async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False,
                                         verify=context) as client:
                for attempt in range(2 if form is None else 1):
                    async with client.stream('GET' if form is None else 'POST', url, data=form,
                                             headers={'Accept': 'application/json'}) as response:
                        if (response.status_code in {429, 502, 503, 504}
                                and form is None and attempt == 0):
                            continue
                        if response.status_code != 200:
                            raise OIDCError('SSO_PROVIDER_UNAVAILABLE', 503)
                        content_type = response.headers.get('content-type', '').split(';')[0]
                        if content_type != 'application/json':
                            raise OIDCError()
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw) > 65536:
                                raise OIDCError()
                        return strict_json(bytes(raw))
    except OIDCError:
        raise
    except (httpx.HTTPError, OSError, TimeoutError, ValueError):
        raise OIDCError('SSO_PROVIDER_UNAVAILABLE', 503) from None
    raise OIDCError('SSO_PROVIDER_UNAVAILABLE', 503)


async def exchange(settings: Any, code: str, verifier: str) -> dict[str, Any]:
    exact_text(code, 2048)
    challenge(verifier)
    result = await fetch(settings, settings.sso_token_url, {
        'grant_type': 'authorization_code', 'code': code, 'code_verifier': verifier,
        'client_id': settings.sso_client_id, 'client_secret': settings.sso_client_secret,
        'redirect_uri': settings.sso_redirect_uri})
    if not isinstance(result.get('id_token'), str) or len(result['id_token']) > 16384:
        raise OIDCError()
    return result


async def verify(settings: Any, token: str, nonce: str) -> dict[str, Any]:
    import jwt

    try:
        header, _ = token_parts(token)
        jwks = await fetch(settings, settings.sso_jwks_url)
        candidate = select_key(jwks, header['kid'])
        key = jwt.PyJWK(candidate, algorithm='RS256').key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=settings.sso_client_id,
                            issuer=settings.sso_issuer, leeway=30,
                            options={'require': ['exp', 'iat', 'iss', 'sub', 'aud', 'nonce']})
        return validate_claims(claims, settings, nonce)
    except OIDCError:
        raise
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise OIDCError() from None
