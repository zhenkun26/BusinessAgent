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

### Requirement: 答案质量必须有可度量的目标值
The evaluation SHALL retain every frozen case and its source provenance. Normal-answer
keyword coverage SHALL use all eligible cases, including zero credit for failed, empty,
skipped or missing answers. A target of 0.85 SHALL NOT mean factual correctness.
Primary and supplemental role controls SHALL have separate explicit denominators.
Citation correctness, no-answer refusal and cross-department negatives SHALL be reviewed
on the accepted C02 profile before quality acceptance; offline doubles SHALL NOT satisfy it.

#### Scenario: Generation failure or omitted case
- **WHEN** generation fails, is skipped, or evidence for an expected case is missing
- **THEN** its row and denominator contribution remain, with zero answer credit and attribution

#### Scenario: Mechanical checks pass
- **WHEN** keywords and citation indexes meet their numerical checks
- **THEN** semantic review and real profile acceptance remain separately required

### Requirement: 低覆盖样本必须做失效模式分析
The evaluator SHALL distinguish retrieval failure, retrieval miss, retrieved-context keyword
gap, generation failure and generation keyword gap per sample. Backend outages SHALL NOT
be counted as correct no-answer refusals. Reported retrieval stages SHALL name the actual
vector, bounded keyword-scan or PostgreSQL fulltext/ILIKE algorithms, not claim BM25.

#### Scenario: Empty knowledge versus unavailable backend
- **WHEN** the backend fails instead of returning a valid empty result
- **THEN** the agent returns a service failure and the evaluator grants no refusal credit

### Requirement: RAG 链路变更必须执行回归评测
RAG changes SHALL preserve the frozen evaluation set and run relevant offline regressions.
Full-corpus runtime regression and semantic review SHALL precede integration acceptance.
Unavailable runtime resources SHALL leave C17 and complete RAG acceptance BLOCKED.

#### Scenario: Offline-only delivery
- **WHEN** injected regression tests pass without the actual C02 services and published corpus
- **THEN** only offline implementation evidence is recorded and whole-item acceptance stays open
