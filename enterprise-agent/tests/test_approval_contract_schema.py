"""Source checks and explicit policy models, NOT PostgreSQL acceptance.

No application imports, SQL execution, subprocesses or services. The models specify
the intended boundary; they do not establish catalog deparsing, trigger semantics,
transaction rollback or locking. Those require the separately authorized PG harness.
Run directly with Python -I -B -S to use only the standard library.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unittest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
MIGRATION = DEPLOY / "migrations/009_approval_contract_provenance.sql"
SQL = MIGRATION.read_text()
CODE = "\n".join(line for line in SQL.splitlines() if not line.lstrip().startswith("--"))
STRINGS = {
    "version", "approval_id", "session_id", "requester_id", "operation_type", "risk_level",
    "created_at", "expires_at",
}
ARRAYS = {"tool_calls", "approver_roles", "targets"}
ORIGINAL = {
    # Integrated managed v1 is the candidate schema-only baseline, not old public init.
    "init.sql": "3652c4b0fc3421b369f643566d3b89451ed82cb35d46d6050ca5d87230a26212",
    "migrations/009_approval_contract_provenance.sql":
        "64c29daeb31d3b9d8f0fa3ad04c8e2b9285323b7b84879606b9194e651cab769",
    "migrations/001_prompt_versions.sql":
        "40e24bb3274db572b953fabca7347f20dbaf42716146c91f49f5e0baafd120da",
    "migrations/002_documents_ledger.sql":
        "b3f06ffc3f072aad49fed519121c6862430f2e8d20766af5d5c3b932c438e339",
    "migrations/003_user_password_hash.sql":
        "c7b5c2b4252a7f6a80fe540dfd82cccc481063b29d3191043b06455845c0be3d",
    "migrations/004_user_management.sql":
        "ff4331ecea9197e967d5aae45419fdb2097bba6c1882424226a8a55bf5c69ac8",
    "migrations/005_user_sso_identity.sql":
        "9ca86e4b3fcb90a62136b4cae7a62cf89b9894932eec704e9eb38cb907c05b65",
}


def snapshot() -> dict:
    return {
        "version": "utc-human-v2", "approval_id": "approval-new", "session_id": "session",
        "requester_id": "requester", "operation_type": "send_email_external", "risk_level": "high",
        "created_at": "2026-11-01T12:00:00.000000", "expires_at": "2026-11-02T12:00:00.000000",
        "tool_calls": [{"tool": "send_email_external", "params": {}}],
        "approver_roles": ["manager", "admin"],
        "targets": [{"tool": "send_email_external", "provider": "mock", "endpoint": ""}],
    }


def shape_model(value: object, *, sql_null: bool = False) -> bool:
    """Outer-shape specification. Python None otherwise models JSON null, not SQL NULL."""
    if sql_null:
        return True
    return (isinstance(value, dict) and set(value) == STRINGS | ARRAYS
            and value["version"] == "utc-human-v2"
            and all(isinstance(value[key], str) for key in STRINGS)
            and all(isinstance(value[key], list) for key in ARRAYS))


def update_model(old: dict, new: dict) -> dict:
    """Contract equality models JSONB value equality, not raw JSON formatting."""
    if old.get("approval_contract") != new.get("approval_contract"):
        raise ValueError("APPROVAL_CONTRACT_IMMUTABLE")
    return deepcopy(new)


EXPECTED_OBJECTS = {"column": "jsonb-nullable", "shape_function": "reviewed-shape",
                    "guard_function": "reviewed-guard", "check": "validated-shape",
                    "trigger": "always-after-update"}


def install_model(state: dict, *, late_failure: bool = False) -> dict:
    """Atomic policy model only; cannot prove PostgreSQL transaction behavior."""
    staged = deepcopy(state)
    existing = staged["objects"]
    if existing:
        if existing != EXPECTED_OBJECTS:
            raise ValueError("PARTIAL_OR_DRIFTED_INSTALLATION")
    else:
        staged["objects"] = deepcopy(EXPECTED_OBJECTS)
        for row in staged["rows"]:
            row["approval_contract"] = None
    if late_failure:
        raise ValueError("SYNTHETIC_LATE_FAILURE")
    return staged


class MigrationSourceTests(unittest.TestCase):
    def test_complete_transaction_locks_before_ddl(self) -> None:
        self.assertTrue(CODE.strip().startswith("BEGIN;"))
        self.assertTrue(CODE.strip().endswith("COMMIT;"))
        self.assertEqual(len(re.findall(r"(?m)^COMMIT;$", CODE)), 1)
        self.assertLess(CODE.index("LOCK TABLE public.approval_requests IN ACCESS EXCLUSIVE MODE"),
                        CODE.index("ADD COLUMN approval_contract"))
        self.assertIn("SET LOCAL search_path TO pg_catalog", CODE)

    def test_no_history_backfill_overwrite_or_ledger(self) -> None:
        self.assertNotRegex(CODE, r"(?i)\b(?:UPDATE|DELETE\s+FROM)\s+(?:public\.)?approval_requests\b")
        self.assertNotRegex(CODE, r"(?i)\b(?:DROP|TRUNCATE)\b|CREATE\s+OR\s+REPLACE")
        self.assertNotIn("schema_migrations", CODE)
        self.assertNotRegex(CODE, r"00[1-8]_")

    def test_existing_column_shape_and_defaults_are_checked(self) -> None:
        self.assertIn("ADD COLUMN approval_contract JSONB DEFAULT NULL", CODE)
        for guard in ("actual.atttypid <> 'jsonb'::regtype", "actual.attnotnull",
                      "actual.attidentity <> ''", "actual.attgenerated <> ''",
                      "actual.default_expression IS NOT NULL",
                      "actual.default_expression <> 'NULL::jsonb'"):
            self.assertIn(guard, CODE)

    def test_shape_source_requires_exact_outer_keys_and_types(self) -> None:
        body = SQL.split("$shape$")[1]
        key_lists = re.findall(r"ARRAY\[(.*?)\]", body, re.S)
        self.assertEqual(len(key_lists), 2)
        for keys in key_lists:
            self.assertEqual(set(re.findall(r"'([^']+)'", keys)), STRINGS | ARRAYS)
        self.assertIn("WHEN contract IS NULL THEN TRUE", body)
        self.assertIn("jsonb_typeof(contract) <> 'object'", body)
        self.assertIn("contract ->> 'version' = 'utc-human-v2'", body)
        for key in STRINGS - {"version"}:
            self.assertIn(f"jsonb_typeof(contract -> '{key}') = 'string'", body)
        for key in ARRAYS:
            self.assertIn(f"jsonb_typeof(contract -> '{key}') = 'array'", body)

    def test_repeat_verifies_function_bodies_and_security_properties(self) -> None:
        for guard in ("routine_count <> 1", "pg_get_function_identity_arguments(actual.oid)",
                      "pg_get_function_result(actual.oid)", "actual.lanname <> item.language",
                      "actual.prosrc <> item.source", "actual.prosecdef", "actual.proisstrict",
                      "actual.proleakproof", "actual.prosupport <> 0", "actual.proretset",
                      "actual.provolatile::text", "actual.proparallel::text",
                      "actual.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']"):
            self.assertIn(guard, CODE)
        self.assertIn("APPROVAL_CONTRACT_PARTIAL_INSTALLATION", CODE)
        self.assertIn("APPROVAL_CONTRACT_FUNCTION_MISSING_OR_OVERLOADED", CODE)

    def test_repeat_checks_validated_constraint_expression(self) -> None:
        self.assertIn("actual.contype <> 'c' OR NOT actual.convalidated", CODE)
        self.assertIn("pg_get_expr(actual.conbin, actual.conrelid) IS DISTINCT FROM", CODE)
        self.assertIn("'public.approval_contract_v2_shape(approval_contract)'", CODE)
        self.assertIn("actual.conkey IS DISTINCT FROM ARRAY[column_number]", CODE)

    def test_all_update_trigger_checks_old_new_and_actual_catalog(self) -> None:
        self.assertIn("OLD.approval_contract IS DISTINCT FROM NEW.approval_contract", CODE)
        self.assertIn("ERRCODE = '23514'", CODE)
        self.assertIn("AFTER UPDATE ON public.approval_requests", CODE)
        self.assertNotIn("UPDATE OF", CODE)
        self.assertIn("ENABLE ALWAYS TRIGGER approval_contract_v2_immutable", CODE)
        for guard in ("actual.tgfoid <> guard_oid", "actual.tgtype <> 17",
                      "actual.tgenabled <> 'A'", "actual.tgattr::text <> ''",
                      "actual.tgqual IS NOT NULL", "actual.tgnargs <> 0"):
            self.assertIn(guard, CODE)

    def test_integrated_baseline_and_standalone_history_unchanged(self) -> None:
        for path, expected in ORIGINAL.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((DEPLOY / path).read_bytes()).hexdigest(), expected)


class ManagedMigrationTests(unittest.TestCase):
    def test_managed_v1_to_v8_are_frozen_including_c10(self):
        expected = {
            'init.sql':
                '3652c4b0fc3421b369f643566d3b89451ed82cb35d46d6050ca5d87230a26212',
            '002_tool_operations.sql':
                'eaad50d8ab534afac91138a8e2f9e0924e5731be52c5883ef9ab96c2066bf1e7',
            '003_task_jobs.sql':
                '509c51e084a35a657491cae09709d4f930a6c958ff1d54fdbeb06571bcd0b8a2',
            '004_saga_journal.sql':
                '00b28bf3f460525713a0ec19a378cf783c43850ace1787f95b3e92fc05e12376',
            '005_approval_execution.sql':
                '3c4fd1fc49c4e3792c7955149684f2c677459383d2f98a94b76c48cbf5977126',
            '006_knowledge_publication.sql':
                '52ff47563aad423e62fdd018fccf3403bd6532dd4404e80c5caa171873ee618d',
            '007_audit_identity.sql':
                '37a67f266c8141c8faca6ff3282f1413845ed6948c952646c3568378266a1243',
            '008_session_fencing.sql':
                'bde273f31cffd92af6aa8768d98186357f3f678504010230c5b57f9d7089e59d',
        }
        manifest = json.loads((DEPLOY / 'schema_manifest.json').read_text())
        self.assertEqual([m['version'] for m in manifest['migrations']], list(range(1, 10)))
        self.assertEqual({m['file']: m['sha256'] for m in manifest['migrations'][:8]}, expected)
        for name, checksum in expected.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((DEPLOY / name).read_bytes()).hexdigest(), checksum)
        self.assertEqual(manifest['migrations'][7]['name'], 'session_fencing')
        self.assertIn('session_write_fences', manifest['columns'])
        self.assertIn('session_checkpoint_publications', manifest['columns'])

    def test_managed_v9_is_exact_standalone_body_inside_runner_transaction(self):
        manifest = json.loads((DEPLOY / 'schema_manifest.json').read_text())
        entry = manifest['migrations'][8]
        self.assertEqual(entry['name'], 'approval_contract_provenance')
        managed = (DEPLOY / entry['file']).read_text()
        self.assertEqual(hashlib.sha256(managed.encode()).hexdigest(), entry['sha256'])
        body = SQL[SQL.index('SET LOCAL search_path'):].removesuffix('COMMIT;\n')
        self.assertEqual(managed[managed.index('SET LOCAL search_path'):], body)
        self.assertNotRegex(managed, r'(?m)^(?:BEGIN|COMMIT|ROLLBACK);$')
        self.assertEqual(manifest['columns']['approval_requests']['approval_contract'], {'type': 'jsonb'})


class ContractPolicyModelTests(unittest.TestCase):
    def test_insert_accepts_sql_null_or_shaped_snapshot(self) -> None:
        self.assertTrue(shape_model(None, sql_null=True))
        self.assertTrue(shape_model(snapshot()))
        for value in (None, [], "utc-human-v2", {}, {**snapshot(), "version": "utc-human-v1"},
                      {**snapshot(), "extra": True}, {**snapshot(), "tool_calls": {}},
                      {**snapshot(), "expires_at": None}):
            with self.subTest(value=value):
                self.assertFalse(shape_model(value))

    def test_shape_alone_never_authenticates_binding_or_ttl(self) -> None:
        row = snapshot()
        row["requester_id"] = "another-person"
        row["expires_at"] = "not-a-date"
        row["tool_calls"] = []
        self.assertTrue(shape_model(row))  # Application verifier must reject these semantics.

    def test_update_never_converts_clears_or_replaces_provenance(self) -> None:
        for before, after in ((None, snapshot()), (snapshot(), None),
                              (snapshot(), {**snapshot(), "requester_id": "replacement"})):
            with self.subTest(before=before, after=after):
                old = {"status": "pending", "approval_contract": before}
                unchanged = deepcopy(old)
                with self.assertRaisesRegex(ValueError, "APPROVAL_CONTRACT_IMMUTABLE"):
                    update_model(old, {"status": "executing", "approval_contract": after})
                self.assertEqual(old, unchanged)

    def test_unchanged_contract_allows_normal_status_transition(self) -> None:
        for contract in (None, snapshot()):
            old = {"status": "pending", "approval_contract": contract}
            new = {"status": "executing", "approval_contract": deepcopy(contract)}
            self.assertEqual(update_model(old, new), new)

    def test_model_install_and_repeat_preserve_all_legacy_values(self) -> None:
        rows = [{"status": status, "created_at": "original-naive", "expires_at": None,
                 "prefill_payload": {"untrusted": True}} for status in
                ("pending", "approved_pending_reauth", "executing", "execution_unknown", "executed")]
        state = {"objects": {}, "rows": rows}
        installed = install_model(state)
        self.assertEqual(installed["rows"], [{**row, "approval_contract": None} for row in rows])
        self.assertEqual(install_model(installed), installed)
        self.assertEqual(state, {"objects": {}, "rows": rows})

    def test_model_partial_or_drifted_installations_fail_without_repair(self) -> None:
        for name in EXPECTED_OBJECTS:
            for missing in (False, True):
                objects = deepcopy(EXPECTED_OBJECTS)
                if missing:
                    objects.pop(name)
                else:
                    objects[name] = "unreviewed-existing-definition"
                state = {"objects": objects, "rows": [{"approval_contract": snapshot()}]}
                before = deepcopy(state)
                with self.assertRaises(ValueError):
                    install_model(state)
                self.assertEqual(state, before)

    def test_model_late_failure_rolls_back_objects_and_rows(self) -> None:
        state = {"objects": {}, "rows": [{"status": "pending"}]}
        before = deepcopy(state)
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_LATE_FAILURE"):
            install_model(state, late_failure=True)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
