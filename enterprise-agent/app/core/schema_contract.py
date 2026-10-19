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
    except SchemaError:
        raise
    except Exception:
        raise SchemaError("DB_SCHEMA_UNAVAILABLE") from None
