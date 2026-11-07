# Upstream notice evidence

## ADDED Requirements

### Requirement: Exact upstream notice retention
The source distribution SHALL retain verified complete license texts and applicable original copyright statements for the explicitly mapped tooling and font files.

#### Scenario: Verified generated tooling
- WHEN twelve instruction bodies match the integrity-verified official generator templates under its actual renderer rules
- THEN the mapping identifies the package version, archive integrity, template and renderer hashes, local file hashes and unchanged MIT text.

#### Scenario: Matched font distribution
- WHEN a local font SHA256 equals the font returned by the official stylesheet URL
- THEN the mapping retains that URL, exact byte hash and embedded copyright alongside the OFL notice.

### Requirement: Evidence does not imply blanket acceptance
The notice mapping SHALL preserve unresolved scope and SHALL NOT alter controlled pending statuses or claim complete rights clearance.

#### Scenario: Same font name with different bytes
- WHEN a font has embedded OFL metadata but differs from the official current namesake
- THEN its record remains evidence-incomplete and explains the version/table distinction without alleging infringement.

#### Scenario: Unknown corpus origin
- WHEN the original C17 source evidence remains unknown
- THEN adding unrelated upstream notices does not authorize corpus transmission or clear its rights.
