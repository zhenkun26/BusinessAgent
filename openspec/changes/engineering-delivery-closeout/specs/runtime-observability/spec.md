## ADDED Requirements

### Requirement: Readiness reflects required capabilities
The service SHALL return 503 when a bounded required dependency probe fails and 200 only
when all required capabilities are observed ready. Liveness SHALL remain independent.

#### Scenario: Dependency fails and recovers
- **WHEN** PostgreSQL, Redis, configured vector/checkpoint storage, tools, worker or audit retention is unavailable
- **THEN** readiness fails with sanitized component states and can recover after fresh successful probes

### Requirement: Audit replay retains stable event identity without deletion
API and worker SHALL attempt to retain sanitized audit events in shared persistent storage before delivery,
deduplicate PostgreSQL writes by event ID and retain acknowledgements without deleting files.

#### Scenario: Commit acknowledgement is lost or a process restarts
- **WHEN** a retained event is retried after an ambiguous commit
- **THEN** at most one database event with that ID exists and retained bytes/receipts remain available

#### Scenario: Both audit storage paths fail
- **WHEN** neither retention nor database delivery succeeds
- **THEN** the process reports unretained events and unhealthy readiness rather than claiming lossless delivery; restart does not establish repaired evidence

### Requirement: Correlation and metric labels have distinct purposes
The application SHALL correlate request and worker execution audits with bounded IDs while
metrics use bounded route/method/outcome labels and measure complete streamed responses.

#### Scenario: Multiple processes serve dynamic paths and an interrupted stream
- **WHEN** each process is scraped independently
- **THEN** dynamic identifiers do not create label series and response-start/body-completion/abort semantics are distinguishable

### Requirement: Controlled alerts preserve fault and recovery evidence
A controlled monitor SHALL retain fault/resolution events, retry with stable IDs and require
an independent receiver acknowledgement before recording delivery.

#### Scenario: Receiver is unavailable during a fault then recovers
- **WHEN** delivery fails and is later retried
- **THEN** retained fault and recovery events are not silently discarded or duplicated at the receiver

### Requirement: Runtime acceptance remains independent
C21 SHALL record actual process/store/receiver evidence separately from offline checks.

#### Scenario: Only injected or in-memory tests pass
- **WHEN** no isolated runtime execution has occurred
- **THEN** C21 and all prior runtime gates remain open or BLOCKED and C10 fencing is not closed
