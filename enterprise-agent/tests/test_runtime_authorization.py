"""C05 offline source execution; injected dependencies are not JWT/HTTP/SQL acceptance."""

from __future__ import annotations

import ast
from contextlib import ExitStack, asynccontextmanager
from copy import deepcopy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Optional
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, **attrs: Any) -> ModuleType:
    result = ModuleType(name)
    result.__dict__.update(attrs)
    return result


def load(name: str, path: str) -> ModuleType:
    result = module(name)
    source = ROOT / path
    result.__file__ = str(source)
    exec(compile(source.read_bytes(), str(source), 'exec'), result.__dict__)
    return result


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str, headers: Any = None) -> None:
        super().__init__(detail)
        self.status_code, self.detail, self.headers = status_code, detail, headers


class Model:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class Router:
    def get(self, *args: Any, **kwargs: Any) -> Any:
        return lambda fn: fn

    post = get


class Mapped:
    def __class_getitem__(cls, value: Any) -> Any:
        return Any


class TokenError(Exception):
    pass


class ExpiredToken(TokenError):
    pass


class Database:
    def __init__(self) -> None:
        self.users = {
            'requester': Model(username='Requester', role='salesperson',
                               department='dept_sales', is_active=True),
            'approver': Model(username='Approver', role='manager',
                              department='dept_sales', is_active=True),
        }
        self.row = Model(approval_id='a1', session_id='s1', requester_id='requester',
                         requester_token='valid', approver_id='approver',
                         approver_roles=['manager'], status='pending',
                         prefill_payload={'tool_calls': [{'tool': 'send_email_external'}]})
        self.queries: list[tuple[str, dict]] = []
        self.writes: list[tuple[str, dict]] = []
        self.fail_users = False
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> Database:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def execute(self, sql: str, params: dict) -> Any:
        self.queries.append((sql, deepcopy(params)))
        if 'FROM users' in sql:
            if self.fail_users:
                raise RuntimeError('SYNTHETIC_PRIVATE_DATABASE_SECRET')
            assert 'WHERE user_id = :uid' in sql
            row = deepcopy(self.users.get(params['uid']))
        elif 'FROM approval_requests' in sql:
            assert 'WHERE approval_id = :id' in sql
            assert 'requester_token' not in sql
            row = deepcopy(self.row)
        elif sql.startswith('UPDATE approval_requests'):
            self.writes.append((sql, deepcopy(params)))
            row = None
        else:
            raise AssertionError('Unexpected SQL')
        return SimpleNamespace(fetchone=lambda: row)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class RuntimeAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.db = Database()
        self.settings = SimpleNamespace(jwt_secret_key='synthetic-key-only', jwt_algorithm='HS256',
            auth_check_db=True, auth_require_password=True, is_dev=False, app_env='prod')
        self.tokens = {
            'valid': {'sub': 'requester', 'exp': 4102444800, 'role': 'admin'},
            'expired': {'sub': 'requester', 'exp': 1},
            'other': {'sub': 'other', 'exp': 4102444800},
            'refreshed': {'sub': 'requester', 'exp': 4102444800},
        }
        self.logger = Mock()
        self.audit = SimpleNamespace(log=AsyncMock(), log_violation=AsyncMock())
        self.notify = AsyncMock()
        self.execute = AsyncMock(return_value=Model(success=True, output={'synthetic': True}))
        self.jwt_manager = SimpleNamespace(
            is_expired=lambda token: token == 'expired',
            refresh_if_needed=AsyncMock(return_value='refreshed'))
        self.decode = Mock(side_effect=self.decode_fixture)
        deps = {
            'jwt': module('jwt', decode=self.decode, PyJWTError=TokenError,
                          ExpiredSignatureError=ExpiredToken),
            'fastapi': module('fastapi', Depends=lambda dependency: None, APIRouter=Router,
                              HTTPException=HTTPException, status=SimpleNamespace()),
            'fastapi.security': module('fastapi.security', HTTPAuthorizationCredentials=Model,
                                       HTTPBearer=lambda **kw: None),
            'loguru': module('loguru', logger=self.logger),
            'pydantic': module('pydantic', BaseModel=Model, Field=lambda default=None, **kw: default),
            'sqlalchemy': module('sqlalchemy', text=lambda value: value, select=Mock(),
                                 Boolean=Mock(), Column=Mock(), DateTime=Mock(), String=Mock()),
            'sqlalchemy.orm': module('sqlalchemy.orm', DeclarativeBase=Model, Mapped=Mapped,
                                     mapped_column=lambda *args, **kw: None),
            'app.config': module('app.config', get_settings=lambda: self.settings),
            'app.core.database': module('app.core.database', get_session_factory=lambda: lambda: self.db,
                                        get_db=Mock()),
            'app.core.approval_notify': module('app.core.approval_notify',
                                              notify_approval_result=self.notify),
            'app.observability.audit': module('app.observability.audit', get_audit_logger=lambda: self.audit),
            'app.security.jwt_manager': module('app.security.jwt_manager',
                                               get_jwt_manager=lambda: self.jwt_manager),
            'app.agents.execution': module('app.agents.execution', ToolCallPlan=Model,
                                           execute_tool_calls=self.execute),
        }
        self.stack.enter_context(patch.dict(sys.modules, deps))
        self.rbac = load('c05_rbac', 'app/security/rbac.py')
        self.stack.enter_context(patch.dict(sys.modules, {'app.security.rbac': self.rbac}))
        self.approval = load('c05_approval', 'app/api/approval.py')

    def decode_fixture(self, token: str, key: str, *, algorithms: list, options: dict) -> dict:
        # A branch-driving fixture, NOT a signature implementation or a PyJWT substitute.
        self.assertEqual(key, self.settings.jwt_secret_key)
        self.assertEqual(algorithms, ['HS256'])
        self.assertEqual(options['require'], ['sub', 'exp'])
        if token not in self.tokens:
            raise TokenError('SYNTHETIC_PRIVATE_TOKEN')
        payload = deepcopy(self.tokens[token])
        if any(claim not in payload for claim in options['require']):
            raise TokenError('missing claim')
        if token == 'expired' and options['verify_exp']:
            raise ExpiredToken()
        return payload

    @staticmethod
    def credentials(token: str = 'valid') -> Model:
        return Model(scheme='Bearer', credentials=token)

    async def call(self, path: str = 'decide', decision: str = 'approved') -> Any:
        approver = Model(user_id='approver', role='admin')  # Deliberately stale elevated role.
        if path == 'decide':
            return await self.approval.decide_approval('a1', Model(decision=decision, comment=''),
                                                       approver=approver, db=self.db)
        if path == 'resume':
            self.db.row.status = 'approved_pending_reauth'
            return await self.approval.resume_pending_execution('a1',
                requester=Model(user_id='requester'), credentials=self.credentials(), db=self.db)
        return await self.approval.batch_decide_approvals(
            Model(approvals=[Model(approval_id='a1', decision=decision)], comment=''),
            approver=approver, db=self.db)

    def assert_no_effects(self) -> None:
        self.assertEqual(self.db.writes, [])
        self.execute.assert_not_awaited()
        self.notify.assert_not_awaited()

    async def denied(self, path: str, code: int) -> None:
        if path == 'batch':
            result = await self.call(path)
            self.assertEqual((result.succeeded, result.failed), (0, 1))
            self.assertEqual(result.results[0]['status_code'], code)
        else:
            with self.assertRaises(HTTPException) as caught:
                await self.call(path)
            self.assertEqual(caught.exception.status_code, code)
            self.audit.log.assert_not_awaited()
        self.assert_no_effects()

    async def test_identity_outage_denies_and_recovery_uses_current_role(self) -> None:
        self.db.fail_users = True
        with self.assertRaises(HTTPException) as caught:
            await self.rbac.get_current_user(self.credentials())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn('SECRET', str(caught.exception) + str(self.logger.mock_calls))
        self.db.fail_users = False
        user = await self.rbac.get_current_user(self.credentials())
        self.assertEqual(user.role, 'salesperson')
        self.assert_no_effects()

    async def test_identity_factory_failure_is_sanitized(self) -> None:
        with patch.object(sys.modules['app.core.database'], 'get_session_factory',
                          side_effect=RuntimeError('SYNTHETIC_PRIVATE_DATABASE_SECRET')):
            with self.assertRaises(HTTPException) as caught:
                await self.rbac.get_current_user(self.credentials())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn('SECRET', str(caught.exception) + str(self.logger.mock_calls))

    async def test_missing_disabled_and_invalid_role_accounts_deny(self) -> None:
        for state in ('missing', 'disabled', 'invalid', 'empty'):
            with self.subTest(state=state):
                self.db.users['requester'] = Model(username='R', role='salesperson',
                    department=None, is_active=state != 'disabled')
                if state == 'missing':
                    self.db.users.pop('requester')
                elif state in ('invalid', 'empty'):
                    self.db.users['requester'].role = 'unknown' if state == 'invalid' else None
                with self.assertRaises(HTTPException) as caught:
                    await self.rbac.get_current_user(self.credentials())
                self.assertEqual(caught.exception.status_code, 401)

    async def test_invalid_tokens_and_claims_deny_before_database(self) -> None:
        for payload in ({'exp': 9}, {'sub': 'requester'}, {'sub': '', 'exp': 9},
                        {'sub': [], 'exp': 9}, {'sub': 'x' * 65, 'exp': 9},
                        {'sub': 'r', 'exp': '9'}, {'sub': 'r', 'exp': True},
                        {'sub': 'r', 'exp': float('nan')}, {'sub': 'r', 'exp': float('inf')}):
            self.tokens['malformed'] = payload
            with self.assertRaises(HTTPException) as caught:
                await self.rbac.get_current_user(self.credentials('malformed'))
            self.assertEqual(caught.exception.status_code, 401)
        for token in ('expired', 'forged', ''):
            with self.assertRaises(HTTPException) as caught:
                await self.rbac.get_current_user(self.credentials(token))
            self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(self.db.queries, [])

    async def test_missing_or_wrong_scheme_credentials_deny(self) -> None:
        for credentials in (None, Model(scheme='Basic', credentials='valid')):
            with self.assertRaises(HTTPException) as caught:
                await self.rbac.get_current_user(credentials)
            self.assertEqual(caught.exception.status_code, 401)

    async def test_token_only_is_explicitly_development_only(self) -> None:
        self.settings.auth_check_db = False
        with self.assertRaises(HTTPException) as caught:
            await self.rbac.get_current_user(self.credentials())
        self.assertEqual(caught.exception.status_code, 503)
        self.settings.is_dev = True
        self.assertEqual((await self.rbac.get_current_user(self.credentials())).role, 'admin')
        self.assertEqual(self.db.queries, [])

    async def test_approval_outage_denies_every_execution_entry(self) -> None:
        self.db.fail_users = True
        for path in ('decide', 'resume', 'batch'):
            self.db.row.status = 'pending'
            with self.subTest(path=path):
                await self.denied(path, 503)

    async def test_each_participant_revocation_denies_every_entry(self) -> None:
        original = deepcopy(self.db.users)
        for path in ('decide', 'resume', 'batch'):
            for participant in ('requester', 'approver'):
                for state in ('missing', 'disabled', 'invalid-role'):
                    with self.subTest(path=path, participant=participant, state=state):
                        self.db.users = deepcopy(original)
                        self.db.row.status = 'pending'
                        if state == 'missing':
                            self.db.users.pop(participant)
                        elif state == 'disabled':
                            self.db.users[participant].is_active = False
                        else:
                            self.db.users[participant].role = 'unknown'
                        await self.denied(path, 401)

    async def test_current_roles_override_stale_request_and_token_roles(self) -> None:
        for path in ('decide', 'resume', 'batch'):
            for participant in ('requester', 'approver'):
                self.db.users['requester'].role = 'salesperson'
                self.db.users['approver'].role = 'manager'
                self.db.users[participant].role = 'finance'
                self.db.row.status = 'pending'
                with self.subTest(path=path, participant=participant):
                    await self.denied(path, 403)

    async def test_legacy_tokens_are_ignored_by_decisions(self) -> None:
        for path in ('decide', 'batch'):
            for token in ('other', 'forged', 'expired', 'valid'):
                self.db.row.requester_token = token
                self.db.row.status = 'pending'
                await self.call(path)
        self.execute.assert_not_awaited()
        self.decode.assert_not_called()
        self.assertTrue(all('requester_token' not in sql for sql, _ in self.db.queries))

    async def test_resume_requires_bearer_and_rejects_expired_or_wrong_subject(self) -> None:
        self.db.row.status = 'approved_pending_reauth'
        for credentials in (None, Model(scheme='Basic', credentials='valid'),
                            self.credentials('other'), self.credentials('expired'),
                            self.credentials('forged')):
            with self.assertRaises(HTTPException) as caught:
                await self.approval.resume_pending_execution('a1',
                    requester=Model(user_id='requester'), credentials=credentials, db=self.db)
            self.assertEqual(caught.exception.status_code, 401)
            self.assert_no_effects()

    async def test_resume_missing_original_approver_denies(self) -> None:
        self.db.row.approver_id = None
        await self.denied('resume', 403)

    async def test_unknown_tool_or_malformed_payload_denies(self) -> None:
        for payload, code in (({'tool_calls': [{'tool': 'unknown'}]}, 403),
                              ({'tool_calls': []}, 400), ('broken-json', 400),
                              ({'tool_calls': [{'tool': 'query_order', 'params': []}]}, 400)):
            self.db.row.prefill_payload = payload
            await self.denied('decide', code)

    async def test_invalid_approval_roles_deny_even_administrator(self) -> None:
        self.db.users['approver'].role = 'admin'
        for roles in ([], 'manager', ['unknown'], [['manager']]):
            self.db.row.approver_roles = roles
            await self.denied('decide', 403)

    async def test_expired_or_missing_stored_token_only_enters_reauth(self) -> None:
        for token in ('expired', ''):
            self.db.row.requester_token = token
            result = await self.call()
            self.assertEqual(result.status, 'approved_pending_reauth')
            self.execute.assert_not_awaited()
        self.assertTrue(all('approved_pending_reauth' in sql for sql, _ in self.db.writes))

    async def test_expired_token_does_not_bypass_revoked_requester(self) -> None:
        self.db.row.requester_token = 'expired'
        self.db.users['requester'].is_active = False
        await self.denied('decide', 401)

    async def test_approval_does_not_refresh_or_use_stored_credentials(self) -> None:
        self.jwt_manager.refresh_if_needed.side_effect = AssertionError('Must not refresh')
        result = await self.call()
        self.assertEqual(result.status, 'approved_pending_reauth')
        self.jwt_manager.refresh_if_needed.assert_not_awaited()
        self.execute.assert_not_awaited()

    async def test_resume_executes_identity_only_context(self) -> None:
        result = await self.call('resume')
        self.assertEqual(result.status, 'executed')
        context = self.execute.await_args.args[1]
        self.assertNotIn('jwt_token', context)
        self.assertEqual((context['user_id'], context['role'], context['dept']),
                         ('requester', 'salesperson', 'dept_sales'))
        queries = [(sql, params['uid']) for sql, params in self.db.queries if 'FROM users' in sql]
        self.assertEqual([uid for _, uid in queries], ['approver', 'requester'])
        self.assertTrue(all('FOR SHARE' in sql for sql, _ in queries))

    async def test_decision_records_auditable_confirmation_requirement(self) -> None:
        await self.call()
        payload = self.audit.log.await_args.kwargs['payload']
        self.assertEqual(payload['decided_by'], 'approver')
        self.assertEqual(payload['execution_authorization'], 'requester_confirmation_required')
        self.execute.assert_not_awaited()

    async def test_revocation_after_approval_prevents_later_resume(self) -> None:
        await self.call()
        self.db.writes.clear()
        self.audit.log.reset_mock()
        self.notify.reset_mock()
        self.db.users['approver'].role = 'finance'
        await self.denied('resume', 403)

    async def test_valid_resume_rechecks_original_approver(self) -> None:
        result = await self.call('resume')
        self.assertEqual(result.status, 'executed')
        self.assertNotIn('jwt_token', self.execute.await_args.args[1])
        self.assertTrue(all('token' not in params for _, params in self.db.writes))
        self.assertEqual(self.audit.log.await_args.kwargs['payload']['decided_by'], 'approver')

    async def test_valid_batch_only_records_approval(self) -> None:
        result = await self.call('batch')
        self.assertEqual((result.succeeded, result.failed), (1, 0))
        self.execute.assert_not_awaited()
        self.assertEqual(result.results[0]['new_status'], 'approved_pending_reauth')

    async def test_development_bypass_does_not_apply_to_approvals(self) -> None:
        self.settings.auth_check_db = False
        self.settings.is_dev = True
        self.db.fail_users = True
        await self.denied('decide', 503)

    async def test_rejection_rechecks_approver_but_needs_no_requester_token(self) -> None:
        self.db.row.requester_token = 'forged'
        result = await self.call(decision='rejected')
        self.assertEqual(result.status, 'rejected')
        self.execute.assert_not_awaited()


class ConfigurationTests(unittest.IsolatedAsyncioTestCase):
    def validator(self) -> Any:
        source = ROOT / 'app/config.py'
        tree = ast.parse(source.read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == 'validate_production_settings']
        nodes += [n for n in tree.body if isinstance(n, ast.AnnAssign)
                  and isinstance(n.target, ast.Name) and n.target.id == '_DEFAULT_SECRETS']
        namespace = {'Optional': Optional, 'Settings': Any}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
        return namespace['validate_production_settings']

    def config(self, **changes: Any) -> Any:
        values = dict(is_dev=False, app_env='prod', auth_require_password=True, auth_check_db=True,
                      jwt_secret_key='synthetic-only-' * 4, postgres_password='synthetic-pg',
                      redis_password='synthetic-redis', milvus_password='synthetic-milvus',
                      cors_allow_origins='https://synthetic.invalid', crm_tool_provider='mock',
                      mail_tool_provider='mock', ticket_tool_provider='mock', sso_enabled=False)
        values.update(changes)
        return SimpleNamespace(**values)

    def test_both_auth_flags_required_in_production(self) -> None:
        validate = self.validator()
        self.assertEqual(validate(self.config()), [])
        for flag in ('auth_require_password', 'auth_check_db'):
            self.assertTrue(any(flag.upper() in v for v in validate(self.config(**{flag: False}))))
        self.assertEqual(validate(self.config(is_dev=True, auth_require_password=False,
                                             auth_check_db=False)), [])

    async def test_api_and_worker_reject_flags_before_external_initialization(self) -> None:
        validate = self.validator()
        for path, entry in (('app/main.py', 'lifespan'), ('app/worker.py', 'main')):
            for flag in ('auth_require_password', 'auth_check_db'):
                with self.subTest(path=path, flag=flag):
                    config = self.config(**{flag: False})
                    init_db = AsyncMock()
                    model = AsyncMock()
                    namespace = dict(asynccontextmanager=asynccontextmanager, FastAPI=Any,
                        get_settings=lambda: config, validate_production_settings=validate,
                        logger=Mock(), init_db=init_db)
                    source = ROOT / path
                    tree = ast.parse(source.read_text())
                    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                                and n.name == entry)
                    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
                    deps = {'app.config': module('app.config', validate_production_settings=validate),
                            'app.rag.model_profile': module('app.rag.model_profile', verify_model_startup=model)}
                    with patch.dict(sys.modules, deps), self.assertRaises(RuntimeError):
                        if entry == 'lifespan':
                            async with namespace[entry](None):
                                self.fail('Startup unexpectedly continued')
                        else:
                            await namespace[entry]()
                    init_db.assert_not_awaited()
                    model.assert_not_awaited()

    def test_production_compose_pins_both_flags(self) -> None:
        source = (ROOT / 'docker-compose.prod.yml').read_text()
        self.assertEqual(source.count('AUTH_REQUIRE_PASSWORD: "true"'), 2)
        self.assertEqual(source.count('AUTH_CHECK_DB: "true"'), 2)


if __name__ == '__main__':
    sys.dont_write_bytecode = True

    def guard(event: str, args: tuple[Any, ...]) -> None:
        # asyncio creates AF_UNIX socketpairs for its local wakeup pipe.
        if event == 'socket.__new__' and args[1] == 1:
            return
        if event.startswith(('socket.', 'subprocess.')) or event in {
            'os.remove', 'os.rmdir', 'os.rename', 'os.system', 'os.mkdir', 'os.chmod',
        }:
            raise RuntimeError('Offline suite prohibited side effect')
        if event == 'open' and (isinstance(args[1], str) and any(c in args[1] for c in 'wax+')
                                or isinstance(args[2], int) and args[2] & 3):
            raise RuntimeError('Offline suite prohibited file write')

    sys.addaudithook(guard)
    unittest.main(verbosity=2)
