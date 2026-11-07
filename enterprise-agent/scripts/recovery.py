"""Plan-first cold recovery for explicitly isolated Docker projects; retains every asset."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from typing import Any
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'deploy/schema_manifest.json'
SPEC = importlib.util.spec_from_file_location(
    'recovery_archive', Path(__file__).with_name('recovery_archive.py'))
assert SPEC and SPEC.loader
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)
CORE = {'postgres_data', 'redis_data', 'etcd_data', 'minio_data', 'milvus_data', 'audit_state'}
ORDER = {'postgres': 0, 'redis': 0, 'etcd': 0, 'minio': 0, 'milvus-standalone': 1,
         'reference-crm': 2, 'reference-ticket': 2, 'reference-mail': 2, 'reference-idp': 2,
         'alert-receiver': 2, 'observation-monitor': 3, 'api': 4, 'api2': 4, 'worker': 4,
         'nginx': 5}
INSPECT = ('{"id":{{json .Id}},"image":{{json .Image}},'
           '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
           '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
           '"running":{{json .State.Running}},"paused":{{json .State.Paused}},'
           '"restarting":{{json .State.Restarting}},"exit_code":{{json .State.ExitCode}},'
           '"recovery_helper":{{json (index .Config.Labels "businessagent.recovery.helper")}},'
           '"mounts":{{json .Mounts}}}')


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def identity(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,127}', value):
        raise ValueError('RECOVERY_NAME_REJECTED')
    return value


def load(path: Path, limit: int = 268435456) -> Any:
    archive.safe_path(path)
    if path.stat().st_size > limit:
        raise ValueError('RECOVERY_JSON_TOO_LARGE')
    return json.loads(path.read_text())


class Docker:
    def run(self, *args: str, timeout: int = 120) -> str:
        # No shell, retries, automatic pulls, inherited output or raw exceptions.
        try:
            result = subprocess.run(['docker', *args], check=False, capture_output=True,
                                    text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError('DOCKER_COMMAND_UNCERTAIN') from None
        if result.returncode:
            raise RuntimeError('DOCKER_COMMAND_FAILED')
        return result.stdout.strip()

    def inventory(self, project: str) -> dict[str, Any]:
        ids = self.run('ps', '-aq', '--no-trunc').splitlines()
        if len(ids) > 512:
            raise ValueError('CONTAINER_INVENTORY_LIMIT')
        rows = [json.loads(self.run('inspect', '--format', INSPECT, cid)) for cid in ids]
        own = []
        for row in rows:
            if row['project'] != project:
                continue
            mounts = [{'type': m['Type'], 'name': m.get('Name', ''),
                       'target': m['Destination'], 'writable': m['RW']} for m in row['mounts']]
            own.append({k: row[k] for k in ('id', 'image', 'service', 'running', 'paused',
                                          'restarting', 'exit_code')} | {'mounts': mounts})
        volumes = {m['name'] for c in own for m in c['mounts'] if m['type'] == 'volume'}
        labelled = self.run('volume', 'ls', '--filter',
                            'label=com.docker.compose.project='+project, '--format', '{{.Name}}')
        volumes.update(labelled.splitlines())
        if len(volumes) > 128:
            raise ValueError('VOLUME_INVENTORY_LIMIT')
        outsiders = sorted(row['id'] for row in rows if row['project'] != project
                           and any(m.get('Name') in volumes and m['RW'] for m in row['mounts'])
                           and (row['running'] or row['paused'] or row['restarting']
                                or row.get('recovery_helper') != 'c22'))
        volume_info = []
        template = ('{"name":{{json .Name}},"driver":{{json .Driver}},'
                    '"options":{{if .Options}}true{{else}}false{{end}},'
                    '"project":{{json (index .Labels "com.docker.compose.project")}},'
                    '"logical":{{json (index .Labels "com.docker.compose.volume")}}}')
        for volume in sorted(volumes):
            raw = self.run('volume', 'inspect', '--format', template, volume)
            volume_info.append(json.loads(raw))
        return {'project': project, 'containers': sorted(own, key=lambda c: c['id']),
                'volumes': volume_info, 'external_writers': outsiders}


def validate_source(source: dict[str, Any]) -> list[str]:
    project = name(source['project'])
    containers = source['containers']
    if source['external_writers'] or not 1 <= len(containers) <= 64:
        raise ValueError('SOURCE_WRITERS_REJECTED')
    volumes = set(); ids = set(); services = set()
    for c in containers:
        if (not re.fullmatch('[0-9a-f]{64}', c['id']) or c['id'] in ids
                or not re.fullmatch('sha256:[0-9a-f]{64}', c['image'])
                or c['paused'] or c['restarting'] or not isinstance(c['running'], bool)):
            raise ValueError('SOURCE_CONTAINER_REJECTED')
        ids.add(c['id']); services.add(name(c['service']))
        for mount in c['mounts']:
            if mount['type'] == 'volume':
                volume = name(mount['name'])
                if not volume.startswith(project + '_'):
                    raise ValueError('SOURCE_VOLUME_REJECTED')
                volumes.add(volume)
            elif mount['type'] != 'bind' or mount['writable']:
                raise ValueError('SOURCE_MOUNT_REJECTED')
    required_services = {'api', 'worker', 'postgres', 'redis', 'etcd', 'minio', 'milvus-standalone'}
    if (not required_services.issubset(services)
            or not {project+'_'+v for v in CORE}.issubset(volumes) or len(volumes) > 128):
        raise ValueError('SOURCE_STATE_INCOMPLETE')
    infos = source['volumes']
    if len(infos) != len(volumes) or {v['name'] for v in infos} != volumes:
        raise ValueError('SOURCE_VOLUME_INVENTORY_REJECTED')
    for v in infos:
        if (v['driver'] != 'local' or v['options'] or v['project'] != project
                or v['name'] != project+'_'+name(v['logical'])):
            raise ValueError('SOURCE_VOLUME_DRIVER_REJECTED')
    required = {'postgres': ('postgres_data', '/var/lib/postgresql/data'),
                'redis': ('redis_data', '/data'), 'etcd': ('etcd_data', '/etcd'),
                'minio': ('minio_data', '/minio_data'),
                'milvus-standalone': ('milvus_data', '/var/lib/milvus'),
                'api': ('audit_state', '/data/observability'),
                'worker': ('audit_state', '/data/observability')}
    for c in containers:
        if c['service'] in required:
            logical, target = required[c['service']]
            if not any(m['type'] == 'volume' and m['name'] == project+'_'+logical
                       and m['target'] == target and m['writable'] for m in c['mounts']):
                raise ValueError('SOURCE_ROLE_MOUNT_REJECTED')
    return sorted(volumes)


def plan(source: dict[str, Any], helper_image: str, commit: str) -> dict[str, Any]:
    volumes = validate_source(source)
    if (not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/-]*@sha256:[0-9a-f]{64}', helper_image)
            or not re.fullmatch('[0-9a-f]{40}', commit)):
        raise ValueError('CANDIDATE_IDENTITY_REJECTED')
    return {'format': 1, 'run_id': uuid.uuid4().hex, 'source': source, 'volumes': volumes,
            'helper_image': helper_image, 'commit': commit,
            'schema_sha256': archive.file_hash(SCHEMA),
            'created_at': now(), 'runtime_acceptance': 'BLOCKED'}


def validate_plan(value: dict[str, Any], approval: str, isolated: str) -> None:
    if (identity(value) != approval or value['source']['project'] != isolated
            or value['format'] != 1 or value['schema_sha256'] != archive.file_hash(SCHEMA)
            or value['volumes'] != validate_source(value['source'])
            or not re.fullmatch('[0-9a-f]{32}', value['run_id'])):
        raise ValueError('RECOVERY_PLAN_REJECTED')
    # Reuse the structural identity constraints without changing the reviewed plan.
    plan(value['source'], value['helper_image'], value['commit'])


def states_match(expected: dict[str, Any], actual: dict[str, Any], *, cold: bool = False) -> bool:
    if cold:
        expected = json.loads(json.dumps(expected)); actual = json.loads(json.dumps(actual))
        for source in (expected, actual):
            for c in source['containers']:
                c.pop('running'); c.pop('exit_code')
        return expected == actual
    return expected == actual


def cold_check(docker: Docker, source: dict[str, Any]) -> None:
    current = docker.inventory(source['project'])
    validate_source(current)
    if (not states_match(source, current, cold=True)
            or any(c['running'] for c in current['containers'])):
        raise ValueError('SOURCE_NOT_QUIESCENT')
    if any(c['exit_code'] != 0 for c in current['containers']):
        raise ValueError('SOURCE_SHUTDOWN_NOT_CLEAN')


def resume(docker: Docker, value: dict[str, Any]) -> list[str]:
    failed = []
    original = [c for c in value['source']['containers'] if c['running']]
    for c in sorted(original, key=lambda row: (ORDER.get(row['service'], 3), row['id'])):
        try:
            docker.run('start', c['id'])
            state = json.loads(docker.run('inspect', '--format', '{{json .State}}', c['id']))
            if not state['Running'] or state.get('Paused') or state.get('Restarting'):
                failed.append(c['id'])
        except BaseException:
            failed.append(c['id'])
    return failed


def helper(docker: Docker, value: dict[str, Any], operation: str, volume: str,
           bundle: Path, *, target: str | None = None) -> None:
    if ',' in str(bundle):
        raise ValueError('BUNDLE_PATH_REJECTED')
    index = str(value['volumes'].index(volume))
    container = 'c22-' + value['run_id'] + '-' + operation + '-' + index
    mounts = ['--mount', 'type=bind,src='+str(bundle)+',dst=/bundle'
              + (',readonly' if target else '')]
    mounts += ['--mount', 'type=volume,src='+(target or volume)
               + ',dst='+('/target' if target else '/source')
               + ('' if target else ',readonly') + ',volume-nocopy']
    docker.run('create', '--name', container, '--label', 'businessagent.recovery.helper=c22',
               '--network', 'none', '--read-only', '--user', '0:0', '--pull=never',
               '--security-opt', 'no-new-privileges:true',
               '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--cap-add', 'FOWNER',
               '--cap-add', 'DAC_OVERRIDE', *mounts, '--entrypoint', 'python',
               value['helper_image'],
               '-B', '/app/deploy/recovery_archive.py', operation, '--name', volume,
               '--owner-uid', str(os.getuid()), '--owner-gid', str(os.getgid()),
               '--expected-schema', value['schema_sha256'])
    try:
        docker.run('start', '-a', container, timeout=3600)
    except BaseException:
        try:
            docker.run('stop', '--time', '30', container, timeout=45)
        except Exception:
            pass  # Outcome remains failed/uncertain; assets must be inspected, never reused.
        raise
    state = json.loads(docker.run('inspect', '--format', '{{json .State}}', container))
    if state['Running'] or state['ExitCode'] != 0:
        raise RuntimeError('ARCHIVE_HELPER_FAILED')


def backup(docker: Docker, value: dict[str, Any], bundle: Path) -> dict[str, Any]:
    archive.safe_path(bundle)
    if bundle.exists() or not bundle.parent.is_dir() or ',' in str(bundle):
        raise ValueError('BUNDLE_DESTINATION_REJECTED')
    if not states_match(value['source'], docker.inventory(value['source']['project'])):
        raise ValueError('SOURCE_DRIFT')
    helper_id = docker.run('image', 'inspect', '--format', '{{.Id}}', value['helper_image'])
    if any(c['image'] != helper_id for c in value['source']['containers']
           if c['service'] in {'api', 'api2', 'worker'}):
        raise ValueError('HELPER_IMAGE_MISMATCH')
    for volume in value['volumes']:
        docker.run('volume', 'inspect', volume, '--format', '{{.Name}}')
    bundle.mkdir(mode=0o700)
    archive.write_json(bundle / 'plan.json', value)
    started = now(); completed = False; failed = []; error = None
    try:
        # Highest-level writers stop first. All named state is copied only after all stop.
        for c in sorted(value['source']['containers'],
                        key=lambda row: ORDER.get(row['service'], 3), reverse=True):
            if c['running']:
                docker.run('stop', '--time', '60', c['id'], timeout=90)
        cold_check(docker, value['source'])
        for volume in value['volumes']:
            cold_check(docker, value['source'])
            helper(docker, value, 'pack', volume, bundle)
            cold_check(docker, value['source'])
            report = load(bundle / (volume + '.json'))
            if archive.file_hash(bundle / (volume + '.tar')) != report['sha256']:
                raise ValueError('BUNDLE_HASH_MISMATCH')
            archive.verify(bundle / (volume + '.tar'), report['members'])
        completed = True
    except BaseException as exc:
        error = exc
    finally:
        failed = resume(docker, value)
        result = {'format': 1, 'plan_sha256': identity(value), 'snapshot_started_at': started,
                  'snapshot_finished_at': now(), 'snapshot_complete': completed,
                  'source_resume_failed': failed, 'runtime_acceptance': 'BLOCKED'}
        if completed:
            result['files'] = {v+suffix: archive.file_hash(bundle/(v+suffix))
                               for v in value['volumes'] for suffix in ('.tar', '.json')}
        archive.write_json(bundle / 'result.json', result)
    if error is not None or failed:
        raise RuntimeError('BACKUP_OR_SOURCE_RESUME_FAILED') from None
    return result


def verify_bundle(bundle: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    archive.safe_path(bundle)
    value = load(bundle / 'plan.json', 2097152)
    validate_plan(value, identity(value), value['source']['project'])
    report = load(bundle / 'result.json', 2097152)
    expected = {v+s for v in value['volumes'] for s in ('.tar', '.json')}
    if (not report['snapshot_complete'] or report['plan_sha256'] != identity(value)
            or set(report.get('files', {})) != expected):
        raise ValueError('BUNDLE_INCOMPLETE')
    for filename, checksum in report['files'].items():
        if archive.file_hash(archive.safe_path(bundle / filename)) != checksum:
            raise ValueError('BUNDLE_HASH_MISMATCH')
    for volume in value['volumes']:
        entry = load(bundle / (volume+'.json'))
        if entry['sha256'] != report['files'][volume+'.tar']:
            raise ValueError('BUNDLE_HASH_MISMATCH')
        archive.verify(bundle / (volume+'.tar'), entry['members'])
    return value, report


def restore_plan(bundle: Path, target: str) -> dict[str, Any]:
    value, result = verify_bundle(bundle)
    name(target)
    if target == value['source']['project'] or not target.startswith('c22-restore-'):
        raise ValueError('RESTORE_PROJECT_REJECTED')
    return {'format': 1, 'source_plan': value, 'bundle_result_sha256': identity(result),
            'target_project': target, 'run_id': uuid.uuid4().hex,
            'volumes': {v: name(target+'_'+v[len(value['source']['project'])+1:])
                        for v in value['volumes']},
            'runtime_acceptance': 'BLOCKED'}


def restore_bundle(docker: Docker, proposal: dict[str, Any], bundle: Path, output: Path) -> None:
    value, result = verify_bundle(bundle)
    target = name(proposal['target_project'])
    checked = restore_plan(bundle, target)
    if (not re.fullmatch('[0-9a-f]{32}', proposal['run_id'])
            or proposal['source_plan'] != value or proposal['volumes'] != checked['volumes']
            or proposal['bundle_result_sha256'] != identity(result)):
        raise ValueError('RESTORE_PLAN_DRIFT')
    existing = set(docker.run('volume', 'ls', '--format', '{{.Name}}').splitlines())
    target_state = docker.inventory(target)
    if (existing.intersection(proposal['volumes'].values())
            or target_state['containers'] or target_state['volumes']):
        raise ValueError('RESTORE_TARGET_EXISTS')
    helper_id = docker.run('image', 'inspect', '--format', '{{.Id}}', value['helper_image'])
    if any(c['image'] != helper_id for c in value['source']['containers']
           if c['service'] in {'api', 'api2', 'worker'}):
        raise ValueError('HELPER_IMAGE_MISMATCH')
    archive.safe_path(output)
    output.mkdir(mode=0o700)  # Exclusive retained receipt directory; no overwrite.
    archive.write_json(output/'restore-plan.json', proposal)
    archive.write_json(output/'restored-volumes.compose.json', {'volumes': {
        info['logical']: {'external': True, 'name': proposal['volumes'][info['name']]}
        for info in value['source']['volumes']}})
    restored = []; failed = False
    helper_plan = {**value, 'run_id': proposal['run_id']}
    try:
        for volume, destination in proposal['volumes'].items():
            # Refuse concurrent precreation. Isolation must exclude all external operators.
            if destination in docker.run('volume', 'ls', '--format', '{{.Name}}').splitlines():
                raise ValueError('RESTORE_VOLUME_EXISTS')
            docker.run('volume', 'create', '--label', 'com.docker.compose.project='+target,
                       '--label', 'com.docker.compose.volume='+destination[len(target)+1:],
                       '--label', 'businessagent.recovery.run='+proposal['run_id'], destination)
            owner = docker.run('volume', 'inspect', '--format',
                               '{{index .Labels "businessagent.recovery.run"}}', destination)
            attached = docker.run('ps', '-aq', '--filter', 'volume='+destination)
            if owner != proposal['run_id'] or attached:
                raise ValueError('RESTORE_VOLUME_OWNERSHIP_REJECTED')
            helper(docker, helper_plan, 'restore', volume, bundle, target=destination)
            restored.append(destination)
    except BaseException:
        failed = True
        raise
    finally:
        archive.write_json(output/'restore-result.json', {'byte_restore_complete': not failed,
                           'restored_volumes': restored, 'finished_at': now(),
                           'application_started': False, 'runtime_acceptance': 'BLOCKED'})


def rollback_plan(candidate: dict[str, Any]) -> dict[str, Any]:
    image, commit = candidate['image'], candidate['commit']
    if (not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/-]*@sha256:[0-9a-f]{64}', image)
            or not re.fullmatch('[0-9a-f]{40}', commit)
            or candidate['schema_sha256'] != archive.file_hash(SCHEMA)):
        raise ValueError('ROLLBACK_SCHEMA_OR_IMAGE_REJECTED')
    return {'kind': 'image_only_candidate', 'image': image, 'commit': commit,
            'schema_sha256': candidate['schema_sha256'], 'schema_identity_equal': True,
            'semantic_compatibility_verified': False, 'execution_allowed': False,
            'runtime_acceptance': 'BLOCKED'}


def assess_window(observation: dict[str, str]) -> dict[str, Any]:
    times = {key: datetime.fromisoformat(observation[key]) for key in (
        'snapshot_started_at', 'snapshot_finished_at', 'incident_at', 'service_verified_at')}
    if any(value.tzinfo is None for value in times.values()):
        raise ValueError('RECOVERY_TIMEZONE_REQUIRED')
    start, finish, incident, ready = (times[k] for k in (
        'snapshot_started_at', 'snapshot_finished_at', 'incident_at', 'service_verified_at'))
    if not start <= finish <= incident <= ready:
        raise ValueError('RECOVERY_TIME_ORDER_REJECTED')
    rpo = (incident-start).total_seconds(); rto = (ready-incident).total_seconds()
    return {'rpo_upper_bound_seconds': rpo, 'rto_observed_seconds': rto,
            'rpo_within_24h': rpo <= 86400, 'rto_within_1h': rto <= 3600,
            'status': 'OBSERVED' if rpo <= 86400 and rto <= 3600 else 'FAIL',
            'runtime_acceptance': 'BLOCKED', 'independent_evidence_verified': False}


@contextmanager
def termination_guard() -> Iterator[None]:
    def interrupted(signum: int, frame: Any) -> None:
        raise InterruptedError('RECOVERY_INTERRUPTED')
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inventory', 'plan-backup', 'backup', 'resume',
                                         'plan-restore', 'restore', 'plan-rollback',
                                         'assess-window'])
    parser.add_argument('--project'); parser.add_argument('--inventory', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle', type=Path); parser.add_argument('--helper-image')
    parser.add_argument('--commit'); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approved-plan-sha256'); parser.add_argument('--isolated-project')
    args = parser.parse_args()
    try:
        if args.action == 'inventory':
            result = Docker().inventory(name(args.project))
        elif args.action == 'plan-backup':
            result = plan(load(args.inventory, 2097152), args.helper_image, args.commit)
        elif args.action == 'plan-rollback':
            result = rollback_plan(load(args.inventory, 2097152))
        elif args.action == 'assess-window':
            result = assess_window(load(args.inventory, 2097152))
        elif args.action == 'plan-restore':
            result = restore_plan(args.bundle, name(args.project))
        else:
            value = load(args.plan, 2097152)
            if not args.execute or identity(value) != args.approved_plan_sha256:
                raise ValueError('EXPLICIT_EXECUTION_REQUIRED')
            if args.action in {'backup', 'resume'}:
                validate_plan(value, args.approved_plan_sha256, args.isolated_project)
                if args.action == 'backup':
                    backup(Docker(), value, args.output)
                    print('BACKUP_CAPTURED_RUNTIME_BLOCKED'); return 0
                archive.safe_path(args.output)
                if args.output.exists():
                    raise ValueError('RESUME_RECEIPT_EXISTS')
                current = Docker().inventory(value['source']['project'])
                if not states_match(value['source'], current, cold=True):
                    raise ValueError('RESUME_SOURCE_DRIFT')
                failed = resume(Docker(), value)
                archive.write_json(args.output, {'resume_failed': failed,
                                                 'runtime_acceptance': 'BLOCKED'})
                print('SOURCE_RESUME_FAILED' if failed else 'SOURCE_RESUMED_READINESS_UNVERIFIED')
                return 1 if failed else 0
            if args.isolated_project != value['target_project']:
                raise ValueError('RESTORE_PROJECT_REJECTED')
            restore_bundle(Docker(), value, args.bundle, args.output)
            print('BYTES_RESTORED_APPLICATION_NOT_STARTED'); return 0
        archive.write_json(args.output, result)
        print(json.dumps({'status': result.get('status', 'PLAN_ONLY'), 'sha256': identity(result),
                          'runtime_acceptance': 'BLOCKED'}))
        return 1 if result.get('status') == 'FAIL' else 0
    except Exception:
        print('RECOVERY_OPERATION_FAILED_ASSETS_RETAINED')
        return 1


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    with termination_guard():
        raise SystemExit(main())
