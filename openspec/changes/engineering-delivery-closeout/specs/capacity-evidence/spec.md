## ADDED Requirements

### Requirement: Freeze the workload before execution
The runner SHALL bind candidate images/schema, hardware, model profile, dataset, roles,
arrival rate, concurrency, business mix, sample minimum and thresholds in a reviewed plan.

#### Scenario: Draft or changed plan
- **WHEN** required identities are missing or the approved digest differs
- **THEN** no network call occurs and execution remains BLOCKED

### Requirement: Preserve scheduled work and actual business outcomes
The runner SHALL cover Q&A, analysis and approved reference business for at least 30 minutes,
with a bounded open-loop schedule, fresh sessions, no health throughput and no business retries.

#### Scenario: A slot is dropped or HTTP 200 has no valid business result
- **WHEN** a launch is missed, rate limited, interrupted or semantically unconfirmed
- **THEN** retain it in the denominator and never count it as successful business throughput

### Requirement: Keep timing and acceptance claims distinct
The reporter SHALL separate endpoint full response, stream first token, workflow duration
and unavailable queue/execution observations, and report per-kind p95/p99/errors.

#### Scenario: Incomplete evidence or threshold breach
- **WHEN** evidence is missing or a frozen threshold is exceeded
- **THEN** report BLOCKED or FAIL respectively, without silently relaxing limits, replacing
  TTFT with headers, or declaring maximum capacity, enterprise SLA or production approval

### Requirement: Retain isolated evidence without sensitive content
The runner SHALL use fixed internal targets, transient credentials, explicit execution,
fresh output paths and bounded responses; it SHALL NOT provision, delete or replay mutations.

#### Scenario: Interrupted run
- **WHEN** a process stops before all scheduled work and drain complete
- **THEN** retain available records and require missing work to remain visible and unaccepted
