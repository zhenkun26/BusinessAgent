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


### Requirement: Shared rate limiting fails closed and recovers
Outside explicit development, rate-limit store failure SHALL return a fixed 503 with a
five-second retry hint and SHALL NOT admit work using per-process fallback quotas. Development
MAY reuse retained memory windows and SHALL label that backend. Quota denial SHALL remain 429.
Each process SHALL retry after a five-second monotonic cooldown with at most one in-flight
probe, bounded probe/command calls, zero automatic command retries and sanitized diagnostics.

#### Scenario: Redis fails at initialization or during quota accounting
- **WHEN** probing or a quota command fails, times out or has an ambiguous result
- **THEN** non-dev requests return 503 before downstream work; development fallback is labeled
  and does not erase existing local windows; no same-request Redis replay occurs

#### Scenario: Recovery and concurrent callers
- **WHEN** the cooldown expires and requests arrive concurrently
- **THEN** one local probe runs while others use the failure policy, successful recovery allows
  fresh shared checks without restart, and older probe success cannot erase a newer failure

#### Scenario: Probe cancellation
- **WHEN** a request is cancelled during a probe or quota operation
- **THEN** cancellation propagates without downstream work, probe ownership is released and
  a later eligible request can retry rather than remaining permanently degraded

#### Scenario: Shared quota observations have equal timestamps
- **WHEN** independent callers record quota observations with the same timestamp
- **THEN** transactionally counted entries have distinct members and cannot overwrite one
  another; fake-store validation alone does not close real multi-process acceptance
