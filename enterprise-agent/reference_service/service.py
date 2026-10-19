"""Strict business and operator dispatch, independent of application tool adapters."""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import json
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from reference_service.contract import (
    PROFILE, SCHEMA, Rejected, Response, calendar_date, fingerprint, identifier,
    json_object, normalize, uuid4,
)
from reference_service.store import Store


@dataclass(frozen=True)
class Credential:
    principal: str
    permissions: frozenset[str]


class Service:
    def __init__(self, store: Store, credentials: dict[str, Credential], operator_token: str) -> None:
        self.store = store
        self.credentials = dict(credentials)
        self.operator_token = operator_token
        if (not credentials or operator_token in credentials or len(operator_token) < 32
                or any(len(token) < 32 for token in credentials)):
            raise ValueError('REFERENCE_CREDENTIALS_INVALID')
        for grant in credentials.values():
            identifier(grant.principal)
            if not grant.permissions <= {'read', 'write', 'compensate'}:
                raise ValueError('REFERENCE_PERMISSIONS_INVALID')

    def authenticate(self, headers: dict[str, str], *, control: bool) -> Credential | None:
        value = headers.get('authorization', '')
        if not value.startswith('Bearer '):
            raise Rejected(401, 'UNAUTHORIZED')
        token = value[7:]
        if control:
            if not hmac.compare_digest(token.encode(), self.operator_token.encode()):
                raise Rejected(401, 'UNAUTHORIZED')
            return None
        for secret, grant in self.credentials.items():
            if hmac.compare_digest(token.encode(), secret.encode()):
                return grant
        raise Rejected(401, 'UNAUTHORIZED')

    def handle(self, method: str, target: str, headers: dict[str, str], raw: bytes = b'',
               *, control: bool = False) -> Response:
        try:
            response = self.dispatch(method, target, headers, raw, control=control)
        except Rejected as exc:
            response = Response(exc.status, {'error': {'code': exc.code, 'operation_id': None}})
        except Exception:
            # No exception/payload/header echo; pending transaction evidence is retained.
            response = Response(503, {'error': {'code': 'REFERENCE_UNAVAILABLE', 'operation_id': None}})
        response.headers['X-Reference-Profile'] = PROFILE
        return response

    def dispatch(self, method: str, target: str, headers: dict[str, str], raw: bytes,
                 *, control: bool) -> Response:
        if target == '/health' and method == 'GET' and not raw:
            with self.store.lock:
                self.store.db.execute('SELECT 1').fetchone()
            return Response(200, {'status': 'ready'})
        grant = self.authenticate(headers, control=control)
        request_id = uuid4(headers.get('x-request-id'))
        url = urlsplit(target)
        if (url.scheme or url.netloc or url.fragment or '%' in url.path
                or not re.fullmatch(r'/[A-Za-z0-9_/-]+', url.path)):
            raise Rejected(422, 'INVALID_PATH')
        try:
            query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True,
                             max_num_fields=10)
        except ValueError:
            raise Rejected(422, 'INVALID_QUERY') from None
        if any(len(values) != 1 for values in query.values()):
            raise Rejected(422, 'INVALID_QUERY')
        params = {key: values[0] for key, values in query.items()}
        if method == 'GET' and (raw or headers.get('accept') != 'application/json'):
            raise Rejected(422, 'INVALID_READ')
        if method != 'GET' and headers.get('content-type') != 'application/json':
            raise Rejected(422, 'INVALID_CONTENT_TYPE')
        body = json_object(raw) if raw else None
        with self.store.lock:
            if control:
                if params:
                    raise Rejected(422, 'INVALID_QUERY')
                return self.control(method, url.path, body)
            if not url.path.startswith('/api/v1/'):
                raise Rejected(404, 'NOT_FOUND')
            run_id = uuid4(headers.get('x-reference-run-id'))
            self.store.run(run_id, grant.principal)
            inverse = headers.get('x-compensates-operation')
            required = 'read' if method == 'GET' else 'compensate' if inverse else 'write'
            if required not in grant.permissions:
                raise Rejected(403, 'FORBIDDEN')
            path = url.path[len('/api/v1'):]
            # Every variable path segment uses the resource/UUID grammar; no traversal decoding.
            for part in path.split('/')[1:]:
                identifier(part)
            if method == 'GET':
                response = self.read(run_id, grant.principal, path, params)
                self.store.attempt(run_id, grant.principal, None, request_id, 0, 'read', response.status)
                return response
            if params:
                raise Rejected(422, 'INVALID_QUERY')
            key = headers.get('idempotency-key', '')
            if not key.startswith('ba-ref-v1:'):
                raise Rejected(422, 'INVALID_IDEMPOTENCY_KEY')
            oid = uuid4(key[len('ba-ref-v1:'):])
            if method != 'DELETE' and body is None:
                raise Rejected(422, 'BODY_REQUIRED')
            # Explicit route shapes keep prefix matching in normalization unambiguous.
            allowed = ({'POST /crm_tasks', 'DELETE /crm_tasks/{id}'} if self.store.service == 'crm'
                       else {'POST /tickets', 'PATCH /tickets/{id}'}
                       if self.store.service == 'ticket' else
                       {'POST /send', 'POST /messages/{id}/recall',
                        'POST /messages/{id}/recall_requests'})
            parts = path.split('/')
            pattern = path if len(parts) == 2 else '/' + parts[1] + '/{id}' + (
                '/' + parts[3] if len(parts) == 4 else '')
            if len(parts) > 4 or method + ' ' + pattern not in allowed:
                raise Rejected(404, 'NOT_FOUND')
            request = normalize(self.store.service, method, path, body,
                                headers.get('if-match'), inverse)
            return self.store.mutate(run_id, grant.principal, oid, request_id, request)

    def control(self, method: str, path: str, body: dict[str, Any] | None) -> Response:
        if path == '/control/v1/runs' and method == 'POST' and body is not None:
            return Response(201, self.store.provision(body))
        match = re.fullmatch(r'/control/v1/runs/([a-f0-9-]+)/([a-z]+)', path)
        if match:
            run_id, action = uuid4(match[1]), match[2]
            if action == 'faults' and method == 'POST' and body is not None:
                return Response(201, self.store.install_fault(run_id, body))
            if action == 'evidence' and method == 'GET':
                return Response(200, self.store.evidence(run_id))
        raise Rejected(404, 'NOT_FOUND')

    def read(self, run_id: str, principal: str, path: str, params: dict[str, str]) -> Response:
        parts = path.strip('/').split('/')
        if len(parts) != 2:
            raise Rejected(404, 'NOT_FOUND')
        kind, rid = parts
        if kind == 'operations':
            if params:
                raise Rejected(422, 'INVALID_QUERY')
            row = self.store.operation(run_id, principal, uuid4(rid))
            if row is None:
                raise Rejected(404, 'NOT_FOUND')
            return Response(200, {'operation': json.loads(row['receipt']),
                'result': json.loads(row['result']) if row['state'] == 'committed' else None})
        if self.store.service == 'crm' and kind == 'analysis' and rid in {'orders', 'customers'}:
            return Response(200, self.analysis(run_id, principal, rid, params))
        allowed = {'crm': {'customers', 'orders'}, 'ticket': {'tickets'}, 'mail': {'messages'}}
        if kind not in allowed[self.store.service]:
            raise Rejected(404, 'NOT_FOUND')
        obj = self.store.get(run_id, kind, rid)
        if kind == 'customers':
            if set(params) - {'fields'}:
                raise Rejected(422, 'INVALID_QUERY')
            names = params.get('fields', 'name,contact,phone,email,industry,level').split(',')
            if not set(names) <= {'name', 'contact', 'phone', 'email', 'industry', 'level'}:
                raise Rejected(422, 'INVALID_QUERY')
            return Response(200, {'customer': {key: obj[key] for key in
                                               ['customer_id', 'version', *names]}})
        if kind == 'orders':
            if set(params) - {'include_items'} or params.get('include_items', '0') not in {'0', '1'}:
                raise Rejected(422, 'INVALID_QUERY')
            if params.get('include_items', '0') == '0':
                obj.pop('items', None)
            return Response(200, {'order': obj})
        if params:
            raise Rejected(422, 'INVALID_QUERY')
        if kind == 'tickets':
            return Response(200, {'ticket': obj})
        return Response(200, {'message_id': obj['message_id'], 'version': obj['version'],
                             'receipt_state': obj['receipt_state'],
                             'recipients': sorted(set(obj['to'] + obj['cc']))})

    def analysis(self, run_id: str, principal: str, kind: str,
                 params: dict[str, str]) -> dict[str, Any]:
        if set(params) - {'limit', 'start_date', 'end_date', 'snapshot_id', 'cursor'}:
            raise Rejected(422, 'INVALID_QUERY')
        limit = params.get('limit', '100')
        if not re.fullmatch(r'[1-9][0-9]{0,2}', limit) or int(limit) > 100:
            raise Rejected(422, 'INVALID_QUERY')
        start, end = params.get('start_date'), params.get('end_date')
        if (start is None) != (end is None):
            raise Rejected(422, 'INVALID_DATE')
        if start is not None and calendar_date(start) > calendar_date(end):
            raise Rejected(422, 'INVALID_DATE')
        if kind == 'customers' and 'snapshot_id' not in params:
            raise Rejected(409, 'SNAPSHOT_REQUIRED')
        run = self.store.run(run_id, principal)
        selected_range = {'start_date': start, 'end_date': end}
        sid = fingerprint([run_id, principal, run['fixture_hash'], selected_range])
        if params.get('snapshot_id', sid) != sid:
            raise Rejected(409, 'SNAPSHOT_CONFLICT')
        cursor = params.get('cursor')
        offset = 0
        if cursor:
            match = re.fullmatch(kind + r'_([1-9][0-9]{0,3})_' + sid[:20], cursor)
            if not match or 'snapshot_id' not in params:
                raise Rejected(409, 'CURSOR_CONFLICT')
            offset = int(match[1])
        source = run['data'][kind]  # Immutable run seed; the same records as B01/B02.
        if kind == 'orders':
            keys = ('order_id', 'customer_id', 'amount_minor', 'currency', 'status', 'version', 'created_at')
            items = [{key: row[key] for key in keys} for row in source
                     if start is None or start <= row['created_at'] <= end]
        else:
            items = [{key: row[key] for key in ('customer_id', 'name', 'level', 'version')}
                     for row in source]
        if offset and offset >= len(items):
            raise Rejected(409, 'CURSOR_CONFLICT')
        page = items[offset:offset + int(limit)]
        next_offset = offset + len(page)
        return {'schema': 'crm-analysis-v1', 'run_id': run_id, 'snapshot_id': sid,
                'as_of': run['created_at'], 'range': selected_range, 'items': page,
                'total': len(items), 'next_cursor':
                f'{kind}_{next_offset}_{sid[:20]}' if next_offset < len(items) else None}
