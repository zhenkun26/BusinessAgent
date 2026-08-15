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
