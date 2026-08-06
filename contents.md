# contents · 全仓库目录树索引

> 本文件为仓库目录树索引，每一行注释说明该路径的作用。新增/移动/删除文件后请同步更新本文件。

```text
BusinessAgent/
├── README.md                           # 全仓库唯一导航入口（本层所有链接起点）
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
│   │   ├── 产品使用手册-前端版.md        # 浏览器 /ui 演示与验收手册
│   │   └── 运维维护手册.md              # 日常启停/数据维护/监控/告警值班预案/故障排查
│   ├── 40-process/                     # 过程记录层：迭代过程与项目演进档案
│   │   ├── README.md                   # 过程记录层索引
│   │   ├── ROADMAP.md                  # 里程碑规划（已完成/进行中/挂起，单一事实源）
│   │   ├── DECISIONS.md                # 设计决策记录（背景/决策/放弃/改判条件）
│   │   ├── ISSUES.md                   # 问题/坑/backlog（状态/优先级/根因/修复/验证）
│   │   ├── 模板-阶段性总结.md            # 后续迭代阶段总结模板
│   │   ├── 阶段性总结_W2-W6.md          # W2-W6 阶段总结（含已修正的历史路径）
│   │   ├── 阶段性总结_W7-W9_联调.md      # W7-W9 + 整体联调阶段总结
│   │   ├── 生产对抗性审查与部署验收报告.md  # 12 项漏洞修复与部署验收记录（2026-08-04）
│   │   ├── 上线评审材料-2026-08-05.md     # 生产上线评审材料（边界/SLA/风险清单）
│   │   ├── 优化方向分析-生产上线-2026-08-05.md  # explore 阶段产物：差距对照与候选 change 清单
│   │   └── 临时备忘.md                  # 历史速查备忘（内容已拆入 ROADMAP/ISSUES，保留备查）
│   ├── 50-engineering/                 # 工程文档层：索引 enterprise-agent 内部工程文档
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
│   ├── eval/                           # 验证脚本（W5-W9）+ 评测数据 + 知识库样本 + k6 压测资产（load_test_k6.js 等）
│   ├── deploy/                         # 部署配置：init.sql/migrations/DEPLOY.md/nginx/prometheus + 告警规则/漏洞豁免/DR 演练编排
│   ├── scripts/                        # 运维脚本（fix_seed_approvals.py、backup.sh 备份脚本）
│   ├── tests/                          # 单元测试（89 项，含越权/checkpoint TTL/token 用量/评测指标）
│   ├── docker-compose.yml              # 开发环境编排（Milvus/PG/Redis/Ollama）
│   ├── docker-compose.prod.yml         # 生产部署编排（Nginx + 资源限制）
│   ├── Dockerfile                      # 应用镜像构建
│   ├── pyproject.toml                  # 工程配置（ruff/pytest/dev 依赖）
│   └── .env.example                    # 环境变量模板（真实 .env 不入库）
└── openspec/                           # openspec 需求演进体系
    ├── config.yaml                     # openspec 配置（schema + 项目 context）
    ├── specs/                          # 主规格 13 项（已归档能力，长期资产）
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
    │   └── security-operations/        # 安全运营规格（密钥/漏洞扫描/越权测试）
    └── changes/                        # 变更记录（propose→apply→archive 生命周期）
        ├── ticket-system-integration/      # 工单真实接入试点（已提案 0/16）
        ├── crm-mail-sso-integration/       # CRM/邮件/SSO 真实接入（已提案 0/19）
        ├── uat-and-ga-rollout/             # UAT、灰度、上线门槛（已提案 0/15）
        └── archive/                        # 已归档变更（全部完成）
            ├── 2026-08-04-documentation-baseline/        # 文档基线（归档）
            ├── 2026-08-04-complete-business-processes/   # 业务闭环补齐 41/41（归档）
            ├── 2026-08-05-production-readiness-baseline/ # 生产就绪基线 10/10（归档）
            ├── 2026-08-05-rag-answer-quality/            # RAG 答案质量 15/15（归档）
            ├── 2026-08-06-rename-agent-to-zhiduoxing/    # 智能体更名「智多星」7/7（归档）
            ├── 2026-08-06-load-test-and-dr-drill/        # 压测与容灾演练 14/14（归档）
            └── 2026-08-06-security-hardening-plus/       # 安全加固 21/21（归档）
```
