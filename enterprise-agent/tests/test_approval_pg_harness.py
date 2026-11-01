"""Pure guard tests only: no application import, socket connection or PG execution."""
from __future__ import annotations

import asyncio
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "eval/run_approval_pg_acceptance.py"
SPEC = importlib.util.spec_from_file_location("approval_pg_harness_pure", SOURCE)
HARNESS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HARNESS
SPEC.loader.exec_module(HARNESS)
RUN = "8e67f06f5ee94b90be640d3e812d3a27"
SHA = "a" * 40


class HarnessGuards(unittest.TestCase):
    def fixture(self, **changes):
        values = dict(run_id=RUN, database=f"ba_approval_{RUN}_fresh", port=5432,
                      candidate_sha=SHA, artifact_dir=Path("/tmp/approval-test-artifacts"))
        return HARNESS.Fixture(**(values | changes))

    def test_exact_run_database_boundary(self):
        self.fixture().validate()
        self.fixture(database=f"ba_approval_{RUN}_upgrade").validate()
        for changes in ({"database": "postgres"}, {"database": "enterprise_agent"},
                        {"database": f"ba_approval_{'b' * 32}_fresh"},
                        {"database": f"ba_approval_{RUN}_fresh;DROP DATABASE x"},
                        {"run_id": "0" * 32}, {"run_id": "not-a-uuid"},
                        {"port": 0}, {"port": 65536}, {"candidate_sha": "main"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.fixture(**changes).validate()

    def test_missing_execute_cannot_reach_source_or_database(self):
        with patch.object(HARNESS, "verify_export", side_effect=AssertionError("must not run")) as verify:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                HARNESS.main(["--run-id", RUN, "--database", f"ba_approval_{RUN}_fresh",
                              "--port", "5432", "--candidate-sha", SHA, "--artifact-dir", "/tmp/test"])
        self.assertEqual(caught.exception.code, 2)
        verify.assert_not_called()

    def test_server_marks_and_privileges_are_fail_closed(self):
        good = dict(database=self.fixture().database, role=HARNESS.APP_ROLE,
                    fixture=HARNESS.FIXTURE_MARK, run_id=RUN, owner=HARNESS.DDL_ROLE,
                    superuser=False, createdb=False, createrole=False,
                    replication=False, bypassrls=False)
        HARNESS.validate_server(good, self.fixture(), HARNESS.APP_ROLE)
        changes = [{field: True} for field in ("superuser", "createdb", "createrole", "replication", "bypassrls")]
        changes += [{field: "wrong"} for field in ("database", "role", "fixture", "run_id", "owner")]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                HARNESS.validate_server(good | change, self.fixture(), HARNESS.APP_ROLE)

    def make_export(self, root):
        names = ["enterprise-agent/eval/run_approval_pg_acceptance.py",
                 "enterprise-agent/app/agents/execution.py", "enterprise-agent/app/api/approval.py",
                 "enterprise-agent/app/core/approval_deadline.py", "enterprise-agent/app/core/approval_timeout.py",
                 "enterprise-agent/" + HARNESS.MIGRATION]
        files = {}
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("pure fixture source\n")
            files[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest = dict(head=SHA, tree="b" * 40, manifest_sha256="c" * 64, files=files)
        (root / "EXPORT-MANIFEST.json").write_text(json.dumps(manifest))
        return manifest

    def test_complete_export_and_source_tampering(self):
        for mutation in ("none", "bytes", "extra", "missing", "head", "traversal", "symlink"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                data = self.make_export(root)
                target = root / "enterprise-agent/app/api/approval.py"
                if mutation == "bytes": target.write_text("modified")
                if mutation == "extra": (root / "unapproved.py").write_text("extra")
                if mutation == "missing": target.unlink()
                if mutation == "head": data["head"] = "d" * 40
                if mutation == "traversal": data["files"]["../escape"] = "a" * 64
                if mutation == "symlink":
                    target.unlink()
                    target.symlink_to(root / "enterprise-agent/app/agents/execution.py")
                (root / "EXPORT-MANIFEST.json").write_text(json.dumps(data))
                if mutation == "none":
                    self.assertEqual(HARNESS.verify_export(root, SHA)["files_verified"], 6)
                else:
                    with self.assertRaises(ValueError): HARNESS.verify_export(root, SHA)

    def test_network_fence_rejects_without_opening_socket_connection(self):
        denied = []
        with HARNESS.network_fence(5432, denied), socket.socket() as sock:
            for address in (("example.invalid", 5432), ("127.0.0.1", 6379), ("::1", 5432), "/tmp/socket"):
                with self.assertRaises(PermissionError): sock.connect(address)
        self.assertEqual(len(denied), 4)

    def test_synthetic_credentials_only(self):
        for value in ("", "a" * 31, "actual-password", "f" * 129):
            with patch.dict("os.environ", {"BA_APPROVAL_PG_PASSWORD": value}):
                with self.assertRaises(ValueError): HARNESS.password("BA_APPROVAL_PG_PASSWORD")
        with patch.dict("os.environ", {"BA_APPROVAL_PG_PASSWORD": "a" * 64}):
            self.assertEqual(HARNESS.password("BA_APPROVAL_PG_PASSWORD"), "a" * 64)

    def test_commit_ack_fault_is_after_real_delegate(self):
        async def check():
            class Session:
                commits = 0
                async def commit(self): self.commits += 1
            real = Session()
            wrapped = HARNESS.FaultSession(real, "ack")
            with self.assertRaises(ConnectionError): await wrapped.commit()
            self.assertEqual(real.commits, 1)
            self.assertTrue(wrapped.injected)
        asyncio.run(check())

    def test_barrier_precedes_actual_commit(self):
        async def check():
            class Session:
                commits = 0
                async def commit(self): self.commits += 1
            real = Session()
            entered, release = asyncio.Event(), asyncio.Event()
            wrapped = HARNESS.PreCommitBarrier(real, entered, release)
            task = asyncio.create_task(wrapped.commit())
            await entered.wait()
            self.assertEqual(real.commits, 0)
            release.set()
            await task
            self.assertEqual(real.commits, 1)
        asyncio.run(check())

    def test_mandatory_checks_are_unique_and_no_skips_defined(self):
        self.assertEqual(len(set(HARNESS.MANDATORY)), len(HARNESS.MANDATORY))
        self.assertNotIn("@unittest.skip", SOURCE.read_text())
        # Other suite modules legitimately import app.main. Verify this harness in
        # a fresh stdlib-only process instead of relying on global collection order.
        code = """import importlib.util,sys
spec=importlib.util.spec_from_file_location('isolated_harness',sys.argv[1])
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
assert not any(name=='app' or name.startswith('app.') or name=='asyncpg' for name in sys.modules)
print('STDLIB_IMPORT_ONLY')
"""
        result = subprocess.run([sys.executable, '-I', '-B', '-S', '-c', code, str(SOURCE)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr[:300])
        self.assertEqual(result.stdout.strip(), 'STDLIB_IMPORT_ONLY')

    def test_missing_failed_or_truthy_check_never_passes(self):
        good = {name: {"passed": True} for name in HARNESS.MANDATORY}
        self.assertTrue(HARNESS.complete_checks(good))
        first = HARNESS.MANDATORY[0]
        for value in ({}, {"passed": False}, {"passed": "true"}, {"passed": 1}, None):
            self.assertFalse(HARNESS.complete_checks(good | {first: value}))
        self.assertFalse(HARNESS.complete_checks({key: value for key, value in good.items() if key != first}))
        self.assertFalse(HARNESS.complete_checks(good | {"unknown": {"passed": True}}))


if __name__ == "__main__":
    unittest.main()
