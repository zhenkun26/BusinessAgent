"""Packaged migration contracts; standard library only, never connects on import."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
LOCK_ID = 53409303003
HISTORY_SQL = "SELECT version, name, checksum FROM public.schema_migrations ORDER BY version"
COLUMNS_SQL = """SELECT table_name, column_name, udt_name, character_maximum_length, is_nullable
FROM information_schema.columns WHERE table_schema = 'public'"""
INDEXES_SQL = """SELECT c.relname, i.indisunique
FROM pg_catalog.pg_index i
JOIN pg_catalog.pg_class c ON c.oid = i.indexrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND i.indisvalid"""
TABLES_SQL = "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"


# Read-only catalog verification. Sources come from the checked, immutable v9 SQL,
# not client data. Both function bodies and catalog security attributes are bound.
APPROVAL_GUARD_SQL = """WITH relation AS (
    SELECT pg_catalog.to_regclass('public.approval_requests') AS oid
), attribute AS (
    SELECT a.*, pg_catalog.pg_get_expr(d.adbin, d.adrelid) AS default_expression
    FROM pg_catalog.pg_attribute a
    LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
    WHERE a.attrelid = (SELECT oid FROM relation)
      AND a.attname = 'approval_contract' AND NOT a.attisdropped
), expected(name, arguments, result_type, language, volatility, parallel, source) AS (
    VALUES ('approval_contract_v2_shape', 'contract jsonb', 'boolean', 'sql', 'i', 's',
            CAST(:shape_source AS text)),
           ('approval_contract_v2_immutable', '', 'trigger', 'plpgsql', 'v', 'u',
            CAST(:guard_source AS text))
), functions AS (
    SELECT p.*, l.lanname, e.arguments, e.result_type, e.language,
           e.volatility, e.parallel, e.source
    FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_language l ON l.oid = p.prolang
    JOIN expected e ON e.name = p.proname
    WHERE p.pronamespace = 'public'::regnamespace
)
SELECT
    EXISTS (SELECT 1 FROM pg_catalog.pg_class c
        WHERE c.oid = (SELECT oid FROM relation) AND c.relkind = 'r'
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i
                         WHERE i.inhrelid = c.oid OR i.inhparent = c.oid)) AS table_ok,
    EXISTS (SELECT 1 FROM attribute a
        WHERE a.atttypid = 'jsonb'::regtype AND a.atttypmod = -1
          AND NOT a.attnotnull AND a.attidentity = '' AND a.attgenerated = ''
          AND a.attinhcount = 0 AND a.attislocal
          AND (a.default_expression IS NULL OR a.default_expression = 'NULL::jsonb')) AS column_ok,
    (SELECT count(*) = 2 AND bool_and(
        pg_catalog.pg_get_function_identity_arguments(f.oid) = f.arguments
        AND pg_catalog.pg_get_function_result(f.oid) = f.result_type
        AND f.lanname = f.language AND f.prosrc = f.source
        AND f.prokind = 'f' AND NOT f.prosecdef AND NOT f.proleakproof
        AND NOT f.proisstrict AND NOT f.proretset AND f.provariadic = 0
        AND f.prosupport = 0 AND f.pronargdefaults = 0
        AND f.proargdefaults IS NULL AND f.proallargtypes IS NULL
        AND f.proargmodes IS NULL AND f.probin IS NULL AND f.prosqlbody IS NULL
        AND f.provolatile::text = f.volatility AND f.proparallel::text = f.parallel
        AND f.proconfig IS NOT DISTINCT FROM ARRAY['search_path=pg_catalog']::text[])
        FROM functions f) AS functions_ok,
    EXISTS (SELECT 1 FROM pg_catalog.pg_constraint c
        WHERE c.conrelid = (SELECT oid FROM relation)
          AND c.conname = 'approval_contract_v2_shape_check'
          AND c.contype = 'c' AND c.convalidated
          AND NOT c.condeferrable AND NOT c.condeferred AND c.conislocal
          AND c.coninhcount = 0 AND NOT c.connoinherit AND c.conparentid = 0
          AND c.conkey = ARRAY[(SELECT attnum FROM attribute)]::smallint[]
          AND pg_catalog.pg_get_expr(c.conbin, c.conrelid) IN (
              'public.approval_contract_v2_shape(approval_contract)',
              'approval_contract_v2_shape(approval_contract)')
          AND EXISTS (SELECT 1 FROM pg_catalog.pg_depend d
              WHERE d.classid = 'pg_catalog.pg_constraint'::regclass AND d.objid = c.oid
                AND d.refclassid = 'pg_catalog.pg_proc'::regclass
                AND d.refobjid = pg_catalog.to_regprocedure(
                    'public.approval_contract_v2_shape(jsonb)') AND d.deptype = 'n')) AS check_ok,
    EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t
        WHERE t.tgrelid = (SELECT oid FROM relation)
          AND t.tgname = 'approval_contract_v2_immutable'
          AND t.tgfoid = pg_catalog.to_regprocedure('public.approval_contract_v2_immutable()')
          AND t.tgtype = 17 AND t.tgenabled = 'A' AND NOT t.tgisinternal
          AND t.tgparentid = 0 AND t.tgconstraint = 0
          AND t.tgconstrrelid = 0 AND t.tgconstrindid = 0
          AND NOT t.tgdeferrable AND NOT t.tginitdeferred AND t.tgnargs = 0
          AND t.tgattr::text = '' AND t.tgargs = ''::bytea AND t.tgqual IS NULL
          AND t.tgoldtable IS NULL AND t.tgnewtable IS NULL) AS trigger_ok"""


class SchemaError(RuntimeError):
    """Fixed safe code, never raw database messages or connection values."""


def read_artifact(root: Path, filename: str, checksum: str) -> str:
    relative = Path(filename)
    if relative.is_absolute() or not relative.parts or any(p in ("..", ".") for p in relative.parts):
        raise SchemaError("DB_MANIFEST_PATH_INVALID")
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise SchemaError("DB_MANIFEST_PATH_INVALID")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise SchemaError("DB_MANIFEST_PATH_INVALID")
    data = candidate.read_bytes()
    if hashlib.sha256(data).hexdigest() != checksum:
        raise SchemaError("DB_MANIFEST_CHECKSUM_INVALID")
    return data.decode("utf-8")


def load_manifest(root: Path = DEPLOY) -> dict[str, Any]:
    try:
        path = root / "schema_manifest.json"
        if path.is_symlink():
            raise SchemaError("DB_MANIFEST_PATH_INVALID")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        migrations = manifest["migrations"]
        if manifest["format"] != 1 or not isinstance(migrations, list) or not migrations:
            raise SchemaError("DB_MANIFEST_INVALID")
        filenames: set[str] = set()
        for version, entry in enumerate(migrations, 1):
            if (type(entry["version"]) is not int or entry["version"] != version
                    or not re.fullmatch(r"[a-z][a-z0-9_]*", entry["name"])
                    or entry["file"] in filenames):
                raise SchemaError("DB_MANIFEST_INVALID")
            filenames.add(entry["file"])
            # Execute precisely the bytes that were checked, not a second filesystem read.
            entry["sql"] = read_artifact(root, entry["file"], entry["sha256"])
        seed = manifest["demo_seed"]
        seed["sql"] = read_artifact(root, seed["file"], seed["sha256"])
        for key in ("columns", "legacy_columns", "indexes"):
            if not isinstance(manifest[key], dict) or not manifest[key]:
                raise SchemaError("DB_MANIFEST_INVALID")
        return manifest
    except SchemaError:
        raise
    except Exception:
        raise SchemaError("DB_MANIFEST_INVALID") from None


def check_history(rows: list[Any], manifest: dict[str, Any], *, current: bool) -> int:
    expected = manifest["migrations"]
    if len(rows) > len(expected):
        raise SchemaError("DB_HISTORY_UNKNOWN")
    for index, row in enumerate(rows):
        item = expected[index]
        if tuple(row) != (item["version"], item["name"], item["sha256"]):
            raise SchemaError("DB_HISTORY_MISMATCH")
    if current and len(rows) != len(expected):
        raise SchemaError("DB_SCHEMA_PENDING")
    return len(rows)


def check_structure(columns: list[Any], indexes: list[Any], manifest: dict[str, Any],
                    *, legacy: bool = False) -> None:
    actual = {(row[0], row[1]): row[2:] for row in columns}
    required = manifest["legacy_columns" if legacy else "columns"]
    for table, fields in required.items():
        for name, contract in fields.items():
            value = actual.get((table, name))
            if (value is None or value[0] != contract["type"]
                    or ("length" in contract and value[1] != contract["length"])):
                raise SchemaError("DB_SCHEMA_SHAPE_MISMATCH")
    if not legacy:
        if actual[("users", "password_hash")][2] != "NO":
            raise SchemaError("DB_SCHEMA_SHAPE_MISMATCH")
        existing_indexes = dict(indexes)
        for name, unique in manifest["indexes"].items():
            if name not in existing_indexes or existing_indexes[name] != unique:
                raise SchemaError("DB_SCHEMA_INDEX_MISMATCH")


def approval_guard_parameters(manifest: dict[str, Any]) -> dict[str, str]:
    """Use the reviewed SQL function bodies without executing a migration at startup."""
    entries = [item for item in manifest["migrations"]
               if item["name"] == "approval_contract_provenance"]
    if len(entries) != 1 or entries[0]["version"] != 9:
        raise SchemaError("DB_APPROVAL_CONTRACT_MANIFEST_INVALID")
    params = {}
    for key, delimiter in (("shape_source", "$shape$"), ("guard_source", "$guard$")):
        parts = entries[0]["sql"].split(delimiter)
        if len(parts) != 3:
            raise SchemaError("DB_APPROVAL_CONTRACT_MANIFEST_INVALID")
        params[key] = parts[1]
    return params


def check_approval_guard(row: Any) -> None:
    """A present column is insufficient: missing or altered guards fail closed."""
    if row is None or len(row) != 5 or any(value is not True for value in row):
        raise SchemaError("DB_APPROVAL_CONTRACT_DRIFT")


def verify_sync_approval_guard(connection: Any, manifest: dict[str, Any]) -> None:
    query = APPROVAL_GUARD_SQL.replace(":shape_source", "%(shape_source)s").replace(
        ":guard_source", "%(guard_source)s")
    result = connection.execute(query, approval_guard_parameters(manifest))
    check_approval_guard(result.fetchone())


async def verify_async_schema(connection: Any, text: Any) -> None:
    """Read-only schema gate for SQLAlchemy connections; no implicit migration."""
    manifest = load_manifest()
    try:
        lock = await connection.execute(text(
            "SELECT pg_try_advisory_xact_lock_shared(:lock_id)"), {"lock_id": LOCK_ID})
        if not lock.scalar():
            raise SchemaError("DB_MIGRATION_BUSY")
        result = await connection.execute(text(HISTORY_SQL))
        check_history(result.fetchall(), manifest, current=True)
        columns = await connection.execute(text(COLUMNS_SQL))
        indexes = await connection.execute(text(INDEXES_SQL))
        check_structure(columns.fetchall(), indexes.fetchall(), manifest)
        guards = await connection.execute(text(APPROVAL_GUARD_SQL),
                                          approval_guard_parameters(manifest))
        check_approval_guard(guards.fetchone())
    except SchemaError:
        raise
    except Exception:
        raise SchemaError("DB_SCHEMA_UNAVAILABLE") from None
