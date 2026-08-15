## Purpose

为正式 UAT 之前的 G0 技术彩排提供可复现、可审计且明确隔离真实业务副作用的场景回放能力。

## ADDED Requirements

### Requirement: Replay accepts only a valid synthetic fixture

The replay process SHALL read a JSON fixture that declares `official_uat=false` and `external_side_effects_allowed=false`, and SHALL reject the run when either safety marker is missing or has an unsafe value.

#### Scenario: Safe fixture is accepted

- **WHEN** the runner receives the repository's valid synthetic fixture
- **THEN** it starts a G0 replay and preserves the fixture's declared safety markers in the report

#### Scenario: Unsafe fixture is rejected

- **WHEN** the input fixture declares `official_uat=true` or `external_side_effects_allowed=true`
- **THEN** the runner exits unsuccessfully and does not produce a passing report

### Requirement: Replay validates referential and coverage integrity

The replay process SHALL validate that scenario references resolve to declared entities, that required roles and namespaces are represented, and that all planned UAT scenario identifiers are present exactly once.

#### Scenario: Complete fixture passes integrity checks

- **WHEN** all scenario references resolve and the fixture covers the required entity sets
- **THEN** the integrity check is reported as passed

#### Scenario: Broken reference is surfaced

- **WHEN** a scenario references an unknown customer, document, approval, session, or user
- **THEN** the affected check is reported as failed with the scenario identifier and missing reference

### Requirement: Replay evaluates scenario-level safety assertions

The replay process SHALL evaluate each scenario independently and SHALL verify, at minimum, namespace access roles, approval state coverage, synthetic email domains, absence of requester tokens, and absence of real external side effects.

#### Scenario: Scenario checks pass

- **WHEN** a scenario's actor, data references, approval records, and safety markers satisfy the fixture contract
- **THEN** the scenario receives a passing result with its referenced entity identifiers

#### Scenario: Scenario safety violation is isolated

- **WHEN** one scenario contains an unauthorized namespace reference or unsafe side-effect marker
- **THEN** that scenario is marked failed while other scenarios retain independent results

### Requirement: Replay emits distinguishable evidence

The replay process SHALL emit a machine-readable JSON result and a human-readable Markdown summary containing the fixture identifier, execution mode, timestamp, per-check status, failure details, and an explicit statement that the result is not formal UAT or release evidence.

#### Scenario: All checks pass

- **WHEN** the fixture passes all integrity and scenario checks
- **THEN** the command exits successfully and the report states `G0 technical rehearsal` with formal UAT status remaining pending

#### Scenario: Any check fails

- **WHEN** one or more checks fail
- **THEN** the command exits unsuccessfully, preserves failure details in both report formats, and never labels the run as formal UAT passed
