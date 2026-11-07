# C10 isolated acceptance
## ADDED Requirements
### Requirement: Scoped evidence shall not imply complete acceptance
The acceptance runner SHALL identify exactly executed cases, fail when any declared case is missing or fails, and preserve BLOCKED status for unexecuted normative requirements.
#### Scenario: All Phase A cases pass
- WHEN all declared Phase A cases pass with stable candidate binding
- THEN phase_execution is PASS
- AND full_c10_acceptance remains false while any normative matrix gap remains
### Requirement: Real isolated persistence evidence
The runner SHALL use independent processes and actual isolated PG/Redis saver operations with synthetic data, retaining exact source and backend identities.
#### Scenario: Commit acknowledgement is lost
- WHEN a transport proxy drops the actual PG commit acknowledgement
- THEN an independent observer checks durable publication and tokens
- AND the failed client is not treated as rollback or permission to replay
