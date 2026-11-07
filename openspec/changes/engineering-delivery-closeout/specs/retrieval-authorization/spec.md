## ADDED Requirements

### Requirement: Retrieval uses one explicit authorization matrix
All user retrieval paths SHALL require a known role, active documents and matching
document access_roles. Ordinary roles SHALL see only an allowed current department
plus shared_company; missing department SHALL mean shared-only. Invalid nonempty
departments SHALL deny. Managers SHALL access the configured four departments plus
shared_company; administrators SHALL retain wildcard namespaces but not bypass ACL.

#### Scenario: Role and department differ
- **WHEN** a salesperson has a finance department or an unknown role is supplied
- **THEN** retrieval is denied before embedding/storage and no fallback widens access

#### Scenario: Missing department or cross-department manager
- **WHEN** an ordinary role has no department or a manager retrieves knowledge
- **THEN** the ordinary role sees shared-only and the manager sees its explicit role
  namespace grant, subject to document ACL and active state in every backend

### Requirement: All expressions encode values
Milvus dynamic strings SHALL use a shared literal encoder, never raw interpolation.
SQL values SHALL remain bound and role JSON SHALL use serialization. Malformed
values SHALL reject safely. Type constraints SHALL persist across fallback paths;
an empty type list SHALL produce no documents.

#### Scenario: Quotes and operators in values
- **WHEN** department, role, document type, document ID or keyword contains quotes,
  backslashes, wildcard characters or operators
- **THEN** it is rejected or treated as a literal and cannot enlarge authorization

### Requirement: Unauthorized result bodies and metadata never leave retrieval
Backends SHALL fetch and recheck ACL metadata before text scoring and return.
Retriever results SHALL be checked before external reranking and generation;
rerankers SHALL preserve ACL metadata. Missing/malformed ACL metadata SHALL deny.

#### Scenario: Backend returns an unauthorized candidate
- **WHEN** a candidate is inactive, foreign, ACL-denied or lacks required metadata
- **THEN** its body/title/source URL does not reach rerank, model context or citations

### Requirement: Live acceptance remains distinct
Offline tests SHALL not close Milvus/PostgreSQL parser, runtime or API acceptance.
Historical credential remediation and prior runtime blockers SHALL remain unchanged.

#### Scenario: Offline increment delivered
- **WHEN** injected tests pass and C07 is committed locally
- **THEN** C07 live acceptance remains BLOCKED, C08 waits for confirmation and
  formal_uat, release_evidence and release_allowed remain false
