"""C03 offline orchestration contracts; fake PostgreSQL is not SQL/runtime acceptance."""

from __future__ import annotations

import ast
from contextlib import asynccontextmanager, contextmanager, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    target = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(target)
    return target


def module(name: str, **attrs) -> ModuleType:
    result = ModuleType(name)
    result.__dict__.update(attrs)
    return result


contract = load('c03_contract', 'app/core/schema_contract.py')
with patch.dict(sys.modules, {'app.core.schema_contract': contract}):
    bootstrap = load('c03_bootstrap', 'app/core/db_bootstrap.py')


def columns(manifest, legacy=False):
    return [(table, name, value['type'], value.get('length'),
             'NO' if (table, name) == ('users', 'password_hash') else 'YES')
            for table, fields in manifest['legacy_columns' if legacy else 'columns'].items()
            for name, value in fields.items()]


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, manifest):
        self.manifest = manifest
        self.autocommit = True
        self.lock_available = True
        self.fail_sql = False
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.state = dict(tables=set(), history=[], columns=[], indexes=[], business=[],
                          admin=False, seed=None, schema_touched=False)

    @contextmanager
    def transaction(self):
        before = deepcopy(self.state)
        try:
            yield
        except BaseException:
            self.state = before
            self.rollbacks += 1
            raise
        else:
            self.commits += 1

    def execute(self, query, params=None, **kwargs):
        self.calls.append((query, params, kwargs))
        if query.startswith('SET '):
            return Cursor([])
        if 'pg_try_advisory_xact_lock' in query:
            return Cursor([(self.lock_available,)])
        if query == contract.TABLES_SQL:
            return Cursor([(table,) for table in self.state['tables']])
        if query == contract.HISTORY_SQL:
            return Cursor(list(self.state['history']))
        if query == contract.COLUMNS_SQL:
            return Cursor(list(self.state['columns']))
        if query == contract.INDEXES_SQL:
            return Cursor(list(self.state['indexes']))
        if query.startswith('SELECT to_regclass'):
            return Cursor([('schema_migrations' if 'schema_migrations' in self.state['tables'] else None,)])
        if query == bootstrap.LEDGER_SQL:
            self.state['tables'].add('schema_migrations')
        elif query == bootstrap.SEED_LEDGER_SQL:
            self.state['tables'].add('schema_bootstrap')
        elif query in [item['sql'] for item in self.manifest['migrations']]:
            self.state['schema_touched'] = True
            if self.fail_sql:
                raise RuntimeError('SYNTHETIC_PRIVATE_DATABASE_ERROR')
            self.state['tables'].update(self.manifest['columns'])
            self.state['columns'] = columns(self.manifest)
            self.state['indexes'] = list(self.manifest['indexes'].items())
        elif query.startswith('INSERT INTO public.schema_migrations'):
            self.state['history'].append(tuple(params))
        elif query.startswith('SELECT 1 FROM public.users WHERE'):
            return Cursor([(1,)] if self.state['admin'] else [])
        elif query.startswith('INSERT INTO public.users'):
            self.state['admin'] = True
            self.state['business'].append(tuple(params))
        elif query.startswith('SELECT checksum FROM public.schema_bootstrap'):
            return Cursor([(self.state['seed'],)] if self.state['seed'] else [])
        elif 'EXISTS(SELECT 1 FROM public.users)' in query:
            return Cursor([(bool(self.state['business']),)])
        elif query.startswith('SELECT set_config'):
            pass
        elif query == self.manifest['demo_seed']['sql']:
            self.state['business'].append('demo-fixture')
        elif query.startswith('INSERT INTO public.schema_bootstrap'):
            self.state['seed'] = params[1]
        else:
            raise AssertionError('Unexpected fake SQL path')
        return Cursor([])


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.manifest = contract.load_manifest()
        self.conn = FakeConnection(self.manifest)
        self.password_hash = '$2b$12$' + 'a' * 53  # format-only synthetic bcrypt fixture

    def test_empty_apply_and_repeat_preserve_rows(self):
        result = bootstrap.apply_migrations(self.conn, self.manifest)
        self.assertEqual(result['applied_versions'], [m['version'] for m in self.manifest['migrations']])
        self.assertFalse(self.conn.state['business'])
        self.conn.state['business'].append(('existing', 'unchanged'))
        count = sum(q == self.manifest['migrations'][0]['sql'] for q, _, _ in self.conn.calls)
        self.assertEqual(bootstrap.apply_migrations(self.conn, self.manifest)['applied_versions'], [])
        self.assertEqual(self.conn.state['business'], [('existing', 'unchanged')])
        self.assertEqual(sum(q == self.manifest['migrations'][0]['sql'] for q, _, _ in self.conn.calls), count)

    def test_pending_versions_are_applied_in_order(self):
        bootstrap.apply_migrations(self.conn, self.manifest)
        next_version = len(self.manifest['migrations']) + 1
        self.manifest['migrations'].append(dict(version=next_version, name='synthetic_upgrade',
                                               file='unused.sql', sha256='b' * 64,
                                               sql="SELECT 'synthetic upgrade'"))
        self.assertEqual(bootstrap.apply_migrations(self.conn, self.manifest)['applied_versions'], [next_version])
        self.assertEqual([row[0] for row in self.conn.state['history']], list(range(1, next_version + 1)))

    def test_statement_failure_rolls_back_schema_and_history_together(self):
        self.conn.state['business'] = ['preserved']
        before = deepcopy(self.conn.state)
        self.conn.fail_sql = True
        with self.assertRaises(RuntimeError):
            bootstrap.apply_migrations(self.conn, self.manifest)
        self.assertEqual(self.conn.state, before)
        self.assertEqual(self.conn.rollbacks, 1)
        self.assertEqual(self.conn.commits, 0)

    def test_lock_contention_stops_before_ddl(self):
        self.conn.lock_available = False
        with self.assertRaisesRegex(contract.SchemaError, '^DB_MIGRATION_BUSY$'):
            bootstrap.apply_migrations(self.conn, self.manifest)
        self.assertFalse(any('CREATE TABLE' in q for q, _, _ in self.conn.calls))

    def test_legacy_adoption_requires_explicit_flag_and_keeps_business_rows(self):
        self.conn.state['tables'] = set(self.manifest['legacy_columns'])
        self.conn.state['columns'] = columns(self.manifest, legacy=True)
        self.conn.state['business'] = [('legacy-user', 'unchanged-hash')]
        before = deepcopy(self.conn.state)
        with self.assertRaisesRegex(contract.SchemaError, 'DB_LEGACY_ADOPTION_REQUIRED'):
            bootstrap.apply_migrations(self.conn, self.manifest)
        self.assertEqual(self.conn.state, before)
        bootstrap.apply_migrations(self.conn, self.manifest, adopt_legacy=True)
        self.assertEqual(self.conn.state['business'], before['business'])

    def test_partial_legacy_schema_is_rejected(self):
        self.conn.state['tables'] = {'users'}
        self.conn.state['columns'] = [row for row in columns(self.manifest) if row[0] == 'users']
        with self.assertRaisesRegex(contract.SchemaError, 'DB_SCHEMA_SHAPE_MISMATCH'):
            bootstrap.apply_migrations(self.conn, self.manifest, adopt_legacy=True)
        self.assertFalse(self.conn.state['history'])

    def test_history_drift_unknown_and_missing_versions_are_rejected(self):
        item = self.manifest['migrations'][0]
        valid = (1, item['name'], item['sha256'])
        for rows in ([(1, item['name'], 'wrong')], [(2, item['name'], item['sha256'])],
                     [valid, (2, 'unknown', 'c' * 64)]):
            self.conn.state['tables'] = {'schema_migrations'}
            self.conn.state['history'] = rows
            with self.assertRaises(contract.SchemaError):
                bootstrap.apply_migrations(self.conn, self.manifest)
        with self.assertRaisesRegex(contract.SchemaError, 'DB_SCHEMA_PENDING'):
            contract.check_history([], self.manifest, current=True)

    def test_status_is_readonly_and_detects_removed_columns(self):
        bootstrap.apply_migrations(self.conn, self.manifest)
        self.conn.calls.clear()
        self.assertEqual(bootstrap.schema_status(self.conn, self.manifest)['status'], 'PASS')
        self.assertTrue(any(q == 'SET TRANSACTION READ ONLY' for q, _, _ in self.conn.calls))
        self.assertFalse(any(q.startswith(('INSERT', 'CREATE', 'ALTER')) for q, _, _ in self.conn.calls))
        self.conn.state['columns'].pop()
        with self.assertRaisesRegex(contract.SchemaError, 'DB_SCHEMA_SHAPE_MISMATCH'):
            bootstrap.schema_status(self.conn, self.manifest)

    def test_schema_type_index_and_password_nullability_drift_fail(self):
        for mutate in ('type', 'index', 'nullable'):
            bootstrap.apply_migrations(self.conn, self.manifest)
            if mutate == 'type':
                row = self.conn.state['columns'][0]
                self.conn.state['columns'][0] = (*row[:2], 'text', *row[3:])
            elif mutate == 'index':
                self.conn.state['indexes'] = []
            else:
                self.conn.state['columns'] = [(*r[:4], 'YES') if r[:2] == ('users', 'password_hash') else r
                                               for r in self.conn.state['columns']]
            with self.assertRaises(contract.SchemaError):
                bootstrap.schema_status(self.conn, self.manifest)
            self.conn = FakeConnection(self.manifest)

    def test_admin_creation_is_parameterized_and_never_resets_an_account(self):
        bootstrap.apply_migrations(self.conn, self.manifest)
        username = "O'Reilly; SELECT private"
        bootstrap.bootstrap_admin(self.conn, self.manifest, 'admin_test', username, self.password_hash)
        inserts = [(q, p) for q, p, _ in self.conn.calls if q.startswith('INSERT INTO public.users')]
        self.assertEqual(inserts[0][1][1], username)
        self.assertNotIn(username, inserts[0][0])
        before = deepcopy(self.conn.state)
        with self.assertRaisesRegex(contract.SchemaError, 'DB_ADMIN_ALREADY_EXISTS'):
            bootstrap.bootstrap_admin(self.conn, self.manifest, 'another', 'New', self.password_hash)
        self.assertEqual(self.conn.state, before)

    def test_admin_rejects_invalid_identifiers_or_hash(self):
        for user_id, username, password_hash in [('bad;sql', 'a', self.password_hash),
                                               ('a', '', self.password_hash), ('a', 'b', 'plaintext')]:
            with self.assertRaisesRegex(contract.SchemaError, 'DB_ADMIN_INPUT_INVALID'):
                bootstrap.bootstrap_admin(self.conn, self.manifest, user_id, username, password_hash)
        self.assertFalse(self.conn.calls)

    def test_seed_has_atomic_once_only_marker(self):
        bootstrap.apply_migrations(self.conn, self.manifest)
        self.assertTrue(bootstrap.seed_demo(self.conn, self.manifest, self.password_hash)['demo_seeded'])
        before = deepcopy(self.conn.state)
        self.assertFalse(bootstrap.seed_demo(self.conn, self.manifest, self.password_hash)['demo_seeded'])
        self.assertEqual(self.conn.state, before)
        self.conn.state['seed'] = 'wrong'
        with self.assertRaisesRegex(contract.SchemaError, 'DB_SEED_CHECKSUM_MISMATCH'):
            bootstrap.seed_demo(self.conn, self.manifest, self.password_hash)

    def test_seed_rejects_existing_data(self):
        bootstrap.apply_migrations(self.conn, self.manifest)
        self.conn.state['business'] = ['real-user']
        with self.assertRaisesRegex(contract.SchemaError, 'DB_DEMO_REQUIRES_EMPTY_DATASET'):
            bootstrap.seed_demo(self.conn, self.manifest, self.password_hash)

    def test_artifact_checksum_and_path_guards(self):
        with patch.object(Path, 'read_bytes', return_value=b'altered'):
            with self.assertRaisesRegex(contract.SchemaError, 'DB_MANIFEST_CHECKSUM_INVALID'):
                contract.load_manifest()
        for path in ('../outside.sql', '/outside.sql'):
            with self.assertRaisesRegex(contract.SchemaError, 'DB_MANIFEST_PATH_INVALID'):
                contract.read_artifact(contract.DEPLOY, path, 'a' * 64)
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaisesRegex(contract.SchemaError, 'DB_MANIFEST_PATH_INVALID'):
                contract.load_manifest()

    def test_offline_plan_and_missing_execute_do_not_load_driver(self):
        for args, code in ((['plan'], 0), (['apply'], 2), (['admin'], 2), (['demo'], 2)):
            with patch.dict(sys.modules, {'psycopg': None, 'app.config': None}), \
                    redirect_stdout(io.StringIO()) as out:
                self.assertEqual(bootstrap.main(args), code)
            self.assertNotIn('SYNTHETIC_SECRET', out.getvalue())

    def test_production_demo_and_weak_password_are_refused_before_connect(self):
        for app_env, allow, tools in [('prod', True, 'mock'), ('dev', False, 'mock'),
                                      ('dev', True, 'http')]:
            config = SimpleNamespace(app_env=app_env, tool_provider=tools, crm_tool_provider='',
                                     mail_tool_provider='', ticket_tool_provider='')
            driver = module('psycopg', connect=Mock(side_effect=AssertionError))
            deps = {'app.config': module('app.config', get_settings=lambda: config), 'psycopg': driver}
            args = ['demo', '--execute'] + (['--allow-demo'] if allow else [])
            with patch.dict(sys.modules, deps), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(bootstrap.main(args), 2)
            self.assertIn('DB_DEMO_NOT_ALLOWED', out.getvalue())
            driver.connect.assert_not_called()
        with patch.dict('os.environ', {'BOOTSTRAP_ADMIN_PASSWORD': 'short'}):
            with self.assertRaisesRegex(contract.SchemaError, 'DB_BOOTSTRAP_PASSWORD_INVALID'):
                bootstrap.password_from_env('BOOTSTRAP_ADMIN_PASSWORD')

    def test_default_artifacts_have_no_seed_mount_or_password_backfill(self):
        sql = self.manifest['migrations'][0]['sql']
        self.assertNotIn('INSERT INTO', sql)
        self.assertNotIn('UPDATE users', sql)
        self.assertIn("ERRCODE = 'PBA01'", sql)
        seed = self.manifest['demo_seed']['sql']
        self.assertNotIn('$2b$12$', seed)
        self.assertIn("current_setting('businessagent.demo_password_hash')", seed)
        self.assertEqual(seed.count('INSERT INTO'), 8)
        for path in ('docker-compose.yml', 'docker-compose.prod.yml'):
            self.assertNotIn('/docker-entrypoint-initdb.d/', (ROOT / path).read_text())
        for name in ('schema_manifest.json', 'demo_seed.sql'):
            self.assertIn('deploy/' + name, (ROOT / 'Dockerfile.prod').read_text())

    def test_cli_database_errors_never_print_credentials(self):
        config = SimpleNamespace(postgres_host='synthetic', postgres_port=5432,
                                 postgres_user='synthetic', postgres_password='SYNTHETIC_SECRET',
                                 postgres_db='synthetic')
        for sqlstate, code in [(None, 'DB_OPERATION_FAILED'), ('PBA01', 'DB_LEGACY_PASSWORD_MISSING')]:
            error = RuntimeError('SYNTHETIC_SECRET')
            error.sqlstate = sqlstate
            deps = {'app.config': module('app.config', get_settings=lambda: config),
                    'psycopg': module('psycopg', connect=Mock(side_effect=error))}
            with patch.dict(sys.modules, deps), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(bootstrap.main(['status']), 1)
            self.assertEqual(json.loads(out.getvalue()), {'status': 'FAIL', 'code': code})

    def test_password_byte_limit_and_missing_value(self):
        for value in ['', 'x' * 73, '密' * 25, ' ' * 16]:
            with patch.dict('os.environ', {'BOOTSTRAP_ADMIN_PASSWORD': value}):
                with self.assertRaisesRegex(contract.SchemaError, 'DB_BOOTSTRAP_PASSWORD_INVALID'):
                    bootstrap.password_from_env('BOOTSTRAP_ADMIN_PASSWORD')


class DatabaseStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_and_worker_stop_before_audit_or_queue_when_schema_fails(self):
        for source, name in [('app/main.py', 'lifespan'), ('app/worker.py', 'main')]:
            tree = ast.parse((ROOT / source).read_text())
            fn = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                      and node.name == name)
            settings = SimpleNamespace(app_env='dev', embedding_model='synthetic',
                                       reranker_model='synthetic')
            database = AsyncMock(side_effect=contract.SchemaError('DB_SCHEMA_STARTUP_FAILED'))
            namespace = dict(asynccontextmanager=asynccontextmanager, FastAPI=object,
                             get_settings=lambda: settings, logger=Mock(), init_db=database,
                             asyncio=__import__("asyncio"), close_db=AsyncMock(),
                             validate_production_settings=lambda config: [])
            exec(compile(ast.Module(body=[fn], type_ignores=[]), source, 'exec'), namespace)
            audit = Mock(side_effect=AssertionError('Audit must not start'))
            deps = {'app.rag.model_profile': module('app.rag.model_profile',
                                                   verify_model_startup=AsyncMock()),
                    'app.tools.base': module('app.tools.base', init_all_tools=Mock()),
                    'app.observability.tracing': module('app.observability.tracing',
                        init_tracing=lambda **kw: False, instrument_fastapi=Mock()),
                    'app.observability.audit': module('app.observability.audit',
                        init_audit_logger=audit, get_audit_logger=audit)}
            with patch.dict(sys.modules, deps):
                with self.assertRaisesRegex(RuntimeError,
                        '^DB_SCHEMA_STARTUP_FAILED$' if name == 'lifespan' else '^WORKER_FAILED$'):
                    if name == 'lifespan':
                        async with namespace[name](object()):
                            self.fail('API must not become ready')
                    else:
                        await namespace[name]()
            database.assert_awaited_once()
            audit.assert_not_called()
            if name == "main":
                namespace["close_db"].assert_awaited_once()

    async def test_failed_schema_check_does_not_publish_pool_and_health_is_safe(self):
        engine = Mock()
        engine.dispose = AsyncMock()
        transaction = Mock(__aenter__=AsyncMock(return_value=object()),
                           __aexit__=AsyncMock(return_value=False))
        engine.begin.return_value = transaction
        guard = AsyncMock(side_effect=contract.SchemaError('DB_SCHEMA_PENDING'))
        deps = {'app.config': module('app.config', get_settings=lambda: SimpleNamespace(
                    postgres_dsn='synthetic', is_dev=False)),
                'loguru': module('loguru', logger=Mock()),
                'sqlalchemy': module('sqlalchemy', text=lambda s: s),
                'app.core.schema_contract': module('app.core.schema_contract', SchemaError=contract.SchemaError,
                                                   verify_async_schema=guard),
                'sqlalchemy.ext.asyncio': module('sqlalchemy.ext.asyncio', AsyncEngine=object,
                    AsyncSession=object, async_sessionmaker=Mock(return_value='factory'),
                    create_async_engine=Mock(return_value=engine))}
        with patch.dict(sys.modules, deps):
            target = load('c03_database', 'app/core/database.py')
            with self.assertRaisesRegex(contract.SchemaError, '^DB_SCHEMA_STARTUP_FAILED$'):
                await target.init_db()
            self.assertIsNone(target._engine)
            self.assertIsNone(target._session_factory)
            engine.dispose.assert_awaited_once()
            guard.side_effect = None
            await target.init_db()
            self.assertEqual(target.get_session_factory(), 'factory')
            guard.side_effect = RuntimeError('SYNTHETIC_SECRET')
            self.assertEqual(await target.check_db_health(),
                             {'status': 'unhealthy', 'reason': 'DB_SCHEMA_UNAVAILABLE'})

    async def test_async_schema_contract_checks_lock_history_and_structure(self):
        manifest = contract.load_manifest()
        item = manifest['migrations'][0]
        connection = SimpleNamespace(execute=AsyncMock(side_effect=[
            Mock(scalar=lambda: True), Cursor([(m['version'], m['name'], m['sha256']) for m in manifest['migrations']]),
            Cursor(columns(manifest)), Cursor(list(manifest['indexes'].items()))]))
        await contract.verify_async_schema(connection, lambda s: s)
        connection.execute = AsyncMock(return_value=Mock(scalar=lambda: False))
        with self.assertRaisesRegex(contract.SchemaError, 'DB_MIGRATION_BUSY'):
            await contract.verify_async_schema(connection, lambda s: s)
        self.assertEqual(connection.execute.await_count, 1)


if __name__ == '__main__':
    def offline_guard(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.bind',
                     'os.remove', 'os.rmdir', 'os.rename'):
            raise RuntimeError('OFFLINE_TEST_SIDE_EFFECT_DENIED')
    sys.addaudithook(offline_guard)
    unittest.main(verbosity=2)
