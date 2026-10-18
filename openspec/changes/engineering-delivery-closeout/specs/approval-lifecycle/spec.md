## MODIFIED Requirements

### Requirement: 待审批单必须支持超时自动流转
The system SHALL expire pending and approved_pending_reauth requests with missing or
elapsed deadlines using database time. Decisions and execution claims SHALL be conditional
and serialized. A claimed execution SHALL NOT be reset or replayed when its observation
deadline expires; it SHALL remain unknown until retained evidence proves its result.

#### Scenario: Decision, resume and timeout race
- **WHEN** competing requests act on the same approval
- **THEN** only a valid status/deadline transition commits, and no expired unclaimed request executes

### Requirement: 审批状态迁移必须记录审计
The system SHALL atomically record safe audit events with approval transitions. Executed
SHALL require complete durable success evidence. Failure, compensation and unknown states
SHALL be distinct in API/UI/audit. Batch decisions SHALL commit all accepted transitions
or none; duplicate IDs SHALL be rejected before mutation.

#### Scenario: Tool failure or interrupted execution
- **WHEN** a tool fails, a Saga compensates, or execution loses its response
- **THEN** the approval reports the corresponding retained outcome and never infers executed from approval or a timeout

#### Scenario: Repeated resume
- **WHEN** a claimed approval is resumed again
- **THEN** the existing state/evidence is returned without a new execution or operation identity

### Requirement: 发起人必须收到审批结果通知
The system SHALL attempt a result notification only after the state transaction commits.
Notification delivery failure SHALL NOT roll back or relabel the business outcome; delivery
status SHALL be recorded truthfully, without claiming that a missing message was sent.

#### Scenario: Notification failure after commit
- **WHEN** notification transport or audit reporting fails after the approval transition commits
- **THEN** the API retains the committed outcome and does not repeat the tool execution
