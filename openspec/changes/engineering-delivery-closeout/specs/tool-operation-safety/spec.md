## ADDED Requirements

### Requirement: Persist logical action identity before dispatch
The application SHALL persist an execution UUID and distinct per-action UUIDs before I/O, freeze the plan and provider scope, and reject changed replay input or missing identity.

#### Scenario: A scope is replayed after restart
- **WHEN** a retained execution is loaded again
- **THEN** it uses its original action IDs; identical new actions in separate slots remain distinct

### Requirement: Mutations require an exclusive durable dispatch claim
The gateway SHALL persist the wire request before atomically claiming dispatch. It SHALL NOT automatically reclaim dispatched or unknown work to send another mutation.

#### Scenario: A response or local receipt commit is lost
- **WHEN** a write may have committed
- **THEN** re-entry queries the original operation or reports unknown, never creates a new ID or reports rollback

### Requirement: Validate receipts and bound transport
Reference tools SHALL validate status, profile, identity, request hash, resource, version and effect; missing evidence SHALL NOT count as success. All requests SHALL have total deadlines and redirects disabled. Mutation retries SHALL be disabled; reads MAY retry at most twice.

#### Scenario: The provider returns an empty success or malformed receipt
- **WHEN** receipt verification fails
- **THEN** the action remains unknown and success-dependent work stops

### Requirement: Reauthorize actions at the gateway
Actions SHALL require current database role permission even when skip_rbac is requested. External mail SHALL require a fresh requester authorization scope bound to the approved frozen calls; admin role alone SHALL NOT bypass it.

#### Scenario: Direct invocation supplies only an approval flag
- **WHEN** the caller has no verified approval execution scope
- **THEN** the gateway refuses before dispatch

### Requirement: Keep incomplete recovery explicit
Missing compensation evidence SHALL fail closed. Queue recovery, durable Saga compensation and approval state transitions remain separate tasks; offline doubles SHALL NOT close live acceptance.

#### Scenario: Only offline checks pass
- **WHEN** the C12 increment is delivered
- **THEN** live acceptance, C10 fencing and C18 integration remain open and the next item waits for confirmation
