## MODIFIED Requirements

### Requirement: 用户反馈候选必须经审核后才能激活
The application SHALL persist feedback candidates as draft documents. Only an administrator SHALL approve publication. Approval SHALL atomically enqueue a retained job and move the draft to queued, returning HTTP 202 and a stable task ID. A worker SHALL revalidate current authority and frozen input before ingestion; queued acceptance SHALL NOT mean active publication. Only draft candidates SHALL be rejectable.

#### Scenario: 查看待审核候选
- **WHEN** an administrator requests pending candidates
- **THEN** draft titles, content, source sessions and uploaders are returned

#### Scenario: 审核通过候选
- **WHEN** an administrator approves a draft
- **THEN** the document and job are committed together, repeated identical approval returns the original task, and publication status is queried separately

#### Scenario: 审核拒绝候选
- **WHEN** an administrator rejects a draft
- **THEN** it becomes rejected with reviewer/time/reason; rejection of a queued or active document returns conflict

#### Scenario: 入库执行结果不明
- **WHEN** dispatch may have produced a vector or ledger effect
- **THEN** the retained task requires reconciliation without blind replay; the immutable generation remains invisible until complete index acknowledgment and conditional ledger activation; explicit retry reuses its chunk identities

### Requirement: 文档入库必须写入文档台账
The system SHALL persist immutable publication generations before indexing and atomically
activate only a complete acknowledged generation. Retry SHALL reuse frozen chunk identities.
Old, rejected, disabled, partial and unversioned content SHALL be excluded from application
retrieval before reranking or generation using current PostgreSQL visibility and ACL data.

#### Scenario: Index or activation failure
- **WHEN** indexing is partial or ledger activation fails
- **THEN** retained evidence permits explicit idempotent retry while no partial generation is visible

#### Scenario: Concurrent update or deactivation
- **WHEN** a stale writer finishes after a document change or deactivation
- **THEN** conditional activation fails and old chunks cannot become current through that write

#### Scenario: Retrieval store failure
- **WHEN** current publication visibility cannot be established
- **THEN** retrieval fails closed without exposing vector, keyword or cached legacy content
