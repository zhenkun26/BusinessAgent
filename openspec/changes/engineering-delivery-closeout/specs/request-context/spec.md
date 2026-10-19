## ADDED Requirements

### Requirement: Agent context belongs to one dispatched task
Agents SHALL NOT cache request-bearing instances across dispatches. Execution
context SHALL carry the current authenticated identity, conversation and request
ID without credentials. Send state SHALL contain independent identity/task/history copies.

#### Scenario: Overlapping requests from the same user
- **WHEN** two requests use different conversations or refreshed identity attributes
- **THEN** each task sees only its own context and cannot mutate another task's history

### Requirement: History contains request-bound answers
History SHALL use the invocation checkpointer, validate answer/request identity and
current user/conversation/role/department, and deduplicate by request ID. New entries
SHALL clear inherited answer/replan/error fields. Legacy unbound snapshots SHALL be
skipped without modification. History loading SHALL be bounded and fail to empty.

#### Scenario: Repeated questions and stale answers
- **WHEN** distinct completed requests repeat a question or an unfinished snapshot
  inherits an earlier answer
- **THEN** repeated completed turns remain distinct and the mismatched answer is excluded

### Requirement: Unsupported dependencies reject before fan-out
Any declared dependency or malformed dependency field SHALL reject the entire plan
before agents, tools or approvals execute. Parsing/deduplication SHALL NOT silently
discard dependencies. Rejection SHALL return a fixed terminal explanation with no
replan. Independent tasks SHALL retain fan-out behavior.

#### Scenario: Dependent action after a lookup
- **WHEN** a plan declares that a write needs a lookup result
- **THEN** no subtask runs and the user is asked to submit ordered steps separately

### Requirement: Offline delivery does not close runtime acceptance
C08 SHALL remain open until isolated real LangGraph/API/SSE/JWT/checkpoint acceptance.
Same-session concurrency consistency and general DAG scheduling are outside this increment.

#### Scenario: Offline regressions pass
- **WHEN** C08 is committed locally
- **THEN** live acceptance remains BLOCKED and C08 push and C09 await confirmation
