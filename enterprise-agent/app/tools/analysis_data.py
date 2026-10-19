"""Bounded CRM snapshot reader; no implicit Mock fallback or live-service claim."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlencode

SCHEMA = 'crm-analysis-v1'
MAX_ROWS = 5000
PAGE_SIZE = 100


class AnalysisDataError(Exception):
    """Fixed public error code; provider payloads are never exception messages."""


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise AnalysisDataError('ANALYSIS_SCHEMA_INVALID')
    return value


def iso_date(value: Any) -> str:
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except (ValueError, TypeError):
        raise AnalysisDataError('ANALYSIS_RANGE_INVALID') from None
    return value


async def authorize(user_id: str | None, role: Any, department: str | None) -> bool:
    from app.core.database import get_session_factory
    from app.security.rbac import AgentRole, can_use_tool, resolve_active_user
    try:
        identifier(user_id)
        async with asyncio.timeout(5), get_session_factory()() as db:
            user = await resolve_active_user(user_id, db)
        current = AgentRole(user.role)
        if (current != role or (user.department or 'shared_company') !=
                (department or 'shared_company') or not can_use_tool(current, 'query_order')):
            raise ValueError
        return can_use_tool(current, 'query_customer')
    except Exception:
        raise AnalysisDataError('ANALYSIS_AUTHORIZATION_DENIED') from None


def validate_row(row: Any, kind: str) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise AnalysisDataError('ANALYSIS_SCHEMA_INVALID')
    required = ({'order_id', 'customer_id', 'amount_minor', 'currency', 'status', 'version',
                 'created_at'} if kind == 'orders' else {'customer_id', 'name', 'level', 'version'})
    if set(row) != required or type(row['version']) is not int or row['version'] < 1:
        raise AnalysisDataError('ANALYSIS_SCHEMA_INVALID')
    identifier(row['customer_id'])
    if kind == 'orders':
        identifier(row['order_id'])
        iso_date(row['created_at'])
        if (type(row['amount_minor']) is not int or not 0 <= row['amount_minor'] <= 10**14
                or not isinstance(row['currency'], str)
                or not re.fullmatch(r'[A-Z]{3}', row['currency'])
                or row['status'] not in {'pending', 'completed', 'cancelled', 'refunded'}):
            raise AnalysisDataError('ANALYSIS_SCHEMA_INVALID')
    elif any(not isinstance(row[k], str) or not 1 <= len(row[k]) <= 200
             or any(ord(c) < 32 for c in row[k]) for k in ('name', 'level')):
        raise AnalysisDataError('ANALYSIS_SCHEMA_INVALID')
    return dict(row)


class AnalysisReader:
    def __init__(self, user_id: str | None, role: Any, department: str | None) -> None:
        self.user_id = user_id
        self.role = role
        self.department = department

    async def read(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        from app.config import get_settings
        from app.tools.crm import QueryOrderTool, get_all_customers, get_all_orders
        from app.tools.reference import target
        if (start is None) != (end is None):
            raise AnalysisDataError('ANALYSIS_RANGE_INVALID')
        if start is not None and iso_date(start) > iso_date(end):
            raise AnalysisDataError('ANALYSIS_RANGE_INVALID')
        try:
            async with asyncio.timeout(30):
                can_customers = await authorize(self.user_id, self.role, self.department)
                tool = QueryOrderTool()
                provider = tool._effective_provider()
                config = target(tool, get_settings())
                requested = {'start_date': start, 'end_date': end}
                if provider == 'mock':
                    orders = []
                    for item in get_all_orders():
                        # Mock fixtures use decimal major units, explicitly CNY/2 decimals.
                        amount = Decimal(str(item['amount'])) * 100
                        if not amount.is_finite() or amount != amount.to_integral_value():
                            raise AnalysisDataError('ANALYSIS_SCHEMA_INVALID')
                        orders.append(validate_row({k: item[k] for k in (
                            'order_id', 'customer_id', 'status', 'created_at')} | {
                                'amount_minor': int(amount), 'currency': 'CNY', 'version': 1},
                                'orders'))
                    customers = [validate_row(
                        {k: c[k] for k in ('customer_id', 'name', 'level')} | {'version': 1},
                        'customers') for c in get_all_customers()] if can_customers else []
                    snapshot = hashlib.sha256(json.dumps([orders, customers], sort_keys=True,
                        ensure_ascii=False).encode()).hexdigest()
                    as_of = datetime.now(timezone.utc).isoformat()
                elif provider == 'http':
                    orders, identity = await self._pages(config, 'orders', requested, None)
                    snapshot, as_of = identity
                    customers = (await self._pages(config, 'customers', requested, identity))[0] \
                        if can_customers else []
                else:
                    raise AnalysisDataError('ANALYSIS_PROVIDER_UNSUPPORTED')
                for rows, key in ((orders, 'order_id'), (customers, 'customer_id')):
                    if len(rows) > MAX_ROWS or len({r[key] for r in rows}) != len(rows):
                        raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
                if can_customers and not {o['customer_id'] for o in orders} <= {
                        c['customer_id'] for c in customers}:
                    raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
                orders = [o for o in orders if start is None or start <= o['created_at'] <= end]
                await authorize(self.user_id, self.role, self.department)
                return {'orders': orders, 'customers': customers, 'provenance': {
                    'provider': provider, 'schema': SCHEMA, 'snapshot_id': snapshot,
                    'as_of': as_of, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                    'requested_range': requested, 'is_mock': provider == 'mock',
                    'customer_details': can_customers, 'currency_scale': 2,
                    'amount_semantics': 'gross_order_amount_all_statuses_not_revenue'}}
        except AnalysisDataError:
            raise
        except Exception:
            raise AnalysisDataError('ANALYSIS_SOURCE_UNAVAILABLE') from None

    async def _pages(self, config: dict[str, Any], kind: str, requested: dict[str, Any],
                     identity: tuple[str, str] | None) -> tuple[list[dict], tuple[str, str]]:
        from app.tools.reference import request
        rows: list[dict] = []
        seen: set[str] = set()
        cursors: set[str] = set()
        cursor = None
        total = None
        for _ in range(MAX_ROWS // PAGE_SIZE):
            await authorize(self.user_id, self.role, self.department)
            params = {'limit': PAGE_SIZE, **{k: v for k, v in requested.items() if v is not None}}
            if identity is not None:
                params['snapshot_id'] = identity[0]
            if cursor is not None:
                params['cursor'] = cursor
            ok, data, _, meta = await request(config, 'GET',
                '/analysis/' + kind + '?' + urlencode(params), retries=2)
            if not ok or meta.get('status') != 200:
                raise AnalysisDataError('ANALYSIS_SOURCE_UNAVAILABLE')
            if (not isinstance(data, dict) or set(data) != {'schema', 'run_id', 'snapshot_id',
                    'as_of', 'range', 'items', 'total', 'next_cursor'}
                    or data['schema'] != SCHEMA or data['run_id'] != config['run_id']
                    or data['range'] != requested):
                raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
            snapshot = identifier(data['snapshot_id'])
            stamp = datetime.fromisoformat(data['as_of'].replace('Z', '+00:00'))
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
            received = (snapshot, data['as_of'])
            if identity is not None and identity != received:
                raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
            identity = received
            if (type(data['total']) is not int or not 0 <= data['total'] <= MAX_ROWS
                    or total is not None and total != data['total']
                    or not isinstance(data['items'], list) or len(data['items']) > PAGE_SIZE):
                raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
            total = data['total']
            for row in data['items']:
                row = validate_row(row, kind)
                key = row['order_id' if kind == 'orders' else 'customer_id']
                if key in seen:
                    raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
                seen.add(key)
                rows.append(row)
                if kind == 'orders' and requested['start_date'] is not None and not (
                        requested['start_date'] <= row['created_at'] <= requested['end_date']):
                    raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
            cursor = data['next_cursor']
            if cursor is None:
                if len(rows) != total:
                    raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
                return rows, identity
            identifier(cursor)
            if cursor in cursors or not data['items'] or len(rows) >= total:
                raise AnalysisDataError('ANALYSIS_SNAPSHOT_INVALID')
            cursors.add(cursor)
        raise AnalysisDataError('ANALYSIS_LIMIT_EXCEEDED')
