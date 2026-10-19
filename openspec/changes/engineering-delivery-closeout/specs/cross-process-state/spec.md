## ADDED Requirements

### Requirement: Cancellation is shared and bound to one live run
Chat entry SHALL reserve an expiring shared session lease before graph execution.
Another API process SHALL be able to signal that run after existing session access
checks. Renewals and release SHALL compare run tokens. Conflicting starts SHALL
return 409; store failures SHALL deny new starts/cancel requests and abort owned work.

#### Scenario: Cancel reaches a different worker
- **WHEN** worker B accepts cancellation for worker A's active session
- **THEN** A observes the shared signal and cancels cooperatively; old cleanup or
  cancellation cannot affect a later run and no completed side effect is rolled back

#### Scenario: Owner dies or loses the store
- **WHEN** its lease expires or Redis becomes unavailable
- **THEN** the lease is not treated as persistent work, live owners stop cooperatively,
  and no automatic replay, recovery or exactly-once execution is claimed

### Requirement: SSO state is shared and atomically consumed
SSO state SHALL store only a short-lived nonce in shared Redis. All callbacks SHALL
validate the browser state cookie before consuming it exactly once. Store failures
SHALL return a fixed 503 without token exchange or issuance; no memory fallback is allowed.

#### Scenario: Callback changes worker or is replayed
- **WHEN** a callback goes to another process or repeats a previously consumed state
- **THEN** the first matching callback obtains the nonce and all replays/expired states deny

### Requirement: Persistent graph requests use committed prompt snapshots
Each persistent graph invocation SHALL load active prompt content and weights from
PostgreSQL before model execution and pin the snapshot for that invocation. A later
request on another worker SHALL observe a committed activation/traffic update.
Snapshot loading failure SHALL abort instead of silently using a stale process cache.

#### Scenario: Activation during a running request
- **WHEN** an administrator commits a new version while a request is running
- **THEN** that request keeps its snapshot and the next invocation reads the new version

### Requirement: Cross-process support requires real acceptance evidence
Offline doubles SHALL NOT close C09. At least two real API processes SHALL verify
Redis atomicity/TTL, restart/failure, SQL visibility and HTTP/SSE/SSO behavior before
multi-process support is accepted. Existing deployment defaults SHALL remain provisional.

#### Scenario: Local increment delivered
- **WHEN** offline checks pass
- **THEN** C09 stays open, prior runtime/history blockers persist, and C10 awaits confirmation
