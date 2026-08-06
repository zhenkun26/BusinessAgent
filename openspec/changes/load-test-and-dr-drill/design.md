## Context

现状见 proposal.md 的 Why。关键事实：压测仅有对抗性审查时的一次 1000 并发冒烟（ISSUES I-11 验证项），ISSUES I-01 仍 open；备份为 `deploy/DEPLOY.md:199-243` 的文档脚本（每日 pg_dump 到 `backups/pg_*.sql.gz` + etcd snapshot 到 `backups/etcd_*.db`，保留 7 天），恢复流程（DEPLOY.md:245-258）从未演练；监控栈为 Compose monitoring profile 的 Prometheus + Grafana（`docker-compose.prod.yml`），`deploy/prometheus.yml` 只配了采集，DEPLOY.md 第六节列了关键指标与建议阈值（P95 > 5s、错误率 > 5% 等，注意这些运维阈值比 SLA 初值宽松，两者口径需在告警规则中区分）；SLA 初值由 `production-readiness-baseline` 承载（p95 ≤ 2s、p99 ≤ 5s、错误率 < 0.5%、RTO ≤ 1 小时、RPO ≤ 24 小时），本 change 只引用不修改。

## Goals / Non-Goals

**Goals:**
- 压测脚本可重复执行、达标判定自动化，报告可作为 SLA 校准的输入。
- 恢复演练真实执行一次并取得实测 RTO/RPO，不纸上谈兵。
- 告警规则可加载、可触发，值班预案与之逐项对应。

**Non-Goals:**
- 不改动业务代码与生产部署架构（不引入 K8s、不改 Compose 服务拓扑）。
- 不做混沌工程/多轮容灾演练（本轮只做一次基线恢复演练）。
- 不引入 Alertmanager 等通知通道的完整落地（预案先行，通知通道作为后续项，见 Open Questions）。
- 不修改 `production-readiness-baseline` 的规格文本（校准结论以书面记录给出，由其归档流程消化）。

## Decisions

### 1. 压测工具首选 k6，脚本落 `enterprise-agent/eval/`

k6 原生支持阶梯加压（stages）、内置 p95/p99/错误率统计与阈值断言（thresholds 未达标即非零退出），与"达标判定自动化"目标直接匹配；vegeta 需要外部脚本拼装统计与判定，作为备选。脚本与报告遵循 eval 目录既有惯例（`eval/run_w5_e2e` 等入口 + `eval/results/` 输出），压测报告写入 `eval/results/` 并在 ISSUES 留引用。

备选：vegeta（ISSUES I-01 计划中提到）。否决：统计与阈值判定需自行拼装，可重复执行性弱于 k6 thresholds。若环境无法安装 k6，允许退回 vegeta 并等效实现判定。

### 2. 恢复演练在隔离副本环境执行，不动生产数据卷

按 DEPLOY.md 恢复流程，将最近备份（`backups/pg_*.sql.gz` + `backups/etcd_*.db`）恢复到一套独立的 Compose 实例（不同 project name/端口/数据卷），全程计时得实测 RTO；RPO 以"备份时点与演练时点的数据差"评估。一致性核查用可执行的机械步骤：就绪检查全通过 + Milvus 集合实体数与备份记录比对 + PG 关键表行数比对。

备选：直接在生产实例上演练。否决：恢复流程要求停 Milvus、覆盖 etcd 数据目录，生产上执行属于高危操作，违背演练目的。

### 3. 告警规则与 DEPLOY.md 运维阈值分层，SLA 口径单独标注

DEPLOY.md 的阈值（P95 > 5s、错误率 > 5%）是运维处置线，SLA 初值（p95 ≤ 2s、错误率 < 0.5%）是质量承诺线，直接混用会让告警要么太吵要么形同虚设。规则文件 `deploy/prometheus-alerts.yml` 中每条告警标注其口径来源；SLA 口径用于趋势观察（warning 级），运维口径用于处置触发（critical 级）。Compose 监控 profile 挂载该规则文件即可加载。

备选：全部按 SLA 初值告警。否决：SLA 是承诺线不是处置线，按 p95 > 2s 立即告警会淹没值班人员（告警疲劳）。

### 4. 值班预案落 `docs/30-guides/运维维护手册.md` 新增章节

遵循文档六大层与单一事实源原则，预案属于操作手册层，不新建平行文档；预案条目与告警规则文件中的告警名一一对应，评审时逐项核对。

## Risks / Trade-offs

- 压测环境（本机/单机 Compose）与真实生产配置差异导致结果失真 → 压测报告必须记录环境配置（CPU/内存/worker 数/模型路径），校准结论注明适用前提。
- 云端 LLM rate limit 成为压测瓶颈上限（ISSUES I-01 预期）→ 报告区分"系统自身瓶颈"与"外部依赖瓶颈"，校准 SLA 时分开处理。
- 恢复演练暴露备份脚本缺陷（如 etcd snapshot 恢复失败、备份已损坏）→ 这正是演练目的；缺陷记入 ISSUES，修复任务追加到本 change 或新开 change。
- 告警规则无通知通道，触发后无人知 → 本轮先保证规则可触发、Grafana 可观察；通知通道（Alertmanager/邮件/webhook）列为 Open Question 与后续项。

## Migration Plan

无代码迁移。执行顺序：压测脚本编写 → 阶梯压测执行与报告 → 恢复演练执行与记录 → 告警规则编写与加载验证 → 值班预案编写 → SLA 校准结论与 ISSUES 回写 → 归档。

## Open Questions

- 告警通知通道选型（Alertmanager + 邮件/企业微信 webhook）未在本轮落地，待通知渠道资源确定后新开 change。
- 压测是否需要覆盖流式对话接口（SSE）的完整生成时长，还是仅以首 token 计？倾向按 SLA 口径以首 token 计、完整时长作参考指标，执行时确认。
