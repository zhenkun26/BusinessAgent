"""Pure guard tests only: no application import, socket connection or PG execution."""
from __future__ import annotations

import asyncio
import ast
import builtins
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
from types import ModuleType
from uuid import uuid4
import unittest
from unittest.mock import AsyncMock, Mock, patch


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

    def make_export(self, root, *, mutation="none"):
        names = ["enterprise-agent/eval/run_approval_pg_acceptance.py",
                 "enterprise-agent/app/agents/execution.py", "enterprise-agent/app/api/approval.py",
                 "enterprise-agent/app/core/approval_deadline.py", "enterprise-agent/app/core/approval_timeout.py",
                 "enterprise-agent/" + HARNESS.MIGRATION]
        files = {}
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            content = b"pure fixture source\n"
            files[name] = hashlib.sha256(content).hexdigest()
            if name == "enterprise-agent/app/api/approval.py" and mutation in {"missing", "symlink"}:
                continue  # Construct the absent/link fixture without deleting a file.
            target.write_bytes(content)
        if mutation == "symlink":
            (root / "enterprise-agent/app/api/approval.py").symlink_to(
                root / "enterprise-agent/app/agents/execution.py")
        manifest = dict(head=SHA, tree="b" * 40, manifest_sha256="c" * 64, files=files)
        (root / "EXPORT-MANIFEST.json").write_text(json.dumps(manifest))
        return manifest

    def test_complete_export_and_source_tampering(self):
        for mutation in ("none", "bytes", "extra", "missing", "head", "traversal", "symlink"):
            with self.subTest(mutation=mutation):
                root = SOURCE.parents[1] / "eval/results" / ("approval-export-" + uuid4().hex)
                root.mkdir(parents=True)
                data = self.make_export(root, mutation=mutation)
                target = root / "enterprise-agent/app/api/approval.py"
                if mutation == "bytes": target.write_text("modified")
                if mutation == "extra": (root / "unapproved.py").write_text("extra")
                if mutation == "head": data["head"] = "d" * 40
                if mutation == "traversal": data["files"]["../escape"] = "a" * 64
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
        # Isolate this module's namespace and import capability in-process. Reject
        # application/third-party imports even if another test preloaded them.
        imports = []
        def stdlib_only(name, globals=None, locals=None, fromlist=(), level=0):
            imports.append(name)
            if level or name.split(".", 1)[0] not in sys.stdlib_module_names:
                raise AssertionError("Harness import must remain standard-library only")
            return builtins.__import__(name, globals, locals, fromlist, level)

        isolated = ModuleType("isolated_harness")
        isolated.__file__ = str(SOURCE)
        isolated.__dict__["__builtins__"] = dict(vars(builtins), __import__=stdlib_only)
        with patch.dict(sys.modules, {isolated.__name__: isolated}):
            exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), isolated.__dict__)
            self.assertTrue(imports)
            self.assertFalse(any(name == "app" or name.startswith("app.")
                                 or name == "asyncpg" for name in imports))
            # CLI help must exit without export reads or any network/DB setup.
            with patch.object(isolated, "verify_export", side_effect=AssertionError) as verify, \
                    patch.object(socket, "create_connection", side_effect=AssertionError) as connect, \
                    redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as caught:
                isolated.main(["--help"])
            self.assertEqual(caught.exception.code, 0)
            self.assertIn("--execute", output.getvalue())
            verify.assert_not_called()
            connect.assert_not_called()

    async def run_guard_control(self, enabled, *, original_query=False):
        """Model asyncpg's catalog char codec without importing a DB driver."""
        transaction = Mock(start=AsyncMock(), rollback=AsyncMock())
        ddl = Mock()
        ddl.transaction.return_value = transaction
        ddl.execute = AsyncMock(side_effect=["ALTER TABLE", "UPDATE 1"])

        async def fetchval(query, *args):
            if "tgenabled" in query:
                return enabled if "tgenabled::text" in query else enabled.encode()
            return "{}"

        ddl.fetchval = AsyncMock(side_effect=fetchval)
        case = HARNESS.Acceptance("test_postgresql_acceptance")
        case.ddl, case.guard_value, case.legacy_id = ddl, "{}", "fixture_legacy"
        case.deadline = Mock(contract=Mock(return_value=None))
        case.row, case.report = AsyncMock(return_value=object()), {}
        method = HARNESS.Acceptance.guard_negative_control
        if original_query:
            # Reproduce the pre-fix query while keeping all other assertions intact.
            source = SOURCE.read_text()
            self.assertEqual(source.count("SELECT tgenabled::text FROM pg_trigger WHERE "), 1)
            tree = ast.parse(source.replace("SELECT tgenabled::text FROM pg_trigger WHERE ",
                                            "SELECT tgenabled FROM pg_trigger WHERE "))
            definition = next(node for node in tree.body
                              if isinstance(node, ast.ClassDef) and node.name == "Acceptance")
            method_node = next(node for node in definition.body
                               if isinstance(node, ast.AsyncFunctionDef)
                               and node.name == "guard_negative_control")
            namespace = {}
            exec(compile(ast.Module(body=[method_node], type_ignores=[]),
                         "original_guard_negative_control", "exec"), namespace)
            method = namespace["guard_negative_control"]
        try:
            await method(case)
        finally:
            transaction.rollback.assert_awaited_once()
        self.assertTrue(case.report["negative_controls"][
            "guard_disabled_upgrade_succeeds_then_rolled_back"])

    def test_original_catalog_char_comparison_fails(self):
        with self.assertRaises(AssertionError):
            asyncio.run(self.run_guard_control("A", original_query=True))

    def test_catalog_text_cast_preserves_guard_negative_control(self):
        asyncio.run(self.run_guard_control("A"))

    def test_guard_restoration_still_rejects_non_always_states(self):
        for enabled in ("D", "O", ""):
            with self.subTest(enabled=enabled), self.assertRaises(AssertionError):
                asyncio.run(self.run_guard_control(enabled))

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
