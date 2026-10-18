"""Independent authorization-code store with retained evidence and explicit controls."""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from typing import Any, Iterator
from urllib.parse import urlsplit

SCHEMA = 'controlled-idp-v1'
FAULTS = {'none', 'bad_signature', 'wrong_kid', 'issuer', 'audience', 'nonce', 'expired',
          'future_iat', 'missing_sub', 'long_sub', 'multi_audience', 'privilege_claims',
          'malformed'}


class Denied(Exception):
    def __init__(self, code: str = 'invalid_request', status: int = 400) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def opaque(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', value):
        raise Denied()
    return value


def fields(body: dict[str, Any], names: set[str]) -> None:
    if not isinstance(body, dict) or set(body) != names:
        raise Denied()


def https(value: str) -> str:
    try:
        if (not isinstance(value, str) or len(value) > 2048
                or any(ord(c) < 33 or ord(c) == 127 for c in value)):
            raise ValueError
        url = urlsplit(value)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or '\\' in value
                or url.port is not None and not 1 <= url.port <= 65535):
            raise ValueError
    except ValueError:
        raise Denied('invalid_configuration', 503) from None
    return value


class Issuer:
    def __init__(self, db: sqlite3.Connection, config: dict[str, Any], signer: Any,
                 *, initialize: bool = False) -> None:
        self.db = db
        self.config = config
        self.signer = signer
        self.lock = threading.RLock()
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('PRAGMA temp_store=MEMORY')
        self.db.execute('PRAGMA journal_mode=PERSIST')
        self.db.execute('PRAGMA synchronous=FULL')
        if initialize:
            if self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                raise Denied('store_exists', 503)
            self.db.executescript('''
                CREATE TABLE metadata (id INTEGER PRIMARY KEY, identity TEXT NOT NULL,
                    active_kid TEXT NOT NULL, published TEXT NOT NULL);
                CREATE TABLE requests (request_id TEXT PRIMARY KEY, browser_hash TEXT NOT NULL,
                    data TEXT NOT NULL, expires INTEGER NOT NULL, state TEXT NOT NULL,
                    fault TEXT NOT NULL DEFAULT 'none', attempts INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE codes (code_hash TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    subject TEXT NOT NULL, expires INTEGER NOT NULL, consumed INTEGER NOT NULL);
                CREATE TABLE events (id INTEGER PRIMARY KEY, event TEXT NOT NULL,
                    request_id TEXT, observed_at INTEGER NOT NULL);
            ''')
            self.db.execute('INSERT INTO metadata VALUES (1,?,?,?)',
                            (self.identity(), config['active_kid'],
                             json.dumps([config['active_kid']])))
        metadata = self.db.execute('SELECT * FROM metadata WHERE id=1').fetchone()
        if (not metadata or metadata['identity'] != self.identity()
                or self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok'):
            raise Denied('store_identity_invalid', 503)
        for name in ('requests', 'codes', 'events'):
            self.db.execute(f'SELECT * FROM {name} LIMIT 0')
        self.publication()

    def identity(self) -> str:
        # Binding public keys and immutable subjects also detects accidental environment drift.
        return digest(json.dumps({'schema': SCHEMA, 'store': self.config['store_id'],
            'issuer': self.config['issuer'], 'client': self.config['client_id'],
            'redirect': self.config['redirect_uri'], 'subjects': sorted(
                user['sub'] for user in self.config['users'].values()),
            'public_keys': self.signer.public}, sort_keys=True))

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def event(self, event: str, request_id: str | None = None) -> None:
        self.db.execute('INSERT INTO events VALUES (NULL,?,?,?)',
                        (event, request_id, int(time.time())))

    def publication(self) -> tuple[str, list[str]]:
        row = self.db.execute('SELECT active_kid,published FROM metadata WHERE id=1').fetchone()
        published = json.loads(row['published'])
        if (row['active_kid'] not in published or len(published) != len(set(published))
                or not set(published) <= set(self.signer.public)):
            raise Denied('publication_invalid', 503)
        return row['active_kid'], published

    def rotate(self, body: dict[str, Any]) -> None:
        fields(body, {'active_kid', 'published'})
        published = body['published']
        if (not isinstance(published, list) or not all(isinstance(k, str) for k in published)
                or body['active_kid'] not in published or len(set(published)) != len(published)
                or not set(published) <= set(self.signer.public)):
            raise Denied()
        with self.transaction():
            self.db.execute('UPDATE metadata SET active_kid=?,published=? WHERE id=1',
                            (body['active_kid'], json.dumps(published)))
            self.event('key_publication_changed')

    def authorize(self, params: dict[str, str]) -> tuple[str, str]:
        fields(params, {'client_id', 'redirect_uri', 'response_type', 'scope', 'state', 'nonce',
                        'code_challenge', 'code_challenge_method'})
        if (params['client_id'] != self.config['client_id']
                or params['redirect_uri'] != self.config['redirect_uri']
                or params['response_type'] != 'code' or params['code_challenge_method'] != 'S256'
                or 'openid' not in params['scope'].split()
                or set(params['scope'].split()) - {'openid', 'profile', 'email'}):
            raise Denied()
        for name in ('state', 'nonce', 'code_challenge'):
            opaque(params[name])
        request_id, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.transaction():
            self.db.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,0)',
                (request_id, digest(browser), json.dumps(params), int(time.time()) + 300,
                 'pending', 'none'))
            self.event('authorization_started', request_id)
        return request_id, browser

    def authenticate(self, body: dict[str, str], browser: str) -> dict[str, str]:
        fields(body, {'request_id', 'username', 'password'})
        request_id = opaque(body['request_id'])
        opaque(browser)
        denied = False
        with self.transaction():
            row = self.db.execute('SELECT * FROM requests WHERE request_id=?',
                                  (request_id,)).fetchone()
            if (row is None or row['state'] != 'pending' or row['expires'] <= time.time()
                    or row['attempts'] >= 5
                    or not hmac.compare_digest(row['browser_hash'], digest(browser))):
                raise Denied('authorization_invalid')
            user = self.config['users'].get(body['username'])
            expected = user['password'] if user else self.config['operator_token']
            if not hmac.compare_digest(body['password'].encode(), expected.encode()) or not user:
                self.db.execute('UPDATE requests SET attempts=attempts+1 WHERE request_id=?',
                                (request_id,))
                self.event('authentication_denied', request_id)
                denied = True
            else:
                code = secrets.token_urlsafe(32)
                self.db.execute('UPDATE requests SET state=? WHERE request_id=?',
                                ('authorized', request_id))
                self.db.execute('INSERT INTO codes VALUES (?,?,?,?,0)',
                                (digest(code), request_id, user['sub'], int(time.time()) + 120))
                self.event('code_issued', request_id)
                result = {'code': code, 'state': json.loads(row['data'])['state']}
        if denied:
            raise Denied('authentication_failed', 401)
        return result

    def token(self, form: dict[str, str]) -> dict[str, Any]:
        fields(form, {'grant_type', 'code', 'client_id', 'client_secret', 'redirect_uri',
                      'code_verifier'})
        if (form['client_id'] != self.config['client_id']
                or not hmac.compare_digest(form['client_secret'].encode(),
                                           self.config['client_secret'].encode())):
            raise Denied('invalid_client', 401)
        opaque(form['code'])
        verifier = form['code_verifier']
        if not re.fullmatch(r'[A-Za-z0-9_~.-]{43,128}', verifier):
            raise Denied('invalid_grant')
        with self.transaction():
            row = self.db.execute('''SELECT c.*,r.data,r.fault FROM codes c
                JOIN requests r USING(request_id) WHERE code_hash=?''',
                (digest(form['code']),)).fetchone()
            if (row is None or row['consumed'] or row['expires'] <= time.time()
                    or form['grant_type'] != 'authorization_code'
                    or form['redirect_uri'] != self.config['redirect_uri']):
                raise Denied('invalid_grant')
            original = json.loads(row['data'])
            if not hmac.compare_digest(encoded(hashlib.sha256(verifier.encode()).digest()),
                                       original['code_challenge']):
                raise Denied('invalid_grant')
            now = int(time.time())
            claims = {'iss': self.config['issuer'], 'aud': self.config['client_id'],
                      'sub': row['subject'], 'nonce': original['nonce'], 'iat': now,
                      'exp': now + 120, 'preferred_username': 'reference-user'}
            fault = row['fault']
            changes = {'issuer': {'iss': 'https://wrong.reference.invalid'},
                       'audience': {'aud': 'wrong-client'}, 'nonce': {'nonce': 'wrong'},
                       'expired': {'iat': now - 600, 'exp': now - 120},
                       'future_iat': {'iat': now + 300, 'exp': now + 600},
                       'long_sub': {'sub': 'x' * 256},
                       'multi_audience': {'aud': [self.config['client_id'], 'other']},
                       'privilege_claims': {'role': 'admin', 'department': 'dept_finance'}}
            claims.update(changes.get(fault, {}))
            if fault == 'missing_sub':
                claims.pop('sub')
            active, _ = self.publication()
            token = self.signer.sign(claims, active, fault)
            self.db.execute('UPDATE codes SET consumed=1 WHERE code_hash=?',
                            (digest(form['code']),))
            self.event('token_issued', row['request_id'])
            # A lost response cannot reissue this code. Start a new application login.
            return {'id_token': token, 'access_token': secrets.token_urlsafe(32),
                    'token_type': 'Bearer', 'expires_in': 120}

    def fault(self, body: dict[str, str]) -> None:
        fields(body, {'request_id', 'mode'})
        request_id = opaque(body['request_id'])
        if body['mode'] not in FAULTS - {'none'}:
            raise Denied()
        with self.transaction():
            row = self.db.execute('SELECT state,fault FROM requests WHERE request_id=?',
                                  (request_id,)).fetchone()
            if row is None or row['state'] != 'pending' or row['fault'] != 'none':
                raise Denied('fault_scope_invalid', 409)
            self.db.execute('UPDATE requests SET fault=? WHERE request_id=?',
                            (body['mode'], request_id))
            self.event('fault_installed', request_id)

    def evidence(self) -> dict[str, Any]:
        requests = [dict(r) for r in self.db.execute('''SELECT request_id,state,expires,fault,
            attempts FROM requests ORDER BY rowid LIMIT 201''')]
        codes = [dict(r) for r in self.db.execute('''SELECT request_id,consumed,expires
            FROM codes ORDER BY rowid LIMIT 201''')]
        events = [dict(r) for r in self.db.execute('SELECT * FROM events ORDER BY id LIMIT 1001')]
        if len(requests) > 200 or len(codes) > 200 or len(events) > 1000:
            raise Denied('evidence_limit', 503)
        active, published = self.publication()
        return {'schema': SCHEMA, 'store_id': self.config['store_id'],
                'identity_hash': self.identity(), 'active_kid': active, 'published': published,
                'requests': requests, 'codes': codes, 'events': events, 'runtime': 'BLOCKED'}


def open_database(path: Path, *, initialize: bool = False) -> sqlite3.Connection:
    if (not path.is_absolute() or path.is_symlink() or not path.parent.is_dir()
            or any(p.is_symlink() for p in path.parents) or path.exists() == initialize):
        raise Denied('store_path_invalid', 503)
    return sqlite3.connect(path.as_uri() + ('?mode=rwc' if initialize else '?mode=rw'),
                           uri=True, isolation_level=None, check_same_thread=False)
