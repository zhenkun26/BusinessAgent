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
- **THEN** the retained task requires reconciliation without blind replay; full vector/ledger consistency remains C15 acceptance
