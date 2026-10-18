## ADDED Requirements

### Requirement: Frontend assets are reproducible and self hosted
The delivery SHALL pin and serve the existing Vue, Marked and DOMPurify browser builds locally,
retain licenses and integrity evidence, and provide visible boot failure and safe text fallback.

#### Scenario: Browser cannot reach a CDN or a renderer is missing
- **WHEN** public CDN access is unavailable or a local renderer fails
- **THEN** the normal UI needs no CDN and untrusted content is escaped on rendering failure

### Requirement: UI authority and asynchronous results follow current identity
The UI SHALL verify local/SSO identity through the current-user endpoint, gate privileged views
and mutations, and discard obsolete responses after logout or conversation changes.

#### Scenario: Role changes or an old response arrives
- **WHEN** current authority is insufficient or an operation belongs to an obsolete identity/session
- **THEN** no privileged action or private view update is accepted by that UI flow

### Requirement: Browser actions report truthful outcomes
The UI SHALL guard duplicate mutations, honor cancelled confirmation, distinguish unavailable
data from empty results, and require a terminal event before presenting a completed stream.

#### Scenario: A response is lost or cancellation is only requested
- **WHEN** an operation is interrupted or the server has only accepted a cancellation request
- **THEN** the UI shows incomplete/unknown/requested state and does not fabricate success or retry writes

### Requirement: Role acceptance is separate from offline checks
The project SHALL document every supported role's UI/API-only workflow, reproducible browser
acceptance steps and evidence requirements. VM/static results SHALL NOT close live acceptance.

#### Scenario: No isolated browser and real backend evidence exists
- **WHEN** only offline checks have passed
- **THEN** C20 stays open and all browser/runtime, UAT and release gates remain blocked
