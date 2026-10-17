# Retained jobs and independent workers

C14 candidate, 2026-10-17. Offline orchestration verified; real acceptance **BLOCKED**.
See [delivery record](../40-process/阶段性总结_C14队列可靠性与Worker初始化.md).

## Storage and identity

PostgreSQL `task_jobs` replaces the previously unused Redis List transport. This uses
existing dependencies and lets the business transition and enqueue share one commit.
Migration v3 adds jobs and consumer progress; v1/v2 bytes remain immutable. Apply only
through the [explicit bootstrap workflow](../../enterprise-agent/deploy/DATABASE_BOOTSTRAP.md)
in a separately authorized isolated candidate. No migration was executed this round.
API and worker both require manifest v3 before accepting work.

Each job has a UUID, unique logical scope, frozen payload hash, attempt count, state,
owner token, database-clock deadline and safe error code. Success and failure rows
remain stored indefinitely; there is no destructive acknowledgment, pruning, retry
endpoint or reset. Retention/capacity and archival policy need later review. Queue
writes are not extra copies of business content or bearer credentials.

| Transition | Condition and outcome |
| --- | --- |
| enqueue -> pending | Job plus document queued state commit together; caller owns transaction |
| pending -> leased | Due job, attempts below 4, `FOR UPDATE SKIP LOCKED`; random owner, 120-second lease |
| leased -> running | Matching unexpired owner; commit before handler invocation |
| running -> done | Handler succeeds and matching unexpired owner commits acknowledgment |
| expired leased -> pending | Same ID/input, delay `min(300, 5 * 2^(attempts-1))` seconds |
| expired leased -> dead | Four claims exhausted; `TASK_LEASE_EXHAUSTED` |
| expired running -> dead | `TASK_OUTCOME_UNKNOWN`; do not requeue |
| handler error -> dead | Fixed terminal code or `TASK_OUTCOME_UNKNOWN`; no automatic side-effect retry |

Claims whose responses are lost remain leased and recoverable. Dispatch whose commit
response is lost never invokes the handler, but conservatively remains running until
reconciliation. Lost completion responses never create a new job or replay an effect.
Recovery scans at most 100 expired rows per cycle. Polling waits one second; database
outages back off 1/2/4/8/16/30 seconds, then remain capped at 30. Queue transactions have
a 10-second client deadline. Claims and renewals use database time, not worker clocks.

A running handler renews every 20 seconds. The 300-second handler timeout and SIGTERM
shutdown are cooperative. Existing synchronous embedding/vector calls can block the
loop and cannot be forcefully cancelled. An expired owner cannot update queue state,
but an old process/thread may still finish an external write. A dead task therefore
means reconciliation required, **not stopped, rolled back or safe to repeat**. Before
any manual recovery, establish old-worker termination and inspect independent effects.
No exactly-once guarantee or C10 checkpoint write fencing is claimed.

## Application path and API contract

`POST /api/v1/admin/knowledge-candidates/{document_id}/approve` now returns **202**:
`data = {document_id, task_id, status}` where status is the retained job state, initially
`pending`. It no longer returns synchronous chunks or asserts active publication.
The document moves `draft -> queued`; identical submissions return the same job,
including after a commit response was lost. The `knowledge_publication_queued` audit
record commits in that same transaction and explicitly records acceptance, not
publication success. Different publication options conflict.
Non-draft documents without an existing job are rejected. Queued/active documents
cannot be rejected through the draft-rejection route.

The envelope stores document ID, snapshot hash, original reviewer and publication
options only. The worker reloads the queued document, checks snapshot and explicit ACL,
reauthorizes the current reviewer as admin, then calls text ingestion. Arbitrary local
file paths and legacy file-ingestion payloads are refused. Zero chunks is failure.
Full publication/version consistency, vector-before-ledger failures and concurrent
out-of-band document edits remain C15; there is no automatic replay to amplify them.

All status endpoints require current admin authorization:

- `GET /api/v1/admin/task-jobs/{task_id}`: identity, queue, state, attempts, safe error and timestamps.
- `GET /api/v1/admin/task-jobs?state=dead&limit=20&offset=0`: retained failure list; no payload or owner token.
- `GET /api/v1/admin/task-consumers?limit=100`: worker UUID, queue, last progress time and `fresh` (45 seconds).

Job records are durable execution evidence, not a complete replacement for the C21
audit pipeline. Completion means the ingestion function returned a positive count
and queue acknowledgment committed, not independent verification of Milvus visibility.
The original scope currently allows one publication per document; versioned updates
and deliberate re-publication must be designed in C15, not implemented by clearing jobs.

## Worker lifecycle and unresolved capabilities

Startup verifies production configuration, model profile and schema, initializes audit
and all built-in tools, and initializes Milvus when selected. No vector fallback is
allowed. Memory is an explicit development-only option and is not a usable independent
API/worker publication backend. Partial startup failure closes the connection pool and
Milvus connection. Consumers start only after initialization succeeds.

Per-consumer progress heartbeats are updated during polling and lease renewal. An
unexpected consumer/maintenance return terminates the worker with a fixed error and
cancels siblings; process restart policy remains the existing deployment policy.
SIGTERM requests cooperative shutdown. Database outages keep consumers retrying with
stale progress visible. Status rows are retained across restarts, so operators must
check **both queue kinds for the current worker**, not any historical fresh row.
Compose still disables the inherited API HTTP probe; consumer freshness is separate
from Docker health and full C21 readiness/alerts.

Saga dispatch returns `C13_REQUIRED` without calling legacy compensation. There is
still no durable Saga business producer/step/inverse identity; C13 must supply these
and reuse C12 operation IDs before safe recovery can be enabled. The available queue
can carry retained identities, but C14 does not invent missing IDs or claim Saga replay.

The legacy audit cache flusher deletes files. This worker no longer invokes it; files
remain untouched and unsynchronized until C21 delivers a reviewed non-deleting path.
Do not run legacy cache replay as a workaround.

Redis remains required for checkpoint, cancellation and SSO. Its outage cannot lose
PostgreSQL queue rows, but can still block the application. Existing Redis Lists are
not imported, drained or deleted. Stop old consumers before a future rollout, inspect
legacy depth read-only, and prepare a separately approved migration/reconciliation
plan if entries exist. Never deploy old and new workers against a mixed queue contract.

## Outstanding acceptance matrix

All following rows are **BLOCKED**, not proven by SQL doubles:

| Case | Required isolated evidence |
| --- | --- |
| v3 migration and schema gate | Empty/v2 upgrade, repeat, rollback, checksums and refusal before migration |
| Two producers / two workers | One stable job, exclusive real SQL claims and unchanged unrelated rows |
| Crash before/after claim/dispatch/ack | Retained identity, pre-dispatch delayed recovery, unknown/dead instead of duplicate effects |
| PostgreSQL interruption | Commit-response loss, bounded reconnect, stale heartbeat, eventual recovery |
| Redis interruption | Durable queue rows unaffected; dependent API/checkpoint failure reported truthfully |
| Cold independent worker | Correct models/schema/tools/Milvus initialization; actual knowledge API -> job -> vector/ledger |
| Expiry, stale owner, timeout, SIGTERM | No late queue acknowledgment; inspect actual effects; do not infer external fencing |
| Exhaustion / malformed task | Queryable safe failure, no raw payload/credential diagnostics |
| Saga recovery | Requires C13 producer, retained forward/inverse IDs and independent reference receipts |
| Audit recovery / system readiness | Requires C21 non-deleting replay and full health/alert evidence |

C14 remains open. C10 race, C13 HTTP compensation, C15 publication consistency, C18
independent services, all prior runtime/browser/SSO/history blockers and enterprise
UAT/release gates remain unchanged.
