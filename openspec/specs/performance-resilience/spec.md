# performance-resilience Specification

## Purpose
为「Hello，智多星」建立性能与容灾能力的可验证基线：用正式阶梯压测验证并校准 SLA 达标线，用真实备份恢复演练取得实测 RTO/RPO，用告警规则与值班预案把故障从被动发现转为可预期响应。
## Requirements
### Requirement: 系统必须通过阶梯压测验证 SLA 达标线

系统 SHALL 提供可重复执行的阶梯加压脚本，覆盖核心接口（至少包括对话接口、健康检查接口），按阶梯递增并发执行并采集 p95/p99 延迟与错误率；压测达标判定 SHALL 以 `production-readiness` 规格定义的 SLA 目标值为依据（初值：核心接口 p95 ≤ 2s、p99 ≤ 5s、错误率 < 0.5%）；每轮正式压测 SHALL 产出包含并发阶梯、实测指标与瓶颈分析的压测报告，压测后 SHALL 回访并校准 SLA 初值。

#### Scenario: 阶梯压测可重复执行

- **WHEN** 运维人员在测试或生产同构环境执行压测脚本
- **THEN** 脚本按预设并发阶梯自动加压，输出各阶梯的 p95/p99 与错误率，并给出是否达标的明确结论

#### Scenario: 压测未达标时定位瓶颈

- **WHEN** 任一阶梯实测指标超出 SLA 达标线
- **THEN** 压测报告记录超出项与观测到的瓶颈（如云端 LLM rate limit、uvicorn worker、Milvus 内存），作为容量决策依据

#### Scenario: 压测后校准 SLA 初值

- **WHEN** 一轮正式压测完成
- **THEN** 以实测数据回访 `production-readiness` 规格的 SLA 初值，确认达标或提出校准变更，形成书面结论

### Requirement: 系统必须完成备份恢复演练并记录实测恢复能力

系统 SHALL 按现行备份机制（每日 pg_dump + etcd snapshot）至少完成一次真实全量恢复演练，恢复 PostgreSQL 与 Milvus（etcd 元数据）；演练 SHALL 记录实测恢复时间（RTO）与可接受数据丢失窗口（RPO）的实际值，并将结论回写运维文档；恢复完成后系统 SHALL 通过就绪检查且核心数据与备份时点一致。

#### Scenario: 真实恢复演练完成并留档

- **WHEN** 在演练环境用最近一次备份执行全量恢复
- **THEN** 恢复流程完整走通，实测 RTO/RPO 与过程中发现的问题被记录到过程文档

#### Scenario: 恢复后数据一致性核查

- **WHEN** 恢复完成
- **THEN** 就绪检查全部通过，且关键数据（如知识库文档数、会话记录）与备份时点一致

### Requirement: 系统必须配置覆盖关键指标的告警规则

系统 SHALL 维护一份 Prometheus 告警规则文件，至少覆盖：服务不可用、接口延迟（p95 超阈值）、错误率超阈值、关键依赖（PostgreSQL/Redis/Milvus）异常、磁盘与内存资源耗尽；告警规则 SHALL 通过 Prometheus 规则校验并在加载后可触发、可观察。

#### Scenario: 告警规则通过校验并被加载

- **WHEN** 告警规则文件更新后启用监控栈
- **THEN** Prometheus 成功加载规则且无语法/求值错误，规则列表中可见全部告警项

#### Scenario: 指标越限触发告警

- **WHEN** 被监控指标持续越过告警阈值
- **THEN** 对应告警进入触发状态并可被值班人员观察到

### Requirement: 系统必须具备值班预案

系统 SHALL 维护一份值班预案，覆盖告警分级（紧急/重要/提示）、各级别的响应动作与负责人、故障升级路径，并与告警规则逐项对应；预案变更 SHALL 与告警规则变更同步评审。

#### Scenario: 预案可查阅且与告警规则对应

- **WHEN** 值班人员收到任一告警
- **THEN** 值班预案中存在与该告警对应的响应动作与升级路径说明
