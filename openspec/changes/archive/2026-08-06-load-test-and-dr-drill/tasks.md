## 1. 阶梯压测

- [x] 1.1 安装/确认压测工具（首选 k6；不可行时退回 vegeta 并等效实现统计与判定）
- [x] 1.2 在 `enterprise-agent/eval/` 下编写阶梯加压脚本：覆盖对话接口与 `/health` 等核心接口，配置并发阶梯与 thresholds（p95 ≤ 2s、p99 ≤ 5s、错误率 < 0.5%），未达标即非零退出
- [x] 1.3 在目标环境执行正式压测，产出压测报告（环境配置、各阶梯实测 p95/p99/错误率、瓶颈分析）写入 `eval/results/`
- [x] 1.4 依据报告回访 SLA 初值：确认达标或提出校准结论（书面记录，供 `production-readiness-baseline` 归档消化），并关闭 `docs/40-process/ISSUES.md` 的 I-01

## 2. 备份恢复演练

- [x] 2.1 确认最近备份可用（`backups/pg_*.sql.gz` 与 `backups/etcd_*.db`，对应 `deploy/DEPLOY.md` 备份脚本产出）
- [x] 2.2 在隔离副本环境（独立 Compose project/端口/数据卷）按 DEPLOY.md 恢复流程执行 PG + etcd 全量恢复，全程计时
- [x] 2.3 一致性核查：就绪检查全通过、Milvus 集合实体数与 PG 关键表行数同备份时点比对，记录实测 RTO/RPO 与问题清单
- [x] 2.4 演练结论回写：实测 RTO/RPO 与发现问题记入 `docs/40-process/ISSUES.md` 与 `docs/30-guides/运维维护手册.md` 备份章节

## 3. 告警规则与值班预案

- [x] 3.1 编写 `deploy/prometheus-alerts.yml`：覆盖服务不可用、p95 超阈值、错误率超阈值、PG/Redis/Milvus 依赖异常、磁盘/内存耗尽；每条标注口径来源（SLA 口径 warning 级 / 运维口径 critical 级）
- [x] 3.2 将规则文件挂载进 Compose monitoring profile 并启动验证：Prometheus 规则校验通过、规则列表可见全部告警项
- [x] 3.3 触发验证：构造至少一条指标越限（如压测期间的延迟/错误率），确认告警进入触发状态且在 Prometheus/Grafana 可观察
- [x] 3.4 在 `docs/30-guides/运维维护手册.md` 新增值班预案章节：告警分级、响应动作、升级路径，与告警规则逐项对应

## 4. 收尾

- [x] 4.1 汇总压测报告、演练记录、告警规则、预案，核对规格四条需求的验收点全部满足
- [x] 4.2 运行 `openspec validate load-test-and-dr-drill --strict` 通过后归档
