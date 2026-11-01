"""Opt-in PostgreSQL acceptance on newly owned synthetic fixture databases only.

Preparation/import/--help never connects. Execution requires --execute, a verified
read-only candidate export, two synthetic credentials and server-side fixture marks.
The orchestrator invokes this once for each fresh/upgrade database. This script
does not create/drop databases, start services, install packages or import app.main.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import socket
import sys
from types import SimpleNamespace
from typing import Any, Iterator
import unittest
from unittest.mock import AsyncMock, Mock, patch
import uuid


APP_ROLE = "ba_approval_fixture"
DDL_ROLE = "ba_approval_ddl"
FIXTURE_MARK = "approval-pg-v1"
PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT.parent
MIGRATION = "deploy/migrations/009_approval_contract_provenance.sql"
MANDATORY = (
    "fixture_identity", "bootstrap", "migration_rollback", "migration_install",
    "migration_repeat", "migration_drift_rejection", "legacy_preservation", "runtime_role", "writer_utc",
    "writer_shanghai", "deadline_boundary", "legacy_payload_hold", "contract_immutable",
    "guard_negative_control", "malformed_contract_insert", "concurrent_claim", "reauth_resume", "commit_ack_lost",
    "outcome_persistence_failure", "payload_drift_cas", "cancellation_hold", "partial_tool_stop",
    "legacy_pagination", "batch_stop", "network_boundary",
)


@dataclass(frozen=True)
class Fixture:
    run_id: str
    database: str
    port: int
    candidate_sha: str
    artifact_dir: Path

    def validate(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", self.run_id):
            raise ValueError("run-id must be UUID hex")
        if uuid.UUID(hex=self.run_id).version != 4:
            raise ValueError("run-id must be a fresh UUID4")
        if self.database not in {f"ba_approval_{self.run_id}_{m}" for m in ("fresh", "upgrade")}:
            raise ValueError("database is not this run's exact fixture")
        if not 1024 <= self.port <= 65535:
            raise ValueError("invalid fixture port")
        if not re.fullmatch(r"[0-9a-f]{40}", self.candidate_sha):
            raise ValueError("candidate-sha must be complete")


def verify_export(root: Path, candidate_sha: str) -> dict[str, Any]:
    """Validate the complete exported bytes before adding the app to sys.path.

    manifest_sha256 names an externally approved manifest; this verifier records
    it, while the orchestrator binds approval and the export-manifest file itself.
    """
    manifest_path = root / "EXPORT-MANIFEST.json"
    if manifest_path.is_symlink():
        raise ValueError("manifest symlink forbidden")
    data = json.loads(manifest_path.read_text())
    if data.get("head") != candidate_sha or not re.fullmatch(r"[0-9a-f]{40}", data.get("tree", "")):
        raise ValueError("export candidate identity mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}", data.get("manifest_sha256", "")):
        raise ValueError("external approval manifest identity missing")
    files = data.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("export file inventory missing")
    for name, digest in files.items():
        path = PurePosixPath(name)
        if (not isinstance(name, str) or path.is_absolute() or str(path) != name
                or any(p in (".", "..", ".git") for p in path.parts)
                or name == "EXPORT-MANIFEST.json"):
            raise ValueError("unsafe export path")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid exported file digest")
        target = root / name
        if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
            raise ValueError("exported file is missing or unsafe")
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("exported bytes changed")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("export symlink forbidden")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(files) | {"EXPORT-MANIFEST.json"}:
        raise ValueError("export contains unmanifested files")
    required = {
        "enterprise-agent/eval/run_approval_pg_acceptance.py",
        "enterprise-agent/app/agents/execution.py", "enterprise-agent/app/api/approval.py",
        "enterprise-agent/app/core/approval_deadline.py",
        "enterprise-agent/app/core/approval_timeout.py", "enterprise-agent/" + MIGRATION,
    }
    if not required <= files.keys():
        raise ValueError("required candidate files missing")
    return {"head": data["head"], "tree": data["tree"],
            "approval_manifest_sha256": data["manifest_sha256"],
            "export_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "files_verified": len(files), "core_hashes": {p: files[p] for p in sorted(required)}}


def password(name: str) -> str:
    value = os.environ.get(name, "")
    if not re.fullmatch(r"[0-9a-f]{32,128}", value):
        raise ValueError("synthetic fixture credential missing or malformed")
    return value


def complete_checks(checks: dict[str, Any]) -> bool:
    return (set(checks) == set(MANDATORY)
            and all(isinstance(item, dict) and item.get("passed") is True for item in checks.values()))


def validate_server(row: Any, fixture: Fixture, role: str) -> None:
    if (row["database"] != fixture.database or row["role"] != role
            or row["fixture"] != FIXTURE_MARK or row["run_id"] != fixture.run_id
            or row["owner"] != DDL_ROLE):
        raise ValueError("server is not the provisioned fixture")
    if any(row[k] for k in ("superuser", "createdb", "createrole", "replication", "bypassrls")):
        raise ValueError("fixture role has forbidden elevated privileges")


@contextmanager
def network_fence(port: int, denied: list[str]) -> Iterator[None]:
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def check(address: Any) -> None:
        if not isinstance(address, tuple) or address[:2] != ("127.0.0.1", port):
            denied.append("non-fixture socket attempt")
            raise PermissionError("only the fixture PostgreSQL socket is allowed")

    def connect(sock: socket.socket, address: Any) -> Any:
        check(address)
        return original(sock, address)

    def connect_ex(sock: socket.socket, address: Any) -> Any:
        check(address)
        return original_ex(sock, address)

    with patch.object(socket.socket, "connect", connect), patch.object(socket.socket, "connect_ex", connect_ex):
        yield


class FaultSession:
    """Delegate actual SQL/transactions; inject only the named transport boundary."""
    def __init__(self, session: Any, mode: str) -> None:
        self.session = session
        self.mode = mode
        self.injected = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.session, name)

    async def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        if (self.mode == "outcome" and not self.injected
                and str(statement).startswith("UPDATE approval_requests SET status = :state")
                and (params or {}).get("state") in {"executed", "execution_unknown"}):
            self.injected = True
            raise ConnectionError("synthetic result-persistence failure")
        return await self.session.execute(statement, params, **kwargs)

    async def commit(self) -> None:
        await self.session.commit()
        if self.mode == "ack" and not self.injected:
            self.injected = True
            raise ConnectionError("synthetic acknowledgment loss AFTER actual COMMIT")


class PreCommitBarrier:
    """Pause before the real claim COMMIT, retaining PostgreSQL locks."""
    def __init__(self, session: Any, entered: asyncio.Event, release: asyncio.Event) -> None:
        self.session, self.entered, self.release = session, entered, release
        self.paused = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.session, name)

    async def commit(self) -> None:
        if not self.paused:
            self.paused = True
            self.entered.set()
            await asyncio.wait_for(self.release.wait(), 10)
        await self.session.commit()


class Acceptance(unittest.IsolatedAsyncioTestCase):
    fixture: Fixture
    report: dict[str, Any]

    async def check(self, name: str, operation: Any) -> None:
        try:
            await operation()
        except BaseException as exc:
            self.report["checks"][name] = {"passed": False, "error_type": type(exc).__name__}
            raise AssertionError(f"mandatory acceptance check failed: {name} ({type(exc).__name__})") from None
        self.report["checks"][name] = {"passed": True}

    async def identity(self, connection: Any, role: str) -> None:
        row = await connection.fetchrow("""SELECT current_database() AS database,
            current_user AS role, current_setting('businessagent.acceptance_fixture', true) AS fixture,
            current_setting('businessagent.acceptance_run_id', true) AS run_id,
            pg_get_userbyid(d.datdba) AS owner, r.rolsuper AS superuser,
            r.rolcreatedb AS createdb, r.rolcreaterole AS createrole,
            r.rolreplication AS replication, r.rolbypassrls AS bypassrls
            FROM pg_database d, pg_roles r
            WHERE d.datname = current_database() AND r.rolname = current_user""")
        validate_server(row, self.fixture, role)

    async def old_rows(self) -> list[Any]:
        return list(await self.ddl.fetch("SELECT approval_id, (to_jsonb(a)-'approval_contract')::text "
                                        "AS body FROM public.approval_requests a ORDER BY approval_id"))

    async def schema_objects(self) -> Any:
        return await self.ddl.fetchrow("""SELECT
            pg_get_functiondef('public.approval_contract_v2_shape(jsonb)'::regprocedure) AS shape,
            pg_get_functiondef('public.approval_contract_v2_immutable()'::regprocedure) AS guard,
            (SELECT pg_get_constraintdef(oid) FROM pg_constraint
             WHERE conrelid='public.approval_requests'::regclass
             AND conname='approval_contract_v2_shape_check' AND convalidated) AS check_definition,
            (SELECT pg_get_triggerdef(oid) FROM pg_trigger
             WHERE tgrelid='public.approval_requests'::regclass
             AND tgname='approval_contract_v2_immutable' AND tgenabled='A') AS trigger_definition""")

    async def bootstrap(self) -> None:
        self.assertEqual(await self.ddl.fetchval("SELECT count(*) FROM pg_class "
            "WHERE relnamespace='public'::regnamespace"), 0, "fixture must start empty")
        self.assertEqual(await self.ddl.fetchval("SELECT count(*) FROM pg_proc "
            "WHERE pronamespace='public'::regnamespace"), 0)
        files = [PROJECT / "deploy/init.sql"]
        for number in range(1, 6):
            matches = list((PROJECT / "deploy/migrations").glob(f"{number:03}_*.sql"))
            self.assertEqual(len(matches), 1)
            files.extend(matches)
        self.assertEqual(list((PROJECT / "deploy/migrations").glob("009_*.sql")), [PROJECT / MIGRATION])
        self.report["schema_hashes"] = {}
        for path in files:
            contents = path.read_bytes()
            self.report["schema_hashes"][path.relative_to(PROJECT).as_posix()] = hashlib.sha256(contents).hexdigest()
            await self.ddl.execute(contents.decode())
        if self.fixture.database.endswith("_upgrade"):
            await self.ddl.execute("""INSERT INTO users(user_id, username, role, password_hash)
                VALUES ('fixture_upgrade_owner','fixture_upgrade_owner','salesperson','synthetic-not-login');
                INSERT INTO sessions(session_id,user_id) VALUES ('fixture_upgrade_session','fixture_upgrade_owner');
                INSERT INTO approval_requests(approval_id,session_id,requester_id,operation_type,
                    risk_level,prefill_payload,approver_roles,status,created_at,expires_at)
                VALUES ('fixture_upgrade_legacy','fixture_upgrade_session','fixture_upgrade_owner',
                    'send_email_external','high','{"deadline_contract":{"version":"utc-human-v2"}}',
                    '["manager"]','pending',CURRENT_TIMESTAMP-INTERVAL '2 days',
                    CURRENT_TIMESTAMP-INTERVAL '1 day')""")
        self.legacy_before = await self.old_rows()
        self.assertTrue(self.legacy_before)
        self.migration_sql = (PROJECT / MIGRATION).read_text()
        self.report["schema_hashes"][MIGRATION] = hashlib.sha256(self.migration_sql.encode()).hexdigest()

    async def migration_rollback(self) -> None:
        self.assertEqual(len(re.findall(r"(?m)^COMMIT;\s*$", self.migration_sql)), 1)
        broken = re.sub(r"(?m)^COMMIT;\s*$", "SELECT 1 / 0;\nCOMMIT;", self.migration_sql)
        with self.assertRaises(self.asyncpg.PostgresError):
            await self.ddl.execute(broken)
        await self.ddl.execute("ROLLBACK")
        self.assertEqual(await self.ddl.fetchval("SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='approval_requests' AND column_name='approval_contract'"), 0)
        self.assertEqual(await self.ddl.fetchval("SELECT count(*) FROM pg_proc WHERE "
            "pronamespace='public'::regnamespace AND proname LIKE 'approval_contract_v2_%'"), 0)
        self.assertEqual(await self.old_rows(), self.legacy_before)

    async def migration_install(self) -> None:
        await self.ddl.execute(self.migration_sql)
        objects = await self.schema_objects()
        self.assertTrue(all(objects.values()))
        self.assertTrue(await self.ddl.fetchval("SELECT public.approval_contract_v2_shape(NULL)"))
        self.assertFalse(await self.ddl.fetchval("SELECT public.approval_contract_v2_shape('{}'::jsonb)"))
        self.assertIsNone(await self.ddl.fetchval("SELECT approval_contract FROM public.approval_requests LIMIT 1"))

    async def migration_repeat(self) -> None:
        before = await self.schema_objects()
        await self.ddl.execute(self.migration_sql)
        self.assertEqual(before, await self.schema_objects())

    async def migration_drift_rejection(self) -> None:
        # Only outer transaction delimiters are adapted, preserving the actual
        # migration body. Even a faulty migration cannot COMMIT a damaged fixture.
        self.assertEqual(len(re.findall(r"(?m)^BEGIN;\s*$", self.migration_sql)), 1)
        scoped = re.sub(r"(?m)^BEGIN;\s*$", "SAVEPOINT approval_fixture_candidate;", self.migration_sql)
        scoped = re.sub(r"(?m)^COMMIT;\s*$", "RELEASE SAVEPOINT approval_fixture_candidate;", scoped)
        original = await self.schema_objects()
        cases = (
            ("missing_trigger", "DROP TRIGGER approval_contract_v2_immutable ON public.approval_requests",
             "APPROVAL_CONTRACT_TRIGGER_DRIFT"),
            ("partial_installation", "ALTER TABLE public.approval_requests DROP COLUMN approval_contract CASCADE",
             "APPROVAL_CONTRACT_PARTIAL_INSTALLATION"),
            ("weakened_guard", "CREATE OR REPLACE FUNCTION public.approval_contract_v2_immutable() "
             "RETURNS trigger LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE CALLED ON NULL INPUT "
             "SECURITY INVOKER SET search_path TO pg_catalog AS 'BEGIN RETURN NEW; END'",
             "APPROVAL_CONTRACT_FUNCTION_DRIFT"),
        )
        for label, mutation, expected in cases:
            transaction = self.ddl.transaction()
            await transaction.start()
            try:
                await self.ddl.execute(mutation)
                drifted = await self.schema_objects()
                rows = await self.old_rows()
                with self.assertRaises(self.asyncpg.PostgresError) as caught:
                    await self.ddl.execute(scoped)
                self.assertIn(expected, str(caught.exception))
                await self.ddl.execute("ROLLBACK TO SAVEPOINT approval_fixture_candidate")
                self.assertEqual(await self.schema_objects(), drifted, label)
                self.assertEqual(await self.old_rows(), rows, label)
            finally:
                await transaction.rollback()
            self.assertEqual(await self.schema_objects(), original)
            self.assertEqual(await self.old_rows(), self.legacy_before)

    async def legacy_preservation(self) -> None:
        self.assertEqual(self.legacy_before, await self.old_rows())
        self.assertEqual(await self.ddl.fetchval("SELECT count(*) FROM approval_requests "
                                               "WHERE approval_contract IS NOT NULL"), 0)

    async def runtime_role(self) -> None:
        await self.ddl.execute("""REVOKE ALL ON SCHEMA public FROM PUBLIC;
            GRANT USAGE ON SCHEMA public TO ba_approval_fixture;
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ba_approval_fixture;
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ba_approval_fixture;
            GRANT EXECUTE ON FUNCTION public.approval_contract_v2_shape(jsonb) TO ba_approval_fixture;
            GRANT EXECUTE ON FUNCTION public.approval_contract_v2_immutable() TO ba_approval_fixture""")
        app = await self.connect(APP_ROLE, "BA_APPROVAL_PG_PASSWORD")
        try:
            await self.identity(app, APP_ROLE)
            self.assertFalse(await app.fetchval("SELECT has_schema_privilege(current_user,'public','CREATE')"))
            self.assertEqual(await app.fetchval("SELECT count(*) FROM pg_auth_members "
                "WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)"), 0)
            with self.assertRaises(self.asyncpg.InsufficientPrivilegeError):
                await app.execute("ALTER TABLE approval_requests DISABLE TRIGGER approval_contract_v2_immutable")
        finally:
            await app.close()

    async def connect(self, role: str, variable: str) -> Any:
        return await self.asyncpg.connect(host="127.0.0.1", port=self.fixture.port,
            database=self.fixture.database, user=role, password=password(variable), ssl=False,
            timeout=10, command_timeout=60, server_settings={"application_name": "approval-pg-acceptance"})

    def configure_application(self, stack: ExitStack) -> None:
        from sqlalchemy import URL, text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool
        from app import config
        # Explicit settings avoid .env and inherited provider/credential settings.
        settings = config.Settings.model_construct(**{
            name: field.default for name, field in config.Settings.model_fields.items()})
        settings.jwt_secret_key = secrets.token_hex(32)
        settings.jwt_algorithm = "HS256"
        settings.tool_provider = settings.mail_tool_provider = "mock"
        settings.crm_tool_provider = settings.ticket_tool_provider = "mock"
        settings.openai_api_key = settings.cohere_api_key = ""
        settings.mail_api_token = settings.crm_api_token = settings.ticket_api_token = ""
        settings.mail_api_base = settings.crm_api_base = settings.ticket_api_base = ""
        settings.postgres_host, settings.postgres_port = "127.0.0.1", self.fixture.port
        settings.postgres_user, settings.postgres_db = APP_ROLE, self.fixture.database
        settings.postgres_password = password("BA_APPROVAL_PG_PASSWORD")
        settings.redis_password = settings.milvus_password = ""
        settings.vector_store_provider = "memory"
        stack.enter_context(patch.object(config, "get_settings", lambda: settings))
        from app.observability import audit
        audit_sink = SimpleNamespace(log=AsyncMock(), log_tool_call=AsyncMock(), log_violation=AsyncMock())
        stack.enter_context(patch.object(audit, "get_audit_logger", lambda: audit_sink))
        from app.agents import execution
        from app.api import approval
        from app.core import approval_deadline, approval_timeout, database
        from app.security.jwt_manager import JWTManager
        from app.tools import base, mail
        self.assertEqual(approval_deadline.VERSION, "utc-human-v2")
        self.assertTrue(callable(approval_deadline.build_contract))
        self.api, self.execution, self.deadline, self.timeout = approval, execution, approval_deadline, approval_timeout
        self.text, self.ToolResult = text, base.ToolResult
        self.jwt = JWTManager()
        stack.enter_context(patch.object(approval, "get_jwt_manager", lambda: self.jwt))
        stack.enter_context(patch.object(approval, "notify_approval_result", AsyncMock()))
        stack.enter_context(patch.object(approval_timeout, "notify_approval_result", AsyncMock()))
        stack.enter_context(patch.object(execution, "get_lite_llm", Mock(side_effect=AssertionError("LLM forbidden"))))
        tool = mail.SendEmailExternalTool()
        tool.provider_override = "mock"
        stack.enter_context(patch.object(tool, "_execute", self.effect))
        stack.enter_context(patch.object(tool, "_call_external", AsyncMock(side_effect=AssertionError("HTTP forbidden"))))
        stack.enter_context(patch.object(base, "_tool_registry", {tool.name: tool}))
        stack.enter_context(patch.object(execution, "_ensure_tools", lambda: None))
        self.engines, self.factories = [], {}
        for zone in ("UTC", "Asia/Shanghai"):
            url = URL.create("postgresql+asyncpg", username=APP_ROLE,
                password=password("BA_APPROVAL_PG_PASSWORD"), host="127.0.0.1",
                port=self.fixture.port, database=self.fixture.database)
            engine = create_async_engine(url, poolclass=NullPool, connect_args={"ssl": False,
                "server_settings": {"timezone": zone, "application_name": "approval-pg-acceptance"}})
            self.engines.append(engine)
            self.factories[zone] = async_sessionmaker(engine, expire_on_commit=False)
        self.factory = self.factories["UTC"]
        stack.enter_context(patch.object(database, "get_session_factory", lambda: self.factory))
        self.agent = execution.ExecutionAgent(execution.AgentRole.SALESPERSON, llm=object())
        self.effects: list[str] = []
        self.effect_mode = "success"
        self.partial_baseline = 0
        self.entered, self.release = asyncio.Event(), asyncio.Event()

    async def effect(self, params: dict[str, Any], context: dict[str, Any]) -> Any:
        self.assertTrue(self.deadline.in_approval_dispatch())
        self.effects.append(context["approval_id"])
        if self.effect_mode == "barrier":
            self.entered.set()
            await asyncio.wait_for(self.release.wait(), 10)
        if self.effect_mode == "payload_drift":
            # Synthetic concurrent DB fault after the committed claim, before the
            # actual handler's result CAS. The immutable contract is NOT changed.
            async with self.factory() as db:
                row = await self.deadline.load(db, context["approval_id"])
                payload = json.loads(self.deadline.canonical(self.deadline.payload(row)))
                payload["tool_calls"][0]["params"]["body"] = "Synthetic concurrent payload drift"
                await db.execute(self.text("UPDATE approval_requests SET prefill_payload=CAST(:payload AS JSONB) "
                    "WHERE approval_id=:id"), {"payload": self.deadline.canonical(payload),
                                               "id": context["approval_id"]})
                await db.commit()
        failed = self.effect_mode == "unknown" or (
            self.effect_mode == "partial" and len(self.effects) - self.partial_baseline == 2)
        return self.ToolResult(success=not failed, tool_name="send_email_external",
            output={"message_id": "fixture-only-receipt"},
            error="fixture unknown outcome" if failed else None)

    async def participants(self) -> tuple[Any, Any]:
        prefix = "fixture_" + uuid.uuid4().hex[:16]
        owner = SimpleNamespace(user_id=prefix + "_owner", role="salesperson")
        manager = SimpleNamespace(user_id=prefix + "_manager", role="manager")
        async with self.factory() as db:
            for person in (owner, manager):
                await db.execute(self.text("INSERT INTO users(user_id,username,role,department,password_hash) "
                    "VALUES (:id,:id,:role,'shared_company','synthetic-not-login')"),
                    {"id": person.user_id, "role": person.role})
            await db.commit()
        return owner, manager

    def token(self, owner: Any, *, expired: bool = False) -> str:
        return self.jwt.encode({"sub": owner.user_id, "role": owner.role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=-1 if expired else 2)})

    def plans(self) -> list[Any]:
        return [self.execution.ToolCallPlan(tool="send_email_external", params={
            "to": ["recipient@example.invalid"], "subject": "Synthetic acceptance",
            "body": "Synthetic fixture only; no delivery."})]

    async def create(self, owner: Any, *, expired_token: bool = False) -> str:
        return await self.agent._create_approval_request(self.plans(), {
            "user_id": owner.user_id, "role": owner.role, "jwt_token": self.token(owner, expired=expired_token)},
            "Synthetic approval acceptance")

    async def row(self, aid: str) -> Any:
        async with self.factory() as db:
            return await self.deadline.load(db, aid)

    async def decide(self, aid: str, manager: Any, db: Any = None) -> Any:
        req = self.api.ApprovalDecisionRequest(decision="approved")
        if db is not None:
            return await self.api.decide_approval(aid, req, manager, db)
        async with self.factory() as session:
            return await self.api.decide_approval(aid, req, manager, session)

    async def expect_http(self, operation: Any, status: int, detail: str | None = None) -> None:
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught:
            await operation
        self.assertEqual(caught.exception.status_code, status)
        if detail is not None:
            self.assertEqual(caught.exception.detail, detail)

    async def insert_fixture(self, owner: Any, *, aid: str | None = None,
                             expired: bool = False, trusted: bool = True) -> str:
        """Only test setup uses INSERT; deadline mutation of existing contracts is forbidden."""
        aid = aid or "fixture_" + uuid.uuid4().hex
        async with self.factory() as db:
            now = (await db.execute(self.text("SELECT clock_timestamp() AT TIME ZONE 'UTC'"))).scalar_one()
            expires = now if expired else now + timedelta(hours=24)
            created = expires - timedelta(hours=24)
            payload = {"tool_calls": [p.model_dump() for p in self.plans()]}
            row = SimpleNamespace(approval_id=aid, session_id="session_" + uuid.uuid4().hex,
                requester_id=owner.user_id, operation_type="send_email_external", risk_level="high",
                created_at=created, expires_at=expires, approver_roles=["manager", "admin"],
                prefill_payload=payload)
            contract = self.deadline.build_contract(row)
            if not trusted:
                payload["deadline_contract"] = contract  # Fully plausible model/client forgery remains untrusted.
            await db.execute(self.text("INSERT INTO sessions(session_id,user_id) VALUES (:sid,:uid)"),
                             {"sid": row.session_id, "uid": owner.user_id})
            await db.execute(self.text("INSERT INTO approval_requests(approval_id,session_id,requester_id,"
                "operation_type,risk_level,prefill_payload,approver_roles,status,requester_token,created_at,"
                "expires_at,approval_contract) VALUES (:id,:sid,:uid,'send_email_external','high',"
                "CAST(:payload AS JSONB),'[\"manager\",\"admin\"]','pending',:token,:created,:expires,"
                "CAST(:contract AS JSONB))"), {"id": aid, "sid": row.session_id, "uid": owner.user_id,
                "payload": self.deadline.canonical(payload), "token": self.token(owner), "created": created,
                "expires": expires, "contract": self.deadline.canonical(contract) if trusted else None})
            await db.commit()
        return aid

    async def writer(self, zone: str) -> None:
        self.factory = self.factories[zone]
        try:
            owner, _ = await self.participants()
            async with self.factory() as db:
                self.assertEqual((await db.execute(self.text("SHOW timezone"))).scalar_one(), zone)
                before = (await db.execute(self.text("SELECT clock_timestamp() AT TIME ZONE 'UTC'"))).scalar_one()
            aid = await self.create(owner)
            row = await self.row(aid)
            async with self.factory() as db:
                after = (await db.execute(self.text("SELECT clock_timestamp() AT TIME ZONE 'UTC'"))).scalar_one()
            self.assertLessEqual(before, row.created_at)
            self.assertLessEqual(row.created_at, after)
            self.assertEqual(row.expires_at - row.created_at, timedelta(hours=24))
            self.assertIsNone(row.created_at.tzinfo)
            self.assertTrue(self.deadline.verified(row))
            self.assertEqual(self.deadline.contract(row)["version"], "utc-human-v2")
            self.assertNotIn("deadline_contract", self.deadline.payload(row))
        finally:
            self.factory = self.factories["UTC"]

    async def deadline_boundary(self) -> None:
        owner, manager = await self.participants()
        aid = await self.insert_fixture(owner, expired=True)
        before = len(self.effects)
        await self.expect_http(self.decide(aid, manager), 409, "APPROVAL_EXPIRED")
        self.assertEqual(len(self.effects), before)
        self.assertEqual((await self.row(aid)).status, "pending")
        await self.timeout.scan_expired_approvals()
        self.assertEqual((await self.row(aid)).status, "timeout")
        # This is at-or-before server now, not a claim of freezing clock_timestamp().

    async def legacy_payload_hold(self) -> None:
        owner, manager = await self.participants()
        aid = await self.insert_fixture(owner, trusted=False, expired=True)
        self.legacy_id = aid
        before = await self.row(aid)
        await self.expect_http(self.decide(aid, manager), 409, self.deadline.HOLD)
        await self.expect_http(self.create(owner), 409, self.deadline.HOLD)
        await self.timeout.scan_expired_approvals()
        self.assertEqual(tuple(await self.row(aid)), tuple(before))
        self.assertIsNone(self.deadline.contract(before))
        self.assertTrue(self.deadline.review_fields(before)["human_review_required"])

    async def contract_immutable(self) -> None:
        from sqlalchemy.exc import DBAPIError
        row = await self.row(self.legacy_id)
        value = self.deadline.build_contract(row)
        self.guard_value = self.deadline.canonical(value)
        for aid, contract in ((self.legacy_id, self.guard_value),):
            async with self.factory() as db:
                with self.assertRaises(DBAPIError) as caught:
                    await db.execute(self.text("UPDATE approval_requests SET approval_contract=CAST(:value AS JSONB) "
                        "WHERE approval_id=:id"), {"value": contract, "id": aid})
                self.assertEqual(getattr(caught.exception.orig, "sqlstate", None), "23514")
                await db.rollback()
            self.assertIsNone(self.deadline.contract(await self.row(aid)))
        owner, _ = await self.participants()
        aid = await self.create(owner)
        before = await self.row(aid)
        replacement = dict(self.deadline.contract(before), risk_level="medium")
        for value in (None, self.deadline.canonical(replacement)):
            async with self.factory() as db:
                with self.assertRaises(DBAPIError) as caught:
                    await db.execute(self.text("UPDATE approval_requests SET approval_contract=CAST(:value AS JSONB) "
                        "WHERE approval_id=:id"), {"id": aid, "value": value})
                self.assertEqual(getattr(caught.exception.orig, "sqlstate", None), "23514")
                await db.rollback()
            self.assertEqual(tuple(await self.row(aid)), tuple(before))

    async def guard_negative_control(self) -> None:
        transaction = self.ddl.transaction()
        await transaction.start()
        try:
            await self.ddl.execute("ALTER TABLE public.approval_requests DISABLE TRIGGER approval_contract_v2_immutable")
            self.assertEqual(await self.ddl.execute("UPDATE public.approval_requests SET approval_contract=$1::jsonb "
                "WHERE approval_id=$2", self.guard_value, self.legacy_id), "UPDATE 1")
            self.assertIsNotNone(await self.ddl.fetchval("SELECT approval_contract FROM approval_requests WHERE approval_id=$1", self.legacy_id))
        finally:
            await transaction.rollback()
        self.assertIsNone(self.deadline.contract(await self.row(self.legacy_id)))
        self.assertEqual(await self.ddl.fetchval("SELECT tgenabled FROM pg_trigger WHERE "
            "tgrelid='public.approval_requests'::regclass AND tgname='approval_contract_v2_immutable'"), "A")
        self.report["negative_controls"] = {"guard_disabled_upgrade_succeeds_then_rolled_back": True}

    async def malformed_contract_insert(self) -> None:
        from sqlalchemy.exc import DBAPIError
        owner, _ = await self.participants()
        source = await self.create(owner)
        for value in ("null", "{}", "[]", "1", '{"version":"utc-human-v2"}'):
            aid = "fixture_bad_" + uuid.uuid4().hex
            async with self.factory() as db:
                with self.assertRaises(DBAPIError) as caught:
                    await db.execute(self.text("INSERT INTO approval_requests(approval_id,session_id,requester_id,"
                        "operation_type,risk_level,prefill_payload,approver_roles,status,created_at,expires_at,"
                        "approval_contract) SELECT :id,session_id,requester_id,operation_type,risk_level,"
                        "prefill_payload,approver_roles,'pending',created_at,expires_at,CAST(:value AS JSONB) "
                        "FROM approval_requests WHERE approval_id=:source"),
                        {"id": aid, "value": value, "source": source})
                self.assertEqual(getattr(caught.exception.orig, "sqlstate", None), "23514")
                await db.rollback()
            self.assertIsNone(await self.row(aid))

    async def concurrent_claim(self) -> None:
        from fastapi import HTTPException
        owner, manager = await self.participants()
        aid = await self.create(owner)
        before = len(self.effects)
        entered, release = asyncio.Event(), asyncio.Event()
        async with self.factory() as first_db, self.factory() as second_db:
            holder = (await first_db.execute(self.text("SELECT pg_backend_pid()"))).scalar_one()
            waiter = (await second_db.execute(self.text("SELECT pg_backend_pid()"))).scalar_one()
            self.assertNotEqual(holder, waiter)
            tasks = [asyncio.create_task(self.decide(aid, manager,
                                                    PreCommitBarrier(first_db, entered, release)))]
            try:
                await asyncio.wait_for(entered.wait(), 5)
                tasks.append(asyncio.create_task(self.decide(aid, manager, second_db)))

                async def observe_blocking() -> list[int]:
                    async with self.factory() as observer:
                        while True:
                            blockers = (await observer.execute(
                                self.text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter})).scalar_one()
                            if holder in blockers:
                                return list(blockers)
                            self.assertFalse(tasks[1].done(), "second claim did not block")
                            await asyncio.sleep(0.01)  # Poll real lock evidence; never infer it from delay.

                blockers = await asyncio.wait_for(observe_blocking(), 5)
                self.assertEqual(len(self.effects), before)
                self.report["concurrent_claim_lock_evidence"] = {
                    "holder_pid": holder, "waiter_pid": waiter, "blocking_pids": blockers,
                    "phase": "before_actual_claim_commit", "independent_sessions": True}
            finally:
                release.set()
                try:
                    outcomes = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
                except BaseException:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    raise
        self.assertEqual(outcomes[0].status, "executed")
        self.assertIsInstance(outcomes[1], HTTPException)
        self.assertEqual(outcomes[1].status_code, 409)
        self.assertEqual(self.effects[before:], [aid])
        self.assertEqual((await self.row(aid)).status, "executed")

    async def reauth_resume(self) -> None:
        from fastapi.security import HTTPAuthorizationCredentials
        owner, manager = await self.participants()
        aid = await self.create(owner, expired_token=True)
        original = await self.row(aid)
        self.assertEqual((await self.decide(aid, manager)).status, "approved_pending_reauth")
        waiting = await self.row(aid)
        self.assertEqual(waiting.expires_at, original.expires_at)
        async with self.factory() as db:
            result = await self.api.resume_pending_execution(aid, owner,
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=self.token(owner)), db)
        self.assertEqual(result.status, "executed")
        self.assertEqual((await self.row(aid)).expires_at, original.expires_at)

    async def persistence_fault(self, mode: str) -> None:
        owner, manager = await self.participants()
        aid = await self.create(owner)
        before = len(self.effects)
        async with self.factory() as real:
            wrapped = FaultSession(real, mode)
            await self.expect_http(self.decide(aid, manager, wrapped), 503)
            self.assertTrue(wrapped.injected)
        self.assertEqual((await self.row(aid)).status, "executing")
        expected = 0 if mode == "ack" else 1
        self.assertEqual(len(self.effects) - before, expected)
        await self.expect_http(self.decide(aid, manager), 409, self.deadline.HOLD)
        await self.expect_http(self.create(owner), 409, self.deadline.HOLD)
        self.assertEqual(len(self.effects) - before, expected)

    async def legacy_pagination(self) -> None:
        owner, _ = await self.participants()
        legacy = []
        for index in range(105):
            legacy.append(await self.insert_fixture(owner, aid=f"fixture_legacy_{self.fixture.run_id}_{index:03}",
                                                    expired=True, trusted=False))
        trusted_owner, _ = await self.participants()
        trusted = await self.insert_fixture(trusted_owner, aid="zz_fixture_" + self.fixture.run_id, expired=True)
        self.assertEqual(await self.timeout.scan_expired_approvals(), 1)
        self.assertEqual((await self.row(trusted)).status, "timeout")
        for aid in legacy:
            self.assertEqual((await self.row(aid)).status, "pending")
        self.assertEqual(await self.timeout.scan_expired_approvals(), 0)

    async def payload_drift_cas(self) -> None:
        owner, manager = await self.participants()
        aid = await self.create(owner)
        original = await self.row(aid)
        before = len(self.effects)
        self.effect_mode = "payload_drift"
        try:
            await self.expect_http(self.decide(aid, manager), 503,
                                   "APPROVAL_RESULT_UNCONFIRMED_NO_RETRY")
        finally:
            self.effect_mode = "success"
        current = await self.row(aid)
        self.assertEqual(current.status, "executing")
        self.assertEqual(self.deadline.contract(current), self.deadline.contract(original))
        self.assertNotEqual(self.deadline.payload(current), self.deadline.payload(original))
        self.assertFalse(self.deadline.verified(current))
        self.assertEqual(self.effects[before:], [aid])
        await self.expect_http(self.decide(aid, manager), 409, self.deadline.HOLD)
        self.assertEqual(self.effects[before:], [aid])

    async def cancellation_hold(self) -> None:
        owner, manager = await self.participants()
        aid = await self.create(owner)
        before = len(self.effects)
        self.effect_mode = "barrier"
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        task = asyncio.create_task(self.decide(aid, manager))
        try:
            await asyncio.wait_for(self.entered.wait(), 5)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            self.release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.effect_mode = "success"
        self.assertEqual((await self.row(aid)).status, "executing")
        await self.expect_http(self.decide(aid, manager), 409, self.deadline.HOLD)
        self.assertEqual(self.effects[before:], [aid])

    async def partial_tool_stop(self) -> None:
        owner, manager = await self.participants()
        plans = [self.plans()[0] for _ in range(3)]
        for index, plan in enumerate(plans):
            plan.params["body"] = f"Synthetic step {index}"
        aid = await self.agent._create_approval_request(plans, {
            "user_id": owner.user_id, "role": owner.role, "jwt_token": self.token(owner)},
            "Synthetic multi-step acceptance")
        self.partial_baseline = len(self.effects)
        self.effect_mode = "partial"
        try:
            result = await self.decide(aid, manager)
        finally:
            self.effect_mode = "success"
        self.assertEqual(result.status, "execution_unknown")
        self.assertEqual(self.effects[self.partial_baseline:], [aid, aid])
        await self.expect_http(self.decide(aid, manager), 409, self.deadline.HOLD)
        self.assertEqual(self.effects[self.partial_baseline:], [aid, aid])

    async def batch_stop(self) -> None:
        owner, manager = await self.participants()
        first, second = await self.create(owner), await self.create(owner)
        before = len(self.effects)
        self.effect_mode = "unknown"
        try:
            request = self.api.BatchApprovalRequest(approvals=[
                {"approval_id": aid, "decision": "approved"} for aid in (first, second)])
            async with self.factory() as db:
                result = await self.api.batch_decide_approvals(request, manager, db)
        finally:
            self.effect_mode = "success"
        self.assertEqual(result.results[1]["error"], "NOT_ATTEMPTED_HUMAN_REVIEW_REQUIRED")
        self.assertEqual(self.effects[before:], [first])
        self.assertEqual((await self.row(first)).status, "execution_unknown")
        self.assertEqual((await self.row(second)).status, "pending")

    async def test_postgresql_acceptance(self) -> None:
        import asyncpg
        self.asyncpg = asyncpg
        denied: list[str] = []
        self.engines = []
        with network_fence(self.fixture.port, denied), ExitStack() as stack:
            self.ddl = await self.connect(DDL_ROLE, "BA_APPROVAL_PG_DDL_PASSWORD")
            try:
                await self.check("fixture_identity", lambda: self.identity(self.ddl, DDL_ROLE))
                for name in ("bootstrap", "migration_rollback", "migration_install", "migration_repeat", "migration_drift_rejection",
                             "legacy_preservation", "runtime_role"):
                    await self.check(name, getattr(self, name))
                self.configure_application(stack)
                await self.check("writer_utc", lambda: self.writer("UTC"))
                await self.check("writer_shanghai", lambda: self.writer("Asia/Shanghai"))
                for name in ("deadline_boundary", "legacy_payload_hold", "contract_immutable",
                             "guard_negative_control", "malformed_contract_insert", "concurrent_claim", "reauth_resume"):
                    await self.check(name, getattr(self, name))
                await self.check("commit_ack_lost", lambda: self.persistence_fault("ack"))
                await self.check("outcome_persistence_failure", lambda: self.persistence_fault("outcome"))
                await self.check("payload_drift_cas", self.payload_drift_cas)
                await self.check("cancellation_hold", self.cancellation_hold)
                await self.check("partial_tool_stop", self.partial_tool_stop)
                await self.check("legacy_pagination", self.legacy_pagination)
                await self.check("batch_stop", self.batch_stop)
                self.assertFalse(denied)
                self.report["checks"]["network_boundary"] = {"passed": True, "denied_attempts": 0}
            finally:
                for engine in self.engines:
                    await engine.dispose()
                await self.ddl.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly authorize fixture connections for this invocation")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("preparation only: --execute is required; no database connection attempted")
    fixture = Fixture(args.run_id, args.database, args.port, args.candidate_sha, args.artifact_dir)
    try:
        fixture.validate()
        export = verify_export(REPOSITORY, fixture.candidate_sha)
        password("BA_APPROVAL_PG_PASSWORD")
        password("BA_APPROVAL_PG_DDL_PASSWORD")
        if fixture.artifact_dir.resolve().is_relative_to(REPOSITORY):
            raise ValueError("artifacts cannot modify the candidate export")
        fixture.artifact_dir.mkdir(parents=True, exist_ok=True)
        report_path = fixture.artifact_dir / "result.json"
        if report_path.exists():
            raise ValueError("refusing stale acceptance report")
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print("APPROVAL_PG_ACCEPTANCE_REFUSED:" + type(exc).__name__, file=sys.stderr)
        return 2
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(PROJECT))  # Only after the full source export was verified.
    report: dict[str, Any] = {"passed": False, "run_id": fixture.run_id,
        "database": fixture.database, "candidate_sha": fixture.candidate_sha,
        "scope": "core_application_and_schema", "required_checks": list(MANDATORY),
        "source": export, "checks": {}, "not_covered": [
            "HTTP authentication/dependency routing (handlers receive synthetic authenticated users)",
            "Real provider delivery, LLM, Redis, production deployment, cross-process crash recovery",
            "An exact frozen clock_timestamp microsecond (boundary is at-or-before actual server time)",
            "DST zones and deliberately long-open transaction clock behavior",
            "Concurrent creation/direct-action owner holds (claim contention is tested)",
            "Process termination during a provider effect (task cancellation is tested)",
            "Exhaustive malformed JSON shapes and every possible catalog drift (representative cases tested)",
            "Audit-write failure injection (actual transition/outcome audit SQL otherwise remains active)",
        ]}
    Acceptance.fixture, Acceptance.report = fixture, report
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite([Acceptance("test_postgresql_acceptance")]))
    for name in MANDATORY:
        report["checks"].setdefault(name, {"passed": False, "error_type": "NOT_EXECUTED"})
    report["passed"] = (result.wasSuccessful() and not result.skipped
                        and complete_checks(report["checks"]))
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if report["passed"]:
        print("APPROVAL_PG_ACCEPTANCE_COMPLETED:" + fixture.database)
        return 0
    print("APPROVAL_PG_ACCEPTANCE_FAILED:" + fixture.database)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
