"""C19 actual-source/in-memory checks; crypto, HTTP, Redis and PG remain injected."""
from __future__ import annotations

import ast
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from enum import Enum
import hashlib
import io
import json
from pathlib import Path
import runpy
import secrets
import sqlite3
import sys
import time
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference_idp.core import Denied, Issuer, encoded
from reference_idp.server import Service, parameters, Handler
from reference_idp.acceptance import CASES, observations, plan
BASE = runpy.run_path(str(ROOT / 'tests/test_cross_process_state.py'))
OIDC = BASE['load']('c19_oidc', 'app/security/oidc.py')


def settings():
    return NS(sso_enabled=True, sso_issuer='https://idp.reference.test:8443',
        sso_client_id='reference-app', sso_client_secret='synthetic-client-' + 'x' * 32,
        sso_authorize_url='https://idp.reference.test:8443/authorize',
        sso_token_url='https://reference-idp:8443/token',
        sso_jwks_url='https://reference-idp:8443/jwks',
        sso_redirect_uri='https://app.reference.test:8443/api/v1/auth/sso/callback',
        sso_scopes='openid profile email', sso_ca_bundle='', sso_default_role='salesperson',
        sso_default_department='dept_sales', is_dev=False)


def jwt_text(claims, kid='key-a', algorithm='RS256'):
    return '.'.join([encoded(json.dumps({'alg': algorithm, 'kid': kid}).encode()),
                     encoded(json.dumps(claims).encode()), encoded(b'NOT_A_REAL_SIGNATURE')])


class FakeSigner:
    """Deliberate non-cryptographic signer: tests cannot certify RSA or PyJWT."""
    def __init__(self):
        self.public = {kid: dict(kid=kid, kty='RSA', use='sig', alg='RS256', e='AQAB',
            n=encoded(((1 << 2047) + index).to_bytes(256, 'big')))
            for kid, index in [('key-a', 1), ('key-b', 3)]}
        self.calls = []

    def sign(self, claims, kid, fault):
        self.calls.append((deepcopy(claims), kid, fault))
        return jwt_text(claims, 'unknown' if fault == 'wrong_kid' else kid)


def make():
    s = settings()
    config = dict(issuer=s.sso_issuer, client_id=s.sso_client_id,
        client_secret=s.sso_client_secret, redirect_uri=s.sso_redirect_uri,
        store_id=str(uuid4()), active_kid='key-a', operator_token='synthetic-operator-' + 'x' * 32,
        users={'alice': {'sub': 'subject-a', 'password': 'synthetic-password-a'},
               'bob': {'sub': 'subject-b', 'password': 'synthetic-password-b'}})
    db = sqlite3.connect(':memory:', isolation_level=None, check_same_thread=False)
    return Issuer(db, config, FakeSigner(), initialize=True)


def request_params(issuer, verifier='v' * 43):
    return dict(client_id=issuer.config['client_id'], redirect_uri=issuer.config['redirect_uri'],
        response_type='code', scope='openid profile email', state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32), code_challenge=OIDC.challenge(verifier),
        code_challenge_method='S256')


def grant(issuer, fault=None):
    params = request_params(issuer)
    rid, browser = issuer.authorize(params)
    if fault: issuer.fault({'request_id': rid, 'mode': fault})
    response = issuer.authenticate(dict(request_id=rid, username='alice',
                                       password='synthetic-password-a'), browser)
    form = dict(client_id=issuer.config['client_id'], client_secret=issuer.config['client_secret'],
        redirect_uri=issuer.config['redirect_uri'], code=response['code'], code_verifier='v' * 43,
        grant_type='authorization_code')
    return form, rid, params


class IdpTests(unittest.TestCase):
    def setUp(self):
        self.issuer = make(); self.addCleanup(self.issuer.db.close)
        self.service = Service(self.issuer)

    def test_exact_client_redirect_and_pkce_required(self):
        for change in ({'redirect_uri': 'https://untrusted.invalid'}, {'client_id': 'other'},
                       {'code_challenge_method': 'plain'}, {'scope': 'email'}, {'state': 'short'}):
            with self.assertRaises(Denied):
                self.issuer.authorize({**request_params(self.issuer), **change})
        self.assertEqual(self.issuer.evidence()['requests'], [])

    def test_code_one_use_bound_to_identity_and_nonce(self):
        form, rid, params = grant(self.issuer)
        result = self.issuer.token(form)
        claims = self.issuer.signer.calls[0][0]
        self.assertEqual(claims['sub'], 'subject-a')
        self.assertEqual(claims['nonce'], params['nonce'])
        with self.assertRaises(Denied): self.issuer.token(form)
        self.assertEqual(len(self.issuer.signer.calls), 1)
        evidence = json.dumps(self.issuer.evidence())
        for secret in (form['code'], form['client_secret'], params['nonce'], result['id_token']):
            self.assertNotIn(secret, evidence)

    def test_wrong_client_redirect_proof_do_not_consume_or_sign(self):
        form, _, _ = grant(self.issuer)
        for change in ({'client_secret': 'wrong'}, {'redirect_uri': 'https://other.invalid'},
                       {'code_verifier': 'z' * 43}, {'grant_type': 'refresh_token'}):
            with self.assertRaises(Denied): self.issuer.token({**form, **change})
        self.assertEqual(self.issuer.signer.calls, [])
        self.assertEqual(self.issuer.evidence()['codes'][0]['consumed'], 0)
        self.issuer.token(form)

    def test_expired_code_denies_without_new_token(self):
        form, _, _ = grant(self.issuer)
        with patch('reference_idp.core.time.time', return_value=time.time() + 121):
            with self.assertRaises(Denied): self.issuer.token(form)
        self.assertEqual(self.issuer.signer.calls, [])

    def test_expired_browser_request_and_wrong_cookie_deny(self):
        rid, cookie = self.issuer.authorize(request_params(self.issuer))
        body = dict(request_id=rid, username='alice', password='synthetic-password-a')
        with self.assertRaises(Denied): self.issuer.authenticate(body, secrets.token_urlsafe(32))
        with patch('reference_idp.core.time.time', return_value=time.time() + 301):
            with self.assertRaises(Denied): self.issuer.authenticate(body, cookie)
        self.assertEqual(self.issuer.evidence()['codes'], [])

    def test_login_attempts_are_retained_and_bounded(self):
        rid, cookie = self.issuer.authorize(request_params(self.issuer))
        for _ in range(5):
            with self.assertRaises(Denied):
                self.issuer.authenticate(dict(request_id=rid, username='alice', password='bad'), cookie)
        with self.assertRaises(Denied):
            self.issuer.authenticate(dict(request_id=rid, username='alice',
                                         password='synthetic-password-a'), cookie)
        self.assertEqual(self.issuer.evidence()['requests'][0]['attempts'], 5)

    def test_parallel_exchange_one_terminal_issue(self):
        form, _, _ = grant(self.issuer)
        def exchange(_):
            with self.issuer.lock:
                try: self.issuer.token(form); return True
                except Denied: return False
        with ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual(sum(pool.map(exchange, range(6))), 1)
        self.assertEqual(len(self.issuer.signer.calls), 1)

    def test_signing_failure_rolls_back_consumption(self):
        form, _, _ = grant(self.issuer)
        with patch.object(self.issuer.signer, 'sign', side_effect=ValueError('synthetic')):
            with self.assertRaises(ValueError): self.issuer.token(form)
        self.assertEqual(self.issuer.evidence()['codes'][0]['consumed'], 0)

    def test_rotation_retains_keys_and_removes_unpublished_match(self):
        self.issuer.rotate({'active_kid': 'key-b', 'published': ['key-a', 'key-b']})
        self.assertEqual(self.issuer.publication()[0], 'key-b')
        self.issuer.rotate({'active_kid': 'key-b', 'published': ['key-b']})
        status, data, _ = self.service.handle('GET', '/jwks', {}, b'')
        self.assertEqual(status, 200)
        with self.assertRaises(OIDC.OIDCError): OIDC.select_key(data, 'key-a')
        self.assertIn('key-a', self.issuer.signer.public)
        with self.assertRaises(Denied): self.issuer.rotate({'active_kid': 'key-a', 'published': []})

    def test_fault_is_scoped_once_and_only_before_authorization(self):
        form, rid, _ = grant(self.issuer, 'nonce')
        with self.assertRaises(Denied): self.issuer.fault({'request_id': rid, 'mode': 'issuer'})
        self.issuer.token(form)
        self.assertEqual(self.issuer.signer.calls[0][0]['nonce'], 'wrong')
        fresh, _, _ = grant(self.issuer); self.issuer.token(fresh)
        self.assertNotEqual(self.issuer.signer.calls[1][0]['nonce'], 'wrong')

    def test_restart_model_preserves_consumed_codes_and_identity(self):
        form, _, _ = grant(self.issuer); self.issuer.token(form)
        reopened = Issuer(self.issuer.db, self.issuer.config, self.issuer.signer)
        with self.assertRaises(Denied): reopened.token(form)
        with self.assertRaises(Denied):
            Issuer(self.issuer.db, {**self.issuer.config, 'store_id': str(uuid4())}, self.issuer.signer)

    def test_operator_controls_denied_to_client_and_no_reset(self):
        header = {'authorization': 'Bearer ' + self.issuer.config['client_secret']}
        self.assertEqual(self.service.handle('GET', '/control/evidence', header, b'', control=True)[0], 401)
        header['authorization'] = 'Bearer ' + self.issuer.config['operator_token']
        self.assertEqual(self.service.handle('GET', '/control/evidence', header, b'', control=True)[0], 200)
        self.assertEqual(self.service.handle('POST', '/reset', header, b'{}', control=True)[0], 404)

    def test_form_is_browser_bound_no_password_or_token_echo(self):
        status, html, headers = self.service.handle('GET', '/authorize?' +
            urlencode(request_params(self.issuer)), {}, b'')
        self.assertEqual(status, 200); self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertNotIn('synthetic-password', html)
        self.assertEqual(self.service.handle('POST', '/authenticate',
            {'content-type': 'application/x-www-form-urlencoded', 'origin': 'https://other.invalid'},
            b'username=alice&password=bad&request_id=bad')[0], 403)
        self.assertEqual(self.service.handle('GET', '/authorize?client_id=a&client_id=b', {}, b'')[0], 400)

    def test_discovery_only_advertises_supported_profile(self):
        status, data, _ = self.service.handle('GET', '/.well-known/openid-configuration', {}, b'')
        self.assertEqual(data['id_token_signing_alg_values_supported'], ['RS256'])
        self.assertEqual(data['code_challenge_methods_supported'], ['S256'])
        self.assertNotIn('userinfo_endpoint', data)

    def test_http_handler_does_not_echo_request_errors(self):
        handler = object.__new__(Handler)
        handler.server = NS(service=self.service)
        handler.send_response = Mock(); handler.send_header = Mock(); handler.end_headers = Mock()
        handler.wfile = io.BytesIO()
        handler.send_error(400, 'synthetic-password')
        self.assertNotIn(b'synthetic-password', handler.wfile.getvalue())
        self.assertIn(('Cache-Control', 'no-store'), [x.args for x in handler.send_header.call_args_list])
        headers = dict(x.args for x in handler.send_header.call_args_list)
        self.assertIn("form-action 'self' https://app.reference.test:8443;",
                      headers['Content-Security-Policy'])

    def test_plan_is_complete_blocked_and_reports_do_not_certify(self):
        report = dict(candidate_commit='a' * 40, app_digest='sha256:' + 'b' * 64,
            idp_digest='sha256:' + 'c' * 64, store_id=str(uuid4()), store_identity_hash='d' * 64,
            cases=[{'id': key, 'reported_status': 'PASS', 'artifact_sha256': ['e' * 64]}
                   for key in CASES])
        result = observations(report)
        self.assertEqual(len(plan()['cases']), 16)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(all(row['status'] == 'BLOCKED' for row in result['cases']))
        self.assertFalse(result['release_allowed'])
        self.assertEqual(result['evidence_type'], 'operator_report_unverified')
        report['cases'][0]['artifact_sha256'] = []
        with self.assertRaises(ValueError): observations(report)

    def test_observations_deny_extra_fields_duplicates_and_secret_text(self):
        report = dict(candidate_commit='a' * 40, app_digest='sha256:' + 'b' * 64,
            idp_digest='sha256:' + 'c' * 64, store_id=str(uuid4()), store_identity_hash='d' * 64,
            cases=[{'id': key, 'reported_status': 'BLOCKED', 'artifact_sha256': []}
                   for key in CASES])
        observations(report)
        for change in ({'token': 'secret'}, {'candidate_commit': 'secret'},
                       {'cases': report['cases'][:-1]}, {'store_id': 'not-a-store'}):
            with self.assertRaises(ValueError): observations({**report, **change})
        report['cases'][-1] = report['cases'][0]
        with self.assertRaises(ValueError): observations(report)

    def test_strict_configuration_primitives(self):
        from reference_idp.core import https
        from reference_idp.server import strict_json
        for value in ('https://idp.invalid:0', 'https://idp.invalid:99999',
                      'https://idp.invalid\n', 'http://idp.invalid', 'https://u:p@idp.invalid'):
            with self.assertRaises(Denied): https(value)
        for raw in (b'{"x":NaN}', b'{"x":1,"x":2}'):
            with self.assertRaises(ValueError): strict_json(raw)


class RelyingPartyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = settings(); self.issuer = make(); self.addCleanup(self.issuer.db.close)
        self.claims = dict(iss=self.settings.sso_issuer, sub='subject-a',
            aud=self.settings.sso_client_id, nonce='n' * 43, iat=int(time.time()), exp=int(time.time()) + 120)

    def test_configuration_denies_http_credentials_and_privileged_default(self):
        OIDC.configuration(self.settings)
        for field, value in [('sso_token_url', 'http://reference-idp/token'),
            ('sso_authorize_url', 'https://user:secret@idp.invalid'), ('sso_default_role', 'admin'),
            ('sso_client_secret', 'short'), ('sso_issuer', 'https://idp.invalid?x=1')]:
            altered = NS(**vars(self.settings)); setattr(altered, field, value)
            with self.assertRaises(OIDC.OIDCError): OIDC.configuration(altered)
        tree = ast.parse((ROOT / 'app/config.py').read_text())
        chosen = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                  and node.module == '__future__' or isinstance(node, ast.FunctionDef)
                  and node.name == 'validate_production_settings']
        ns = {'_DEFAULT_SECRETS': {}}
        exec(compile(ast.Module(body=chosen, type_ignores=[]), '<config-source>', 'exec'), ns)
        configured = NS(**vars(self.settings), auth_require_password=True, auth_check_db=True,
                        jwt_secret_key='x' * 32, cors_allow_origins='https://app.reference.test',
                        crm_tool_provider='mock', mail_tool_provider='mock', ticket_tool_provider='mock')
        with patch.dict(sys.modules, {'app.security.oidc': OIDC}):
            self.assertEqual(ns['validate_production_settings'](configured), [])
            configured.sso_default_role = 'admin'
            self.assertTrue(any('SSO_CONFIGURATION_INVALID' in item for item in
                                ns['validate_production_settings'](configured)))

    def test_algorithm_kid_and_embedded_key_not_trusted(self):
        for algorithm, kid in [('HS256', 'key-a'), ('none', 'key-a'), ('RS256', '')]:
            with self.assertRaises(OIDC.OIDCError): OIDC.token_parts(jwt_text(self.claims, kid, algorithm))
        for key in ('jku', 'jwk', 'crit'):
            raw = dict(alg='RS256', kid='key-a', **{key: 'untrusted'})
            token = encoded(json.dumps(raw).encode()) + '.' + encoded(b'{}') + '.c2ln'
            with self.assertRaises(OIDC.OIDCError): OIDC.token_parts(token)

    def test_unknown_duplicate_symmetric_private_and_weak_jwks_deny(self):
        key = self.issuer.signer.public['key-a']
        for keys, kid in [([key], 'unknown'), ([key, key], 'key-a'),
            ([{**key, 'kty': 'oct'}], 'key-a'), ([{**key, 'use': 'enc'}], 'key-a'),
            ([{**key, 'd': 'private'}], 'key-a'), ([{**key, 'n': 'AQAB'}], 'key-a'),
            ([{**key, 'key_ops': ['sign']}], 'key-a')]:
            with self.assertRaises(OIDC.OIDCError): OIDC.select_key({'keys': keys}, kid)

    def test_issuer_audience_nonce_time_and_authorized_party(self):
        for change in ({'iss': 'https://other'}, {'aud': 'other'}, {'nonce': 'other'},
            {'exp': int(time.time()) - 60}, {'iat': int(time.time()) + 60}, {'iat': True},
            {'aud': ['reference-app', 'other']}, {'azp': 'other'}, {'sub': ['subject-a']}):
            with self.assertRaises(OIDC.OIDCError):
                OIDC.validate_claims({**self.claims, **change}, self.settings, 'n' * 43)
        self.assertEqual(OIDC.validate_claims({**self.claims, 'aud': ['reference-app', 'other'],
            'azp': 'reference-app'}, self.settings, 'n' * 43)['sub'], 'subject-a')

    def test_duplicate_json_and_exact_subject_boundaries(self):
        with self.assertRaises(OIDC.OIDCError): OIDC.strict_json(b'{"sub":"one","sub":"two"}')
        for sub in ('', 'x' * 256, 'bad\n', ['abc']):
            with self.assertRaises(OIDC.OIDCError): OIDC.exact_text(sub, 255)
        self.assertEqual(OIDC.exact_text(' Subject-A ', 255), ' Subject-A ')

    async def test_pyjwt_is_called_with_fixed_algorithm_and_required_claims(self):
        token = jwt_text(self.claims)
        decoder = Mock(return_value=self.claims)
        fake = NS(PyJWK=Mock(return_value=NS(key='PUBLIC_KEY_DOUBLE')), decode=decoder,
                  PyJWTError=type('FakeJWTError', (Exception,), {}))
        with patch.dict(sys.modules, {'jwt': fake}), patch.object(OIDC, 'fetch',
                AsyncMock(return_value={'keys': list(self.issuer.signer.public.values())})):
            await OIDC.verify(self.settings, token, 'n' * 43)
        self.assertEqual(decoder.call_args.kwargs['algorithms'], ['RS256'])
        self.assertIn('aud', decoder.call_args.kwargs['options']['require'])

    async def test_signature_exception_never_returns_claims(self):
        error = type('FakeJWTError', (Exception,), {})
        fake = NS(PyJWK=Mock(return_value=NS(key='PUBLIC')), decode=Mock(side_effect=error()),
                  PyJWTError=error)
        with patch.dict(sys.modules, {'jwt': fake}), patch.object(OIDC, 'fetch',
                AsyncMock(return_value={'keys': list(self.issuer.signer.public.values())})):
            with self.assertRaises(OIDC.OIDCError):
                await OIDC.verify(self.settings, jwt_text(self.claims), 'n' * 43)

    async def test_exchange_sends_bound_proof_no_extra_retry(self):
        fetch = AsyncMock(return_value={'id_token': 'synthetic'})
        with patch.object(OIDC, 'fetch', fetch):
            await OIDC.exchange(self.settings, 'code', 'v' * 43)
        self.assertEqual(fetch.await_args.args[2]['code_verifier'], 'v' * 43)
        self.assertEqual(fetch.await_count, 1)

    async def test_bounded_transport_no_redirect_or_post_retry(self):
        class Response:
            def __init__(self, status, raw):
                self.status_code, self.raw = status, raw
                self.headers = {'content-type': 'application/json'}
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def aiter_bytes(self): yield self.raw
        class Client:
            def __init__(self, responses): self.responses, self.calls = responses, []
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def stream(self, *args, **kwargs):
                self.calls.append((args, kwargs)); return self.responses.pop(0)
        for responses, form, expected in [([Response(307, b'{}')], None, 1),
            ([Response(503, b'{}')], {'code': 'secret'}, 1),
            ([Response(503, b'{}'), Response(200, b'{}')], None, 2),
            ([Response(200, b'x' * 65537)], None, 1)]:
            client = Client(responses); factory = Mock(return_value=client)
            fake = NS(AsyncClient=factory, HTTPError=type('HTTPError', (Exception,), {}))
            with patch.dict(sys.modules, {'httpx': fake}), patch.object(OIDC.ssl,
                    'create_default_context', return_value='TRUSTED_CA_DOUBLE'):
                try: await OIDC.fetch(self.settings, self.settings.sso_token_url, form)
                except OIDC.OIDCError: pass
            self.assertEqual(len(client.calls), expected)
            self.assertFalse(factory.call_args.kwargs['follow_redirects'])
            self.assertFalse(factory.call_args.kwargs['trust_env'])
            self.assertEqual(factory.call_args.kwargs['verify'], 'TRUSTED_CA_DOUBLE')


class MappingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(sys.modules, {'app.security.oidc': OIDC}))
        self.settings = settings()
        class Field:
            def __init__(self, name): self.name = name
            def __eq__(self, value): return self.name, value
        class User:
            sso_issuer = Field('issuer'); sso_subject = Field('subject'); username = Field('username')
            def __init__(self, **kwargs): self.__dict__.update(kwargs)
        class Role(Enum): SALESPERSON = 'salesperson'
        self.error = type('IntegrityError', (Exception,), {})
        self.issue = Mock(return_value='LOCAL_JWT_DOUBLE')
        self.ns = dict(get_settings=lambda: self.settings, User=User, AgentRole=Role,
            select=lambda model: NS(where=lambda *args: args), HTTPException=BASE['load'](
                'c19_http_errors', 'tests/test_runtime_authorization.py').HTTPException,
            IntegrityError=self.error, hash_password=lambda raw: 'RANDOM_HASH_DOUBLE',
            secrets=secrets, hashlib=hashlib, json=json, _issue_token=self.issue,
            get_audit_logger=lambda: NS(log=AsyncMock()), verify_password=Mock(return_value=False),
            Depends=lambda fn: None, get_db=Mock())
        nodes = []
        for node in ast.parse((ROOT / 'app/api/auth.py').read_text()).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                '_claim_text', '_find_or_provision_sso_user', 'login'}:
                node.decorator_list = []; nodes.append(ast.unparse(node))
        exec('from __future__ import annotations\n' + '\n'.join(nodes), self.ns)
        self.db = NS(execute=AsyncMock(side_effect=[NS(scalar_one_or_none=lambda: None)] * 2),
                     add=Mock(), commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())

    async def provision(self, **claims):
        return await self.ns['_find_or_provision_sso_user'](self.db,
            {'iss': self.settings.sso_issuer, 'sub': 'subject-a', **claims})

    async def test_first_user_ignores_remote_privilege_and_department(self):
        user, created = await self.provision(role='admin', department='dept_finance')
        self.assertTrue(created); self.assertEqual(user.role, 'salesperson')
        self.assertEqual(user.department, 'dept_sales')
        self.assertEqual(user.password_hash, 'RANDOM_HASH_DOUBLE')

    async def test_privileged_default_cannot_provision(self):
        self.settings.sso_default_role = 'manager'
        with self.assertRaises(self.ns['HTTPException']): await self.provision()
        self.db.add.assert_not_called()

    async def test_subject_is_not_truncated_or_coerced(self):
        for sub in ('x' * 256, ['same'], ''):
            with self.assertRaises(self.ns['HTTPException']): await self.provision(sub=sub)
        self.db.execute.assert_not_awaited()
        user, _ = await self.provision(sub=' Case-sensitive ')
        self.assertEqual(user.sso_subject, ' Case-sensitive ')
        self.assertIn(('subject', ' Case-sensitive '), self.db.execute.await_args_list[0].args[0])

    async def test_existing_identity_authority_retained_and_disabled_denied(self):
        existing = NS(is_active=True, role='manager', department='local')
        self.db.execute = AsyncMock(return_value=NS(scalar_one_or_none=lambda: existing))
        user, created = await self.provision(role='admin', department='remote')
        self.assertIs(user, existing); self.assertFalse(created)
        self.assertEqual(user.role, 'manager'); self.db.add.assert_not_called()
        existing.is_active = False
        with self.assertRaises(self.ns['HTTPException']): await self.provision()

    async def test_username_collision_does_not_link_local_user(self):
        self.db.execute = AsyncMock(side_effect=[NS(scalar_one_or_none=lambda: None),
                                                 NS(scalar_one_or_none=lambda: object())])
        user, created = await self.provision(preferred_username='same-name')
        self.assertTrue(created); self.assertTrue(user.username.startswith('same-name_'))
        self.assertEqual(user.sso_subject, 'subject-a')

    async def test_concurrent_provision_conflict_reloads_only_exact_identity(self):
        winner = NS(is_active=True)
        self.db.commit.side_effect = self.error()
        results = [None, None, winner]
        self.db.execute = AsyncMock(
            side_effect=lambda sql: NS(scalar_one_or_none=lambda: results.pop(0)))
        user, created = await self.provision()
        self.assertIs(user, winner); self.assertFalse(created)
        self.db.rollback.assert_awaited_once()

    async def test_sso_user_cannot_use_passwordless_dev_login(self):
        self.settings.auth_require_password = False
        user = NS(is_active=True, sso_subject='subject-a', password_hash='unknown')
        self.db.execute = AsyncMock(return_value=NS(scalar_one_or_none=lambda: user))
        with self.assertRaises(self.ns['HTTPException']):
            await self.ns['login'](NS(username='mapped', password='wrong'), self.db)
        self.issue.assert_not_called()


class FlowTests(BASE['CrossProcessStateFixture']):
    async def test_shared_state_pkce_consumed_once_and_old_state_not_accepted(self):
        state, nonce = await self.runtime_a.register_sso_state(verifier='v' * 43)
        binding = await self.runtime_b.consume_sso_state(state, with_verifier=True)
        self.assertEqual(binding, {'nonce': nonce, 'verifier': 'v' * 43})
        self.assertIsNone(await self.runtime_a.consume_sso_state(state, with_verifier=True))
        state, _ = await self.runtime_a.register_sso_state()
        self.assertIsNone(await self.runtime_b.consume_sso_state(state, with_verifier=True))

    async def test_actual_callback_with_independent_grant_and_injected_crypto(self):
        issuer = make(); self.addCleanup(issuer.db.close)
        ns = self.auth_functions(); ns['get_settings'] = settings
        login = await ns['sso_login']()
        params = parameters(urlsplit(login.kwargs['url']).query)
        rid, browser = issuer.authorize(params)
        grant_result = issuer.authenticate(dict(request_id=rid, username='alice',
            password='synthetic-password-a'), browser)
        async def exchange(code, verifier):
            return issuer.token(dict(code=code, code_verifier=verifier,
                client_id=issuer.config['client_id'], client_secret=issuer.config['client_secret'],
                redirect_uri=issuer.config['redirect_uri'], grant_type='authorization_code'))
        async def verify(token, nonce):
            # Explicit crypto double: actual binding/claims validation, no signature claim.
            _, claims = OIDC.token_parts(token)
            return OIDC.validate_claims(claims, settings(), nonce)
        ns['_exchange_sso_code'] = exchange; ns['_verify_id_token'] = verify
        state = params['state']; request = NS(cookies={'sso_state': state}, headers={})
        result = await ns['sso_callback'](request, code=grant_result['code'], state=state, db=None)
        self.assertEqual(result.status_code, 200)
        ns['_find_or_provision_sso_user'].assert_awaited_once()
        replay = await ns['sso_callback'](request, code=grant_result['code'], state=state, db=None)
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(len(issuer.signer.calls), 1)

    async def test_callback_bad_claim_stops_before_provision(self):
        ns = self.auth_functions()
        state, _ = await self.runtime_a.register_sso_state(verifier='v' * 43)
        ns['_verify_id_token'].side_effect = ns['HTTPException'](401, 'SSO_IDENTITY_INVALID')
        result = await ns['sso_callback'](NS(cookies={'sso_state': state}, headers={}),
                                         code='code', state=state, db=None)
        self.assertEqual(result.status_code, 401)
        ns['_find_or_provision_sso_user'].assert_not_awaited()
        ns['_issue_token'].assert_not_called()


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(cls(name) for cls in (IdpTests, RelyingPartyTests, MappingTests, FlowTests)
                              for name in cls.__dict__ if name.startswith('test_'))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    def guard(event, args):
        if event == 'sqlite3.connect' and args[0] != ':memory:':
            raise RuntimeError('OFFLINE_DATABASE_FILE_DENIED')
        if event == 'socket.__new__' and args[1] == 1: return
        if event.startswith(('socket.', 'subprocess.', 'ctypes.')) or event in {
            'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod', 'os.chown',
            'os.truncate', 'os.utime', 'os.link', 'os.symlink', 'os.exec', 'os.posix_spawn',
            'os.fork', 'os.forkpty', 'os.putenv', 'os.unsetenv'}:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                or isinstance(args[2], int) and args[2] & 3):
            raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
