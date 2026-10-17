# contents · 全仓库目录树索引

> 本文件为仓库目录树索引，每一行注释说明该路径的作用。新增/移动/删除文件后请同步更新本文件。

```text
BusinessAgent/
├── README.md                           # 中文项目介绍与全仓库导航入口
├── README-en.md                        # English translation of the root README
├── contents.md                         # 本文件：目录树索引（每行注释用途）
├── CHANGELOG.md                        # 版本变更日志（按时间倒序，含版本号/日期/摘要）
├── AGENTS.md                           # AI 助手项目说明：目录结构、常用命令、工程约定
├── LICENSE                             # MIT 许可证
├── .gitignore                          # Git 忽略规则：排除 .env/日志/模型/虚拟环境/评测结果
├── .gitleaks.toml                      # gitleaks 密钥扫描配置（CI 兜底，见 ci.yml）
├── .pre-commit-config.yaml             # pre-commit 钩子（ruff/gitleaks 等提交前检查）
├── 启动智多星.bat                       # Windows 一键启动脚本（自检 Docker/容器/API 并打开 /ui）
├── 启动智多星.command                   # macOS 一键启动脚本（含 Worker 后台进程）
├── IMG_5043.jpg / IMG_5044.jpg         # 项目相关照片素材（根目录暂存）
├── .kimi-code/                         # Kimi Code 工作流 skills（openspec ×6，openspec init 生成）
├── .codex/                             # Codex 工作流 skills（openspec ×6，openspec init 生成）
├── docs/                               # 统一文档体系（六大层 + 归档层）
│   ├── 00-overview/                    # 元层：项目概览与导航说明（README/contents/CHANGELOG 索引）
│   │   └── README.md                   # 00-overview 层索引
│   ├── 10-product-plan/                # 产品方案层：现行产品方案与研究依据
│   │   ├── README.md                   # 产品方案层索引
│   │   ├── 企业知识工作流Agent产品方案_v3_整合版.md  # 现行产品技术方案基线（2026-07-26）
│   │   ├── research/                   # 选型研究（deep-research 报告 ×3 + 执行摘要 PDF）
│   │   └── assets/                     # 方案配图（模型应用场景图）
│   ├── 20-product/                     # 产品文档层：产品权威现状文档
│   │   ├── README.md                   # 产品文档层索引
│   │   ├── 产品文档.md                  # 产品权威现状文档 v1.4（架构/流程/API/backlog）
│   │   └── assets/                     # 文档配图（业务流程图、架构总览图）
│   ├── 30-guides/                      # 操作手册层：使用与运维手册
│   │   ├── README.md                   # 操作手册层索引
│   │   ├── 使用案例手册.md              # 功能全流程测试用例（curl 脚本 + 预期）
│   │   ├── 产品使用手册-前端版.md        # 浏览器 /ui 使用与验收手册
│   │   ├── 运维维护手册.md              # 日常启停/数据维护/监控/告警值班预案/故障排查
│   │   ├── UAT验收计划.md                # 真实用户验收计划、场景矩阵与执行记录模板
│   │   └── 发布灰度与上线门槛检查单.md    # 灰度策略、回滚路径与全量放行门槛
│   ├── 40-process/                     # 过程记录层：迭代过程与项目演进档案
│   │   ├── README.md                   # 过程记录层索引
│   │   ├── ROADMAP.md                  # 里程碑规划（已完成/进行中/挂起，单一事实源）
│   │   ├── 阶段性总结_S0工程交付基线.md # S0 文档交付与验证；运行时收尾尚未实施
│   │   ├── 阶段性总结_C24安全验证前置.md # 安全入口前置交付与回归；整项尚未完成
│   │   ├── 阶段性总结_C02模型依赖.md # 模型契约与离线检查；真实 API/Linux 验收阻塞
│   │   ├── 阶段性总结_C03数据库迁移与初始化.md # 迁移/bootstrap 离线增量；真实数据库验收阻塞
│   │   ├── 阶段性总结_C12工具幂等与安全重试.md # 持久动作与回执验证
│   │   ├── 阶段性总结_C18参考契约前置.md # 参考业务接口与失败/补偿契约
│   │   ├── 阶段性总结_C10检查点持久化与故障语义.md # 固定 checkpoint 后端与失败契约
│   │   ├── 阶段性总结_C09跨进程运行状态.md # 共享运行状态与 Prompt 请求快照
│   │   ├── 阶段性总结_C08请求上下文与子任务依赖.md # 请求隔离、历史归属与依赖拒绝
│   │   ├── 阶段性总结_C07检索权限与表达式编码.md # 检索矩阵、编码与离线验证
│   │   ├── 阶段性总结_C06凭证与HTML失败安全.md # 瞬时授权、脱敏与 HTML 回退
│   │   ├── 阶段性总结_C05认证失败闭合与运行时授权.md # 身份与审批授权；运行验收阻塞
│   │   ├── 阶段性总结_C04会话归属校验.md # 五入口会话归属；真实 HTTP/PG 验收阻塞
│   │   ├── 阶段性总结_C01部署产物与入口.md # 部署配置修复；目标运行验收阻塞
│   │   ├── 模板-工程验收证据.md         # 版本、环境、命令/人工步骤、证据等级与结果模板
│   │   ├── code-simplification/20260928-backend/ # FGR-01/FAT-01 审计、交付报告、验证脚本与 JSON 证据
│   │   ├── delivery-followup/20260929/          # CI 保护设置快照与离线核验 JSON
│   │   ├── 交付与离线推进记录-2026-09-29.md
│   │   ├── 下一步执行阻塞清单-2026-09-29.md       # 企业现场输入清单；工程顺序见 ROADMAP
│   │   ├── DECISIONS.md                # 设计决策记录（背景/决策/放弃/改判条件）
│   │   ├── ISSUES.md                   # 问题/坑/backlog（状态/优先级/根因/修复/验证）
│   │   ├── 模板-阶段性总结.md            # 后续迭代阶段总结模板
│   │   ├── 阶段性总结_W2-W6.md          # W2-W6 阶段总结（含已修正的历史路径）
│   │   ├── 阶段性总结_W7-W9_联调.md      # W7-W9 + 整体联调阶段总结
│   │   ├── 生产对抗性审查与部署验收报告.md  # 12 项漏洞修复与部署验收记录（2026-08-04）
│   │   ├── 上线评审材料-2026-08-05.md     # 生产上线评审材料（边界/SLA/风险清单）
│   │   ├── UAT计划评审记录-2026-08-15.md  # UAT 计划与 G0 fixture 结构评审（资源未齐）
│   │   ├── UAT执行准备核对报告-2026-08-15.md  # UAT 真实执行资源核对（当前 BLOCKED）
│   │   ├── 下一步执行阻塞清单-2026-08-15.md  # active change 依赖、证据与执行顺序
│   │   ├── 发布门槛核对报告-2026-08-15.md  # 六项上线门槛程序化核对（当前 BLOCKED）
│   │   ├── 灰度方案评审记录-2026-08-15.md  # 灰度方案条件评审（最短观察期4周，业务阈值待确认）
│   │   ├── 优化方向分析-生产上线-2026-08-05.md  # explore 阶段产物：差距对照与候选 change 清单
│   │   └── 临时备忘.md                  # 历史速查备忘（内容已拆入 ROADMAP/ISSUES，保留备查）
│   ├── 50-engineering/                 # 工程文档层：跨模块交付契约与实现文档索引
│   │   ├── engineering-delivery-baseline.md # 工程交付边界、参考服务与验收证据契约
│   │   ├── safe-validation.md           # C24 离线入口与副作用审查、状态及限制
│   │   └── README.md                   # 工程文档层索引（指向后端 README 与部署指南）
│   ├── 60-knowledge/                   # 知识数据库层：索引 eval/sample_docs 知识数据
│   │   └── README.md                   # 知识数据库层索引（知识文档 + 入库规范摘要）
│   └── 90-archive/                     # 归档层：历史方案与淘汰文档（只读）
│       ├── README.md                   # 归档层索引
│       ├── 企业知识工作流Agent产品方案.md         # 产品方案 v1（历史）
│       ├── 企业知识工作流Agent产品方案_v2_LangGraph版.md  # 产品方案 v2（历史）
│       └── 改进文档.md                  # P0-P2 改进项跟踪（已全部完成，历史）
├── interview/                          # 面试与演示资产独立体系
│   ├── Agent项目面试备稿.md             # 面试备稿（九大维度 Q&A + 取舍/失败/边界）
│   └── 产品介绍网页/                    # 产品演示网页（单文件 index.html + 截图 + 字体 + 演讲词）
│       ├── index.html                  # 演示页（27 页 / 八幕，零构建）
│       ├── 演讲提示词.md                # 15 分钟演讲逐页口播稿
│       ├── screenshots/                # 演示截图（登录/对话/审批/Saga 等 9 组，png+webp）
│       ├── fonts/                      # 页面字体资源（woff2）
│       └── 启动演讲汇报.bat             # Windows 启动演讲汇报脚本
├── enterprise-agent/                   # 后端主工程（FastAPI + LangGraph + RAG + 工具）
│   ├── README.md                       # 后端 README：快速开始/项目结构/实施进度/技术栈
│   ├── app/                            # 应用代码：api/agents/graph/rag/tools/security/observability（含 token_usage）
│   ├── eval/                           # 验证脚本（W5-W9）+ 评测数据 + 知识库样本 + k6 压测资产 + 工单 stub 与联调验收 + UAT 彩排模拟数据
│   │   ├── generate_uat_simulation.py  # 生成确定性 G0 技术彩排数据（不连接外部系统）
│   │   ├── run_uat_replay.py           # 只读 fixture 的结构/安全契约回放器
│   │   ├── validate_uat_plan.py         # UAT 计划与 G0 fixture 结构校验器
│   │   ├── validate_release_gate.py     # 发布门槛检查单只读核对器
│   │   ├── validate_grey_release_plan.py # 灰度方案结构与回滚路径核验器
│   │   ├── validate_uat_execution_readiness.py # UAT 真实执行资源核验器
│   │   └── uat_simulation/             # fixture.json + 使用说明
│   ├── deploy/                         # 部署配置：init.sql/migrations/DEPLOY.md/nginx/prometheus + 告警规则/漏洞豁免/DR 演练编排
│   ├── scripts/                        # 运维脚本（fix_seed_approvals.py、backup.sh 备份脚本）
│   │   ├── safe_validate.py            # 仅运行已审查函数；禁止验证副作用，独占创建证据
│   │   └── check_deployment_contract.py # 从 stdin 读取 Compose JSON；摘要镜像/挂载/暴露边界核验
│   ├── tests/                          # 单元测试（129 项，含越权/checkpoint TTL/token 用量/评测指标/工单外部调用）
│   │   ├── test_rate_limit.py          # 限流工厂选择、降级与响应行为的离线回归测试
│   │   ├── test_safe_validation.py     # 直接用标准库 unittest 运行，夹具保留不清理
│   │   └── test_deployment_contract.py # 部署契约与入口静态回归，不代表 Nginx 运行验收
│   ├── docker-compose.yml              # 开发环境编排（Milvus/PG/Redis/Ollama）
│   ├── docker-compose.prod.yml         # 生产部署编排（Nginx + 资源限制）
│   ├── Dockerfile                      # 应用镜像构建
│   ├── pyproject.toml                  # 工程配置（ruff/pytest/dev 依赖）
│   └── .env.example                    # 环境变量模板（真实 .env 不入库）
└── openspec/                           # openspec 需求演进体系
    ├── config.yaml                     # openspec 配置（schema + 项目 context）
    ├── specs/                          # 主规格 15 项（既有规格；不代表企业现场已验收）
    │   ├── documentation-layout/       # 文档目录布局规格
    │   ├── version-control/            # 版本控制规格
    │   ├── progress-issue-records/     # 进度与问题记录规格
    │   ├── openspec-normalization/     # openspec 规范化规格
    │   ├── knowledge-operations/       # 知识库运营规格（含答案质量指标）
    │   ├── agent-replan/               # 重规划闭环规格
    │   ├── approval-lifecycle/         # 审批生命周期规格
    │   ├── external-system-integration/# 外部系统接入规格（Mock 契约）
    │   ├── user-lifecycle/             # 用户生命周期规格
    │   ├── quality-testing/            # 质量与测试规格
    │   ├── production-readiness/       # 生产就绪规格（边界/SLA/风险清单）
    │   ├── performance-resilience/     # 性能与容灾规格（压测/恢复演练/告警值班）
    │   ├── security-operations/        # 安全运营规格（密钥/漏洞扫描/越权测试）
    │   ├── release-management/         # UAT、灰度与正式放行契约
    │   └── uat-replay/                 # G0 技术彩排与证据边界
    └── changes/                        # 变更记录（propose→apply→archive 生命周期）
        ├── engineering-delivery-closeout/ # S0/C24/C01 配置已交付；C01/C02/C03/C04/C05/C06/C07/C08/C09/C10 运行验收阻塞
        ├── crm-mail-sso-integration/       # CRM/邮件/SSO 真实接入（实施中 9/19）
        ├── uat-and-ga-rollout/             # UAT、灰度、上线门槛（实施中 8/15）
        └── archive/                        # 已归档变更（全部完成）
            ├── 2026-08-04-documentation-baseline/        # 文档基线（归档）
            ├── 2026-08-04-complete-business-processes/   # 业务闭环补齐 41/41（归档）
            ├── 2026-08-05-production-readiness-baseline/ # 生产就绪基线 10/10（归档）
            ├── 2026-08-05-rag-answer-quality/            # RAG 答案质量 15/15（归档）
            ├── 2026-08-06-rename-agent-to-zhiduoxing/    # 智能体更名「智多星」7/7（归档）
            ├── 2026-08-06-load-test-and-dr-drill/        # 压测与容灾演练 14/14（归档）
            ├── 2026-08-06-security-hardening-plus/       # 安全加固 21/21（归档）
            ├── 2026-08-06-ticket-system-integration/     # 工单真实接入试点 16/16（归档，含 stub 验收记录）
            ├── 2026-08-15-fix-prod-image-pip-removal/   # 生产镜像 pip 清理顺序修复 4/4（归档）
            ├── 2026-08-15-uat-replay-harness/          # G0 fixture 与只读回放器（归档）
            ├── 2026-09-28-simplify-backend-internals/  # FGR-01/FAT-01 内部简化与验证（已合并归档）
            ├── 2026-09-28-scan-image-before-publish/  # CI 先扫描后发布（已合并并发布镜像）
            ├── 2026-09-29-close-delivery-and-require-ci/ # 交付收尾、CI 必需检查与离线推进
            ├── 2026-10-17-fix-vulnerable-runtime-dependencies/ # Runtime dependency repair; CI passed
            └── 2026-10-17-refresh-bilingual-readmes/  # Chinese and English README refresh and validation
```

C02 候选详情：[模型 profile](enterprise-agent/deploy/MODEL_PROFILE.md)、[可选本地实验依赖（生产未采用）](enterprise-agent/deploy/requirements-ml.txt)、[启动校验](enterprise-agent/app/rag/model_profile.py)、[离线回归](enterprise-agent/tests/test_model_profile.py)、[外部适配器回归](enterprise-agent/tests/test_remote_models.py)。

C03 候选详情：[数据库初始化手册](enterprise-agent/deploy/DATABASE_BOOTSTRAP.md)、[版本清单](enterprise-agent/deploy/schema_manifest.json)、[显式迁移入口](enterprise-agent/app/core/db_bootstrap.py)、[schema 契约](enterprise-agent/app/core/schema_contract.py)、[演示种子](enterprise-agent/deploy/demo_seed.sql)、[离线回归](enterprise-agent/tests/test_db_bootstrap.py)。

C04 候选详情：[会话归属契约](docs/50-engineering/session-ownership.md)、[统一授权守卫](enterprise-agent/app/security/session_access.py)、[离线验证入口](enterprise-agent/eval/run_c04_session_ownership.py)、[对抗性回归](enterprise-agent/tests/test_session_ownership.py)。

C05 候选详情：[认证与运行时授权契约](docs/50-engineering/runtime-authorization.md)、[离线验证入口](enterprise-agent/eval/run_c05_runtime_authorization.py)、[交付记录](docs/40-process/阶段性总结_C05认证失败闭合与运行时授权.md)。

C06 候选详情：[凭证安全契约](docs/50-engineering/credential-safety.md)、[Python 离线验证](enterprise-agent/eval/run_c06_credential_safety.py)、[浏览器脚本验证](enterprise-agent/tests/test_browser_credential_safety.cjs)、[交付记录](docs/40-process/阶段性总结_C06凭证与HTML失败安全.md)。

C07 候选详情：[检索权限契约](docs/50-engineering/retrieval-authorization.md)、[离线验证](enterprise-agent/eval/run_c07_retrieval_authorization.py)、[交付记录](docs/40-process/阶段性总结_C07检索权限与表达式编码.md)。

C08 候选详情：[请求上下文契约](docs/50-engineering/request-context.md)、[离线验证](enterprise-agent/eval/run_c08_request_context.py)、[交付记录](docs/40-process/阶段性总结_C08请求上下文与子任务依赖.md)。

C09 候选详情：[跨进程状态契约](docs/50-engineering/cross-process-state.md)、[离线验证](enterprise-agent/eval/run_c09_cross_process_state.py)、[交付记录](docs/40-process/阶段性总结_C09跨进程运行状态.md)。

C10 候选详情：[持久化契约](docs/50-engineering/checkpoint-durability.md)、[离线验证](enterprise-agent/eval/run_c10_checkpoint_durability.py)、[交付记录](docs/40-process/阶段性总结_C10检查点持久化与故障语义.md)。

C18 前置详情：[参考契约](docs/50-engineering/reference-business-contract.md)、[交付记录](docs/40-process/阶段性总结_C18参考契约前置.md)；仅契约冻结，完整参考 HTTP 验收仍 BLOCKED。

C12 离线增量：[操作契约](docs/50-engineering/tool-operation-safety.md)、[交付记录](docs/40-process/阶段性总结_C12工具幂等与安全重试.md)；真实运行 BLOCKED，C14 等待确认。
