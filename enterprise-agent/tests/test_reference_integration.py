"""C18 in-memory SQLite and actual-source integration contracts; no real sockets/disk/services."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
from pathlib import Path
import runpy
import sqlite3
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference_service.contract import PROFILE, SCHEMA, Rejected, canonical, fingerprint, json_object
from reference_service.service import Credential, Service
from reference_service.store import Store
from reference_service.server import Handler

TOKEN = 'synthetic-business-credential-000000000'
OPERATOR = 'synthetic-operator-credential-000000000'
READ = 'synthetic-read-only-credential-000000000'
OTHER = 'synthetic-other-principal-000000000000'
BASE = runpy.run_path(str(ROOT / 'tests/test_tool_operation_safety.py'))


def uid():
    return str(uuid.uuid4())


def make(service, run_id, variant='baseline', supported=True):
    db = sqlite3.connect(':memory:', isolation_level=None, check_same_thread=False)
    store = Store(db, service, uid(), initialize=True)
    app = Service(store, {TOKEN: Credential('application', frozenset({'read', 'write', 'compensate'})),
        READ: Credential('application', frozenset({'read'})),
        OTHER: Credential('other', frozenset({'read', 'write', 'compensate'}))}, OPERATOR)
    store.provision(dict(run_id=run_id, principal='application', users=['test-user', 'manager'],
                         fixture=variant, external_recall_supported=supported))
    return app


def call(app, run_id, method, path, body=None, *, oid=None, token=TOKEN, version=None,
         inverse=None, control=False, raw=None):
    headers = {'authorization': 'Bearer ' + token, 'x-reference-run-id': run_id,
               'x-request-id': uid(), 'accept': 'application/json',
               'content-type': 'application/json'}
    if method != 'GET': headers['idempotency-key'] = 'ba-ref-v1:' + (oid or uid())
    if version is not None: headers['if-match'] = '"' + str(version) + '"'
    if inverse is not None: headers['x-compensates-operation'] = inverse
    data = raw if raw is not None else canonical(body).encode() if body is not None else b''
    return app.handle(method, path if control else '/api/v1' + path, headers, data, control=control)


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.run_id = uid()
        self.apps = {name: make(name, self.run_id) for name in ('crm', 'ticket', 'mail')}
        for app in self.apps.values(): self.addCleanup(app.store.db.close)

    def send(self, service, method, path, body=None, **kwargs):
        return call(self.apps[service], self.run_id, method, path, body, **kwargs)

    def create(self, service='ticket', **kwargs):
        oid = uid()
        body = {'title': 'Synthetic action'}
        path = '/tickets' if service == 'ticket' else '/crm_tasks'
        if service == 'crm': body.update(customer_id='C001', assignee='test-user')
        body.update(kwargs)
        result = self.send(service, 'POST', path, body, oid=oid)
        self.assertEqual(result.status, 201, result.data)
        key = 'ticket' if service == 'ticket' else 'task'
        return oid, result.data[key][key + '_id'], result

    def evidence(self, service):
        return self.apps[service].store.evidence(self.run_id)

    def test_read_projection_items_absence_and_exact_minor_money(self):
        r = self.send('crm', 'GET', '/customers/C001?fields=name')
        self.assertEqual(set(r.data['customer']), {'customer_id', 'version', 'name'})
        r = self.send('crm', 'GET', '/orders/O001')
        self.assertEqual(r.data['order']['amount_minor'], 120050)
        self.assertNotIn('items', r.data['order'])
        self.assertIn('items', self.send('crm', 'GET', '/orders/O001?include_items=1').data['order'])
        self.assertEqual(self.send('crm', 'GET', '/customers/absent').status, 404)
        self.assertEqual(self.evidence('crm')['operations'], [])

    def test_normalized_defaults_replay_and_distinct_identical_actions(self):
        oid, rid, first = self.create()
        body = {'title': 'Synthetic action', 'description': '', 'customer_id': None,
                'priority': 'normal', 'category': 'general'}
        replay = self.send('ticket', 'POST', '/tickets', body, oid=oid)
        self.assertEqual(replay.data, first.data)
        self.assertEqual(replay.headers['Idempotency-Replayed'], 'true')
        _, second_id, _ = self.create()
        self.assertNotEqual(rid, second_id)
        self.assertEqual(len(self.evidence('ticket')['operations']), 2)

    def test_changed_body_path_or_precondition_is_conflict(self):
        oid, rid, _ = self.create()
        conflict = self.send('ticket', 'POST', '/tickets', {'title': 'changed'}, oid=oid)
        self.assertEqual(conflict.status, 409)
        conflict = self.send('ticket', 'PATCH', '/tickets/' + rid, {'status': 'closed'}, oid=oid, version=1)
        self.assertEqual(conflict.data['error']['code'], 'IDEMPOTENCY_CONFLICT')
        self.assertEqual(self.send('ticket', 'GET', '/tickets/' + rid).data['ticket']['version'], 1)

    def test_parallel_same_key_has_one_effect(self):
        oid = uid()
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies = list(pool.map(lambda _: self.send('ticket', 'POST', '/tickets',
                {'title': 'concurrent'}, oid=oid), range(8)))
        self.assertTrue(all(reply.status == 201 for reply in replies))
        self.assertEqual(len({reply.data['ticket']['ticket_id'] for reply in replies}), 1)
        self.assertEqual(len(self.evidence('ticket')['operations']), 1)
        self.assertEqual(sum(row['phase'] == 'committed' for row in self.evidence('ticket')['attempts']), 1)

    def test_auth_scope_control_and_reset_deny(self):
        for token, status in [('invalid', 401), (OTHER, 404)]:
            self.assertEqual(self.send('crm', 'GET', '/customers/C001', token=token).status, status)
        self.assertEqual(self.send('ticket', 'POST', '/tickets', {'title': 'denied'}, token=READ).status, 403)
        path = '/control/v1/runs/' + self.run_id + '/evidence'
        self.assertEqual(self.send('crm', 'GET', path, control=True).status, 401)
        self.assertEqual(self.send('crm', 'POST', '/control/v1/reset', {}, token=OPERATOR,
                                   control=True).status, 404)
        self.assertEqual(self.evidence('ticket')['operations'], [])
        self.assertEqual(self.send('crm', 'GET', '/customers/C001', token=OPERATOR).status, 401)

    def test_cross_run_reads_and_operation_queries_are_hidden(self):
        oid, _, _ = self.create()
        self.assertEqual(call(self.apps['ticket'], uid(), 'GET', '/operations/' + oid).status, 404)
        self.assertEqual(self.send('ticket', 'GET', '/operations/' + oid, token=OTHER).status, 404)

    def test_malformed_json_types_and_routes_have_zero_effect(self):
        for raw in (b'{"title":"x","title":"y"}', b'{"title":NaN}', b'{"title":1.1}',
                    b'[]', b'x' * 65537, b'{"title":"x","unknown":1}'):
            self.assertEqual(self.send('ticket', 'POST', '/tickets', raw=raw).status, 422)
        for path in ('/tickets/../T1', '/tickets/a%2fb', '/tickets//', '/tickets/T1/other'):
            self.assertIn(self.send('ticket', 'PATCH', path, {'status': 'closed'}, version=1).status,
                          {404, 422})
        self.assertEqual(self.evidence('ticket')['operations'], [])

    def test_service_isolation_and_missing_key(self):
        self.assertEqual(self.send('mail', 'POST', '/tickets', {'title': 'x'}).status, 404)
        r = self.apps['ticket'].handle('POST', '/api/v1/tickets', {
            'authorization': 'Bearer ' + TOKEN, 'x-reference-run-id': self.run_id,
            'x-request-id': uid(), 'content-type': 'application/json'}, b'{"title":"x"}')
        self.assertEqual(r.status, 422)

    def test_version_conflict_retains_no_effect_receipt(self):
        _, rid, _ = self.create()
        oid = uid()
        self.assertEqual(self.send('ticket', 'PATCH', '/tickets/' + rid,
                                   {'status': 'resolved'}, oid=oid, version=7).status, 409)
        query = self.send('ticket', 'GET', '/operations/' + oid)
        self.assertEqual(query.data['operation']['state'], 'rejected')
        self.assertEqual(query.data['operation']['error_code'], 'VERSION_CONFLICT')
        self.assertIsNone(query.data['result'])
        self.assertEqual(self.send('ticket', 'GET', '/tickets/' + rid).data['ticket']['version'], 1)
        self.assertEqual(self.send('ticket', 'PATCH', '/tickets/' + rid, {'status': 'closed'}).status, 428)

    def test_crm_tombstone_is_retained_and_replay_precedes_version(self):
        forward, rid, _ = self.create('crm')
        inverse = uid()
        r = self.send('crm', 'DELETE', '/crm_tasks/' + rid, oid=inverse, version=1, inverse=forward)
        self.assertEqual(r.status, 200)
        self.assertEqual(r.data['task']['status'], 'deleted')
        self.assertEqual(self.send('crm', 'DELETE', '/crm_tasks/' + rid, oid=inverse,
            version=1, inverse=forward).data, r.data)
        retained = self.apps['crm'].store.get(self.run_id, 'crm_tasks', rid)
        self.assertEqual(retained['version'], 2)
        self.assertEqual(len(self.evidence('crm')['operations']), 2)

    def test_ticket_update_restore_keeps_comment_and_before_image(self):
        _, rid, _ = self.create()
        forward, inverse = uid(), uid()
        update = self.send('ticket', 'PATCH', '/tickets/' + rid,
            {'priority': 'urgent', 'assignee': 'manager', 'comment': 'retained'}, oid=forward, version=1)
        self.assertEqual(update.data['operation']['before']['priority'], 'normal')
        restore = self.send('ticket', 'PATCH', '/tickets/' + rid, {'restore_operation_id': forward},
                            oid=inverse, version=2, inverse=forward)
        self.assertEqual(restore.status, 200, restore.data)
        ticket = restore.data['ticket']
        self.assertEqual(ticket['priority'], 'normal'); self.assertIsNone(ticket['assignee'])
        self.assertEqual(ticket['comments'][0]['text'], 'retained')
        self.assertEqual(ticket['comments'][0]['superseded_by'], inverse)
        self.assertEqual(ticket['comments'][1]['compensates_operation_id'], forward)

    def test_ticket_create_compensation_and_later_update_conflict(self):
        forward, rid, _ = self.create()
        self.send('ticket', 'PATCH', '/tickets/' + rid, {'priority': 'high'}, version=1)
        r = self.send('ticket', 'PATCH', '/tickets/' + rid,
            {'status': 'closed', 'closure_reason': 'saga_compensation'}, version=1, inverse=forward)
        self.assertEqual(r.status, 409)
        self.assertEqual(self.send('ticket', 'GET', '/tickets/' + rid).data['ticket']['priority'], 'high')
        forward, rid, _ = self.create()
        r = self.send('ticket', 'PATCH', '/tickets/' + rid,
            {'status': 'closed', 'closure_reason': 'saga_compensation'}, version=1, inverse=forward)
        self.assertEqual(r.data['operation']['effect'], 'closed')

    def test_wrong_compensation_link_cannot_change_resource(self):
        forward, rid, _ = self.create(); _, other, _ = self.create()
        r = self.send('ticket', 'PATCH', '/tickets/' + other,
            {'status': 'closed', 'closure_reason': 'saga_compensation'}, version=1, inverse=forward)
        self.assertEqual(r.status, 409)
        self.assertEqual(self.send('ticket', 'GET', '/tickets/' + rid).data['ticket']['version'], 1)

    def mail(self, scope='internal', **kwargs):
        return self.send('mail', 'POST', '/send', {'scope': scope,
            'to': ['employee@reference.invalid'] if scope == 'internal' else ['customer@reference.invalid'],
            'subject': 'Synthetic reference', 'body': 'Plain text only', **kwargs})

    def test_mail_allowlist_scope_attachments_and_no_partial_capture(self):
        for kwargs in ({'to': ['someone@example.com']}, {'cc': ['someone@example.com']},
                       {'attachments': ['/private/file']}, {'to': ['customer@reference.invalid']},
                       {'to': ['employee@reference.invalid'] * 2}):
            self.assertEqual(self.mail(**kwargs).status, 422)
        self.assertEqual(self.evidence('mail')['operations'], [])
        r = self.mail(cc=['employee@reference.invalid', 'manager@reference.invalid'])
        self.assertEqual(r.data['recipients'], 2)
        self.assertEqual(r.data['receipt_state'], 'captured')

    def test_internal_recall_and_external_request_are_distinct(self):
        for scope, suffix, status, effect in [('internal', 'recall', 200, 'recalled'),
                ('external', 'recall_requests', 202, 'recall_requested')]:
            r = self.mail(scope)
            op, rid = r.data['operation']['operation_id'], r.data['message_id']
            inverse = self.send('mail', 'POST', '/messages/' + rid + '/' + suffix, {},
                                version=1, inverse=op)
            self.assertEqual(inverse.status, status)
            self.assertEqual(inverse.data['receipt_state'], effect)
            self.assertEqual(self.send('mail', 'GET', '/messages/' + rid).data['version'], 2)

    def test_external_recall_unsupported_is_retained_rejection(self):
        run = uid(); app = make('mail', run, supported=False); self.addCleanup(app.store.db.close)
        r = call(app, run, 'POST', '/send', {'scope': 'external', 'to': ['customer@reference.invalid'],
                                          'subject': 'synthetic', 'body': 'fixture'})
        oid, rid = r.data['operation']['operation_id'], r.data['message_id']; inverse = uid()
        r = call(app, run, 'POST', '/messages/' + rid + '/recall_requests', {}, oid=inverse,
                 version=1, inverse=oid)
        self.assertEqual(r.status, 501)
        self.assertEqual(call(app, run, 'GET', '/operations/' + inverse).data[
            'operation']['error_code'], 'UNSUPPORTED')
        self.assertEqual(call(app, run, 'GET', '/messages/' + rid).data['receipt_state'], 'captured')

    def arm(self, oid, phase, mode, service='ticket'):
        return self.send(service, 'POST', '/control/v1/runs/' + self.run_id + '/faults',
                         dict(operation_id=oid, attempt=1, phase=phase, mode=mode),
                         token=OPERATOR, control=True)

    def test_post_commit_faults_query_original_receipt_and_do_not_duplicate(self):
        for mode in ('503', '429', 'drop', 'delay', 'malformed', 'wrong_receipt', 'redirect'):
            oid = uid(); self.assertEqual(self.arm(oid, 'after_commit', mode).status, 201)
            self.send('ticket', 'POST', '/tickets', {'title': mode}, oid=oid)
            query = self.send('ticket', 'GET', '/operations/' + oid)
            self.assertEqual(query.data['operation']['operation_id'], oid)
            self.assertEqual(query.data['operation']['state'], 'committed')
            replay = self.send('ticket', 'POST', '/tickets', {'title': mode}, oid=oid)
            self.assertEqual(replay.data, query.data['result'])
            self.assertEqual(replay.headers['Idempotency-Replayed'], 'true')
        self.assertEqual(len(self.evidence('ticket')['operations']), 7)

    def test_pre_commit_fault_has_no_effect_and_safe_same_key_resume(self):
        for mode in ('503', '429', 'drop', 'delay', 'pending'):
            oid = uid(); self.arm(oid, 'before_commit', mode)
            self.send('ticket', 'POST', '/tickets', {'title': mode}, oid=oid)
            query = self.send('ticket', 'GET', '/operations/' + oid)
            self.assertEqual(query.data['operation']['state'], 'pending')
            self.assertIsNone(query.data['result'])
            self.assertEqual(self.send('ticket', 'POST', '/tickets', {'title': mode}, oid=oid).status, 201)

    def test_faults_are_operator_only_immutable_and_not_title_triggered(self):
        oid = uid(); self.assertEqual(self.arm(oid, 'after_commit', '503').status, 201)
        self.assertEqual(self.arm(oid, 'after_commit', '503').status, 409)
        _, _, result = self.create(title='timeout fail reset 503')
        self.assertEqual(result.status, 201)
        data = json.dumps(self.evidence('ticket'))
        self.assertNotIn(TOKEN, data); self.assertNotIn(OPERATOR, data)

    def test_transaction_error_rolls_back_resource_and_keeps_pending(self):
        app = self.apps['ticket']; original = app.store.put
        def fail(*args):
            original(*args)
            raise RuntimeError('PRIVATE_SECRET')
        oid = uid()
        with patch.object(app.store, 'put', side_effect=fail):
            result = self.send('ticket', 'POST', '/tickets', {'title': 'x'}, oid=oid)
        self.assertEqual(result.status, 503); self.assertNotIn('PRIVATE_SECRET', repr(result))
        self.assertFalse(any(r['kind'] == 'tickets' for r in self.evidence('ticket')['resources']))
        self.assertEqual(self.send('ticket', 'GET', '/operations/' + oid).data['operation']['state'], 'pending')
        self.assertEqual(self.send('ticket', 'POST', '/tickets', {'title': 'x'}, oid=oid).status, 201)

    def test_sqlite_reopen_identity_and_receipt_model_not_disk_durability(self):
        oid, _, first = self.create()
        old = self.apps['ticket'].store
        reopened = Store(old.db, 'ticket', old.store_id)
        self.assertEqual(json.loads(reopened.operation(self.run_id, 'application', oid)['result']), first.data)
        with self.assertRaises(ValueError): Store(old.db, 'mail', old.store_id)
        with self.assertRaises(ValueError): Store(old.db, 'ticket', uid())
        with self.assertRaises(ValueError): Store(old.db, 'ticket', old.store_id, initialize=True)

    def test_analysis_snapshot_pages_range_and_source_agreement(self):
        first = self.send('crm', 'GET', '/analysis/orders?limit=1').data
        sid, cursor = first['snapshot_id'], first['next_cursor']
        second = self.send('crm', 'GET', '/analysis/orders?limit=1&snapshot_id=' + sid + '&cursor=' + cursor).data
        self.assertEqual(first['total'], 2); self.assertIsNone(second['next_cursor'])
        self.assertEqual(first['items'][0]['amount_minor'],
                         self.send('crm', 'GET', '/orders/O001').data['order']['amount_minor'])
        customers = self.send('crm', 'GET', '/analysis/customers?snapshot_id=' + sid).data
        self.assertEqual(customers['as_of'], first['as_of'])
        self.assertEqual(self.send('crm', 'GET', '/analysis/orders?snapshot_id=wrong').status, 409)
        self.assertEqual(self.send('crm', 'GET', '/analysis/customers?snapshot_id=' + sid + '&cursor=' + cursor).status, 409)
        empty = self.send('crm', 'GET', '/analysis/orders?start_date=2027-01-01&end_date=2027-01-31').data
        self.assertEqual(empty['total'], 0)
        changed = self.send('crm', 'GET', '/analysis/orders?snapshot_id=' + sid + '&start_date=2027-01-01&end_date=2027-01-31')
        self.assertEqual(changed.status, 409)

    def test_new_fixture_changes_query_and_analytics_without_overwriting_run(self):
        other = uid(); app = make('crm', other, variant='variant'); self.addCleanup(app.store.db.close)
        query = call(app, other, 'GET', '/orders/O001').data['order']
        analytics = call(app, other, 'GET', '/analysis/orders').data['items'][0]
        self.assertEqual(query['amount_minor'], analytics['amount_minor'])
        self.assertEqual(query['amount_minor'], 240100)
        with self.assertRaises(Rejected):
            app.store.provision(dict(run_id=other, principal='application', users=['test-user'], fixture='baseline'))

    def test_http_handler_fault_encoding_is_explicit_without_listeners(self):
        handler = object.__new__(Handler)
        handler.server = NS(control=False); handler.wfile = io.BytesIO()
        handler.connection = Mock(); handler.send_response = Mock()
        handler.send_header = Mock(); handler.end_headers = Mock()
        from reference_service.contract import Response
        handler.respond(Response(201, {'ok': True}, fault='malformed'))
        self.assertEqual(handler.wfile.getvalue(), b'{invalid')
        handler.respond(Response(201, {}, fault='drop'))
        handler.connection.shutdown.assert_called_once()
        with patch('reference_service.server.time.sleep') as sleep:
            handler.respond(Response(201, {}, fault='delay')); sleep.assert_called_once_with(6)

    def test_oversized_receipt_rolls_back_effect_and_retains_rejection(self):
        store = self.apps['ticket'].store
        original = store.apply
        def oversized(*args):
            result, status, rid, effect, before = original(*args)
            result['excess'] = 'x' * 65536
            return result, status, rid, effect, before
        oid = uid()
        with patch.object(store, 'apply', oversized):
            response = self.send('ticket', 'POST', '/tickets', {'title': 'test'}, oid=oid)
        self.assertEqual(response.status, 422)
        self.assertEqual([r for r in self.evidence('ticket')['resources'] if r['kind'] == 'tickets'], [])
        receipt = self.send('ticket', 'GET', '/operations/' + oid).data['operation']
        self.assertEqual(receipt['state'], 'rejected')
        self.assertEqual(receipt['effect'], 'none')
        self.assertNotIn('before', receipt)

    def test_terminal_recheck_prevents_reapplying_between_registration_and_effect(self):
        store = self.apps['ticket'].store
        from contextlib import contextmanager
        transaction = store.transaction
        intercepted = False
        @contextmanager
        def interleave():
            nonlocal intercepted
            with transaction():
                yield
            if not intercepted:
                intercepted = True
                row = store.db.execute('SELECT * FROM operations').fetchone()
                with patch.object(store, 'transaction', transaction):
                    store.mutate(self.run_id, 'application', row['operation_id'], uid(),
                                 json.loads(row['request']))
        with patch.object(store, 'transaction', interleave), patch.object(store, 'apply', wraps=store.apply) as apply:
            result = self.send('ticket', 'POST', '/tickets', {'title': 'interleaved'})
        self.assertEqual(result.status, 201)
        self.assertEqual(apply.call_count, 1)
        self.assertEqual(result.headers['Idempotency-Replayed'], 'true')

    def test_analysis_customers_require_snapshot(self):
        self.assertEqual(self.send('crm', 'GET', '/analysis/customers').status, 409)

    def test_handler_rejects_duplicate_headers_chunking_and_short_body(self):
        from email.message import Message
        for values, raw in (([('Content-Length', '0'), ('Content-Length', '0')], b''),
                            ([('Transfer-Encoding', 'chunked')], b''),
                            ([('Content-Length', '65537')], b''),
                            ([('Content-Length', '3')], b'xx')):
            handler = object.__new__(Handler); handler.headers = Message()
            for key, value in values: handler.headers[key] = value
            handler.path = '/api/v1/tickets'; handler.rfile = io.BytesIO(raw)
            handler.send_error = Mock(); handler.server = Mock()
            handler.process()
            handler.send_error.assert_called_once_with(422)
            handler.server.service.handle.assert_not_called()


class AdapterTests(BASE['SafetyTests']):
    def setUp(self):
        super().setUp()
        self.settings.tool_reference_principal = 'application'
        for service in ('crm', 'ticket', 'mail'):
            setattr(self.settings, service + '_api_token', TOKEN)
        self.apps = {name: make(name, self.settings.tool_reference_run_id) for name in ('crm', 'ticket', 'mail')}
        for app in self.apps.values(): self.addCleanup(app.store.db.close)

    async def test_actual_client_forward_inverse_receipts_match_independent_service(self):
        params = {'create_ticket': {'title': 'ticket'},
                  'create_crm_task': {'customer_id': 'C001', 'title': 'task'},
                  'send_email_internal': {'to': ['employee@reference.invalid'], 'subject': 'x', 'body': 'x'},
                  'send_email_external': {'to': ['customer@reference.invalid'], 'subject': 'x', 'body': 'x'}}
        for name, body in params.items():
            wire = self.ref.wire(name, body, 'test-user'); oid = uid()
            service = self.ref.SERVICES[name]
            response = call(self.apps[service], self.settings.tool_reference_run_id,
                wire['method'], wire['path'], wire['body'], oid=oid)
            row = {'operation_id': oid, 'intent': {'tool': name, 'params': body, 'target':
                {'run_id': self.settings.tool_reference_run_id, 'service': service}}, 'request': wire}
            row['receipt'] = self.ref.receipt(response.data, row)
            inverse = {'operation_id': uid(), 'request': self.ref.inverse_wire(row)}
            req = inverse['request']
            result = call(self.apps[service], self.settings.tool_reference_run_id,
                req['method'], req['path'], req['body'], oid=inverse['operation_id'], version=1, inverse=oid)
            self.assertEqual(self.ref.inverse_receipt(result.data, inverse, row), result.data)

    async def test_actual_client_update_restore_and_rejection_receipts(self):
        app = self.apps['ticket']; run = self.settings.tool_reference_run_id
        create = call(app, run, 'POST', '/tickets', {'title': 'x'}); rid = create.data['ticket']['ticket_id']
        params = {'ticket_id': rid, 'comment': 'retained', 'priority': 'urgent'}
        wire = self.ref.wire('update_ticket', params, 'test-user'); wire['if_match'] = '"1"'
        oid = uid(); result = call(app, run, 'PATCH', wire['path'], wire['body'], oid=oid, version=1)
        row = {'operation_id': oid, 'intent': {'tool': 'update_ticket', 'params': params,
            'target': {'run_id': run, 'service': 'ticket'}}, 'request': wire}
        row['receipt'] = self.ref.receipt(result.data, row)
        inverse = {'operation_id': uid(), 'request': self.ref.inverse_wire(row)}
        result = call(app, run, 'PATCH', wire['path'], inverse['request']['body'],
                      oid=inverse['operation_id'], version=2, inverse=oid)
        self.ref.inverse_receipt(result.data, inverse, row)
        inverse['operation_id'] = uid()
        call(app, run, 'PATCH', wire['path'], inverse['request']['body'],
             oid=inverse['operation_id'], version=2, inverse=oid)
        result = call(app, run, 'GET', '/operations/' + inverse['operation_id'])
        self.assertTrue(self.ref.rejected(result.data, {**inverse, 'intent': row['intent']}, inverse=True))

    async def test_actual_request_sends_json_headers_for_reads_and_bodyless_inverse(self):
        config = {'run_id': self.settings.tool_reference_run_id, 'service': 'crm',
                  'endpoint': self.settings.crm_api_base}
        async def transport(method, url, **kwargs):
            headers = kwargs['extra_headers']
            self.assertEqual(headers['Accept'], 'application/json')
            if method != 'GET': self.assertEqual(headers['Content-Type'], 'application/json')
            kwargs['meta'].update(profile=PROFILE, status=200)
            return True, {}, None
        with patch.object(self.ref, 'call_external_api', transport):
            await self.real_request(config, 'GET', '/customers/C001')
            await self.real_request(config, 'DELETE', '/crm_tasks/T1', operation_id=uid(),
                                    if_match='"1"', compensates_operation_id=uid())


    async def test_gateway_reconciles_real_reference_postcommit_loss(self):
        await self.prepare()
        oid = self.context['operation_id']
        app = self.apps['ticket']
        app.store.install_fault(self.settings.tool_reference_run_id, {
            'operation_id': oid, 'attempt': 1, 'phase': 'after_commit', 'mode': '503'})

        async def transport(method, url, **kwargs):
            from urllib.parse import urlsplit
            parsed = urlsplit(url)
            headers = {k.lower(): v for k, v in kwargs['extra_headers'].items()}
            headers.update(authorization='Bearer ' + kwargs['api_token'], **{'x-request-id': uid()})
            raw = canonical(kwargs['json_body']).encode() if kwargs['json_body'] is not None else b''
            response = app.handle(method, parsed.path, headers, raw)
            kwargs['meta'].update(profile=PROFILE, status=response.status)
            return response.status < 300, response.data, None if response.status < 300 else 'EXTERNAL_HTTP_503'

        with patch.object(self.ref, 'request', self.real_request), patch.object(
                self.ref, 'call_external_api', transport):
            first = await self.tool.invoke({'title': 'test'}, self.context)
            again = await self.tool.invoke({'title': 'test'}, self.context)
        self.assertTrue(first.success, first)
        self.assertTrue(again.success)
        evidence = app.store.evidence(self.settings.tool_reference_run_id)
        self.assertEqual(len(evidence['operations']), 1)
        self.assertEqual(len([r for r in evidence['resources'] if r['kind'] == 'tickets']), 1)
        self.assertEqual(self.db.operations[oid]['state'], 'committed')

    async def test_admin_profile_requires_isolated_http_credentials_and_auth(self):
        helper = BASE['load']('app.core.reference_evidence', 'app/core/reference_evidence.py')
        self.settings.auth_require_password = self.settings.auth_check_db = True
        for service in ('crm', 'ticket', 'mail'):
            setattr(self.settings, service + '_api_token', TOKEN + service)
        getter = lambda name: self.tool
        profile = helper.configuration(self.settings, getter)
        self.assertEqual(profile['status'], 'CONFIGURED')
        self.assertNotIn(TOKEN, canonical(profile))
        self.settings.auth_check_db = False
        self.assertEqual(helper.configuration(self.settings, getter)['status'], 'BLOCKED')
        self.settings.auth_check_db = True
        self.settings.crm_api_base = 'https://unrelated.invalid/api/v1'
        self.assertEqual(helper.configuration(self.settings, getter)['status'], 'BLOCKED')
        self.assertEqual(helper.configuration(self.settings, lambda name: None)['status'], 'BLOCKED')

    async def test_admin_evidence_parameterizes_bounds_and_omits_payload(self):
        helper = BASE['load']('app.core.reference_evidence', 'app/core/reference_evidence.py')
        sql_seen = []
        async def execute(sql, params):
            sql_seen.append(sql)
            self.assertEqual(params, {'sid': 'session'})
            self.assertIn('LIMIT 201', sql)
            rows = [{'operation_id': uid(), 'request': {'body': 'synthetic-private-body'}}] if 'o.request' in sql else []
            return NS(mappings=lambda: NS(all=lambda: rows))
        result = await helper.collect(NS(execute=execute), 'session')
        self.assertEqual(len(sql_seen), 6)
        self.assertFalse(result['snapshot_atomic'])
        self.assertNotIn('synthetic-private-body', canonical(result))
        self.assertEqual(len(result['operations'][0]['request_hash']), 64)
        with self.assertRaises(Exception): await helper.collect(NS(execute=execute), "' OR true")
        oversized = NS(execute=AsyncMock(return_value=NS(mappings=lambda: NS(all=lambda: [{}] * 201))))
        with self.assertRaisesRegex(ValueError, 'REFERENCE_EVIDENCE_LIMIT'):
            await helper.collect(oversized, 'session')

    async def test_actual_analysis_reader_consumes_independent_snapshot(self):
        analysis = BASE['load']('app.tools.analysis_data', 'app/tools/analysis_data.py')
        async def request(config, method, path, **kwargs):
            response = call(self.apps['crm'], self.settings.tool_reference_run_id, method, path)
            return response.status == 200, response.data, None, {'status': response.status}
        reader = analysis.AnalysisReader('test-user', 'manager', 'synthetic')
        with patch.object(analysis, 'authorize', AsyncMock(return_value=True)), patch.object(
                self.ref, 'request', request), patch.object(analysis, 'PAGE_SIZE', 1):
            orders, identity = await reader._pages({'run_id': self.settings.tool_reference_run_id},
                'orders', {'start_date': None, 'end_date': None}, None)
            customers, final = await reader._pages({'run_id': self.settings.tool_reference_run_id},
                'customers', {'start_date': None, 'end_date': None}, identity)
        self.assertEqual(sum(row['amount_minor'] for row in orders), 130049)
        self.assertEqual(len(customers), 2)
        self.assertEqual(final, identity)


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        from reference_service import acceptance
        self.acceptance = acceptance
        self.plan = json.loads(acceptance.DEFAULT_PLAN.read_bytes())
        self.run_id = uid()
        self.env = {'REFERENCE_CANDIDATE_COMMIT': 'a' * 40,
                    'BUSINESSAGENT_IMAGE': 'synthetic/app@sha256:' + 'b' * 64,
                    'REFERENCE_IMAGE': 'synthetic/ref@sha256:' + 'c' * 64,
                    'REFERENCE_OPERATOR_TOKEN': OPERATOR, 'TOOL_REFERENCE_RUN_ID': self.run_id,
                    'TOOL_REFERENCE_PRINCIPAL': 'application'}
        for service in ('crm', 'ticket', 'mail'):
            self.env['REFERENCE_' + service.upper() + '_STORE_ID'] = uid()
        for actor in ('ADMIN', 'REQUESTER', 'APPROVER'):
            self.env['APP_' + actor + '_USERNAME'] = actor
            self.env['APP_' + actor + '_PASSWORD'] = 'synthetic-private-password'
        self.calls = []
        self.approval = 'pending'
        self.ambiguous = False
        self.store_mismatch = False

    def request(self, target, method, path, token=None, body=None):
        self.calls.append((target, method, path, body))
        if path.endswith('/auth/login'):
            actor = body['username']
            return 200, {'access_token': 'synthetic-private-jwt-' + actor, 'user_id': actor,
                         'role': 'admin' if actor == 'ADMIN' else 'manager', 'department': 'synthetic'}
        if path.endswith('/reference-profile'):
            return 200, {'data': {'status': 'CONFIGURED', 'run_id': self.run_id, 'principal': 'application'}}
        if path == '/control/v1/runs': return 201, {}
        if target != 'app':
            return 200, {'service': target, 'run_id': self.run_id, 'principal': 'application',
                'store_id': uid() if self.store_mismatch else self.env['REFERENCE_' + target.upper() + '_STORE_ID'],
                'schema': SCHEMA, 'fixture_hash': 'd' * 64, 'operations': []}
        if '/reference-evidence/' in path:
            approvals = [{'approval_id': 'approval-1', 'requester_id': 'REQUESTER',
                          'operation_type': 'send_email_external', 'status': self.approval}]
            if self.ambiguous: approvals += [{**approvals[0], 'approval_id': 'approval-2'}]
            return 200, {'data': {'operations': [], 'approvals': approvals, 'steps': [], 'audit': []}}
        if path.endswith('/decide'):
            self.approval = 'approved_pending_reauth'
            return 200, {'decided': True}
        if path.endswith('/resume'): return 200, {'resumed': True}
        return 200, {'session_id': 'synthetic-session', 'reply': 'synthetic-private-jwt-REQUESTER'}

    def test_transcript_uses_real_entry_routes_and_never_closes_cases(self):
        report = self.acceptance.run(self.plan, self.env, self, provision=True)
        self.assertEqual(report['transcript_status'], 'EXECUTED', report)
        self.assertTrue(all(s['status'] == 'OBSERVED' for s in report['steps']))
        self.assertEqual(set(report['runtime_cases'].values()), {'BLOCKED'})
        self.assertFalse(report['release_allowed'])
        self.assertTrue(any('/approval/approval-1/decide' in c[2] for c in self.calls))
        self.assertTrue(any('/pending-executions/approval-1/resume' in c[2] for c in self.calls))
        for secret in (OPERATOR, 'synthetic-private-jwt', 'synthetic-private-password'):
            self.assertNotIn(secret, canonical(report))

    def test_ambiguous_approval_stops_before_decision(self):
        self.ambiguous = True
        report = self.acceptance.run(self.plan, self.env, self)
        self.assertEqual(report['transcript_status'], 'BLOCKED')
        self.assertFalse(any(c[2].endswith('/decide') for c in self.calls))
        self.assertEqual(report['steps'][-1]['status'], 'NOT_RUN')

    def test_store_mismatch_stops_before_any_business_message(self):
        self.store_mismatch = True
        report = self.acceptance.run(self.plan, self.env, self)
        self.assertEqual(report['transcript_status'], 'BLOCKED')
        self.assertFalse(any(c[2].endswith('/chat/message') for c in self.calls))

    def test_incomplete_config_does_not_login_or_provision(self):
        self.env.pop('REFERENCE_CRM_STORE_ID')
        report = self.acceptance.run(self.plan, self.env, self, provision=True)
        self.assertEqual(report['transcript_status'], 'BLOCKED')
        self.assertEqual(self.calls, [])

    def test_plan_rejects_forward_session_reference_and_unknown_keys(self):
        for change in ({'session_step': 'later'}, {'unknown': True}, {'case': 'R21'}):
            plan = deepcopy(self.plan); plan['steps'][0].update(change)
            with self.assertRaises(ValueError): self.acceptance.validate_plan(plan)

        plan = deepcopy(self.plan)
        plan['steps'].append({'id': 'invalid_fault', 'case': 'R10', 'action': 'fault',
            'session_step': 'query', 'tool': 'create_ticket', 'inverse': False,
            'attempt': 1, 'phase': 'before_commit', 'mode': 'malformed'})
        with self.assertRaisesRegex(ValueError, 'ACCEPTANCE_FAULT_INVALID'):
            self.acceptance.validate_plan(plan)

    def test_default_cli_does_not_construct_client(self):
        with patch.object(sys, 'argv', ['reference-acceptance']), patch.object(
                self.acceptance, 'Client', side_effect=AssertionError('network')), patch('builtins.print'):
            self.assertEqual(self.acceptance.main(), 2)

    def test_bounded_client_reads_final_chunk_without_detached_fp_access(self):
        connection = Mock(); sock = Mock(); connection.sock = sock
        response = Mock(status=200)
        response.isclosed.side_effect = [False, True]
        response.read1.return_value = b'{"confidence":0.75}'
        connection.getresponse.return_value = response
        with patch.object(self.acceptance.http.client, 'HTTPConnection', return_value=connection):
            status, data = self.acceptance.Client().request('app', 'GET', '/health')
        self.assertEqual(data['confidence'], .75)
        connection.close.assert_called_once()
        sock.settimeout.assert_called()

    def test_client_rejects_redirect_and_strict_json(self):
        connection = Mock(); connection.getresponse.return_value = Mock(status=307)
        with patch.object(self.acceptance.http.client, 'HTTPConnection', return_value=connection):
            with self.assertRaisesRegex(ValueError, 'REDIRECT'):
                self.acceptance.Client().request('app', 'GET', '/health')
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ValueError): self.acceptance.strict_json(raw)

    def test_correlation_flags_hash_mismatch_and_keeps_unknown_unresolved(self):
        oid = uid(); op = dict(operation_id=oid, request_hash='one', state='committed',
                              run_id=self.run_id, service='ticket')
        refs = {'ticket': {'operations': [{'operation': op}]}}
        result = self.acceptance.correlate({'operations': [{**op, 'request_hash': 'two'}]}, refs)
        self.assertEqual(result['status'], 'FAIL')
        result = self.acceptance.correlate({'operations': [{**op, 'state': 'unknown'}]}, refs)
        self.assertEqual(result['unresolved_forward_ids'], [oid])

    def test_new_admin_routes_require_admin_in_actual_source(self):
        import ast
        source = ast.parse((ROOT / 'app/api/admin.py').read_text())
        for name in ('get_reference_profile', 'get_reference_evidence'):
            node = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
            self.assertIn('Depends(require_roles(AgentRole.ADMIN))', ast.unparse(node.args))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(cls(name) for cls in (ReferenceTests, AdapterTests, AcceptanceTests)
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
