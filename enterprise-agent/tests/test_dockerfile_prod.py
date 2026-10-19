"""生产 Dockerfile 的关键构建顺序回归测试。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
DOCKERFILE_PATH = PROJECT_ROOT / "enterprise-agent/Dockerfile.prod"


def test_runner_copies_venv_before_removing_venv_pip():
    content = DOCKERFILE_PATH.read_text(encoding="utf-8")
    runner = content.split("FROM python:3.13-slim AS runner", maxsplit=1)[1]

    system_cleanup = runner.index(
        "RUN /usr/local/bin/python -m pip uninstall -y pip --break-system-packages"
    )
    venv_copy = runner.index("COPY --from=builder /opt/venv /opt/venv")
    venv_cleanup = runner.index("RUN /opt/venv/bin/python -m pip uninstall -y pip")

    assert system_cleanup < venv_copy < venv_cleanup
    assert "/opt/venv/bin/pip uninstall" not in runner


def test_runner_installs_libpq_without_ignoring_apt_failure() -> None:
    content = DOCKERFILE_PATH.read_text(encoding="utf-8")
    runner = content.split("FROM python:3.13-slim AS runner", maxsplit=1)[1]
    install = runner.split("RUN apt-get update", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert "apt-get install -y --no-install-recommends ca-certificates tzdata libpq5" in install
    assert "|| true" not in install


def test_checkpoint_import_probe_runs_in_final_non_root_runtime() -> None:
    content = DOCKERFILE_PATH.read_text(encoding="utf-8")
    runner = content.split("FROM python:3.13-slim AS runner", maxsplit=1)[1]
    probe = runner.index('RUN python -c "import psycopg;')
    assert runner.index("COPY --from=builder /opt/venv /opt/venv") < probe
    assert runner.index("USER 65534:65534") < probe
    assert "from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver" in runner


if __name__ == '__main__':
    # Direct read-only entry; no pytest/plugin/cache or image execution.
    import unittest
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn) for fn in (
        test_runner_copies_venv_before_removing_venv_pip,
        test_runner_installs_libpq_without_ignoring_apt_failure,
        test_checkpoint_import_probe_runs_in_final_non_root_runtime,
    ))
    raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
