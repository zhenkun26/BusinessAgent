# Checkpoint persistence and failure contract

C10 current offline candidate, 2026-10-19 (initial increment: 2026-10-17). **Real durability acceptance BLOCKED.**
No current-store access, setup, migration, restart or deletion was performed.

## Backend selection and compatibility

`CHECKPOINT_BACKEND` chooses exactly one backend for the lifetime of each API process:

| Value | Initialization and retention | Support/evidence boundary |
| --- | --- | --- |
| `redis` (default) | Existing AsyncRedisSaver index setup, bounded read probe; `CHECKPOINT_TTL_DAYS=7` maps to 10080 minutes with refresh-on-read | Redis Stack/Search/JSON required; actual version, key TTL and Redis restart durability unverified |
| `postgres` | Enter AsyncPostgresSaver context, read pre-provisioned schema; no automatic setup at API startup | Explicit alternative, no Redis-state migration; real psycopg/libpq/saver compatibility unverified |
| `memory` | Explicit `APP_ENV=dev` only, process-local | Developer-only, lost on restart, no cross-process recovery |

Unknown backend and memory outside development fail closed. All API processes must
share backend, target store, schema and TTL settings. A cached selection does not
change if configuration changes during the process lifetime. No initialization or
runtime fallback, migration, graph replay or write retry is added. The underlying
client may reconnect to the same target; that is not recovery of erased/expired data.
C09 still requires Redis for chat admission and SSO even when checkpoints use PostgreSQL.

Changing backend/target requires draining traffic and a separately approved migration
or explicit new-session policy. Existing session IDs must not silently be interpreted
as restored in an empty/new store. This increment neither migrates nor deletes history.
There is no automatic resume endpoint: a new chat turn is not replay of interrupted
business work. Business idempotency, Saga and approval recovery retain their C12/C13/C11 contracts;
checkpoint ownership does not fence their external side effects.

## Lifetime, provisioning and failure

An async lock serializes first initialization. The saver is published only after its
read probe succeeds. Failed initialization, cancellation and shutdown close owned
resources; shutdown also clears compiled graph caches after requests drain. Do not
call `reset_checkpointer()` while requests are active. Initialization has a 15-second
async bound; connection/read/close bounds are five seconds. Cancellation bounds are
cooperative and require actual driver tests. Cleanup failure logs a fixed code and
may still need process termination; it is not proof that the remote connection closed.

Redis keeps its pre-existing additive index setup. PostgreSQL provisioning is separate
from both application schema bootstrap and API startup. After separately authorizing
an isolated target, a future operator may configure `CHECKPOINT_BACKEND=postgres` and
run from `enterprise-agent/`:

```bash
# No --execute: refuses before opening a store.
python -m app.graph.checkpointer setup-postgres
# Explicit DDL/metadata writes to the configured target; NOT executed in this increment.
python -m app.graph.checkpointer setup-postgres --execute
```

The command enters `AsyncPostgresSaver.from_conn_string`, calls awaited `setup()`,
probes and closes. It is not part of the application's schema ledger and does not
claim all-or-nothing rollback of the library's migrations. On failure, stop and
inspect the isolated schema/version; do not automatically retry against current data.
There is no down/delete/prune implementation. PostgreSQL DSNs use psycopg's conninfo
builder so reserved characters in credentials are not concatenated into a URI.

The adapter contracts were checked against upstream [PostgreSQL saver source](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py)
and [Redis async saver reference](https://redis-developer.github.io/langgraph-redis/main/api/async_checkpoint_saver.html).
They establish API usage, not verification of installed candidate packages. The production image uses pinned requirements; record resolved versions and image digest
during acceptance. Source inspection of installed Redis/PostgreSQL saver exact-ID lookup
is not a real round-trip or durability test.

API startup must initialize the configured saver before yielding. Failed initialization
prevents startup; a cached backend name in `/ready` is only a label, not a continuous
liveness check. C21 adds runtime readiness probes, whose real fault behavior remains BLOCKED.

History enumeration failure now aborts before graph/model execution, using fixed
`CHECKPOINT_UNAVAILABLE`. The history-snapshot endpoint uses legacy only without a pointer;
multi-turn context may supplement accepted turns with older read-only legacy after
publication exhaustion within the shared budget.
A recorded publication whose checkpoint is absent is an error, not empty history. Without
a pointer, expired, erased and never-created legacy states cannot be distinguished.
Legacy snapshots without matching request/identity binding remain excluded as in C08.
Message/history persistence-read failures return 503. Other graph/write exceptions
remain fixed chat execution errors (500, or an SSE error), without retry/fallback.

SSE tokens/progress are provisional. After graph completion, the saved final snapshot
must exist, contain a nonempty answer and match request ID, user, session, role and
department; foreign/stale/absent snapshots emit `CHECKPOINT_UNAVAILABLE`, not `final`.
A fresh plan-rejection response can be terminal without entering answer history.
A failed write may have committed remotely before the response was lost; error does
not prove rollback. Completed external effects are not undone or automatically replayed.

## Retention and concurrency limits

Redis TTL is sliding and applies only to that saver. Nonpositive TTL disables expiry;
changing it does not retroactively rewrite all existing keys. PostgreSQL and memory
have no automatic TTL in this implementation. Redis TTL is not a guaranteed privacy
purge: backups, pending writes and related-key coverage require separate evidence.
No cleanup, credential revocation or historical purge was performed.

The initial C10 increment had no write fence after Redis lease expiry. The 2026-10-19
repair implements the following candidate; real two-process acceptance is still BLOCKED.

### Ownership and publication

1. Redis admission creates a unique run token. PostgreSQL `session_write_fences` then
   claims the logical session using that token and a 30-second database-clock lease.
   An occupied live database lease refuses admission even if Redis has expired. Failed
   database admission conditionally releases only the requesting Redis token.
2. The watcher renews the database lease only after Redis confirms ownership and no
   cancellation. An expired database lease cannot be revived. All owner changes,
   session-start updates and publication lock the same fence row; status writes also
   test token and database-clock expiry. Database operations fail closed, with a
   10-second transaction bound and 5-second lock/statement bounds in the fence adapter.
3. Each run writes to `c10_<sha256(logical-session)>_<unique-run-token>`. Persistent graph
   entries require that run's context; direct calls without ownership fail. The explicit
   no-checkpointer test entry remains available. Logical session IDs are not saver write
   destinations. A suspended old write may finish in its own orphan thread, including
   pending writes, but cannot replace the successor's physical thread.
4. After graph completion, the API reads and validates that run's final checkpoint.
   One PostgreSQL transaction locks current ownership, appends the exact checkpoint
   ID/backend/thread/namespace, updates terminal status and cumulative tokens, and
   releases ownership. Expiry before the guarded status update rolls the transaction
   back. Repeated publication/late failed or cancelled callbacks cannot overwrite a
   successor or count tokens again. Message success and SSE `final` follow confirmation
   of this transaction; provisional token/progress events remain provisional.
5. History reads only accepted IDs, never the latest raw snapshot of an orphan run.
   Inspect at most 100 snapshots, filtering before collecting up to five eligible turns.
   One five-second deadline covers publication lookup, saver reads and read-only legacy.
   Stop early and close async iterators once enough valid turns exist. After available
   publications are exhausted, remaining scan budget may supply older legacy turns.
   Identity/role/department and current-request exclusions remain enforced. Budget
   exhaustion returns only collected eligible turns; missing required data, wrong IDs,
   backend mismatch or timeout fails closed, without partial-history substitution or
   orphan discovery. The synchronous legacy adapter runs a bounded batch in a thread;
   request cancellation cannot forcibly stop an already-blocked synchronous driver call.
   Configured Redis/Postgres application savers use the async path and driver timeouts.

PostgreSQL is the logical publication authority; this is not a distributed transaction
with Redis or the raw saver. Row locks serialize publication and takeover, relying on
[PostgreSQL Read Committed row-lock qualification](https://www.postgresql.org/docs/16/transaction-iso.html).
The lock is held through transaction completion, so an old publisher cannot commit after
a successor has acquired the same fence. This is a design argument, not measured PG proof.
A lost commit acknowledgement returns failure and is not retried: the accepted pointer
may already exist. A later failure callback cannot undo a committed publication. Token
totals count accepted turns only; partial/failed attempts may still incur provider costs.

Admission failure after creating a new session can leave a retained `pending` row.
Crash/expiry may leave `running` metadata until a later owned turn; no background repair,
automatic resume, orphan discovery, cleanup or deletion is added. PostgreSQL publication
rows have no TTL. Redis accepted snapshots may expire while their pointers remain, which
correctly makes reads unavailable; retention/backup recovery must cover both stores.
Development memory checkpoints still disappear on restart and cannot satisfy durability.

### Schema and upgrade boundary

`deploy/008_session_fencing.sql` is an additive v8 migration with checksums in the managed
manifest; earlier v1–v7 files are unchanged. Both API and worker require the full manifest.
Migration execution is separate and was not performed here. Drain traffic, stop all older
API writers, snapshot the approved isolated target, apply/verify the manifest and start
only the new binary. Mixed old/new writers are unsupported. Old logical checkpoint threads
remain read-only compatibility history. Do not run the old application against schema v8
or treat downgrade as permission to remove tables. C22 restoration uses matching source,
image and schema identities and needs fresh v8 acceptance.

Do not raise the provisional Compose worker count or claim durable business recovery.
External actions, audit records and knowledge writes retain their own contracts and are
not made atomic with checkpoint publication by this repair.

## Citation projection contract

Message, SSE final and found history snapshots share `normalize_sources`. The history
endpoint now adds `sources` to its existing owned-session response; a missing checkpoint
retains its prior `found: false` response. Public fields are document_id, chunk_id, title,
source_url, updated_at (ISO 8601), score (finite) and namespace. The existing
RetrievalSource model is the validation authority; its class/module identity is unchanged.
Known lc=1/2 envelopes are projected from kwargs without executing stored constructors.
Unexpected fields are omitted; malformed sources cause CHECKPOINT_UNAVAILABLE, including
HTTP 503 or SSE error without final success. Validation happens before publication, but
stored/raw state is not rewritten. This is structural validity, not semantic RAG evidence.

## C10-R1/R2 implementation plan — 2026-10-19

Authorized after planning commit `c0a4464`; implementation starts from that candidate.
Scope is the two reviewed defects only. No new dependency, migration, live service/API,
committee review, push, merge, release or archive. C10 and live/full RAG gates stay open.

1. Reproduce Redis source-envelope leakage and valid history hidden behind rejected turns.
2. Normalize sources through one validated projection shared by message, SSE and the
   authorized history response. Accept the existing model, plain fields and the known
   Redis constructor envelope without executing constructors from stored metadata.
   Preserve the public source fields; malformed sources fail with a fixed checkpoint
   error rather than partial citations or raw metadata. Validate before publication.
3. Read accepted snapshots lazily, filter before counting turns, and stop at five eligible
   turns. Share a 100-snapshot budget and a five-second deadline across publication and
   read-only legacy history. Only scan legacy after exhausting available publications
   within the budget; never scan orphan threads. Budget exhaustion returns only eligible
   turns already found; read errors/timeouts fail explicitly. Retain identity, role,
   department, request binding, duplicate suppression and chronological output.
4. Add deterministic counterexample, malformed-input, timeout/count-bound, legacy,
   cancellation and authorization regressions, including the actual installed Redis
   serializer round-trip. Run reviewed offline eval entry and relevant/full regression
   without skips; preserve fixtures and deny network/deletion. Record source identity.
5. Review the diff, synchronize ISSUES/ROADMAP/delivery/OpenSpec, and commit locally.
   Stop for user confirmation; passing offline checks does not close C10/live gates.

Acceptance: all three source projections agree without `lc/type/id/kwargs` leakage;
malformed persisted sources cannot publish a successful final; five rejected/foreign
turns do not hide a sixth valid answer; valid turns, not scanned records, consume the
turn limit; both total budgets and existing failure/privacy/fencing behavior are tested.
Execution complete: 25 focused cases and complete local pytest 925 tests + 249 subtests
PASS, zero skips/guard denials. Results and retained receipts are in the delivery status
and [follow-up record](../40-process/阶段性总结_C10检查点持久化与故障语义.md#c10-r1r2-follow-up--2026-10-19).
Real API/store/process and full RAG acceptance remain BLOCKED; C10 is not closed.

## Acceptance matrix

| Check | Required evidence | Current status |
| --- | --- | --- |
| Offline lifecycle/failure contracts | Actual application source with saver/framework doubles, no network/filesystem writes | PASS; see delivery record |
| Installed package compatibility | Record Python, LangGraph, Redis saver, PG saver, psycopg/libpq versions and candidate digest; imports and full graph writes/readback | BLOCKED |
| Cross-process/restart | A writes, B reads; terminate/restart A and repeat on each selected backend; preserve owner/request binding | BLOCKED |
| Redis retention | Observe refresh-on-read/write, inactivity expiry, related keys, zero-TTL and API/Redis restart behavior without calling expiry a cleanup proof | BLOCKED |
| Same-session race | Run the expiry/takeover scenarios below against actual processes and stores | BLOCKED; isolation/publication candidate and offline tests do not close it |
| Backend outage/uncertain write | Disconnect during initial probe, history, checkpoint write and final read; no silent backend change or final success; record possible partial commit | BLOCKED |
| PG setup | Fresh isolated checkpoint schema, repeat setup, interrupted setup and API read-only startup; actual async saver methods pass | BLOCKED |
| API/SSE/browser | Auth/ownership, status/error mapping and provisional stream behavior under real transport | BLOCKED |

C10 remains open. Prior real Redis/two-process/LangGraph/Milvus/JWT/PostgreSQL/API/SSE/
Linux/browser/SSO/historical-credential blockers stay unchanged. The current user authorization covers C10 implementation, offline checks, documents and
a local commit only. No push, merge, release, deployment, spec synchronization or archive.


## Required stale-writer runtime scenarios

All scenarios below remain **BLOCKED**; capture candidate commit/image, schema checksums,
backend/library versions, two independent process IDs and sanitized before/after state.
Use authorized isolated stores and controlled faults, not the developer's current data.

| Scenario | Acceptance standard |
| --- | --- |
| Active overlap | A owns Redis and PG; B is refused without changing A's session or checkpoints |
| Redis expiry only | Lose A's Redis lease while PG remains live; B cannot claim PG; A stops and cannot report success |
| PG expiry only | Redis still renews but PG lease expires; A cannot revive it, publish or mutate terminal metadata |
| Delayed old write | Pause A during saver `aput` and separately `aput_writes`; expire ownership, let B publish, then resume A; only B's exact ID/status/tokens are session-visible |
| Late callbacks | After B takes ownership, A's start/completed/failed/cancelled/release/renew calls leave B unchanged |
| Commit versus takeover | Pause publication around row lock, insert, guarded status and commit; B waits or acquires afterward; no old commit overwrites an already accepted B run |
| Crash/outage | Kill A or disconnect Redis/PG/saver before and during publication; no false success, fallback or replay; record retained pending/running/orphan state |
| Uncertain acknowledgement | Lose reply after PG commit; response is failure, accepted pointer may exist; follow-up failure and repeated publish cannot duplicate tokens |
| History/restart/TTL | B reads accepted A history after restart; orphan threads are excluded; missing referenced ID/backend mismatch yields unavailable; legacy history remains read-only |
| API/SSE/cancellation | Success/final only after confirmed publication; swallowed cancellation cannot become success; ownership/auth and provisional event semantics hold over real transport |
| Upgrade/recovery | Drain old writers, apply v8 twice with no duplicate DDL, verify startup refusal on v7/drift; restore a matching v8 backup and recheck pointers plus physical checkpoints |

Offline reproduction: `python3 -I -B enterprise-agent/eval/run_c10_session_fencing.py`
from the repository root. The 28 cases use explicit clocks and transactional SQL/saver
semantics doubles; they do not execute PostgreSQL SQL, prove row locking, or emulate
real process/network timing. Results and full regression evidence are retained in the
[C10 delivery record](../40-process/阶段性总结_C10检查点持久化与故障语义.md).
