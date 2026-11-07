## ADDED Requirements

### Requirement: Approval is separate from execution
The system SHALL record approval without dispatching mutations. Only the original requester, after approval, SHALL explicitly confirm execution against the immutable server-generated trusted contract and current permissions.

#### Scenario: Approver accepts a request
- **WHEN** an authorized approver accepts an active request
- **THEN** the decision is stored without tool dispatch and requester confirmation remains required

### Requirement: Failures require human review
The system SHALL stop remaining actions and retain structured evidence after partial failure or uncertain execution. It SHALL NOT automatically compensate, repeat uncertain mutations or release a human hold upon late receipts.

#### Scenario: A late receipt arrives for uncertain execution
- **WHEN** fresh operation evidence becomes available
- **THEN** evidence is retained for human review while the hold and prohibition on automatic continuation remain
