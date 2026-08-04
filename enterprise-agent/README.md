# Hello，小A——企业知识工作流 Agent

> 当前版本:v1.1.0(2026-08-04 业务闭环补全;版本单一事实源见 `app/__init__.py`,变更记录见根目录 `CHANGELOG.md`)

基于 **LangChain + LangGraph + Milvus** 的企业级多 Agent 系统。

## 快速开始

### 1. 环境准备

```bash
# 复制环境变量配置
cp .env.example .env

# 编辑 .env, 填入实际的 API Key 与连接配置
# 必填: OPENAI_API_KEY(DeepSeek) / LOCAL_LLM_BASE_URL(Ollama) / EMBEDDING_MODEL(bge-m3路径)
```

### 2. 启动服务

```bash
# 启动全部服务(Milvus + PostgreSQL + Redis + Ollama)
docker compose up -d etcd minio milvus-standalone postgres redis

# API 在宿主机直接跑(开发模式,.env 默认已指向 localhost + milvus)
python -m app.main

# 或容器化运行(生产模式)
docker compose --profile production up -d api

# 启动监控(可选)
docker compose --profile monitoring up -d prometheus grafana jaeger
```

### 3. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 依赖检查
curl http://localhost:8000/ready

# API 文档
open http://localhost:8000/docs

# 前端界面(单文件 SPA,零构建)
open http://localhost:8000/ui
```

### 4. 登录获取 Token

```bash
# 使用种子用户登录(密码任意)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "销售员张三"}'

# 刷新 Token
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Authorization: Bearer <your-token>"
```

### 5. 发送对话

```bash
# 知识问答(RAG)
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "请告诉我销售政策"}'

# 数据分析(AnalysisAgent)
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "对比一下 C001 和 C002 两个客户的订单金额"}'

# 续接对话(断点恢复)
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "继续", "session_id": "<上次的session_id>"}'
```

### 6. 审批流(高风险操作)

```bash
# 经理发起高风险操作(发外部邮件)→ 自动建审批单,返回审批号 appr_xxx
# 查看待我审批列表
curl http://localhost:8000/api/v1/approvals/pending \
  -H "Authorization: Bearer <manager-token>"

# 批准 → 服务端自动执行(prefill_payload 中的工具调用)
curl -X POST http://localhost:8000/api/v1/approval/appr_xxx/decide \
  -H "Authorization: Bearer <manager-token>" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "comment": "同意"}'
```

### 7. 验证脚本

```bash
# W5 端到端(多Agent 图 + RAG)
$env:REDIS_HOST="localhost"; $env:POSTGRES_HOST="localhost"
python -m eval.run_w5_e2e

# W6 Checkpointer 断点恢复
python -m eval.run_w6_checkpoint

# W7 ExecutionAgent + 工具 + Saga
python -m eval.run_w7_execution

# W9 Milvus 真实接入
python -m eval.run_w9_milvus

# W9 OpenTelemetry tracing
python -m eval.run_w9_tracing
```

## 项目结构

```
enterprise-agent/
├── app/
│   ├── api/              # FastAPI 路由(auth/chat/approval)
│   ├── agents/           # Agent 实现(knowledge/analysis/execution)
│   ├── core/             # 基础设施(database/milvus_client)
│   ├── security/         # 安全(rbac/jwt_manager)
│   ├── middleware/       # 中间件(rate_limit)
│   ├── observability/    # 监控审计(metrics/tracing/audit)
│   ├── graph/            # LangGraph 图(planner/executor/aggregator/dispatcher/checkpointer)
│   ├── tools/            # 工具实现(crm/mail/ticket/base/saga)
│   ├── rag/              # RAG 模块(retriever/reranker/confidence/degradation/embeddings/ingest/vector_store)
│   ├── config.py
│   └── main.py
├── eval/                 # 验证脚本(W2-W9 共 8 个验证)
├── deploy/               # 部署配置(init.sql/prometheus.yml/nginx.conf/DEPLOY.md)
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
└── .env.example
# 文档(产品文档/阶段性总结/使用案例手册)在上一级目录,见下方「关联文档」
```

## 实施进度

### 阶段一: 基础设施(W2-W4) ✅

- [x] **W2** Docker Compose 环境 + 本地 Embeddings(bge-m3) + BGE Reranker + 三层模型分层(DeepSeek v4-pro / v4-flash / qwen3.5:4b)
- [x] **W3** RAG 两阶段检索(向量召回 + BGE 精排) + 场景化置信度决策 + LLM 降级(DeepSeek v4-pro→qwen3.5:4b)
- [x] **W4** RAG 评测体系(命中率/覆盖率/延迟 P95) + 评测数据集

### 阶段二: 多 Agent 协同(W5-W8) ✅

- [x] **W5** LangGraph StateGraph + Planner + Aggregator + Send API 并行 fan-out + 本地小模型闲聊判断优化
- [x] **W6** Redis Checkpointer 三级降级链(Redis→PG→Memory) + interrupt 人工介入 + 跨进程状态恢复
- [x] **W7** ExecutionAgent + ToolGateway(8 工具:CRM/邮件/工单/审批进度) + RBAC 角色权限 + Prompt 注入防护 + Saga 补偿回滚
- [x] **W8** API 层(chat/auth refresh/approval) + 批量审批 batch_id 原子事务 + JWT 刷新 + 限流中间件(Redis 滑动窗口→内存降级)

### 阶段三: 企业级生产化(W9) ✅

- [x] **W9-1** 生产级 docker-compose.prod.yml(Nginx 反向代理 + 资源限制 + 日志驱动)
- [x] **W9-2** OpenTelemetry tracing 全链路(RAG/Tool/Saga span 注入 + Jaeger 容器 + FastAPI/Redis/requests 自动埋点)
- [x] **W9-3** 部署文档(Nginx + HTTPS + 备份策略 + 健康检查)
- [x] **W9-4** Milvus 真实接入(从 InMemory 切换到 Milvus 2.4 + HNSW 索引 + Partition 命名空间隔离)

### 阶段四: 整体联调 + P1 迭代 ✅(2026-07-26)

- [x] **整体联调** 真实基础设施(Milvus + PG + Redis + Ollama + DeepSeek)端到端 17 项测试全通过,修复 4 个联调 bug(SQLAlchemy text() / checkpointer reducer 残留 / Aggregator 错误掩盖 / JSONB ANY)
- [x] **P1-1** `.env` 修正 VECTOR_STORE_PROVIDER=milvus(向量检索名实相符)
- [x] **P1-2** AnalysisAgent 完整实现(lite LLM 解析分析计划 → Python 真实聚合 → primary LLM 报告,支持对比分析 + 最多 2 轮多跳补充,planner 新增 data_analysis 意图)
- [x] **P1-3** 审批流与 chat 打通(高风险工具 send_email_external 自动建单挂起 → 批准后服务端执行 prefill_payload,decide/resume/batch 三路径)
- [x] **P1-4** 审计日志接线(AuditLogger 改造为 SQLAlchemy 存储,chat/tool/approval/auth/建单/反馈 6 类事件落 audit_logs)
- [x] **P1-5** 知识库反馈循环(/feedback 落 user_feedback,点踩+评论自动生成 documents draft 知识候选)

### 阶段五: P2 迭代 ✅(2026-07-26)

- [x] **P2-1 Prompt 版本管理**:`prompt_versions` 表(draft/active/archived + traffic_weight)+ `app/prompts/` 注册模块(缓存读取、md5 确定性 A/B 分流、DB 故障降级代码默认)+ 管理 API(仅 admin/manager);11 个 prompt 全部从硬编码迁出,E2E 验证 draft→activate→traffic 80/20→回滚,变更落 prompt_change 审计
- [x] **P2-2 用户取消机制**:Agent 内 LLM 调用全部 ainvoke 化(取消在 LLM 等待期间即时生效,顺带消除事件循环阻塞);`POST /chat/cancel`(本人/admin);E2E 实测:长请求 16.6s 取消成功,sessions=cancelled,audit 链 chat_request→chat_cancel_requested→chat_cancelled
- [x] **P2-3 部门级测试数据入库**:dept_sales/dept_finance 专属文档入库,命名空间隔离验证 4/4 通过(`eval/run_p2_namespace.py`);顺带修复降级链跨部门泄露 + partition 静默兜底两个缺陷
- [x] **P2-4 sessions 表梳理**:双轨定责(checkpointer=状态快照,sessions=生命周期元数据);/message 主链路维护 running→completed/failed/cancelled 全状态机;/history 未命中时回查 sessions 兜底

### 架构亮点(已实现)

| 能力 | 实现 |
|------|------|
| RAG 两阶段检索 | 向量粗排(1024×n) + BGE Reranker 精排(top=5) |
| 三级降级链 | LLM(primary: v4-pro→qwen3.5:4b;lite: qwen3.5:4b→v4-flash,初始化降级 + 工具选择/意图分类输出不可用时运行时回退) / 检索(向量→BM25→PG LIKE) / Redis Checkpointer(Redis→PG→Memory) |
| 模型分层 | DeepSeek v4-pro(推理) / qwen3.5:4b 本地(轻量任务主路径:分类/抽取/grounded 生成) / v4-flash(云端降级) |
| 多 Agent 并行 | LangGraph Send API fan-out + planner/dispatcher 动态路由 |
| 数据分析 | AnalysisAgent:LLM 计划解析 + Python 真实聚合 + 对比/多跳,RBAC 按角色取数 |
| 断点恢复 | Redis Checkpointer + interrupt 人机共治 + 可重置 reducer(跨轮不串结果) |
| Saga 补偿 | 多步骤工具执行 + 失败反向回滚 |
| RBAC 权限 | 5 角色 × 8 工具矩阵 + 命名空间文档隔离 + 工具层二次校验 |
| 审批流 | 高风险工具自动建单 → 经理/管理员审批 → 服务端执行,支持批量原子审批 |
| Prompt 安全 | 9 种注入模式检测(系统提示覆盖/身份劫持/代码注入) |
| 可观测性 | Prometheus 指标 + OpenTelemetry tracing(Jaeger) + 审计日志(6 类事件落 PG,本地文件兜底) |
| 反馈循环 | 用户点踩 → user_feedback 入库 + 自动生成知识候选草稿(审核后入库) |
| 限流 | Redis ZSET 滑动窗口 → 内存降级 |
| 流式输出 | SSE `/chat/stream`:节点进度 + token 打字机(astream_events + final_answer 标签过滤,仅面向用户的生成) |
| 前端 | 单文件 SPA(`/ui`,零构建 FastAPI 托管):对话(流式/取消/反馈)/审批/Prompt 管理/系统状态,角色感知 |

### 剩余工作(技术债务)

| 优先级 | 任务 |
|--------|------|
| P2 | Prompt 版本管理(A/B 测试) |
| P2 | 用户取消机制(cancellation token) |
| P2 | 部门级测试数据入库,验证命名空间隔离 |
| P2 | sessions 表与 checkpointer 关系梳理 |
| P3 | 压测(vegeta/k6) |
| P3 | UAT + 安全测试 |
| P3 | needs_replan 标志语义复查(知识问答误报 true) |
| P3 | pymilvus 3.1 将移除 ORM 风格 API,`milvus_client.py`/`degradation.py` 需迁移到 MilvusClient(已在依赖清单钉 `<3.1` 防误升级) |
| P3 | 开发环境 uvicorn reload 在 Windows 卡住 |

## 关联文档

- [v3 产品方案](../企业知识工作流Agent产品方案_v3_整合版.md)
- [部署文档](deploy/DEPLOY.md)
- [阶段性总结(W2-W6)](../阶段性总结_W2-W6.md)
- [阶段性总结(W7-W9 + 整体联调)](../阶段性总结_W7-W9_联调.md)
- [产品文档](../产品文档.md)
- [使用案例手册](../使用案例手册.md)

## 技术栈

| 组件 | 版本 | 用途 |
| :-- | :-- | :-- |
| Python | 3.11+ | 运行时 |
| LangChain | 1.x | 原子能力层 |
| LangGraph | 1.2+ | Agent 编排 |
| pymilvus | 2.4+(实测 3.0) | 向量检索客户端(3.1 将移除 ORM API,代码有弃用告警待迁移) |
| FastAPI | 0.115+ | Web 框架 |
| PostgreSQL | 16 | 业务/审计存储 |
| Redis | 7 (redis-stack-server) | Checkpointer / 缓存 / 限流 |
| Ollama | latest | 本地小模型托管(qwen3.5:4b) |
| BGE-M3 | local | Embeddings(1024维) |
| BGE Reranker | local | 精排重排序 |
| OpenTelemetry | 1.x | 全链路追踪 |
| Jaeger | 1.60 | Trace 可视化 |
| Prometheus | latest | 指标采集 |
