## ADDED Requirements

### Requirement: CRM 工具真实接入必须保证契约一致与写操作幂等

启用真实 CRM 提供方时，`query_customer`、`query_order`、`create_crm_task` 三个工具 SHALL 通过 HTTP 适配层调用真实 CRM API，返回的 `ToolResult` 结构与 Mock 模式保持一致（字段名与嵌套结构不变）；`create_crm_task` SHALL 携带幂等键发起创建请求，网络重试或审批后重放不得产生重复任务；其 Saga 补偿 SHALL 调用真实 CRM 的删除接口而非仅修改本地状态。

#### Scenario: 真实查询返回与 Mock 一致的结构

- **WHEN** CRM 配置为真实提供方且调用 `query_customer` 或 `query_order`
- **THEN** 系统向 CRM API 发起 HTTP 请求，返回的 `ToolResult.output` 字段结构与 Mock 模式一致，下游 Agent 无需感知差异

#### Scenario: 重复创建请求不产生重复任务

- **WHEN** `create_crm_task` 因超时重试或审批后重放而对同一业务请求发起第二次创建调用
- **THEN** CRM 侧按幂等键去重，不产生第二条跟进任务，工具返回首个任务的结果

#### Scenario: 补偿调用真实删除接口

- **WHEN** Saga 回滚触发 `create_crm_task` 的补偿且 CRM 为真实提供方
- **THEN** 系统调用真实 CRM 的删除接口回滚已创建任务，并记录补偿结果

### Requirement: 邮件工具真实接入必须保留审批前置与补偿降级语义

启用真实邮件提供方时，`send_email_internal` 与 `send_email_external` SHALL 通过 HTTP 适配层调用真实邮件 API；`send_email_external` SHALL 维持审批前置（`requires_approval`）与更严格的角色约束；邮件不可撤销时补偿 SHALL 降级为撤回请求并写入审计事件，不得谎报已撤回。

#### Scenario: 外部邮件真实发送仍需审批

- **WHEN** 邮件配置为真实提供方且非经理/管理员角色发起 `send_email_external`
- **THEN** 系统按既有审批流要求人工审批，未通过不执行真实发送

#### Scenario: 外部邮件补偿降级为撤回请求

- **WHEN** Saga 回滚触发真实外部邮件的补偿且邮件系统不支持完全撤回
- **THEN** 系统向邮件系统提交撤回请求并记录审计事件，补偿结果如实标注为「撤回请求已提交」而非「已撤回」

### Requirement: 真实接入必须支持逐系统灰度与 Mock 回退

CRM 与邮件的真实接入 SHALL 支持按系统独立开关切换真实/Mock 提供方；真实系统不可用或契约验证未通过时 SHALL 可回退 Mock 提供方，回退状态 SHALL 在日志中可辨识，且回退不得改变工具的对外契约。

#### Scenario: 逐系统独立切换

- **WHEN** 运维仅将 CRM 切换为真实提供方而邮件保持 Mock
- **THEN** CRM 工具发起真实 HTTP 调用，邮件工具仍返回 Mock 数据，互不影响

#### Scenario: 契约验证未通过时回退

- **WHEN** 真实 CRM 或邮件系统的契约验证未通过或持续不可用
- **THEN** 运维可将对应系统切回 Mock 提供方，回退动作在日志中留有记录，工具对外契约不变
