# CHANGELOG · 版本变更日志

> 版本规则:语义化版本 `主.次.补丁`(X.Y.Z)
> - 主版本:破坏性/里程碑级变更(如生产级基线)
> - 次版本:新增能力(向后兼容)
> - 补丁:缺陷修复
>
> 单一事实源:`enterprise-agent/app/__init__.py` 的 `__version__`;
> 升级时同步 `pyproject.toml`、本文件、核心文档版本头,并打 Git tag `vX.Y.Z`。

## v1.1.0 · 业务闭环补全（2026-08-04）

> 对应 openspec change:`complete-business-processes`(41/41 任务完成)

### 新增能力

- **用户生命周期闭环**：`users` 表 `password_hash` 非空 + `is_active`/username 索引（迁移 004）；admin 用户管理 API（`GET/POST /admin/users`、`PATCH /admin/users/{id}`，重复用户名 409，密码 bcrypt 哈希，创建/变更审计含操作者与旧新值）。
- **外部系统接入**：`BaseTool._call_external` 抽象 + `tool_provider` 开关（mock/http）；统一 HTTP 适配器（httpx 超时、指数退避、401/403 与 5xx 归一化、凭证不入日志）；CRM/邮件/工单 7 个工具接入适配契约（Mock 默认）。
- **后台任务**：Redis List 任务队列（文档入库、Saga 补偿重试），失败带 `retry_count` 与退避重排；worker 启动/周期回写审计本地缓存。

### 修复与验证

- 测试从 36 项增至 **58 项**（新增 HTTP 适配契约、任务队列 fakeredis、用户管理 API、ToolGateway RBAC/注入、Aggregator、Saga 补偿重试等），全部通过。
- W7 工具执行回归 7/7 通过（真实 DeepSeek + PG/Redis）。
- 产品文档/使用案例手册/运维维护手册补齐运营闭环（知识审核、审批超时、重规划、用户管理、worker）章节。
- `openspec validate` 两个 change 均通过。

### 兼容性说明

- 认证默认仍为「密码任意」（`AUTH_REQUIRE_PASSWORD=false`）；外部系统默认 mock（`tool_provider=mock`），切换 http 需配置凭证与 base URL。
- 新增迁移 003/004 均幂等；`init.sql` 已同步。

## v1.0.0 · 生产级基线（2026-08-04）

> Git tag:`v1.0.0`

### 里程碑说明

项目由「演示/学习」状态正式进入「生产级基线」:文档体系、业务闭环能力、安全加固、容器化与部署清单全部就位。

### 新增与变更

- **文档体系基线**（docs/ 六大层 + interview/ + contents.md + README 导航 + ROADMAP/DECISIONS/ISSUES）与 Git 版本控制初始化。
- **业务能力**：知识库运营闭环（documents 台账/审核 API/PG tsvector 降级）、审批生命周期闭环（超时扫描/通知）、Agent 重规划闭环（图回边 ≤2 轮）；测试基座 36 项通过。
- **生产对抗性审查修复**（12 项漏洞）：
  - P0：JWT 默认密钥强校验、登录 bcrypt 密码校验（`AUTH_REQUIRE_PASSWORD` 开关）、默认数据库口令强校验、Redis URL 日志脱敏。
  - P1：`get_current_user` 回查 users 表（禁用/角色变更即时生效）、CORS 白名单、PG checkpointer 改 AsyncPostgresSaver、Milvus 表达式转义、审计本地缓存回写、`X-Request-ID` 全链路、启动环境自检。
- **容器化**：`Dockerfile.prod` 多阶段构建（非 root 65534、HEALTHCHECK、pip 缓存挂载、`INSTALL_ML` 可选），实测 742MB。
- **K8s 清单**：`deploy/k8s/` 8 个清单（Deployment/Service/ConfigMap/Secret/Ingress/HPA/PDB + 双探针）。
- **运维修复**：网站 URL `**` 容错重定向、本机 Redis 端口冲突处理、macOS 一键启动脚本 `启动小A.command`。

### 兼容性说明

- 认证默认仍为「密码任意」（`AUTH_REQUIRE_PASSWORD=false`），生产开启后种子用户初始密码 `ChangeMe123!`，上线前必须重置。
- `/health` 返回 `version` 由 `0.1.0` 升级为 `1.0.0`；旧文档中的期望值已同步更新。
- 既有 API 契约、数据库表结构（新增列均幂等迁移）向下兼容。

## v0.1.0 · 文档基线（2026-08-04）

> Git tag:`v0.1.0`

### 变更摘要

- 初始化 Git 仓库（基线 `b4cca93` → 结构迁移 `cb560d5` → 导航与记录规范化 `0b22b78`）。
- 根目录文档迁入 `docs/` 六大层 + `90-archive`；面试备稿与演示资产独立为 `interview/`。
- 新增 `contents.md`（目录树索引 + 每行注释）、`CHANGELOG.md`、`ROADMAP.md`、`DECISIONS.md`、`ISSUES.md`。
- openspec 规范化：config context 补全、四个文档能力沉淀为主规格。
- 文档版本头统一（版本号 + 校验日期 + commit），交叉引用与 `file:///d:/` 绝对路径修正。
