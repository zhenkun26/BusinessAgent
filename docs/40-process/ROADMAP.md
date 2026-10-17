# ROADMAP · 里程碑规划

> 进度规划的单一事实源。与 README、openspec change 状态保持一致。
> 更新日期:2026-10-17
> 当前主线：C01 配置独立增量 `2a9c364` 已推送，运行验收 BLOCKED；C02 外部模型增量 `42bfc7f` 已推送，真实 API/Linux 验收 BLOCKED；C03 增量 `fc8da91` 已推送，真实 PostgreSQL/API/Linux 验收 BLOCKED；C04 增量 `dbc8236` 已推送；C05 `9f5397c` 已推送；C06 `6955133` 已推送；C07 `ceae708` 已推送；C08 `d81c281` 已推送；C09 `079cd62` 已推送；C10 `a57bd4e` 已推送（此前 166 项离线测试 PASS），真实双进程/Redis/LangGraph/Milvus/JWT/API/SSE/PG/Linux 验收 BLOCKED，浏览器/SSO/历史处置阻塞保留；C10 整项 open，租约到期写入竞态未解决；C18 参考契约前置已完成（文档/规格），完整集成仍 BLOCKED；暂停等待确认，不进入 C12。

<a id="engineering-closeout-stages"></a>
## 当前工程收尾：S0–S7

范围依据：[工程交付基线](../50-engineering/engineering-delivery-baseline.md)。逐项现状与验收唯一记录在 [ISSUES C01–C25](ISSUES.md#engineering-closeout)，任务勾选见 [OpenSpec tasks](../../openspec/changes/engineering-delivery-closeout/tasks.md)。

| 阶段 | 执行顺序 / 依赖 | 阶段出口 | 当前状态 |
| --- | --- | --- | --- |
| S0 冻结范围 | 交付基线、C01–C25、规格、决策与索引 | 文档结构/链接/范围检查；明确验证限制；暂停等待用户确认 | 用户已确认，`05d8d0c` 已推送；CLI 严格校验仍 BLOCKED |
| S1 可复现环境 | C24 安全验证入口前置 → C01 → C02 → C03 | 隔离环境能按文档启动同一候选产物、模型与数据库 | C24 前置完成；C01 配置已修，运行验收 BLOCKED；C02 离线实现已完成，真实 API/Linux 验收 BLOCKED；C03 离线增量 `fc8da91` 已推送，真实 PostgreSQL/Linux 验收 BLOCKED |
| S2 权限与敏感信息 | S1 后，C04 → C05 → C06 → C07 | 会话、身份、凭证、检索边界验收通过后，才进入受控业务写入 | C04 `dbc8236` 已推送；C05 `9f5397c` 已推送；C06 `6955133` 已推送；C07 `ceae708` 已推送，运行验收 BLOCKED；既有浏览器/SSO/历史处置阻塞保留；C08 见 S3 |
| S3 会话与运行状态 | S2 后，C08 → C09 → C10 | 上下文不串用，支持进程数与状态持久化声明符合实测 | C08 `d81c281` 已推送；C09 `079cd62` 已推送；C10 离线增量已完成，真实持久化/双进程/写入竞态验收 BLOCKED |
| S4 执行一致性与恢复 | S3 后，先 C18 参考契约前置，再 C12 → C14 → C13 → C11 | 幂等、队列、Saga 和审批竞争/崩溃验证通过 | C18 契约前置已完成，仅文档/规格；C12 未开始，阶段运行出口未通过 |
| S5 数据与参考集成 | S4 后，C15 → C16 → C17 → C18 完整链路 → C19 | 数据来源一致，质量指标透明，参考 HTTP/IdP 经应用入口通过 | 未开始 |
| S6 用户与运维 | S5 后，C20 → C21 → C22 → C23 | 人工流程、监控/审计、恢复、规定负载测试形成证据 | 未开始 |
| S7 最终候选 | C24 最终回归 → C25 记录收口 → 规格同步/归档检查 | 最终提交/镜像与证据一致，无范围内 P0/P1；严格校验通过 | 未开始 |

**执行规则**：阶段只是分组，每次仅推进用户确认的一个 C 项；完成后交付范围、检查、人工验收与限制，等待下一项确认。C24/C18/C25 的前置部分不计整项完成。若运行时契约变化，先补对应 delta/design 再实施。S0 授权不延伸为 S1 实施、安装依赖、推送、合并或部署授权。

真实企业集成、UAT、安全验收、四周灰度与签署继续由既有两个 active change 管理，不以参考服务替代。**C01 目标环境验收保持 BLOCKED**。用户已明确授权推送 C10 后推进 C18 参考契约前置；C10 已核对推送同名远端分支。C18 前置完成文档/规格后暂停，本次文档推送与下一项 C12 仍需后续确认。S1/S2/S3 运行出口与 C10 租约到期后的写入竞态仍未通过，C10 整项保持 open；本次前置工作不解除阻塞、不授权 S4 运行验收。

本轮验证、限制与交付状态见 [S0 阶段总结](阶段性总结_S0工程交付基线.md)。
最新增量见 [C24 前置阶段总结](阶段性总结_C24安全验证前置.md)；五函数核验不等于完整应用回归。
当前记录：[C01 配置交付](阶段性总结_C01部署产物与入口.md)、[C02 模型依赖与阻塞](阶段性总结_C02模型依赖.md)、[C03 迁移与初始化](阶段性总结_C03数据库迁移与初始化.md)、[C04 会话归属](阶段性总结_C04会话归属校验.md)、[C05 认证与运行时授权](阶段性总结_C05认证失败闭合与运行时授权.md)、[C06 凭证与 HTML 安全](阶段性总结_C06凭证与HTML失败安全.md)、[C07 检索权限](阶段性总结_C07检索权限与表达式编码.md)、[C08 请求上下文](阶段性总结_C08请求上下文与子任务依赖.md)、[C09 跨进程状态](阶段性总结_C09跨进程运行状态.md)、[C10 checkpoint](阶段性总结_C10检查点持久化与故障语义.md)、[C18 契约前置](阶段性总结_C18参考契约前置.md)。

## 一、已完成阶段（历史里程碑）

| 阶段 | 主题 | 状态 | 交付 |
|---|---|---|---|
| W2 | 基础设施 | ✅ | Docker 服务、本地 Embeddings(bge-m3)、配置体系 |
| W3 | RAG + KnowledgeAgent | ✅ | 两阶段检索、三级降级、置信度决策 |
| W4 | 评测体系 | ✅ | eval_set、run_eval、命中率/覆盖率指标 |
| W5 | 多 Agent 并行图 | ✅ | LangGraph Send fan-out、Planner→Executor→Aggregator |
| W6 | Checkpointer 断点恢复 | ✅ | Redis→PG→Memory 三级降级、跨进程恢复、interrupt |
| W7 | ExecutionAgent + 工具 | ✅ | 8 工具、RBAC、Prompt 注入防护、Saga 补偿 |
| W8 | API 层 + 安全 | ✅ | chat/auth/approval、JWT 刷新、批量审批、限流 |
| W9 | 生产化 | ✅ | compose.prod、OpenTelemetry、部署文档、Milvus 真实接入 |
| 整体联调 | 真实基础设施 E2E | ✅ | 17/17 通过，修复 4 个联调 bug |
| P1 | 分析/审批/审计/反馈 | ✅ | AnalysisAgent、审批流打通、审计 6 类事件、反馈循环 |
| P2 | 体验与验证补强 | ✅ | Prompt 版本管理、取消机制、命名空间隔离、sessions 梳理 |
| P2 后续 | 前端与流式 | ✅ | 单文件 SPA、SSE 流式、/metrics、前端 v2/v3、审批进度跟踪 |
| 生产对抗性审查 | 2026-08-04 | ✅ | 12 项漏洞修复、36 项测试、1000 并发 0 失败、生产镜像与 K8s 清单 |
| 业务闭环补全 | 2026-08-04 | ✅ | openspec complete-business-processes 41/41 完成并归档(v1.1.0) |
| 项目归档完结 | 2026-08-04 | ✅ | 两个 change 全部归档、主规格 10 项、v1.2.0 收口 |
| 生产就绪基线 | 2026-08-05 | ✅ | production-readiness-baseline 10/10 归档：边界/SLA/风险清单落规格、checkpoint TTL、token 用量统计、备份脚本 |
| RAG 答案质量 | 2026-08-05 | ✅ | rag-answer-quality 15/15 归档：评测集扩充、答案覆盖率指标与评测脚本 |
| 智能体更名 | 2026-08-06 | ✅ | rename-agent-to-zhiduoxing 7/7 归档：「小A」全量更名「智多星」 |
| 压测与容灾演练 | 2026-08-06 | ✅ | load-test-and-dr-drill 14/14 归档：k6 阶梯压测、备份恢复演练（实测 RTO/RPO）、告警规则与值班预案 |
| 安全加固 | 2026-08-06 | ✅ | security-hardening-plus 21/21 归档：gitleaks/pip-audit/Trivy 三道 CI 扫描、豁免清单、越权测试，主规格 13 项 |
| 工单真实接入试点 | 2026-08-06 | ✅ | ticket-system-integration 16/16 归档：幂等键/补偿真实化/审计回写，stub 沙箱验收 7/7（external-system-integration 规格扩展） |
| G0 UAT 技术彩排回放 | 2026-08-15 | ✅ | uat-replay-harness 9/9 归档：合成 fixture、结构/安全回放器、JSON/Markdown 证据报告 |
| 后端内部简化 | 2026-09-29 | ✅ 已合并并发布 | PR #1 合并为 `2d4bfc1`；Python 3.11/3.13 各 143 项测试通过；仅 FGR-01/FAT-01，OpenSpec 已归档；[交付证据](code-simplification/20260928-backend/cleanup-report.md) |
| CI 镜像发布门禁修复 | 2026-09-29 | ✅ 已合并并发布 | 先扫描后发布同一镜像；主分支 CI `36522224892` 全部通过，GHCR 提交标签与 latest 摘要一致；OpenSpec 已归档，未部署生产；[验证与授权范围](code-simplification/20260928-backend/ci-publication-report.md) |
| 交付收尾与 CI 必需检查 | 2026-09-29 | ✅ 必需检查生效，离线核验完成 | strict 模式绑定三个 GitHub Actions 检查；G0 16/16 通过、GATE-01 自动回归证据就绪；保持真实 UAT/联调/灰度阻塞；[推进记录](交付与离线推进记录-2026-09-29.md) |
| 中英文 README | 2026-10-17 | ✅ PR #3 已合并 | 合并提交 `065bdf7`；中文 README 与完整英文翻译、互链及目录索引；原文档检查见[变更与验证记录](../../openspec/changes/archive/2026-10-17-refresh-bilingual-readmes/tasks.md)，不代表运行验收 |

## 二、进行中

生产上线导向优化（2026-08-05 启动，候选依据见 `优化方向分析-生产上线-2026-08-05.md`）：

| openspec change | 优先级 | 状态 | 范围 |
| --- | --- | --- | --- |
| ~~production-readiness-baseline~~ | P0 | ✅ 已归档 2026-08-05 | 系统边界 / SLA / 风险操作清单落规格（新能力 production-readiness） |
| ~~rag-answer-quality~~ | P0 | ✅ 已归档 2026-08-05 | 评测集扩充 ≥100 条、答案覆盖率目标 ≥0.85（改 knowledge-operations） |
| ~~load-test-and-dr-drill~~ | P1 | ✅ 已归档 2026-08-06 | 阶梯压测 + 备份恢复演练 + 告警值班（新能力 performance-resilience） |
| ~~security-hardening-plus~~ | P1 | ✅ 已归档 2026-08-06 | 密钥管理、CI 漏洞扫描、越权测试、I-06/I-07 收口（新能力 security-operations） |
| ~~ticket-system-integration~~ | P2 | ✅ 已归档 2026-08-06 | 工单真实接入试点：幂等/补偿/审计/联调（改 external-system-integration） |
| ~~fix-vulnerable-runtime-dependencies~~ | P1 | ✅ 已归档，PR #3 已合并 | `492882c` 修复 4 个既有依赖，随 `065bdf7` 合入；既有 CI 证据及限制见[记录](../../openspec/changes/archive/2026-10-17-fix-vulnerable-runtime-dependencies/tasks.md)，不是新收尾基线的验收 |
| engineering-delivery-closeout | P0/P1 | C01 配置已修，运行验收阻塞 | S0/C24 前置已完成；25 项整项验收仍 open，C02 离线实现已完成，真实 API/Linux 验收 BLOCKED；C03 离线增量已推送；C04 `dbc8236` 已推送；C05 `9f5397c` 已推送；C06 `6955133` 已推送；C07 `ceae708` 已推送；C08 `d81c281` 已推送；C09 `079cd62` 已推送；C10 `a57bd4e` 已推送、运行验收 BLOCKED；C18 前置文档已完成；C12 未授权 |
| crm-mail-sso-integration | P2 | 实施中 9/19 | CRM/邮件/SSO 真实接入（配置、SSO 通用流程与文档已完成；外部契约/沙箱待确认） |
| uat-and-ga-rollout | P3 | 实施中 8/15 | UAT、灰度、上线门槛检查单（灰度方案条件评审通过，最短观察期 4 周；UAT 资源核验仍 BLOCKED） |
| ~~fix-prod-image-pip-removal~~ | P1 | ✅ 已归档 2026-08-15 | 修复生产镜像 runner 阶段 pip 清理顺序；CI run 31890705614 已通过 Python 3.11/3.13、生产镜像构建与 Trivy 扫描 |

## 三、挂起事项（P3，暂不上线）

工程收尾的当前执行顺序见本文件顶部 S0–S7；企业现场所需外部输入继续参考 `下一步执行阻塞清单-2026-09-29.md`。正式 UAT、真实外部接入、真实灰度和全量放行均不得跳过前置证据。

- [x] ~~压测（vegeta/k6）~~（✅ 2026-08-05 随 load-test-and-dr-drill 落地：k6 阶梯压测已执行，报告见 `eval/results/`，SLA 初值已回访，I-01 关闭）
- [ ] UAT + 安全测试（含 Prompt 注入攻击面实测）——已由 uat-and-ga-rollout 提案承接
- [x] ~~`needs_replan` 语义复查~~（✅ 2026-08-04 已随重规划闭环落地：知识无结果/部分覆盖/分析无数据按规格传播并触发回边补检 ≤2 轮）
- [ ] pymilvus 3.1 迁移（ORM API 弃用，已钉 `>=2.4,<3.1` 防误升级）
- [ ] Windows 开发体验：uvicorn reload 偶发卡死，需手动重启

## 四、远期规划（未排期）

- 多租户扩展（命名空间 → 租户隔离）
- TLS 全量开启、密钥管理深化（K8s 清单已就绪，CI 已接入 gitleaks/pip-audit/Trivy）
- 对话压缩（超长会话摘要，历史注入已落地）
- 子任务依赖编排（`SubTask.depends_on` 已定义未消费）
- `ROLE_NAMESPACES` 接入检索路径（manager 跨部门可见性）
- 长期记忆 `user_memories` 读写（表已建未接）
- token 成本报表（用量采集已落地，报表未做）
