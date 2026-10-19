## ADDED Requirements

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
