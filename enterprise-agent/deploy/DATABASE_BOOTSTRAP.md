# Database migrations and bootstrap

Status (2026-10-17): C03 implementation and offline checks only. Real PostgreSQL,
Linux deployment and login acceptance remain **BLOCKED**. Commands below are an
operator runbook for a separately authorized isolated target; none were run against
the current database. C02 paid API tests remain blocked independently.

## Contract and prerequisites

Use the same reviewed application commit and image digest for the migration job,
API and worker. PostgreSQL 16 is the Compose target. The CLI uses the already
declared psycopg and bcrypt dependencies; production libpq5 was approved in C02.
For host development, use the project's installed environment and run commands
from `enterprise-agent/`. `plan` needs only Python 3.11+ and never loads application
settings or database drivers. All other commands read the existing `POSTGRES_*`
settings and require a reachable, explicitly selected database.

`schema_manifest.json` pins ordered migrations and SHA-256 hashes. Managed version
1 is the schema-only `init.sql` (nine application tables); old `migrations/001`–`005`
files are historical references and are never discovered or executed by this runner.
In particular, their historical shared-password backfills are not part of C03.
Do not run SQL files manually or mix the old scripts with the managed entry point.

Managed v2 adds retained tool executions/operations; v3 adds `task_jobs` and
`task_consumers` for transactional publication and worker progress. API/worker startup
requires all three versions. No migration is applied implicitly; C14 real migration
acceptance is still BLOCKED. Do not run a v2 application against v3 history.

`schema_migrations` records version, name, checksum and application time.
`schema_bootstrap` records one-time demo seeding. Applied migrations are immutable:
add a new ordered manifest entry and reviewed SQL file for later schema changes,
then update the expected schema contract. Never edit a stored checksum to silence drift.
This is a PostgreSQL-specific runner, not an Alembic dependency or a generic ORM diff tool.

## Offline preview

```bash
python -B -m app.core.db_bootstrap plan
```

Expected: safe JSON with `offline=true`, versions and hashes. This verifies packaged
bytes only; it does not parse PostgreSQL SQL, inspect a server or establish readiness.
Mutating commands without `--execute` stop before importing settings or connecting.
`status` is read-only but does connect; it is not an offline check.

## Empty target and legacy-copy upgrade

Before an authorized run, record target identity, candidate commit/image digest and
database snapshot identity without credentials. Quiesce API/worker and other writers.
Check privileges for schema/sequence creation and alteration; use an operator account
appropriate to the isolated target. Runtime least-privilege separation is still future work.

```bash
# Empty isolated PostgreSQL database only; no model startup or calls.
python -B -m app.core.db_bootstrap apply --execute
python -B -m app.core.db_bootstrap status
# Repeat apply: PASS with applied_versions=[] and unchanged business rows.
python -B -m app.core.db_bootstrap apply --execute
```

For an authorized restored legacy copy, replace the first command with:

```bash
python -B -m app.core.db_bootstrap apply --execute --adopt-legacy
```

Nonempty unversioned databases require this explicit flag and the known legacy
table/column/type contract. The baseline adds supported document, prompt and SSO
schema objects. Unknown history, partial schemas, incompatible types or widths,
missing passwords and uniqueness conflicts stop the operation; it never overwrites
accounts, invents passwords or repairs business data. Empty/NULL passwords produce
`DB_LEGACY_PASSWORD_MISSING`; other driver failures return `DB_OPERATION_FAILED`.
Review such failures with an authorized database operator on the copy. Preserve the
original data and prepare a separately reviewed forward repair if required.
Existing password hashes, including historical demo hashes, remain unchanged;
adoption does not certify credential security. Review and rotate legacy credentials
before any production use under the separate authentication acceptance work.

The runner uses an exclusive transaction advisory lock, parameterized values,
10-second connection, 5-second lock and 60-second statement timeouts. All pending
schema changes and version inserts share one transaction. Concurrent managed jobs
fail with `DB_MIGRATION_BUSY`; uncoordinated external SQL writers are not controlled
by this advisory protocol. Psycopg's explicit transaction context provides commit
or rollback on exit ([transaction documentation](https://www.psycopg.org/psycopg3/docs/basic/transactions.html));
the lock is transaction-scoped ([PostgreSQL advisory locks](https://www.postgresql.org/docs/16/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS)).
Reviewed multi-statement SQL has no parameters and disables preparation; runtime
values use separate parameterized statements ([psycopg batch limitations](https://www.psycopg.org/psycopg3/docs/basic/from_pg2.html#multiple-statements-in-the-same-query)).

## Explicit accounts and demo data

Production has no seed accounts. Supply `BOOTSTRAP_ADMIN_ID`,
`BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` securely as process
environment variables, not command-line literals or checked-in files. Host-mode
bootstrap variables must be exported; putting them only in `.env` is insufficient.
Password length must be at least 12 characters and at most 72 UTF-8 bytes; use a
unique randomly generated value. ID permits ASCII letters, digits, underscore and
hyphen (1–64 characters); username is nonblank and at most 128 characters.

```bash
python -B -m app.core.db_bootstrap admin --execute
```

The command requires a current schema and refuses any existing administrator,
including inactive accounts; it never resets, overwrites or reactivates one.
Existing ID/name collisions fail transactionally. `AUTH_REQUIRE_PASSWORD=true`
is required outside development and enforced in production Compose for API/worker.
This narrow bootstrap guard does not complete C05's broader authentication review.

Demo is a separate choice for an empty **development** dataset, not a step after
production admin creation. Set `APP_ENV=dev`, mock business tool providers and a
securely exported `BOOTSTRAP_DEMO_PASSWORD`, then explicitly run:

```bash
python -B -m app.core.db_bootstrap demo --execute --allow-demo
```

This imports the preserved synthetic fixtures with operator-supplied bcrypt hashes.
Any existing application rows cause refusal. Seed rows and their checksum marker
commit together; repetition with the same seed returns `demo_seeded=false` without
duplicates. A changed seed checksum fails. The shared demo password is for an
isolated test dataset only. No administrator or demo seed is invoked on startup.

## Same-image production sequence (not executed)

Follow [DEPLOY.md](DEPLOY.md) for the explicit `.env.prod`, immutable image and
configuration check. After isolated-host authorization, start PostgreSQL only and
run the CLI from the reviewed API image before starting API/worker:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml pull api worker
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --no-build postgres
# Wait for the PostgreSQL health check; do not retry writes blindly.
docker compose --env-file .env.prod -f docker-compose.prod.yml run --no-deps api \
  python -B -m app.core.db_bootstrap apply --execute
docker compose --env-file .env.prod -f docker-compose.prod.yml run --no-deps api \
  python -B -m app.core.db_bootstrap status
# Export the three BOOTSTRAP_ADMIN_* variables securely before this command.
docker compose --env-file .env.prod -f docker-compose.prod.yml run --no-deps \
  -e BOOTSTRAP_ADMIN_ID -e BOOTSTRAP_ADMIN_USERNAME -e BOOTSTRAP_ADMIN_PASSWORD api \
  python -B -m app.core.db_bootstrap admin --execute
```

Stop on any nonzero exit. `--no-deps` prevents unrelated service/model startup;
one-off containers are retained for inspection, without automatic cleanup. Do not
inspect/export raw container environments. Only after schema status, administrator
bootstrap and the separately authorized C02 paid-probe gate may API/worker start.
The CLI itself does not invoke model probes. Preserve all existing volumes.

## Startup, recovery and acceptance

API/worker publish no session factory until exact current history and required
columns/types/widths, password NOT NULL and valid index names/uniqueness flags match.
Failure disposes the unpublished pool and aborts before audit/queue work. Database
health rechecks the same contract. This does not validate all constraint definitions,
index expressions, ownership, defaults, sequences or data quality; C03 live checks
must inspect these. C21 still owns full HTTP readiness and continuous health semantics.
The C02 model startup gate currently runs before the schema gate; use the standalone
CLI for database acceptance to avoid paid calls.

On SQL/verification failure, the transaction rolls back. If connection loss makes
commit outcome uncertain, run read-only `status` after reconnecting before deciding
to retry. Stop writers and preserve the snapshot and failed target. There is no
automatic down migration, database drop or volume cleanup. A post-commit problem
requires a reviewed forward migration or restoring the saved snapshot into a new
isolated database and explicitly selecting it; restoring over the current database
is outside this authorization. Never point an older application at newer history:
unknown versions fail closed. PostgreSQL sequence advances can have nontransactional
effects; failed account/seed operations may leave harmless ID gaps.

Required live evidence remains BLOCKED: empty initialization and repeat run; legacy
copy upgrade with before/after business-row and credential digests; migration failure
rollback; concurrent jobs; history/shape corruption rejection; administrator login,
duplicate/refused bootstrap and development-only demo repetition; API/worker refusal
on pending schema; recovery into a separate restored copy. Bind sanitized output,
exit codes and target identity to commit, image digest and manifest hashes. Never
store credentials, full row contents or raw database exceptions in evidence.
