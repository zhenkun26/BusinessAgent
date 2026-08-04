## Purpose

补全审批单的完整生命周期：待审批单超时自动流转、发起人收到结果通知、所有状态迁移留下可审计记录。

## ADDED Requirements

### Requirement: 待审批单必须支持超时自动流转

系统 SHALL 在后台扫描 `approval_requests` 中状态为 `pending` 且超过 `expires_at` 的审批单，并将其状态流转为 `timeout`；该流转 SHALL 幂等，只允许发生一次，且不得影响其他状态。

#### Scenario: 待审批单超过截止时间
- **WHEN** 审批单保持 `pending` 且超过 `expires_at`
- **THEN** 审批单状态变为 `timeout`，审批人无法再对该单执行批准或拒绝

#### Scenario: 已处理审批单不会重复超时
- **WHEN** 审批单已流转为 `executed` 或 `rejected`
- **THEN** 后台扫描不会改变其状态，也不会追加超时记录

### Requirement: 发起人必须收到审批结果通知

当审批单进入 `executed`、`rejected` 或 `timeout` 终态时，系统 SHALL 通过内部通知（内部邮件或站内消息）告知发起人审批单号与结果。

#### Scenario: 审批通过并执行
- **WHEN** 审批人批准且工具执行成功
- **THEN** 发起人收到包含审批单号与执行结果的通知

#### Scenario: 审批超时
- **WHEN** 后台将待审批单流转为 `timeout`
- **THEN** 发起人收到审批单已超时且未执行的通知

### Requirement: 审批状态迁移必须记录审计

系统 SHALL 为审批单每一次状态迁移（`pending` 到 `executed`、`rejected`、`approved_pending_reauth`、`timeout`）写入审计事件，包含审批单号、操作者、新状态与时间。

#### Scenario: 后台超时迁移产生审计记录
- **WHEN** 后台将审批单流转为 `timeout`
- **THEN** 审计日志中出现该审批单的超时事件，操作者标记为系统

#### Scenario: 人工审批迁移产生审计记录
- **WHEN** 审批人批准或拒绝审批单
- **THEN** 审计日志记录审批人身份、决策与新状态
