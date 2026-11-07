## ADDED Requirements

### Requirement: Schema changes must use a single versioned entry point
The system SHALL provide an explicit manifest-driven migration command with ordered versions,
SHA-256 checksums, a PostgreSQL transaction and an exclusive advisory lock. Default database
container startup SHALL NOT run application schema or demo seeds. Application startup SHALL
only check the installed schema and SHALL NOT migrate it.

#### Scenario: Empty database or explicit legacy adoption
- **WHEN** an operator explicitly applies the packaged manifest to an empty database or opts into adoption of a supported legacy schema
- **THEN** schema and version records commit together, existing rows remain unchanged, and reapplying the same manifest performs no schema changes

#### Scenario: Failed or conflicting migration
- **WHEN** SQL fails, another migrator holds the lock, or a stored version/checksum differs from the manifest
- **THEN** the command fails with a safe error code and no partial migration is committed

### Requirement: Schema readiness must fail closed
API and worker SHALL require the complete known migration history and expected table/column/index
structure before publishing a database session factory or processing business work.

#### Scenario: Missing or stale schema
- **WHEN** migrations are absent, pending, changed, unknown, or required schema objects are missing
- **THEN** startup fails and database readiness cannot report healthy; credentials and raw database errors are not returned

### Requirement: Bootstrap must not create default accounts or credentials
Schema migration SHALL contain no demonstration rows or shared password backfill. Administrator
creation SHALL be a separate parameterized command with an operator-supplied strong password,
refusing an existing administrator rather than changing that user's credentials. Demo data SHALL
require explicit development-only opt-in, mock business providers, an operator password and an
empty application dataset; a transactionally recorded seed checksum SHALL prevent duplicate rows.

#### Scenario: Default production initialization
- **WHEN** the manifest is applied without an explicit bootstrap or seed command
- **THEN** no accounts or sample business records are inserted

#### Scenario: Unsafe legacy credentials or an existing administrator
- **WHEN** a legacy database has missing passwords, or administrator bootstrap finds an existing admin
- **THEN** the operation refuses to invent/reset credentials, preserves data, and requires operator review

### Requirement: Runtime acceptance must remain evidence-bound
Offline tests SHALL be distinguished from real PostgreSQL empty-database/legacy-upgrade/rollback
and concurrency tests. No current database SHALL be migrated in this increment; C03 SHALL remain
open while isolated runtime acceptance is blocked. Recovery SHALL preserve the original database,
using a reviewed new-database restore or forward fix rather than automatic destructive downgrade.

#### Scenario: Only offline checks are available
- **WHEN** manifest, fake-connection and source-wiring checks pass without a PostgreSQL runtime
- **THEN** only the implementation increment is complete; runtime acceptance remains BLOCKED and C04 is not started
