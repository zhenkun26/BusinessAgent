## ADDED Requirements

### Requirement: Credentials remain transient
Application bearer credentials SHALL NOT enter new approval records, graph inputs
or checkpoint state. Approval decisions SHALL only record approval and request
fresh requester confirmation; execution SHALL use a current requester-bound bearer
and recheck both participants as required by C05. Legacy stored tokens SHALL NOT
be read or refreshed for execution.

#### Scenario: Approval followed by requester confirmation
- **WHEN** an authorized manager approves individually or in a batch
- **THEN** the request enters approved_pending_reauth without tools; only the
  requester may resume with valid current credentials and a still-authorized approver

#### Scenario: Legacy record contains a token
- **WHEN** a legacy approval is decided or resumed
- **THEN** the stored token is ignored, no new reusable token is persisted, and
  historical remediation remains separately authorized and BLOCKED until verified

### Requirement: Diagnostics and persistence redact credentials
Audit database/local-cache writes and replay, configured application logging,
tracing and external-tool outputs SHALL redact sensitive fields and recognized
credential strings before truncation or serialization. Public exception paths
SHALL use safe errors; HTTP error bodies and URL credentials SHALL NOT be echoed.

#### Scenario: Marker credentials in failures and nested payloads
- **WHEN** synthetic credentials occur in nested objects, summaries, provider errors
  or application exceptions
- **THEN** covered output sinks omit the credentials; audit fallback obeys the same
  policy as database writes, and diagnostic failure does not expose raw objects

### Requirement: Browser credential lifecycle is bounded
Normal browser access tokens SHALL remain in application memory. SSO SHALL use a
single-use tab-scoped handoff consumed and cleared on UI load, never a URL token.
Logout and 401 SHALL clear identity/session state and abort an active stream.
Passwords SHALL not be stored. Reload SHALL require login after handoff consumption.

#### Scenario: Logout, expiry or page reload
- **WHEN** the user logs out, receives 401, or reloads the UI
- **THEN** no reusable application token is recovered from persistent local storage

### Requirement: HTML failures return escaped text
Markdown rendering SHALL sanitize successful output. If renderer or sanitizer is
missing, unsupported or throws, the fallback SHALL HTML-escape the original text
before it reaches v-html.

#### Scenario: Unavailable sanitizer or malicious input
- **WHEN** HTML/script/attribute injection is rendered with a missing or throwing library
- **THEN** fallback displays text, never executable raw HTML

### Requirement: Offline evidence does not close live acceptance
C06 SHALL retain real JWT/PostgreSQL/API/SSE/Linux/browser and historical-remediation
BLOCKED states until measured. C07 SHALL wait for user authorization.

#### Scenario: Offline candidate delivered
- **WHEN** static and injected tests pass
- **THEN** only the offline increment is complete and release_allowed remains false
