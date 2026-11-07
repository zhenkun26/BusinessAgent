## ADDED Requirements

### Requirement: Published citation fields are consistent and validated
Message, SSE and authorized history responses SHALL expose the same JSON-safe source
fields for model, plain and known Redis-envelope representations. Invalid persisted
sources SHALL fail with a fixed checkpoint error, without constructor execution,
metadata leakage, partial citations or successful publication.

#### Scenario: Redis stores a source as a constructor envelope
- **WHEN** the actual serializer restores a RetrievalSource as an envelope
- **THEN** all three response paths retain the public source fields and omit envelope internals

#### Scenario: Persisted citation is malformed
- **WHEN** a source lacks required fields or carries an unknown constructor envelope
- **THEN** final publication is refused and APIs expose a fixed checkpoint failure

### Requirement: History counts eligible turns within shared budgets
History SHALL filter identity, request and answer binding before counting eligible
turns. It SHALL inspect at most 100 snapshots under a shared five-second deadline,
stop at five eligible turns, and read legacy only after available publications are
exhausted within the budget. Count exhaustion MAY yield fewer valid turns; read errors
and timeouts SHALL fail explicitly. Orphan snapshots SHALL NOT be discovered.

#### Scenario: Rejected turns precede a valid answer
- **WHEN** five rejected or unauthorized publications precede an eligible older answer within the budget
- **THEN** history includes the eligible answer, keeps privacy filters and chronological ordering

#### Scenario: Scan limits or failures occur
- **WHEN** the shared scan count is exhausted or a required store read times out or fails
- **THEN** count exhaustion returns only eligible collected turns, while read failure or timeout aborts without empty-history substitution

### Requirement: Persistence backend is explicit and stable
The application SHALL select one configured backend and SHALL NOT silently switch to another store or memory after initialization or runtime failure. Memory SHALL require explicit development configuration.

#### Scenario: Configured backend is unavailable
- **WHEN** initialization or a persistent operation fails
- **THEN** the request/startup fails explicitly without invoking another backend, replaying graph execution or claiming restored state

### Requirement: Saver resources have a managed lifetime
The application SHALL serialize singleton initialization, verify a read before publication and close resources on failed initialization/cancellation/shutdown. PostgreSQL schema provisioning SHALL be explicit and separate from API startup.

#### Scenario: Concurrent first access or setup failure
- **WHEN** several callers request a saver or setup/probe fails
- **THEN** only one successful instance is published, failed resources close, and exceptions contain no connection credentials

### Requirement: History and final-state failures cannot imply success
The application SHALL distinguish a missing history from a failed read, stop execution on read failure and verify streamed final-state request/identity binding before publishing success.

#### Scenario: Missing or stale stream snapshot
- **WHEN** a stream ends but its snapshot is missing or belongs to another request or identity
- **THEN** it emits a fixed error and does not emit final success

#### Scenario: History storage is unreachable
- **WHEN** history enumeration fails or times out
- **THEN** graph/model work does not continue with an empty-history substitute

### Requirement: Durability claims require real evidence
The project SHALL retain separate acceptance for backend versions, restart/cross-process recovery, Redis TTL, same-session write races and outages, and SHALL NOT equate C09 leases or mocked saver calls with fencing or durable business recovery.

#### Scenario: Only offline checks pass
- **WHEN** tests use in-memory saver/framework doubles
- **THEN** C10 parent/live acceptance remains BLOCKED and no next closeout item starts without confirmation


### Requirement: Expired runs cannot publish over a successor
Persistent runs SHALL write separate physical checkpoint threads. Session publication,
terminal status and token totals SHALL require the current unexpired database-clock owner
inside the same transaction that serializes ownership transfer. Expired ownership SHALL
NOT revive; missing ownership SHALL reject direct persistent graph invocation.

#### Scenario: A delayed old writer resumes after takeover
- **WHEN** a lease expires and a successor owns the same logical session
- **THEN** old raw writes remain in its own thread, old publication/status/token updates fail, and the successor checkpoint and metadata remain unchanged

#### Scenario: Publication acknowledgement is lost
- **WHEN** a commit may have succeeded but its acknowledgement is unavailable
- **THEN** the request reports a fixed failure without automatic replay or a rollback claim; no streamed final success precedes confirmed publication

#### Scenario: Published history is missing or mismatched
- **WHEN** a publication points to an absent checkpoint or a different backend
- **THEN** history fails explicitly rather than selecting an uncommitted or orphan snapshot

### Requirement: Citation time preserves explicit instant and legacy uncertainty
New epoch-derived KnowledgeAgent citations SHALL use timezone-aware UTC, independent of
server timezone, and serialize an explicit UTC offset. Historical naive citation values
SHALL retain wall-clock fields without an inferred timezone or migration. Aware historical
values SHALL retain their supported offset and instant through public projection.

#### Scenario: The server timezone changes across DST or a date boundary
- **WHEN** the same valid epoch is converted on UTC, America/New_York or Asia/Shanghai servers
- **THEN** newly generated citation JSON represents the same explicit UTC instant, including epoch zero and fractional seconds

#### Scenario: Legacy sources pass through Redis serialization and history
- **WHEN** an accepted citation has no timezone or has an explicit non-UTC offset
- **THEN** source projection and message/SSE/history responses preserve the respective naive fields or aware instant without silently adding UTC to unknown historical values

#### Scenario: Retrieval returns an invalid epoch
- **WHEN** source construction encounters malformed, non-finite or out-of-range epoch seconds
- **THEN** the agent returns its fixed failure and no partial successful citation list

#### Scenario: Only offline formatting has passed
- **WHEN** Node VM verifies the existing formatter and approval naive-as-UTC compatibility
- **THEN** real browser acceptance remains BLOCKED, legacy naive citations are not reinterpreted, and the current Chinese UI scope is unchanged
