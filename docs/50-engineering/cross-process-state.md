# Cross-process runtime state

Status: C09 offline increment delivered; **real two-process acceptance BLOCKED**.
The target remains at least two API processes on the single-host reference stack.
Current Compose still specifies one provisional API worker; this increment neither
raises that setting nor approves a reduced single-process delivery scope.

## Shared cancellation

Chat message and stream entry use the existing Redis service for short-lived run
leases. The key prefix is `businessagent:runtime:v1:`; identifiers are SHA-256 hashed.
Run/cancel keys for a session share a Redis hash tag. Use an isolated Redis instance
or database per deployment; the prefix is not a multi-tenant security boundary.

Existing-session authorization precedes Redis access. A lease is acquired before
updating existing-session metadata or starting graph/model work. A conflicting live
lease returns `409 SESSION_ALREADY_RUNNING` without changing that run's metadata.
A new server-generated session is created first; reservation failure marks it failed.
Database preparation failure releases an acquired lease before returning the error.

Lease TTL is 30 seconds. During graph work the owner polls every 0.5 seconds and
atomically compares/renews its token. A cancel request on any process atomically
captures the current token into the cancel key. The owner cancels its task after
observing that token. Release compares tokens before removing owned Redis keys;
late cleanup or a stale cancel key cannot target a later lease. Redis key removal
is runtime coordination, not filesystem deletion or historical credential cleanup.

`cancelled=true` means the signal was accepted against an unexpired lease, **not**
that work stopped. No active lease returns false. A dead worker can leave a lease
until expiry, so acceptance does not prove liveness. Completed external effects
are not undone. Blocking calls, cancellation-suppressing code and event-loop stalls
limit prompt interruption; the context refuses success if it observed cancellation
even when a nested coroutine suppressed CancelledError. There is no replay or rollback.

Redis operations use two-second connect/command timeouts and zero automatic retries.
New reservation/cancel failures return `503 RUNTIME_STATE_UNAVAILABLE`. Owner store
failure or lease loss aborts cooperatively; message returns 503 and an already-open
stream emits an error, not a successful user-cancellation event. Cleanup failure
uses a fixed log code and relies on expiry, without masking the original outcome.
An early request failure after reservation can leave a lease until its TTL expires.

Message and stream bookkeeping retain the lease until the response path releases it;
the watcher stops before publishing the final response. Long bookkeeping can therefore outlast TTL.
Lease expiry/Redis eviction or event-loop stalls do not fence PostgreSQL writes or
external tool effects. This is **not** full same-session checkpoint consistency,
exactly-once business execution or durable job recovery; C10–C14 retain those tasks.

## Single-use SSO state

Login generates random 32-byte state and nonce values, storing only nonce under the
hashed state key with `SET NX EX 600`. Every callback first checks the browser state
cookie, including IdP-error callbacks; only then does atomic GETDEL consume the nonce.
Callbacks routed to another process can consume the same shared entry. Missing,
expired, malformed or already-consumed state denies. Store failure returns a fixed
503 before IdP code exchange or JWT issuance; there is no in-memory fallback.

Cookie security remains HttpOnly, SameSite=Lax and Secure outside development.
Redis loss can require a new login; an uncertain GETDEL outcome must not retry token
exchange. TTL expiry remains effective across API restarts, subject to actual Redis
clock/persistence behavior. No claim is made that restoring old Redis backups cannot
resurrect consumed state; shared-state backup/failover is outside this candidate.
Real provider/browser/SSO verification and historical credentials remain blocked.

GETDEL requires Redis 6.2 or later; the deployment candidate uses Redis Stack 7.
The command and retry APIs were checked against [Redis GETDEL documentation](https://redis.io/docs/latest/commands/getdel/)
and [redis-py 5 retry documentation](https://redis.readthedocs.io/en/v5.0.1/retry.html).
These references confirm API contracts, not this project's runtime acceptance.

## Prompt visibility

Each persistent `run_graph` / `run_graph_stream` invocation loads all active prompt
versions and weights from PostgreSQL in one query, with a five-second async timeout,
before planner/agent execution. A ContextVar pins that snapshot through child tasks
and normal Python thread context propagation. Real LangGraph propagation still needs
verification. Running requests keep their selected version set; new requests on any
worker see activation/rollback/traffic commits visible to their database query.

Snapshot failure aborts the graph and produces the existing fixed chat failure
response; it never silently uses an old process cache. An empty active set uses code
defaults (version 0). The process cache remains for non-graph consumers and explicit
non-persistent developer runs; refresh replaces the mapping atomically. No Redis
cache invalidation or new database schema is introduced. Admin writes still commit
before local refresh; even if that refresh fails, later graph requests query the DB.
Concurrent admin transaction semantics are unchanged and are not an atomic rollout claim.

## Offline evidence and real acceptance

Reviewed entry from repository root:

```bash
python3 -I -B enterprise-agent/eval/run_c09_cross_process_state.py
```

The 28 focused tests execute actual state adapters, cancellation contexts, prompt
registry, graph entry and source-extracted SSO functions with separate module instances
over shared in-memory doubles. Fake Redis simulates command contracts; it does not
execute Lua, implement real TTL/network behavior or prove actual process isolation.
SSO HTTP-shaped responses and API calls are injected objects, not real FastAPI requests.

All following cases remain **BLOCKED** until explicitly authorized isolated Linux work:

| Case | Acceptance criterion |
| --- | --- |
| Two API processes, owner A / cancel B | Authorized signal reaches A, stream/message confirms eventual result, foreign owner denied before shared-store access |
| Concurrent starts / stale release | One unexpired session lease admits work; loser returns 409 without changing active metadata; old token cannot release or cancel the next run |
| Crash / expiry / restart / Redis loss | Observe lease expiry, no orphan retry, explicit 503/errors, bounded polling and zero false rollback claims; restore cases recorded separately |
| SSO login A / callback B | Real browser cookie/nonce/signature flow succeeds once, parallel replay fails, wrong cookie cannot consume, expiry/outage never issues JWT |
| Prompt activation / rollback / traffic | Running invocation stays pinned, subsequent request on B sees committed version and weights; DB outage cannot use stale cache |
| Runtime / capacity | Confirm actual Redis Lua/GETDEL and TTL, SQL query timeout/cancellation, LangGraph context propagation, API/SSE ordering, resource and polling cost |

Use isolated ports, Redis database, PostgreSQL, candidate image and test identities.
Route requests explicitly to both worker endpoints and retain redacted request IDs,
version evidence, signal timing and zero-effect assertions. Do not switch the current
deployment or execute restart/fault tests without authorization. C01–C08 blockers,
OpenSpec strict validation and full runtime tests remain; C10 now provides an explicit checkpoint candidate, but lease-expiry write fencing remains unresolved.
