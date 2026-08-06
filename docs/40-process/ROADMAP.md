# ROADMAP · 里程碑规划

> 进度规划的单一事实源。与 README、openspec change 状态保持一致。
> 更新日期:2026-08-06

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
| 智能体更名 | 2026-08-06 | ✅ | rename-agent-to-zhiduoxing 7/7 归档：「小A」全量更名「智多星」，主规格 11 项 |

## 二、进行中

生产上线导向优化（2026-08-05 启动，候选依据见 `优化方向分析-生产上线-2026-08-05.md`）：

| openspec change | 优先级 | 状态 | 范围 |
| --- | --- | --- | --- |
| ~~production-readiness-baseline~~ | P0 | ✅ 已归档 2026-08-05 | 系统边界 / SLA / 风险操作清单落规格（新能力 production-readiness） |
| ~~rag-answer-quality~~ | P0 | ✅ 已归档 2026-08-05 | 评测集扩充 ≥100 条、答案覆盖率目标 ≥0.85（改 knowledge-operations） |
| load-test-and-dr-drill | P1 | 13/14，待 validate 归档 | 阶梯压测 + 备份恢复演练 + 告警值班（新能力 performance-resilience） |
| security-hardening-plus | P1 | 19/21，待 CI 验证后归档 | 密钥管理、CI 漏洞扫描、越权测试、I-06/I-07 收口（新能力 security-operations） |
| ticket-system-integration | P2 | 已提案 0/16 | 工单真实接入试点：幂等/补偿/审计/联调（改 external-system-integration） |
| crm-mail-sso-integration | P2 | 已提案 0/19 | CRM/邮件/SSO 真实接入（改 external-system-integration + user-lifecycle） |
| uat-and-ga-rollout | P3 | 已提案 0/15 | UAT、灰度、上线门槛检查单（新能力 release-management） |

## 三、挂起事项（P3，暂不上线）

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
