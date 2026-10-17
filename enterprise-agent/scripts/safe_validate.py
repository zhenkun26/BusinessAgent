"""Run reviewed offline checks without cleanup, application startup or external calls.

This allowlisted entry point is not a sandbox for arbitrary Python code.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
REVIEWED = {
    "uat-plan": (
        "validate_uat_plan",
        "10aed812e152cc155439efc3b51203247e1a655c9a580d094ac457873546d267",
    ),
    "uat-readiness": (
        "validate_uat_execution_readiness",
        "8d567acad2a3568d1414fbe24359f9badc9ff2c488def3aa410407ceaa90e916",
    ),
    "grey-plan": (
        "validate_grey_release_plan",
        "356e40dc9818a7a5a5e2ffa97fa718e803e35c4b522b143dcc0629801cdf9e30",
    ),
    "release-gate": (
        "validate_release_gate",
        "55e779bd775adc1dcde8d977d4a2637e4c761dc9bbb8588dde20303aa566707e",
    ),
    "g0-replay": (
        "run_uat_replay",
        "64ed4eb0c9c7be314537b439306f6a6c7aa729a5636a122f93b4b6dd1afc6a76",
    ),
}
INPUTS = (
    "docs/30-guides/UAT验收计划.md",
    "docs/30-guides/发布灰度与上线门槛检查单.md",
    "enterprise-agent/eval/uat_simulation/fixture.json",
)
EXIT_CODES = {"PASS": 0, "FAIL": 1, "BLOCKED": 2}


class SafetyError(RuntimeError):
    """A fixed error code, with no source payload or credential attached."""


class QuietOutput:
    """Discard validator output rather than retaining potentially sensitive text."""

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        pass


class ReadOnlyGuard:
    """Audit-hook protection for reviewed stdlib-only functions, not hostile code."""

    def __init__(self) -> None:
        self.active = False
        self.denied = False

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if not self.active:
            return
        blocked = event.startswith(("socket.", "subprocess.", "ctypes.")) or event in {
            "os.remove", "os.rmdir", "os.rename", "os.mkdir", "os.chmod", "os.chown",
            "os.truncate", "os.utime", "os.link", "os.symlink", "os.system", "os.exec",
            "os.posix_spawn", "os.fork", "os.forkpty", "os.startfile", "os.chdir",
            "os.putenv", "os.unsetenv",
        }
        if event == "open":
            mode, flags = args[1:3]
            blocked = (
                isinstance(mode, str) and any(char in mode for char in "wax+")
            ) or (
                isinstance(flags, int)
                and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            )
        if blocked:
            self.denied = True
            raise SafetyError("SIDE_EFFECT_DENIED")

    def __enter__(self) -> ReadOnlyGuard:
        sys.addaudithook(self.audit)
        self.active = True
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.active = False


def require_regular_path(path: Path, root: Path) -> None:
    """Reject links on every component, including dangling output links."""
    if not path.is_relative_to(root):
        raise SafetyError("PATH_OUTSIDE_ROOT")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise SafetyError("SYMLINK_DENIED")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_metadata(root: Path) -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
        check=True, timeout=10,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise SafetyError("REVISION_UNAVAILABLE")
    dirty = subprocess.run(
        ["git", "-c", "core.fileMode=false", "diff", "--quiet", "HEAD", "--"],
        cwd=root, capture_output=True, timeout=10,
    ).returncode
    if dirty not in (0, 1):
        raise SafetyError("REVISION_UNAVAILABLE")
    return {"commit": revision, "tracked_content_dirty": bool(dirty)}


def load_reviewed(root: Path, check_id: str) -> types.ModuleType:
    name, expected = REVIEWED[check_id]
    path = root / "enterprise-agent/eval" / (name + ".py")
    require_regular_path(path, root)
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != expected:
        raise SafetyError("SOURCE_REVIEW_REQUIRED")
    module = types.ModuleType("_safe_validation_" + name)
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    # Compile the exact bytes reviewed above; never execute a stale .pyc or __main__.
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def summarize(check_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    status = {
        "passed": "PASS", "ready": "PASS", "blocked": "BLOCKED",
        "failed": "FAIL", "invalid": "FAIL", "needs_revision": "FAIL",
    }.get(raw.get("overall_status"))
    if status is None or not isinstance(raw.get("checks"), list) or not raw["checks"]:
        raise SafetyError("INVALID_CHECK_RESULT")
    checks = []
    for index, check in enumerate(raw["checks"], 1):
        passed = check.get("passed")
        if check_id == "g0-replay":
            if check.get("status") not in ("passed", "failed"):
                raise SafetyError("INVALID_CHECK_RESULT")
            passed = check["status"] == "passed"
        if not isinstance(passed, bool):
            raise SafetyError("INVALID_CHECK_RESULT")
        checks.append({"index": index, "passed": passed})
    if status == "PASS" and not all(check["passed"] for check in checks):
        status = "FAIL"
    return {
        "id": check_id,
        "evidence_level": "E1" if check_id == "g0-replay" else "E0",
        "execution_status": "PASS",
        "result_status": status,
        "checks": checks,
        # These checks never authorize production, even if future resource rows change.
        "formal_uat": False,
        "release_evidence": False,
        "release_allowed": False,
    }


def run_checks(root: Path, selected: list[str]) -> dict[str, Any]:
    if not selected or len(selected) != len(set(selected)) or any(
        name not in REVIEWED for name in selected
    ):
        raise SafetyError("CHECK_NOT_ALLOWED")
    root = root.absolute()
    metadata = git_metadata(root)
    paths = list(INPUTS) + [
        f"enterprise-agent/eval/{REVIEWED[name][0]}.py" for name in selected
    ] + ["enterprise-agent/scripts/safe_validate.py"]
    for name in paths:
        require_regular_path(root / name, root)
    hashes = {name: digest(root / name) for name in paths}
    results = []
    plan, gate, fixture = (root / name for name in INPUTS)
    for check_id in selected:
        try:
            with ReadOnlyGuard() as guard, contextlib.redirect_stdout(QuietOutput()), \
                    contextlib.redirect_stderr(QuietOutput()):
                module = load_reviewed(root, check_id)
                if check_id == "uat-plan":
                    raw = module.validate_uat_plan(plan, fixture)
                elif check_id == "uat-readiness":
                    raw = module.validate_uat_execution_readiness(plan)
                elif check_id == "grey-plan":
                    raw = module.validate_grey_release_plan(gate)
                elif check_id == "release-gate":
                    raw = module.validate_release_gate(gate, root)
                else:
                    raw = module.run_replay(json.loads(fixture.read_text(encoding="utf-8")))
                if guard.denied:
                    raise SafetyError("SIDE_EFFECT_DENIED")
                result = summarize(check_id, raw)
        except Exception as exc:
            # Never serialize exception messages or arbitrary module output.
            code = "SOURCE_REVIEW_REQUIRED" if (
                isinstance(exc, SafetyError) and exc.args == ("SOURCE_REVIEW_REQUIRED",)
            ) else "CHECK_EXECUTION_FAILED"
            result = {
                "id": check_id, "execution_status": "BLOCKED", "result_status": "BLOCKED",
                "error_code": code,
            }
        results.append(result)
    if any(digest(root / name) != value for name, value in hashes.items()):
        raise SafetyError("INPUT_CHANGED_DURING_RUN")
    statuses = {result["result_status"] for result in results}
    overall = "FAIL" if "FAIL" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS"
    return {
        "schema_version": 1, "scope": "C24-offline-preflight", "overall_status": overall,
        "execution_status": "PASS" if all(
            item["execution_status"] == "PASS" for item in results
        ) else "BLOCKED",
        "executed_at": datetime.now(UTC).isoformat(), "python_version": sys.version.split()[0],
        "source": metadata, "sha256": hashes, "results": results,
        "formal_uat": False, "release_evidence": False, "release_allowed": False,
    }


def record_report(root: Path, run_id: str, report: dict[str, Any]) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", run_id):
        raise SafetyError("INVALID_RUN_ID")
    directory = root / "enterprise-agent/eval/results/safe-validation"
    path = directory / (run_id + ".json")
    require_regular_path(path, root)
    directory.mkdir(parents=True, exist_ok=True)
    # x mode is exclusive, including when another process won the same run ID.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", nargs="+", choices=tuple(REVIEWED), default=list(REVIEWED))
    parser.add_argument("--list", action="store_true", help="List allowed checks without executing")
    parser.add_argument(
        "--record", metavar="RUN_ID", help="Create a new ignored JSON evidence file"
    )
    args = parser.parse_args()
    if args.list:
        print(json.dumps({"allowed_checks": list(REVIEWED)}))
        return 0
    try:
        report = run_checks(ROOT, args.check)
        if args.record:
            record_report(ROOT, args.record, report)
    except Exception:
        # No raw argparse values, exception messages, environment or absolute paths in evidence.
        print(json.dumps({"overall_status": "BLOCKED", "error_code": "PREFLIGHT_OR_RECORD_FAILED"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return EXIT_CODES[report["overall_status"]]


if __name__ == "__main__":
    raise SystemExit(main())
