## ADDED Requirements

### Requirement: Session access must use persisted ownership
The chat API SHALL authorize existing sessions against `sessions.user_id` before
reading checkpoint state, recording request audits, starting graphs or changing
session, feedback or draft data. Session identifiers SHALL NOT grant access by
themselves. A missing session, including an orphan checkpoint, and a session owned
by someone else SHALL produce the same 404 status and fixed error detail.

#### Scenario: Cross-user request
- **WHEN** user B supplies user A's session ID to message, stream, history, feedback or cancel
- **THEN** the request returns the same unavailable-session response as an unknown ID, with no graph/checkpoint access, cancellation, audit or business writes

#### Scenario: Ownership store unavailable
- **WHEN** the ownership query fails
- **THEN** the endpoint returns a fixed 503 error without raw database details and without continuing through checkpoint, graph or fallback paths

### Requirement: Administrator exceptions must be explicit per endpoint
Message continuation, streaming, history and feedback SHALL be owner-only, including
for administrators. Cancel SHALL preserve the existing owner-or-administrator
exception. Managers SHALL have no cross-user exception on these endpoints.

#### Scenario: Administrator operations
- **WHEN** an administrator targets another user's session
- **THEN** only cancel is permitted; message, stream, history and feedback return the generic 404 without impersonating the owner

### Requirement: New sessions must be created only by the server
Message and stream SHALL create a session only when `session_id` is omitted or null,
using a server-generated opaque ID within the database's 64-character limit.
An explicit unknown, empty or oversized session ID SHALL NOT create a session.
Feedback SHALL require an existing owned session and SHALL NOT create placeholder
sessions. Existing session ownership SHALL NOT be reassigned by chat operations.

#### Scenario: First message and continuation
- **WHEN** an authenticated user sends a first message without an ID and then continues with the returned ID
- **THEN** the first request creates a row for that user, continuation preserves ownership, and both ordinary and streaming graph calls use the authorized ID

#### Scenario: Concurrent row change or generated ID collision
- **WHEN** ownership changes between lookup and update, or a generated ID conflicts with an existing row
- **THEN** the operation does not overwrite/adopt the other row or start graph work; existing-row updates include the owner predicate and new-row inserts never upsert over a conflict

### Requirement: Authorization must precede streaming and feedback side effects
SSE authorization SHALL complete before a streaming response or producer task is
created. History SHALL check the session before obtaining a checkpointer and use
only authorized metadata for checkpoint-miss fallback. Feedback SHALL hold a shared
row lock while inserting feedback and any draft in the request transaction.

#### Scenario: Negative feedback and history fallback
- **WHEN** an owner submits negative feedback or reads a session without a checkpoint
- **THEN** feedback/draft writes reference that owned session without placeholder insertion, and history returns only its authorized status; a non-owner cannot reach either path

### Requirement: Offline and live evidence must remain distinct
The C04 increment SHALL include adversarial A/B, manager and administrator tests
with isolated dependencies. Real PostgreSQL locking/rollback, HTTP/SSE transport,
authentication and Linux deployment SHALL remain BLOCKED until executed in an
authorized isolated environment. C05 authentication freshness and C09 concurrency
semantics SHALL NOT be claimed complete by C04 ownership checks.

#### Scenario: Offline implementation delivered
- **WHEN** offline tests pass without the real application runtime
- **THEN** only the C04 implementation subtask is complete, the parent acceptance remains open, and C05 is not started
