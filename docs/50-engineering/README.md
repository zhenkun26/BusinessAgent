# 50-engineering · 工程文档层

本层提供工程文档索引与跨模块交付契约。实现、部署与操作说明保留在代码目录内；交付基线只定义范围和验收证据，不复制实现说明。

## 索引

| 文档 | 位置 | 用途 |
|---|---|---|
| 当前交付状态 | [delivery-status.md](delivery-status.md) | C25 Git/版本/支持/规格与证据映射；CI FAIL、运行 BLOCKED |
| 最终候选离线验证 | [final-candidate-verification.md](final-candidate-verification.md) | C24 固定入口、候选绑定、C01–C24 映射与阻塞 |
| 规定负载与容量候选 | [capacity-evidence.md](capacity-evidence.md) | C23 冻结计划、混合采集、分项指标与 L01–L16 阻塞 |
| RAG 质量与指标 | [rag-quality.md](rag-quality.md) | C17 冻结语料、固定分母、引用/拒答/权限与运行边界 |
| 分析数据适配 | [analysis-data.md](analysis-data.md) | C16 provider 一致取数、分页快照、权限与确定性统计 |
| 知识发布与索引一致性 | [knowledge-publication.md](knowledge-publication.md) | C15 版本化发布、重试与可见性 |
| 审批执行状态 | [approval-execution.md](approval-execution.md) | C11 条件决策、一次领取与结果核对 |
| Saga 与故障恢复 | [saga-recovery.md](saga-recovery.md) | C13 持久日志、关联补偿与恢复边界 |
| 队列与 worker | [queue-reliability.md](queue-reliability.md) | C14 PostgreSQL 任务、202 契约、恢复与依赖阻塞 |
| 工程交付基线 | [engineering-delivery-baseline.md](engineering-delivery-baseline.md) | 单组织单机支持边界、参考集成、验收证据与工程完成条件 |
| 离线安全验证入口 | [safe-validation.md](safe-validation.md) | C24 前置：允许范围、副作用审查、执行方式、输出状态与限制 |
| 工具幂等与重试 | [tool-operation-safety.md](tool-operation-safety.md) | C12 动作身份、持久发送与回执；真实运行 BLOCKED |
| 保留式恢复候选 | [retained-recovery.md](retained-recovery.md) | 当前版本停写备份、新卷恢复、回退与 D01–D16/RTO/RPO 阻塞 |
| 运行可观测性候选 | [runtime-observability.md](runtime-observability.md) | 就绪、保留式审计、关联、指标、受控告警与 O01–O16 运行阻塞 |
| 浏览器交付候选 | [browser-delivery.md](browser-delivery.md) | 固定本地依赖、角色/UI/API-only 边界与 B01–B16 运行阻塞 |
| 受控 SSO 候选 | [controlled-sso.md](controlled-sso.md) | 独立 IdP、严格验签/PKCE/身份映射与 S01–S16 运行阻塞 |
| 完整参考 HTTP 候选 | [reference-integration.md](reference-integration.md) | 独立服务、隔离部署配方、应用证据与 R01–R20 运行阻塞 |
| 参考业务契约 | [reference-business-contract.md](reference-business-contract.md) | C18 前置：接口、持久操作身份、失败/回执/补偿与未来验收 |
| Checkpoint 持久化 | [checkpoint-durability.md](checkpoint-durability.md) | C10 后端选择、资源生命周期、故障与待验收竞态 |
| 跨进程运行状态 | [cross-process-state.md](cross-process-state.md) | C09 Redis 租约/SSO、Prompt 快照与双进程验收边界 |
| 请求上下文与依赖 | [request-context.md](request-context.md) | C08 任务隔离、历史归属、依赖拒绝与真实验收边界 |
| 检索权限与表达式 | [retrieval-authorization.md](retrieval-authorization.md) | C07 角色/部门/共享区矩阵、编码与真实验收边界 |
| 凭证与 HTML 安全 | [credential-safety.md](credential-safety.md) | C06 凭证生命周期、脱敏、浏览器与历史处置边界 |
| 认证与运行时授权 | [runtime-authorization.md](runtime-authorization.md) | C05 身份故障闭合、生产开关、审批执行权限与验收边界 |
| 会话归属契约 | [session-ownership.md](session-ownership.md) | C04 五入口权限矩阵、错误与事务边界、离线和运行验收 |
| 后端 README | [enterprise-agent/README.md](../../enterprise-agent/README.md) | 快速开始、项目结构、实施进度、技术栈 |
| 生产部署指南 | [enterprise-agent/deploy/DEPLOY.md](../../enterprise-agent/deploy/DEPLOY.md) | 部署架构、备份恢复、监控、安全清单 |

## 约定

- 工程文档随代码维护，不在 `docs/` 复制内容。
- 新增工程文档（如架构图、接口规范）时，先在此层登记索引。
