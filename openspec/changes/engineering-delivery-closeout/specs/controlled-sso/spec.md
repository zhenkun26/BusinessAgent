## ADDED Requirements

### Requirement: Controlled issuer is independent and retained
The system SHALL provide a separately deployed HTTPS reference issuer with explicit synthetic
credentials, exact client/redirect bindings, S256 PKCE and atomic single-use expiring codes.
It SHALL retain hashed code/request evidence and require separate operator authorization for
key publication/rotation and scoped faults, without reset, deletion or automatic key generation.

#### Scenario: A code is reused or its binding changes
- **WHEN** an authorization code is expired, consumed, has a wrong client/redirect or PKCE proof
- **THEN** token issuance is denied without minting another identity or deleting evidence

### Requirement: The relying party validates a fixed asymmetric profile
The application SHALL require configured HTTPS endpoints, fixed RS256, a unique matching RSA
signing kid, exact issuer/audience and valid authorized-party, nonce and time claims. It SHALL
reject redirects, malformed or oversized responses and unknown/ambiguous keys without fallback.

#### Scenario: Unknown key or invalid token claims
- **WHEN** a key rotates out of publication, a signature fails or issuer/audience/azp/nonce/time is invalid
- **THEN** SSO fails before local identity provisioning or application token issuance

### Requirement: Mapping preserves exact identity and least privilege
The application SHALL preserve exact bounded issuer/sub values, never truncate identity or
link accounts by email/username. First login SHALL use only the least-privileged default role
and locally configured department; existing role/active state SHALL remain authoritative.

#### Scenario: Remote claims request privilege or collide with another account
- **WHEN** an IdP returns privileged role/department claims, duplicate display names or invalid subjects
- **THEN** no account is linked or elevated from those claims and malformed identity is rejected

### Requirement: Browser authorization binds PKCE to shared single-use state
The application SHALL bind state, nonce and PKCE verifier in shared expiring storage and consume
it once after cookie/state validation. Failure SHALL NOT weaken local password authentication.

#### Scenario: Callback crosses processes or repeats
- **WHEN** another API process consumes valid state or a callback replays after consumption
- **THEN** one callback may exchange the bound code and all later callbacks are denied

### Requirement: SSO evidence remains distinct from runtime acceptance
The project SHALL provide a browser/operator acceptance matrix covering success, malformed claims,
state/code replay, expiry, rotation, disabled accounts, collisions and IdP/storage failure.
Offline doubles SHALL NOT close independent issuer/browser/runtime acceptance or enterprise SSO.

#### Scenario: Only offline checks pass
- **WHEN** no real signed token, browser, PostgreSQL/Redis and TLS execution is observed
- **THEN** C19 remains open and all runtime cases, formal UAT and release gates remain blocked
