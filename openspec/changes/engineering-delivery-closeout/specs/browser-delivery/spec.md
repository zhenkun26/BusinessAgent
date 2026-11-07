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


### Requirement: Keyboard actions and input names are available in the UI
The UI SHALL use native keyboard-operable controls, associated/contextual input names,
visible focus and disclosed expanded/current state for the repaired existing flows. Chat
submission MUST preserve composition and modified Enter editing.

#### Scenario: A user operates a disclosure or composes text
- **WHEN** a user activates or dismisses an account/scene disclosure or presses Enter during IME composition
- **THEN** expose the disclosure state, restore its trigger on Escape, and do not submit composing/repeated/modified key events

### Requirement: Focus and announcements follow current work
The UI SHALL restore focus only to intentional/current targets and announce bounded
request outcomes without streaming tokens or elapsed-time updates.

#### Scenario: Focus moves while an asynchronous request ends
- **WHEN** an old request/render callback completes after identity/session/view or focused control changes
- **THEN** preserve the user's current focus and reject stale announcements

#### Scenario: A stream is partial or cancellation is only accepted
- **WHEN** tokens arrive, cancellation is requested, or a stream fails before validation
- **THEN** do not announce per-token content or success; expose requested/incomplete state and announce completion only after validated termination

#### Scenario: Only synthetic static or VM evidence is available
- **WHEN** offline control and event checks pass
- **THEN** keep real browser, assistive technology, zoom/contrast and C20/F2-07 acceptance BLOCKED
