"""Synthetic input/inventory tests; no Docker, package installation or live repository calls."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_verifier', ROOT/'scripts/verify_build.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def fixture(tmp_path: Path) -> tuple[Path, dict]:
    for name in build.INPUT_FILES | {'deploy/build-inputs.json'}:
        target = tmp_path/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    return tmp_path, json.loads((tmp_path/'deploy/build-inputs.json').read_text())


def reseal(root: Path, manifest: dict, name: str) -> None:
    manifest['files'][name] = build.digest((root/name).read_bytes())
    (root/'deploy/build-inputs.json').write_text(json.dumps(manifest))


def installed(manifest: dict) -> list[tuple[str, str]]:
    return [(n, p['version']) for n, p in manifest['packages'].items()]


OS_PACKAGES = 'ca-certificates\t1\tall\ntzdata\t2\tall\nlibpq5:amd64\t3\tamd64\n'


def inventory(root: Path, manifest: dict, **kwargs: object) -> dict:
    args = dict(profile='production', python=manifest['python'], system='Linux',
                machine='x86_64', os_packages=OS_PACKAGES)
    args.update(kwargs)
    return build.inventory(root, manifest, installed(manifest), **args)


def test_reviewed_production_inputs_pass_without_runtime_imports() -> None:
    manifest = build.verify_inputs(ROOT)
    assert len(manifest['packages']) == 98
    assert manifest['packages']['numpy']['version'] == '2.4.6'
    assert manifest['limits']['two_clean_builds'] == 'BLOCKED'
    assert manifest['limits']['c10'] == 'OPEN'


@pytest.mark.parametrize('text', ['', 'numpy>=2', 'numpy==2.*', 'numpy @ https://example.invalid/x',
                                  '-r other.txt', 'numpy==2 ; python_version>"3"',
                                  'numpy==2\nnumpy==2', 'some_pkg==1\nsome-pkg==1',
                                  'numpy[unreviewed]==2', 'numpy==2 --index-url=x'])
def test_ranges_direct_urls_markers_duplicate_names_and_options_rejected(text: str) -> None:
    with pytest.raises(build.InvalidBuild):
        build.pins(text)


@pytest.mark.parametrize('suffix', ['', '--hash=md5:'+'a'*32, '--hash=sha256:x',
                                  '--hash=sha256:'+'a'*64+' --hash=sha256:'+'a'*64])
def test_hashes_are_required_valid_and_unique(suffix: str) -> None:
    with pytest.raises(build.InvalidBuild):
        build.pins('numpy==2 '+suffix, hashes=True)


def test_continuation_lines_extras_and_normalized_names() -> None:
    result = build.pins('PyJWT[crypto]==2.15.0 \\\n    --hash=sha256:'+'a'*64, hashes=True)
    assert result == {'pyjwt': {'version':'2.15.0', 'extras':'crypto', 'hashes':['a'*64]}}


@pytest.mark.parametrize('name', sorted(build.INPUT_FILES))
def test_any_sealed_recipe_or_dependency_change_fails(tmp_path: Path, name: str) -> None:
    root, manifest = fixture(tmp_path)
    p = root/name
    p.write_bytes(p.read_bytes()+b'\n# synthetic change\n')
    with pytest.raises(build.InvalidBuild, match='BUILD_INPUT_DRIFT'):
        build.verify_inputs(root)


@pytest.mark.parametrize('mutation', ['version', 'hash', 'package_set', 'source', 'base', 'frontend'])
def test_manifest_and_lock_disagreement_fails(tmp_path: Path, mutation: str) -> None:
    root, manifest = fixture(tmp_path)
    if mutation == 'version':
        manifest['packages']['numpy']['version'] = '0'
    elif mutation == 'hash':
        manifest['packages']['numpy']['wheels'][0]['sha256'] = '0'*64
    elif mutation == 'package_set':
        manifest['packages']['unexpected'] = manifest['packages']['numpy']
    elif mutation == 'source':
        manifest['packages']['numpy']['source'] = 'https://example.invalid/source'
    else:
        manifest[mutation]['reference'] = 'python:latest'
    (root/'deploy/build-inputs.json').write_text(json.dumps(manifest))
    with pytest.raises(build.InvalidBuild):
        build.verify_inputs(root)


@pytest.mark.parametrize('mutation', ['remove_hash_mode', 'range_upgrade', 'unsigned_os'])
def test_resealed_inputs_still_enforce_install_policy(tmp_path: Path, mutation: str) -> None:
    root, manifest = fixture(tmp_path)
    name = 'deploy/debian.sources' if mutation == 'unsigned_os' else 'Dockerfile.prod'
    p = root/name
    text = p.read_text()
    if mutation == 'remove_hash_mode':
        text = text.replace('--require-hashes', '')
    elif mutation == 'range_upgrade':
        text += '\nRUN pip install --upgrade numpy\n'
    else:
        text = text.replace('Signed-By:', 'Untrusted-Key:')
    p.write_text(text)
    reseal(root, manifest, name)
    with pytest.raises(build.InvalidBuild):
        build.verify_inputs(root)


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'version', 'duplicate'])
def test_installed_inventory_rejects_missing_extra_version_and_duplicate(mutation: str) -> None:
    manifest = build.verify_inputs(ROOT)
    packages = installed(manifest)
    if mutation == 'missing':
        packages = packages[1:]
    elif mutation == 'extra':
        packages += [('unexpected-package', '1')]
    elif mutation == 'version':
        packages[0] = (packages[0][0], '0')
    else:
        packages += [packages[0]]
    with pytest.raises(build.InvalidBuild):
        build.compare_packages(manifest['packages'], packages, profile='production')


def test_experimental_ml_is_never_production_verified() -> None:
    manifest = build.verify_inputs(ROOT)
    packages = installed(manifest)+[('synthetic-ml-extra','1')]
    result = build.inventory(ROOT, manifest, packages, profile='experimental-ml',
                             python=manifest['python'], system='Linux', machine='x86_64',
                             os_packages=OS_PACKAGES)
    assert result['status'] == 'EXPERIMENTAL_NOT_ACCEPTED'
    assert result['runtime_acceptance'] == 'BLOCKED'
    assert result['full_rag'] == 'BLOCKED' and result['c10'] == 'OPEN'


@pytest.mark.parametrize('values', [{'python':'3.13.15'}, {'system':'Darwin'},
                                   {'machine':'aarch64'}, {'profile':'unknown'},
                                   {'os_packages':''}, {'os_packages':OS_PACKAGES+OS_PACKAGES},
                                   {'os_packages':'not tab separated'}])
def test_inventory_rejects_platform_or_os_record_mismatch(values: dict) -> None:
    with pytest.raises(build.InvalidBuild):
        inventory(ROOT, build.verify_inputs(ROOT), **values)


def test_inventory_is_order_independent_and_bound_to_input_bytes() -> None:
    manifest = build.verify_inputs(ROOT)
    first = inventory(ROOT, manifest)
    second = build.inventory(ROOT, manifest, reversed(installed(manifest)), profile='production',
                             python=manifest['python'], system='Linux', machine='x86_64',
                             os_packages='\n'.join(reversed(OS_PACKAGES.splitlines()))+'\n')
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first['build_inputs_sha256'] == build.digest((ROOT/'deploy/build-inputs.json').read_bytes())
    assert first['status'] == 'INSTALLED_SET_VERIFIED'
    assert first['bit_identical_rebuild'] == 'NOT_ESTABLISHED'


def test_offline_cli_does_not_probe_host_or_start_processes(monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr(sys, 'argv', ['verify_build', '--root', str(ROOT)])
    forbidden = Mock(side_effect=AssertionError('host probe forbidden'))
    monkeypatch.setattr(build.subprocess, 'run', forbidden)
    monkeypatch.setattr(build.importlib.metadata, 'distributions', forbidden)
    assert build.main() == 0
    assert json.loads(capsys.readouterr().out)['installed_image'] == 'BLOCKED'
    forbidden.assert_not_called()


def test_ci_keeps_security_gates_and_exports_installed_image_before_publish() -> None:
    workflow = yaml.safe_load((ROOT.parent/'.github/workflows/ci.yml').read_text())
    steps = workflow['jobs']['docker']['steps']
    builder = next(s for s in steps if s.get('uses','').startswith('docker/build-push-action@'))
    assert builder['with']['platforms'] == 'linux/amd64'
    assert builder['with']['push'] is False and builder['with']['load'] is True
    run_index = next(i for i,s in enumerate(steps) if '--installed' in s.get('run',''))
    scan_index = next(i for i,s in enumerate(steps) if s.get('uses','').startswith('aquasecurity/trivy-action@'))
    publish_index = next(i for i,s in enumerate(steps) if 'docker push' in s.get('run',''))
    assert run_index < scan_index < publish_index
    assert '--network none --read-only' in steps[run_index]['run']
    assert 'docker image inspect' in steps[run_index]['run']
    assert steps[scan_index]['with']['exit-code'] == '1'
    assert steps[scan_index]['with']['severity'] == 'HIGH,CRITICAL'
    upload = next(s for s in steps if s.get('with',{}).get('name')=='production-build-inventory')
    assert 'installed-inventory.json' in upload['with']['path']
    assert 'image-identity.json' in upload['with']['path']
    assert upload['with']['if-no-files-found'] == 'error'
    assert 'pip-audit -r deploy/requirements-prod.txt' in (ROOT.parent/'.github/workflows/ci.yml').read_text()


def test_installed_cli_uses_bounded_read_only_inventory_command(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    from types import SimpleNamespace
    manifest = build.verify_inputs(ROOT)
    monkeypatch.setattr(sys, 'argv', ['verify_build', '--root', str(ROOT), '--installed'])
    monkeypatch.setattr(build.platform, 'python_version', lambda: manifest['python'])
    monkeypatch.setattr(build.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(build.platform, 'machine', lambda: 'x86_64')
    monkeypatch.setattr(build.importlib.metadata, 'distributions', lambda: [
        SimpleNamespace(metadata={'Name':n}, version=v) for n,v in installed(manifest)])
    command = Mock(return_value=SimpleNamespace(stdout=OS_PACKAGES))
    monkeypatch.setattr(build.subprocess, 'run', command)
    assert build.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'INSTALLED_SET_VERIFIED'
    args, kwargs = command.call_args
    assert args[0][0:2] == ['dpkg-query', '-W']
    assert kwargs == {'capture_output':True, 'text':True, 'check':True, 'timeout':15}


def test_cli_failure_is_nonzero_and_does_not_expose_exception_text(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr(sys, 'argv', ['verify_build', '--root', str(ROOT)])
    monkeypatch.setattr(build, 'verify_inputs', Mock(side_effect=OSError('PRIVATE local path')))
    assert build.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        'status':'FAIL', 'code':'BUILD_VERIFICATION_FAILED'}


@pytest.mark.parametrize('python_full_version', ['3.11.3', '3.13.16'])
def test_reviewed_metadata_closure_preserves_ci_and_production_patch_baselines(
        python_full_version: str) -> None:
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    manifest = build.verify_inputs(ROOT)
    packages = manifest['packages']
    python_version = '.'.join(python_full_version.split('.')[:2])
    env = {'python_version':python_version, 'python_full_version':python_full_version,
           'sys_platform':'linux', 'platform_machine':'x86_64', 'platform_system':'Linux',
           'implementation_name':'cpython', 'implementation_version':python_full_version,
           'platform_python_implementation':'CPython', 'os_name':'posix', 'extra':''}
    for name, record in packages.items():
        assert env['python_full_version'] in SpecifierSet(record['requires_python'] or ''), name
        extras = ['', 'crypto'] if name == 'pyjwt' else ['']
        for value in record['requires_dist']:
            dep = Requirement(value)
            if dep.marker and not any(dep.marker.evaluate(dict(env, extra=e)) for e in extras):
                continue
            dependency = packages[build.normalized(dep.name)]
            assert dependency['version'] in dep.specifier, (name, value)
