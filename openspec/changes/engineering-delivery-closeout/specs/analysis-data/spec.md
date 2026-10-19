## ADDED Requirements

### Requirement: Analysis follows the configured CRM provider
Analysis SHALL use the same effective CRM provider as query tools. HTTP failures SHALL
NOT fall back to Mock. All output SHALL identify provider, snapshot, acquisition time,
requested date range and observed date range; Mock SHALL be explicitly labeled.

#### Scenario: Reference records change
- **WHEN** a new valid snapshot contains changed order amounts
- **THEN** Python totals change consistently with query records, without using built-in samples

### Requirement: Complete authorized snapshots precede aggregation
Analysis SHALL refresh current identity, require order permission, fetch customer data
only with customer permission, and validate bounded paginated snapshot identity, row IDs,
types, dates, versions, currency and exact integer minor amounts. Partial, malformed,
expired or inaccessible snapshots SHALL produce fixed errors without partial statistics.

#### Scenario: Pagination fails or authority changes
- **WHEN** any page fails, repeats records or changes snapshot, or caller authority changes
- **THEN** no partial totals or unauthorized customer data are returned

### Requirement: Reports preserve computed facts
Python SHALL compute and render money without binary floating-point aggregation or LLM
rewriting, including multi-agent final answers. Different currencies SHALL remain separate.
Empty input SHALL produce explicit empty status. Unsupported periods or unknown entities
SHALL NOT silently broaden the analysis. Lifetime revenue SHALL NOT be approximated.

#### Scenario: Model attempts to invent a total
- **WHEN** an analysis result reaches final aggregation
- **THEN** its deterministic report is preserved without a numerical rewrite by a model

#### Scenario: No matching orders
- **WHEN** the complete snapshot or requested range contains no orders
- **THEN** output states no data and its scope rather than inventing a successful report
