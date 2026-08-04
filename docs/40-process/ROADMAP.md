# ROADMAP · 里程碑规划

> 进度规划的单一事实源。与 README、openspec change 状态保持一致。
> 更新日期:2026-08-04

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

## 二、进行中

当前无进行中 change；新需求按 openspec 生命周期（propose → apply → archive）重新开启。

## 三、挂起事项（P3，暂不上线）

- [ ] 压测（vegeta/k6）：功能已验证，并发承载未知
- [ ] UAT + 安全测试（含 Prompt 注入攻击面实测）
- [ ] `needs_replan` 语义复查（知识问答偶发误报 true）
- [ ] pymilvus 3.1 迁移（ORM API 弃用，已钉 `>=2.4,<3.1` 防误升级）
- [ ] Windows 开发体验：uvicorn reload 偶发卡死，需手动重启

## 四、远期规划（未排期）

- 真实业务系统对接（CRM/邮件/工单，当前 Mock、契约已对齐）
- 多租户扩展（命名空间 → 租户隔离）
- K8s 部署清单、密钥管理、TLS 全量开启
- 对话压缩（超长会话摘要，历史注入已落地）
- 子任务依赖编排（`SubTask.depends_on` 已定义未消费）
- checkpoint TTL / 清理策略
- `ROLE_NAMESPACES` 接入检索路径（manager 跨部门可见性）
- 长期记忆 `user_memories` 读写（表已建未接）
- token usage 全量采集与成本报表
