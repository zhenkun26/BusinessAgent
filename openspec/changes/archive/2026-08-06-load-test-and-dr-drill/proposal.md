## Why

项目 v1.2.0 已归档完结，`production-readiness-baseline` 正在冻结 SLA 初值（可用性、p95/p99、错误率、RTO/RPO）作为达标线，但系统从未验证过能否兑现这些承诺：压测只有对抗性审查时的一次 1000 并发冒烟记录（ISSUES I-01 open），无正式阶梯压测；备份仅为 `deploy/DEPLOY.md` 中的文档脚本（每日 pg_dump + etcd snapshot），恢复流程从未真实演练过，RTO/RPO 无实测数据；`deploy/prometheus.yml` 只采集指标，无告警规则与值班预案，故障只能被动发现。没有这三项实证，上线放行决策等于凭空拍板，因此列为生产上线第一阶段后的 P1 工作。

## What Changes

- 阶梯压测与达标判定：编写 vegeta/k6 阶梯加压脚本（覆盖对话、检索、健康检查等核心接口），按 SLA 初值（核心接口 p95 ≤ 2s、p99 ≤ 5s、错误率 < 0.5%）判定达标，产出压测报告；压测结果必须回访 `production-readiness-baseline` 的 SLA 初值并完成校准闭环，同时关闭 ISSUES I-01。
- 备份恢复演练：按 `deploy/DEPLOY.md` 的备份/恢复脚本真实执行一次 PG + etcd 全量恢复，记录实测 RTO/RPO 与问题清单，结论回写 ISSUES/运维手册。
- 告警与值班预案：为 Prometheus 编写正式告警规则（对齐 SLA 指标与 DEPLOY.md 关键指标表），编写值班预案（告警分级、响应动作、升级路径）。
- 本 change 以脚本、配置、演练记录与文档为主，不改业务代码。

## Capabilities

### New Capabilities
- `performance-resilience`: 阶梯压测达标门槛（对齐 SLA 初值并要求压测后校准）、备份恢复演练（实测 RTO/RPO）、Prometheus 告警规则与值班预案，构成系统性能与容灾能力的可验证基线。

### Modified Capabilities

<!-- 无现有规格的需求变更：SLA 初值由进行中的 production-readiness-baseline 承载，本 change 只引用其概念、不修改其需求。 -->

## Impact

- 脚本与配置：`enterprise-agent/eval/`（压测脚本与报告入口）、`enterprise-agent/deploy/`（prometheus 告警规则文件、备份脚本完善）、值班预案文档落 `docs/30-guides/运维维护手册.md` 或同层新章节。
- 文档：`docs/40-process/ISSUES.md` 关闭 I-01 并记录演练结论；`production-readiness-baseline` 归档前须以本 change 的实测数据校准 SLA 初值。
- 依赖：可能新增 vegeta/k6 作为压测工具（外部二进制，非 Python 依赖）。
- 代码：无业务代码变更。
