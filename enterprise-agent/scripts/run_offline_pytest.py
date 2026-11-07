"""Retained, no-network/no-deletion full pytest entry; no filter or cleanup switch."""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import sys
from uuid import uuid4
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]


def dependencies_match() -> bool:
    from packaging.requirements import Requirement
    for line in (ROOT / 'deploy/requirements-prod.txt').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        requirement = Requirement(line)
        if importlib.metadata.version(requirement.name) not in requirement.specifier:
            return False
    for name in ('pytest', 'pytest-asyncio', 'pytest-cov', 'fakeredis'):
        importlib.metadata.version(name)
    return True


def diagnostic_guard(root: Path, denials: Counter) -> Callable[[str, tuple], None]:
    def deny(code: str) -> None:
        denials[code] += 1
        raise RuntimeError(code)

    def guard(event: str, args: tuple) -> None:
        if event in {'os.remove', 'os.rmdir', 'os.rename', 'os.system'}:
            deny('OFFLINE_DELETE_OR_MUTATION')
        if event in {'os.symlink', 'os.link'}:
            if not all(Path(name).resolve().is_relative_to(root / 'eval/results') for name in args[:2]):
                deny('OFFLINE_LINK_ESCAPE')
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind', 'socket.sendto'}:
            deny('OFFLINE_NETWORK')
        if event == 'subprocess.Popen':
            command = args[1]
            allowed = [['rev-parse', 'HEAD'], ['-c', 'core.fileMode=false', 'diff', '--quiet', 'HEAD', '--']]
            if (not isinstance(command, (list, tuple)) or Path(command[0]).name != 'git'
                    or list(command[1:]) not in allowed):
                deny('OFFLINE_SUBPROCESS')
        if event in {'os.mkdir', 'os.chmod', 'os.chown'}:
            if not Path(args[0]).resolve().is_relative_to(root / 'eval/results'):
                deny('OFFLINE_PATH')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.name.startswith('.env') and path.name != '.env.example':
                deny('OFFLINE_PRIVATE_ENV')
            writing = args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            if writing and not path.is_relative_to(root / 'eval/results') and str(path) != '/dev/null':
                deny('OFFLINE_WRITE')

    return guard


def main() -> int:
    if len(sys.argv) != 1:
        print(json.dumps({'schema': 'offline-pytest-v1', 'status': 'FAIL',
                          'reason': 'FILTERS_NOT_ALLOWED'}))
        return 1
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    # Ignore credentials/configuration inherited by this synthetic diagnostic process.
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    for key in list(os.environ):
        if key in {'PYTEST_ADDOPTS', 'PYTEST_PLUGINS'} or key.startswith((
                'LANGCHAIN_', 'LANGSMITH_', 'OTEL_', 'TELEMETRY_')):
            os.environ.pop(key)
    try:
        if not dependencies_match():
            raise ImportError
        import coverage
        import pytest
        from app.config import Settings
        Settings.model_config['env_file'] = None
        for key in list(os.environ):
            if key.lower() in Settings.model_fields:
                os.environ.pop(key)
    except (ImportError, importlib.metadata.PackageNotFoundError):
        print(json.dumps({'schema': 'offline-pytest-v1', 'status': 'BLOCKED',
                          'reason': 'DEPENDENCIES_UNAVAILABLE'}))
        return 2
    # Import by reviewed local path, not a globally resolved scripts package.
    import runpy
    verifier = runpy.run_path(str(ROOT / 'scripts/offline_verify.py'))
    hashes = verifier['source_snapshot'](ROOT.parent)
    retained = ROOT / 'eval/results' / ('offline-pytest-' + uuid4().hex)
    retained.mkdir()
    os.chdir(retained)
    counts: Counter = Counter()
    nodeids: list[str] = []
    denials: Counter = Counter()

    class RetainedFixtures:
        def pytest_collection_finish(self, session: Any) -> None:
            nodeids.extend(item.nodeid for item in session.items)

        def pytest_deselected(self, items: list[Any]) -> None:
            counts['deselected'] += len(items)

        def pytest_runtest_logreport(self, report: Any) -> None:
            if report.when == 'call' or report.failed or report.skipped:
                counts[('subtest_' if hasattr(report, 'context') else '') + report.outcome] += 1
            if getattr(report, 'wasxfail', False):
                counts['xfail'] += 1

        def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
            if (not nodeids or counts['passed'] != len(nodeids)
                    or any(v for k, v in counts.items() if k not in {'passed', 'subtest_passed'})
                    or denials):
                session.exitstatus = 1

        @pytest.fixture
        def tmp_path(self) -> Path:
            path = retained / uuid4().hex
            path.mkdir()
            return path

    guard = diagnostic_guard(ROOT, denials)

    sys.addaudithook(guard)
    captured = io.StringIO()
    with redirect_stdout(captured), redirect_stderr(captured):
        # urllib3's import-time IPv6 bind is not part of synthetic tests.
        import socket
        ipv6 = socket.has_ipv6
        try:
            socket.has_ipv6 = False
            import urllib3  # noqa: F401
        finally:
            socket.has_ipv6 = ipv6
        measurement = coverage.Coverage(data_file=None, source=[str(ROOT / 'app')],
                                        config_file=str(ROOT / 'pyproject.toml'))
        measurement.start()
        code = pytest.main([str(ROOT / 'tests'), '-c', str(ROOT / 'pyproject.toml'),
                            '-p', 'pytest_asyncio.plugin', '-p', 'no:cacheprovider',
                            '-p', 'no:tmpdir', '--capture=sys', '--tb=short'],
                           plugins=[RetainedFixtures()])
        measurement.stop()
        percentage = measurement.xml_report(outfile=str(retained / 'coverage.xml'))
    stable = all(hashlib.sha256((ROOT.parent / n).read_bytes()).hexdigest() == h
                 for n, h in hashes.items())
    passed = int(code) == 0 and stable and not denials
    report = {'schema': 'offline-pytest-v1', 'status': 'PASS' if passed else 'FAIL',
              'python': platform.python_version(), 'collected': len(nodeids),
              'counts': dict(counts), 'guard_denials': sum(denials.values()),
              'production_requirements_match': True, 'source_stable': stable,
              'coverage_percent': percentage, 'evidence': str(retained.relative_to(ROOT.parent)),
              'runtime': 'BLOCKED', 'full_rag': 'BLOCKED', 'c10': 'OPEN'}
    (retained / 'receipt.json').write_text(json.dumps({**report, 'sources': hashes,
                                                    'nodeids': nodeids}, indent=2))
    # Synthetic diagnostics remain ignored/local; aggregator and CI consume only safe JSON.
    (retained / 'pytest.log').write_text(captured.getvalue())
    print(json.dumps(report, sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
