# Hello，小A——企业知识工作流 Agent

[![版本](https://img.shields.io/badge/版本-v1.0.0-1e88e5)](https://github.com/zhenkun26/BusinessAgent/releases)
[![CI](https://github.com/zhenkun26/BusinessAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/zhenkun26/BusinessAgent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688)](https://fastapi.tiangolo.com/)
[![Milvus](https://img.shields.io/badge/Milvus-2.4-00A1E9)](https://milvus.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-FF4438)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-多阶段%20%2F%20742MB-2496ED)](https://hub.docker.com/)
[![K8s](https://img.shields.io/badge/Kubernetes-清单就绪-326CE5)](enterprise-agent/deploy/k8s)
[![License](https://img.shields.io/badge/License-未指定-gray)](https://github.com/zhenkun26/BusinessAgent)

> 当前版本:v1.0.0(2026-08-04 生产级基线)

基于 **LangChain + LangGraph + Milvus** 的企业级多 Agent 系统：员工用自然语言一站式完成 **知识问答、数据分析、业务执行**，带权限隔离、审批闭环、全栈降级。

> 本文件是全仓库唯一导航入口。目录索引见 [contents.md](contents.md)，版本变更见 [CHANGELOG.md](CHANGELOG.md)，Codex 工程约定见 [AGENTS.md](AGENTS.md)。

## 快速导航

| 层 | 内容 | 位置 |
|---|---|---|
| 产品方案层 | 现行方案 v3、选型研究 | [docs/10-product-plan/](docs/10-product-plan/README.md) |
| 产品文档层 | 产品权威现状文档 | [docs/20-product/产品文档.md](docs/20-product/产品文档.md) |
| 操作手册层 | 使用案例 / 前端版 / 运维手册 | [docs/30-guides/](docs/30-guides/README.md) |
| 过程记录层 | ROADMAP / DECISIONS / ISSUES / 阶段性总结 | [docs/40-process/](docs/40-process/README.md) |
| 工程文档层 | 后端 README、部署指南（索引） | [docs/50-engineering/](docs/50-engineering/README.md) |
| 知识数据库层 | 知识库数据与入库规范（索引） | [docs/60-knowledge/](docs/60-knowledge/README.md) |
| 面试与演示 | 面试备稿、产品介绍网页 | [interview/](interview/) |
| 需求演进 | openspec 变更与主规格 | [openspec/](openspec/) |

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

Windows 一键启动：双击根目录 `启动小A.bat`。

## 当前状态

- **已完成**：W2-W9 全部阶段、整体联调 17/17、P1/P2 迭代、前端 v2/v3 与流式输出。
- **进行中**：openspec change `documentation-baseline`（文档基线，本仓库结构重组）与 `complete-business-processes`（业务闭环补齐，0/41 任务）。
- **挂起**：P3 压测、UAT/安全测试等（见 [ROADMAP](docs/40-process/ROADMAP.md) 与 [ISSUES](docs/40-process/ISSUES.md)）。

## 维护入口

- 里程碑规划：[ROADMAP.md](docs/40-process/ROADMAP.md)
- 设计决策：[DECISIONS.md](docs/40-process/DECISIONS.md)
- 问题与坑：[ISSUES.md](docs/40-process/ISSUES.md)
- 版本变更：[CHANGELOG.md](CHANGELOG.md)
- 工程约定：[AGENTS.md](AGENTS.md)
