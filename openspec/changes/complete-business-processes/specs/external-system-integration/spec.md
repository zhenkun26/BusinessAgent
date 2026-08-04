## Purpose

为 CRM、邮件、工单工具提供真实 HTTP 接入能力，同时保留 Mock 回退，并让文档入库、Saga 补偿重试与审计回写由后台 worker 异步完成。

## ADDED Requirements

### Requirement: 工具必须通过 HTTP 适配器调用外部系统

系统 SHALL 为 CRM、邮件、工单工具提供可切换的 HTTP 适配层：启用真实提供方时通过配置的 base URL 发起 HTTP 调用，启用 Mock 时不得发起网络请求；凭证 SHALL 只来自环境变量。

#### Scenario: 启用真实提供方
- **WHEN** 工具配置指向真实业务系统且调用工具
- **THEN** 系统向对应 base URL 发起 HTTP 请求并返回标准化 `ToolResult`

#### Scenario: 启用 Mock 提供方
- **WHEN** 工具配置为 Mock 且调用工具
- **THEN** 系统不发起网络请求，直接返回 Mock 数据

### Requirement: 外部调用失败必须结构化返回

系统 SHALL 为外部 HTTP 调用设置超时与重试；调用失败时 SHALL 返回 `success=false` 的 `ToolResult` 与错误信息，不得抛出未处理异常，且日志不得包含凭证或完整请求体。

#### Scenario: 外部系统返回 5xx
- **WHEN** 外部系统连续返回 5xx 且重试耗尽
- **THEN** 工具返回 `success=false` 并携带超时或服务不可用错误

#### Scenario: 凭证无效
- **WHEN** 外部系统返回 401/403
- **THEN** 工具返回 `success=false`，且日志中不出现凭证内容

### Requirement: 后台 worker 必须执行异步任务

系统 SHALL 由独立 worker 进程消费文档入库任务、Saga 失败补偿重试与审计日志本地缓存回写；任务处理失败时 SHALL 记录错误并按策略重试。

#### Scenario: 文档入库任务被消费
- **WHEN** 文档入库任务进入任务队列
- **THEN** worker 消费任务并完成向量与台账写入，或在失败时留下可重试记录

#### Scenario: Saga 失败补偿重试
- **WHEN** Saga 补偿步骤执行失败
- **THEN** worker 按退避策略重试补偿，并记录最终结果

#### Scenario: 审计缓存回写
- **WHEN** 审计日志因数据库不可用写入本地缓存
- **THEN** worker 在数据库恢复后回写缓存并标记已同步
