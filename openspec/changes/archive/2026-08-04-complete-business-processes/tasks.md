## 1. 知识库运营闭环

- [x] 1.1 编写幂等迁移：`documents` 表补充 `search_vector` 与审核字段（`reviewed_by`/`reviewed_at`/`reject_reason`），并给 `document_id` 建唯一索引
- [x] 1.2 改造 `app/rag/ingest.py`：向量写入成功后同步 upsert `documents` 台账（active），写入失败保留失败标记并可重试
- [x] 1.3 实现 `KeywordRetriever` 第三级：PostgreSQL tsvector 查询，强制 `dept_namespace in (本部门, shared_company)` 与 `access_roles` 过滤
- [x] 1.4 新增知识候选审核 API：`GET /admin/knowledge-candidates`、`POST /admin/knowledge-candidates/{id}/approve`、`POST /admin/knowledge-candidates/{id}/reject`，仅 admin 可用
- [x] 1.5 审核通过时触发向量入库并将候选置为 active；拒绝时记录 `reject_reason` 并置为 rejected
- [x] 1.6 新增文档台账 API（`GET /admin/documents`），前端知识库文档页改为调用真实接口并渲染 draft/active/rejected 状态
- [x] 1.7 为降级链与审核接口补充单元测试（见第 6 组），并更新使用案例手册中知识库运营流程

## 2. 审批生命周期闭环

- [x] 2.1 worker 新增周期扫描任务：每 60 秒将 `status='pending' AND expires_at < NOW()` 的审批单幂等更新为 `timeout`
- [x] 2.2 超时流转写入审计事件（操作者=system），并触发发起人通知
- [x] 2.3 实现审批结果通知：`executed`/`rejected`/`timeout` 时向发起人发送内部邮件或站内消息（复用内部邮件工具）
- [x] 2.4 校验审批状态机：已处理的审批单不可重复超时，`approved_pending_reauth` 不参与超时扫描
- [x] 2.5 补充审批超时与通知的单元测试，并更新运维维护手册

## 3. Agent 重规划闭环

- [x] 3.1 在 `AgentState` 增加 `replan_count` 与 `replan_history`，初始化为 0/空，断点恢复时正确继承
- [x] 3.2 图结构增加回边：`aggregator` 后条件边，`needs_replan && replan_count < 2` 时回到 `planner`
- [x] 3.3 `planner` 消费 `replan_reason` 与 `replan_hint`：覆盖不足时只重排知识子任务，失败路径带上下文请求澄清
- [x] 3.4 达到 2 轮上限时强制进入 `END`，响应包含 `needs_replan` 与 `replan_reason`
- [x] 3.5 修正 `needs_replan` 语义：知识无结果、部分覆盖、分析无数据按规格统一传播
- [x] 3.6 补充重规划成功、耗尽、跨轮不残留的单元测试与端到端验证

## 4. 用户生命周期闭环

- [x] 4.1 迁移 `users` 表：`password_hash` 必填、补充 `is_active` 索引；为种子用户初始化密码哈希
- [x] 4.2 登录接口改为校验密码（bcrypt），错误/缺失密码返回统一 401
- [x] 4.3 `get_current_user` 校验用户 `is_active`，禁用用户旧令牌立即失效
- [x] 4.4 新增 admin 用户管理 API：`GET /admin/users`、`POST /admin/users`、`PATCH /admin/users/{id}`（角色/部门/禁用），用户名重复返回 409
- [x] 4.5 用户创建与角色调整写入审计日志（操作者、旧值、新值、时间）
- [x] 4.6 补充密码校验、禁用、角色即时生效的单元测试

## 5. 外部系统接入与后台任务

- [x] 5.1 `BaseTool` 增加 `_call_external` 抽象与 `provider` 配置开关（mock/http）
- [x] 5.2 实现统一 HTTP 适配器：httpx 超时、指数退避重试、401/403 与 5xx 错误归一化为 `ToolResult`
- [x] 5.3 CRM 工具接入适配器：查询客户、查询订单、创建任务；凭证从环境变量读取
- [x] 5.4 邮件工具接入适配器：内部/外部邮件发送与补偿；Mock 保持为默认提供方
- [x] 5.5 工单工具接入适配器：创建/更新工单
- [x] 5.6 worker 实现三类异步任务：文档入库队列、Saga 补偿重试、审计本地缓存回写（Redis List + BLPOP，失败带重试计数与退避）
- [x] 5.7 补充 HTTP 适配契约测试（测试桩服务）与 worker 任务处理测试

## 6. 质量测试闭环

- [x] 6.1 建立 `tests/` 目录与 pytest 配置，接入 `pytest-asyncio`，确认离线可运行
- [x] 6.2 建立公共测试基座：DB 依赖替换、Mock LLM、Mock HTTP、临时目录 fixture
- [x] 6.3 为本 change 新增的审核、审批超时、重规划、用户管理、外部适配接口补齐正常/边界/错误路径测试
- [x] 6.4 为既有核心接口补齐单元测试：auth/chat/approval API、KnowledgeAgent、AnalysisAgent、ExecutionAgent、ToolGateway、RAG 检索与图节点
- [x] 6.5 测试命名统一为 `test_should_<behaviour>_when_<condition>`，结构使用 Given-When-Then
- [x] 6.6 在 `pyproject.toml` 增加覆盖率命令，CI/本地文档记录测试运行方式

## 7. 联调、文档与收尾

- [x] 7.1 全量运行 pytest 与 W5-W9 eval 脚本，确认无回归
- [x] 7.2 更新产品文档：业务流程补充知识库审核、审批超时、重规划、用户管理四段
- [x] 7.3 更新使用案例手册与运维维护手册：新增运营审核、超时处理、用户管理、worker 启动说明
- [x] 7.4 `openspec validate` 通过，等待归档

> 开放决定（实现时按默认值执行，不阻塞规划）：通知渠道先走内部邮件，后续可扩展站内消息；种子用户统一初始化密码并允许首次登录修改，演示环境保留任意密码兼容开关。
