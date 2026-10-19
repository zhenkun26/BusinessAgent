"""Retained reference ledger. Business effects and terminal receipts share one transaction."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator
from uuid import uuid4 as new_uuid

from reference_service.contract import (
    SCHEMA, Rejected, Response, canonical, fields, fingerprint, fixture, identifier, now,
    precondition, uuid4,
)

DDL = '''
CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), service TEXT NOT NULL,
                       schema_version TEXT NOT NULL, store_id TEXT NOT NULL);
CREATE TABLE runs (run_id TEXT PRIMARY KEY, principal TEXT NOT NULL, data TEXT NOT NULL,
                   fixture_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE resources (run_id TEXT NOT NULL, kind TEXT NOT NULL, resource_id TEXT NOT NULL,
                        data TEXT NOT NULL, PRIMARY KEY(run_id,kind,resource_id));
CREATE TABLE operations (run_id TEXT NOT NULL, principal TEXT NOT NULL, operation_id TEXT NOT NULL,
    request_hash TEXT NOT NULL, request TEXT NOT NULL, state TEXT NOT NULL,
    receipt TEXT NOT NULL, status INTEGER, result TEXT, PRIMARY KEY(run_id,principal,operation_id));
CREATE TABLE attempts (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, principal TEXT NOT NULL,
    operation_id TEXT, request_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
    phase TEXT NOT NULL, status INTEGER NOT NULL, observed_at TEXT NOT NULL);
CREATE TABLE faults (run_id TEXT NOT NULL, operation_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
    phase TEXT NOT NULL, mode TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(run_id,operation_id,ordinal,phase));
'''


class Store:
    def __init__(self, db: sqlite3.Connection, service: str, store_id: str,
                 *, initialize: bool = False) -> None:
        self.db = db
        self.service = service
        self.store_id = uuid4(store_id)
        self.lock = threading.RLock()
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('PRAGMA temp_store=MEMORY')
        self.db.execute('PRAGMA journal_mode=PERSIST')
        self.db.execute('PRAGMA synchronous=FULL')
        if service not in {'crm', 'ticket', 'mail'}:
            raise ValueError('REFERENCE_SERVICE_INVALID')
        if initialize:
            if self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                raise ValueError('REFERENCE_STORE_ALREADY_EXISTS')
            self.db.executescript(DDL)
            self.db.execute('INSERT INTO metadata VALUES (1,?,?,?)', (service, SCHEMA, store_id))
        row = self.db.execute('SELECT * FROM metadata WHERE id=1').fetchone()
        if (row is None or (row['service'], row['schema_version'], row['store_id']) !=
                (service, SCHEMA, store_id) or
                self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok'):
            raise ValueError('REFERENCE_STORE_IDENTITY_INVALID')
        # Do not adopt an incompatible/partial schema or recreate it at startup.
        for name in ('runs', 'resources', 'operations', 'attempts', 'faults'):
            self.db.execute(f'SELECT * FROM {name} LIMIT 0')  # Only static names enter SQL.

    @classmethod
    def open(cls, path: Path, service: str, store_id: str,
             *, initialize: bool = False) -> Store:
        if (not path.is_absolute() or path.is_symlink() or not path.parent.is_dir()
                or any(parent.is_symlink() for parent in path.parents)
                or path.exists() == initialize):
            raise ValueError('REFERENCE_STORE_PATH_INVALID')
        uri = path.as_uri() + ('?mode=rwc' if initialize else '?mode=rw')
        db = sqlite3.connect(uri, uri=True, isolation_level=None, check_same_thread=False)
        try:
            return cls(db, service, store_id, initialize=initialize)
        except Exception:
            db.close()
            raise

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def run(self, run_id: str, principal: str | None = None) -> dict[str, Any]:
        row = self.db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
        if row is None or principal is not None and row['principal'] != principal:
            raise Rejected(404, 'NOT_FOUND')
        return {**dict(row), 'data': json.loads(row['data'])}

    def provision(self, body: dict[str, Any]) -> dict[str, Any]:
        fields(body, {'run_id', 'principal', 'users', 'fixture', 'external_recall_supported'},
               {'run_id', 'principal', 'users', 'fixture'})
        run_id, principal = uuid4(body['run_id']), identifier(body['principal'])
        users = body['users']
        if (not isinstance(users, list) or not 1 <= len(users) <= 20
                or any(not isinstance(user, str) for user in users)):
            raise Rejected(422, 'INVALID_USERS')
        for user in users:
            identifier(user)
        if len(set(users)) != len(users):
            raise Rejected(422, 'INVALID_USERS')
        supported = body.get('external_recall_supported', True)
        if type(supported) is not bool:
            raise Rejected(422, 'INVALID_FIELD')
        data = {**fixture(body['fixture']), 'users': users,
                'external_recall_supported': supported}
        with self.transaction():
            if self.db.execute('SELECT 1 FROM runs WHERE run_id=?', (run_id,)).fetchone():
                raise Rejected(409, 'RUN_EXISTS')
            stamp = now()
            self.db.execute('INSERT INTO runs VALUES (?,?,?,?,?)',
                            (run_id, principal, canonical(data), fingerprint(data), stamp))
            for kind in ('customers', 'orders'):
                key = 'customer_id' if kind == 'customers' else 'order_id'
                for row in data[kind]:
                    self.put(run_id, kind, row[key], row)
        return {'run_id': run_id, 'fixture_hash': fingerprint(data), 'created_at': stamp,
                'store_id': self.store_id, 'schema': SCHEMA}

    def get(self, run_id: str, kind: str, rid: str) -> dict[str, Any]:
        row = self.db.execute('SELECT data FROM resources WHERE run_id=? AND kind=? AND resource_id=?',
                              (run_id, kind, rid)).fetchone()
        if row is None:
            raise Rejected(404, 'NOT_FOUND')
        return json.loads(row['data'])

    def put(self, run_id: str, kind: str, rid: str, value: dict[str, Any]) -> None:
        self.db.execute('''INSERT INTO resources VALUES (?,?,?,?)
            ON CONFLICT(run_id,kind,resource_id) DO UPDATE SET data=excluded.data''',
            (run_id, kind, rid, canonical(value)))

    def operation(self, run_id: str, principal: str, oid: str) -> sqlite3.Row | None:
        return self.db.execute('''SELECT * FROM operations
            WHERE run_id=? AND principal=? AND operation_id=?''', (run_id, principal, oid)).fetchone()

    def install_fault(self, run_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self.run(run_id)
        fields(body, {'operation_id', 'attempt', 'phase', 'mode'},
               {'operation_id', 'attempt', 'phase', 'mode'})
        oid = uuid4(body['operation_id'])
        ordinal, phase, mode = body['attempt'], body['phase'], body['mode']
        modes = {'before_commit': {'503', '429', 'drop', 'delay', 'pending'},
                 'after_commit': {'503', '429', 'drop', 'delay', 'malformed', 'wrong_receipt',
                                  'redirect'}}
        if (type(ordinal) is not int or not 1 <= ordinal <= 100 or not isinstance(phase, str)
                or phase not in modes or not isinstance(mode, str) or mode not in modes[phase]):
            raise Rejected(422, 'INVALID_FAULT')
        with self.transaction():
            if self.db.execute('''SELECT 1 FROM faults
                WHERE run_id=? AND operation_id=? AND ordinal=? AND phase=?''',
                (run_id, oid, ordinal, phase)).fetchone():
                raise Rejected(409, 'FAULT_EXISTS')
            self.db.execute('INSERT INTO faults VALUES (?,?,?,?,?,0)',
                            (run_id, oid, ordinal, phase, mode))
        return {'installed': True, **body}

    def fault(self, run_id: str, oid: str, ordinal: int, phase: str) -> str | None:
        args = (run_id, oid, ordinal, phase)
        row = self.db.execute('''SELECT mode FROM faults WHERE run_id=? AND operation_id=?
            AND ordinal=? AND phase=? AND consumed=0''', args).fetchone()
        if row is None:
            return None
        self.db.execute('''UPDATE faults SET consumed=1 WHERE run_id=? AND operation_id=?
            AND ordinal=? AND phase=?''', args)
        return row['mode']

    def attempt(self, run_id: str, principal: str, oid: str | None, request_id: str,
                ordinal: int, phase: str, status: int) -> None:
        self.db.execute('INSERT INTO attempts VALUES (NULL,?,?,?,?,?,?,?,?)',
                        (run_id, principal, oid, request_id, ordinal, phase, status, now()))

    def mutate(self, run_id: str, principal: str, oid: str, request_id: str,
               request: dict[str, Any]) -> Response:
        data = self.run(run_id, principal)['data']
        request_hash = fingerprint(request)
        with self.transaction():
            old = self.operation(run_id, principal, oid)
            ordinal = self.db.execute('''SELECT count(*) FROM attempts
                WHERE run_id=? AND principal=? AND operation_id=? AND phase='received' ''',
                (run_id, principal, oid)).fetchone()[0] + 1
            self.attempt(run_id, principal, oid, request_id, ordinal, 'received', 0)
            if old is not None:
                if old['request_hash'] != request_hash:
                    self.attempt(run_id, principal, oid, request_id, ordinal, 'conflict', 409)
                    return Response(409, {'error': {'code': 'IDEMPOTENCY_CONFLICT',
                                                   'operation_id': oid}})
                if old['state'] != 'pending':
                    self.attempt(run_id, principal, oid, request_id, ordinal, 'replayed', old['status'])
                    return Response(old['status'], json.loads(old['result']),
                                    {'Idempotency-Replayed': 'true'})
                receipt = json.loads(old['receipt'])
            else:
                receipt = dict(operation_id=oid, run_id=run_id, service=self.service,
                    request_hash=request_hash, state='pending', resource_id=None, after_version=None,
                    created_at=now(), completed_at=None, effect='none',
                    compensates_operation_id=request['compensates_operation_id'])
                self.db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?)',
                    (run_id, principal, oid, request_hash, canonical(request), 'pending',
                     canonical(receipt), None, None))
            before_fault = self.fault(run_id, oid, ordinal, 'before_commit')
            if before_fault:
                self.attempt(run_id, principal, oid, request_id, ordinal, 'before_commit', 202)
        if before_fault:
            return self.fault_response(before_fault, Response(202, {'operation': receipt, 'result': None}))
        # Recheck under the writer transaction: another connection may have finished
        # the pending operation between registration and execution.
        with self.transaction():
            current = self.operation(run_id, principal, oid)
            if current['state'] != 'pending':
                self.attempt(run_id, principal, oid, request_id, ordinal, 'replayed', current['status'])
                return Response(current['status'], json.loads(current['result']),
                                {'Idempotency-Replayed': 'true'})
            base_receipt = dict(receipt)
            self.db.execute('SAVEPOINT effect')
            try:
                result, status, rid, effect, before = self.apply(run_id, principal, oid, request, data)
                receipt = {**receipt, 'state': 'committed', 'resource_id': rid,
                           'after_version': result.get('task', result.get('ticket', {})).get(
                               'version', 2 if request['compensates_operation_id'] else 1),
                           'completed_at': now(), 'effect': effect}
                if before is not None:
                    receipt['before'] = before
                result['operation'] = receipt
                if len(canonical(result).encode()) > 65536:
                    raise Rejected(422, 'RESPONSE_LIMIT')
            except Rejected as exc:
                # Keep rejection and rollback of the tentative effect in one writer
                # transaction so a concurrent retry cannot overwrite either outcome.
                self.db.execute('ROLLBACK TO effect')
                self.db.execute('RELEASE effect')
                receipt = {**base_receipt, 'state': 'rejected', 'resource_id': None,
                           'after_version': None, 'completed_at': now(), 'effect': 'none',
                           'error_code': 'VERSION_CONFLICT' if exc.code == 'VERSION_CONFLICT' else
                           'UNSUPPORTED' if exc.status == 501 else 'VALIDATION_REJECTED'}
                result = {'error': {'code': exc.code, 'operation_id': oid}}
                self.finish(run_id, principal, oid, receipt, exc.status, result)
                self.attempt(run_id, principal, oid, request_id, ordinal, 'rejected', exc.status)
                return Response(exc.status, result)
            self.db.execute('RELEASE effect')
            self.finish(run_id, principal, oid, receipt, status, result)
            self.attempt(run_id, principal, oid, request_id, ordinal, 'committed', status)
            after_fault = self.fault(run_id, oid, ordinal, 'after_commit')
        response = Response(status, result)
        return self.fault_response(after_fault, response) if after_fault else response

    def finish(self, run_id: str, principal: str, oid: str, receipt: dict[str, Any],
               status: int, result: dict[str, Any]) -> None:
        self.db.execute('''UPDATE operations SET state=?,receipt=?,status=?,result=?
            WHERE run_id=? AND principal=? AND operation_id=?''',
            (receipt['state'], canonical(receipt), status, canonical(result), run_id, principal, oid))

    @staticmethod
    def fault_response(mode: str, response: Response) -> Response:
        if mode in {'503', '429'}:
            return Response(int(mode), {'error': {'code': 'INJECTED_FAULT', 'operation_id': None}})
        if mode == 'wrong_receipt':
            result = deepcopy(response.data)
            result['operation']['operation_id'] = str(new_uuid())
            return Response(response.status, result)
        if mode == 'redirect':
            return Response(307, {'error': {'code': 'INJECTED_REDIRECT', 'operation_id': None}})
        if mode == 'pending':
            return response
        return Response(response.status, response.data, fault=mode)

    def apply(self, run_id: str, principal: str, oid: str, request: dict[str, Any],
              data: dict[str, Any]) -> tuple[dict[str, Any], int, str, str, dict[str, Any] | None]:
        body, path = request['body'], request['path']
        inverse = request['compensates_operation_id']
        if inverse:
            return self.compensate(run_id, principal, oid, request, data)
        if request['method'] == 'POST' and path in {'/crm_tasks', '/tickets', '/send'}:
            rid = oid.replace('-', '')
            if path == '/send':
                obj = {**body, 'message_id': rid, 'version': 1, 'receipt_state': 'captured'}
                self.put(run_id, 'messages', rid, obj)
                return ({'message_id': rid, 'receipt_state': 'captured',
                         'recipients': len(set(body['to'] + body['cc']))}, 201, rid, 'captured', None)
            if body.get('customer_id') is not None:
                self.get(run_id, 'customers', body['customer_id'])
            if body.get('assignee') is not None and body['assignee'] not in data['users']:
                raise Rejected(422, 'UNKNOWN_ASSIGNEE')
            key, kind = ('task_id', 'crm_tasks') if path == '/crm_tasks' else ('ticket_id', 'tickets')
            obj = {**body, key: rid, 'status': 'open', 'version': 1,
                   'created_by': principal, 'created_at': now()}
            if kind == 'tickets':
                obj.update(assignee=None, comments=[])
            self.put(run_id, kind, rid, obj)
            return ({'task' if kind == 'crm_tasks' else 'ticket': obj}, 201, rid, 'created', None)
        rid = path.rsplit('/', 1)[-1]
        obj = self.get(run_id, 'tickets', rid)
        if obj['version'] != precondition(request['if_match']):
            raise Rejected(409, 'VERSION_CONFLICT')
        if obj['status'] == 'closed' and body.get('status', 'closed') != 'closed':
            raise Rejected(409, 'STATE_CONFLICT')
        if body.get('assignee') is not None and body['assignee'] not in data['users']:
            raise Rejected(422, 'UNKNOWN_ASSIGNEE')
        before = deepcopy(obj)
        obj.update({key: value for key, value in body.items() if key != 'comment'})
        if 'comment' in body:
            obj['comments'].append({'comment_id': oid.replace('-', ''), 'text': body['comment']})
        obj['version'] += 1
        self.put(run_id, 'tickets', rid, obj)
        return {'ticket': obj}, 200, rid, 'updated', before

    def compensate(self, run_id: str, principal: str, oid: str, request: dict[str, Any],
                   data: dict[str, Any]) -> tuple[dict[str, Any], int, str, str, None]:
        original = self.operation(run_id, principal, request['compensates_operation_id'])
        if original is None or original['state'] != 'committed':
            raise Rejected(409, 'FORWARD_NOT_COMMITTED')
        forward = json.loads(original['receipt'])
        rid = forward['resource_id']
        kind = {'crm': 'crm_tasks', 'ticket': 'tickets', 'mail': 'messages'}[self.service]
        expected_path = '/' + kind + '/' + rid
        if self.service == 'mail':
            expected_path += ('/recall' if json.loads(original['request'])['body']['scope'] == 'internal'
                              else '/recall_requests')
        if (request['path'] != expected_path or forward['compensates_operation_id'] is not None
                or precondition(request['if_match']) != forward['after_version']):
            raise Rejected(409, 'COMPENSATION_CONFLICT')
        obj = self.get(run_id, kind, rid)
        if obj['version'] != forward['after_version']:
            raise Rejected(409, 'VERSION_CONFLICT')
        status = 200
        if self.service == 'crm':
            if forward['effect'] != 'created':
                raise Rejected(409, 'COMPENSATION_CONFLICT')
            obj['status'] = effect = 'deleted'
        elif self.service == 'ticket':
            if forward['effect'] == 'created':
                if request['body'] != {'status': 'closed', 'closure_reason': 'saga_compensation'}:
                    raise Rejected(422, 'INVALID_COMPENSATION')
                obj.update(status='closed', closure_reason='saga_compensation'); effect = 'closed'
            elif forward['effect'] == 'updated':
                if request['body'] != {'restore_operation_id': forward['operation_id']}:
                    raise Rejected(422, 'INVALID_COMPENSATION')
                before = forward['before']
                obj.update({key: before[key] for key in ('status', 'priority', 'assignee')})
                old_ids = {comment['comment_id'] for comment in before['comments']}
                for comment in obj['comments']:
                    if comment['comment_id'] not in old_ids:
                        comment['superseded_by'] = oid
                obj['comments'].append({'comment_id': oid.replace('-', ''),
                    'text': 'Reference compensation of retained update',
                    'compensates_operation_id': forward['operation_id']})
                effect = 'restored'
            else:
                raise Rejected(409, 'COMPENSATION_CONFLICT')
        else:
            if forward['effect'] != 'captured' or obj['receipt_state'] != 'captured':
                raise Rejected(409, 'COMPENSATION_CONFLICT')
            if obj['scope'] == 'external' and not data['external_recall_supported']:
                raise Rejected(501, 'RECALL_UNSUPPORTED')
            effect = 'recalled' if obj['scope'] == 'internal' else 'recall_requested'
            obj['receipt_state'] = effect
            status = 200 if effect == 'recalled' else 202
        obj['version'] += 1
        self.put(run_id, kind, rid, obj)
        result = ({'message_id': rid, 'receipt_state': effect} if self.service == 'mail' else
                  {'task' if self.service == 'crm' else 'ticket': obj})
        return result, status, rid, effect, None

    def evidence(self, run_id: str) -> dict[str, Any]:
        run = self.run(run_id)
        operations = self.db.execute('SELECT * FROM operations WHERE run_id=? ORDER BY operation_id',
                                     (run_id,)).fetchall()
        return {'run_id': run_id, 'principal': run['principal'], 'service': self.service,
                'store_id': self.store_id, 'schema': SCHEMA, 'fixture_hash': run['fixture_hash'],
                'operations': [{'request_hash': row['request_hash'],
                                'operation': json.loads(row['receipt']),
                                'result': json.loads(row['result']) if row['result'] else None}
                               for row in operations],
                'resources': [{'kind': row['kind'], 'value': json.loads(row['data'])} for row in
                    self.db.execute('SELECT * FROM resources WHERE run_id=? ORDER BY kind,resource_id',
                                    (run_id,))],
                'attempts': [dict(row) for row in self.db.execute(
                    'SELECT * FROM attempts WHERE run_id=? ORDER BY id', (run_id,))],
                'faults': [dict(row) for row in self.db.execute(
                    'SELECT * FROM faults WHERE run_id=? ORDER BY operation_id,ordinal,phase', (run_id,))]}
