# 50-engineering · 工程文档层

本层提供工程文档索引与跨模块交付契约。实现、部署与操作说明保留在代码目录内；交付基线只定义范围和验收证据，不复制实现说明。

## 索引

| 文档 | 位置 | 用途 |
|---|---|---|
| 知识发布与索引一致性 | [knowledge-publication.md](knowledge-publication.md) | C15 版本化发布、重试与可见性 |
| 审批执行状态 | [approval-execution.md](approval-execution.md) | C11 条件决策、一次领取与结果核对 |
| Saga 与故障恢复 | [saga-recovery.md](saga-recovery.md) | C13 持久日志、关联补偿与恢复边界 |
| 队列与 worker | [queue-reliability.md](queue-reliability.md) | C14 PostgreSQL 任务、202 契约、恢复与依赖阻塞 |
| 工程交付基线 | [engineering-delivery-baseline.md](engineering-delivery-baseline.md) | 单组织单机支持边界、参考集成、验收证据与工程完成条件 |
| 离线安全验证入口 | [safe-validation.md](safe-validation.md) | C24 前置：允许范围、副作用审查、执行方式、输出状态与限制 |
| 工具幂等与重试 | [tool-operation-safety.md](tool-operation-safety.md) | C12 动作身份、持久发送与回执；真实运行 BLOCKED |
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
