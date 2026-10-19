"""C24 fixed offline regression inventory; trusted reviewed code, not a sandbox."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'enterprise-agent/scripts/final_candidate_sources.json'
Suite = tuple[str, str, str, int, int]
# Explicit entries only: (id, path below enterprise-agent, parser, count, allowed skips).
SUITES = (
    ('C01', 'tests/test_deployment_contract.py', 'unittest', 11, 1),
    ('C01-image', 'tests/test_dockerfile_prod.py', 'unittest', 3, 0),
    ('C02-profile', 'tests/test_model_profile.py', 'unittest', 15, 0),
    ('C02-remote', 'tests/test_remote_models.py', 'unittest', 12, 0),
    ('C03', 'tests/test_db_bootstrap.py', 'unittest', 22, 0),
    ('C04', 'eval/run_c04_session_ownership.py', 'unittest', 20, 0),
    ('C05', 'eval/run_c05_runtime_authorization.py', 'unittest', 29, 0),
    ('C06', 'eval/run_c06_credential_safety.py', 'unittest', 20, 0),
    ('C07', 'eval/run_c07_retrieval_authorization.py', 'unittest', 21, 0),
    ('C08', 'eval/run_c08_request_context.py', 'unittest', 23, 0),
    ('C09', 'eval/run_c09_cross_process_state.py', 'unittest', 28, 0),
    ('C10', 'eval/run_c10_checkpoint_durability.py', 'unittest', 27, 0),
    ('C11', 'eval/run_c11_approval_execution.py', 'unittest', 34, 0),
    ('C12', 'eval/run_c12_tool_operation_safety.py', 'unittest', 41, 0),
    ('C13', 'eval/run_c13_saga_recovery.py', 'unittest', 34, 0),
    ('C14', 'eval/run_c14_queue_reliability.py', 'unittest', 50, 0),
    ('C15', 'eval/run_c15_knowledge_publication.py', 'unittest', 36, 0),
    ('C16', 'eval/run_c16_analysis_data.py', 'unittest', 33, 0),
    ('C17', 'eval/run_c17_rag_quality.py', 'unittest', 29, 0),
    ('C18', 'eval/run_c18_reference_integration.py', 'unittest', 45, 0),
    ('C19', 'eval/run_c19_controlled_sso.py', 'unittest', 37, 0),
    ('C20-credentials', 'tests/test_browser_credential_safety.cjs', 'node', 14, 0),
    ('C20', 'tests/test_browser_delivery.cjs', 'node', 45, 0),
    ('C20-assets', 'scripts/verify_frontend_assets.py', 'assets', 7, 0),
    ('C21', 'eval/run_c21_runtime_observability.py', 'unittest', 45, 0),
    ('C22', 'eval/run_c22_retained_recovery.py', 'unittest', 46, 0),
    ('C23', 'eval/run_c23_capacity_evidence.py', 'unittest', 42, 0),
    ('C24-safety', 'tests/test_safe_validation.py', 'unittest', 12, 0),
    ('C24-receipt', 'tests/test_final_candidate.py', 'unittest', 16, 0),
    ('C24-plans', 'scripts/safe_validate.py', 'plans', 5, 0),
)
BLOCKERS = ('L01-L16', 'D01-D16', 'O01-O16', 'B01-B16', 'S01-S16', 'R01-R20',
            'REAL_RUNTIME_FULL_RAG', 'C10_WRITE_FENCING', 'HISTORICAL_CREDENTIALS',
            'FULL_PYTEST_DEPENDENCIES', 'IMAGE_BUILD_SCANNERS_CURRENT_CI',
            'OPENSPEC_STRICT', 'ENTERPRISE_UAT_RELEASE')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('PATH_REJECTED')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('PATH_REJECTED')
    return path


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(['git', *args], cwd=root, capture_output=True, check=True,
                          timeout=15).stdout


def candidate(root: Path) -> dict[str, Any]:
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    if not re.fullmatch('[a-f0-9]{40,64}', head):
        raise ValueError('REVISION_UNAVAILABLE')
    paths = sorted(p.decode() for p in git(root, 'ls-files', '-z').split(b'\0') if p)
    hashes = {p: digest(checked_path(root, p).read_bytes()) for p in paths}
    dirty = bool(git(root, '-c', 'core.fileMode=false', 'diff', '--name-only', 'HEAD', '--'))
    untracked = len([p for p in git(root, 'ls-files', '--others', '--exclude-standard', '-z')
                     .split(b'\0') if p])
    modes = len(re.findall(rb'^ mode change ', git(root, 'diff', '--summary', 'HEAD'), re.M))
    return {'commit': head, 'tracked_content_sha256': digest(json.dumps(hashes, sort_keys=True)
            .encode()), 'tracked_content_dirty': dirty, 'untracked_files': untracked,
            'mode_only_differences': modes}


def verify_sources(root: Path) -> str:
    raw = checked_path(root, MANIFEST).read_bytes()
    manifest = json.loads(raw)
    paths = manifest['sources']
    required = {'enterprise-agent/' + row[1] for row in SUITES}
    if not required <= paths.keys() or not paths:
        raise ValueError('SOURCE_REVIEW_REQUIRED')
    for path, expected in paths.items():
        if digest(checked_path(root, path).read_bytes()) != expected:
            raise ValueError('SOURCE_REVIEW_REQUIRED')
    return digest(raw)


def command(row: Suite, root: Path) -> list[str]:
    _, path, kind, _, _ = row
    args = ['node'] if kind == 'node' else [sys.executable, '-I', '-B']
    args.append(str(root / 'enterprise-agent' / path))
    if kind == 'assets':
        args.append(str(root / 'enterprise-agent/app/static'))
    return args


def parse_result(row: Suite, code: int, output: str) -> dict[str, Any]:
    ident, _, kind, expected, allowed_skips = row
    result = {'id': ident, 'status': 'FAIL', 'executed': 0, 'passed': 0, 'skipped': 0,
              'unit': 'tests' if kind in ('unittest', 'node') else kind,
              'reason': 'INVALID_RESULT'}
    if kind == 'plans':
        try:
            value = json.loads(output)
            checks = value['results']
            expected_states = {'uat-plan': 'PASS', 'uat-readiness': 'BLOCKED',
                               'grey-plan': 'PASS', 'release-gate': 'BLOCKED', 'g0-replay': 'PASS'}
            states = {r['id']: r['result_status'] for r in checks}
            valid = (code == 2 and value['execution_status'] == 'PASS'
                     and value['overall_status'] == 'BLOCKED' and len(checks) == expected
                     and states == expected_states and all(value[k] is False for k in
                         ('formal_uat', 'release_allowed', 'release_evidence')))
        except (ValueError, KeyError, TypeError):
            valid = False
        if valid:
            result.update(status='BLOCKED', executed=5, passed=3, reason='REAL_GATES_BLOCKED')
        return result
    if code != 0:
        result['reason'] = 'SUITE_FAILED'
        return result
    skipped = 0
    if kind == 'unittest':
        counts = re.findall(r'^Ran (\d+) tests? in [\d.]+s$', output, re.M)
        endings = re.findall(r'^OK(?: \(skipped=(\d+)\))?$', output, re.M)
        if len(counts) != 1 or len(endings) != 1:
            return result
        count = int(counts[0]); skipped = int(endings[0] or 0)
        # This exact missing-dependency case is the only permitted skip.
        skip_reason = 'Declared PyYAML dependency unavailable; parse YAML separately'
        if skipped and skip_reason not in output:
            return result
    else:
        pattern = {
            'C20-credentials': (r'^PASS: (\d+) browser-script cases '
                                r'\(VM only; real DOM/browser acceptance BLOCKED\)$'),
            'C20': (r'^PASS: (\d+) C20 cases; VM/static only, '
                    r'real browser/API acceptance BLOCKED$'),
            'C20-assets': (r'^PASS: (\d+) browser distribution/license files; '
                           r'runtime acceptance BLOCKED$'),
        }
        matches = re.findall(pattern[ident], output, re.M)
        if len(matches) != 1:
            return result
        count = int(matches[0])
    if count != expected or skipped > allowed_skips:
        return result
    result.update(status='BLOCKED' if skipped else 'PASS', executed=count - skipped,
                  passed=count - skipped, skipped=skipped,
                  reason='DEPENDENCY_UNAVAILABLE' if skipped else 'COMPLETED')
    return result


def summarize(results: list[dict], stable: bool, clean: bool) -> dict[str, Any]:
    failed = any(r['status'] == 'FAIL' for r in results)
    tests = [r for r in results if r['unit'] == 'tests']
    return {'overall_status': 'FAIL' if failed else 'BLOCKED',
            'candidate_binding': 'PASS' if stable and clean else 'BLOCKED',
            'passed_tests': sum(r['passed'] for r in tests),
            'skipped_tests': sum(r['skipped'] for r in tests),
            'failed_entries': sum(r['status'] == 'FAIL' for r in results),
            'formal_uat': False, 'release_allowed': False, 'release_evidence': False}


def run(root: Path) -> dict[str, Any]:
    reviewed = verify_sources(root)
    runner_hash = digest(Path(__file__).read_bytes())
    before = candidate(root)
    environment = dict(os.environ)
    # -I protects Python; Node's preload/coverage settings can execute or write before tests.
    for key in ('NODE_OPTIONS', 'NODE_V8_COVERAGE'):
        environment.pop(key, None)
    results = []
    for row in SUITES:
        try:
            child = subprocess.run(command(row, root), cwd=root, env=environment,
                                   capture_output=True, text=True, timeout=90)
            result = parse_result(row, child.returncode, child.stdout + child.stderr)
        except FileNotFoundError:
            result = {'id': row[0], 'status': 'BLOCKED', 'executed': 0, 'passed': 0,
                      'skipped': 0, 'unit': 'tests', 'reason': 'EXECUTABLE_UNAVAILABLE'}
        except subprocess.TimeoutExpired:
            result = {'id': row[0], 'status': 'FAIL', 'executed': 0, 'passed': 0,
                      'skipped': 0, 'unit': 'tests', 'reason': 'TIMEOUT'}
        results.append(result)
    after = candidate(root)
    stable = (before == after and verify_sources(root) == reviewed
              and digest(Path(__file__).read_bytes()) == runner_hash)
    clean = not before['tracked_content_dirty'] and before['untracked_files'] == 0
    try:
        version = subprocess.run(['node', '--version'], capture_output=True, text=True,
                                 timeout=10, env=environment, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        version = 'UNAVAILABLE'
    return {'schema': 'c24-offline-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
            'candidate': before, 'sources_sha256': reviewed,
            'runner_sha256': runner_hash,
            'python_version': '.'.join(map(str, sys.version_info[:3])),
            'node_version': version if re.fullmatch(r'v\d+\.\d+\.\d+', version) else 'UNAVAILABLE',
            'source_stable': stable, 'results': results, 'blocked_gates': list(BLOCKERS),
            **summarize(results, stable, clean)}


def record(root: Path, run_id: str, report: dict) -> None:
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', run_id):
        raise ValueError('RUN_ID_REJECTED')
    target = checked_path(root, 'enterprise-agent/eval/results/final-candidate/' + run_id + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--record', metavar='FRESH_RUN_ID')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'status': 'PLAN_ONLY', 'entries': [r[0] for r in SUITES],
                          'blocked_gates': BLOCKERS}))
        return 0
    try:
        # Reject a collision/invalid path before any child creates retained fixtures.
        if args.record:
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', args.record):
                raise ValueError('RUN_ID_REJECTED')
            relative = 'enterprise-agent/eval/results/final-candidate/' + args.record + '.json'
            path = checked_path(ROOT, relative)
            if path.exists():
                raise ValueError('RECORD_EXISTS')
        report = run(ROOT)
        if args.record:
            record(ROOT, args.record, report)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps({'overall_status': 'BLOCKED', 'reason': 'PREFLIGHT_OR_RECORD_FAILED',
                          'release_allowed': False}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report['overall_status'] == 'FAIL' else 2


if __name__ == '__main__':
    raise SystemExit(main())
