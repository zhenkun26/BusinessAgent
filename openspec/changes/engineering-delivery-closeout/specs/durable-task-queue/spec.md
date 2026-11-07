## ADDED Requirements

### Requirement: Persist jobs with business transitions
The application SHALL enqueue knowledge publication in the same PostgreSQL transaction as the queued document state. Repeated identical submissions SHALL return the same retained job; conflicting intent SHALL fail. Acceptance SHALL mean queued, not published.

#### Scenario: Producer commit response is lost
- **WHEN** the caller repeats the same approval
- **THEN** the original job identity is returned without another publication

### Requirement: Retain ownership and uncertain outcomes
Claims SHALL use exclusive database ownership and deadlines. Only an unexpired owner SHALL dispatch, renew or finish. Jobs SHALL be retained after completion or failure; exhausted or uncertain jobs SHALL be queryable without payload disclosure.

#### Scenario: Worker dies before dispatch
- **WHEN** a leased job expires
- **THEN** it is delayed and retried within a bounded attempt budget, or retained as dead

#### Scenario: Worker dies after dispatch
- **WHEN** a running job expires or its outcome is uncertain
- **THEN** it is retained for manual reconciliation without automatic repeat of side effects

### Requirement: Initialize and supervise independent workers
Workers SHALL initialize schema, models, audit, tools and the configured vector backend before claiming jobs; fail closed on startup failure; reconnect after store failures; publish per-consumer progress; and exit on unexpected consumer termination.

#### Scenario: Dependency initialization or a consumer fails
- **WHEN** initialization fails or a consumer exits unexpectedly
- **THEN** no healthy-worker completion is claimed and resources/children are closed

### Requirement: Preserve dependent recovery boundaries
Knowledge jobs SHALL revalidate current reviewer authority and the frozen document. HTTP Saga recovery SHALL remain disabled until C13 provides durable compensation identities. C15 publication consistency, C10 fencing and real runtime evidence SHALL remain separate.

#### Scenario: Only offline orchestration tests pass
- **WHEN** C14 is delivered locally
- **THEN** C14 remains open with runtime and Saga acceptance BLOCKED and further work waits for confirmation
