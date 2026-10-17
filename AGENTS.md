# BusinessAgent 项目说明

## 项目概览

本仓库是「智多星——企业级多智能体平台」的工程实践项目：基于
LangChain + LangGraph + Milvus 构建的多 Agent 系统。当前没有真实企业使用，工程验证与企业现场生产验证须分开记录；交付边界见 `docs/50-engineering/engineering-delivery-baseline.md`。后端代码位于
`enterprise-agent/`，文档统一存放在 `docs/`（六大层分类），面试与演示资产
独立存放在 `interview/`。

## 目录结构

- `enterprise-agent/`：FastAPI 后端主工程，包含 `app/`（API、Agent、Graph、
  RAG、工具、安全、可观测性）、`eval/`（W2-W9 评测脚本）、`deploy/`（部署配置）、
  `README.md`
- `docs/`：统一文档体系，按六大层分类（产品方案 / 产品文档 / 操作手册 /
  过程记录 / 工程文档 / 知识数据库 + 归档层），每层有 README 索引
- `interview/`：面试与演示资产独立体系（面试备稿 + 产品介绍网页）
- `openspec/`：openspec 变更与主规格（需求演进规范化）
- 根目录保留：`README.md`（导航入口）、`contents.md`（目录索引）、
  `CHANGELOG.md`（版本变更）、`启动智多星.bat`（一键启动）

## 常用命令

以下命令在 `enterprise-agent/` 目录下执行：

```bash
# 启动依赖服务（Milvus + PostgreSQL + Redis + Ollama）
docker compose up -d etcd minio milvus-standalone postgres redis

# 启动 API（开发模式，先复制 .env.example 为 .env 并填写配置）
python -m app.main

# 健康检查与 API 文档
curl http://localhost:8000/health
open http://localhost:8000/docs

# 端到端验证脚本（W5-W9）
python -m eval.run_w5_e2e
python -m eval.run_w6_checkpoint
python -m eval.run_w7_execution
python -m eval.run_w9_milvus
python -m eval.run_w9_tracing
```

## 工程约定

- Python 3.11+，遵循 PEP 8，行宽 100（ruff 配置见 `pyproject.toml`）。
- 全量类型注解；异步代码优先；类必须在 `__init__` 中初始化全部实例属性。
- 密钥只从环境变量读取；`.env`、`.env.local`、日志和审计输出永不提交。
- SQL 一律参数化；外部 API 调用必须设置超时、重试并处理网络异常。
- 所有外部输入视为不可信，使用前校验；涉及删除、清库等破坏性操作先与用户确认。
- 修改后端行为后运行相关 `eval/` 脚本验证；新增公共接口时补充单元测试。
- 保持根目录中文文档与代码同步，重要变更同步更新 README 或对应手册。
- 版本管理：项目版本单一事实源为 `enterprise-agent/app/__init__.py` 的 `__version__`（语义化版本）；升级时同步 `pyproject.toml`、`CHANGELOG.md`、核心文档版本头并打 Git tag `vX.Y.Z`。

## openspec 管控

- 需求与文档演进一律走 openspec 生命周期：explore → propose → apply → archive，
  流程规则单一事实源为 `openspec/specs/openspec-normalization/spec.md`。
- AI 工具集成：Kimi Code（`.kimi-code/skills/`）与 Codex（`.codex/skills/`）均已
  由 `openspec init` 生成 6 个工作流 skill；CLI 升级后用 `openspec update` 刷新。
- 主规格 15 项见 `openspec/specs/`（2026-10-17）；新需求在 `openspec/changes/` 下开启 change。
- 当前工程收尾 change 为 `engineering-delivery-closeout`：S0/C24 前置已完成并推送；C01 配置独立提交 `2a9c364` 已推送，运行验收 BLOCKED；C02 外部模型增量 `42bfc7f` 已推送，真实 API/Linux 验收 BLOCKED；C03 增量 `fc8da91` 已推送，真实 PostgreSQL/API/Linux 验收 BLOCKED；C04 会话归属增量 `dbc8236` 已推送，真实 HTTP/PG 验收 BLOCKED；C05 增量 `9f5397c` 已推送；C06 `6955133` 已推送；C07 `ceae708` 已推送；C08 `d81c281` 已推送；C09 `079cd62` 已推送；C10 `a57bd4e` 已推送（此前 27 项专项 + 139 项相关回归 PASS），真实双进程/Redis/LangGraph/Milvus/JWT/API/SSE/PG/Linux 验收 BLOCKED，浏览器/SSO 与历史凭证处置阻塞保留；租约到期后的同会话写入 fencing 尚未解决，C10 整项 open。C18 参考契约前置 `317aa7f` 已推送；C12 `21b5287` 已推送；C14 持久任务、知识审核入队与 worker 初始化离线增量完成（43 项专项 + 112 项相关回归 PASS），真实运行验收 BLOCKED；C14 整项 open，Saga 恢复/HTTP 补偿等待 C13，审计非删除回写等待 C21。本轮本地交付后暂停，不进入 C13。顺序以 ROADMAP 为准，验收以 ISSUES C01–C25 为准。真实企业接入与 UAT/灰度两个 change 保持独立，不以参考环境通过替代。
- 离线前置核验使用 `python3 -I -B enterprise-agent/scripts/safe_validate.py`（仓库根目录）；默认只输出摘要，exit 2 可表示真实 UAT/发布仍阻塞，不等于入口失败。副作用范围见 `docs/50-engineering/safe-validation.md`；其他脚本不得自动视为已通过安全审查。

## 关键文档

- [enterprise-agent/README.md](enterprise-agent/README.md)
- [contents.md](contents.md)（全仓库目录树索引）
- [docs/20-product/产品文档.md](docs/20-product/产品文档.md)
- [docs/30-guides/运维维护手册.md](docs/30-guides/运维维护手册.md)
- [docs/30-guides/产品使用手册-前端版.md](docs/30-guides/产品使用手册-前端版.md)
- [docs/30-guides/使用案例手册.md](docs/30-guides/使用案例手册.md)
- [docs/40-process/ROADMAP.md](docs/40-process/ROADMAP.md)（里程碑规划）
- [docs/40-process/ISSUES.md](docs/40-process/ISSUES.md)（问题与坑记录）
- [docs/40-process/DECISIONS.md](docs/40-process/DECISIONS.md)（设计决策记录）
