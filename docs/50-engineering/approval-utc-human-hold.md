# Approval UTC and human review candidate

## Current integrated approval boundary (2026-11-07)

This guidance supersedes conflicting preintegration behavior below. See the
[approved integration change](../../openspec/changes/integrate-local-delivery-security/proposal.md).
Approval records a decision only; the original requester must explicitly confirm with
fresh authentication. Batch decisions are atomic decisions, never batch execution.
Before each dispatch, enforce the exact committed approval, current participant/tool
permissions and UTC deadline. A mixed QUERY + approved ACTION plan fails closed:
run the query separately, then request approval for the action-only plan. Durable action
receipts cannot certify query results.

Stop on failure or unknown effects; never automatically compensate an approval execution.
Retain late receipts as evidence without automatically clearing a manual hold. Legacy
records without trusted provenance stay held; neither reapproval nor replacement requests
are a supported bypass. Authorized `GET /approval/{id}/evidence` (under `/api/v1`)
returns safe per-operation summaries, not a release capability. No release endpoint exists.

Managed schema v9 retains C10 v8 and adds approval guards. Follow
[database bootstrap](../../enterprise-agent/deploy/DATABASE_BOOTSTRAP.md), not the
historical standalone main 009 script directly. No database migration, service or deployment
was run for this documentation alignment. Real runtime/full RAG/C10, privacy and rights
acceptance remain BLOCKED or pending; historical synthetic results do not clear those gates.

## Historical standalone candidate and synthetic acceptance

The following describes the November 1 preintegration candidate, not the managed
integration installation procedure. Its standalone-009 instructions and test results are
retained as historical evidence only. They do not authorize execution on the managed path.


This is a local candidate against public main `5c57f0c719a4a079b94fdd8108cd6bcb20b01351`.
Core application/schema acceptance has passed on isolated PostgreSQL with synthetic data.
This is not full application or deployment acceptance, and no production database was changed.
The standalone additive 009 schema increment was executed only in the synthetic fixtures.
Public migrations 001–005 and init.sql are unchanged; unpublished 006–008 are neither copied nor overwritten.

## Behavior and human authority

New approvals use one database UTC wall-clock sample and a 24-hour deadline. Approval,
requester reauthentication, batch decisions and expiration scanning verify the same contract.
Reauthentication does not extend the deadline. An expired record cannot be dispatched.

Old nonterminal records without trustworthy provenance retain their original data and state.
They are displayed as requiring human review and cannot be automatically approved, resumed,
expired, converted or resubmitted. The hold covers all new approval creation and direct ACTION
execution for that requester, because the application has no reliable semantic operation key
with which to distinguish a retry from a different request. Read-only queries remain available.
This deliberately broad scope needs product acceptance before release.

AI can summarize evidence, explain risks and suggest options. It cannot supply a human decision,
clear a hold, promote an old approval or authorize another execution. No release/resubmit endpoint
is provided here. An authorized human must check the original record, provider evidence and
possible effects; a separately reviewed operational procedure is required to enact that decision.
Do not manually mark unknown records as successful or create replacements to bypass the hold.

## Four separate guarantees

1. Deadline checks use `clock_timestamp() AT TIME ZONE 'UTC'` and reject the exact boundary.
2. Row locks and a conditional status transition serialize claims. The transaction commits
   `executing` before calling any tool; an unconfirmed commit dispatches nothing.
3. Execution is sequential, stops on failure, skips Saga/compensation and disables HTTP mutation
   retries. Failed or uncertain effects become `execution_unknown`; if result persistence fails,
   `executing` remains. Neither state is automatically released. A batch stops on an uncertain
   result or server error; earlier external effects are not rolled back.
4. Human-review state is independent of deadline and of whether an external operation occurred.
   A timeout, network error, cancellation or missing mail receipt may follow a real external effect.

The mail adapter requires a 2xx response and a nonblank string message ID in the approval scope.
That is an acknowledgement shape, not proof of delivery, durable provider idempotency or exactly-once.
Multiple steps may have partially succeeded. A crash after claim but before I/O may cause zero
executions; another crash after I/O can leave an unknown result. No cross-request deduplication,
protection against database rollback, or exactly-once external service guarantee is claimed.

## Server-owned database provenance

New records store an independent `approval_contract` JSONB column, default SQL NULL. The
application builds the full immutable snapshot from row identity, UTC timestamps, ordered tool
plans, roles and effective provider/endpoint. Requests and model output never supply this column.
The old payload's self-described `deadline_contract` or `approval_contract` fields are ignored.
Before every transition, the saved snapshot must exactly match actual row fields and current targets.
The database guard rejects every UPDATE change to the contract, including NULL promotion, erasure
and content replacement. Only a new server writer INSERT creates trusted provenance. New imports
without trusted metadata remain NULL and held; there is no legacy backfill or release procedure.

No new long-lived signing key is required or configured. A dedicated column is appropriate
here because the server already owns
all trusted database writes. It avoids secret distribution/rotation while making legacy NULL explicit.
This is not protection from database administrators, arbitrary SQL/application compromise or
rollback, and it is not proof that a human approved an operation. Authentication, current roles
and the state transition remain separate checks. The snapshot does not bind the provider account
behind an API credential; operational account changes still require review.

The standalone `deploy/migrations/009_approval_contract_provenance.sql` is atomic and does not
change old records. A complete matching installation may be repeated; partial or incompatible
objects fail instead of being repaired or silently treated as trusted. The column is nullable,
with SQL NULL/default absence accepted; a default that automatically blesses old/new imports is
forbidden. Missing schema is an error, never a fallback to the old execution path. This script
is independent of unpublished migrations 006–008 and must never overwrite their history.

## Operational constraints before any future rollout

- Stop/drain all old API and worker processes first. Do not run mixed versions. An old executable
  can reopen old pending/reauth records and bypass the hold; rollback to it is unsafe even when
  no new `executing` records exist. Disabling execution is the safe rollback direction.
- Apply the new schema increment only in a separately authorized rollout after stopping old
  executors. Use a DDL identity for schema installation and an application identity without DDL
  or superuser privileges. The synthetic acceptance verified that permission split. No production
  access or migration has been authorized or performed here.
- Both new installations and existing databases must explicitly execute the complete 009 SQL file
  before enabling this application version. CI, application startup and image startup do not apply
  it. Compose mounts only the old init.sql; copying migrations into the image does not install them.
  Without 009, approval queries fail on the missing column. This is not a drop-in rolling upgrade.
  No startup migration, legacy backfill or automatic repair is provided.
- Endpoint/provider/override changes pause outstanding contracts if their target snapshot differs. The contract does not
  bind the account/principal behind an API credential: account changes require human review
  even if the URL stays the same. Never interpret secret rotation as proof that the target
  business account stayed unchanged.
- Existing Saga/Redis compensation tasks are outside this new dispatch protocol. Inspect and
  isolate them in a separately authorized deployment procedure; this code does not certify or
  automatically stop previously queued work. New approvals do not create such retry tasks.
- Public migrations 001–005 and the old init.sql are untouched; this patch does not supply or depend on unpublished 006–008. Historical naive timestamps are not
  interpreted as recoverable UTC. Terminal historical records are not changed.

## Completed synthetic PostgreSQL acceptance

On 2026-11-01, two new isolated PostgreSQL 16.15 (linux/arm64) databases completed all
25 required core checks each, using a fixed published Python 3.13 runner (linux/amd64).
Both started empty and applied the actual init.sql, public migrations 001–005 and candidate 009.
The second fixture additionally inserted an expired legacy pending approval with a forged payload
version before 009. These are two synthetic fixtures, not existing enterprise deployments.

The application and SQL tested were from candidate
`05297375d297179a3b069bb2069a004deaea584e`. A separately bound harness corrected one query from
`SELECT tgenabled` to `SELECT tgenabled::text`, because asyncpg decodes PostgreSQL's catalog char
as bytes. The corrected harness is now included byte-for-byte; production code and SQL remain
identical to the tested candidate. The original uncorrected harness did not pass this acceptance.
The correction preserves the strict trigger-state assertion and has an old-query negative control.

All 25 required stages passed in each fixture, with no missing or skipped required stages.
They exercised the real writer, approval handlers, timeout scanner and migration SQL. Coverage
included UTC/Asia-Shanghai 24-hour deadlines, expiry rejection, preserved legacy NULL contracts,
forged payload holds, immutable contract updates, malformed inserts, atomic migration rollback,
repeat installation and representative schema drift. Independent database sessions demonstrated
actual lock contention before claim commit, then one simulated effect and duplicate rejection.
Commit acknowledgement loss, outcome persistence failure, payload drift, task cancellation,
partial tool failure, pagination and batch stopping also passed. The disabled-trigger negative
control succeeded only within its rolled-back transaction; the ALWAYS guard was then verified.

No real email or provider API was called. The fixture had no host ports and used only synthetic
identities and data. Reports and source hashes were saved before stopping; successful fixtures
were deleted under explicit cleanup authorization. Earlier failed validation attempts and private
runtime records remain outside the public patch. A pure test suite and independent review covered
the harness type correction and evidence export; these are distinct from the actual PG results.
The preceding application regression baseline was 320 tests plus 71 subtests, with 26 secret-scan
regression tests. Counts for later harness-only tests must not be presented as a new full-suite run.

## Acceptance boundaries and future operation

`eval/run_approval_pg_acceptance.py` requires explicit execution and verifies a complete source
export and synthetic fixture arguments before connecting. After connecting, it verifies the
server/database/run markers and role privileges before schema or application operations.
Import, `--help` and pure guard tests do not connect. All 25 mandatory stages must return boolean true; missing or skipped
stages fail. Running this harness against a new source revision requires a newly bound export.
Keep fixture execution and any permanent synthetic cleanup within their explicit authorization;
preserve reports before stopping and retain failed fixtures for inspection. A failed Docker
connection cannot guarantee shutdown within a hard wall-clock deadline.

This acceptance does not cover HTTP login/authentication dependency routing, full document/RAG
flows, real providers, LLM/Redis, DST or deliberately long-open transactions, concurrent creation
or direct-action owner holds, cross-process termination during a provider effect, or audit-write
failure injection. The boundary check is at-or-before the actual database clock, not a frozen
microsecond. Catalog/JSON mutation cases are representative rather than exhaustive.

A core PASS is not complete deployment acceptance or proof of exactly-once external delivery.
It does not authorize AI to approve, unpause or reexecute uncertain legacy records. Dropping the
contract column or restoring the old executor is not a safe rollback; disable execution instead.

The existing PR workflow runs tests, secret/dependency scans and a local image build/scan; it
does not publish GHCR images for pull_request events. A successful push to main or a matching
version tag publishes the commit-tagged image and latest. Neither operation runs 009 or deploys
the business application. Publication, image release and any actual rollout remain separate
approval scopes; this candidate makes no changes to that workflow.
