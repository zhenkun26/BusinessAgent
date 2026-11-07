"""Current reviewed offline checks. Never grants runtime, UAT or release acceptance."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'enterprise-agent/scripts/offline_sources.json'
# Commands are code-reviewed constants; the manifest cannot supply arbitrary commands.
CHECKS = {
    'python': ('scripts/run_offline_pytest.py', 'python'),
    'node-page': ('tests/test_browser_delivery.cjs', 'node'),
    'node-credentials': ('tests/test_browser_credential_safety.cjs', 'node'),
    'frontend-assets': ('scripts/verify_frontend_assets.py', 'python'),
    'build-inputs': ('scripts/verify_build.py', 'python'),
    'provenance': ('scripts/verify_license_inventory.py', 'python'),
    'rag-controls': ('eval/run_f206_rag_safety.py', 'python'),
    'safe-preflight': ('scripts/safe_validate.py', 'python'),
}
COVERAGE = {
    'F2-01': ['python'], 'F2-02': ['python'], 'F2-03': ['python'],
    'F2-04': ['python', 'build-inputs', 'frontend-assets'], 'F2-05': ['python'],
    'F2-06': ['python', 'rag-controls'], 'F2-07': ['python', 'node-page'],
    'F2-08': ['python', 'node-page'], 'F2-09': ['python', 'provenance'],
    'F2-10': list(CHECKS), 'F2-11': ['provenance'],
}
BLOCKERS = ['REAL_RUNTIME_FULL_RAG', 'C10_TWO_PROCESS_ACCEPTANCE', 'F2_05_PRIVACY',
            'F2_09_SOURCE_RIGHTS', 'L01-L16', 'D01-D16', 'O01-O16', 'B01-B16',
            'S01-S16', 'R01-R20', 'HISTORICAL_CREDENTIALS', 'CURRENT_REMOTE_CI_IMAGE_SCANS',
            'OPENSPEC_STRICT', 'ENTERPRISE_UAT_RELEASE']


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    parts = Path(relative)
    if parts.is_absolute() or '..' in parts.parts or not parts.parts:
        raise ValueError('PATH_REJECTED')
    path = root / parts
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('PATH_REJECTED')
    return path


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True,
                          timeout=15).stdout


def repository_files(root: Path) -> list[str]:
    tracked = git(root, 'ls-files', '-z')
    other = git(root, 'ls-files', '--others', '--exclude-standard', '-z')
    return sorted({p.decode() for p in (tracked + other).split(b'\0') if p})


def source_paths(root: Path) -> list[str]:
    """All delivered backend code/config/data and workflow bytes; no private/ignored files."""
    return [n for n in repository_files(root)
            if n != MANIFEST and n.startswith(('enterprise-agent/', '.github/'))
            and (not n.endswith('.md') or n.startswith('enterprise-agent/eval/sample_docs/'))]


def source_snapshot(root: Path) -> dict[str, str]:
    return {n: digest(checked_path(root, n).read_bytes()) for n in source_paths(root)}


def candidate(root: Path) -> dict[str, Any]:
    hashes = {n: digest(checked_path(root, n).read_bytes()) for n in repository_files(root)}
    return {'commit': git(root, 'rev-parse', 'HEAD').decode().strip(),
            'content_sha256': digest(json.dumps(hashes, sort_keys=True).encode()),
            'clean': not git(root, '-c', 'core.fileMode=false', 'status', '--porcelain')}


def json_object(text: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in items:
            if k in result:
                raise ValueError('DUPLICATE_JSON_KEY')
            result[k] = v
        return result
    value = json.loads(text, object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError('INVALID_JSON_OBJECT')
    return value


def verify_sources(root: Path) -> tuple[dict[str, Any], str]:
    raw = checked_path(root, MANIFEST).read_bytes()
    value = json_object(raw.decode())
    if (value.get('schema') != 'offline-sources-v1' or value.get('checks') != list(CHECKS)
            or value.get('finding_coverage') != COVERAGE
            or set(value.get('sources', {})) != set(source_paths(root))):
        raise ValueError('SOURCE_OR_CHECK_REVIEW_REQUIRED')
    expected = value.get('expected', {})
    if (set(expected) != {'python', 'node-page', 'node-credentials', 'frontend-assets',
                         'production-packages', 'pending-sources'}
            or any(type(v) is not int or v <= 0 for v in expected.values())):
        raise ValueError('EXPECTED_COUNTS_INVALID')
    for path, expected_hash in value['sources'].items():
        if digest(checked_path(root, path).read_bytes()) != expected_hash:
            raise ValueError('SOURCE_REVIEW_REQUIRED')
    return value, digest(raw)


def command(ident: str, root: Path) -> list[str]:
    path, tool = CHECKS[ident]
    args = ['node'] if tool == 'node' else [sys.executable, '-I', '-B']
    args.append(str(root / 'enterprise-agent' / path))
    if ident == 'frontend-assets':
        args.append(str(root / 'enterprise-agent/app/static'))
    elif ident == 'build-inputs':
        args.extend(['--root', str(root / 'enterprise-agent')])
    return args


def no_release_claims(value: Any) -> bool:
    if isinstance(value, dict):
        return all((k not in {'formal_uat', 'release_allowed', 'release_evidence'} or v is False)
                   and no_release_claims(v) for k, v in value.items())
    if isinstance(value, list):
        return all(no_release_claims(v) for v in value)
    return True


def parse_result(ident: str, code: int, output: str, expected: dict[str, int]) -> dict[str, Any]:
    result: dict[str, Any] = {'id': ident, 'status': 'FAIL', 'reason': 'INVALID_EVIDENCE'}
    if ident not in CHECKS:
        return result
    if code not in (0, 2):
        return {**result, 'reason': 'CHILD_FAILED'}
    try:
        if ident in {'node-page', 'node-credentials', 'frontend-assets'}:
            patterns = {
                'node-page': r'^PASS: (\d+) C20/F2-08/F2-07 cases; VM/static/compile only, real browser/API acceptance BLOCKED$',
                'node-credentials': r'^PASS: (\d+) browser-script cases \(VM only; real DOM/browser acceptance BLOCKED\)$',
                'frontend-assets': r'^PASS: (\d+) browser distribution/license files; runtime acceptance BLOCKED$',
            }
            found = re.findall(patterns[ident], output, re.M)
            if code != 0 or len(found) != 1 or int(found[0]) != expected[ident]:
                return result
            if ident == 'node-page':
                cases = re.findall(r'^PASS (.+)$', output, re.M)
                if len(cases) != expected[ident] or len(set(cases)) != len(cases):
                    return result
            return {**result, 'status': 'PASS', 'reason': 'COMPLETED', 'count': int(found[0])}
        value = json_object(output)
        if not no_release_claims(value):
            return result
        if ident == 'python':
            if (code == 2 and value.get('schema') == 'offline-pytest-v1'
                    and value.get('status') == 'BLOCKED'
                    and value.get('reason') == 'DEPENDENCIES_UNAVAILABLE'):
                return {**result, 'status': 'BLOCKED', 'reason': 'DEPENDENCIES_UNAVAILABLE'}
            counts = value.get('counts', {})
            if not isinstance(counts, dict):
                return result
            if (code != 0 or value.get('schema') != 'offline-pytest-v1'
                    or value.get('status') != 'PASS' or value.get('source_stable') is not True
                    or value.get('production_requirements_match') is not True
                    or value.get('guard_denials') != 0
                    or type(value.get('guard_denials')) is not int
                    or value.get('collected') != expected['python']
                    or type(value.get('collected')) is not int
                    or counts.get('passed') != expected['python']
                    or any(type(n) is not int or n < 0 for n in counts.values())
                    or any(v for k, v in counts.items() if k not in {'passed', 'subtest_passed'})
                    or value.get('runtime') != 'BLOCKED' or value.get('full_rag') != 'BLOCKED'
                    or value.get('c10') != 'OPEN'):
                return result
            return {**result, 'status': 'PASS', 'reason': 'COMPLETED', 'counts': counts,
                    'coverage_percent': value.get('coverage_percent'),
                    'evidence': value.get('evidence')}
        if ident == 'build-inputs':
            valid = (code == 0 and value.get('status') == 'INPUTS_VERIFIED'
                     and value.get('packages') == expected['production-packages']
                     and value.get('installed_image') == value.get('runtime') == 'BLOCKED'
                     and value.get('c10') == 'OPEN')
        elif ident == 'provenance':
            valid = (code == 0 and value.get('integrity') == 'PASS'
                     and value.get('distribution_acceptance') == value.get('runtime')
                     == value.get('full_rag') == 'BLOCKED' and value.get('c10') == 'OPEN'
                     and value.get('pending_source_files') == expected['pending-sources']
                     and value.get('production_packages') == expected['production-packages'])
        elif ident == 'rag-controls':
            valid = (code == 0 and value.get('checker_verification') == 'PASS'
                     and value.get('model_robustness') == 'NOT_MEASURED'
                     and value.get('semantic_review') == 'PENDING'
                     and value.get('quality_acceptance') == value.get('runtime') == 'BLOCKED'
                     and value.get('unexpected_negative_case_ids') == [])
            for kind, passes, gate in [('safe_controls', 8, 'PASS'), ('unsafe_controls', 0, 'FAIL')]:
                part = value.get(kind, {})
                if not isinstance(part, dict):
                    return result
                rows = part.get('samples', [])
                ids = [r.get('case_id') for r in rows if isinstance(r, dict)]
                valid = (valid and part.get('case_denominator') == 8
                         and part.get('mechanical_pass_count') == passes
                         and part.get('mechanical_gate') == gate
                         and part.get('missing_case_ids') == [] and len(rows) == len(ids) == 8
                         and set(ids) == {'PI01', 'PI02', 'PI03', 'PI04', 'NG01', 'NG02', 'NG03', 'NG04'}
                         and all(r.get('mechanical_check') == gate for r in rows)
                         and part.get('actual_pipeline_executed') is False
                         and part.get('quality_acceptance') == 'BLOCKED'
                         and part.get('model_robustness') == 'NOT_MEASURED'
                         and part.get('semantic_review') == 'PENDING')
        else:
            states = {r['id']: r['result_status'] for r in value['results']}
            valid = (code == 2 and value['execution_status'] == 'PASS'
                     and value['overall_status'] == 'BLOCKED' and len(value['results']) == 5
                     and states == {'uat-plan': 'PASS', 'uat-readiness': 'BLOCKED',
                                    'grey-plan': 'PASS', 'release-gate': 'BLOCKED',
                                    'g0-replay': 'PASS'} and all(value[k] is False for k in
                                    ('formal_uat', 'release_allowed', 'release_evidence')))
        if valid:
            return {**result, 'status': 'PASS', 'reason': 'OFFLINE_ONLY'}
    except (ValueError, KeyError, TypeError):
        pass
    return result


def summarize(results: list[dict[str, Any]], stable: bool, clean: bool) -> dict[str, Any]:
    ids = [r.get('id') for r in results]
    complete = len(ids) == len(CHECKS) and len(set(ids)) == len(ids) and set(ids) == set(CHECKS)
    failed = not complete or any(r.get('status') not in {'PASS', 'BLOCKED'} for r in results)
    execution = 'FAIL' if failed else 'PASS' if all(r['status'] == 'PASS' for r in results) else 'BLOCKED'
    return {'execution_status': execution, 'candidate_binding': 'PASS' if stable and clean else 'BLOCKED',
            'source_stable': stable, 'overall_status': 'FAIL' if failed else 'BLOCKED',
            'formal_uat': False, 'release_allowed': False, 'release_evidence': False}


def run(root: Path) -> dict[str, Any]:
    manifest, reviewed = verify_sources(root)  # Reject omissions/drift before any child.
    before = candidate(root)
    environment = dict(os.environ)
    for key in ('NODE_OPTIONS', 'NODE_V8_COVERAGE', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS'):
        environment.pop(key, None)
    results = []
    for ident, (_, tool) in CHECKS.items():
        try:
            if tool == 'node' and shutil.which('node', path=environment.get('PATH')) is None:
                raise FileNotFoundError
            child = subprocess.run(command(ident, root), cwd=root, env=environment,
                                   capture_output=True, text=True, timeout=300)
            results.append(parse_result(ident, child.returncode, child.stdout, manifest['expected']))
        except FileNotFoundError:
            results.append({'id': ident, 'status': 'BLOCKED', 'reason': 'TOOL_UNAVAILABLE'})
        except subprocess.TimeoutExpired:
            results.append({'id': ident, 'status': 'FAIL', 'reason': 'TIMEOUT'})
    after = candidate(root)
    try:
        stable = before == after and verify_sources(root)[1] == reviewed
    except (ValueError, OSError):
        stable = False
    return {'schema': 'current-offline-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
            'candidate': before, 'sources_sha256': reviewed, 'results': results,
            'blocked_gates': BLOCKERS, **summarize(results, stable, before['clean'])}


def exit_code(report: dict[str, Any], ci: bool) -> int:
    if report['execution_status'] == 'FAIL':
        return 1
    return 0 if ci and report['execution_status'] == report['candidate_binding'] == 'PASS' else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--ci', action='store_true', help='execute; scoped offline success only')
    parser.add_argument('--record', metavar='FRESH_RUN_ID')
    args = parser.parse_args()
    if not (args.execute or args.ci):
        print(json.dumps({'status': 'PLAN_ONLY', 'checks': list(CHECKS), 'finding_coverage': COVERAGE,
                          'blocked_gates': BLOCKERS}))
        return 0
    try:
        target = None
        if args.record:
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', args.record):
                raise ValueError('RUN_ID_REJECTED')
            target = checked_path(ROOT, 'enterprise-agent/eval/results/offline/' + args.record + '.json')
            if target.exists():
                raise ValueError('RECORD_EXISTS')
        report = run(ROOT)
        if target:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x', encoding='utf-8') as stream:
                json.dump(report, stream, indent=2, sort_keys=True)
        code = exit_code(report, args.ci)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        report = {'execution_status': 'BLOCKED', 'overall_status': 'BLOCKED',
                  'reason': 'PREFLIGHT_OR_RECORD_FAILED', 'blocked_gates': BLOCKERS,
                  'formal_uat': False, 'release_allowed': False, 'release_evidence': False}
        code = 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
