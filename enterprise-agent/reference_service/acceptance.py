"""Opt-in application transcript and independent ledger capture; never auto-closes R01-R20."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from uuid import uuid4

from reference_service.contract import SCHEMA, canonical, identifier, now, uuid4 as valid_uuid

CASES = [f'R{i:02d}' for i in range(1, 21)]
DEFAULT_PLAN = Path(__file__).with_name('application-plan.json')


def strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('ACCEPTANCE_DUPLICATE_KEY')
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError('ACCEPTANCE_NONFINITE_JSON')

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def sanitize(value: Any, secrets: list[str], depth: int = 0) -> Any:
    if depth > 30:
        return '[DEPTH_LIMIT]'
    if isinstance(value, dict):
        return {key: '[REDACTED]' if any(part in key.lower() for part in
                ('token', 'password', 'authorization', 'cookie', 'credential', 'secret'))
                else sanitize(item, secrets, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item, secrets, depth + 1) for item in value]
    if isinstance(value, str):
        for secret in sorted(set(secrets), key=len, reverse=True):
            if secret:
                value = value.replace(secret, '[REDACTED]')
        value = re.sub(r'eyJ[\w-]+\.[\w-]+\.[\w-]+', '[REDACTED]', value)
        return re.sub(r'(?i)Bearer\s+[^\s"<>;,]+', 'Bearer [REDACTED]', value)
    return value


class Client:
    def __init__(self) -> None:
        self.targets = {'app': ('api', 8000), **{
            name: ('reference-' + name, 8081) for name in ('crm', 'ticket', 'mail')}}

    def request(self, target: str, method: str, path: str, token: str | None = None,
                body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        host, port = self.targets[target]
        if not path.startswith('/') or '://' in path or any(c in path for c in '\r\n'):
            raise ValueError('ACCEPTANCE_PATH_INVALID')
        budget = 180 if target == 'app' else 30
        connection = http.client.HTTPConnection(host, port, timeout=budget)
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json',
                   'X-Request-Id': str(uuid4()), 'Connection': 'close'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        deadline = time.monotonic() + budget
        try:
            connection.request(method, path, body=canonical(body).encode() if body is not None else None,
                               headers=headers)
            sock = connection.sock
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            sock.settimeout(remaining)
            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise ValueError('ACCEPTANCE_REDIRECT_DENIED')
            chunks = bytearray()
            while not response.isclosed():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                sock.settimeout(remaining)
                part = response.read1(65536)
                if not part:
                    break
                chunks.extend(part)
                if len(chunks) > 8 * 1024 * 1024:
                    raise ValueError('ACCEPTANCE_RESPONSE_LIMIT')
            data = strict_json(bytes(chunks))
            if not isinstance(data, dict):
                raise ValueError('ACCEPTANCE_RESPONSE_INVALID')
            return response.status, data
        finally:
            connection.close()


def validate_plan(plan: dict[str, Any]) -> None:
    if set(plan) != {'schema', 'steps'} or plan['schema'] != 'reference-transcript-v1':
        raise ValueError('ACCEPTANCE_PLAN_INVALID')
    if not isinstance(plan['steps'], list) or not 1 <= len(plan['steps']) <= 50:
        raise ValueError('ACCEPTANCE_PLAN_INVALID')
    ids = set()
    for step in plan['steps']:
        identifier(step['id'])
        if step['id'] in ids or step['case'] not in CASES:
            raise ValueError('ACCEPTANCE_PLAN_INVALID')
        common = {'id', 'case', 'action', 'session_step'}
        extra = {'message': {'text'}, 'decide': {'decision'}, 'resume': set(),
                 'observe': set(), 'fault': {'tool', 'inverse', 'attempt', 'phase', 'mode'}}
        if step['action'] not in extra or set(step) - common - extra[step['action']]:
            raise ValueError('ACCEPTANCE_PLAN_INVALID')
        if 'session_step' in step and step['session_step'] not in ids:
            raise ValueError('ACCEPTANCE_SESSION_INVALID')
        if step['action'] != 'message' and 'session_step' not in step:
            raise ValueError('ACCEPTANCE_SESSION_INVALID')
        if step['action'] == 'message' and (not isinstance(step.get('text'), str)
                                           or not 1 <= len(step['text']) <= 2000):
            raise ValueError('ACCEPTANCE_MESSAGE_INVALID')
        if step['action'] == 'decide' and step.get('decision') not in {'approved', 'rejected'}:
            raise ValueError('ACCEPTANCE_DECISION_INVALID')
        if step['action'] == 'fault':
            modes = {'before_commit': {'503', '429', 'drop', 'delay', 'pending'},
                     'after_commit': {'503', '429', 'drop', 'delay', 'malformed',
                                      'wrong_receipt', 'redirect'}}
            if (not isinstance(step.get('tool'), str) or type(step.get('inverse')) is not bool
                    or type(step.get('attempt')) is not int or not 1 <= step['attempt'] <= 100
                    or step.get('phase') not in {'before_commit', 'after_commit'}
                    or step.get('mode') not in modes[step['phase']]):
                raise ValueError('ACCEPTANCE_FAULT_INVALID')
        ids.add(step['id'])


def correlate(application: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    receipts = {entry['operation']['operation_id']: entry['operation']
                for service in reference.values() for entry in service['operations']}
    matched, mismatches, unresolved = [], [], []
    for row in application.get('operations', []):
        oid = row['operation_id']
        op = receipts.get(oid)
        if op is None or row['state'] in {'prepared', 'dispatched', 'unknown'}:
            unresolved.append(oid)
        elif (row['state'] != op['state'] or row['request_hash'] != op['request_hash']
              or row['run_id'] != op['run_id'] or row['service'] != op['service']):
            mismatches.append(oid)
        else:
            matched.append(oid)
    return {'matched_forward_ids': matched, 'mismatched_forward_ids': mismatches,
            'unresolved_forward_ids': unresolved,
            'audit_rows_observed': len(application.get('audit', [])),
            'status': 'FAIL' if mismatches else 'OBSERVED',
            'semantic_and_fault_acceptance': 'BLOCKED'}


def run(plan: dict[str, Any], env: dict[str, str], client: Any,
        *, provision: bool = False) -> dict[str, Any]:
    validate_plan(plan)
    report: dict[str, Any] = {
        'schema': 'reference-acceptance-v1', 'started_at': now(), 'plan': plan,
        'candidate_commit': env.get('REFERENCE_CANDIDATE_COMMIT'),
        'application_image': env.get('BUSINESSAGENT_IMAGE'), 'reference_image': env.get('REFERENCE_IMAGE'),
        'image_identity_verification': 'OPERATOR_REQUIRED',
        'runtime_cases': {case: 'BLOCKED' for case in CASES},
        'steps': [{'id': s['id'], 'status': 'NOT_RUN'} for s in plan['steps']],
        'status': 'BLOCKED', 'formal_uat': False, 'release_evidence': False, 'release_allowed': False}
    secrets = [value for key, value in env.items() if any(part in key for part in ('TOKEN', 'PASSWORD'))]
    sessions: dict[str, str] = {}
    observations: dict[str, Any] = {}
    identities: dict[str, Any] = {}
    tokens: dict[str, str] = {}
    operator = env.get('REFERENCE_OPERATOR_TOKEN', '')
    try:
        if (not re.fullmatch(r'[a-f0-9]{40}', report['candidate_commit'] or '')
                or any(not re.fullmatch(r'[^\s]+@sha256:[a-f0-9]{64}', report[k] or '')
                       for k in ('application_image', 'reference_image')) or len(operator) < 32):
            raise ValueError('ACCEPTANCE_CONFIG_INVALID')
        store_ids = {name: valid_uuid(env['REFERENCE_' + name.upper() + '_STORE_ID'])
                     for name in ('crm', 'ticket', 'mail')}
        if len(set(store_ids.values())) != 3:
            raise ValueError('ACCEPTANCE_STORE_IDENTITY_INVALID')
        for actor in ('ADMIN', 'REQUESTER', 'APPROVER'):
            status, data = client.request('app', 'POST', '/api/v1/auth/login', body={
                'username': env['APP_' + actor + '_USERNAME'],
                'password': env['APP_' + actor + '_PASSWORD']})
            if status != 200 or not isinstance(data.get('access_token'), str):
                raise ValueError('ACCEPTANCE_LOGIN_FAILED')
            tokens[actor] = data['access_token']; secrets.append(data['access_token'])
            identities[actor] = {key: data[key] for key in ('user_id', 'role', 'department')}
        if (identities['ADMIN']['role'] != 'admin'
                or identities['REQUESTER']['user_id'] == identities['APPROVER']['user_id']):
            raise ValueError('ACCEPTANCE_IDENTITIES_INVALID')
        status, data = client.request('app', 'GET', '/api/v1/admin/reference-profile', tokens['ADMIN'])
        profile = data.get('data', {})
        if status != 200 or profile.get('status') != 'CONFIGURED':
            raise ValueError('ACCEPTANCE_PROFILE_REQUIRED')
        run_id = profile['run_id']
        if run_id != env.get('TOOL_REFERENCE_RUN_ID') or profile['principal'] != env.get('TOOL_REFERENCE_PRINCIPAL'):
            raise ValueError('ACCEPTANCE_RUN_MISMATCH')
        report.update(profile=profile, identities=identities)
        for service in ('crm', 'ticket', 'mail'):
            if provision:
                status, _ = client.request(service, 'POST', '/control/v1/runs', operator, {
                    'run_id': run_id, 'principal': profile['principal'],
                    'users': sorted({identity['user_id'] for identity in identities.values()}),
                    'fixture': env.get('REFERENCE_FIXTURE', 'baseline')})
                if status != 201:
                    raise ValueError('ACCEPTANCE_FRESH_RUN_REQUIRED')
        fixture_hashes: dict[str, str] = {}

        def reference_evidence() -> dict[str, Any]:
            result = {}
            for service in ('crm', 'ticket', 'mail'):
                status, data = client.request(service, 'GET',
                    '/control/v1/runs/' + run_id + '/evidence', operator)
                if status != 200 or data.get('run_id') != run_id or data.get('principal') != profile['principal']:
                    raise ValueError('ACCEPTANCE_REFERENCE_EVIDENCE_FAILED')
                if (data.get('service') != service or data.get('schema') != SCHEMA
                        or data.get('store_id') != store_ids[service]
                        or not re.fullmatch(r'[a-f0-9]{64}', data.get('fixture_hash', ''))
                        or fixture_hashes.get(service, data['fixture_hash']) != data['fixture_hash']):
                    raise ValueError('ACCEPTANCE_STORE_IDENTITY_CHANGED')
                fixture_hashes[service] = data['fixture_hash']
                result[service] = data
            return result
        report['reference_before'] = reference_evidence()
        for index, step in enumerate(plan['steps']):
            record = report['steps'][index]
            record['status'] = 'STARTED'
            action = step['action']
            sid = sessions.get(step.get('session_step', ''))
            if action == 'message':
                body = {'message': step['text']}
                if sid:
                    body['session_id'] = sid
                status, data = client.request('app', 'POST', '/api/v1/chat/message', tokens['REQUESTER'], body)
                if status != 200:
                    raise ValueError('ACCEPTANCE_MESSAGE_FAILED')
                sid = identifier(data['session_id'])
            else:
                if sid is None:
                    raise ValueError('ACCEPTANCE_SESSION_REQUIRED')
                status, envelope = client.request('app', 'GET',
                    '/api/v1/admin/reference-evidence/' + sid, tokens['ADMIN'])
                if status != 200:
                    raise ValueError('ACCEPTANCE_APP_EVIDENCE_FAILED')
                observed = envelope['data']
                if action in {'decide', 'resume'}:
                    expected = 'pending' if action == 'decide' else 'approved_pending_reauth'
                    candidates = [row for row in observed['approvals']
                        if row['status'] == expected and row['requester_id'] == identities['REQUESTER']['user_id']
                        and row['operation_type'] == 'send_email_external']
                    if len(candidates) != 1:
                        raise ValueError('ACCEPTANCE_APPROVAL_AMBIGUOUS')
                    aid = identifier(candidates[0]['approval_id'])
                    path = ('/api/v1/approval/' + aid + '/decide' if action == 'decide' else
                            '/api/v1/pending-executions/' + aid + '/resume')
                    actor = 'APPROVER' if action == 'decide' else 'REQUESTER'
                    body = ({'decision': step['decision'],
                             'comment': 'Controlled reference acceptance'}
                            if action == 'decide' else None)
                    status, data = client.request('app', 'POST', path, tokens[actor], body)
                    if status != 200:
                        raise ValueError('ACCEPTANCE_APPROVAL_FAILED')
                elif action == 'fault':
                    candidates = [row for row in observed['operations'] if row['tool'] == step['tool']]
                    if len(candidates) != 1:
                        raise ValueError('ACCEPTANCE_OPERATION_AMBIGUOUS')
                    selected = candidates[0]; oid = selected['operation_id']
                    if step['inverse']:
                        inverses = [row for row in observed['steps'] if row['operation_id'] == oid]
                        if len(inverses) != 1:
                            raise ValueError('ACCEPTANCE_INVERSE_NOT_PREPARED')
                        oid = inverses[0]['compensation_id']
                    status, data = client.request(selected['service'], 'POST',
                        '/control/v1/runs/' + run_id + '/faults', operator,
                        {'operation_id': oid, **{key: step[key] for key in ('attempt', 'phase', 'mode')}})
                    if status != 201:
                        raise ValueError('ACCEPTANCE_FAULT_FAILED')
                else:
                    data = {'observed': True}
            sessions[step['id']] = sid
            status, envelope = client.request('app', 'GET', '/api/v1/admin/reference-evidence/' + sid,
                                              tokens['ADMIN'])
            if status != 200:
                raise ValueError('ACCEPTANCE_APP_EVIDENCE_FAILED')
            refs = reference_evidence()
            observations[step['id']] = {'application': envelope['data'], 'reference': refs}
            record.update(status='OBSERVED', response=data,
                          correlation=correlate(envelope['data'], refs))
        report['transcript_status'] = 'EXECUTED'
    except Exception:
        report['transcript_status'] = 'BLOCKED'
        report['error_code'] = 'ACCEPTANCE_STEP_OR_PREFLIGHT_FAILED'
    report.update(observations=observations, finished_at=now())
    report['remaining_evidence'] = ['R01_R20_INDEPENDENT_RUNTIME_ORACLES',
        'IMAGE_AND_STORE_IDENTITY', 'PROCESS_RESTART_AND_REAL_TRANSPORT_FAILURE',
        'APPLICATION_APPROVAL_SAGA_QUEUE_AUDIT_CORRELATION', 'C10_OPEN', 'C21_DEFERRED']
    return sanitize(report, secrets)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--provision', action='store_true', help='Explicit fresh-run provisioning')
    parser.add_argument('--plan', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    plan_bytes = args.plan.read_bytes()
    plan = strict_json(plan_bytes); validate_plan(plan)
    if not args.execute:
        print(canonical({'status': 'BLOCKED', 'execution': 'NOT_RUN', 'cases': CASES,
                         'steps': len(plan['steps'])}))
        return 2
    if (args.output is None or args.output.exists() or args.output.is_symlink()
            or args.output.suffix != '.json' or not args.output.parent.is_dir()
            or any(parent.is_symlink() for parent in args.output.parents)):
        parser.error('Choose a fresh JSON path in an existing non-symlink directory')
    report = run(plan, dict(os.environ), Client(), provision=args.provision)
    report['plan_sha256'] = hashlib.sha256(plan_bytes).hexdigest()
    report['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(Path(__file__).parent.glob('*.py'))}
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(canonical({'status': report['status'], 'transcript_status': report['transcript_status']}))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
