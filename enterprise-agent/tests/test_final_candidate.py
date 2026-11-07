"""C24 receipt regressions; injected children and retained synthetic files only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'candidate', ROOT/'enterprise-agent/scripts/final_candidate.py')
assert SPEC and SPEC.loader
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)
FIXTURES = ROOT/'enterprise-agent/eval/results'/('c24-tests-'+uuid.uuid4().hex)
ROW = ('fixture', 'tests/fixture.py', 'unittest', 2, 0)
GOOD = 'Ran 2 tests in 0.001s\n\nOK\n'
STATE = {'commit': 'a'*40, 'tracked_content_dirty': False, 'untracked_files': 0}


def plans() -> dict:
    return {'execution_status': 'PASS', 'overall_status': 'BLOCKED',
            'formal_uat': False, 'release_allowed': False, 'release_evidence': False,
            'results': [{'id': name, 'result_status': status} for name, status in
                        [('uat-plan', 'PASS'), ('uat-readiness', 'BLOCKED'),
                         ('grey-plan', 'PASS'), ('release-gate', 'BLOCKED'),
                         ('g0-replay', 'PASS')]]}


class CandidateTests(unittest.TestCase):
    def test_python_isolation_and_node_no_shell(self) -> None:
        self.assertEqual(c.command(ROW, ROOT)[:3], [sys.executable, '-I', '-B'])
        node = next(r for r in c.SUITES if r[0] == 'C20')
        self.assertEqual(c.command(node, ROOT)[0], 'node')
        self.assertEqual(len(c.command(node, ROOT)), 2)

    def test_empty_wrong_and_duplicate_counts_never_pass(self) -> None:
        for text in ('', 'Ran 0 tests in 0.01s\nOK\n', GOOD+GOOD,
                     'Ran 3 tests in 0.01s\nOK\n', 'OK\n'):
            self.assertEqual(c.parse_result(ROW, 0, text)['status'], 'FAIL')
        self.assertEqual(c.parse_result(ROW, 0, GOOD)['passed'], 2)

    def test_failure_exit_cannot_be_hidden_by_ok_output(self) -> None:
        result = c.parse_result(ROW, 1, GOOD+'SYNTHETIC_PRIVATE_DETAIL')
        self.assertEqual(result['status'], 'FAIL')
        self.assertNotIn('SYNTHETIC_PRIVATE_DETAIL', json.dumps(result))

    def test_only_declared_dependency_skip_is_accepted(self) -> None:
        text = ('Declared PyYAML dependency unavailable; parse YAML separately\n'
                'Ran 11 tests in 0.01s\nOK (skipped=1)\n')
        result = c.parse_result(c.SUITES[0], 0, text)
        self.assertEqual((result['status'], result['passed'], result['skipped']),
                         ('BLOCKED', 10, 1))
        for bad in (text.replace('skipped=1', 'skipped=2'), text.split('\n', 1)[1]):
            self.assertEqual(c.parse_result(c.SUITES[0], 0, bad)['status'], 'FAIL')
        self.assertEqual(
            c.parse_result(ROW, 0, text.replace('11 tests','2 tests'))['status'], 'FAIL')

    def test_node_requires_exact_current_summary(self) -> None:
        row = next(r for r in c.SUITES if r[0] == 'C20')
        good = 'PASS: 45 C20 cases; VM/static only, real browser/API acceptance BLOCKED\n'
        self.assertEqual(c.parse_result(row, 0, good)['passed'], 45)
        for bad in (good.replace('45','0'), good+good, 'PASS'):
            self.assertEqual(c.parse_result(row, 0, bad)['status'], 'FAIL')

    def test_plan_results_never_claim_release(self) -> None:
        row = c.SUITES[-1]
        self.assertEqual(c.parse_result(row, 2, json.dumps(plans()))['status'], 'BLOCKED')
        for field in ('release_allowed', 'release_evidence', 'formal_uat'):
            value = plans(); value[field] = True
            self.assertEqual(c.parse_result(row, 2, json.dumps(value))['status'], 'FAIL')
        value = plans(); value['results'].append(value['results'][0])
        self.assertEqual(c.parse_result(row, 2, json.dumps(value))['status'], 'FAIL')
        self.assertEqual(c.parse_result(row, 0, json.dumps(plans()))['status'], 'FAIL')

    def test_failure_priority_and_separate_file_counts(self) -> None:
        good = c.parse_result(ROW, 0, GOOD)
        result = c.summarize([good, {'status':'FAIL','unit':'assets'}], True, True)
        self.assertEqual(result['overall_status'], 'FAIL')
        self.assertEqual(result['passed_tests'], 2)
        self.assertFalse(result['release_allowed'])

    def test_dirty_or_changed_candidate_is_not_bound(self) -> None:
        for stable, clean in ((False,True),(True,False),(False,False)):
            result = c.summarize([c.parse_result(ROW,0,GOOD)],stable,clean)
            self.assertEqual(result['candidate_binding'], 'BLOCKED')
            self.assertEqual(result['overall_status'], 'BLOCKED')

    def test_source_drift_stops_before_child(self) -> None:
        with patch.object(c,'verify_sources',side_effect=ValueError('SOURCE_REVIEW_REQUIRED')), \
                patch.object(c.subprocess,'run') as child:
            with self.assertRaises(ValueError): c.run(ROOT)
            child.assert_not_called()

    def test_candidate_mutation_retains_results_but_blocks_binding(self) -> None:
        states = [STATE, {**STATE,'commit':'b'*40}]
        with patch.object(c,'SUITES',(ROW,)), \
                patch.object(c,'verify_sources',return_value='hash'), \
                patch.object(c,'candidate',side_effect=states), \
                patch.object(c.subprocess,'run',return_value=SimpleNamespace(
                    returncode=0, stdout=GOOD, stderr='')):
            result = c.run(ROOT)
        self.assertEqual(result['candidate_binding'],'BLOCKED')
        self.assertEqual(result['passed_tests'],2)
        self.assertFalse(result['source_stable'])

    def test_timeout_is_failed_without_exception_payload(self) -> None:
        with patch.object(c,'SUITES',(ROW,)), \
                patch.object(c,'verify_sources',return_value='hash'), \
                patch.object(c,'candidate',return_value=STATE), \
                patch.object(c.subprocess,'run',side_effect=subprocess.TimeoutExpired(
                    'PRIVATE',90)):
            result=c.run(ROOT)
        self.assertEqual(result['overall_status'],'FAIL')
        self.assertEqual(result['results'][0]['reason'],'TIMEOUT')
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_missing_executable_is_blocked_and_environment_preloads_removed(self) -> None:
        with patch.object(c,'SUITES',(ROW,)), \
                patch.object(c,'verify_sources',return_value='hash'), \
                patch.object(c,'candidate',return_value=STATE), \
                patch.dict(c.os.environ,{'NODE_OPTIONS':'PRIVATE','NODE_V8_COVERAGE':'PRIVATE'}), \
                patch.object(c.subprocess,'run',side_effect=FileNotFoundError('PRIVATE')) as child:
            result=c.run(ROOT)
        self.assertEqual(result['results'][0]['status'],'BLOCKED')
        self.assertNotIn('NODE_OPTIONS',child.call_args_list[0].kwargs['env'])
        self.assertNotIn('NODE_V8_COVERAGE',child.call_args_list[0].kwargs['env'])
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_record_collision_preserves_original_bytes(self) -> None:
        root=FIXTURES/uuid.uuid4().hex
        c.record(root,'retained',{'value':'original'})
        path=root/'enterprise-agent/eval/results/final-candidate/retained.json'
        before=path.read_bytes()
        with self.assertRaises(FileExistsError):c.record(root,'retained',{'value':'replacement'})
        self.assertEqual(path.read_bytes(),before)

    def test_record_rejects_path_traversal_before_mkdir(self) -> None:
        with patch.object(Path,'mkdir') as mkdir:
            for value in ('../private','/absolute','','a'*81):
                with self.assertRaises(ValueError):c.record(ROOT,value,{})
            mkdir.assert_not_called()
        with self.assertRaises(ValueError):c.checked_path(ROOT,'../private')

    def test_symlink_component_is_rejected(self) -> None:
        with patch.object(Path,'is_symlink',return_value=True):
            with self.assertRaises(ValueError):c.checked_path(ROOT,'child/file')

    def test_manifest_requires_all_entries_and_correct_hashes(self) -> None:
        root=FIXTURES/uuid.uuid4().hex
        manifest=root/c.MANIFEST;manifest.parent.mkdir(parents=True)
        source=root/'enterprise-agent/tests/fixture.py';source.parent.mkdir(parents=True)
        source.write_text('synthetic source')
        content={'sources':{'enterprise-agent/tests/fixture.py':c.digest(source.read_bytes())}}
        manifest.write_text(json.dumps(content))
        with patch.object(c,'SUITES',(ROW,)):
            self.assertEqual(c.verify_sources(root),c.digest(manifest.read_bytes()))
            source.write_text('changed source')
            with self.assertRaises(ValueError):c.verify_sources(root)
            manifest.write_text(json.dumps({'sources':{}}))
            with self.assertRaises(ValueError):c.verify_sources(root)


if __name__ == '__main__':
    def guard(event: str, args: tuple) -> None:
        if event.startswith(('socket.','subprocess.')) or event in {
                'os.remove','os.rmdir','os.rename','os.system','os.symlink','os.link'}:
            raise RuntimeError('OFFLINE_SIDE_EFFECT_DENIED')
        if event in {'os.mkdir','os.chmod','os.chown'}:
            path=Path(args[0]).absolute()
            if path != FIXTURES and FIXTURES not in path.parents:
                raise RuntimeError('OFFLINE_PATH_DENIED')
        if event=='open' and not isinstance(args[0],int):
            writing=(isinstance(args[1],str) and any(c in args[1] for c in 'wax+')) or (
                isinstance(args[2],int) and args[2]&3)
            if writing and FIXTURES not in Path(args[0]).absolute().parents:
                raise RuntimeError('OFFLINE_WRITE_DENIED')
    sys.addaudithook(guard)
    unittest.main(verbosity=2)
