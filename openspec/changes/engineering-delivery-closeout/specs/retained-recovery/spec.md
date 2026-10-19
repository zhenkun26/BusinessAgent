## ADDED Requirements

### Requirement: Recovery execution requires a reviewed isolated plan
The recovery entry SHALL default to planning and bind execution to a plan digest, exact isolated
project, current schema and complete sanitized source inventory.

#### Scenario: Source state or plan changes
- **WHEN** image, container, writable mount, schema or plan identity differs
- **THEN** execution refuses before stopping services or writing a target volume

### Requirement: Cold backups retain complete coordinated state
The backup SHALL include all project named volumes, reject unknown writers and capture only
while source containers are stopped. Partial output SHALL never be labelled complete.

#### Scenario: Backup fails after some containers stop
- **WHEN** a stop, copy or verification fails
- **THEN** all originally running containers are independently attempted for resumption and all assets remain retained

### Requirement: Restore never overwrites existing state
Restoration SHALL verify archive integrity and safe members before writing only to never-existing
target volumes. Existing source and target assets SHALL not be removed or replaced.

#### Scenario: Malicious archive or existing destination
- **WHEN** content hashes, member paths/types, schema or target identity are invalid
- **THEN** restore refuses without writing target data or running application services

### Requirement: Recovery measurements and rollback remain evidence bound
A restored filesystem SHALL not imply application recovery, exactly-once external effects,
RTO/RPO compliance or compatible image/schema rollback.

#### Scenario: Offline verification or byte restore alone succeeds
- **WHEN** no isolated current-version functional recovery has completed
- **THEN** D01–D16 and prior runtime gates remain BLOCKED, C10 stays open and C22 is not closed
