"""Fail-closed, event-scoped Gitleaks history and exact tracked-tree checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

VERSION = "8.24.3"
ZERO = "0" * 40


def tool_environment() -> dict[str, str]:
    """Local inspection never needs caller Git redirection, credentials or filters."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0")
    return env


class ScanError(Exception):
    """An input, coverage or tool failure; never a clean scan."""


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo), *args],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        env=tool_environment(),
    )
    if result.returncode:
        raise ScanError(f"Git operation failed: {args[0]}")
    return result.stdout


def commit(repo: Path, value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ScanError("Event requires a complete hexadecimal SHA")
    if value == ZERO:
        raise ScanError("Zero SHA is not a candidate commit")
    # Annotated tag pushes can identify a tag object rather than its peeled commit.
    return git(repo, "rev-parse", "--verify", value + "^{commit}").decode().strip()


def select_range(repo: Path, name: str, event: dict[str, Any], sha: str) -> dict[str, Any]:
    head = commit(repo, sha)
    if git(repo, "rev-parse", "HEAD").decode().strip() != head:
        raise ScanError("Checkout does not match the event SHA")
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ScanError("Full history is required; shallow checkout rejected")
    if git(repo, "for-each-ref", "refs/replace").strip():
        raise ScanError("Replacement refs are not supported")
    grafts = Path(os.fsdecode(git(repo, "rev-parse", "--git-path", "info/grafts").strip()))
    if not grafts.is_absolute():
        grafts = repo / grafts
    if grafts.exists() and grafts.stat().st_size:
        raise ScanError("Grafted history is not supported")
    policy = head
    if name == "push":
        if event.get("deleted") is True:
            raise ScanError("Deleted refs have no candidate to scan")
        if commit(repo, event.get("after")) != head:
            raise ScanError("Push after SHA does not match checkout")
        before = event.get("before")
        if before == ZERO:
            revision = head
        else:
            base = commit(repo, before)
            if base == head:
                raise ScanError("No-op push has an empty range")
            revision = base + ".." + head
    elif name == "pull_request":
        pr = event["pull_request"]
        base = commit(repo, pr["base"]["sha"])
        source = commit(repo, pr["head"]["sha"])
        parents = git(repo, "show", "-s", "--format=%P", head).decode().split()
        if parents != [base, source]:
            raise ScanError("PR checkout must be the exact event base/head merge")
        if source == base:
            raise ScanError("PR source and base are identical")
        revision, policy = base + ".." + head, base
    elif name == "workflow_dispatch":
        revision = head
    else:
        raise ScanError("Unsupported event type")
    count = int(git(repo, "rev-list", "--count", revision))
    if count == 0:
        raise ScanError("Selected commit range is empty")
    # --diff-merges controls displayed merge diffs, not ancestry traversal.
    log_options = ("--full-history --diff-merges=first-parent --text --no-ext-diff "
                   "--no-textconv --no-show-signature " + revision)
    numstat = git(repo, "log", "--format=", "--numstat", "--full-history",
                  "--diff-merges=first-parent", "--text", "--no-ext-diff", "--no-textconv",
                  "--no-show-signature", revision)
    has_text = any(
        re.match(rb"[0-9]+\t[0-9]+\t", line)
        and sum(int(part) for part in line.split(b"\t", 2)[:2]) > 0
        for line in numstat.splitlines()
    )
    return {"head": head, "policy_commit": policy, "revision": revision,
            "selected_commits": count, "has_text_changes": has_text,
            "log_options": log_options}


def policy_files(repo: Path, sha: str, directory: Path) -> tuple[Path, Path]:
    config = directory / "policy.toml"
    config.write_bytes(git(repo, "show", sha + ":.gitleaks.toml"))
    ignore = directory / "policy.ignore"
    entry = git(repo, "ls-tree", sha, "--", ".gitleaksignore")
    ignore.write_bytes(git(repo, "show", sha + ":.gitleaksignore") if entry else b"")
    return config, ignore


def isolated_history(repo: Path, sha: str, destination: Path) -> tuple[Path, str, int]:
    """A bare scan source cannot auto-load candidate policy or execute file filters."""
    entries = [r for r in git(repo, "ls-tree", "-rz", "--full-tree", sha).split(b"\0") if r]
    for record in entries:
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, _ = metadata.split()
        if kind != b"blob" or mode not in (b"100644", b"100755", b"120000"):
            raise ScanError("Submodules or unsupported tree entries require explicit handling")
        path = os.fsdecode(raw_path)
        if path.startswith("/") or any(p in ("", ".", "..") or p.lower() == ".git"
                                       for p in path.split("/")):
            raise ScanError("Unsafe tree path")
    destination.mkdir()
    git(destination, "init", "--bare", "--quiet")
    objects = Path(os.fsdecode(git(repo, "rev-parse", "--git-path", "objects").strip()))
    if not objects.is_absolute():
        objects = repo / objects
    if "\n" in str(objects) or "\r" in str(objects):
        raise ScanError("Unsupported object directory path")
    (destination / "objects/info/alternates").write_text(str(objects.resolve()) + "\n")
    git(destination, "update-ref", "refs/heads/candidate", sha)
    git(destination, "symbolic-ref", "HEAD", "refs/heads/candidate")
    tree = git(repo, "rev-parse", sha + "^{tree}").decode().strip()
    # A local parentless commit makes every tracked blob part of one root diff.
    # It keeps original paths, cannot import source/.gitleaksignore as policy,
    # and never follows symlink targets or honors archive attributes.
    snapshot = git(destination, "-c", "user.name=Secret scan snapshot",
                   "-c", "user.email=secret-scan@example.invalid", "-c", "commit.gpgsign=false",
                   "commit-tree", tree, data=b"Local secret-scan tree snapshot\n").decode().strip()
    if (git(destination, "rev-parse", snapshot + "^{tree}").decode().strip() != tree
            or git(destination, "show", "-s", "--format=%P", snapshot).strip()):
        raise ScanError("Snapshot tree/parent identity mismatch")
    return destination, snapshot, len(entries)


def scan(binary: str, source: Path, config: Path, ignore: Path,
         output: Path, label: str, extra: list[str]) -> dict[str, Any]:
    report, log = output / (label + ".json"), output / (label + ".log")
    args = [binary, "detect", "--source", str(source), "--config", str(config),
            "--gitleaks-ignore-path", str(ignore), "--redact=100", "--exit-code=2",
            "--report-format=json", "--report-path", str(report), "--log-level=info",
            "--no-banner", "--no-color", *extra]
    result: dict[str, Any] = {"case": label, "status": "error"}
    try:
        process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 timeout=300, env=tool_environment())
        log.write_bytes(process.stdout)
        result["exit"] = process.returncode
        if process.returncode not in (0, 2):
            raise ScanError("Scanner execution failed")
        values = json.loads(report.read_text())
        if not isinstance(values, list) or any(not isinstance(v, dict) or not v.get("RuleID")
                                               for v in values):
            raise ScanError("Malformed scanner report")
        if (process.returncode == 0) != (len(values) == 0):
            raise ScanError("Scanner exit/report inconsistency")
        result.update(findings=len(values), status="findings" if values else "clean")
        match = re.search(rb"(\d+) commits scanned", process.stdout)
        result["scanned_commits"] = int(match[1]) if match else None
    except (ScanError, OSError, ValueError, subprocess.TimeoutExpired):
        result["status"] = "error"
        result["error"] = "Scanner failed or did not produce a valid consistent report"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--event-path", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--gitleaks", default="gitleaks")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summary: dict[str, Any] = {"event": args.event_name, "status": "error", "scans": []}
    code = 1
    try:
        args.output = args.output.resolve()
        args.output.mkdir(parents=True, exist_ok=False)  # Never reuse stale reports.
        repo = args.repo.resolve()
        event = json.loads(args.event_path.read_text())
        if not isinstance(event, dict):
            raise ScanError("Event payload must be an object")
        selected = select_range(repo, args.event_name, event, args.sha)
        summary.update(selected)
        version = subprocess.check_output([args.gitleaks, "version"], text=True, timeout=30,
                                          env=tool_environment()).strip()
        if version != VERSION:
            raise ScanError("Unexpected Gitleaks version")
        summary["scanner_version"] = version
        with tempfile.TemporaryDirectory(prefix="businessagent-secret-scan-") as temporary:
            root = Path(temporary)
            config, ignore = policy_files(repo, selected["policy_commit"], root)
            summary["policy_sha256"] = hashlib.sha256(config.read_bytes()).hexdigest()
            summary["ignore_sha256"] = hashlib.sha256(ignore.read_bytes()).hexdigest()
            source, snapshot, files = isolated_history(repo, selected["head"], root / "history.git")
            summary["tracked_files"] = files
            summary["snapshot_commit"] = snapshot
            summary["snapshot_tree"] = git(
                repo, "rev-parse", selected["head"] + "^{tree}").decode().strip()
            history = scan(args.gitleaks, source, config, ignore, args.output, "history",
                           ["--log-opts=" + selected["log_options"]])
            if selected["has_text_changes"] and not history.get("scanned_commits"):
                history.update(status="error",
                               error="Text history exists but scanner coverage is zero/unknown")
            summary["scans"].append(history)
            tree_options = ("--root --text --no-ext-diff --no-textconv --no-show-signature "
                            "-1 " + snapshot)
            tree_result = scan(args.gitleaks, source, config, ignore, args.output,
                               "tree", ["--log-opts=" + tree_options])
            if files and not tree_result.get("scanned_commits"):
                tree_result.update(status="error",
                                   error="Tracked tree has zero/unknown scan coverage")
            summary["scans"].append(tree_result)
        if any(s["status"] == "error" for s in summary["scans"]):
            raise ScanError("One or more required scans failed")
        code = 2 if any(s["status"] == "findings" for s in summary["scans"]) else 0
        summary["status"] = "findings" if code else "clean"
    except (ScanError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        # Never print tool stderr, event contents or suspected secret values.
        summary["error"] = str(exc) if isinstance(exc, ScanError) else type(exc).__name__
    summary["exit"] = code
    if args.output.is_dir() and not (args.output / "summary.json").exists():
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
