"""Frozen plans and conservative capacity summaries; standard library only."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

KINDS = ('qa', 'analysis', 'approval')
BASELINE = {'p95_ms': 2000, 'p99_ms': 5000, 'error_rate_lt': 0.005}
PHASES = ('stream', 'evidence', 'decide', 'resume', 'mail_ledger')


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def strict_json(raw: str | bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError('CAPACITY_DUPLICATE_KEY')
            result[key] = value
        return result

    def invalid(_: str) -> None:
        raise ValueError('CAPACITY_NONFINITE')

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def require(condition: bool) -> None:
    if not condition:
        raise ValueError('CAPACITY_CONTRACT_INVALID')


def keys(value: Any, expected: str) -> None:
    require(isinstance(value, dict) and set(value) == set(expected.split()))


def number(value: Any, low: float, high: float) -> None:
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high)


def integer(value: Any, low: int, high: int) -> None:
    require(type(value) is int and low <= value <= high)


def label(value: Any) -> None:
    require(isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9_.:/@+-]{1,160}', value)))


def sha(value: Any, length: int = 64) -> None:
    require(isinstance(value, str) and bool(re.fullmatch('[a-f0-9]{%d}' % length, value)))


def validate(plan: dict[str, Any]) -> None:
    """Reject placeholders, extra fields and unbounded schedules before creating a client."""
    keys(plan, 'schema candidate environment models dataset workload actors oracles baseline')
    require(plan['schema'] == 'capacity-plan-v1' and plan['baseline'] == BASELINE)
    c = plan['candidate']
    keys(c, 'commit application_image reference_image capacity_image schema_sha256')
    sha(c['commit'], 40); sha(c['schema_sha256'])
    for key in ('application_image', 'reference_image', 'capacity_image'):
        require(isinstance(c[key], str) and bool(re.fullmatch(
            r'[A-Za-z0-9_.:/-]+@sha256:[a-f0-9]{64}', c[key])))
    e = plan['environment']
    keys(e, 'os cpu cores memory_gib storage api_processes worker_processes evidence_sha256')
    for key in ('os', 'cpu', 'storage'):
        label(e[key])
    require(e['os'].lower().startswith('linux'))
    integer(e['cores'], 1, 1024); number(e['memory_gib'], 1, 65536)
    integer(e['api_processes'], 1, 2); integer(e['worker_processes'], 1, 16)
    sha(e['evidence_sha256'])
    m = plan['models']
    keys(m, 'embedding reranker llm primary_llm region quota_cost_review_sha256')
    for key in ('embedding', 'reranker', 'llm', 'primary_llm', 'region'):
        label(m[key])
    sha(m['quota_cost_review_sha256'])
    d = plan['dataset']
    keys(d, 'manifest_sha256 documents chunks orders reference_run_id mail_store_id '
         'mail_fixture_sha256 principal')
    for key in ('manifest_sha256', 'mail_fixture_sha256'):
        sha(d[key])
    for key in ('documents', 'chunks', 'orders'):
        integer(d[key], 1, 100000000)
    for key in ('reference_run_id', 'mail_store_id'):
        require(isinstance(d[key], str) and str(UUID(d[key])) == d[key] and UUID(d[key]).version == 4)
    label(d['principal'])
    w = plan['workload']
    keys(w, 'duration_seconds interval_seconds concurrency cycle min_samples_per_kind '
         'request_timeout_seconds drain_seconds max_start_lag_ms')
    integer(w['duration_seconds'], 1800, 7200)
    integer(w['interval_seconds'], 1, 60)
    integer(w['concurrency'], 1, 8)
    integer(w['request_timeout_seconds'], 5, 180)
    integer(w['drain_seconds'], w['request_timeout_seconds'] * 6, 1800)
    number(w['max_start_lag_ms'], 1, 1000)
    require(isinstance(w['cycle'], list) and 3 <= len(w['cycle']) <= 100
            and set(w['cycle']) == set(KINDS))
    integer(w['min_samples_per_kind'], 30, 100000)
    require(w['duration_seconds'] % (w['interval_seconds'] * len(w['cycle'])) == 0)
    counts = Counter(kind for _, _, kind in schedule(plan))
    require(all(counts[k] >= w['min_samples_per_kind'] for k in KINDS))
    a = plan['actors']
    keys(a, 'requester_role approver_role rate_limit_per_minute login_limit_per_minute '
         'isolation_review_sha256')
    require(a['requester_role'] == 'manager' and a['approver_role'] == 'manager')
    # Existing middleware shares user keys across routes. This is not per-endpoint headroom.
    require(a['rate_limit_per_minute'] == 30 and a['login_limit_per_minute'] == 10)
    sha(a['isolation_review_sha256'])
    o = plan['oracles']
    keys(o, 'qa analysis')
    for kind in ('qa', 'analysis'):
        keys(o[kind], 'prompt required_text source_ids')
        require(isinstance(o[kind]['prompt'], str) and 1 <= len(o[kind]['prompt']) <= 2000)
        require(isinstance(o[kind]['required_text'], list)
                and 1 <= len(o[kind]['required_text']) <= 20)
        require(all(isinstance(s, str) and 1 <= len(s) <= 200 for s in o[kind]['required_text']))
        require('REPLACE_' not in canonical(o[kind]))
        require(isinstance(o[kind]['source_ids'], list) and len(o[kind]['source_ids']) <= 50)
        for sid in o[kind]['source_ids']:
            label(sid)
    require(bool(o['qa']['source_ids']) and not o['analysis']['source_ids'])


def schedule(plan: dict[str, Any]) -> list[tuple[int, int, str]]:
    w = plan['workload']
    return [(i, offset, w['cycle'][i % len(w['cycle'])])
            for i, offset in enumerate(range(0, w['duration_seconds'], w['interval_seconds']))]


def percentile(values: list[float], percent: int) -> float | None:
    """Nearest rank; missing/censored durations are never invented as zero."""
    if not values:
        return None
    return sorted(values)[math.ceil(len(values) * percent / 100) - 1]


def stats(values: list[float]) -> dict[str, Any]:
    return {'samples': len(values), 'p95_ms': percentile(values, 95),
            'p99_ms': percentile(values, 99), 'max_ms': max(values) if values else None}


def validate_record(row: dict[str, Any]) -> None:
    keys(row, 'slot kind start_ms elapsed_ms ttft_ms outcome phases oracle_sha256')
    integer(row['slot'], 0, 100000)
    require(row['kind'] in KINDS)
    for key in ('start_ms', 'elapsed_ms', 'ttft_ms'):
        if row[key] is not None:
            number(row[key], 0, 20000000)
    require(row['outcome'] in {'OBSERVED', 'HTTP_ERROR', 'ORACLE_FAILED', 'TRANSPORT_ERROR',
                               'DROPPED', 'INTERRUPTED'})
    if row['outcome'] == 'OBSERVED':
        require(row['elapsed_ms'] is not None and row['start_ms'] is not None)
        sha(row['oracle_sha256'])
    else:
        require(row['oracle_sha256'] is None)
    if row['ttft_ms'] is not None:
        require(row['elapsed_ms'] is not None and row['ttft_ms'] <= row['elapsed_ms'])
    require(isinstance(row['phases'], list) and len(row['phases']) <= 6)
    if row['outcome'] == 'OBSERVED':
        expected = (['stream', 'evidence', 'decide', 'resume', 'evidence', 'mail_ledger']
                    if row['kind'] == 'approval' else ['stream'])
        require([p.get('name') for p in row['phases']] == expected)
        require(all(p.get('status') == 200 and p.get('complete') is True for p in row['phases']))
    for phase in row['phases']:
        keys(phase, 'name status elapsed_ms complete')
        require(phase['name'] in PHASES and type(phase['complete']) is bool)
        integer(phase['status'], 0, 599)
        number(phase['elapsed_ms'], 0, 20000000)


def summarize(plan: dict[str, Any], records: list[dict[str, Any]], *, completed: bool,
              evidence_kind: str) -> dict[str, Any]:
    validate(plan)
    require(type(completed) is bool and evidence_kind in {'synthetic', 'runtime'})
    expected = schedule(plan)
    by_slot: dict[int, dict[str, Any]] = {}
    for row in records:
        validate_record(row)
        index = row['slot']
        require(index < len(expected) and expected[index][2] == row['kind'] and index not in by_slot)
        if row['outcome'] == 'OBSERVED':
            require(abs(row['start_ms'] - expected[index][1] * 1000)
                    <= plan['workload']['max_start_lag_ms'])
        by_slot[index] = row
    completed = completed and len(by_slot) == len(expected)
    results: dict[str, Any] = {}
    endpoint: dict[str, Any] = {}
    for kind in KINDS:
        total = sum(k == kind for _, _, k in expected)
        rows = [r for r in records if r['kind'] == kind]
        good = sum(r['outcome'] == 'OBSERVED' for r in rows)
        times = [r['elapsed_ms'] for r in rows if r['elapsed_ms'] is not None]
        ttfts = [r['ttft_ms'] for r in rows if r['ttft_ms'] is not None]
        within = sum(r['outcome'] == 'OBSERVED' and r['start_ms'] + r['elapsed_ms'] <=
                     plan['workload']['duration_seconds'] * 1000 for r in rows)
        item = {**stats(times), 'scheduled': total, 'recorded': len(rows),
                'missing': total - len(rows), 'observed_business': good,
                'failed_or_missing': total - good, 'error_rate': (total - good) / total,
                'outcomes': dict(Counter(r['outcome'] for r in rows)), 'ttft': stats(ttfts),
                'completed_in_window': within, 'completed_in_drain': good - within,
                'business_per_second': within / plan['workload']['duration_seconds']}
        # Baseline applied to full workflow here; per-HTTP phase baseline is separate below.
        breach = (item['error_rate'] >= BASELINE['error_rate_lt']
                  or (item['p95_ms'] is not None and item['p95_ms'] > BASELINE['p95_ms'])
                  or (item['p99_ms'] is not None and item['p99_ms'] > BASELINE['p99_ms']))
        item['historical_baseline'] = 'FAIL' if breach else 'OBSERVED_WITHIN_BASELINE'
        item['ttft_status'] = ('OBSERVED' if ttfts else 'NOT_OBSERVED')
        item['ttft_missing'] = total - len(ttfts)
        results[kind] = item
        for name in PHASES:
            phases = [p for r in rows for p in r['phases'] if p['name'] == name]
            if not phases:
                continue
            measured = [p['elapsed_ms'] for p in phases if p['complete']]
            entry = {**stats(measured), 'attempts': len(phases),
                     'censored': sum(not p['complete'] for p in phases),
                     'http_errors': sum(not p['complete'] or p['status'] != 200 for p in phases),
                     'rate_limited': sum(p['status'] == 429 for p in phases)}
            entry['error_rate'] = entry['http_errors'] / len(phases)
            entry['historical_baseline'] = ('FAIL' if entry['error_rate'] >= .005 or
                (entry['p95_ms'] is not None and entry['p95_ms'] > 2000) or
                (entry['p99_ms'] is not None and entry['p99_ms'] > 5000)
                else 'OBSERVED_WITHIN_BASELINE')
            endpoint[kind + ':' + name] = entry
    failed = any(v['historical_baseline'] == 'FAIL' for v in [*results.values(), *endpoint.values()])
    return {'schema': 'capacity-report-v1', 'plan_sha256': digest(plan),
            'evidence_kind': evidence_kind, 'collector_completed': completed,
            'declared_candidate': plan['candidate'], 'declared_environment': plan['environment'],
            'declared_models': plan['models'], 'declared_dataset': plan['dataset'],
            'declared_workload': plan['workload'], 'identity_verification': 'OPERATOR_REQUIRED',
            'measurement_status': 'FAIL' if failed else ('OBSERVED' if completed else 'BLOCKED'),
            'acceptance_status': 'FAIL' if failed and evidence_kind == 'runtime' else 'BLOCKED',
            'business': results, 'http_phases': endpoint, 'baseline': BASELINE,
            'required_evidence': ['L01_L16_RUNTIME_REVIEW', 'SEMANTIC_AND_CITATION_REVIEW',
                                  'QUEUE_AND_EXECUTION_TIMING', 'RESOURCE_TIME_SERIES',
                                  'BACKLOG_DRAIN', 'ACTUAL_IDENTITY_QUOTA_AND_COST'],
            'queue_latency': 'NOT_OBSERVED', 'execution_latency': 'NOT_OBSERVED',
            'runtime_cases': {f'L{i:02d}': 'BLOCKED' for i in range(1, 17)},
            'formal_uat': False, 'release_evidence': False, 'release_allowed': False}


def read_json(path: Path, limit: int = 32 * 1024 * 1024) -> Any:
    require(not path.is_symlink() and not any(p.is_symlink() for p in path.parents))
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit)
    return strict_json(raw)


def write_new(path: Path, value: Any) -> None:
    require(path.parent.is_dir() and not path.is_symlink()
            and not any(p.is_symlink() for p in path.parents))
    with path.open('x', encoding='utf-8') as stream:
        stream.write(canonical(value) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
