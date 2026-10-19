## ADDED Requirements

### Requirement: Delivery reconciliation identifies the unreleased candidate honestly
The project SHALL distinguish source version, schema version, Git candidate, image identity,
historical evidence and current acceptance; bilingual entry points SHALL agree on current contracts.

#### Scenario: Offline documentation reconciliation finishes before runtime acceptance
- **WHEN** current documentation, version identities and evidence links are reconciled offline
- **THEN** record that bounded work as complete while C25 and release acceptance remain open; retain runtime blockers and observed CI failures

#### Scenario: A historical manual conflicts with a current contract
- **WHEN** an old example describes automatic initialization, model defaults, state fallback or cleanup
- **THEN** label the historical scope and direct current operations to the reviewed contract without rewriting past test evidence as current acceptance

### Requirement: Final candidate offline receipts preserve evidence boundaries
The project SHALL execute only explicitly reviewed offline entries, bind results to
the candidate and reviewed source identity, and retain skipped/unavailable checks.

#### Scenario: Reviewed sources or candidate change during verification
- **WHEN** the frozen source digest differs or the candidate changes during execution
- **THEN** execution or candidate binding is BLOCKED; stale results cannot qualify the new candidate

#### Scenario: Offline regression succeeds with runtime gates unavailable
- **WHEN** the fixed offline suite completes but runtime, browser, load or recovery evidence is absent
- **THEN** only completed E0/E1 checks are PASS; acceptance stays BLOCKED, C10 stays open and release flags stay false

#### Scenario: Suite fails, skips or reports no tests
- **WHEN** a suite fails, emits malformed/zero-count output, or skips a case
- **THEN** record FAIL or an explicit BLOCKED skip, never count the skipped case as passed, and retain the initial failure and rerun disposition

### Requirement: 工程交付与企业现场验证必须分开判定
项目 SHALL 以单组织、Linux 单机 Compose、真实 PostgreSQL/Redis/Milvus、独立 worker 和一套经过验证的模型 profile 作为首轮工程支持边界，并保留正式企业上线的独立门槛。

#### Scenario: 参考环境验收通过
- **WHEN** 受控参考环境的工程验收全部通过
- **THEN** 结论仅可记为「工程交付验收通过，企业现场生产验证未开展」，不得将 formal_uat、release_evidence 或 release_allowed 改为 true

### Requirement: 差距清单必须具有代码证据和可判定验收
项目 SHALL 在 ISSUES 以 C01–C25 记录现状、源文件、缺口、优先级、日期、状态及验收标准；静态发现与运行验证 SHALL 分别标注。

#### Scenario: 开始处理一个 C 项
- **WHEN** 用户确认推进该项
- **THEN** 实施者先复核该项代码基线与依赖，补齐需要的设计和运行时 delta，再按其验收标准处理，不以历史测试代替当前结果

### Requirement: 交付必须按依赖逐项推进
项目 SHALL 按 ROADMAP 的 S0–S7 及阶段内顺序执行，每个 C 项交付后等待用户确认下一项；完成 S0 SHALL NOT 授权运行时代码修改。

#### Scenario: S0 文档检查完成
- **WHEN** S0 计划、边界、验收标准与索引已落盘
- **THEN** 记录文档验证结果并暂停，所有运行时 C 项仍未完成；不自动启动 S1、推送、合并或部署

### Requirement: 支持声明必须对应可运行的完整链路
项目 SHALL 对部署与模型匹配、权限隔离、会话与跨进程状态、审批幂等与恢复、知识与分析数据、参考集成和 UI 分别保留验收证据，详见 C01–C20。

#### Scenario: 仅有局部测试
- **WHEN** 某能力只有 Mock、单进程或工具层测试
- **THEN** 仅声明该证据覆盖范围，完整应用链路或多进程支持保持未验证，不勾选完整交付验收

### Requirement: 运维与容量必须绑定测量条件
项目 SHALL 按 C21–C23 记录健康/就绪、审计、告警、备份恢复、负载与容量证据，并在执行前固定环境、指标定义和阈值。

#### Scenario: 新候选版本准备验收
- **WHEN** 性能或恢复结果来自旧版本、不同模型或不同部署形态
- **THEN** 将其标为历史参考并执行当前候选复测，不能作为新候选已达标证据

### Requirement: 验收记录必须区分证据等级与失败状态
项目 SHALL 按工程基线记录静态、自动化、完整参考环境、人工交互、企业现场证据；每项使用 PASS、FAIL、BLOCKED 或 NOT_APPLICABLE，并按 C24/C25 绑定最终候选提交。

#### Scenario: 验证工具或外部资源缺失
- **WHEN** OpenSpec CLI、运行环境或企业资源缺失
- **THEN** 相应验证记录 BLOCKED，描述影响，不编造测试结果，不将未执行或文档存在记为 PASS

### Requirement: 参考服务不得替代企业资源确认
项目 SHALL 明确受控 HTTP/IdP 的地址、契约、数据与故障模型，禁止向真实收件人发送验收邮件，并保留既有两个企业相关 change 的阻塞任务。

#### Scenario: 参考集成通过而企业沙箱缺失
- **WHEN** C18/C19 参考链路通过但真实提供方未确认
- **THEN** 只记录工程集成证据，真实 CRM/邮件/IdP 联调、UAT、四周灰度与上线签署继续未完成

### Requirement: 验收必须遵守非破坏性边界
项目 SHALL 在执行验证入口前检查副作用，使用隔离数据与追加式证据，不执行文件系统删除，不触碰既有业务数据，不在证据中记录凭证或私有数据。

#### Scenario: 既有脚本包含自动清理
- **WHEN** 验证或恢复脚本包含删除文件、临时目录或数据卷的行为
- **THEN** 不直接运行该路径，先在授权范围内提供不删除的路径；确需删除时解释原因并交由用户处理

### Requirement: 离线安全入口必须显式允许检查并保护证据
项目 SHALL 提供不新增依赖的离线入口，只执行已审查且源码哈希匹配的函数；验证期间禁止文件修改、网络与子进程；记录输入/源码哈希，输出采用固定字段摘要，证据写入只能创建新文件。

#### Scenario: 源码变更或检查未获允许
- **WHEN** 检查源码哈希不匹配、来源是符号链接或调用者指定任意模块/命令
- **THEN** 在执行前拒绝，不自动更新审查清单，不启动未允许的检查

#### Scenario: 证据目标已存在
- **WHEN** 指定 run ID 已存在或结果路径含符号链接
- **THEN** 拒绝写入且保留原文件，不覆盖、不删除、不自动清理

#### Scenario: 准备度仍阻塞
- **WHEN** 核验函数正常返回但真实 UAT 或发布准备度为 blocked
- **THEN** 分别记录执行成功与业务 BLOCKED，入口返回非零阻塞退出码，正式放行仍为 false

#### Scenario: 输出中可能包含敏感数据
- **WHEN** 原始报告细节或异常消息带凭证、地址或业务文本
- **THEN** 入口只输出受控状态、计数与哈希，不持久化原文或环境变量；失败原因使用固定错误码

#### Scenario: CI collection or regression fails
- **WHEN** the candidate CI cannot collect or pass the complete unit-test suite
- **THEN** repair stale test contracts or implementation defects, retain all tests and security assertions, record exact local and remote verification separately, and keep runtime acceptance blocked
