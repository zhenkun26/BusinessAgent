## Context

现状见 proposal.md 的 Why。关键约束：密钥当前只从环境变量读取（工程约定，`.env` 已在 `.gitignore`）；JWT 校验与禁用即时性由 `app/security/rbac.py` 的 `auth_check_db` 开关控制（默认每次回查 users 表，DB 故障时降级为仅 JWT 校验并告警）；命名空间访问控制为 `ROLE_NAMESPACES` 静态映射，降级链已修过 BM25 跨部门泄露（ISSUES 历史坑）；checkpoint 主路径为 AsyncRedisSaver（`app/graph/checkpointer.py`），无 TTL；token 采集现状仅 `app/agents/knowledge.py` 提取 `tokens_used` 落 AgentState（aggregator 汇总），`sessions.token_count` 未回写（ISSUES I-07）；CI（`.github/workflows/ci.yml`）现有 test + docker 两个 job，镜像已推 GHCR。

## Goals / Non-Goals

**Goals:**
- 密钥管理形成「清单 + 轮换规程 + 应急流程 + 防泄漏扫描」的完整闭环，选型结论落 DECISIONS.md。
- CI 在不拖慢主链路的前提下完成依赖与镜像漏洞扫描，高危阻断。
- 越权测试用例直接落进现有 pytest 套件（58 用例基线之上新增），CI 自动回归。
- I-06/I-07 以最小侵入收口：不改 checkpoint 主路径选型，不改 LLM 调用结构。

**Non-Goals:**
- 不引入在线密钥管理服务的基础设施改造（Vault 等只给选型结论，实施与否另开 change）。
- 不重构 RBAC 模型本身（角色/命名空间映射不动），只补测试与规程。
- 不做渗透测试与 Prompt 注入实测（属 I-02，归入 `uat-and-ga-rollout` 前的安全测试安排）。

## Decisions

### 1. 密钥管理：环境变量 + 轮换规程 + 防泄漏扫描，Vault 选型结论为「暂缓引入」

单机 Docker Compose 部署下，运维手册补齐密钥清单（JWT 密钥 / PG 口令 / Redis 密码 / DeepSeek API Key / GHCR token）与轮换步骤、验证方式、泄漏应急流程即可满足当前阶段的审计要求；防泄漏用 pre-commit 钩子（gitleaks 或 detect-secrets）+ CI 兜底扫描双保险。

备选：直接引入 HashiCorp Vault。否决：单机 Compose 架构下引入 Vault 等于新增一个需要自身 HA 与运维的关键依赖，成本远超收益；评审要求的是「密钥管理系统的能力」——轮换、应急、防泄漏，规程 + 扫描即可覆盖，选型结论（含改判条件：多机/K8s 化后复评）写入 DECISIONS.md。

### 2. CI 扫描：pip-audit 扫依赖、Trivy 扫镜像，High/Critical 阻断

依赖扫描放入现有 test job 之后的独立 step（pip-audit 扫 `deploy/requirements-prod.txt`，`--vulnerability-service` 默认 OSV）；镜像扫描复用现有 docker job 的构建产物，Trivy 以 `exit-code` 非零在 High/Critical 时失败，报告以 SARIF/table 随 artifact 留存。两者都不改现有测试与构建逻辑，只加 step。

备选：Dependabot/Renovate 替代 pip-audit。否决：Dependabot 只做 PR 提醒不阻断流水线，不满足「高危阻断合并」的规格要求；可作为后续增强，两者不冲突。

### 3. 越权测试：在现有 pytest 套件内新增专项文件，复用 conftest 的 Fake 基础设施

新增 `tests/test_privilege_escalation.py`，用例映射规格四个 Scenario：跨部门命名空间取数（对齐 `run_p2_namespace` 已验证的口径，补 pytest 自动化断言）、禁用用户持旧 JWT（`auth_check_db=True` 时 401，已有 `test_rbac_active_check.py` 覆盖正向，此处补「降级模式告警但放行」的显式断言）、角色降级后旧 token 按 DB 新角色判定、越权使用他角色工具被 ToolGateway 拒绝。全部走 `get_current_user` / `can_access_namespace` / `can_use_tool` 的真实代码路径，Mock DB 复用 `conftest.py` 的 FakeSession。

备选：起真实服务做 HTTP 层越权测试。否决：CI 无 Docker/DB 环境，单元层已能覆盖判定逻辑；端到端越权留待 UAT 安全测试。

### 4. I-06：checkpoint 按会话活跃时间滑动过期，不动 Saver 选型

利用 Redis 键的 TTL 机制：在 checkpointer 写入路径（会话每次活跃）刷新对应 thread 键的过期时间，TTL 值走配置项（初值 7 天，对齐 sessions 表元信息独立可查的前提）；不引入独立清理任务，避免与 AsyncRedisSaver 内部键结构耦合的扫描逻辑。降级后端（PG/Memory）本轮不设 TTL，仅 Redis 主路径生效。

备选：后台定时任务扫描清理。否决：需感知 RedisSaver 内部键命名，版本升级易碎；滑动 TTL 只需在既有写入点加 expire 调用，侵入最小。

### 5. I-07：LangChain callback 统一采集，三处落地

新增一个 LangChain `BaseCallbackHandler`，在 LLM 调用结束回调中累计 token；aggregator 汇总后：① 写审计日志 payload；② 递增 Prometheus counter（`app/observability/metrics.py`）；③ 异步回写 `sessions.token_count`。analysis/execution/aggregator 的自身调用经统一 chat model 封装挂接 callback，knowledge 现有的 `tokens_used` 提取改走同一通道，避免双口径。

备选：从各 LLM 响应 `usage_metadata` 逐点提取。否决：这正是现状的缺口成因（漏了三个节点）；callback 挂在模型封装层可自动覆盖全部调用方。

## Risks / Trade-offs

- RedisSaver 内部键结构与 expire 调用耦合 → expire 只作用于已确认的 thread 前缀键，加单元测试断言键存在性；升级 langgraph-checkpoint-redis 前跑 checkpoint 回归（`eval/run_w6_checkpoint`）。
- token 回写 sessions 增加每次对话一次 UPDATE → 异步 fire-and-forget 执行，失败仅记日志不阻断对话。
- Trivy/pip-audit 可能因历史漏洞长期阻断 CI → 门槛初值仅 High/Critical 阻断，Medium 及以下告警不阻断；确需豁免的条目走配置文件豁免清单并注明复评日期。
- pre-commit 密钥扫描有误报（如文档示例串）→ 维护 allowlist，误报处置写入运维手册。

## Migration Plan

无破坏性变更。顺序：规程与选型落档（运维手册 + DECISIONS）→ pre-commit 与 CI 扫描接入 → 越权测试用例补齐（CI 转绿）→ I-06/I-07 实现并跑相关 eval 回归（`eval/run_w6_checkpoint`、W5 对话回归）→ 更新 ISSUES I-06/I-07 状态后归档。回滚：CI step 与测试文件均为增量，可直接回退；checkpoint TTL 与 token 采集由配置开关控制，关闭即恢复原行为。

## Open Questions

- checkpoint TTL 初值 7 天是否匹配真实会话回访周期？按现有 sessions 表活跃数据确认后定稿，不影响方案结构。
- GHCR 私有镜像的 Trivy 扫描是否需要额外 registry 凭据配置？实施时按 CI 实测确认，pipeline 结构不变。
