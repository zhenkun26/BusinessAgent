## Context

现状见 proposal.md 的 Why 与 What Changes。关键约束：项目是单体 FastAPI + LangGraph，基础设施为 PostgreSQL/Milvus/Redis；工具层目前全部为进程内 Mock，worker 只有心跳循环；`documents` 表已存在但仅被反馈候选写入；`approval_requests` 已有 `expires_at` 但无人消费；图结构为 `planner → agent_executor → aggregator → END`，无回边。

## Goals / Non-Goals

**Goals:**
- 让知识文档、审批、重规划、用户、外部系统、测试六条流程各自形成可运行闭环。
- 保持既有 Mock 契约可继续用于演示与离线测试，真实系统接入以配置切换实现。
- 所有新增行为可被单元测试与端到端脚本验证。

**Non-Goals:**
- 不引入独立微服务或消息中间件（Redis 已有，直接复用其队列/锁语义）。
- 不实现完整的多租户、SLA 或计费能力。
- 不将三套外部业务系统的一次性对接细节定死；本轮只定义适配契约、超时重试与配置开关。

## Decisions

### 1. 文档台账（documents）作为知识库运营的事实源

`documents` 表承担文档元数据与状态的唯一事实源：ingest 在向量写入成功后同步 upsert 台账；反馈候选以 `draft` 写入同一张表；审核 API 只改状态，审核通过时再触发向量入库。前端文档页改接真实台账接口。

备选：新增独立审核表。否决：同一实体拆两张表会引入同步与一致性成本，现有表结构已够用。

### 2. 降级链第三级用 PostgreSQL tsvector + 命名空间过滤

在 `documents` 表增加 `search_vector` 列（或迁移时建立表达式索引），降级链第三级改为 `ts_rank` 查询，并在 SQL 中强制 `dept_namespace in (本部门, shared_company)` 与 `access_roles` 过滤。`KeywordRetriever` 的 Milvus 全表扫描保留为第二级。

备选：直接用 `ILIKE`。否决：中文 `ILIKE` 表达力弱；tsvector + `simple` 配置可先用 `to_tsvector('simple', content)` 提供可控的关键词匹配，后续可换中文分词。

### 3. 审批超时用 worker 周期扫描，不引入调度依赖

worker 主循环每 60 秒执行一次幂等 SQL：`UPDATE approval_requests SET status='timeout', decided_at=NOW() WHERE status='pending' AND expires_at < NOW()`，仅对受影响行写审计与通知。通知复用内部邮件工具（Mock 阶段落库，真实阶段走 HTTP）。

备选：PostgreSQL `pg_cron`。否决：pg_cron 需要扩展与额外权限，与现有 worker 部署模型不一致。

### 4. 重规划用图回边 + 轮次计数器，不新增子图

在 `AgentState` 增加 `replan_count` 与 `replan_history`；`aggregator` 后增加条件边：`needs_replan && replan_count < 2` 时回 `planner`（携带 `replan_reason`），否则到 `END`。`planner` 把重规划原因与历史拼进提示，并只针对知识子任务重新分解；`make_initial_state` 每轮从 checkpoint 继承计数，防止跨轮复活。

备选：在 KnowledgeAgent 内部循环重试。否决：无法感知多子任务场景的整体意图，且把控制权放回图更符合 LangGraph 编排模型。

### 5. 外部系统接入采用 BaseTool 抽象 + 提供方开关

在 `BaseTool` 增加 `_call_external` 抽象方法与 `provider` 配置：`mock` 走现有实现，`http` 走 `httpx.AsyncClient` 适配器（统一超时、指数退避重试、Bearer/基本认证从环境变量读取）。CRM、邮件、工单各自实现 `ExternalApiClient`，把 `_execute` 改为“参数校验 → provider 分发 → 标准化 ToolResult”。

备选：为每个工具写独立 HTTP 客户端。否决：会重复超时/重试/错误归一化逻辑。

### 6. worker 任务表直接复用 Redis 简单队列

文档入库、Saga 补偿重试、审计回写三类任务以 JSON 消息写入 Redis List，worker 用 `BLPOP` 消费；失败消息带 `retry_count` 与 `next_retry_at` 回写延迟队列。审计回写改为启动时读取本地缓存目录逐条写入 PG。

备选：引入 Celery。否决：项目当前规模不需要新框架，Redis 已存在，可保持零新增基础设施。

### 7. 用户密码校验用 passlib bcrypt，管理 API 限定 admin

登录逻辑改为 `verify_password`；新增 `POST /admin/users`、`PATCH /admin/users/{id}`（角色/部门/禁用）、`GET /admin/users`；密码只写哈希；seed 脚本补齐初始密码。禁用用户的旧 JWT 通过用户表状态校验拦截（`get_current_user` 查库或校验缓存）。

备选：JWT 黑名单。否决：表状态查询已足够且更简单，禁用即时生效无需额外存储。

### 8. 测试体系用 pytest + pytest-asyncio，依赖注入优先

新增 `tests/` 目录，按模块组织；公共接口测试使用 FastAPI `TestClient` + 替换 DB 依赖与 Mock LLM/HTTP；图与 RAG 测试直接注入 Fake 依赖；`pyproject.toml` 增加 `[tool.pytest.ini_options]`。测试覆盖以“行为契约”为基准，优先补齐本 change 涉及的新接口，再逐步补旧接口。

## Risks / Trade-offs

- documents 台账与 Milvus 双写可能不一致 → 引入 `status=draft/pending` 与审核激活流程，向量写入失败时台账保留失败标记，worker 重试。
- 审批超时扫描与审批决策并发 → 超时 UPDATE 带 `status='pending'` 条件，天然幂等；决策端以状态机校验兜底。
- 重规划回边可能带来额外 LLM 成本与延迟 → 上限 2 轮，且只对 `needs_replan` 为真的知识路径回边。
- 真实 HTTP 接入无法在本机验证 → Mock 为默认提供方，HTTP 适配用契约测试 + 可配置 base URL 的测试桩验证。
- 用户表加密码字段需要 seed 迁移 → 提供一次性迁移脚本，旧种子用户初始化默认密码并提示修改。

## Migration Plan

1. 先合并数据层迁移：`documents.search_vector`、`users.password_hash` 必填、任务队列表（如需要）；迁移脚本保持幂等。
2. 按能力顺序实施：knowledge-operations → approval-lifecycle → agent-replan → user-lifecycle → external-system-integration → quality-testing。
3. 每步保持默认 Mock 配置，端到端演示不回归；worker 独立启动，API 不依赖 worker 可用。
4. 回滚策略：配置开关回退 Mock 提供方；SQL 迁移提供 down 脚本；图回边与超时扫描均可通过配置关闭。

## Open Questions

- 通知渠道是否需要在真实部署时接入短信/企业微信，还是内部邮件足够（实现层面可扩展，不影响规格）。
- 是否要为种子用户设置统一初始密码（如 `ChangeMe123!`）并要求首次登录修改，还是演示环境继续允许任意密码。
