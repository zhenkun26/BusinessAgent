# Independent reference HTTP integration

C18 implementation candidate, 2026-10-18. **Runtime R01–R20: BLOCKED.**
This guide supplements [business-reference-v1](reference-business-contract.md), without
changing its wire contract or acceptance criteria. The offline increment supplies independent
service code, deployment recipes and an application transcript collector. It does not prove
complete application integration, physical durability, real-provider support or enterprise UAT.

## Components and trust boundaries

| Component | Candidate behavior | Evidence still required |
| --- | --- | --- |
| `reference_service.server` | One process per CRM/ticket/mail service, business port 8080 and operator port 8081 | Actual Linux listeners, isolation, framing and failure behavior |
| SQLite service ledger | Separate volume/store UUID per service; run-bound fixtures, operations, effects, receipts, attempts and faults | Filesystem permissions, crash recovery, physical persistence and retained journals |
| CRM | B01/B02/B03/B08/B10 plus `crm-analysis-v1` pages from the same run fixture | Application query/analysis agreement and exact money values |
| Ticket | B04/B05/B06/B08/B11; versions, before-images and retained comments | Application/Saga partial success and conditional inverse execution |
| Mail sink | B07/B08/B09/B12/B13, synthetic allowlist, capture/recall/requested states | Application approval and no egress under real network policy |
| Application | Existing C12/C13/C11/C14 paths; JSON request headers corrected; two admin observation routes | Real JWT/PG/graph/queue/audit and operation-to-service correlation |
| Acceptance collector | Opt-in login → chat → decision → fresh resume, bounded metadata and independent ledger snapshots | Semantic oracles and all R01–R20 operator observations |

The service package imports no application tool adapters. It uses Python's existing standard
library (`sqlite3`, `http.server`) and adds no third-party dependency. It is a controlled,
single-organization test system, not a production CRM, ticket platform, SMTP service or
multi-tenant authorization boundary. Run one process per service/store; multi-replica operation
is not an accepted deployment mode. The writer-transaction recheck also prevents a second
connection from applying a terminal operation again, but disk/multiprocess behavior is untested.

All three services use separate business credentials. Optional read-only credentials exercise
403 write denial. A separate operator credential grants fresh-run provisioning, fault setup and
per-run evidence on port 8081 only. It is never passed to the application. Application JWTs
never serve as provider credentials. No reset, list-all, cleanup or public control endpoint exists.

## Persistence and failure model

`REFERENCE_DB` must be an absolute file path with an existing, non-symlink parent. Normal
startup opens an existing database in read/write mode and checks service, schema, store UUID
and SQLite integrity; it never creates a replacement for a missing ledger. `--initialize` is a
separate, explicit action for a new path only. A partial initialization is retained and startup
fails; no repair-by-overwrite or deletion is attempted. UUIDs are identity assertions, not a
cryptographic backup provenance proof. Restoring older contents under an unchanged UUID still
requires independent operation-count/hash reconciliation; a UUID match alone is insufficient.

The schema is `reference-store-v1`. `BEGIN IMMEDIATE` serializes mutations. Registration retains
a pending operation; a second transaction rechecks terminal state, then commits business effects
and the terminal receipt together. A savepoint rolls back a rejected tentative effect while the
same writer transaction persists its rejection. Unexpected exceptions roll back the effect and
leave pending evidence. On retry the same logical key/request may finish pending work; committed
work is replayed unchanged. The application still reconciles before retrying an uncertain write.

Storage uses `synchronous=FULL`, `temp_store=MEMORY` and `journal_mode=PERSIST`. SQLite documents
PERSIST as retaining the rollback journal and invalidating its header at commit; see the
[official journal-mode documentation](https://www.sqlite.org/pragma.html#pragma_journal_mode).
This is a configuration choice, not measured filesystem evidence. Verify the deployed SQLite
version/VFS, normal transactions, savepoints and crash recovery under filesystem monitoring
before accepting the no-deletion/durability procedure. Keep database and journal evidence
together; no WAL cleanup, vacuum, automatic compaction or filesystem removal is supplied.
Offline tests use only `:memory:` SQLite and cannot validate those physical properties.

CRM inverse operations retain tombstones. Ticket inverses retain comments and mark superseded
forward comments; unrelated later versions reject with 409. Internal mail can become `recalled`;
external mail becomes only `recall_requested` (202) or rejects as unsupported (501), never falsely
fully compensated. The sink contains no SMTP, DNS/MX lookup, attachment fetch or external-send
implementation. Its allowlist is exactly the three `@reference.invalid` addresses in the contract.

## Isolated Linux preparation (not executed in C18)

Use a new reviewed host/project and fresh application databases/volumes. Do not reuse current
or enterprise state. C01/C02/C03 readiness, actual model credentials and a reviewed non-deleting
audit execution path remain prerequisites. Historical JSON cache paths require separate review;
C21 now provides retained audit/replay; O01–O16 runtime acceptance remains BLOCKED, so this
guide does not authorize starting that path now. Application chat
may call the configured paid LLM. No deployment or paid call was made for this increment.

1. Review `deploy/Dockerfile.reference`, build it from `enterprise-agent/`, resolve the image to
   a digest and record the Python/SQLite versions. Build the application candidate separately
   according to C01/C02. Build/import probes are not runtime acceptance.
2. Prepare ignored `.env.prod` and `.env.reference` using `deploy/reference.env.example`.
   Record the exact 40-character candidate commit and both immutable image digests. Supply
   fresh run UUIDv4 and three distinct store UUIDv4 values; generate independent credentials
   of at least 32 characters. No default secrets are supplied. Keep them out of CLI arguments,
   logs, shell transcripts and published Compose configuration.
3. Review the combined production Compose plus `deploy/docker-compose.reference.yml`.
   The overlay adds an internal reference network and separate volumes; API/worker join it.
   Reference services publish no host ports and have a read-only root, non-root UID, dropped
   capabilities and no automatic restart. Check the inherited production settings separately:
   do not start `nginx`, monitoring or all services implicitly (they can expose host ports).
   Never print a fully expanded secret-bearing Compose configuration into evidence.
4. Explicitly initialize each **new** reference volume once. A representative future command,
   from `enterprise-agent/`, is below. Replace the project/container names with unique reviewed
   names; run analogous commands for ticket/mail. Retain completed containers and volumes.

   ```bash
   docker compose -p isolated-reference-run-01 --env-file .env.prod --env-file .env.reference \
     -f docker-compose.prod.yml -f deploy/docker-compose.reference.yml \
     run --no-deps --name reference-crm-init-run-01 reference-crm \
     python -B -m reference_service.server --initialize
   ```

5. Complete the separately reviewed application bootstrap, identity and checkpoint procedures
   before starting API/worker. Use three active local accounts: admin, manager requester and a
   distinct authorized manager approver. Seed them via the reviewed C03/C11 process; the runner
   does not create users or grant roles. Start only explicitly named dependency/API/worker and
   reference services after the remaining side-effect and runtime gates are resolved.
6. Verify actual image IDs, process separation, private network/egress policy and all store IDs
   before any business input. `/health` only proves a minimal live DB query; it does not certify
   schema provenance, end-to-end readiness or worker health.

Do not use `--rm`, `down`, prune, reset, volume replacement or automatic cleanup. This document
supplies no deletion command. Archive by retaining evidence, containers and volumes for the
user's later disposition. Stop on startup/identity failure; do not initialize a replacement to
make an old operation appear absent.

## Operator control-v1

Every request requires the operator bearer, fresh `X-Request-Id` UUIDv4, JSON Accept header,
and JSON Content-Type for writes. The control listener uses run identity in the path/body;
caller-supplied business run/role headers grant no authority. Control responses are bounded at
8 MiB; oversized evidence fails rather than silently truncating. Business requests/responses
are bounded at 64 KiB and reject duplicate headers/JSON keys, chunked framing and invalid types.

| Method/path | Body or response | Rules |
| --- | --- | --- |
| POST `/control/v1/runs` | `{run_id,principal,users,fixture,external_recall_supported?}` | Fresh UUID only; 1–20 unique existing application user IDs; `baseline` or `variant`; optional bool defaults true |
| POST `/control/v1/runs/{run}/faults` | `{operation_id,attempt,phase,mode}` | Exact UUIDv4, attempt 1–100, immutable one-shot schedule; duplicate returns 409 |
| GET `/control/v1/runs/{run}/evidence` | Store/schema/run/principal/fixture identity, resources, operations, attempts, fault consumption | Authenticated retained evidence; no token or request header export |

`baseline` contains C001/C002 and O001/O002 (120050 and 9999 CNY minor units respectively).
`variant` is a separate new run with O001 at 240100/version 2. It never edits an earlier run.
The same records back B01/B02 and analytics; snapshot identity includes run/principal, fixture
hash and date range. Customer pages require the order snapshot; cursor/range changes reject.

Fault phases/modes:

- `before_commit`: `503`, `429`, `drop`, `delay`, `pending`; registration persists, effect absent.
- `after_commit`: `503`, `429`, `drop`, `delay`, `malformed`, `wrong_receipt`, `redirect`;
  original effect and valid receipt are committed before transport corruption.
- Delay is fixed at six seconds, beyond the application's five-second attempt budget.
  Drop closes the connection before response; malformed returns invalid JSON; wrong receipt
  substitutes only the outbound operation ID. The ledger retains the original truth.
- Faults target an already known operation/attempt; there is no global “next request” switch,
  title trigger or automatic rearming. Terminal receipt replay precedes new fault application.
  An approved-but-not-resumed external mail operation provides a natural preparation pause.
  Other timing-sensitive cases need an explicitly controlled operator schedule or debugger;
  this increment does not automate process crashes or force a planner's chosen tool.

## Application observation and transcript

Admin-only `GET /api/v1/admin/reference-profile` checks exact isolated service URLs, seven HTTP
providers, distinct credentials and password/DB authentication. It exposes booleans and public
run/principal identity, not secrets. CONFIGURED is a preflight result, never acceptance.
`GET /api/v1/admin/reference-evidence/{session_id}` returns at most 200 rows per category:
operation IDs/states/request hashes, approvals, Sagas, compensation IDs, jobs and audit metadata.
Queries are parameterized and bounded by ten seconds. Tool payloads, audit summaries, tokens
and passwords are omitted. The six reads are **not an atomic snapshot**; take stable observations
and retain timestamps. Missing audit rows are reported as missing, never repaired here (C21).

The reference image's `python -B -m reference_service.acceptance` defaults to plan-only,
constructs no network client, writes nothing and exits 2/BLOCKED. It is not an alternative
backend startup command. Explicit execution additionally requires `--execute`, a fresh `.json`
output in an existing non-symlink directory, all three application account credentials and
expected image/run/store identities. `--provision` explicitly creates fresh runs in all services;
existing runs fail instead of resetting. Without it, evidence reads require previously provisioned
matching runs. Partial provisioning is retained and documented; no rollback-by-deletion occurs.

After future authorization, run the evaluator in the same isolated project (retain the container):

```bash
docker compose -p isolated-reference-run-01 --env-file .env.prod --env-file .env.reference \
  -f docker-compose.prod.yml -f deploy/docker-compose.reference.yml \
  run --no-deps --name reference-evidence-run-01 reference-evaluator \
  python -B -m reference_service.acceptance --execute --provision --output /data/run-01.json
```

The default plan performs login/chat query, CRM/ticket create/update, internal mail, external
approval and fresh requester resume via actual API routes. It does not directly invoke tools,
create operations, bypass the planner or manufacture approval state. Planner omissions/failures
must be judged against the ledger; HTTP 200 is not semantic success. Custom JSON plans use
`reference-transcript-v1` and steps with `id`, `case` R01–R20, `action`, optional prior
`session_step`, and action fields: message `text`, decide `decision`, or fault
`tool,inverse,attempt,phase,mode`; observe/resume need no further fields. Ambiguous approvals
or operations stop execution rather than selecting an arbitrary row. A custom plan must already
be present in the reviewed image or a separately reviewed read-only mount.

The client connects only to fixed internal hosts, denies redirects and bounds responses and socket/read budgets
(180 seconds per application call, 30 per control call, 8 MiB). Tokens stay transient and are
redacted from reports. The output retains declared candidate/image identity, actual service
store/fixture identity, plan/source hashes, per-step response/status and per-session app/ledger
observations. A changed store/fixture identity stops before further messages. Declared image
identity still needs operator verification. A killed collector can leave no complete report;
retained application/provider journals remain the recovery evidence, never invent missing steps.

Successful transcript steps are OBSERVED, not PASS. Correlation compares forward IDs, hashes,
run/service and states; mismatches are FAIL, pending/unknown are unresolved. Compensation,
audit completeness, business semantics, process crashes and absence-of-egress require separate
oracles. Overall and all runtime cases remain BLOCKED, with `formal_uat=false`,
`release_evidence=false`, `release_allowed=false`, even if every plan step executes.

## R01–R20 operator evidence schedule

The [frozen matrix](reference-business-contract.md)
is authoritative. Supplement the default transcript, retain before/after ledgers, and record
actual input, IDs, fault placement, expected/observed effect count and reviewed conclusion for
**each** case. Unexecuted/failed subcases cannot be hidden by successful happy paths.

| Cases | Additional controlled operation | Required independent oracle |
| --- | --- | --- |
| R01–R02 | Projection/items/absent ID queries plus planned create/update | Exact fixture values, no query mutation; one bound record/receipt/version and app audit per write |
| R03–R06 | Same request resume/redelivery, distinct same-body actions, changed-key payload and parallel replay | Same logical ID has one effect/original receipt; distinct actions have distinct IDs; conflicts add no effect |
| R07–R08 | Install exact before/after fault at a known prepared operation; interrupt pending owner only under reviewed schedule | Retained pending/committed evidence, bounded behavior; no blind retry or duplicate effect |
| R09–R10 | Read-only/wrong credential, malformed request, stale version, unknown recipient; corrupt outbound response | Denial/no effect or truthful unknown, no permissive success, redirect following or mock fallback |
| R11–R12 | Separately reviewed stop/restart and crash placement for service/application/worker, retaining volumes | Same physical ledger and original operation/receipt across restart; recovery reconciles before new work |
| R13–R15 | Plan reversible multi-step partial failure, fault an inverse, later unrelated update before inverse | Reverse order and linked inverse IDs; one inverse effect; version conflict preserves later change |
| R16–R18 | Captured mail, internal recall, unapproved/expired/duplicate/stale-authority approval, external recall requested/unsupported | Zero unauthorized capture/egress, fresh authorized resume once; requested/501 never becomes fully compensated |
| R19–R20 | Separate run/principal, unauthorized control/reset; unavailable provider/PG/audit/queue and incompatible store identity | No disclosure/reset/fallback/rekey; unknown/manual reconciliation visible; missing audit remains a blocker |

Protocol-level supplemental probes are not substitutes for complete application-path evidence.
For malformed inputs that normal tools cannot emit, retain both the direct protocol rejection
and the application's corresponding validation/unknown behavior. The default collector does
not synthesize these negative paths. Real HTTP listener behavior, physical service restart,
real PostgreSQL/JWT/API/SSE/Linux, accepted model calls, full RAG, browser/SSO and historical
credential disposition remain BLOCKED. C10 checkpoint fencing remains open, and C21 audit
replay is untouched. C19 is the next separate authorization gate.

## Reviewed offline verification

From repository root:

```bash
python3.13 -I -B enterprise-agent/eval/run_c18_reference_integration.py
python3 -I -B enterprise-agent/scripts/safe_validate.py
```

The 45 focused tests use actual independent service code and **in-memory** SQLite, actual
adapter/gateway/analysis functions with injected HTTP/PG/identity, and fake socket/HTTP response
objects. They include atomic rollback, terminal recheck, key conflict/replay, fault phases,
compensation, auth/isolation, HTTP framing, collector boundaries and admin data minimization.
An audit hook rejects file databases, filesystem mutation/deletion, real network and subprocesses.
It does not certify a general-purpose sandbox. No Docker build, server start, real API call,
new dependency install, file database or cleanup was executed. Related C12/C13/C11/C16/C06
regressions pass; see the [delivery record](../40-process/阶段性总结_C18完整参考HTTP业务集成.md).
Legacy `eval/run_ticket_acceptance.py` remains excluded because of startup and cleanup behavior.
