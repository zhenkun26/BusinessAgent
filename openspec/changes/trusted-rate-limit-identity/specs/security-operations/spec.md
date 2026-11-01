## ADDED Requirements

### Requirement: Rate-limit identity must be trusted
The system SHALL charge login to connection IP regardless of bearer identity. Other
routes SHALL use a user quota only after bounded application JWT verification.

#### Scenario: Rotating forged login subjects
- **WHEN** one client submits login requests with different forged JWT subjects
- **THEN** every request consumes the same IP quota and excess requests receive 429.

#### Scenario: Valid authenticated subject
- **WHEN** a non-login request has a signed, unexpired application token
- **THEN** its verified subject selects its user quota; route authorization still applies.
