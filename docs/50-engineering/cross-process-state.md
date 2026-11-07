# Cross-process runtime state

Status: C09 offline increment delivered; **real two-process acceptance BLOCKED**.
The target remains at least two API processes on the single-host reference stack.
Current Compose still specifies one provisional API worker; this increment neither
raises that setting nor approves a reduced single-process delivery scope.

## F2-02 rate-limit failure and recovery plan — 2026-10-19

Authorized after local F2-01 commit `6832527`. Plan recorded before implementation.
Scope is the rate limiter only; cancellation/SSO/checkpoint/queue semantics remain unchanged.

1. Outside explicit development (`is_dev is True`), Redis probe or quota-command failure
   returns fixed `503 RATE_LIMIT_UNAVAILABLE` plus `Retry-After: 5`, without calling the
   downstream handler or consuming a per-process fallback allowance. Genuine quota exhaustion
   remains 429. Existing health/readiness/docs bypasses remain unchanged; readiness is not
   changed into a limiter recovery signal.
2. Development may use the existing memory limiter. Reuse its windows across failed probes;
   clearly mark development fallback responses `X-RateLimit-Backend: memory`. Other decisions
   identify `redis`; unavailable responses identify `unavailable`. This header is diagnostic,
   not an API promise of cross-process correctness or a replacement for O-series metrics.
3. Use a five-second monotonic cooldown per process, one in-flight probe per process and
   reuse one Redis client. Followers during a probe fail closed or use development memory
   immediately; they do not queue behind a shared lock. Successful PING re-enables attempts,
   but every production admission still needs a successful quota command. A failure generation
   prevents an older probe from clearing a newer failure. Cancellation releases the probe flag,
   retains a cooldown and propagates without downstream execution.
4. Bound probe and quota calls to two seconds each (initial/recovery request at most two
   sequential budgets), configure connect/command timeouts and zero SDK retries, and emit
   fixed failure/recovery log codes without Redis URLs, credentials or raw exceptions.
   An uncertain command is never retried on the same request; production returns 503.
5. Keep the existing shared key prefixes/route limits and transaction-based sliding window.
   Give each ZADD observation a unique member so equal timestamps from separate callers do
   not overwrite each other; explicitly require a transactional pipeline. Do not alter the
   existing memory remaining-header arithmetic, route-key coupling or proxy trust policy.
6. Add offline failure/recovery/concurrency/cancellation/timeout tests, shared fake-store
   accounting (including equal timestamps), configuration and sanitized-response tests.
   Retain F2-01 real-JWT checks, run C09 eval and full pytest without skips, review and commit
   locally. Do not run real Redis, change dependencies or deploy.

Acceptance: non-dev requests cannot gain fresh memory quotas on failure; development windows
survive retry attempts; cooldown prevents repeated probes; recovery needs no process restart;
concurrent probes/cancellation cannot permanently strand state; failed or ambiguous operations
never call downstream outside dev. Offline independent-client/shared-store checks are contract
evidence only. Real two-process Redis/proxy failure/recovery and clock behavior remain BLOCKED.
Redis restart/eviction/data loss can reset quota history; this increment provides availability
failure policy, not durable quotas, exactly-once charging or Redis failover certification.

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
OpenSpec strict validation and full runtime tests remain; C10 now implements isolated run threads and database-owned publication; actual lease-expiry write-fencing acceptance remains BLOCKED. See [the current contract](checkpoint-durability.md).


## F2-02 delivery evidence — 2026-10-19

The plan above preceded implementation. Redis failure no longer gives non-dev callers a
fresh process-local allowance. During initial probe, cooldown or recovery probe, non-dev
followers return fixed 503 immediately; even a healthy cold start can briefly return 503
while the first probe is pending. Dev followers may use labeled memory. A successful probe
only restores shared attempts: quota-command failure still denies the request. Successful
older quota operations may finish their own admitted request but cannot reopen failed state.

Compatibility: 429 still means an exhausted quota; 503 means no shared decision. The new
`X-RateLimit-Backend` header identifies `redis`, `memory` or `unavailable`; bypassed paths
remain without limiter headers. Dev memory and Redis windows are not merged, so switching
between them does not promise a global total. Clients must not automatically replay business
writes after an ambiguous HTTP outcome. This change retries dependency probes on later
requests, not the failed quota operation or any business action. Readiness probes remain
separate from quota recovery.

Two-second connect/command settings and asyncio budgets require a responsive event loop
and cooperative cancellation; they are not measured wall-clock latency guarantees. Cooldown
is local and uses monotonic time. Redis quota scores still use host wall clocks; clock skew,
real pipeline behavior, Redis restart/data loss and eviction need isolated acceptance. UUID
members preserve distinct observations even with equal timestamps, including mixed legacy
and new members during a future approved rollout; no key migration or data cleanup is run.

| Verification | Result / boundary |
| --- | --- |
| Pre-fix failure-policy counterexamples | 3 expected FAIL; old code admits non-dev work on store failure |
| New recovery cases | 18 PASS within focused/full runs: probe/command failure, cooldown, dev retention, concurrency, stale completions, timeout/cancel, 429 versus 503, SDK configuration, sanitized diagnostics and shared observations |
| Focused limiter/identity/app-entry tests | 61 PASS, including all 30 F2-01 cases; no security assertion removed |
| C09 reviewed eval | 28 PASS; injected state adapters/graph/SSO checks, not live process acceptance |
| Complete local pytest | 973 tests + 249 subtests PASS, zero skips/xfails/guard denials; 74.54% local line coverage |
| Documentation / scope | 365 local link targets, YAML and manual OpenSpec structure PASS (23 deltas, 112 requirements, 163 scenarios); 221 Python hashes match the full receipt; original modes/unrelated bytes preserved |
| Environment | macOS arm64 Python 3.13.15; retained installed packages match production requirements; no dependency installation |
| Live Redis/proxy/two-process/Linux, remote CI and full RAG | BLOCKED; C09/C10/C23 and prior runtime matrices remain open |

Two independent clients use an already-declared fakeredis shared server for the counting
check. This exercises the real Redis adapter's transaction API and UUID observations in one
Python process, not Redis wire behavior, network failures, distributed clock correctness or
OS process separation. Policy tests inject store failures and a monotonic clock. Existing
memory tests now explicitly select dev; F2-01/app-entry fixtures inject only the quota store
so their identity/route assertions stay active without bypassing production-policy tests.

Retained records under `enterprise-agent/eval/results/`:

- Pre-fix: `ci-pytest-975cafbfbc6748ec82c59aedf2e06b07/receipt.json`.
- Final focused: `ci-pytest-1f2e021b7ead4eab86012cf06d428a60/receipt.json`.
- Full: `ci-pytest-ca8ea48b96c1485eb1fc588ab7063f51/receipt.json`, runner and coverage.

The full receipt records parent `6832527` and tested working-tree hashes, including the new
recovery test. Final code must match these hashes after documentation edits; a retained
postcommit binding records the local commit. Use declared dependencies to run
`python -B -m pytest tests/test_rate_limit_recovery.py tests/test_rate_limit.py
 tests/test_rate_limit_identity.py tests/test_app_entry.py` from `enterprise-agent/`.
In this no-deletion workspace, the retained diagnostic runner is the reviewed method;
no selection filter was used on its complete run. The reviewed C09 command above was also run.

For live acceptance: run two real API processes sharing Redis; verify a single aggregate
quota across workers, interrupt the store and observe 503 with zero downstream admissions,
restore it and observe recovery without restart, retain distinct user/IP behavior through
the proxy, and test client disconnects, command-reply loss, clock skew and restart/eviction.
Bind candidate/image/config and record actual outage duration/admissions; production evidence
must not use development memory. F2-03 remains unstarted. Local commit only; no push, merge,
deployment, release, spec sync or archive. C10 and full RAG are not closed by this increment.
