# contents · 全仓库目录树索引

> 本文件为仓库目录树索引，每一行注释说明该路径的作用。新增/移动/删除文件后请同步更新本文件。

```text
BusinessAgent/
├── README.md                           # 全仓库唯一导航入口（本层所有链接起点）
├── contents.md                         # 本文件：目录树索引（每行注释用途）
├── CHANGELOG.md                        # 版本变更日志（按时间倒序，含版本号/日期/摘要）
├── AGENTS.md                           # Codex 项目说明：目录结构、常用命令、工程约定
├── .gitignore                          # Git 忽略规则：排除 .env/日志/模型/虚拟环境/评测结果
├── 启动小A.bat                         # Windows 一键启动脚本（自检 Docker/容器/API 并打开 /ui）
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
│   │   └── assets/                     # 文档配图（业务流程图）
│   ├── 30-guides/                      # 操作手册层：使用与运维手册
│   │   ├── README.md                   # 操作手册层索引
│   │   ├── 使用案例手册.md              # 功能全流程测试用例（curl 脚本 + 预期）
│   │   ├── 产品使用手册-前端版.md        # 浏览器 /ui 演示与验收手册
│   │   └── 运维维护手册.md              # 日常启停/数据维护/监控/故障排查
│   ├── 40-process/                     # 过程记录层：迭代过程与项目演进档案
│   │   ├── README.md                   # 过程记录层索引
│   │   ├── ROADMAP.md                  # 里程碑规划（已完成/进行中/挂起，单一事实源）
│   │   ├── DECISIONS.md                # 设计决策记录（背景/决策/放弃/改判条件）
│   │   ├── ISSUES.md                   # 问题/坑/backlog（状态/优先级/根因/修复/验证）
│   │   ├── 模板-阶段性总结.md            # 后续迭代阶段总结模板
│   │   ├── 阶段性总结_W2-W6.md          # W2-W6 阶段总结（含已修正的历史路径）
│   │   ├── 阶段性总结_W7-W9_联调.md      # W7-W9 + 整体联调阶段总结
│   │   └── 临时备忘.md                  # 历史速查备忘（内容已拆入 ROADMAP/ISSUES，保留备查）
│   ├── 50-engineering/                 # 工程文档层：索引 enterprise-agent 内部工程文档
│   │   └── README.md                   # 工程文档层索引（指向后端 README 与部署指南）
│   ├── 60-knowledge/                   # 知识数据库层：索引 eval/sample_docs 知识数据
│   │   └── README.md                   # 知识数据库层索引（7 份知识文档 + 入库规范摘要）
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
│   ├── app/                            # 应用代码：api/agents/graph/rag/tools/security/observability
│   ├── eval/                           # 验证脚本（W5-W9）+ 评测数据 + 知识库样本文档
│   ├── deploy/                         # 部署配置：init.sql/migrations/DEPLOY.md/nginx/prometheus
│   ├── scripts/                        # 运维脚本（如 fix_seed_approvals.py）
│   ├── docker-compose.yml              # 开发环境编排（Milvus/PG/Redis/Ollama）
│   ├── docker-compose.prod.yml         # 生产部署编排（Nginx + 资源限制）
│   ├── Dockerfile                      # 应用镜像构建
│   ├── pyproject.toml                  # 工程配置（ruff/pytest/dev 依赖）
│   └── .env.example                    # 环境变量模板（真实 .env 不入库）
└── openspec/                           # openspec 需求演进体系
    ├── config.yaml                     # openspec 配置（schema + 项目 context）
    ├── specs/                          # 主规格（已归档能力，长期资产）
    │   ├── documentation-layout/       # 文档目录布局规格
    │   ├── version-control/            # 版本控制规格
    │   ├── progress-issue-records/     # 进度与问题记录规格
    │   └── openspec-normalization/     # openspec 规范化规格
    └── changes/                        # 变更记录（propose→apply→archive 生命周期）
        └── archive/                    # 已归档变更（全部完成）
            ├── 2026-08-04-documentation-baseline/       # 文档基线（归档）
            └── 2026-08-04-complete-business-processes/  # 业务闭环补齐 41/41（归档）
```
