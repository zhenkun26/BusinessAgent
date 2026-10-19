# CHANGELOG · 版本变更日志

> 版本规则:语义化版本 `主.次.补丁`(X.Y.Z)
> - 主版本:破坏性/里程碑级变更(如生产级基线)
> - 次版本:新增能力(向后兼容)
> - 补丁:缺陷修复
>
> 单一事实源:`enterprise-agent/app/__init__.py` 的 `__version__`;
> 升级时同步 `pyproject.toml`、本文件、核心文档版本头,并打 Git tag `vX.Y.Z`。

## 未发布（Unreleased）

### 当前工程候选（2026-10-19；未发布）

源码版本仍为 **1.3.0**；本节收尾变更不属于历史 `v1.3.0` tag，也未创建新版本/tag/镜像或生产发布。当前交付结论、提交与证据映射见[交付状态](docs/50-engineering/delivery-status.md)。下方日期阶段记录保留当时范围，不作为当前授权或验收状态。

- C01–C03：不可变应用产物与入口、外部模型 profile、显式 checksum 迁移与管理员初始化；当前 schema 要求 v1–v7，应用启动不自动迁移。
- C04–C10：会话归属、运行时授权、瞬时凭证、检索权限与表达式、请求历史隔离、共享协调和固定 checkpoint 后端。**租约到期后的写入 fencing 仍未解决**。
- C11–C14：审批原子领取/过期/结果状态，持久动作身份、保守重试，Saga/HTTP 补偿和 PostgreSQL 队列/worker 候选。
- C15–C20：不可变知识发布、CRM provider 一致的分析快照、RAG 质量口径、独立参考 HTTP/受控 IdP、前端本地分发与身份/异步状态隔离。
- C21–C23：共享保留式审计回写、就绪/指标/告警，当前版本冷备/新卷恢复/回退，以及冻结负载与容量采集候选。
- C24：固定离线清单、源码/候选提交绑定与保留式回执。C25：双语入口、手册、版本/规格身份和交付结论的离线核对；不修改运行代码或创建发布。
- CI 回归修复：更新共享脱敏导入及现行安全契约断言，拆分共享夹具与测试类，避免继承用例在不兼容替身下重复执行；完整本地 pytest 871 tests + 225 subtests PASS、零跳过。未修改生产代码、依赖或测试门槛；`b8c4457` 远端双版本各 871 tests + 225 subtests PASS、零跳过。Gitleaks 后续修复仅记录 16 个已复算的历史源码哈希指纹，并补齐事件 head 的完整扫描范围；双版本测试/扫描 PASS，镜像上下文修复后 CI 待核验。
- 兼容性：不得套用下方旧“无 API 契约变化”到本候选；认证/会话、任务 202、知识可见性、审批恢复、迁移、模型和部署均有收尾契约变化，见[支持与迁移映射](docs/50-engineering/delivery-status.md#support-and-migration-map)。
- 验收：L01–L16、D01–D16、O01–O16、B01–B16、S01–S16、R01–R20、真实运行、完整 RAG 与历史凭证处置仍 BLOCKED；离线测试不等于企业 UAT、生产放行或当前 CI 通过。


### 工程收尾规划（2026-10-17）

- C04 离线增量：五个会话入口统一归属授权，明确管理员仅可跨用户取消；固定拒绝响应、安全新会话创建、带所有者条件的续聊更新、移除反馈占位会话。20 项离线测试通过；C03 `fc8da91` 已推送，真实 PostgreSQL/API/Linux 验收仍 BLOCKED，C04 整项 open，未推进 C05。[实施记录](docs/40-process/阶段性总结_C04会话归属校验.md)。

- C03 离线增量：schema/演示种子分离、版本与校验和迁移、事务锁、显式管理员与开发种子、启动/健康 schema 检查；C02 `42bfc7f` 已推送。真实 PostgreSQL/API/Linux 验收仍 BLOCKED，C03 整项 open，未推进 C04。[实施记录](docs/40-process/阶段性总结_C03数据库迁移与初始化.md)。

- C02 外部模型离线增量：百炼北京 embedding/reranker 与 DeepSeek Flash/Pro，独立密钥、超时重试、严格响应校验、失败闭合与付费启动探针授权开关；slim 构建保留获批 libpq5/import 检查。真实 API/Linux 验收 BLOCKED，C02 整项 open。[实施记录](docs/40-process/阶段性总结_C02模型依赖.md)。
- C01 配置修复：生产 Compose 的 API/worker 使用同一必填镜像引用，部署前契约检查要求 registry digest；不再本地 build 或挂载源码。Nginx 补齐 UI/文档 schema/ready 路由、SSE 关闭缓冲、metrics 保持内部访问；修正 worker 继承 API 探针和部署命令。离线检查通过，但目标环境镜像/登录/SSE 验收 BLOCKED，C01 尚未完成。[实施记录](docs/40-process/阶段性总结_C01部署产物与入口.md)。
- C24 前置：新增标准库离线安全入口、12 项入口回归、副作用盘点和证据模板；只运行五个已审查核验函数，验证期间阻止文件修改/网络/进程，证据只新建且不保存原始敏感细节。当前五函数执行通过，真实 UAT/发布仍 BLOCKED；不代表 C24 整项完成。[交付记录](docs/40-process/阶段性总结_C24安全验证前置.md)。
- 完成 S0 文档增量：交付基线、ISSUES C01–C25 差距与验收、ROADMAP S0–S7 顺序及 `engineering-delivery-closeout` OpenSpec 变更。仅文档与规格，应用版本仍为 1.3.0；所有运行时收尾项尚未实施，真实企业验收与上线门槛仍阻塞。验证与限制见 [S0 阶段总结](docs/40-process/阶段性总结_S0工程交付基线.md)。

### 新增

- 工单真实接入试点（ticket-system-integration 16/16 归档，2026-08-06）：`CreateTicketTool` 幂等键（`ticket-{request_id}-{uuid8}`，经 `Idempotency-Key` 头传递并写入 `side_effects` 供审计关联）；Create/Update Saga 补偿真实化（http 提供方下 PATCH 关闭工单并标注 `saga_compensation` / 恢复 `old_values`，mock 通道零变更）；审计补齐 `provider`、重试次数与幂等键字段；`http_adapter` 新增 keyword-only `meta` 输出参数（向后兼容）。
- 联调验收资产：`eval/ticket_stub_server.py`（FastAPI 临时 stub，支持 Bearer 认证、幂等键去重、故障注入）与 `eval/run_ticket_acceptance.py`（验收 harness，7/7 通过）；验收记录见 `openspec/changes/archive/2026-08-06-ticket-system-integration/acceptance.md`，选型结论见 DECISIONS 第 15 条。
- 规格：`external-system-integration` 主规格扩展 6 条需求（幂等/重试边界/补偿真实化/审计回写/mock 降级/联调验收），`validate --all --strict` 16/16 通过。

### 修复

- 审计本地缓存文件名同秒覆盖缺陷（`time.time()` → `time.time_ns()`）：同秒同事件类型的多条审计曾互相覆盖丢失，验收实测暴露后修复。

### 测试

- 单元测试 89 → 101 项全绿（新增 `test_ticket_external.py` 12 项：幂等键、补偿真实化、worker 重试、审计回写、mock 回归）。

### 兼容性说明

- 无 API 契约变化；`tool_provider=mock` 行为不变；新增配置与参数均有默认值，不开启时行为与 v1.3.0 一致。

## v1.3.0 · 生产就绪与全量更名（2026-08-06）

> Git tag:`v1.3.0`

### 里程碑说明

生产上线导向优化第一阶段收口：本版本共归档 5 个 openspec change（生产就绪基线、RAG 答案质量、智能体更名、压测与容灾演练、安全加固），主规格由 10 项增至 13 项（新增 production-readiness、performance-resilience、security-operations）；剩余 3 个 change（工单/CRM/SSO 真实接入、UAT 与灰度上线）继续推进。

### 更名

- 产品智能体名称「小A」全量更名为「智多星」（2026-08-05）：代码字符串、prompts、静态页 UI、日志/审计/响应文案、文档、openspec 规格与变更、面试资产统一替换；一键启动脚本 `启动小A.bat`/`启动小A.command` 改名 `启动智多星.bat`/`启动智多星.command`；拼音/英文变体同步更新（`XiaoA` → `ZhiDuoXing`，K8s 命名空间 `hello-xiao-a` → `hello-zhiduoxing`）。无功能行为变更。

### 新增

- 生产就绪基线：checkpoint 滑动 TTL（`checkpoint_ttl_days`，<=0 恢复旧行为）、token 用量统计（`app/observability/token_usage.py`）、PG/etcd 备份脚本 `scripts/backup.sh`、生产配置校验测试。
- 压测与容灾：k6 阶梯压测脚本与报告渲染（`eval/load_test_k6.js`、`run_load_test.sh`、`render_load_report.py`）、备份恢复演练编排（`deploy/docker-compose.dr-drill.yml`，实测 RTO/RPO 已记录）、Prometheus 告警规则 `deploy/prometheus-alerts.yml` 与运维手册值班预案章节。
- RAG 答案质量：评测答案覆盖率指标与评测脚本、知识样本扩充（IT 运维与安全制度、人事管理制度）。

### 安全

- CI 接入三道扫描：gitleaks 密钥扫描（命中即失败）、pip-audit 依赖漏洞扫描、Trivy 镜像扫描（High/Critical 阻断）；豁免清单机制 `deploy/security-exemptions.txt`（仅 Medium 及以下可豁免，带复评日期）。
- 新增越权（privilege escalation）测试与 pre-commit 钩子（ruff/gitleaks）。

### 修复

- CI：`trivy-action` 版本标签修正并升级 v0.36.0（v0.28.0 依赖的 `setup-trivy@v0.2.1` 已不存在，导致镜像扫描 job 无法启动）。

### 兼容性说明

- 无 API 契约变化；更名为纯文案替换；新增配置项均有安全默认值，不开启时行为与 v1.2.0 一致。

## v1.2.0 · 项目归档完结（2026-08-04）

> Git tag:`v1.2.0`

### 里程碑说明

两个 openspec change 全部归档,openspec 生命周期闭环:

- `documentation-baseline` → `openspec/changes/archive/2026-08-04-documentation-baseline/`
- `complete-business-processes` → `openspec/changes/archive/2026-08-04-complete-business-processes/`
- 主规格:10 项能力规格(4 文档类 + 6 业务类),`openspec validate --all` 全部通过
- 当前无进行中 change;新需求按 propose → apply → archive 重新开启

### 变更

- Worker 纳入一键启动(`启动智多星.command`),后台运行审批超时扫描/任务队列/审计回写(实测启动即回写 147 条缓存审计)。
- ROADMAP 更新:两 change 移入已完成里程碑,进行中区清空。
- CI 全绿:main 与 tag 推送的测试(3.11/3.13)+ 镜像构建 3/3 通过。

### 兼容性说明

- 无 API 契约变化;归档仅移动 openspec 目录与规格沉淀,不影响运行。

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
- **运维修复**：网站 URL `**` 容错重定向、本机 Redis 端口冲突处理、macOS 一键启动脚本 `启动智多星.command`。

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
