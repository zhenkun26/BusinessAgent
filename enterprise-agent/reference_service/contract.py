"""Independent reference wire validation. No imports from BusinessAgent adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import json
import re
from typing import Any
from uuid import UUID

PROFILE = 'business-reference-v1'
SCHEMA = 'reference-store-v1'
MAX_BODY = 65536
RECIPIENTS = ['employee@reference.invalid', 'manager@reference.invalid',
              'customer@reference.invalid']


class Rejected(Exception):
    def __init__(self, status: int, code: str) -> None:
        self.status = status
        self.code = code
        super().__init__(code)


@dataclass
class Response:
    status: int
    data: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)
    fault: str | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def json_object(data: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ValueError
            out[key] = value
        return out

    def invalid(value: str) -> None:
        raise ValueError

    try:
        if len(data) > MAX_BODY:
            raise ValueError
        result = json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                            parse_float=invalid, parse_constant=invalid)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (ValueError, UnicodeError, RecursionError):
        raise Rejected(422, 'INVALID_JSON') from None


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise Rejected(422, 'INVALID_IDENTIFIER')
    return value


def uuid4(value: Any) -> str:
    try:
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise Rejected(422, 'INVALID_UUID') from None
    return value


def string(value: Any, maximum: int, minimum: int = 0) -> str:
    if (not isinstance(value, str) or not minimum <= len(value) <= maximum
            or '\x00' in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value)):
        raise Rejected(422, 'INVALID_FIELD')
    return value


def fields(body: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    if set(body) - allowed or not required <= set(body):
        raise Rejected(422, 'INVALID_FIELDS')


def enum(value: Any, allowed: set[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise Rejected(422, 'INVALID_ENUM')
    return value


def calendar_date(value: Any) -> str:
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except (TypeError, ValueError):
        raise Rejected(422, 'INVALID_DATE') from None
    return value


def precondition(value: str | None) -> int:
    if value is None:
        raise Rejected(428, 'PRECONDITION_REQUIRED')
    if not re.fullmatch(r'"[1-9][0-9]{0,14}"', value):
        raise Rejected(422, 'INVALID_VERSION')
    return int(value[1:-1])


def normalize(service: str, method: str, path: str, body: dict[str, Any] | None,
              if_match: str | None, inverse: str | None) -> dict[str, Any]:
    """Resolve documented defaults before computing the independent request fingerprint."""
    if inverse:
        uuid4(inverse)
        precondition(if_match)
        if service == 'crm' and method == 'DELETE' and path.startswith('/crm_tasks/'):
            if body is not None:
                raise Rejected(422, 'INVALID_FIELDS')
        elif service == 'ticket' and method == 'PATCH' and path.startswith('/tickets/'):
            if body not in ({'restore_operation_id': inverse},
                            {'status': 'closed', 'closure_reason': 'saga_compensation'}):
                raise Rejected(422, 'INVALID_COMPENSATION')
        elif (service == 'mail' and method == 'POST' and path.startswith('/messages/')
              and path.rsplit('/', 1)[-1] in {'recall', 'recall_requests'}):
            if body != {}:
                raise Rejected(422, 'INVALID_FIELDS')
        else:
            raise Rejected(404, 'NOT_FOUND')
    elif service == 'crm' and method == 'POST' and path == '/crm_tasks':
        fields(body, {'customer_id', 'title', 'description', 'priority', 'assignee', 'due_date'},
               {'customer_id', 'title', 'assignee'})
        body = {'description': '', 'priority': 1, 'due_date': None, **body}
        identifier(body['customer_id']); identifier(body['assignee'])
        string(body['title'], 200, 1); string(body['description'], 2000)
        if type(body['priority']) is not int or not 0 <= body['priority'] <= 5:
            raise Rejected(422, 'INVALID_PRIORITY')
        if body['due_date'] is not None:
            calendar_date(body['due_date'])
    elif service == 'ticket' and method == 'POST' and path == '/tickets':
        fields(body, {'title', 'description', 'customer_id', 'priority', 'category'}, {'title'})
        body = {'description': '', 'customer_id': None, 'priority': 'normal',
                'category': 'general', **body}
        string(body['title'], 200, 1); string(body['description'], 5000)
        string(body['category'], 64, 1)
        enum(body['priority'], {'low', 'normal', 'high', 'urgent'})
        if body['customer_id'] is not None:
            identifier(body['customer_id'])
    elif service == 'ticket' and method == 'PATCH' and path.startswith('/tickets/'):
        fields(body, {'status', 'priority', 'assignee', 'comment'}, set())
        precondition(if_match)
        if not body:
            raise Rejected(422, 'EMPTY_UPDATE')
        if 'status' in body:
            enum(body['status'], {'open', 'in_progress', 'resolved', 'closed'})
        if 'priority' in body:
            enum(body['priority'], {'low', 'normal', 'high', 'urgent'})
        if body.get('assignee') is not None:
            identifier(body['assignee'])
        if 'comment' in body:
            string(body['comment'], 2000, 1)
    elif service == 'mail' and method == 'POST' and path == '/send':
        fields(body, {'scope', 'to', 'cc', 'subject', 'body', 'attachments'},
               {'scope', 'to', 'subject', 'body'})
        body = {'cc': [], 'attachments': [], **body}
        enum(body['scope'], {'internal', 'external'})
        string(body['subject'], 500, 1); string(body['body'], 20000)
        for key, minimum in (('to', 1), ('cc', 0)):
            values = body[key]
            if (not isinstance(values, list) or not minimum <= len(values) <= 50
                    or any(not isinstance(v, str) for v in values)
                    or len(set(values)) != len(values)):
                raise Rejected(422, 'INVALID_RECIPIENTS')
        allowed = RECIPIENTS if body['scope'] == 'external' else RECIPIENTS[:2]
        if not set(body['to'] + body['cc']) <= set(allowed):
            raise Rejected(422, 'RECIPIENT_NOT_ALLOWED')
        if (not isinstance(body['attachments'], list) or len(body['attachments']) > 10
                or any(a != 'fixture-brief-v1' for a in body['attachments'])):
            raise Rejected(422, 'ATTACHMENT_NOT_ALLOWED')
    else:
        raise Rejected(404, 'NOT_FOUND')
    if not inverse and method == 'POST' and if_match is not None:
        raise Rejected(422, 'UNEXPECTED_PRECONDITION')
    return {'profile': PROFILE, 'method': method, 'path': path, 'body': body,
            'if_match': if_match, 'compensates_operation_id': inverse}


def fixture(variant: str) -> dict[str, Any]:
    enum(variant, {'baseline', 'variant'})
    customers = [dict(customer_id='C001', version=1, name='Reference North', contact='Fixture',
                      phone='synthetic-001', email='customer@reference.invalid',
                      industry='synthetic', level='A'),
                 dict(customer_id='C002', version=1, name='Reference South', contact='Fixture',
                      phone='synthetic-002', email='customer@reference.invalid',
                      industry='synthetic', level='B')]
    orders = [dict(order_id='O001', customer_id='C001', amount_minor=120050, currency='CNY',
                   status='completed', version=1, created_at='2026-01-15',
                   items=[dict(sku='SKU001', name='Synthetic item', qty=1, price_minor=120050)]),
              dict(order_id='O002', customer_id='C002', amount_minor=9999, currency='CNY',
                   status='pending', version=1, created_at='2026-02-15',
                   items=[dict(sku='SKU002', name='Synthetic item', qty=1, price_minor=9999)])]
    if variant == 'variant':
        orders[0]['amount_minor'] = orders[0]['items'][0]['price_minor'] = 240100
        orders[0]['version'] = 2
    return {'fixture_version': 'c18-fixture-v1', 'variant': variant,
            'customers': customers, 'orders': orders}
