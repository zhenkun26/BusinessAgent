"""Regression tests with retained fixtures; runnable directly without pytest/plugins."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "enterprise-agent/scripts/safe_validate.py"
SPEC = importlib.util.spec_from_file_location("safe_validate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
safe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(safe)


class SafeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.retained = ROOT / "enterprise-agent/eval/results/safe-validation-tests" / uuid4().hex
        cls.retained.mkdir(parents=True, exist_ok=False)

    def fixture_root(self) -> Path:
        root = self.retained / uuid4().hex
        root.mkdir()
        paths = list(safe.INPUTS) + [
            f"enterprise-agent/eval/{name}.py" for name, _ in safe.REVIEWED.values()
        ] + ["enterprise-agent/scripts/safe_validate.py"]
        for name in paths:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        return root

    def test_reviewed_checks_preserve_blocked_business_outcome(self) -> None:
        report = safe.run_checks(ROOT, list(safe.REVIEWED))
        self.assertEqual(report["execution_status"], "PASS")
        self.assertEqual(report["overall_status"], "BLOCKED")
        statuses = {item["id"]: item["result_status"] for item in report["results"]}
        self.assertEqual(statuses, {
            "uat-plan": "PASS", "uat-readiness": "BLOCKED", "grey-plan": "PASS",
            "release-gate": "BLOCKED", "g0-replay": "PASS",
        })
        self.assertFalse(report["release_allowed"])
        self.assertFalse(report["formal_uat"])

    def test_guard_blocks_real_write_before_truncation(self) -> None:
        target = self.retained / (uuid4().hex + ".txt")
        target.write_text("preserved", encoding="utf-8")
        with safe.ReadOnlyGuard() as guard:
            with self.assertRaises(safe.SafetyError):
                target.write_text("overwrite", encoding="utf-8")
        self.assertTrue(guard.denied)
        self.assertEqual(target.read_text(), "preserved")

    def test_guard_rejects_side_effect_events_without_invoking_syscalls(self) -> None:
        events = [
            ("os.remove", ("probe", -1)), ("os.rmdir", ("probe", -1)),
            ("os.rename", ("a", "b", -1, -1)), ("os.mkdir", ("probe", 0o700, -1)),
            ("os.chmod", ("probe", 0o777, -1)), ("os.symlink", ("a", "b", -1)),
            ("socket.connect", (None, ("127.0.0.1", 1))),
            ("subprocess.Popen", ("probe", [], None, None)),
            ("os.system", (b"probe",)), ("ctypes.dlopen", ("probe",)),
            ("open", ("probe", None, os.O_RDWR)),
        ]
        with safe.ReadOnlyGuard() as guard:
            for event, args in events:
                with self.subTest(event=event), self.assertRaises(safe.SafetyError):
                    # Unit-test policy without emitting fake process-wide OS events.
                    # Real audit-hook installation is exercised by retained write-denial tests.
                    guard.audit(event, args)

    def test_record_collision_keeps_original_bytes(self) -> None:
        root = self.retained / uuid4().hex
        root.mkdir()
        path = safe.record_report(root, "same-id", {"result": "first"})
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            safe.record_report(root, "same-id", {"result": "second"})
        self.assertEqual(path.read_bytes(), before)

    def test_record_rejects_traversal_and_symlink_parent(self) -> None:
        root = self.retained / uuid4().hex
        root.mkdir()
        with self.assertRaises(safe.SafetyError):
            safe.record_report(root, "../escape", {})
        (root / "enterprise-agent").symlink_to(self.retained, target_is_directory=True)
        with self.assertRaises(safe.SafetyError):
            safe.record_report(root, "safe-id", {})

    def test_source_drift_blocks_before_import(self) -> None:
        root = self.fixture_root()
        path = root / "enterprise-agent/eval/validate_uat_plan.py"
        path.write_text("raise RuntimeError('DO_NOT_IMPORT_MARKER')\n", encoding="utf-8")
        with patch.object(safe, "git_metadata", return_value={"commit": "a" * 40}):
            report = safe.run_checks(root, ["uat-plan"])
        self.assertEqual(report["results"][0]["error_code"], "SOURCE_REVIEW_REQUIRED")
        self.assertNotIn("DO_NOT_IMPORT_MARKER", json.dumps(report))

    def test_failure_is_not_relabelled_as_blocked_or_pass(self) -> None:
        root = self.fixture_root()
        path = root / safe.INPUTS[2]
        fixture = json.loads(path.read_text())
        fixture["external_side_effects_allowed"] = True
        path.write_text(json.dumps(fixture), encoding="utf-8")
        with patch.object(safe, "git_metadata", return_value={"commit": "a" * 40}):
            report = safe.run_checks(root, ["g0-replay"])
        self.assertEqual(report["execution_status"], "PASS")
        self.assertEqual(report["overall_status"], "FAIL")
        self.assertEqual(safe.EXIT_CODES[report["overall_status"]], 1)

    def test_raw_details_and_exceptions_are_not_reported(self) -> None:
        marker = "SYNTHETIC_SECRET_DO_NOT_PERSIST"
        result = safe.summarize("uat-plan", {
            "overall_status": "failed", "detail": marker,
            "checks": [{"passed": False, "name": marker, "detail": marker}],
        })
        self.assertNotIn(marker, json.dumps(result))
        with patch.object(safe, "load_reviewed", side_effect=RuntimeError(marker)):
            report = safe.run_checks(ROOT, ["uat-plan"])
        self.assertNotIn(marker, json.dumps(report))
        self.assertEqual(report["results"][0]["error_code"], "CHECK_EXECUTION_FAILED")

    def test_unknown_or_duplicate_checks_rejected_before_metadata(self) -> None:
        with patch.object(safe, "git_metadata") as metadata:
            for selected in (["arbitrary-module"], ["g0-replay", "g0-replay"], []):
                with self.assertRaises(safe.SafetyError):
                    safe.run_checks(ROOT, selected)
            metadata.assert_not_called()

    def test_input_mutation_detected(self) -> None:
        root = self.fixture_root()
        real_digest = safe.digest
        calls = 0

        def changed_hash(path: Path) -> str:
            nonlocal calls
            calls += 1
            # Five pre-run paths for one selected validator; post-run digest differs.
            return "changed" if calls > 5 else real_digest(path)

        with patch.object(safe, "git_metadata", return_value={"commit": "a" * 40}), \
                patch.object(safe, "digest", side_effect=changed_hash):
            with self.assertRaisesRegex(safe.SafetyError, "INPUT_CHANGED_DURING_RUN"):
                safe.run_checks(root, ["uat-plan"])

    def test_suppressed_validator_error_cannot_hide_side_effect_denial(self) -> None:
        target = self.retained / (uuid4().hex + ".txt")
        target.write_text("preserved", encoding="utf-8")

        def validator(*args: object) -> dict:
            print("SYNTHETIC_PRIVATE_OUTPUT")
            try:
                target.write_text("must not overwrite", encoding="utf-8")
            except safe.SafetyError:
                pass
            return {"overall_status": "passed", "checks": [{"passed": True}]}

        module = type("FakeModule", (), {"validate_uat_plan": staticmethod(validator)})
        with patch.object(safe, "load_reviewed", return_value=module), \
                redirect_stdout(io.StringIO()) as output:
            report = safe.run_checks(ROOT, ["uat-plan"])
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(report["overall_status"], "BLOCKED")
        self.assertNotIn("SYNTHETIC_PRIVATE_OUTPUT", json.dumps(report))
        self.assertEqual(target.read_text(encoding="utf-8"), "preserved")

    def test_cli_reports_pass_blocked_and_record_collision(self) -> None:
        root = self.fixture_root()
        with patch.object(safe, "ROOT", root), \
                patch.object(safe, "git_metadata", return_value={"commit": "a" * 40}):
            for args, expected in [
                (["--check", "g0-replay", "--record", "once"], 0),
                (["--check", "g0-replay", "--record", "once"], 2),
                (["--check", "uat-readiness"], 2),
            ]:
                with patch.object(sys, "argv", ["safe_validate.py", *args]), \
                        redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(safe.main(), expected)
                self.assertIn("overall_status", json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
