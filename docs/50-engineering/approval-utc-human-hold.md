# Approval UTC and human review candidate

This is a local candidate against public main `5c57f0c719a4a079b94fdd8108cd6bcb20b01351`.
It has not been deployed or accepted against PostgreSQL. A standalone additive 009 schema increment is included but has NOT been executed. The public baseline has migrations 001–005; they are unchanged. Unpublished 006–008 are neither copied nor overwritten.

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
clear a hold, re-sign an old approval or authorize another execution. No release/resubmit endpoint
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

No new long-lived signing key is required or configured. The earlier local HMAC candidate is
retained for evidence only. A dedicated column is appropriate here because the server already owns
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
  or superuser privileges. The acceptance fixture must verify that permission split. No production
  access or migration has been authorized or performed here.
- Endpoint/provider/override changes pause outstanding contracts if their target snapshot differs. The contract does not
  bind the account/principal behind an API credential: account changes require human review
  even if the URL stays the same. Never interpret secret rotation as proof that the target
  business account stayed unchanged.
- Existing Saga/Redis compensation tasks are outside this new dispatch protocol. Inspect and
  isolate them in a separately authorized deployment procedure; this code does not certify or
  automatically stop previously queued work. New approvals do not create such retry tasks.
- Public migrations 001–005 and the old init.sql are untouched; this patch does not supply or depend on unpublished 006–008. Historical naive timestamps are not
  interpreted as recoverable UTC. Terminal historical records are not changed.

## Required real database acceptance (pending authorization)

Use a new owned PostgreSQL 16 fixture containing only synthetic users/approvals and mock provider
boundaries. Do not connect to an existing database or resume old containers. Run the candidate's
actual writer, API handlers and scanner, not an equivalent SQL-only experiment. Record image
version/digest, architecture and candidate SHA. Use a new PG container with network none and an ephemeral Python runner sharing only its loopback
network namespace. Neither publishes host ports or starts the business server. Proposed aggregate
limits are 2 CPU / 3 GiB. The prepared runner bounds work to 450 seconds, evidence transport to
30 seconds, and then makes independently bounded owned-resource stop attempts. A failed Docker
connection cannot guarantee shutdown within a hard wall-clock deadline; it is a failure requiring
explicit retained-resource reporting, never a pass. Preserve evidence before cleanup; permanent
deletion of the two owned containers and their single synthetic data volume requires explicit
approval together with execution. Failed runs stop and retain resources for inspection.

Exercise UTC and Asia/Shanghai sessions, DST scenarios, delayed transactions and the exact expiry
boundary; NULL/malformed old contracts; forged metadata and modified plans; two independent
connections claiming one approval; creation/direct-action races against a hold; lost commit
acknowledgement; provider success followed by result-write failure; cancellation; partial multi-step
results; batch stopping and expiration scans beyond 100 old records. Verify preserved old rows and
one simulated dispatch at most per approval, including failure paths. No real email/API is permitted.
Test the additive migration only in new synthetic fixture databases, including repeat/rollback and
immutable-column failures. After any new contracts exist, dropping the column or running the old
executor is not a safe rollback; stop execution and retain evidence instead. Approval of this plan does not authorize
business deployment, production changes or a hold-release operation.


The prepared `eval/run_approval_pg_acceptance.py` requires explicit execution authorization and
verifies the candidate export and exact synthetic database/run markers before connecting. Its
25 mandatory stages cover the core application/schema path; missing, skipped or non-boolean-pass
results fail the run. `--help` and pure harness-guard tests do not connect to PostgreSQL.
Current offline evidence is 320 tests + 71 subtests, and 26 secret-scanner regression tests. These
are not database acceptance results. The earlier HMAC candidate's counts must not be reused here.

The prepared PG stage deliberately does not certify HTTP authentication wiring, real providers,
LLM/Redis, DST/long-open transaction cases, concurrent creation/direct-action owner holds,
cross-process termination or audit-write failure injection. Representative schema drift and bad
JSON cases are included; exhaustive catalog/JSON mutation is not claimed. The harness records
these limits in `not_covered`; a core PASS must not be relabelled complete deployment acceptance.
