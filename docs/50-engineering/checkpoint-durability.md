# Checkpoint persistence and failure contract

C10 offline increment, 2026-10-17. **Real durability acceptance BLOCKED.**
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
business work. Business idempotency, Saga and approval recovery remain later items.

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
They establish API usage, not verification of installed candidate packages. The repo
still has version ranges; record resolved versions and image digest during acceptance.

API startup must initialize the configured saver before yielding. Failed initialization
prevents startup; a cached backend name in `/ready` is only a label, not a continuous
liveness check. Full readiness/HTTP status integration remains C21.

History enumeration failure now aborts before graph/model execution, using fixed
`CHECKPOINT_UNAVAILABLE`. Successful reads with no checkpoints return empty history;
expired, erased and never-created states cannot be distinguished from the saver alone.
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

C09 leases reject overlapping API requests while ownership is live. They do not fence
checkpoint writes after expiry or under event-loop stalls; direct graph calls bypass
API admission. This known limitation prevents claiming unconditional same-session
serialization. No cross-process write-fencing mechanism is delivered by C10's offline
increment. Adversarial expiry/stale-owner tests and any required subsequent repair
remain part of C10 before its parent can close, not silently deferred as a passed item.
Do not raise the provisional Compose worker count or claim durable business recovery.

## Acceptance matrix

| Check | Required evidence | Current status |
| --- | --- | --- |
| Offline lifecycle/failure contracts | Actual application source with saver/framework doubles, no network/filesystem writes | PASS; see delivery record |
| Installed package compatibility | Record Python, LangGraph, Redis saver, PG saver, psycopg/libpq versions and candidate digest; imports and full graph writes/readback | BLOCKED |
| Cross-process/restart | A writes, B reads; terminate/restart A and repeat on each selected backend; preserve owner/request binding | BLOCKED |
| Redis retention | Observe refresh-on-read/write, inactivity expiry, related keys, zero-TTL and API/Redis restart behavior without calling expiry a cleanup proof | BLOCKED |
| Same-session race | Active overlap is refused; deliberately expired lease/stalled old writer cannot silently corrupt or overwrite the later run; fix before closing C10 if failure occurs | BLOCKED; current leases alone do not guarantee the latter |
| Backend outage/uncertain write | Disconnect during initial probe, history, checkpoint write and final read; no silent backend change or final success; record possible partial commit | BLOCKED |
| PG setup | Fresh isolated checkpoint schema, repeat setup, interrupted setup and API read-only startup; actual async saver methods pass | BLOCKED |
| API/SSE/browser | Auth/ownership, status/error mapping and provisional stream behavior under real transport | BLOCKED |

C10 remains open. Prior real Redis/two-process/LangGraph/Milvus/JWT/PostgreSQL/API/SSE/
Linux/browser/SSO/historical-credential blockers stay unchanged. No next closeout item
or C10 push is authorized by this local delivery.
