"""Offline regression tests for the event-scoped secret-scan runner.

Every positive uses a real pinned Gitleaks binary and retained Git history.
Generated strings are synthetic, unassociated with any service, and never printed.
Run: GITLEAKS_TEST_BINARY=/verified/gitleaks python -I -B this_file.py -v
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import string
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / ".github/scripts/scan_secrets.py"
ZERO = "0" * 40


class SecretScanTests(unittest.TestCase):
    """Exercise the public CLI, not private implementation helpers."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.binary = os.environ.get("GITLEAKS_TEST_BINARY") or shutil.which("gitleaks")
        if not cls.binary or not os.path.isfile(cls.binary) or not os.access(cls.binary, os.X_OK):
            raise AssertionError(
                "Real Gitleaks is required: set GITLEAKS_TEST_BINARY; no skip allowed")
        if not RUNNER.is_file():
            raise AssertionError("Secret-scan runner is missing")
        result = subprocess.run([cls.binary, "version"], capture_output=True, text=True, timeout=15)
        if result.returncode or result.stdout.strip() != "8.24.3":
            raise AssertionError("Tests require the verified Gitleaks 8.24.3 binary")

    def setUp(self) -> None:
        self.directory = Path(os.environ.get("TMPDIR", "/tmp")) / (
            "ba-secret-scan-test-" + secrets.token_hex(12))
        self.directory.mkdir()
        self.repo = self.directory / "repo"
        self.repo.mkdir()
        self.branches = {"main": self.repo}
        self.values: list[str] = []
        self.sequence = 0
        self.env = {
            key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TMPDIR")
            if key in os.environ
        }
        self.env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                         "GIT_TERMINAL_PROMPT": "0", "PYTHONNOUSERSITE": "1",
                         "PYTHONDONTWRITEBYTECODE": "1"})
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Synthetic Scan Test")
        self.git("config", "user.email", "scan-fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", os.devnull)
        self.git("config", "core.autocrlf", "false")
        shutil.copyfile(ROOT / ".gitleaks.toml", self.repo / ".gitleaks.toml")
        self.write("README.md", "Synthetic offline repository.\n")
        self.base = self.commit("initial clean fixture")

    def git(self, *arguments: str) -> str:
        # Keep a separate checkout per branch: switching branches must not delete
        # another branch's fixture paths. No cleanup is registered.
        if arguments[0] == "checkout":
            options = [arg for arg in arguments[1:] if arg != "-q"]
            if options[0] == "-b":
                name = options[1]
                destination = self.directory / ("branch-" + name)
                self.git("worktree", "add", "--quiet", "-b", name, str(destination),
                         *(options[2:] or ["HEAD"]))
                self.branches[name] = destination
            else:
                name = options[0]
            self.repo = self.branches[name]
            return ""
        result = subprocess.run(["git", "-C", str(self.repo), *arguments], env=self.env,
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            self.fail("Fixture Git operation failed: " + arguments[0])
        return result.stdout.strip()

    def write(self, path: str, text: str | bytes) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            target.write_bytes(text)
        else:
            target.write_text(text, encoding="utf-8")

    def exclude_retained(self, path: str) -> None:
        target = Path(self.git("rev-parse", "--git-path", "info/exclude"))
        if not target.is_absolute():
            target = self.repo / target
        with target.open("a") as stream:
            stream.write(path + "\n")

    def commit(self, message: str, *, empty: bool = False) -> str:
        self.git("add", "-A")
        options = ["commit", "-q", "-m", message]
        if empty:
            options.append("--allow-empty")
        self.git(*options)
        return self.git("rev-parse", "HEAD")

    @staticmethod
    def synthetic_key() -> str:
        # Random words can hit the generic rule's built-in stopwords. Alternating
        # letters/digits avoids that domain; balanced counts ensure high entropy.
        # No scanner retry or filtering is used to select a passing value.
        random_source = secrets.SystemRandom()
        letters = random_source.sample(string.ascii_letters, 32)
        digits = list(string.digits * 3 + "01")
        random_source.shuffle(digits)
        return "".join(letter + digit for letter, digit in zip(letters, digits))

    def leak(self, path: str = "application/settings.py") -> None:
        value = self.synthetic_key()
        self.values.append(value)
        self.write(path, 'api_key = "' + value + '"\n')

    def push(self, before: str, after: str, **extra: object) -> dict[str, object]:
        return {"before": before, "after": after, "ref": "refs/heads/main",
                "deleted": False, **extra}

    def pull_request(self, base: str, head: str) -> dict[str, object]:
        return {"action": "synchronize", "pull_request": {
            "base": {"sha": base, "ref": "main"},
            "head": {"sha": head, "ref": "feature"}}}

    def merge_feature(self) -> tuple[str, str, str]:
        head = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        base = self.git("rev-parse", "HEAD")
        self.git("merge", "-q", "--no-ff", "feature", "-m", "synthetic merge")
        return base, head, self.git("rev-parse", "HEAD")

    def run_scan(self, event: object, *, name: str = "push", sha: str | None = None,
                 binary: str | None = None, raw_event: str | None = None,
                 missing_event: bool = False, output: Path | None = None,
                 extra_env: dict[str, str] | None = None
                 ) -> tuple[int, dict[str, object], Path]:
        self.sequence += 1
        event_path = self.directory / (f"event-{self.sequence}.json")
        if not missing_event:
            event_path.write_text(raw_event if raw_event is not None else json.dumps(event))
        destination = output or self.directory / (f"output-{self.sequence}")
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(RUNNER), "--repo", str(self.repo),
             "--event-path", str(event_path), "--event-name", name,
             "--sha", sha if sha is not None else self.git("rev-parse", "HEAD"),
             "--gitleaks", binary or self.binary, "--output", str(destination)],
            env={**self.env, **(extra_env or {})}, capture_output=True, text=True, timeout=60)
        for value in self.values:
            if value in result.stdout or value in result.stderr:
                self.fail("Runner exposed a generated synthetic value")
        summary_path = destination / "summary.json"
        if not summary_path.is_file():
            self.fail("Runner failed to write summary.json")
        try:
            summary = json.loads(summary_path.read_text())
        except (ValueError, OSError):
            self.fail("Runner summary is not valid JSON")
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary.get("exit"), result.returncode)
        for artifact in destination.iterdir():
            if artifact.is_file():
                data = artifact.read_bytes()
                if any(value.encode() in data for value in self.values):
                    self.fail("Runner artifact exposed a generated synthetic value")
        return result.returncode, summary, destination

    def assert_scan(self, expected: int, event: object, *, history: bool | None = None,
                    tree: bool | None = None, **options: object) -> dict[str, object]:
        code, summary, output = self.run_scan(event, **options)
        self.assertEqual(code, expected, "Unexpected runner exit (details deliberately redacted)")
        self.assertEqual(summary.get("status"), {0: "clean", 1: "error", 2: "findings"}[expected])
        if expected in (0, 2):
            self.assertEqual([scan["case"] for scan in summary["scans"]], ["history", "tree"])
            for label, has_findings in (("history", history), ("tree", tree)):
                report = json.loads((output / (label + ".json")).read_text())
                self.assertIsInstance(report, list)
                if has_findings is not None:
                    self.assertEqual(bool(report), has_findings,
                                     label + " findings count differs from expectation")
        return summary

    def legacy_scan(self, base: str, head: str) -> int:
        """Actual former flag combination must miss the regression fixture."""
        report = self.directory / ("legacy-" + secrets.token_hex(4) + ".json")
        result = subprocess.run(
            [self.binary, "detect", "--source", str(self.repo), "--config",
             str(self.repo / ".gitleaks.toml"), "--redact=100", "--no-banner", "--no-color",
             "--report-format=json", "--report-path", str(report), "--exit-code=2",
             "--log-opts=--full-history --first-parent --no-merges " + base + ".." + head],
            env=self.env, capture_output=True, timeout=30)
        if any(value.encode() in result.stdout + result.stderr for value in self.values):
            self.fail("Legacy negative control exposed a generated synthetic value")
        self.assertEqual(result.returncode, 0,
                         "Old-flag negative control unexpectedly detected fixture")
        self.assertEqual(json.loads(report.read_text()), [])
        return result.returncode

    def test_generated_positive_controls_are_all_detected(self) -> None:
        # One predetermined batch, not repeated attempts until a scanner passes.
        expected_paths = {f"application/control_{number}.py" for number in range(32)}
        for path in sorted(expected_paths):
            self.leak(path)
            self.assertRegex(self.values[-1], r"(?:[a-zA-Z][0-9]){32}\Z")
        head = self.commit("fixed-size synthetic positive-control batch")
        code, summary, output = self.run_scan(self.push(self.base, head))
        self.assertEqual(code, 2)
        self.assertEqual(summary["status"], "findings")
        for phase in ("history", "tree"):
            findings = json.loads((output / (phase + ".json")).read_text())
            self.assertEqual(len(findings), 32)
            self.assertEqual({f["File"] for f in findings}, expected_paths)
            self.assertEqual({f["StartLine"] for f in findings}, {1})
            self.assertEqual({f["RuleID"] for f in findings}, {"generic-api-key"})

    def source_manifest(self, *, wrong_digest: bool = False) -> str:
        path = "enterprise-agent/scripts/offline_sources.json"
        source = "enterprise-agent/app/api_key.py"
        content = b"answer = 42\n"
        self.write(source, content)
        digest = hashlib.sha256(content).hexdigest()
        if wrong_digest:
            digest = hashlib.sha256(b"unrelated bytes").hexdigest()
        self.write(path, json.dumps({"schema": "offline-sources-v1",
                                   "sources": {source: digest}}, indent=2) + "\n")
        return path

    def test_verified_source_digest_preserves_raw_reports(self) -> None:
        self.source_manifest()
        head = self.commit("verified source digest")
        code, summary, output = self.run_scan(self.push(self.base, head))
        self.assertEqual(code, 0)
        for scan in summary["scans"]:
            self.assertEqual(scan["raw_findings"], 1)
            self.assertEqual(scan["verified_source_digests"], 1)
            self.assertEqual(scan["findings"], 0)
            self.assertEqual(len(json.loads((output / (scan["case"] + ".json")).read_text())), 1)

    def test_modified_manifest_entry_binds_both_real_column_modes(self) -> None:
        path = self.source_manifest()
        before = self.commit("initial source manifest")
        source = "enterprise-agent/app/api_key.py"
        content = b"answer = 43\n"
        self.write(source, content)
        value = json.loads((self.repo / path).read_text())
        value["sources"][source] = hashlib.sha256(content).hexdigest()
        self.write(path, json.dumps(value, indent=2) + "\n")
        head = self.commit("change existing manifest entry in first added hunk line")
        code, summary, output = self.run_scan(self.push(before, head))
        spec = importlib.util.spec_from_file_location("secret_scan_columns", RUNNER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for label, offset in (("history", 1), ("tree", 2)):
            findings = json.loads((output / (label + ".json")).read_text())
            self.assertEqual(len(findings), 1)
            finding = findings[0]
            line = (self.repo / path).read_text().splitlines()[finding["StartLine"] - 1]
            prefix = finding["Match"].split("REDACTED")[0]
            self.assertEqual(finding["StartColumn"], line.index(prefix) + offset)
            self.assertEqual(finding["EndColumn"], line.rindex('"') + offset)
            for column in ("StartColumn", "EndColumn"):
                for shift in (-1, 1):
                    with self.subTest(phase=label, column=column, shift=shift):
                        changed = {**finding, column: finding[column] + shift}
                        self.assertIsNone(module.verify_manifest_finding(
                            self.repo, changed, head, summary["snapshot_commit"]))
        self.assertEqual(code, 0)
        self.assertEqual([scan["verified_source_digests"] for scan in summary["scans"]], [1, 1])

    def test_unverified_source_digest_stays_finding(self) -> None:
        self.source_manifest(wrong_digest=True)
        head = self.commit("mismatched source digest")
        self.assert_scan(2, self.push(self.base, head), history=True, tree=True)

    def test_source_secret_is_not_exempted_by_its_valid_digest(self) -> None:
        path = self.source_manifest()
        self.leak("enterprise-agent/app/api_key.py")
        source = "enterprise-agent/app/api_key.py"
        self.write(path, json.dumps({"schema": "offline-sources-v1", "sources": {
            source: hashlib.sha256((self.repo / source).read_bytes()).hexdigest()}}, indent=2))
        head = self.commit("valid digest does not exempt source secret")
        self.assert_scan(2, self.push(self.base, head), history=True, tree=True)

    def test_secret_inside_manifest_is_not_exempted(self) -> None:
        path = self.source_manifest()
        value = json.loads((self.repo / path).read_text())
        secret = self.synthetic_key()
        self.values.append(secret)
        value["api_key"] = secret
        self.write(path, json.dumps(value, indent=2))
        head = self.commit("manifest contains a synthetic credential")
        self.assert_scan(2, self.push(self.base, head), history=True, tree=True)

    def test_verified_frozen_digest_uses_reachable_manifest_provenance(self) -> None:
        self.source_manifest()
        self.commit("historically verified manifest")
        self.write("enterprise-agent/app/api_key.py", "answer = 43\n")
        head = self.commit("source changed while historical manifest remains frozen")
        code, summary, _ = self.run_scan(self.push(self.base, head))
        self.assertEqual(code, 0)
        self.assertEqual([s["verified_source_digests"] for s in summary["scans"]], [1, 1])

    def test_manifest_verification_rejects_ambiguous_coordinates_and_json(self) -> None:
        path = self.source_manifest()
        head = self.commit("verified manifest for adversarial report checks")
        _, summary, output = self.run_scan(self.push(self.base, head))
        spec = importlib.util.spec_from_file_location("secret_scan", RUNNER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        finding = json.loads((output / "history.json").read_text())[0]
        for key, value in (("StartColumn", 0), ("EndColumn", 10000),
                           ("StartLine", True), ("EndLine", finding["EndLine"] + 1),
                           ("Match", "REDACTED"), ("Secret", "different"),
                           ("RuleID", "jwt"),
                           ("Fingerprint", "unbound"), ("Commit", self.base),
                           ("SymlinkFile", "external")):
            with self.subTest(field=key):
                changed = {**finding, key: value}
                self.assertIsNone(module.verify_manifest_finding(
                    self.repo, changed, head, summary["snapshot_commit"]))
        with self.assertRaises(ValueError):
            json.loads('{"sources": {}, "sources": {}}', object_pairs_hook=module.unique_object)

    def test_matching_digest_outside_sources_is_not_exempted(self) -> None:
        path = self.source_manifest()
        value = json.loads((self.repo / path).read_text())
        value["metadata"] = dict(value["sources"])
        self.write(path, json.dumps(value, indent=2))
        head = self.commit("same source entry appears outside sources map")
        code, summary, _ = self.run_scan(self.push(self.base, head))
        self.assertEqual(code, 2)
        self.assertEqual([s["findings"] for s in summary["scans"]], [1, 1])

    def test_duplicate_manifest_keys_and_symlink_sources_are_not_exempted(self) -> None:
        path = self.source_manifest()
        raw = (self.repo / path).read_text()
        self.write(path, raw.replace('"schema": "offline-sources-v1",',
                                    '"schema": "offline-sources-v1",\n  "schema": "offline-sources-v1",'))
        head = self.commit("duplicate JSON schema key")
        self.assert_scan(2, self.push(self.base, head), history=True, tree=True)
        target = self.directory / "outside-source.py"
        target.write_text("answer = 42\n")
        # Create the link at a fresh path; never delete any fixture file.
        link = "enterprise-agent/linked_api_key.py"
        (self.repo / link).symlink_to(target)
        self.write(path, json.dumps({"schema": "offline-sources-v1", "sources": {
            link: hashlib.sha256(target.read_bytes()).hexdigest()}}, indent=2))
        before = head
        head = self.commit("source is a symlink not a regular blob")
        self.assert_scan(2, self.push(before, head), history=True, tree=True)

    def archived_marker_fixture(self) -> tuple[str, str]:
        directory = ".github/secret-scan-provenance/"
        path = directory + "6-test_credential_safety.py.txt"
        self.write(path, (ROOT / path).read_bytes())
        return path, self.commit("exact historical synthetic marker bytes")

    def test_exact_archived_synthetic_marker_is_separately_counted(self) -> None:
        _, head = self.archived_marker_fixture()
        code, summary, _ = self.run_scan(self.push(self.base, head))
        self.assertEqual(code, 0)
        self.assertEqual([s["verified_synthetic_markers"] for s in summary["scans"]], [1, 1])
        self.assertEqual([s["verified_source_digests"] for s in summary["scans"]], [0, 0])

    def test_changed_archive_bytes_and_neighbor_secret_still_fail(self) -> None:
        path, before = self.archived_marker_fixture()
        self.write(path, (self.repo / path).read_text() + "\n# changed byte identity\n")
        head = self.commit("changed archive cannot inherit marker exemption")
        code, summary, _ = self.run_scan(self.push(before, head))
        self.assertEqual(code, 2)
        self.assertEqual(summary["scans"][1]["verified_synthetic_markers"], 0)
        self.leak(".github/secret-scan-provenance/neighbor.py.txt")
        head = self.commit("neighboring real-shaped credential stays detectable")
        self.assert_scan(2, self.push(before, head), history=True, tree=True)

    def test_real_length_signed_jwt_is_not_exempted(self) -> None:
        import base64
        import hmac
        path, before = self.archived_marker_fixture()
        raw = (self.repo / path).read_text()
        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=")
        payload = base64.urlsafe_b64encode(b'{"sub":"synthetic"}').rstrip(b"=")
        message = header + b"." + payload
        signature = base64.urlsafe_b64encode(hmac.new(secrets.token_bytes(32), message,
                                                     hashlib.sha256).digest()).rstrip(b"=")
        token = (message + b"." + signature).decode()
        self.values.append(token)
        lines = raw.splitlines(keepends=True)
        lines[22] = "JWT_MARKER = " + repr(token) + "\n"
        self.write(path, "".join(lines))
        head = self.commit("valid-length signed synthetic JWT is not the pinned marker")
        self.assert_scan(2, self.push(before, head), history=True, tree=True)

    def test_frozen_archive_receipt_is_exact_and_tamper_fails_closed(self) -> None:
        manifest_path = "enterprise-agent/scripts/final_candidate_sources.json"
        directory = ".github/secret-scan-provenance"
        self.write(manifest_path, (ROOT / manifest_path).read_bytes())
        for path in sorted((ROOT / directory).iterdir()):
            self.write(directory + "/" + path.name, path.read_bytes())
        before = self.base
        head = self.commit("frozen manifest with seven retained preimages")
        code, summary, _ = self.run_scan(self.push(before, head))
        self.assertEqual(code, 2)  # Nine other source blobs deliberately absent.
        for scan in summary["scans"]:
            self.assertEqual(scan["verified_source_digests"], 7)
            self.assertEqual(scan["verified_synthetic_markers"], 1)
            self.assertEqual(scan["findings"], 9)
        receipt_path = directory + "/receipt.json"
        original_receipt = (self.repo / receipt_path).read_text()
        self.write(receipt_path, original_receipt.replace(
            '"schema": "frozen-source-preimages-v1",',
            '"schema": "frozen-source-preimages-v1",\n  "schema": "duplicate",'))
        head = self.commit("duplicate receipt keys fail closed")
        _, summary, _ = self.run_scan(self.push(before, head))
        self.assertEqual(summary["scans"][1]["verified_source_digests"], 0)
        for field, value in (("archive", "../outside.txt"), ("source_blob", "0" * 40),
                             ("sha256", "0" * 64)):
            with self.subTest(receipt_field=field):
                receipt = json.loads(original_receipt)
                receipt["sources"][0][field] = value
                self.write(receipt_path, json.dumps(receipt, indent=2))
                head = self.commit("incorrect receipt binding")
                _, summary, _ = self.run_scan(self.push(before, head))
                self.assertEqual(summary["scans"][1]["verified_source_digests"], 6)
        self.write(receipt_path, original_receipt)
        path = directory + "/1-auth.py.txt"
        self.write(path, (self.repo / path).read_bytes() + b"\n# changed preimage\n")
        head = self.commit("archive identity mismatch")
        _, summary, _ = self.run_scan(self.push(before, head))
        self.assertEqual(summary["scans"][1]["verified_source_digests"], 6)
        self.assertEqual(summary["scans"][1]["findings"], 10)
        self.write(manifest_path, (self.repo / manifest_path).read_bytes() + b"\n")
        head = self.commit("frozen manifest blob identity changed")
        _, summary, _ = self.run_scan(self.push(before, head))
        self.assertEqual(summary["scans"][1]["verified_source_digests"], 0)
        self.assertEqual(summary["scans"][1]["findings"], 16)

    def test_clean_push(self) -> None:
        self.write("application/clean.py", "answer = 42\n")
        head = self.commit("clean update")
        self.assert_scan(0, self.push(self.base, head), history=False, tree=False)

    def test_push_detects_real_secret(self) -> None:
        self.leak()
        head = self.commit("synthetic finding")
        self.assert_scan(2, self.push(self.base, head), history=True, tree=True)

    def test_new_ref_checks_removed_history(self) -> None:
        self.leak()
        self.commit("transient synthetic finding")
        self.git("rm", "--cached", "--", "application/settings.py")
        self.exclude_retained("application/settings.py")
        head = self.commit("remove synthetic finding")
        self.assert_scan(2, self.push(ZERO, head, created=True), history=True, tree=False)

    def test_old_flags_miss_side_branch_removed_secret(self) -> None:
        self.git("checkout", "-q", "-b", "feature")
        self.leak()
        self.commit("branch synthetic finding")
        self.git("rm", "--cached", "--", "application/settings.py")
        self.exclude_retained("application/settings.py")
        self.commit("remove branch finding")
        base, _, merge = self.merge_feature()
        self.legacy_scan(base, merge)
        self.assert_scan(2, self.push(base, merge), history=True, tree=False)
        print("NEGATIVE_CONTROL branch_removed: old_exit=0 new_exit=2 history_positive tree_clean")

    def test_old_flags_miss_merge_only_secret(self) -> None:
        self.git("checkout", "-q", "-b", "feature")
        self.write("application/feature.py", "feature = True\n")
        self.commit("clean feature")
        self.git("checkout", "-q", "main")
        self.write("application/main.py", "main = True\n")
        base = self.commit("clean base")
        self.git("merge", "-q", "--no-ff", "--no-commit", "feature")
        self.leak()
        merge = self.commit("merge-only synthetic finding")
        self.legacy_scan(base, merge)
        self.assert_scan(2, self.push(base, merge), history=True, tree=True)
        print("NEGATIVE_CONTROL merge_only: old_exit=0 new_exit=2 history_positive tree_positive")

    def test_pull_request_detects_real_secret(self) -> None:
        self.git("checkout", "-q", "-b", "feature")
        self.leak()
        self.commit("feature synthetic finding")
        base, source, merge = self.merge_feature()
        self.assert_scan(2, self.pull_request(base, source), name="pull_request", sha=merge,
                         history=True, tree=True)

    def test_manual_checks_reachable_removed_history(self) -> None:
        self.leak()
        self.commit("manual synthetic finding")
        self.git("rm", "--cached", "--", "application/settings.py")
        self.exclude_retained("application/settings.py")
        self.commit("remove manual finding")
        self.assert_scan(2, {"ref": "main", "inputs": {}}, name="workflow_dispatch",
                         history=True, tree=False)

    def test_unrelated_branch_is_out_of_scope(self) -> None:
        self.git("checkout", "-q", "-b", "unrelated")
        self.leak()
        self.commit("unrelated synthetic finding")
        self.git("checkout", "-q", "main")
        self.write("application/clean.py", "answer = 42\n")
        head = self.commit("clean selected update")
        self.assert_scan(0, self.push(self.base, head), history=False, tree=False)
        self.assert_scan(0, {"ref": "main"}, name="workflow_dispatch", history=False, tree=False)

    def test_empty_commit_is_valid_and_tree_still_runs(self) -> None:
        head = self.commit("valid empty update", empty=True)
        self.assert_scan(0, self.push(self.base, head), history=False, tree=False)
        self.leak()
        before = self.commit("existing tree finding")
        head = self.commit("empty update over existing finding", empty=True)
        self.assert_scan(2, self.push(before, head), history=False, tree=True)

    def test_binary_only_update_is_valid_and_tree_still_runs(self) -> None:
        self.leak()
        before = self.commit("existing tree finding")
        self.write("application/data.bin", b"\x00\xff\x00\xfe" * 64)
        head = self.commit("binary-only update")
        self.assert_scan(2, self.push(before, head), history=False, tree=True)

    def test_export_ignore_and_gitignore_cannot_hide_tracked_tree(self) -> None:
        self.leak()
        self.write(".gitattributes", "application/settings.py export-ignore\n")
        before = self.commit("tracked finding with archive exclusion")
        self.write(".gitignore", "application/settings.py\n")
        head = self.commit("tracked finding now ignored by worktree rules")
        self.assert_scan(2, self.push(before, head), history=False, tree=True)

    def test_symlink_does_not_read_external_target(self) -> None:
        value = self.synthetic_key()
        self.values.append(value)
        outside = self.directory / "external.py"
        outside.write_text('api_key = "' + value + '"\n')
        (self.repo / "application").mkdir()
        (self.repo / "application/settings.py").symlink_to(outside)
        head = self.commit("tracked link only")
        self.assert_scan(0, self.push(self.base, head), history=False, tree=False)

    def test_binary_attribute_cannot_hide_removed_text_secret(self) -> None:
        self.write(".gitattributes", "application/*.py -diff\n")
        before = self.commit("mark application path binary")
        self.leak()
        self.commit("transient text finding with binary attribute")
        self.git("rm", "--cached", "--", "application/settings.py")
        self.exclude_retained("application/settings.py")
        head = self.commit("remove binary-attributed finding")
        self.assert_scan(2, self.push(before, head), history=True, tree=False)

    def test_git_environment_cannot_redirect_or_replace_history(self) -> None:
        self.leak()
        leaked = self.commit("transient finding before environment injection")
        self.git("rm", "--cached", "--", "application/settings.py")
        self.exclude_retained("application/settings.py")
        head = self.commit("remove transient finding")
        self.git("update-ref", "refs/poison/" + leaked, self.base)
        cases = [
            {"GIT_DIR": str(self.directory / "nonexistent-gitdir"),
             "GIT_WORK_TREE": str(self.directory / "nonexistent-worktree")},
            {"GIT_REPLACE_REF_BASE": "refs/poison/"},
            {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "log.showSignature",
             "GIT_CONFIG_VALUE_0": "true"},
        ]
        for index, extra_env in enumerate(cases):
            with self.subTest(environment=index):
                self.assert_scan(2, self.push(ZERO, head), history=True, tree=False,
                                 extra_env=extra_env)

    def test_force_push_and_annotated_tag_select_candidate(self) -> None:
        self.write("application/old.py", "old = True\n")
        old = self.commit("previous ref tip")
        self.git("checkout", "-q", "-b", "rewritten", self.base)
        self.leak()
        head = self.commit("force-push candidate finding")
        self.assert_scan(2, self.push(old, head, forced=True), history=True, tree=True)
        self.git("tag", "-a", "synthetic-tag", "-m", "local annotated tag")
        tag = self.git("rev-parse", "synthetic-tag")
        self.assert_scan(2, self.push(ZERO, tag, ref="refs/tags/synthetic-tag", created=True),
                         sha=tag, history=True, tree=True)

    def test_pr_candidate_cannot_add_allowlist(self) -> None:
        self.git("checkout", "-q", "-b", "feature")
        self.leak()
        self.write(".gitleaks.toml", '[extend]\nuseDefault = true\n[allowlist]\npaths = [".*"]\n')
        self.commit("candidate attempts broad exemption")
        base, source, merge = self.merge_feature()
        summary = self.assert_scan(2, self.pull_request(base, source), name="pull_request",
                                   sha=merge, history=True, tree=True)
        self.assertEqual(summary["policy_commit"], base)

    def test_pr_candidate_cannot_ignore_removed_history(self) -> None:
        self.git("checkout", "-q", "-b", "feature")
        self.leak("application/transient.py")
        leaked = self.commit("transient candidate finding")
        self.git("rm", "--cached", "--", "application/transient.py")
        self.exclude_retained("application/transient.py")
        self.write(".gitleaksignore", leaked + ":application/transient.py:generic-api-key:1\n")
        self.commit("candidate attempts historical fingerprint exemption")
        base, source, merge = self.merge_feature()
        self.assert_scan(2, self.pull_request(base, source), name="pull_request", sha=merge,
                         history=True, tree=False)

    def test_pr_trusted_base_ignore_is_honored(self) -> None:
        self.git("checkout", "-q", "-b", "feature")
        self.leak("application/transient.py")
        leaked = self.commit("known branch finding")
        self.git("rm", "--cached", "--", "application/transient.py")
        self.exclude_retained("application/transient.py")
        self.commit("remove known finding")
        self.git("checkout", "-q", "main")
        self.write(".gitleaksignore", leaked + ":application/transient.py:generic-api-key:1\n")
        base = self.commit("trusted base policy exempts known fingerprint")
        self.git("checkout", "-q", "feature")
        _, source, merge = self.merge_feature()
        summary = self.assert_scan(0, self.pull_request(base, source), name="pull_request",
                                   sha=merge, history=False, tree=False)
        self.assertEqual(summary["policy_commit"], base)

    def test_pr_candidate_global_ignore_cannot_hide_final_tree(self) -> None:
        self.git("checkout", "-q", "-b", "feature")
        self.leak()
        self.write(".gitleaksignore", "application/settings.py:generic-api-key:1\n")
        self.commit("candidate attempts commit-independent exemption")
        base, source, merge = self.merge_feature()
        self.assert_scan(2, self.pull_request(base, source), name="pull_request", sha=merge,
                         history=True, tree=True)

    def test_pr_trusted_base_global_ignore_preserves_original_path(self) -> None:
        self.write(".gitleaksignore", "application/settings.py:generic-api-key:1\n")
        self.commit("trusted commit-independent exemption")
        self.git("checkout", "-q", "-b", "feature")
        self.leak()
        self.commit("finding covered by trusted base policy")
        base, source, merge = self.merge_feature()
        self.assert_scan(0, self.pull_request(base, source), name="pull_request", sha=merge,
                         history=False, tree=False)

    def test_push_and_manual_use_checked_commit_policy(self) -> None:
        self.leak()
        self.write(".gitleaks.toml", '[extend]\nuseDefault = true\n[allowlist]\n'
                   'paths = ["application/settings.py"]\n')
        head = self.commit("trusted checked commit includes path exemption")
        self.assert_scan(0, self.push(self.base, head), history=False, tree=False)
        self.assert_scan(0, {"ref": "main"}, name="workflow_dispatch", history=False, tree=False)

    def test_input_failures_are_not_clean(self) -> None:
        self.write("application/clean.py", "answer = 42\n")
        head = self.commit("clean candidate")
        cases = [
            ("unknown event", self.push(self.base, head), {"name": "unknown"}),
            ("missing before", {"after": head}, {}),
            ("missing after", {"before": self.base}, {}),
            ("malformed before", self.push("z" * 40, head), {}),
            ("short sha", self.push(self.base, head), {"sha": head[:39]}),
            ("symbolic sha", self.push(self.base, head), {"sha": "main"}),
            ("unknown before", self.push("f" * 40, head), {}),
            ("noop push", self.push(head, head), {}),
            ("deleted ref", self.push(self.base, head, deleted=True), {}),
            ("zero after", self.push(self.base, ZERO), {}),
            ("checkout mismatch", self.push(self.base, head), {"sha": self.base}),
            ("malformed event", {}, {"raw_event": "{"}),
            ("missing event", {}, {"missing_event": True}),
            ("nonobject event", [], {}),
            ("missing tool", self.push(self.base, head),
             {"binary": str(self.directory / "missing-gitleaks")}),
        ]
        for label, event, options in cases:
            with self.subTest(case=label):
                self.assert_scan(1, event, **options)

    def test_invalid_pr_parents_are_rejected(self) -> None:
        self.git("checkout", "-q", "-b", "feature")
        self.write("application/clean.py", "feature = True\n")
        source = self.commit("feature")
        self.assert_scan(1, self.pull_request(self.base, source), name="pull_request")
        base, source, merge = self.merge_feature()
        self.assert_scan(1, self.pull_request(source, base), name="pull_request", sha=merge)
        self.assert_scan(1, self.pull_request(base, base), name="pull_request", sha=merge)

    def test_existing_output_cannot_reuse_stale_reports(self) -> None:
        head = self.commit("empty candidate", empty=True)
        output = self.directory / "existing-output"
        output.mkdir()
        # A stale success summary cannot be overwritten or accepted as a new result.
        sentinel = '{"status":"stale","exit":99}\n'
        (output / "summary.json").write_text(sentinel)
        event_path = self.directory / "existing-event.json"
        event_path.write_text(json.dumps(self.push(self.base, head)))
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(RUNNER), "--repo", str(self.repo),
             "--event-path", str(event_path), "--event-name", "push", "--sha", head,
             "--gitleaks", self.binary, "--output", str(output)],
            env=self.env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertEqual((output / "summary.json").read_text(), sentinel)

    def stub(self, mode: str) -> str:
        path = self.directory / ("stub-" + mode)
        body = '''import json, pathlib, sys
if sys.argv[1:] == ["version"]:
    print("8.24.3")
    raise SystemExit(0)
mode = MODE
if mode == "crash":
    raise SystemExit(7)
args = sys.argv[1:]
report = pathlib.Path(args[args.index("--report-path") + 1])
if mode == "malformed":
    report.write_text("{")
elif mode == "object":
    report.write_text("{}")
elif mode == "baditem":
    report.write_text('[{"Description":"missing rule"}]')
elif mode == "rc0finding":
    report.write_text('[{"RuleID":"synthetic-rule","Secret":"REDACTED"}]')
elif mode == "rc2empty":
    report.write_text("[]")
elif mode == "emptycoverage":
    report.write_text("[]")
    print("0 commits scanned")
if mode == "rc2empty":
    raise SystemExit(2)
raise SystemExit(0)
'''
        path.write_text("#!" + sys.executable + "\n" + body.replace("MODE", repr(mode)))
        path.chmod(0o700)
        return str(path)

    def test_scanner_failures_are_not_clean(self) -> None:
        self.write("application/clean.py", "answer = 42\n")
        head = self.commit("text candidate requires coverage")
        for mode in ("crash", "missing", "malformed", "object", "baditem", "rc0finding",
                     "rc2empty", "emptycoverage"):
            with self.subTest(mode=mode):
                self.assert_scan(1, self.push(self.base, head), binary=self.stub(mode))


if __name__ == "__main__":
    unittest.main()
