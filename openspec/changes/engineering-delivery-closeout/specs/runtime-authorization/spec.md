## ADDED Requirements

### Requirement: Fail-closed current identity
Protected requests SHALL validate a signed JWT with a nonempty bounded subject and
required finite expiry. With database checks enabled, missing, disabled or invalid-role
accounts SHALL return 401 and identity-store failures SHALL return a fixed 503 without
falling back to token claims. Current database role and department SHALL take precedence.
The explicit token-only development option SHALL be rejected outside development.

#### Scenario: Identity-store outage and recovery
- **WHEN** a signed token is presented while the identity store is unavailable
- **THEN** authentication returns 503 without downstream work, and after recovery an
  active account is resolved using its current role without restarting or caching denial

#### Scenario: Invalid credentials or revoked identity
- **WHEN** credentials are missing, malformed, expired, forged, or belong to a deleted,
  disabled or invalid-role account
- **THEN** authentication denies access without exposing credentials or database errors

### Requirement: Production authentication configuration
Production API and worker startup SHALL require password verification and database
identity checks before model initialization, database startup or queue consumption.

#### Scenario: Unsafe production flags
- **WHEN** either AUTH_REQUIRE_PASSWORD or AUTH_CHECK_DB is false in production
- **THEN** both entry points refuse startup with a configuration error

### Requirement: Approval execution reauthorization
Single decision, batch decision and resume SHALL resolve active requester and approver
identities from the database and check their current permissions before executing tools.
Resume SHALL use the original recorded approver and the requester's newly supplied bearer
token. Execution SHALL verify token signature, expiry and requester subject binding.
Identity rows SHALL be locked in stable order for the execution transaction. Authorization
failures SHALL not invoke tools, mutate that approval, or send result notifications.

#### Scenario: Revocation while waiting
- **WHEN** either participant is disabled/deleted or loses the required role/tool permission
- **THEN** execution is denied, including resume after a previous valid decision

#### Scenario: Requester confirmation after approval
- **WHEN** both accounts and permissions remain valid and an approval is granted
- **THEN** the request enters approved_pending_reauth without executing tools;
  C06 requires an explicit requester resume with a current subject-bound token

#### Scenario: Authorized execution
- **WHEN** the requester resumes and both current identities, permissions and the
  requester-bound token are valid
- **THEN** tools execute as the requester using current database role and department;
  the approver's privileges never replace the requester's permissions

### Requirement: Evidence and scope boundary
C05 SHALL distinguish offline injected-dependency checks from real JWT-library, HTTP/SSE,
PostgreSQL locking and Linux acceptance. Runtime acceptance SHALL remain BLOCKED until
measured in the isolated environment. C06 credential persistence and C11 atomic claims,
idempotency and execution state remain separate increments.

#### Scenario: Offline increment delivery
- **WHEN** the offline implementation is committed
- **THEN** C05 remains open, no release is allowed, and C06 waits for explicit confirmation

### Requirement: Rate-limit identity is cryptographically verified
Rate limiting SHALL use the shared identity-token validator without relaxing expiry before
selecting a user quota. Unverified, invalid or oversized bearer credentials SHALL retain
the source-IP quota. Login-prefix requests SHALL always use the source-IP quota regardless
of bearer contents. Quota selection SHALL NOT replace current-account or role authorization.

#### Scenario: Forged subjects rotate or target another user
- **WHEN** one source supplies unsigned, wrongly signed, expired or malformed identity tokens
- **THEN** the requests share its anonymous quota, cannot select the victim user bucket and
  reach no protected route without the original business authentication

#### Scenario: Verified users and login attempts
- **WHEN** valid identities share a source IP or attach tokens to login attempts
- **THEN** non-login user quotas remain separate, login quotas remain source-bound, and
  disabled accounts or identity-store failures still deny protected work with 401 or 503

#### Scenario: Bounded credential parsing
- **WHEN** the Authorization value exceeds 8192 characters or a token lacks valid sub/exp
- **THEN** it cannot select a user bucket; oversized values are rejected before quota JWT decoding
  and errors do not expose credentials
