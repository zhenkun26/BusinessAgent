"""Explicit PostgreSQL administration. `plan` is offline; no application/model startup."""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any

from app.core.schema_contract import (
    COLUMNS_SQL, HISTORY_SQL, INDEXES_SQL, LOCK_ID, TABLES_SQL,
    SchemaError, check_history, check_structure, load_manifest,
)

LEDGER_SQL = """CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum VARCHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""
SEED_LEDGER_SQL = """CREATE TABLE IF NOT EXISTS public.schema_bootstrap (
    name TEXT PRIMARY KEY, checksum VARCHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""


def begin_operation(conn: Any, *, readonly: bool = False) -> None:
    if not conn.autocommit:
        raise SchemaError("DB_AUTOCOMMIT_REQUIRED")
    if readonly:
        conn.execute("SET TRANSACTION READ ONLY")
    conn.execute("SET LOCAL search_path TO public")
    conn.execute("SET LOCAL statement_timeout = '60s'")
    conn.execute("SET LOCAL lock_timeout = '5s'")
    query = ("SELECT pg_try_advisory_xact_lock_shared(%s)" if readonly
             else "SELECT pg_try_advisory_xact_lock(%s)")
    if not conn.execute(query, (LOCK_ID,)).fetchone()[0]:
        raise SchemaError("DB_MIGRATION_BUSY")


def require_current(conn: Any, manifest: dict[str, Any]) -> None:
    if not conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0]:
        raise SchemaError("DB_SCHEMA_UNINITIALIZED")
    check_history(conn.execute(HISTORY_SQL).fetchall(), manifest, current=True)
    check_structure(conn.execute(COLUMNS_SQL).fetchall(),
                    conn.execute(INDEXES_SQL).fetchall(), manifest)


def apply_migrations(conn: Any, manifest: dict[str, Any], *, adopt_legacy: bool = False) -> dict:
    with conn.transaction():
        begin_operation(conn)
        tables = {row[0] for row in conn.execute(TABLES_SQL).fetchall()}
        rows = (conn.execute(HISTORY_SQL).fetchall() if "schema_migrations" in tables else [])
        applied = check_history(rows, manifest, current=False)
        if not applied and tables - {"schema_migrations", "schema_bootstrap"}:
            if not adopt_legacy:
                raise SchemaError("DB_LEGACY_ADOPTION_REQUIRED")
            check_structure(conn.execute(COLUMNS_SQL).fetchall(), [], manifest, legacy=True)
        conn.execute(LEDGER_SQL)
        conn.execute(SEED_LEDGER_SQL)
        for item in manifest["migrations"][applied:]:
            # No params in reviewed SQL batches; execute without server preparation.
            conn.execute(item["sql"], prepare=False)
            conn.execute(
                "INSERT INTO public.schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                (item["version"], item["name"], item["sha256"]),
            )
        require_current(conn, manifest)
    return {"status": "PASS", "applied_versions": [m["version"]
            for m in manifest["migrations"][applied:]], "version": len(manifest["migrations"])}


def schema_status(conn: Any, manifest: dict[str, Any]) -> dict:
    with conn.transaction():
        begin_operation(conn, readonly=True)
        require_current(conn, manifest)
    return {"status": "PASS", "version": len(manifest["migrations"])}


def bootstrap_admin(conn: Any, manifest: dict[str, Any], user_id: str, username: str,
                    password_hash: str) -> dict:
    if (not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", user_id)
            or not username.strip() or len(username) > 128
            or not re.fullmatch(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}", password_hash)):
        raise SchemaError("DB_ADMIN_INPUT_INVALID")
    with conn.transaction():
        begin_operation(conn)
        require_current(conn, manifest)
        if conn.execute("SELECT 1 FROM public.users WHERE role = 'admin' LIMIT 1").fetchone():
            raise SchemaError("DB_ADMIN_ALREADY_EXISTS")
        conn.execute("""INSERT INTO public.users
            (user_id, username, role, department, password_hash, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, username, "admin", "shared_company", password_hash, True))
    return {"status": "PASS", "admin_created": True}


def seed_demo(conn: Any, manifest: dict[str, Any], password_hash: str) -> dict:
    if not re.fullmatch(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}", password_hash):
        raise SchemaError("DB_DEMO_PASSWORD_INVALID")
    seed = manifest["demo_seed"]
    with conn.transaction():
        begin_operation(conn)
        require_current(conn, manifest)
        prior = conn.execute("SELECT checksum FROM public.schema_bootstrap WHERE name = %s",
                             ("demo-v1",)).fetchone()
        if prior:
            if prior[0] != seed["sha256"]:
                raise SchemaError("DB_SEED_CHECKSUM_MISMATCH")
            return {"status": "PASS", "demo_seeded": False}
        # Static SQL identifiers; values never become SQL syntax.
        populated = conn.execute("""SELECT
            EXISTS(SELECT 1 FROM public.users) OR EXISTS(SELECT 1 FROM public.sessions)
            OR EXISTS(SELECT 1 FROM public.approval_requests) OR EXISTS(SELECT 1 FROM public.audit_logs)
            OR EXISTS(SELECT 1 FROM public.user_memories) OR EXISTS(SELECT 1 FROM public.saga_transactions)
            OR EXISTS(SELECT 1 FROM public.user_feedback) OR EXISTS(SELECT 1 FROM public.documents)
            OR EXISTS(SELECT 1 FROM public.prompt_versions)""").fetchone()[0]
        if populated:
            raise SchemaError("DB_DEMO_REQUIRES_EMPTY_DATASET")
        conn.execute("SELECT set_config('businessagent.demo_password_hash', %s, true)",
                     (password_hash,))
        conn.execute(seed["sql"], prepare=False)
        conn.execute("INSERT INTO public.schema_bootstrap (name, checksum) VALUES (%s, %s)",
                     ("demo-v1", seed["sha256"]))
    return {"status": "PASS", "demo_seeded": True}


def password_from_env(name: str) -> str:
    password = os.environ.get(name, "")
    if len(password) < 12 or not password.strip() or len(password.encode("utf-8")) > 72:
        raise SchemaError("DB_BOOTSTRAP_PASSWORD_INVALID")
    from app.security.password import hash_password

    return hash_password(password)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "status", "apply", "admin", "demo"))
    parser.add_argument("--execute", action="store_true", help="Authorize this database write")
    parser.add_argument("--adopt-legacy", action="store_true")
    parser.add_argument("--allow-demo", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest()
        if args.command == "plan":
            print(json.dumps({"status": "PASS", "offline": True, "migrations": [
                {k: item[k] for k in ("version", "name", "sha256")}
                for item in manifest["migrations"]]}))
            return 0
        if args.command in ("apply", "admin", "demo") and not args.execute:
            raise SchemaError("DB_EXECUTE_FLAG_REQUIRED")
        from app.config import get_settings

        settings = get_settings()
        password_hash = ""
        if args.command == "demo":
            if (not args.allow_demo or settings.app_env != "dev"
                    or settings.tool_provider != "mock"
                    or any(value not in ("", "mock") for value in (
                        settings.crm_tool_provider, settings.mail_tool_provider,
                        settings.ticket_tool_provider))):
                raise SchemaError("DB_DEMO_NOT_ALLOWED")
            password_hash = password_from_env("BOOTSTRAP_DEMO_PASSWORD")
        if args.command == "admin":
            if settings.app_env != "dev" and not settings.auth_require_password:
                raise SchemaError("DB_ADMIN_PASSWORD_AUTH_REQUIRED")
            password_hash = password_from_env("BOOTSTRAP_ADMIN_PASSWORD")
        import psycopg

        with psycopg.connect(host=settings.postgres_host, port=settings.postgres_port,
                             user=settings.postgres_user, password=settings.postgres_password,
                             dbname=settings.postgres_db, autocommit=True, connect_timeout=10,
                             options="-c statement_timeout=60000 -c lock_timeout=5000") as conn:
            if args.command == "apply":
                result = apply_migrations(conn, manifest, adopt_legacy=args.adopt_legacy)
            elif args.command == "status":
                result = schema_status(conn, manifest)
            elif args.command == "admin":
                result = bootstrap_admin(conn, manifest, os.environ.get("BOOTSTRAP_ADMIN_ID", ""),
                                         os.environ.get("BOOTSTRAP_ADMIN_USERNAME", ""), password_hash)
            else:
                result = seed_demo(conn, manifest, password_hash)
        print(json.dumps(result))
        return 0
    except SchemaError as exc:
        print(json.dumps({"status": "BLOCKED", "code": str(exc)}))
        return 2
    except Exception as exc:
        code = ("DB_LEGACY_PASSWORD_MISSING" if getattr(exc, "sqlstate", None) == "PBA01"
                else "DB_OPERATION_FAILED")
        print(json.dumps({"status": "FAIL", "code": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
