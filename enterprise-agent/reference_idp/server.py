"""Explicit TLS listeners for synthetic reference OIDC; no access logs or key generation."""
from __future__ import annotations

import argparse
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import ssl
import threading
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

from reference_idp.core import Denied, Issuer, encoded, https, open_database


def strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError

    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    if not isinstance(result, dict):
        raise ValueError
    return result


def parameters(raw: str) -> dict[str, str]:
    data = parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=12)
    if any(len(values) != 1 for values in data.values()):
        raise Denied()
    return {key: values[0] for key, values in data.items()}


class Signer:
    def __init__(self, keys: dict[str, str]) -> None:
        import jwt
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        self.jwt = jwt
        self.private: dict[str, Any] = {}
        self.public: dict[str, Any] = {}
        if not 2 <= len(keys) <= 10:
            raise ValueError('INVALID_KEY_SET')
        for kid, pem in keys.items():
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', kid):
                raise ValueError('INVALID_KEY_ID')
            key = load_pem_private_key(pem.encode(), password=None)
            if (not isinstance(key, RSAPrivateKey) or not 2048 <= key.key_size <= 4096
                    or key.public_key().public_numbers().e != 65537):
                raise ValueError('INVALID_RSA_KEY')
            self.private[kid] = key
            self.public[kid] = {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
                                'kid': kid, 'alg': 'RS256', 'use': 'sig'}
        unique = {json.dumps({x: v for x, v in key.items() if x != 'kid'}, sort_keys=True)
                  for key in self.public.values()}
        if len(unique) != len(keys):
            raise ValueError('DUPLICATE_RSA_KEY')

    def sign(self, claims: dict[str, Any], kid: str, fault: str) -> str:
        if fault == 'malformed':
            return 'invalid-reference-token'
        token = self.jwt.encode(claims, self.private[kid], algorithm='RS256',
                                headers={'kid': 'unpublished-key' if fault == 'wrong_kid' else kid})
        if fault == 'bad_signature':
            import base64
            parts = token.split('.')
            signature = bytearray(base64.urlsafe_b64decode(parts[2] + '=' * (-len(parts[2]) % 4)))
            signature[0] ^= 1
            parts[2] = encoded(bytes(signature))
            token = '.'.join(parts)
        return token


def configuration(env: dict[str, str]) -> tuple[dict[str, Any], Signer]:
    issuer, redirect = https(env['IDP_ISSUER']), https(env['IDP_REDIRECT_URI'])
    store_id = str(UUID(env['IDP_STORE_ID']))
    if (store_id != env['IDP_STORE_ID'] or UUID(store_id).version != 4
            or len(issuer) > 512 or urlsplit(issuer).path
            or len(env['IDP_CLIENT_SECRET']) < 32 or len(env['IDP_OPERATOR_TOKEN']) < 32
            or env['IDP_CLIENT_SECRET'] == env['IDP_OPERATOR_TOKEN']
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', env['IDP_CLIENT_ID'])):
        raise ValueError('INVALID_CONFIGURATION')
    users = strict_json(env['IDP_USERS_JSON'].encode())
    if not 2 <= len(users) <= 10:
        raise ValueError('INVALID_USERS')
    subjects = set()
    for name, user in users.items():
        if (not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name) or not isinstance(user, dict)
                or set(user) != {'sub', 'password'}
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,255}', user['sub'])
                or not isinstance(user['password'], str) or len(user['password']) < 16
                or user['sub'] in subjects):
            raise ValueError('INVALID_USERS')
        subjects.add(user['sub'])
    signer = Signer(strict_json(env['IDP_SIGNING_KEYS_JSON'].encode()))
    if env['IDP_ACTIVE_KID'] not in signer.public:
        raise ValueError('INVALID_ACTIVE_KEY')
    return {'issuer': issuer, 'redirect_uri': redirect, 'store_id': store_id, 'users': users,
            'client_id': env['IDP_CLIENT_ID'], 'client_secret': env['IDP_CLIENT_SECRET'],
            'operator_token': env['IDP_OPERATOR_TOKEN'],
            'active_kid': env['IDP_ACTIVE_KID']}, signer


class Service:
    def __init__(self, issuer: Issuer) -> None:
        self.issuer = issuer

    def handle(self, method: str, target: str, headers: dict[str, str], raw: bytes,
               *, control: bool = False) -> tuple[int, dict[str, Any] | str, dict[str, str]]:
        try:
            with self.issuer.lock:
                return self.dispatch(method, target, headers, raw, control=control)
        except Denied as exc:
            return exc.status, {'error': exc.code}, {}
        except (ValueError, TypeError, KeyError, UnicodeError):
            return 400, {'error': 'invalid_request'}, {}
        except Exception:
            return 503, {'error': 'reference_idp_unavailable'}, {}

    def dispatch(self, method: str, target: str, headers: dict[str, str], raw: bytes,
                 *, control: bool) -> tuple[int, dict[str, Any] | str, dict[str, str]]:
        issuer, config = self.issuer, self.issuer.config
        url = urlsplit(target)
        if url.scheme or url.netloc or url.fragment or '%' in url.path:
            raise Denied()
        if method == 'GET' and raw:
            raise Denied()
        params = parameters(url.query) if url.query else {}
        if control:
            supplied = headers.get('authorization', '')
            if not hmac.compare_digest(supplied.encode(),
                                       ('Bearer ' + config['operator_token']).encode()):
                raise Denied('unauthorized', 401)
            if params:
                raise Denied()
            if method == 'GET' and url.path == '/control/evidence':
                return 200, issuer.evidence(), {}
            if method == 'POST' and headers.get('content-type') == 'application/json':
                body = strict_json(raw)
                if url.path == '/control/rotate':
                    issuer.rotate(body)
                    return 200, {'changed': True}, {}
                if url.path == '/control/fault':
                    issuer.fault(body)
                    return 201, {'installed': True}, {}
            raise Denied('not_found', 404)
        if method == 'GET' and url.path == '/authorize':
            request_id, browser = issuer.authorize(params)
            html = ('<!doctype html><meta charset="utf-8"><title>Controlled reference IdP</title>'
                    '<h1>Synthetic reference login</h1>'
                    '<p>Use isolated fixture credentials only.</p>'
                    '<form method="post" action="/authenticate">'
                    f'<input type="hidden" name="request_id" value="{request_id}">'
                    '<label>Username <input name="username" autocomplete="off" required></label>'
                    '<label>Password <input type="password" name="password" '
                    'autocomplete="off" required></label><button>Sign in</button></form>')
            return 200, html, {'Set-Cookie': 'idp_request=' + browser +
                              '; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=300'}
        if params:
            raise Denied()
        if method == 'GET' and url.path == '/.well-known/openid-configuration':
            return 200, {'issuer': config['issuer'],
                'authorization_endpoint': config['issuer'] + '/authorize',
                'token_endpoint': config['issuer'] + '/token',
                'jwks_uri': config['issuer'] + '/jwks', 'response_types_supported': ['code'],
                'subject_types_supported': ['public'],
                'id_token_signing_alg_values_supported': ['RS256'],
                'token_endpoint_auth_methods_supported': ['client_secret_post'],
                'code_challenge_methods_supported': ['S256'],
                'scopes_supported': ['openid', 'profile', 'email']}, {}
        if method == 'GET' and url.path == '/jwks':
            _, published = issuer.publication()
            return 200, {'keys': [issuer.signer.public[k] for k in published]}, {}
        if method == 'GET' and url.path == '/health':
            issuer.db.execute('SELECT 1')
            return 200, {'status': 'ready'}, {}
        if method == 'POST' and url.path in {'/authenticate', '/token'}:
            if headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                raise Denied()
            form = parameters(raw.decode())
            if url.path == '/token':
                return 200, issuer.token(form), {}
            if headers.get('origin') != config['issuer']:
                raise Denied('browser_binding_invalid', 403)
            cookies = SimpleCookie()
            cookies.load(headers.get('cookie', ''))
            cookie = cookies.get('idp_request')
            result = issuer.authenticate(form, cookie.value if cookie else '')
            return 303, {}, {'Location': config['redirect_uri'] + '?' + urlencode(result),
                            'Set-Cookie': 'idp_request=; Secure; HttpOnly; SameSite=Lax; '
                                          'Path=/; Max-Age=0'}
        raise Denied('not_found', 404)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, service: Service, control: bool, tls: ssl.SSLContext) -> None:
        self.service = service
        self.control = control
        super().__init__(('0.0.0.0', 8444 if control else 8443), Handler)
        self.socket = tls.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)

    def handle_error(self, request: Any, client_address: Any) -> None:
        print('REFERENCE_IDP_CONNECTION_FAILED', flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)
        self.connection.do_handshake()

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def send_error(self, code: int, message: str | None = None,
                   explain: str | None = None) -> None:
        self.respond(code, {'error': 'invalid_http_request'}, {})

    def process(self) -> None:
        try:
            names = [name.lower() for name in self.headers.keys()]
            headers = {name.lower(): value for name, value in self.headers.items()}
            length = headers.get('content-length', '0')
            if (len(names) != len(set(names)) or 'transfer-encoding' in headers
                    or not re.fullmatch(r'[0-9]{1,5}', length) or int(length) > 16384
                    or len(self.path) > 4096):
                self.send_error(400)
                return
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                self.send_error(400)
                return
            self.respond(*self.server.service.handle(self.command, self.path, headers, raw,
                                                      control=self.server.control))
        except (OSError, TimeoutError):
            self.close_connection = True

    def respond(self, status: int, data: dict[str, Any] | str, headers: dict[str, str]) -> None:
        html = isinstance(data, str)
        raw = (data if html else json.dumps(data, allow_nan=False)).encode()
        if len(raw) > 65536:
            status, raw, html, headers = 503, b'{"error":"evidence_limit"}', False, {}
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        redirect = urlsplit(self.server.service.issuer.config['redirect_uri'])
        callback_origin = redirect.scheme + '://' + redirect.netloc
        self.send_header('Content-Security-Policy',
                         "default-src 'none'; form-action 'self' " + callback_origin +
                         "; frame-ancestors 'none'; base-uri 'none'")
        self.send_header('Connection', 'close')
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    do_GET = do_POST = process


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize', action='store_true')
    args = parser.parse_args()
    try:
        config, signer = configuration(dict(os.environ))
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(os.environ['IDP_TLS_CERT'], os.environ['IDP_TLS_KEY'])
        db = open_database(Path(os.environ['IDP_DB']), initialize=args.initialize)
        service = Service(Issuer(db, config, signer, initialize=args.initialize))
        if args.initialize:
            db.close()
            print('REFERENCE_IDP_INITIALIZED')
            return 0
        public, control = Server(service, False, tls), Server(service, True, tls)
        thread = threading.Thread(target=control.serve_forever, daemon=True)
        thread.start()
        try:
            public.serve_forever()
        finally:
            control.shutdown()
            control.server_close()
            public.server_close()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print('REFERENCE_IDP_STARTUP_FAILED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
