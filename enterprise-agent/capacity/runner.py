"""Opt-in mixed application workload. No provisioning, retry, cleanup or service launch."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import http.client
import os
from pathlib import Path
import re
import signal
import ssl
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from capacity.contract import (canonical, digest, read_json, require, schedule,
                               strict_json, summarize, validate, write_new)


class MeasurementError(Exception):
    """Only fixed outcome codes may escape to an observation."""


class SSE:
    """Incremental UTF-8 SSE parser; event boundaries, not HTTP chunks, define tokens."""

    def __init__(self) -> None:
        self.pending = b''
        self.lines: list[bytes] = []
        self.final: dict[str, Any] | None = None
        self.first_token_ms: float | None = None
        self.terminal = False

    def feed(self, chunk: bytes, elapsed_ms: float) -> None:
        self.pending += chunk
        require(len(self.pending) <= 1024 * 1024)
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            line = line.removesuffix(b'\r')
            if line:
                if line.startswith(b'data:'):
                    self.lines.append(line[5:].removeprefix(b' '))
                require(sum(map(len, self.lines)) <= 1024 * 1024)
                continue
            if not self.lines:
                continue
            value = strict_json(b'\n'.join(self.lines))
            self.lines = []
            require(isinstance(value, dict) and not self.terminal)
            if value.get('type') in {'error', 'cancelled'}:
                raise MeasurementError('ORACLE_FAILED')
            if value.get('type') == 'token' and isinstance(value.get('data'), str) and value['data']:
                if self.first_token_ms is None:
                    self.first_token_ms = elapsed_ms
            if value.get('type') == 'final':
                require(isinstance(value.get('data'), dict))
                self.final = value['data']
                self.terminal = True

    def finish(self) -> dict[str, Any]:
        require(not self.pending.strip() and not self.lines and self.final is not None)
        return self.final


class Transport:
    """Fixed private-network targets, bounded full wall budgets, no redirects or proxies."""

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout
        self.targets = {'app': ('nginx', 443), 'mail': ('reference-mail', 8081)}
        # Operator-mounted private CA; normal certificate and hostname validation stay enabled.
        self.tls = ssl.create_default_context(cafile=os.environ.get('CAPACITY_CA_FILE'))

    def request(self, target: str, method: str, path: str, token: str | None,
                body: dict[str, Any] | None = None, *, stream: bool = False,
                measurement: dict[str, Any] | None = None) -> tuple[dict[str, Any], float | None]:
        require(target in self.targets and method in {'GET', 'POST'}
                and bool(re.fullmatch(r'/[A-Za-z0-9_/-]+', path)))
        start = time.monotonic()
        deadline = start + self.timeout
        metric = measurement if measurement is not None else {}
        metric.update(status=0, complete=False, elapsed_ms=0)
        connection = None
        headers = {'Accept': 'text/event-stream' if stream else 'application/json',
                   'Content-Type': 'application/json', 'Connection': 'close'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        headers['X-Request-Id'] = str(uuid4())
        try:
            connection = (http.client.HTTPSConnection(*self.targets[target], timeout=self.timeout,
                                                      context=self.tls) if target == 'app' else
                          http.client.HTTPConnection(*self.targets[target], timeout=self.timeout))
            connection.request(method, path, canonical(body).encode('utf-8') if body is not None else None, headers)
            sock = connection.sock
            require(sock is not None)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            sock.settimeout(remaining)
            response = connection.getresponse()
            metric['status'] = response.status
            # Non-200 is a measured HTTP error; never follow Location or echo its body.
            if response.status != 200:
                metric['complete'] = False
                raise MeasurementError('HTTP_ERROR')
            if stream:
                require(response.getheader('Content-Type', '').split(';')[0] == 'text/event-stream')
            parser = SSE() if stream else None
            raw = bytearray()
            total = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                sock.settimeout(remaining)
                part = response.read1(65536)
                if not part:
                    break
                total += len(part)
                require(total <= 8 * 1024 * 1024)
                if parser:
                    parser.feed(part, (time.monotonic() - start) * 1000)
                else:
                    raw.extend(part)
            metric['complete'] = True
            data = parser.finish() if parser else strict_json(raw)
            require(isinstance(data, dict))
            return data, parser.first_token_ms if parser else None
        finally:
            metric['elapsed_ms'] = (time.monotonic() - start) * 1000
            if connection is not None:
                connection.close()


def evidence_oracle(plan: dict[str, Any], app: dict[str, Any], ledger: dict[str, Any],
                    requester: str, approver: str, approval_id: str) -> str:
    """Require one correlated committed external mail and a captured independent receipt."""
    d = plan['dataset']
    require(ledger.get('run_id') == d['reference_run_id']
            and ledger.get('principal') == d['principal']
            and ledger.get('store_id') == d['mail_store_id']
            and ledger.get('fixture_hash') == d['mail_fixture_sha256']
            and ledger.get('service') == 'mail' and ledger.get('schema') == 'reference-store-v1')
    approvals = app.get('approvals', [])
    require(len(approvals) == 1)
    approval = approvals[0]
    require(approval.get('approval_id') == approval_id and approval.get('status') == 'executed'
            and approval.get('requester_id') == requester and approval.get('approver_id') == approver)
    operations = app.get('operations', [])
    require(len(operations) == 1)
    op = operations[0]
    require(op.get('tool') == 'send_email_external' and op.get('state') == 'committed'
            and op.get('service') == 'mail' and op.get('run_id') == d['reference_run_id'])
    matched = [r for r in ledger.get('operations', [])
               if r.get('operation', {}).get('operation_id') == op['operation_id']]
    require(len(matched) == 1)
    receipt = matched[0]
    external = receipt['operation']
    require(external.get('state') == 'committed' and external.get('request_hash') == op['request_hash']
            and external.get('run_id') == d['reference_run_id'] and external.get('service') == 'mail'
            and external.get('effect') == 'captured' and external.get('compensates_operation_id') is None
            and receipt.get('result', {}).get('receipt_state') == 'captured'
            and receipt['result'].get('message_id') == external.get('resource_id')
            and receipt['result'].get('recipients') == 1)
    resource = [r['value'] for r in ledger.get('resources', [])
                if r.get('kind') == 'messages'
                and r.get('value', {}).get('message_id') == external.get('resource_id')]
    require(len(resource) == 1 and resource[0].get('receipt_state') == 'captured'
            and resource[0].get('scope') == 'external'
            and resource[0].get('to') == ['customer@reference.invalid']
            and resource[0].get('cc') == [] and resource[0].get('attachments') == [])
    require(sum(r.get('operation_id') == op['operation_id'] and r.get('phase') == 'committed'
                for r in ledger.get('attempts', [])) == 1)
    require(any(row.get('success') is True and row.get('tool_name') == 'send_email_external'
                for row in app.get('audit', [])))
    require(not app.get('jobs') and not app.get('steps'))  # This frozen mail flow is synchronous.
    return digest({'operation': op, 'receipt': external, 'approval': approval})


def answer_oracle(plan: dict[str, Any], kind: str, data: dict[str, Any]) -> str:
    oracle = plan['oracles'][kind]
    answer = data.get('answer')
    require(isinstance(answer, str) and bool(answer.strip()) and data.get('needs_replan') is False)
    require(data.get('intent') == ('knowledge_qa' if kind == 'qa' else 'data_analysis'))
    require(all(text in answer for text in oracle['required_text']))
    if kind == 'qa':
        sources = data.get('sources', [])
        require(isinstance(sources, list) and bool(sources))
        require(all(isinstance(s, dict) and s.get('document_id') in oracle['source_ids'] for s in sources))
    # Marker/source checks are mechanical. Semantic review remains a separate acceptance gate.
    return digest(data)


class Workload:
    def __init__(self, plan: dict[str, Any], transport: Any, env: dict[str, str]) -> None:
        self.plan = plan
        self.transport = transport
        self.env = env
        self.tokens: dict[str, str] = {}
        self.ids: dict[str, str] = {}
        self.stop = threading.Event()
        self.operator = env.get('CAPACITY_OPERATOR_TOKEN', '')

    def preflight(self) -> None:
        require(len(self.operator) >= 32)
        actors = ['ADMIN', 'APPROVER'] + [f'REQUESTER_{i}' for i in range(
            self.plan['workload']['concurrency'])]
        for actor in actors:
            username = self.env['CAPACITY_' + actor + '_USERNAME']
            password = self.env['CAPACITY_' + actor + '_PASSWORD']
            require(bool(username) and bool(password))
            data, _ = self.transport.request('app', 'POST', '/api/v1/auth/login', None,
                                            {'username': username, 'password': password})
            token = data.get('access_token')
            require(isinstance(token, str) and bool(token))
            me, _ = self.transport.request('app', 'GET', '/api/v1/auth/me', token)
            require(me.get('role') == ('admin' if actor == 'ADMIN' else 'manager'))
            self.tokens[actor] = token
            self.ids[actor] = me['user_id']
        require(len(set(self.ids.values())) == len(actors))
        profile, _ = self.transport.request('app', 'GET', '/api/v1/admin/reference-profile',
                                            self.tokens['ADMIN'])
        require(profile.get('data', {}).get('status') == 'CONFIGURED'
                and profile['data'].get('run_id') == self.plan['dataset']['reference_run_id']
                and profile['data'].get('principal') == self.plan['dataset']['principal'])
        self.transport.request('app', 'GET', '/ready', None)
        ledger, _ = self.transport.request('mail', 'GET', '/control/v1/runs/' +
                                           self.plan['dataset']['reference_run_id'] + '/evidence',
                                           self.operator)
        require(ledger.get('store_id') == self.plan['dataset']['mail_store_id']
                and ledger.get('fixture_hash') == self.plan['dataset']['mail_fixture_sha256']
                and ledger.get('principal') == self.plan['dataset']['principal']
                and ledger.get('run_id') == self.plan['dataset']['reference_run_id']
                and ledger.get('schema') == 'reference-store-v1' and ledger.get('service') == 'mail'
                and not ledger.get('operations'))  # A new pre-provisioned run, never reset.

    def flow(self, slot: int, offset: int, kind: str, origin: float) -> dict[str, Any]:
        start = time.monotonic()
        row = {'slot': slot, 'kind': kind, 'start_ms': (start - origin) * 1000,
               'elapsed_ms': None, 'ttft_ms': None, 'outcome': 'TRANSPORT_ERROR',
               'phases': [], 'oracle_sha256': None}
        if row['start_ms'] - offset * 1000 > self.plan['workload']['max_start_lag_ms']:
            row['outcome'] = 'DROPPED'
            return row
        actor = f'REQUESTER_{slot % self.plan["workload"]["concurrency"]}'

        def call(name: str, target: str, method: str, path: str, token: str,
                 body: dict[str, Any] | None = None, stream: bool = False) -> dict[str, Any]:
            if self.stop.is_set():
                raise MeasurementError('INTERRUPTED')
            phase: dict[str, Any] = {'name': name}
            row['phases'].append(phase)
            data, ttft = self.transport.request(target, method, path, token, body,
                                                stream=stream, measurement=phase)
            if stream:
                row['ttft_ms'] = ttft
            return data

        try:
            prompt = (self.plan['oracles'][kind]['prompt'] if kind != 'approval' else
                      '向 customer@reference.invalid 发送外部邮件，主题 capacity-reference，'
                      '正文为合成参考验证，不添加抄送和附件，请提交审批。')
            data = call('stream', 'app', 'POST', '/api/v1/chat/stream', self.tokens[actor],
                        {'message': prompt}, True)
            if kind != 'approval':
                row['oracle_sha256'] = answer_oracle(self.plan, kind, data)
            else:
                sid = data['session_id']
                require(isinstance(sid, str) and bool(re.fullmatch('[A-Za-z0-9_-]{1,64}', sid)))
                path = '/api/v1/admin/reference-evidence/' + sid
                observed = call('evidence', 'app', 'GET', path, self.tokens['ADMIN'])['data']
                approvals = observed.get('approvals', [])
                require(len(approvals) == 1 and approvals[0]['status'] == 'pending'
                        and approvals[0]['requester_id'] == self.ids[actor]
                        and approvals[0]['operation_type'] == 'send_email_external')
                aid = approvals[0]['approval_id']
                require(isinstance(aid, str) and bool(re.fullmatch('[A-Za-z0-9_-]{1,64}', aid)))
                decided = call('decide', 'app', 'POST', '/api/v1/approval/' + aid + '/decide',
                               self.tokens['APPROVER'], {'decision': 'approved',
                                                       'comment': 'Controlled capacity run'})
                require(decided.get('status') == 'approved_pending_reauth')
                resumed = call('resume', 'app', 'POST',
                               '/api/v1/pending-executions/' + aid + '/resume', self.tokens[actor])
                require(resumed.get('status') == 'executed')
                observed = call('evidence', 'app', 'GET', path, self.tokens['ADMIN'])['data']
                ledger = call('mail_ledger', 'mail', 'GET', '/control/v1/runs/' +
                              self.plan['dataset']['reference_run_id'] + '/evidence', self.operator)
                row['oracle_sha256'] = evidence_oracle(self.plan, observed, ledger,
                                                       self.ids[actor], self.ids['APPROVER'], aid)
            row['outcome'] = 'OBSERVED'
        except MeasurementError as error:
            row['outcome'] = str(error)
        except (ValueError, KeyError, TypeError):
            row['outcome'] = 'ORACLE_FAILED'
        except Exception:
            row['outcome'] = 'TRANSPORT_ERROR'
        row['elapsed_ms'] = (time.monotonic() - start) * 1000
        return row


def dropped(slot: int, kind: str) -> dict[str, Any]:
    return {'slot': slot, 'kind': kind, 'start_ms': None, 'elapsed_ms': None, 'ttft_ms': None,
            'outcome': 'DROPPED', 'phases': [], 'oracle_sha256': None}


def collect(plan: dict[str, Any], workload: Workload, emit: Callable[[dict[str, Any]], None]) -> bool:
    """One fixed lane per requester; busy arrivals drop instead of silently reducing load."""
    w = plan['workload']
    pool = ThreadPoolExecutor(max_workers=w['concurrency'])
    pending: dict[int, Any] = {}
    origin = time.monotonic()
    complete = False

    def harvest() -> None:
        for lane, future in list(pending.items()):
            if future.done():
                emit(future.result())
                del pending[lane]

    try:
        for slot, offset, kind in schedule(plan):
            delay = origin + offset - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            harvest()
            lane = slot % w['concurrency']
            if lane in pending or time.monotonic() - origin - offset > w['max_start_lag_ms'] / 1000:
                emit(dropped(slot, kind))
            else:
                pending[lane] = pool.submit(workload.flow, slot, offset, kind, origin)
        remaining = origin + w['duration_seconds'] - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        deadline = origin + w['duration_seconds'] + w['drain_seconds']
        while pending and time.monotonic() < deadline:
            harvest()
            if pending:
                time.sleep(.05)
        complete = not pending
    finally:
        workload.stop.set()
        # HTTP calls are individually bounded; stop prevents subsequent mutation phases.
        pool.shutdown(wait=True, cancel_futures=True)
        harvest()
    return complete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approved-plan-sha256')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--summarize', type=Path, help='Offline retained run directory')
    args = parser.parse_args()
    try:
        plan = read_json(args.plan, 256 * 1024)
        validate(plan)
        if args.summarize:
            require(not args.execute and not args.summarize.is_symlink()
                    and not any(p.is_symlink() for p in args.summarize.parents))
            manifest = read_json(args.summarize / 'manifest.json')
            require(manifest['plan_sha256'] == digest(plan))
            rows = [read_json(p) for p in sorted(args.summarize.glob('slot-*.json'))]
            started = (args.summarize / 'started.json').exists()
            if started:
                require(read_json(args.summarize / 'started.json')['plan_sha256'] == digest(plan))
            finished = (args.summarize / 'finished.json').exists()
            if finished:
                marker = read_json(args.summarize / 'finished.json')
                require(marker['plan_sha256'] == digest(plan))
                finished = marker['completed'] is True
            report = summarize(plan, rows, completed=finished, evidence_kind='runtime')
            if not started:
                report.update(measurement_status='BLOCKED', acceptance_status='BLOCKED',
                              execution='NOT_STARTED')
            print(canonical(report))
            return 1 if report['acceptance_status'] == 'FAIL' else 2
        if not args.execute:
            print(canonical({'status': 'BLOCKED', 'execution': 'NOT_RUN',
                             'plan_sha256': digest(plan), 'scheduled': len(schedule(plan))}))
            return 2
        require(args.approved_plan_sha256 == digest(plan) and args.output is not None)
        output = args.output.absolute()
        require(not output.exists() and not output.is_symlink() and output.parent.is_dir()
                and not any(p.is_symlink() for p in output.parents))
        output.mkdir(mode=0o700)
        write_new(output / 'manifest.json', {'plan_sha256': digest(plan),
            'candidate': plan['candidate'], 'evidence_kind': 'runtime',
            'collector_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in Path(__file__).parent.glob('*.py')}})
        completed = False
        started = False
        rows: list[dict[str, Any]] = []

        def emit(row: dict[str, Any]) -> None:
            write_new(output / ('slot-%06d.json' % row['slot']), row)
            rows.append(row)

        def terminate(signum: int, frame: Any) -> None:
            raise KeyboardInterrupt

        old_handler = signal.signal(signal.SIGTERM, terminate)
        try:
            workload = Workload(plan, Transport(plan['workload']['request_timeout_seconds']), dict(os.environ))
            workload.preflight()
            write_new(output / 'started.json', {'plan_sha256': digest(plan),
                      'started_at': datetime.now(timezone.utc).isoformat()})
            started = True
            completed = collect(plan, workload, emit)
        except (Exception, KeyboardInterrupt):
            # No secrets, raw exception or business text. Retained per-slot files survive interruption.
            completed = False
        finally:
            signal.signal(signal.SIGTERM, old_handler)
        report = summarize(plan, rows, completed=completed, evidence_kind='runtime')
        if not started:
            report.update(measurement_status='BLOCKED', acceptance_status='BLOCKED',
                          execution='NOT_STARTED')
        write_new(output / 'finished.json', {'completed': completed, 'plan_sha256': digest(plan),
                  'finished_at': datetime.now(timezone.utc).isoformat()})
        write_new(output / 'report.json', report)
        print(canonical({'acceptance_status': report['acceptance_status'],
                         'collector_completed': completed, 'recorded': len(rows)}))
        return 1 if report['acceptance_status'] == 'FAIL' else 2
    except Exception:
        print(canonical({'status': 'BLOCKED', 'error_code': 'CAPACITY_INPUT_OR_OUTPUT_INVALID'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
