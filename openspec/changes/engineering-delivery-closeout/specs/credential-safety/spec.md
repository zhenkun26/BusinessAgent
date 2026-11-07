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

### Requirement: Covered diagnostics exclude business content
Covered graph, knowledge/execution agent and RAG operational diagnostics SHALL omit raw
queries, history, identity names, subtask descriptions, model responses/reasoning and
exception bodies. Application-owned manual tracing helpers SHALL export only fixed
operation/event names and typed allowlisted metadata, without arbitrary object conversion.
This contract SHALL NOT be represented as repository-wide PII classification or clearance
of business audit, persistence or automatic third-party instrumentation.

#### Scenario: Synthetic content appears in normal and failed model work
- **WHEN** synthetic business markers occur in queries, model responses or exceptions
- **THEN** covered diagnostic outputs omit them while intended model inputs and business results preserve their semantics

#### Scenario: Unknown or malformed manual telemetry attributes
- **WHEN** helpers receive free text, unknown keys, nested objects or invalid metadata types
- **THEN** these values are omitted and approved finite metadata still records without raw exception capture

### Requirement: External processing and retention require separate evidence
The project SHALL document recipients and content categories for model calls, persistence,
audit/replay and backups. Synthetic-only offline evidence SHALL NOT authorize private-data
processing or imply provider no-retention/no-training guarantees, verified data residency,
automated deletion or publication rights.

#### Scenario: Only synthetic offline tests have passed
- **WHEN** transport and logging tests use in-process doubles
- **THEN** private-data admission, provider terms, actual egress/retention and real runtime/full RAG remain BLOCKED, with F2-09 pending and C10 open

### Requirement: Automatic telemetry requires explicit startup admission
Covered application entry points SHALL validate inherited process telemetry before
application dependencies and effective Settings input before clients or model probes.
Default-disabled operation SHALL construct no application exporter or instrumentation.
Only explicit synthetic OTEL mode with a validated collector SHALL admit the retained
project-owned tracing path. Active/malformed unreviewed SDK tracing/export/bootstrap
configuration, conflicting inputs and subsequent environment changes SHALL fail with
fixed errors without configuration values. C21 audit/replay and metrics SHALL retain
their behavior; configuration admission SHALL NOT grant private-data or runtime acceptance.

#### Scenario: An inherited alias or dotenv enables unreviewed tracing
- **WHEN** a process alias, effective settings input or later environment change requests unreviewed tracing
- **THEN** reject before covered client/probe/worker work without echoing values or silently overwriting configuration

#### Scenario: Explicit synthetic reference tracing
- **WHEN** synthetic mode, OTEL enablement and a valid collector are explicitly configured
- **THEN** retain pre-start FastAPI registration and project tracing while audit/metrics continue; reject initialization failure without raw exception output

#### Scenario: Only synthetic offline evidence is available
- **WHEN** configuration and factories pass using recording doubles
- **THEN** real telemetry/privacy/runtime/full RAG remain BLOCKED, F2-09 pending and C10 OPEN
