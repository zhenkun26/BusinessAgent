"""Fail-closed, event-scoped Gitleaks history and exact tracked-tree checks."""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
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


MANIFEST_SCHEMAS = {
    "enterprise-agent/scripts/final_candidate_sources.json": "c24-reviewed-sources-v1",
    "enterprise-agent/scripts/offline_sources.json": "offline-sources-v1",
}


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def regular_blob(repo: Path, sha: str, path: str) -> bytes:
    if (not path or path.startswith("/") or "\\" in path
            or any(part in ("", ".", "..") or part.lower() == ".git"
                   for part in path.split("/"))):
        raise ScanError("Unsafe manifest source path")
    entry = git(repo, "ls-tree", "-z", sha, "--", path).split(b"\0")
    if len(entry) != 2 or entry[1]:
        raise ScanError("Manifest source is not a unique regular blob")
    metadata, actual = entry[0].split(b"\t", 1)
    mode, kind, oid = metadata.split()
    if actual != os.fsencode(path) or kind != b"blob" or mode not in (b"100644", b"100755"):
        raise ScanError("Manifest source is not a regular blob")
    return git(repo, "cat-file", "blob", oid.decode())


def manifest(repo: Path, sha: str, path: str) -> tuple[dict[str, Any], list[str]]:
    raw = regular_blob(repo, sha, path).decode("utf-8")
    value = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(value, dict) or value.get("schema") != MANIFEST_SCHEMAS[path]
            or not isinstance(value.get("sources"), dict)):
        raise ScanError("Unrecognized manifest structure")
    if raw.rstrip("\n") != json.dumps(value, indent=2):
        raise ScanError("Noncanonical manifest layout")
    return value, raw.splitlines()


FROZEN_MANIFEST_BLOB = "88e475ffd9598d3251c78b5f3f9a1ef596af4842"
PROVENANCE = ".github/secret-scan-provenance/"


def archived_preimage(repo: Path, head: str, revision: str, path: str,
                      source_path: str, digest: str) -> dict[str, Any] | None:
    """Only the byte-pinned frozen C24 manifest may use retained source preimages."""
    if (path != "enterprise-agent/scripts/final_candidate_sources.json"
            or git(repo, "rev-parse", revision + ":" + path).decode().strip()
            != FROZEN_MANIFEST_BLOB):
        return None
    try:
        receipt = json.loads(regular_blob(repo, head, PROVENANCE + "receipt.json"),
                             object_pairs_hook=unique_object)
        if (receipt.get("schema") != "frozen-source-preimages-v1"
                or receipt.get("manifest") != path
                or receipt.get("manifest_blob") != FROZEN_MANIFEST_BLOB
                or not isinstance(receipt.get("sources"), list)):
            return None
        entries = [entry for entry in receipt["sources"]
                   if isinstance(entry, dict) and entry.get("source_path") == source_path]
        if len(entries) != 1:
            return None
        entry = entries[0]
        target = entry.get("archive", "")
        if not isinstance(target, str) or not re.fullmatch(
                re.escape(PROVENANCE) + r"[1-7]-[a-z_]+\.(?:py|cjs)\.txt", target):
            return None
        raw = regular_blob(repo, head, target)
        blob = git(repo, "rev-parse", head + ":" + target).decode().strip()
        if (hashlib.sha256(raw).hexdigest() != digest or entry.get("sha256") != digest
                or entry.get("source_blob") != blob or entry.get("bytes") != len(raw)):
            return None
        return {"manifest": path, "manifest_blob": FROZEN_MANIFEST_BLOB,
                "source_path": source_path, "source_sha256": digest,
                "source_blob": blob, "archive": target, "provenance_commit": head}
    except (ScanError, ValueError, KeyError, TypeError, UnicodeError, AttributeError):
        return None


def verify_archived_synthetic(repo: Path, finding: dict[str, Any], head: str,
                              snapshot: str) -> dict[str, Any] | None:
    """One immutable historical redaction-test marker, never a general JWT exception."""
    path = PROVENANCE + "6-test_credential_safety.py.txt"
    if (finding.get("File") != path or finding.get("RuleID") != "jwt"
            or finding.get("SymlinkFile")):
        return None
    try:
        reported = finding["Commit"]
        revision = head if reported == snapshot else reported
        if revision not in git(repo, "rev-list", head).decode().splitlines():
            return None
        raw = regular_blob(repo, revision, path)
        if (hashlib.sha256(raw).hexdigest()
                != "dee01b2d20953da2058540a8da0264256fce8358b100d079ee57990b82e79436"
                or git(repo, "rev-parse", revision + ":" + path).decode().strip()
                != "b5b645b37e0dfcbf8ab0f6156aa01ae02c132fbc"):
            return None
        nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.Assign)
                 and node.lineno == 23]
        if (len(nodes) != 1 or len(nodes[0].targets) != 1
                or not isinstance(nodes[0].targets[0], ast.Name)
                or nodes[0].targets[0].id != "JWT_MARKER"
                or not isinstance(nodes[0].value, ast.Constant)
                or not isinstance(nodes[0].value.value, str)):
            return None
        token = nodes[0].value.value
        if hashlib.sha256(token.encode()).hexdigest() != (
                "d1e7b92f6536fcd4d1cec64d3fadb0d15217153f0113a3b835097f368d4c18f6"):
            return None
        pieces = token.split(".")
        decoded = [base64.b64decode(part + "=" * (-len(part) % 4),
                                   altchars=b"-_", validate=True) for part in pieces]
        if (len(decoded) != 3 or json.loads(decoded[0]) != {"alg": "HS256"}
                or json.loads(decoded[1]) != {"sub": "synthetic"} or len(decoded[2]) != 14):
            return None
        expected = {"StartLine": 23, "EndLine": 23, "StartColumn": 16, "EndColumn": 83}
        if any(type(finding.get(k)) is not int or finding[k] != v for k, v in expected.items()):
            return None
        if (finding.get("Secret") != "REDACTED" or finding.get("Match") != "REDACTED'"
                or finding.get("Fingerprint") != f"{reported}:{path}:jwt:23"):
            return None
        return {"fingerprint": finding["Fingerprint"], "archive": path,
                "source_blob": "b5b645b37e0dfcbf8ab0f6156aa01ae02c132fbc",
                "reason": "Pinned historical test marker has an impossible HS256 signature length"}
    except (ScanError, ValueError, KeyError, TypeError, UnicodeError, SyntaxError):
        return None


def verify_manifest_finding(repo: Path, finding: dict[str, Any], head: str,
                            snapshot: str) -> dict[str, Any] | None:
    """Exempt only an exact digest whose source bytes are independently proven.

    Redaction remains enabled. Reconstruct the exact matched text from Git and
    compare its redacted form, coordinates and fingerprint to the scanner report.
    Historical provenance must be reachable and carry the identical source entry.
    Any ambiguity leaves the original finding active.
    """
    path = finding.get("File")
    if finding.get("RuleID") != "generic-api-key" or path not in MANIFEST_SCHEMAS:
        return None
    try:
        reported = finding["Commit"]
        if not isinstance(reported, str) or not re.fullmatch(r"[0-9a-f]{40}", reported):
            return None
        revision = head if reported == snapshot else reported
        reachable = git(repo, "rev-list", head).decode().splitlines()
        if revision not in reachable or finding.get("SymlinkFile"):
            return None
        value, lines = manifest(repo, revision, path)
        line, end, start_col, end_col = (finding[k] for k in
                                        ("StartLine", "EndLine", "StartColumn", "EndColumn"))
        if (any(type(n) is not int for n in (line, end, start_col, end_col))
                or line != end or not 1 <= line <= len(lines)):
            return None
        sources = value["sources"]
        if any(not isinstance(v, str) for v in sources.values()):
            return None
        sources_start = lines.index('  "sources": {')
        if not sources_start + 1 < line <= sources_start + 1 + len(sources):
            return None
        text = lines[line - 1]
        # Canonical one-entry-per-line JSON only; no extra fields or inline secrets.
        match = re.fullmatch(r'    ("[^"\\]+"):\s*("[0-9a-f]{64}")(,?)', text)
        if not match:
            return None
        source_path, digest = json.loads(match[1]), json.loads(match[2])
        if value["sources"].get(source_path) != digest:
            return None
        digest_start, digest_end = match.start(2) + 1, match.end(2) - 1
        # Pinned Gitleaks 8.24.3 reports a first added hunk line with
        # one-based source columns, but subsequent/root lines include the patch
        # prefix offset. Check two complete coordinate transforms, never mix
        # their endpoints or widen the accepted match/digest boundaries.
        matching_offsets = [
            offset for offset in (1, 2)
            if 0 <= start_col - offset < digest_start
            and end_col == digest_end + offset
            and finding.get("Match") == text[
                start_col - offset:end_col - offset + 1].replace(digest, "REDACTED")
        ]
        if (len(matching_offsets) != 1 or finding.get("Secret") != "REDACTED"
                or finding.get("Fingerprint") != f"{reported}:{path}:generic-api-key:{line}"):
            return None
        candidates = [revision, *git(repo, "log", "--full-history", "--format=%H",
                                      revision, "--", path).decode().splitlines()]
        for candidate in dict.fromkeys(candidates):
            try:
                historical, _ = manifest(repo, candidate, path)
                if historical["sources"].get(source_path) != digest:
                    continue
                source = regular_blob(repo, candidate, source_path)
                if hashlib.sha256(source).hexdigest() == digest:
                    return {"fingerprint": finding["Fingerprint"], "manifest": path,
                            "source_path": source_path, "source_sha256": digest,
                            "provenance_commit": candidate,
                            "source_blob": git(repo, "rev-parse",
                                               candidate + ":" + source_path).decode().strip()}
            except (ScanError, ValueError, KeyError, TypeError, UnicodeError):
                continue
        evidence = archived_preimage(repo, head, revision, path, source_path, digest)
        if evidence is not None:
            return {"fingerprint": finding["Fingerprint"], **evidence}
    except (ScanError, ValueError, KeyError, TypeError, UnicodeError):
        return None
    return None


def classify_manifest_findings(repo: Path, output: Path, result: dict[str, Any],
                               head: str, snapshot: str) -> None:
    if result["status"] == "error":
        return
    findings = json.loads((output / (result["case"] + ".json")).read_text())
    verified, synthetic, remaining = [], [], []
    for finding in findings:
        evidence = verify_manifest_finding(repo, finding, head, snapshot)
        if evidence is not None:
            verified.append(evidence)
        else:
            marker = verify_archived_synthetic(repo, finding, head, snapshot)
            if marker is not None:
                synthetic.append(marker)
            else:
                remaining.append(finding)
    # Never overwrite the raw redacted scanner report or conceal raw findings.
    (output / (result["case"] + "-verified-digests.json")).write_text(
        json.dumps(verified, indent=2) + "\n")
    (output / (result["case"] + "-remaining.json")).write_text(
        json.dumps(remaining, indent=2) + "\n")
    (output / (result["case"] + "-verified-synthetic.json")).write_text(
        json.dumps(synthetic, indent=2) + "\n")
    result.update(raw_findings=len(findings), verified_source_digests=len(verified),
                  verified_synthetic_markers=len(synthetic),
                  findings=len(remaining), status="findings" if remaining else "clean")


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
        # Retain isolated policy and object metadata for audit; never delete fixtures.
        root = args.output / "workspace"
        root.mkdir()
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
        classify_manifest_findings(repo, args.output, history, selected["head"], snapshot)
        summary["scans"].append(history)
        tree_options = ("--root --text --no-ext-diff --no-textconv --no-show-signature "
                        "-1 " + snapshot)
        tree_result = scan(args.gitleaks, source, config, ignore, args.output,
                           "tree", ["--log-opts=" + tree_options])
        if files and not tree_result.get("scanned_commits"):
            tree_result.update(status="error",
                               error="Tracked tree has zero/unknown scan coverage")
        classify_manifest_findings(repo, args.output, tree_result, selected["head"], snapshot)
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
