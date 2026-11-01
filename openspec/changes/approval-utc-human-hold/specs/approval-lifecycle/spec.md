## ADDED Requirements

### Requirement: trusted deadline and human hold
New approvals SHALL have a server-owned immutable contract and 24-hour UTC contract. Missing, altered, expired or unsupported contracts SHALL NOT dispatch tools. Legacy records SHALL remain unchanged and SHALL NOT be automatically cloned, renewed, executed or resumed. Only authorized humans may determine next steps; AI output is advice, never an approval or hold release.

### Requirement: retained execution claim
Decision/resume/batch SHALL commit a conditional executing transition before I/O. Failure, cancellation, unknown response or uncertain persistence SHALL NOT permit automatic redispatch. Scanner SHALL NOT expire or reset executing/unknown claims. Approval execution SHALL NOT automatically retry writes or compensate uncertain effects.

### Requirement: truthful evidence
Validation SHALL distinguish provenance/clock checks, DB claim concurrency and provider-side effects. Offline doubles SHALL NOT be described as PostgreSQL or exactly-once acceptance.

### Requirement: immutable dedicated metadata
The dedicated nullable approval_contract column SHALL default to SQL NULL without legacy backfill. UPDATE SHALL NOT change the column, including NULL promotion. New contracts SHALL be constructed by the server INSERT writer, never request/model metadata. Partial or incompatible schema installs SHALL fail atomically; repeated matching installs SHALL preserve data.
