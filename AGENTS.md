# BusinessAgent 项目说明

## 项目概览

本仓库是「Hello，小A——企业知识工作流 Agent」的学习与演示项目：基于
LangChain + LangGraph + Milvus 构建的多 Agent 系统。后端代码位于
`enterprise-agent/`，仓库根目录存放产品文档、演示网页、使用手册和阶段性总结。

## 目录结构

- `enterprise-agent/`：FastAPI 后端主工程，包含 `app/`（API、Agent、Graph、
  RAG、工具、安全、可观测性）、`eval/`（W2-W9 评测脚本）、`deploy/`（部署配置）、
  `README.md`
- `产品介绍网页/`：产品演示页（单文件 `index.html`，零构建）
- `前置准备/`：产品方案 v1-v3、研究报告与模型选型资料
- 根目录 `.md` 文件：产品文档、使用手册、运维维护手册、阶段性总结

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

## 关键文档

- [enterprise-agent/README.md](enterprise-agent/README.md)
- [产品文档.md](产品文档.md)
- [运维维护手册.md](运维维护手册.md)
- [产品使用手册-前端版.md](产品使用手册-前端版.md)
- [使用案例手册.md](使用案例手册.md)
