"""F2-10 current entry counterexamples; injected children and retained fixtures only."""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('f210', ROOT / 'enterprise-agent/scripts/offline_verify.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
spec = importlib.util.spec_from_file_location('f210_pytest', ROOT / 'enterprise-agent/scripts/run_offline_pytest.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
EXPECTED = {'python': 2, 'node-page': 2, 'node-credentials': 14, 'frontend-assets': 7,
            'production-packages': 98, 'pending-sources': 438}
STATE = {'commit': 'a' * 40, 'clean': True, 'content_sha256': 'b' * 64}


def python_result(**updates):
    return {'schema': 'offline-pytest-v1', 'status': 'PASS', 'collected': 2,
            'counts': {'passed': 2, 'subtest_passed': 1}, 'guard_denials': 0,
            'production_requirements_match': True, 'source_stable': True,
            'runtime': 'BLOCKED', 'full_rag': 'BLOCKED', 'c10': 'OPEN', **updates}


def good(ident='python'):
    return {'id': ident, 'status': 'PASS', 'reason': 'COMPLETED'}


def all_good():
    return [good(i) for i in v.CHECKS]


def test_missing_duplicate_unknown_and_extra_result_cannot_pass():
    for rows in ([], all_good()[:-1], all_good() + [good()],
                 [good('UNKNOWN'), *all_good()[1:]]):
        report = v.summarize(rows, True, True)
        assert report['execution_status'] == 'FAIL'
        assert v.exit_code(report, True) == 1


def test_complete_execution_never_closes_acceptance_or_c10():
    report = v.summarize(all_good(), True, True)
    assert report['execution_status'] == report['candidate_binding'] == 'PASS'
    assert report['overall_status'] == 'BLOCKED'
    assert not any(report[k] for k in ('formal_uat', 'release_allowed', 'release_evidence'))
    assert v.exit_code(report, False) == 2
    assert v.exit_code(report, True) == 0
    assert 'C10_TWO_PROCESS_ACCEPTANCE' in v.BLOCKERS


def test_dirty_or_changed_candidate_blocks_ci_even_with_passed_checks():
    for stable, clean in ((False, True), (True, False), (False, False)):
        report = v.summarize(all_good(), stable, clean)
        assert report['candidate_binding'] == 'BLOCKED'
        assert v.exit_code(report, True) == 2


def test_missing_tool_has_no_pass_credit_or_raw_exception_output():
    with patch.object(v, 'verify_sources', return_value=({'expected': EXPECTED}, 'hash')), \
            patch.object(v, 'candidate', return_value=STATE), \
            patch.object(v.shutil, 'which', return_value=None), \
            patch.object(v.subprocess, 'run', return_value=NS(returncode=0, stdout='')) as child, \
            patch.object(v, 'parse_result', side_effect=lambda i, *a: good(i)):
        report = v.run(ROOT)
    assert report['execution_status'] == 'BLOCKED'
    assert [r['reason'] for r in report['results'] if r['id'].startswith('node-')] == ['TOOL_UNAVAILABLE'] * 2
    assert child.call_count == len(v.CHECKS) - 2
    assert v.exit_code(report, True) == 2


def test_missing_child_executable_is_blocked():
    with patch.object(v, 'verify_sources', return_value=({'expected': EXPECTED}, 'hash')), \
            patch.object(v, 'candidate', return_value=STATE), \
            patch.object(v.shutil, 'which', return_value='node'), \
            patch.object(v.subprocess, 'run', side_effect=FileNotFoundError('SYNTHETIC_PRIVATE')):
        report = v.run(ROOT)
    assert report['execution_status'] == 'BLOCKED'
    assert all(r['reason'] == 'TOOL_UNAVAILABLE' for r in report['results'])
    assert 'SYNTHETIC_PRIVATE' not in json.dumps(report)


def test_child_timeout_fails_and_does_not_abort_other_checks():
    with patch.object(v, 'verify_sources', return_value=({'expected': EXPECTED}, 'hash')), \
            patch.object(v, 'candidate', return_value=STATE), \
            patch.object(v.shutil, 'which', return_value='node'), \
            patch.object(v.subprocess, 'run', side_effect=subprocess.TimeoutExpired('PRIVATE', 300)) as child:
        report = v.run(ROOT)
    assert report['execution_status'] == 'FAIL'
    assert child.call_count == len(v.CHECKS)
    assert 'PRIVATE' not in json.dumps(report)


def test_child_failure_cannot_hide_behind_success_output():
    result = v.parse_result('python', 1, json.dumps(python_result()), EXPECTED)
    assert result['status'] == 'FAIL' and result['reason'] == 'CHILD_FAILED'


def test_python_requires_complete_exact_counts_and_no_exceptions():
    assert v.parse_result('python', 0, json.dumps(python_result()), EXPECTED)['status'] == 'PASS'
    for field in ('skipped', 'xfail', 'xpassed', 'deselected', 'failed', 'error', 'subtest_failed'):
        value = python_result(counts={'passed': 2, field: 1})
        assert v.parse_result('python', 0, json.dumps(value), EXPECTED)['status'] == 'FAIL'
    for update in ({'collected': 0}, {'collected': 1}, {'counts': {'passed': 1}},
                   {'guard_denials': 1}, {'source_stable': False},
                   {'production_requirements_match': False}, {'runtime': 'PASS'}):
        assert v.parse_result('python', 0, json.dumps(python_result(**update)), EXPECTED)['status'] == 'FAIL'


def test_dependency_unavailability_is_blocked_not_skipped():
    text = json.dumps({'schema': 'offline-pytest-v1', 'status': 'BLOCKED',
                       'reason': 'DEPENDENCIES_UNAVAILABLE'})
    assert v.parse_result('python', 2, text, EXPECTED)['status'] == 'BLOCKED'
    assert v.parse_result('python', 0, text, EXPECTED)['status'] == 'FAIL'


def test_empty_duplicate_json_and_array_results_fail():
    for text in ('', '{}', '[]', '{"status":"FAIL","status":"PASS"}', 'not json'):
        assert v.parse_result('python', 0, text, EXPECTED)['status'] == 'FAIL'


def test_node_exact_summary_requires_all_unique_case_lines():
    text = 'PASS one\nPASS two\nPASS: 2 C20/F2-08/F2-07 cases; VM/static/compile only, real browser/API acceptance BLOCKED\n'
    assert v.parse_result('node-page', 0, text, EXPECTED)['status'] == 'PASS'
    for bad in (text + text, text.replace('PASS two\n', ''), text.replace('PASS two', 'PASS one'),
                text.replace('PASS: 2', 'PASS: 1'), 'PASS', text.replace('BLOCKED', 'PASS')):
        assert v.parse_result('node-page', 0, bad, EXPECTED)['status'] == 'FAIL'


def test_release_claims_at_any_level_fail():
    for field in ('release_allowed', 'release_evidence', 'formal_uat'):
        value = python_result(extra={field: True})
        assert v.parse_result('python', 0, json.dumps(value), EXPECTED)['status'] == 'FAIL'
    assert v.no_release_claims({'formal_uat': False})


def test_preflight_source_failure_runs_no_children():
    with patch.object(v, 'verify_sources', side_effect=ValueError('SOURCE_REVIEW_REQUIRED')), \
            patch.object(v.subprocess, 'run') as child:
        with pytest.raises(ValueError):
            v.run(ROOT)
        child.assert_not_called()


def test_source_change_during_run_blocks_binding():
    with patch.object(v, 'verify_sources', side_effect=[({'expected': EXPECTED}, 'hash'),
                                                      ValueError('SOURCE_REVIEW_REQUIRED')]), \
            patch.object(v, 'candidate', return_value=STATE), \
            patch.object(v.shutil, 'which', return_value='node'), \
            patch.object(v.subprocess, 'run', return_value=NS(returncode=0, stdout='')), \
            patch.object(v, 'parse_result', side_effect=lambda i, *a: good(i)):
        report = v.run(ROOT)
    assert not report['source_stable'] and v.exit_code(report, True) == 2


def test_identity_changes_during_run_block_binding():
    with patch.object(v, 'verify_sources', return_value=({'expected': EXPECTED}, 'hash')), \
            patch.object(v, 'candidate', side_effect=[STATE, {**STATE, 'commit': 'c' * 40}]), \
            patch.object(v.shutil, 'which', return_value='node'), \
            patch.object(v.subprocess, 'run', return_value=NS(returncode=0, stdout='')), \
            patch.object(v, 'parse_result', side_effect=lambda i, *a: good(i)):
        report = v.run(ROOT)
    assert not report['source_stable'] and v.exit_code(report, True) == 2


def manifest_fixture(tmp_path):
    source = tmp_path / 'enterprise-agent/app/synthetic.py'
    source.parent.mkdir(parents=True)
    source.write_text('synthetic')
    file = tmp_path / v.MANIFEST
    file.parent.mkdir(parents=True)
    data = {'schema': 'offline-sources-v1', 'checks': list(v.CHECKS),
            'finding_coverage': deepcopy(v.COVERAGE), 'expected': EXPECTED,
            'sources': {'enterprise-agent/app/synthetic.py': v.digest(source.read_bytes())}}
    return file, source, data


def test_manifest_missing_extra_or_changed_source_is_rejected(tmp_path):
    file, source, original = manifest_fixture(tmp_path)
    with patch.object(v, 'source_paths', return_value=list(original['sources'])):
        file.write_text(json.dumps(original))
        assert v.verify_sources(tmp_path)[0]['expected'] == EXPECTED
        for data in ({**original, 'sources': {}}, {**original, 'sources': {'extra': 'hash'}}):
            file.write_text(json.dumps(data))
            with pytest.raises(ValueError):
                v.verify_sources(tmp_path)
        file.write_text(json.dumps(original)); source.write_text('changed')
        with pytest.raises(ValueError):
            v.verify_sources(tmp_path)


def test_manifest_check_or_finding_omission_is_rejected(tmp_path):
    file, _, original = manifest_fixture(tmp_path)
    for update in ({'checks': list(v.CHECKS)[:-1]}, {'checks': list(v.CHECKS) + ['unknown']},
                   {'finding_coverage': {}}, {'expected': {'python': 0}},
                   {'expected': {**EXPECTED, 'python': True}}):
        file.write_text(json.dumps({**original, **update}))
        with patch.object(v, 'source_paths', return_value=list(original['sources'])):
            with pytest.raises(ValueError):
                v.verify_sources(tmp_path)


def test_source_policy_includes_new_code_and_data_not_ignored_outputs():
    names = ['enterprise-agent/tests/new.py', 'enterprise-agent/scripts/new.py',
             '.github/workflows/ci.yml', '.github/scripts/scan_secrets.py',
             '.github/tests/test_secret_scan.py', 'enterprise-agent/eval/sample_docs/source.md',
             'enterprise-agent/app/data.json', 'docs/README.md', v.MANIFEST]
    with patch.object(v, 'repository_files', return_value=names):
        assert set(v.source_paths(ROOT)) == set(names[:-2])


def test_commands_are_fixed_isolated_and_never_install_or_start_services():
    for ident in v.CHECKS:
        command = v.command(ident, ROOT)
        assert '--execute' not in command and 'pip' not in command
        assert all('run_eval.py' not in arg for arg in command)
        if not ident.startswith('node-'):
            assert command[:3] == [sys.executable, '-I', '-B']


def test_preloads_and_filter_environment_are_removed():
    with patch.object(v, 'verify_sources', return_value=({'expected': EXPECTED}, 'hash')), \
            patch.object(v, 'candidate', return_value=STATE), \
            patch.object(v.shutil, 'which', return_value='node'), \
            patch.dict(v.os.environ, {'NODE_OPTIONS': 'PRIVATE', 'NODE_V8_COVERAGE': 'PRIVATE',
                                      'PYTEST_ADDOPTS': '-k hidden', 'PYTEST_PLUGINS': 'hidden'}), \
            patch.object(v.subprocess, 'run', return_value=NS(returncode=0, stdout='')) as child:
        v.run(ROOT)
    environment = child.call_args.kwargs['env']
    assert not set(environment) & {'NODE_OPTIONS', 'NODE_V8_COVERAGE', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS'}


def test_ci_invokes_same_entry_and_preserves_security_dependencies():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    steps = workflow['jobs']['test']['steps']
    commands = '\n'.join(s.get('run', '') for s in steps)
    assert 'scripts/offline_verify.py --ci --record ${{ matrix.record-id }}' in commands
    assert 'python -m pytest tests/' not in commands
    assert 'pip-audit -r deploy/requirements-prod.txt' in commands
    assert 'python .github/scripts/scan_secrets.py' in commands
    assert 'python -m unittest discover -s .github/tests -p test_secret_scan.py' in commands
    assert 'gitleaks_8.24.3_linux_x64.tar.gz' in commands
    assert '9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c' in commands
    assert 'sha256sum --check -' in commands
    assert '--output pip-audit-report.txt' in commands
    checkout = next(s for s in steps if s.get('uses', '').startswith('actions/checkout@'))
    assert checkout['with']['fetch-depth'] == 0
    assert checkout['with']['ref'] == '${{ github.sha }}'
    scanner = (ROOT / '.github/scripts/scan_secrets.py').read_text()
    assert '--full-history' in scanner and '--redact=100' in scanner
    assert 'summary.json' in scanner
    assert workflow['jobs']['docker']['needs'] == 'test'
    assert any(s.get('uses', '').startswith('aquasecurity/trivy-action@')
               for s in workflow['jobs']['docker']['steps'])
    coverage = next(s for s in steps if s.get('with', {}).get('name') == 'coverage-${{ matrix.python-version }}')
    assert coverage['with']['if-no-files-found'] == 'error'
    assert coverage['with']['path'].endswith('offline-pytest-*/coverage.xml')


def test_ci_matrix_record_ids_pass_actual_cli_admission(tmp_path, capsys):
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    job = workflow['jobs']['test']
    matrix = job['strategy']['matrix']
    assert set(matrix) == {'include'}
    rows = matrix['include']
    assert [row['python-version'] for row in rows] == ['3.11', '3.13']
    assert len({row['record-id'] for row in rows}) == len(rows)
    command = next(step['run'] for step in job['steps']
                   if 'scripts/offline_verify.py' in step.get('run', ''))
    report = {'schema': 'current-offline-v1', **v.summarize(all_good(), True, True)}
    for row in rows:
        rendered = command
        for key, value in row.items():
            rendered = rendered.replace('${{ matrix.' + key + ' }}', value)
        argv = shlex.split(rendered)
        assert argv[:3] == ['python', '-I', '-B']
        with patch.object(v, 'ROOT', tmp_path), \
                patch.object(v, 'run', return_value=report) as execute, \
                patch.object(v.sys, 'argv', argv[3:]):
            assert v.main() == 0
            execute.assert_called_once()
        saved = tmp_path / 'enterprise-agent/eval/results/offline' / (row['record-id'] + '.json')
        assert json.loads(saved.read_text())['execution_status'] == 'PASS'
        assert json.loads(capsys.readouterr().out)['overall_status'] == 'BLOCKED'


def test_unsafe_record_ids_remain_rejected_before_execution(tmp_path, capsys):
    for record in ('ci-3.11', 'ci-3.13', '../escape', '/absolute', 'a' * 81):
        with patch.object(v, 'ROOT', tmp_path), patch.object(v, 'run') as execute, \
                patch.object(v.sys, 'argv', ['entry', '--ci', '--record', record]):
            assert v.main() == 2
            execute.assert_not_called()
        assert json.loads(capsys.readouterr().out)['overall_status'] == 'BLOCKED'
    assert not (tmp_path / 'enterprise-agent').exists()


def test_legacy_frozen_inventory_is_not_implicitly_rewritten():
    old = json.loads((ROOT / 'enterprise-agent/scripts/final_candidate_sources.json').read_text())
    assert v.MANIFEST != 'enterprise-agent/scripts/final_candidate_sources.json'
    assert 'enterprise-agent/tests/test_browser_delivery.cjs' in old['sources']
    assert all('final_candidate.py' not in path for path, _ in v.CHECKS.values())


def test_paths_reject_traversal_and_symlink():
    for name in ('../private', '/absolute', ''):
        with pytest.raises(ValueError):
            v.checked_path(ROOT, name)
    with patch.object(Path, 'is_symlink', return_value=True):
        with pytest.raises(ValueError):
            v.checked_path(ROOT, 'synthetic')


def test_pytest_helper_rejects_filters_before_execution(capsys):
    with patch.object(p.sys, 'argv', ['helper', '-k', 'subset']):
        assert p.main() == 1
    assert json.loads(capsys.readouterr().out)['reason'] == 'FILTERS_NOT_ALLOWED'


def test_pytest_retained_directory_creates_missing_checkout_parents(tmp_path):
    assert not (tmp_path / 'eval').exists()
    with patch.object(p, 'uuid4', return_value=NS(hex='fresh')):
        retained = p.create_retained_directory(tmp_path)
    assert retained == tmp_path / 'eval/results/offline-pytest-fresh'
    assert retained.is_dir()
    receipt = retained / 'receipt.json'
    receipt.write_text('synthetic retained evidence')
    assert receipt.read_text() == 'synthetic retained evidence'


def test_pytest_retained_directory_rejects_collision_without_changing_evidence(tmp_path):
    with patch.object(p, 'uuid4', return_value=NS(hex='collision')):
        retained = p.create_retained_directory(tmp_path)
        evidence = retained / 'receipt.json'
        evidence.write_text('existing retained evidence')
        with pytest.raises(FileExistsError):
            p.create_retained_directory(tmp_path)
    assert evidence.read_text() == 'existing retained evidence'
    assert list(retained.iterdir()) == [evidence]


def test_pytest_helper_requires_declared_installed_dependencies():
    with patch.object(p.importlib.metadata, 'version', side_effect=p.importlib.metadata.PackageNotFoundError):
        with pytest.raises(p.importlib.metadata.PackageNotFoundError):
            p.dependencies_match()


def test_pytest_helper_clears_telemetry_mode_before_application_import(capsys):
    def unavailable():
        assert 'TELEMETRY_MODE' not in p.os.environ
        assert 'OTEL_ENABLED' not in p.os.environ
        raise ImportError
    with patch.object(p.sys, 'argv', ['helper']), \
            patch.dict(p.os.environ, {'TELEMETRY_MODE': 'synthetic', 'OTEL_ENABLED': 'true'}), \
            patch.object(p, 'dependencies_match', side_effect=unavailable):
        assert p.main() == 2
    assert json.loads(capsys.readouterr().out)['reason'] == 'DEPENDENCIES_UNAVAILABLE'


def test_unknown_result_kind_and_nonzero_control_output_fail():
    assert v.parse_result('unknown', 0, '{}', EXPECTED)['status'] == 'FAIL'
    assert v.parse_result('frontend-assets', 1, 'PASS: 7 browser distribution/license files; runtime acceptance BLOCKED', EXPECTED)['status'] == 'FAIL'


def test_retained_link_fixtures_are_allowed_but_external_links_are_denied(tmp_path):
    counters = Counter()
    guard = p.diagnostic_guard(tmp_path, counters)
    base = tmp_path / 'eval/results'
    guard('os.symlink', (str(base / 'target'), str(base / 'link'), -1))
    assert not counters
    for source, target in ((tmp_path / 'private', base / 'link'),
                           (base / 'target', tmp_path / 'outside')):
        with pytest.raises(RuntimeError, match='OFFLINE_LINK_ESCAPE'):
            guard('os.symlink', (str(source), str(target), -1))
    assert counters['OFFLINE_LINK_ESCAPE'] == 2


def test_diagnostic_guard_never_permits_deletion_or_network(tmp_path):
    counters = Counter()
    guard = p.diagnostic_guard(tmp_path, counters)
    for event in ('os.remove', 'os.rmdir', 'os.rename', 'socket.connect', 'socket.bind'):
        with pytest.raises(RuntimeError):
            guard(event, (str(tmp_path / 'eval/results/file'),))
    assert sum(counters.values()) == 5


def test_diagnostic_guard_denies_private_env_and_outside_writes(tmp_path):
    import os
    guard = p.diagnostic_guard(tmp_path, Counter())
    for path, flags in ((tmp_path / '.env', os.O_RDONLY),
                        (tmp_path / 'outside', os.O_WRONLY)):
        with pytest.raises(RuntimeError):
            guard('open', (str(path), None, flags))


def test_malformed_python_counters_and_rag_objects_cannot_pass():
    for counters in ([], {'passed': 2, 'skipped': -1}, {'passed': 2, 'subtest_passed': True}):
        assert v.parse_result('python', 0, json.dumps(python_result(counts=counters)), EXPECTED)['status'] == 'FAIL'
    assert v.parse_result('rag-controls', 0, '{"safe_controls":[]}', EXPECTED)['status'] == 'FAIL'


def test_default_plan_never_executes_children(capsys):
    with patch.object(v.sys, 'argv', ['entry']), patch.object(v, 'run') as execute:
        assert v.main() == 0
        execute.assert_not_called()
    assert json.loads(capsys.readouterr().out)['status'] == 'PLAN_ONLY'


def test_record_collision_is_rejected_before_execution_and_keeps_bytes(tmp_path, capsys):
    target = tmp_path / 'enterprise-agent/eval/results/offline/retained.json'
    target.parent.mkdir(parents=True)
    target.write_text('retained original')
    with patch.object(v, 'ROOT', tmp_path), patch.object(v, 'run') as execute, \
            patch.object(v.sys, 'argv', ['entry', '--ci', '--record', 'retained']):
        assert v.main() == 2
        execute.assert_not_called()
    assert target.read_text() == 'retained original'
    report = json.loads(capsys.readouterr().out)
    assert not report['release_allowed'] and report['overall_status'] == 'BLOCKED'


def test_ci_record_retains_offline_success_and_overall_blocked(tmp_path, capsys):
    report = {'schema': 'current-offline-v1', **v.summarize(all_good(), True, True)}
    with patch.object(v, 'ROOT', tmp_path), patch.object(v, 'run', return_value=report), \
            patch.object(v.sys, 'argv', ['entry', '--ci', '--record', 'fresh']):
        assert v.main() == 0
    saved = json.loads((tmp_path / 'enterprise-agent/eval/results/offline/fresh.json').read_text())
    assert saved['overall_status'] == 'BLOCKED' and not saved['formal_uat']
    assert json.loads(capsys.readouterr().out)['execution_status'] == 'PASS'


def test_rag_controls_require_each_case_and_never_semantic_acceptance():
    ids = ['PI01', 'PI02', 'PI03', 'PI04', 'NG01', 'NG02', 'NG03', 'NG04']
    def part(gate, count):
        return {'case_denominator': 8, 'mechanical_pass_count': count, 'mechanical_gate': gate,
                'missing_case_ids': [], 'samples': [{'case_id': i, 'mechanical_check': gate} for i in ids],
                'actual_pipeline_executed': False, 'quality_acceptance': 'BLOCKED',
                'model_robustness': 'NOT_MEASURED', 'semantic_review': 'PENDING'}
    original = {'checker_verification': 'PASS', 'model_robustness': 'NOT_MEASURED',
                'semantic_review': 'PENDING', 'quality_acceptance': 'BLOCKED', 'runtime': 'BLOCKED',
                'unexpected_negative_case_ids': [], 'safe_controls': part('PASS', 8),
                'unsafe_controls': part('FAIL', 0)}
    assert v.parse_result('rag-controls', 0, json.dumps(original), EXPECTED)['status'] == 'PASS'
    for field in ('duplicate', 'missing', 'semantic'):
        value = deepcopy(original)
        if field == 'duplicate':
            value['safe_controls']['samples'][0] = value['safe_controls']['samples'][1]
        if field == 'missing':
            value['unsafe_controls']['samples'].pop()
        if field == 'semantic':
            value['safe_controls']['quality_acceptance'] = 'PASS'
        assert v.parse_result('rag-controls', 0, json.dumps(value), EXPECTED)['status'] == 'FAIL'


def test_integrity_claims_cannot_clear_rights_or_skip_count_checks():
    value = {'integrity': 'PASS', 'distribution_acceptance': 'BLOCKED', 'runtime': 'BLOCKED',
             'full_rag': 'BLOCKED', 'c10': 'OPEN', 'pending_source_files': 438, 'production_packages': 98}
    assert v.parse_result('provenance', 0, json.dumps(value), EXPECTED)['status'] == 'PASS'
    for update in ({'distribution_acceptance': 'PASS'}, {'pending_source_files': 437}, {'c10': 'CLOSED'}):
        assert v.parse_result('provenance', 0, json.dumps({**value, **update}), EXPECTED)['status'] == 'FAIL'
