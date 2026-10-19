# BusinessAgent · 智多星

面向企业知识与业务流程的多智能体平台，将知识检索、数据分析和业务操作接入统一的自然语言工作流。

**简体中文** | [English](README-en.md)

[快速开始](#快速开始) · [系统架构](#系统架构) · [文档](#文档)

[![CI](https://github.com/zhenkun26/BusinessAgent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/zhenkun26/BusinessAgent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](enterprise-agent/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 项目介绍

企业中的一次业务请求，往往同时涉及查制度、取数据和执行操作。
BusinessAgent 通过 Planner 拆解请求，由不同 Agent 处理子任务，再汇总结果。

项目关注从自然语言请求到业务执行的完整过程：

- 回答问题时，检索用户有权访问的知识，并提供来源信息。
- 分析数据时，按 CRM provider 读取快照，由 Python 计算并生成确定性报告。
- 执行业务操作时，校验工具权限，并按操作规则进入人工审批。
- 多步骤操作失败时，对支持补偿的步骤执行 Saga 补偿并记录结果。

仓库包含后端服务、Web 交互界面、评测脚本和部署配置，适合研究多智能体编排、企业 RAG 与受控工具执行。

## 可以做什么

以下示例需要对应知识文档、用户角色及模型配置。

| 场景 | 示例请求 | 处理方式 |
| --- | --- | --- |
| 企业知识问答 | “公司的差旅报销有哪些规定？” | 检索知识库，组织回答并返回来源 |
| 业务数据分析 | “统计各客户的订单总额并进行排名。” | 按授权读取 CRM 快照，由 Python 聚合并生成确定性报告 |
| 业务记录查询 | “查询客户 C001 的信息。” | 校验角色权限后调用业务工具 |
| 流程操作 | “为客户 C001 创建一个售后工单。” | 提取参数，执行权限检查并调用工单工具 |
| 审批协作 | “给外部客户发送一封跟进邮件。” | 根据操作规则创建审批请求，由有权限的人员处理 |
| 组合任务 | “查询客户信息，同时说明公司的售后政策。” | 将请求拆分为不同 Agent 的子任务并汇总结果 |

> 默认业务工具使用 Mock provider，分析复用同一 CRM provider；Mock 使用内置样例，HTTP 使用受控快照接口。
> 示例用于体验工作流；连接真实业务系统需要配置适配器并完成联调。

## 核心能力

### 多智能体编排

- 使用 LangGraph 组织 Planner → Agent Executor → Aggregator 工作流。
- 通过 Send API 并行分发子任务。
- 由 Knowledge、Analysis、Execution 三类 Agent 承担不同职责。
- 对需要补充检索的结果进行有限重规划，最多追加 2 轮。

### 知识检索与回答

- 支持 Markdown、PDF、DOCX 和 TXT 文档加载。
- 使用 Milvus 向量召回与 Reranker 重排。
- 随附 `.env.example` 选择百炼北京 `text-embedding-v4`（1024 维）与 `qwen3-rerank`；本地 BGE 仅保留为开发选项。
- 在检索路径中应用角色与部门命名空间过滤。
- 提供来源信息、置信度决策和检索异常降级路径。

### 受控业务执行

- 提供客户、订单、CRM 任务、工单、邮件与审批查询工具。
- 通过 RBAC 限定不同角色的工具访问权限。
- 对需要审批的操作接入人工审批流程。
- 使用 Saga 协调多步骤执行，并处理支持补偿的失败场景。
- 提供外部 HTTP 适配层，以及超时、重试和审计机制。

### 状态管理与可观测性

- 通过 Checkpointer 保存会话状态，支持状态恢复。
- 显式选择 Redis 或 PostgreSQL checkpoint；故障时拒绝运行，内存仅限开发显式启用。
- 支持 SSE 输出执行进度与回答文本。
- 提供审计日志、Token 用量采集、Prometheus 指标和 OpenTelemetry 链路追踪。
- 提供 Prompt 版本管理、知识候选审核与用户管理接口。

## 系统架构

以下为主工作流的简化结构：

```mermaid
flowchart TD
    U[Web UI / API Client] --> API[FastAPI · Authentication]
    API --> P[Planner]

    P --> K[Knowledge Agent]
    P --> A[Analysis Agent]
    P --> E[Execution Agent]
    P -->|Direct response| G[Aggregator]

    K --> R[RAG · Milvus · Reranker]
    A --> D[CRM Snapshot · Python Aggregation]
    E --> T[Tool Gateway · RBAC]
    T --> H[Approval / Saga / Business Adapters]

    K --> G
    A --> G
    E --> G

    G -->|Replan · max 2 rounds| P
    G --> O[Answer · Sources · Execution Status]
```

| 层次 | 主要技术 |
| --- | --- |
| API 与交互 | FastAPI、Web UI、SSE |
| Agent 编排 | LangGraph、LangChain |
| 模型接入 | DeepSeek Flash 默认、Pro 复杂任务；Ollama 仅开发选项 |
| 检索与重排 | Milvus、百炼北京 text-embedding-v4、qwen3-rerank |
| 业务数据与状态 | PostgreSQL、Redis Stack |
| 安全与流程 | JWT、RBAC、人工审批、Saga |
| 可观测性 | OpenTelemetry、Prometheus、审计日志 |
| 部署与检查 | Docker Compose、Kubernetes 清单、GitHub Actions |

## 快速开始

以下以 macOS / Linux 的本地开发环境为例：
基础设施通过 Docker Compose 启动，API 与 Worker 在本机运行。
工程交付目标是隔离 Linux 单机 Compose；以下为待验收操作步骤，需准备独立数据、账户与 API 预算，不能直接作用于当前业务环境。

### 1. 准备环境

- Python 3.11+
- Git
- Docker 与 Docker Compose
- 百炼北京 embedding/reranker 与 DeepSeek 的独立凭证、访问权限及预算
- 模型/数据/角色配置见[模型 profile](enterprise-agent/deploy/MODEL_PROFILE.md)；别名需在真实验收时再次核对

所选 profile 不需下载本地模型；旧 BGE/Ollama 路径不属于首轮生产候选。

### 2. 获取代码并安装依赖

```bash
git clone https://github.com/zhenkun26/BusinessAgent.git
cd BusinessAgent/enterprise-agent

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r deploy/requirements-prod.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，重点检查以下配置：

| 配置项 | 用途 |
| --- | --- |
| `MODEL_PROFILE` | 当前候选保持 `bailian-deepseek-v1` |
| `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`PRIMARY_LLM_MODEL`、`LITE_LLM_MODEL` | DeepSeek 凭证与 profile 规定的模型名称 |
| `EMBEDDING_API_KEY`、`RERANKER_API_KEY` | 独立百炼北京凭证；端点、维度和集合必须配套 |
| `POSTGRES_*`、`REDIS_*`、`MILVUS_*` | 对应隔离基础设施 |
| `JWT_SECRET_KEY`、`AUTH_REQUIRE_PASSWORD`、`AUTH_CHECK_DB` | 随机密钥，启用口令与数据库身份检查 |
| `TOOL_PROVIDER`、`CRM_TOOL_PROVIDER` | 首次合成数据体验使用 Mock；HTTP 参考服务需另行显式配置 |
| `MODEL_STARTUP_PROBES_ENABLED` | 初始为 false；生产启动须先明确授权付费探针 |

不要提交 `.env` 凭证。当前 profile 使用外部模型；可选本地 ML 实验使用独立声明的
`deploy/requirements-ml.txt`，不是当前候选必需项。不可变镜像、显式迁移与生产配置见
[部署指南](enterprise-agent/deploy/DEPLOY.md)。

### 4. 启动依赖服务

```bash
docker compose up -d etcd minio milvus-standalone postgres redis
docker compose ps
```

等待依赖服务就绪。C03 已取消 PostgreSQL 自动执行应用初始化 SQL；空库必须先显式迁移至 schema v7、检查版本并创建管理员，再启动应用。命令与凭证输入方式见[数据库初始化手册](enterprise-agent/deploy/DATABASE_BOOTSTRAP.md)。已有库只允许对获准的隔离副本显式接管，不直接修改当前库。

可先运行 `python -B -m app.core.db_bootstrap plan` 做离线预览；真实数据库、API 与 Linux 部署验收仍 BLOCKED。当前生产候选使用[外部模型 profile](enterprise-agent/deploy/MODEL_PROFILE.md)，下文涉及真实模型/入库的步骤需另行授权。

### 5. 导入示例知识并启动服务

使用[知识发布契约](docs/50-engineering/knowledge-publication.md)中的获准上传、审核与发布流程，可将 `eval/sample_docs/财务报销制度.md` 作为合成输入。历史直接入库命令不能证明当前发布可见性；真实入库会调用外部模型并写存储，本候选尚未执行验收。

启动 API：

```bash
python -m app.main
```

在另一个终端中，进入 `enterprise-agent/` 并激活同一虚拟环境，
启动后台 Worker：

```bash
python -m app.worker
```

Worker 负责后台任务，包括文档入库处理、审批超时与补偿重试。

### 6. 打开应用

| 入口 | 地址 |
| --- | --- |
| Web 界面 | http://localhost:8000/ui/ |
| API 文档 | http://localhost:8000/docs |
| 服务存活检查 | http://localhost:8000/health |
| 依赖状态 | http://localhost:8000/ready |
| Prometheus 指标 | http://localhost:8000/metrics |

使用显式 bootstrap 的账户登录，由 `/me` 核验当前角色；没有默认口令或按角色绕过登录。可以先尝试：

> 公司的差旅报销有哪些规定？

再使用具备订单查询权限的角色尝试：

> 统计所有客户的订单总额。

`/health` 用于检查 API 是否存活；
完整功能还依赖数据库、检索服务、模型及相应配置。

## 验证与测试

从仓库根目录使用已审查的离线清单：

```bash
python3 -I -B enterprise-agent/scripts/final_candidate.py
# Explicitly run reviewed entries and retain a fresh receipt:
python3 -I -B enterprise-agent/scripts/final_candidate.py --execute --record candidate-001
```

范围与副作用见[最终候选验证说明](docs/50-engineering/final-candidate-verification.md)。
真实门禁未齐时，执行后的退出码为 2。全量 pytest/插件、历史 W5–W9 脚本须另行审查依赖与副作用；固定清单不代表所有测试或真实服务已通过。历史 CI 和上方 `main` 徽章不代表当前候选验收；按提交绑定的 PR/CI 记录与阻塞见[交付状态](docs/50-engineering/delivery-status.md)。

## 当前状态与边界

核心 Agent 工作流、RAG、权限校验、审批、补偿和 Web 交互已有实现。
仓库同时保留自动化测试、技术验证与交付记录。

当前需要注意：

- 数据分析按 CRM provider 读取有界快照并生成确定性报告；真实 HTTP 数据分析验收仍 BLOCKED。
- 业务工具默认采用 Mock；外部适配代码不等于已完成真实系统验收。
- CRM、邮件及 SSO 的真实接入仍需接口契约、测试环境与联调证据。
- 正式 UAT、真实安全验收、灰度运行与生产放行尚未完成。
- 仅独立子任务可并行，识别到依赖会拒绝整单；通用 DAG、多租户和长期记忆不在当前候选范围。
- Checkpoint 不再自动回退；真实双进程持久化与租约到期写入 fencing 仍未验收。
- 单组织、Linux 单机 Compose 为目标；Kubernetes/多机高可用、容量实测和生产就绪均未通过当前验收。
- 源码版本保持 1.3.0，收尾变更未发布；提交、镜像与 schema 身份须分别记录，L/D/O/B/S/R 全部运行矩阵及完整 RAG 继续 BLOCKED。

详细进度与待办见 [ROADMAP](docs/40-process/ROADMAP.md)。

## 项目结构

```text
BusinessAgent/
├── README.md               # Chinese introduction and canonical navigation
├── README-en.md            # English translation
├── enterprise-agent/
│   ├── app/
│   │   ├── agents/          # Knowledge, Analysis, Execution
│   │   ├── graph/           # Planning, dispatch, aggregation, checkpoints
│   │   ├── rag/             # Ingestion, retrieval, reranking, fallback
│   │   ├── tools/           # Business tools, HTTP adapters, Saga
│   │   ├── api/             # Chat, authentication, approval, administration
│   │   ├── security/        # JWT and RBAC
│   │   ├── observability/   # Audit, tracing, metrics, token usage
│   │   └── static/          # Web interface
│   ├── tests/              # Automated tests
│   ├── eval/               # Evaluation scripts and sample documents
│   └── deploy/             # Deployment, database and monitoring configuration
├── docs/                   # Product, operations and engineering documentation
├── openspec/               # Specifications and change records
└── interview/              # Presentation and interview materials
```

## 文档

| 内容 | 入口 |
| --- | --- |
| 全仓库目录索引 | [contents](contents.md) |
| 产品方案 | [企业知识工作流 Agent 产品方案](docs/10-product-plan/企业知识工作流Agent产品方案_v3_整合版.md) |
| 产品功能与设计 | [产品文档](docs/20-product/产品文档.md) |
| Web 界面使用 | [产品使用手册](docs/30-guides/产品使用手册-前端版.md) |
| 场景与操作示例 | [使用案例手册](docs/30-guides/使用案例手册.md) |
| 运维与故障处理 | [运维维护手册](docs/30-guides/运维维护手册.md) |
| 部署配置 | [部署说明](enterprise-agent/deploy/DEPLOY.md) |
| 示例知识文档 | [sample_docs](enterprise-agent/eval/sample_docs/) |
| 开发进度 | [ROADMAP](docs/40-process/ROADMAP.md) |
| 设计决策 | [DECISIONS](docs/40-process/DECISIONS.md) |
| 已知问题 | [ISSUES](docs/40-process/ISSUES.md) |
| 版本变化 | [CHANGELOG](CHANGELOG.md) |
| 项目介绍与面试材料 | [演示网页](interview/产品介绍网页/index.html) · [面试备稿](interview/Agent项目面试备稿.md) |

## 反馈与贡献

欢迎通过 [GitHub Issues](https://github.com/zhenkun26/BusinessAgent/issues)
提交问题或讨论改进方向。

报告问题时，请提供复现步骤、预期行为、实际行为和已脱敏的环境信息。

提交变更前，请阅读 [AGENTS.md](AGENTS.md) 与
[项目变更规范](openspec/specs/openspec-normalization/spec.md)，
并运行与修改范围相关的检查。

## 许可证

[MIT](LICENSE)
