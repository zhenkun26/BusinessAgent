## Why

当前系统的核心对话闭环已经完整，但支撑企业运营的流程仍是半闭环：知识候选无法审核入库、审批超时无人处理、`needs_replan` 只标记不执行、业务系统全部是 Mock、公共接口没有单元测试。这些缺口让项目停留在演示阶段，无法支撑真实企业运营与上线收尾。W2-W9 与 P1/P2 已全部完成，现在是补齐这些闭环、让系统达到可上线状态的时机。

## What Changes

- 知识库运营闭环：入库同步写入 `documents` 表；新增知识候选审核、激活、拒绝 API；前端知识库文档改为真实数据；实现 PG LIKE/tsvector 兜底，让检索降级链真正三级可用。
- 审批生命周期闭环：后台扫描 `expires_at`，待审批超时后自动流转到 `timeout`；审批通过、超时后通知发起人；审计补齐超时事件。
- Agent 重规划闭环：LangGraph 增加 replan 回边；修正 `needs_replan` 语义，知识覆盖不足时自动补检、换意图或请求澄清，并限制重规划轮数。
- 真实业务系统接入：定义工具层的 `_call_external` 抽象，CRM、邮件、工单通过 HTTP 客户端适配真实 API；后台 worker 实现文档入库任务、Saga 补偿重试、审计本地缓存回写。
- 用户生命周期闭环：补齐密码校验与用户管理 API（注册、禁用、角色调整），替代仅靠 SQL 脚本维护用户。
- 测试闭环：为所有公共接口补齐单元测试，覆盖正常路径、边界与错误路径，Mock 数据库、网络和文件系统，建立可持续运行的测试入口。

## Capabilities

### New Capabilities
- `knowledge-operations`: 文档从录入、审核到激活的完整生命周期，以及检索降级链的真实可用性。
- `approval-lifecycle`: 审批单超时流转、发起人通知与状态机完整性。
- `agent-replan`: 知识覆盖不足时的自动重规划能力与轮次护栏。
- `external-system-integration`: 外部业务系统 HTTP 适配与后台异步任务执行。
- `user-lifecycle`: 用户注册、认证、禁用与角色调整的完整生命周期。
- `quality-testing`: 公共接口单元测试覆盖与测试基础设施。

### Modified Capabilities

<!-- 当前仓库 openspec/specs/ 下尚无已发布规格，本轮全部按新能力处理。 -->

## Impact

- 代码：`app/api/`、`app/rag/`、`app/graph/`、`app/tools/`、`app/security/`、`app/worker.py`、`app/static/index.html`
- 数据：`documents`、`user_feedback`、`approval_requests`、`users` 表结构与迁移
- 依赖：复用已有 `httpx`；新增测试框架依赖（pytest 已在 dev extra 中）
- 系统：worker 进程承担超时扫描与后台任务；前端新增知识库审核入口
