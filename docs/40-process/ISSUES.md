# ISSUES · 问题、坑与 backlog

> 问题与坑记录的单一事实源。格式：状态（open/fixed）/ 优先级 / 现象 / 根因 / 修复 / 验证 / 日期。
> 已从运维维护手册第 8 节与临时备忘迁移；新问题追加在「待办与开放问题」，已修复的记入「已修复」。

## 一、待办与开放问题

### I-09 跨机器迁移后本地启动环境缺失（2026-08-04）

- 状态：fixed（已恢复）· 优先级 P2
- 现象：项目从 Windows 拷贝到 macOS 后，登录页/全站请求 Failed to fetch、网站打不开。
- 根因：① 后端未运行（8000 无监听、Docker daemon 未启动）；② 无项目 Python 环境与数据库初始化；③ 旧 uvicorn 仅绑定 127.0.0.1，IPv6 localhost(::1) 与局域网不可达；④ 从加粗文案复制的 URL 带 `**` 后缀导致 404（日志 `GET /ui%2A%2A 404`）。
- 修复：启动 Docker（PG/Redis）→ uv 建 venv 装依赖 → init.sql + 迁移 001/002 → 按 .env `APP_HOST=0.0.0.0` 启动 API；前端 file:// 直开给出明确指引；main.py 增加 URL 尾部 `**` 清洗重定向；新增 macOS 一键启动脚本 `启动小A.command`。
- 验证：`/health` healthy、登录 200、`/ui` 200、`/ui**` 自动重定向 200。
- 注意：知识问答仍需 Milvus + 本地模型（bge-m3/reranker），`.env` 模型路径为 Windows 路径，本机未配置。

### I-10 本机原生 Redis 与 Docker Redis 端口冲突（2026-08-04）

- 状态：fixed · 优先级 P2
- 现象：限流器报「AUTH called without any password configured」降级内存；checkpointer 降级 PG 后报 NotImplementedError，聊天全部失败。
- 根因：macOS 原生 Homebrew Redis（`homebrew.mxcl.redis`，无密码）监听 127.0.0.1:6379，把 Docker Redis（带 requirepass）在 IPv4 回环上遮蔽；应用连 localhost 时命中原生 Redis，认证必然失败。
- 修复：`brew services stop redis` 解除占用（可逆：`brew services start redis` 恢复）；启动脚本 `启动小A.command` 增加 6379 冲突自检。
- 验证：限流器「Redis(生产模式)」、Redis Checkpointer 初始化成功、聊天 66ms 返回、`/ready` db/milvus healthy。

### I-11 最终对抗性生产级审查（2026-08-04）

- 状态：fixed（P0/P1 已修）· 优先级 P0
- 内容：12 项漏洞（JWT 默认密钥、认证绕过、默认数据库口令、Redis 密码日志泄漏、禁用用户越权、CORS、PG checkpointer 500、Milvus 表达式注入、审计缓存丢失、配置幻觉、缺 TraceId 等）全部修复并补 18 项测试。
- 详细报告：[生产对抗性审查与部署验收报告.md](生产对抗性审查与部署验收报告.md)
- 验证：36/36 测试通过、1000 并发 0 失败、生产镜像 742MB 冒烟通过、K8s 清单 8 文件校验通过。

### I-01 压测未做

- 状态：open · 优先级 P3
- 现象：功能验证充分，并发承载未知。
- 计划：vegeta/k6 阶梯加压，盯 P95 与 worker 占用；预期瓶颈：云端 LLM rate limit > uvicorn worker > Milvus 内存。

### I-02 UAT + 安全测试未做

- 状态：open · 优先级 P3
- 现象：真实用户验收与 Prompt 注入攻击面未实测。

### I-03 needs_replan 偶发误报

- 状态：fixed（2026-08-04 随重规划闭环落地）· 优先级 P3
- 现象：知识问答正常回答但响应偶发 `needs_replan=true`。
- 修复：`needs_replan` 语义统一为「知识无结果 / 部分覆盖 / 分析无数据」三类，aggregator 后条件回边自动补检（≤2 轮，见 agent-replan 规格）；部分覆盖标记为有意的补检信号，不再视为误报。

### I-04 pymilvus 3.1 迁移

- 状态：open · 优先级 P3
- 现象：ORM 风格 API 弃用告警，3.1 将移除。
- 缓解：requirements/pyproject 已钉 `>=2.4,<3.1` 防误升级；迁移前跑 `run_p2_namespace` 回归。

### I-05 Windows uvicorn reload 卡死

- 状态：open · 优先级 P3
- 现象：reload 检测变更后不拉起新进程，需手动重启。
- 缓解：开发/演示启动不带 `--reload`。

### I-06 checkpoint 无 TTL / 清理策略

- 状态：open · 优先级 P3
- 现象：Redis 快照随会话数持续增长。
- 计划：按 thread 最近活跃时间滑动过期；sessions 表已可独立支撑元信息查询。

### I-07 token usage 部分采集

- 状态：open · 优先级 P3
- 现象：仅 knowledge 提取 tokens_used 落 AgentState，未持久化 sessions.token_count；analysis/execution/aggregator 自身调用未采集。
- 计划：LangChain callback 统一采集，落 audit payload + Prometheus counter，回写 sessions.token_count。

### I-08 长期记忆 user_memories 未接

- 状态：open · 优先级 远期
- 现象：表已建（memory JSONB + memory_type），代码未读写。
- 计划：写入侧 aggregator 后异步抽取；读取侧 planner 注入；需配套遗忘/过期机制。

## 二、已修复（按日期倒序）

### 2026-07-28 回答质量：意图分类路由 + 运行时 flash 回退 / 闲聊人格化 / 加粗渲染

- 现象：①「查询订单 ORD-xxx」被路由到知识问答；② 闲聊话术机械重复无人格；③ `**5%-10%**` 显示字面星号。
- 根因：① data_operation 定义未覆盖「查询业务记录」；② 闲聊是固定模板；③ CommonMark 侧翼规则不渲染 CJK 相邻加粗。
- 修复：意图分类模板补齐定义 + 运行时云端 flash 回退；闲聊重写为九分支人格话术 + 本地 LLM 即兴兜底；前端 renderMd 预处理。
- 验证：六项实测通过，W7+W5 回归。

### 2026-07-27 前端 14 项走查修复

- 现象：审批种子数据缺 requester_token / payload 扁平、登录响应缺 department、审批失败不可见、点踩取消误发请求、登出状态残留等。
- 修复：`scripts/fix_seed_approvals.py`（重签 10 年期 token + 重写 payload）、TokenResponse 加 department、decide 显示失败原因、前端清理补全。
- 验证：赵六批准三条 batch 单全部 executed；页面经 /ui 确认。

### 2026-07-27 全流程验证收尾

- 现象：① eval 脚本缺 init_milvus 直接跑失败；② 入库脚本不去重导致 collection 从 22 膨胀到 116；③ 外部邮件被错挂内部邮件工具。
- 修复：脚本补 init_milvus；drop 重建 + 标准流程入库回 22 实体；工具选择加地址纠偏（含外部地址改挂外部工具）。

### 2026-07-27 工具参数抽取失败

- 现象：「创建回访任务 + 发内部邮件」连续报「所有子 Agent 执行失败」。
- 根因：工具选择 prompt 未注入参数 schema，本地 qwen 猜错参数名；assignee 显式 null 校验失败。
- 修复：`_param_spec()` 注入字段名/必填/描述；assignee 改 Optional 缺省回填发起人。
- 教训：本地模型「选对工具」与「填对参数」是两层能力，依赖模型猜约定的环节必须显式化。

### 2026-07-26 召回排序：政策场景共享优先平局裁决

- 现象：部门文档（0.528）排到共享政策（0.511）前面，答案来源错位。
- 根因：dept/shared 内容重叠导致近 0.03 噪声带的排序噪声，非候选池挤占（32 条候选全在池）。
- 修复：`_shared_priority_tiebreak`——POLICY 场景分差 ≤0.03 时 shared 优先，带外不干预。
- 验证：`verify_recall_fix.py` 4/4 通过。

### 2026-07-26 模型路由：lite 反转为本地优先 + 移除 Claude 备用链

- 现象：本地调用 44-94s，误判 GPU 争用。
- 根因：ChatOpenAI 走 Ollama /v1 端点时 `extra_body={"think": False}` 被忽略，隐藏思考 token 全量生成。
- 修复：迁 ChatOllama + `reasoning=False`；自评 65.8s→0.23s；移除 Claude 死代码。
- 例外补强：execution 工具选择云端 flash 优先（本地 4B 选错工具，空回退抓不到）。

### 2026-07-26 性能优化：知识问答 58-114s → 14.6s

- 根因：推理模型隐藏推理烧 token、本地 GPU 争用、答案无长度约束。
- 修复：knowledge 答案生成迁 lite flash 且关思考；自评条件化（检索分 ≥0.85 或 ≤0.30 跳过）。

### 2026-07-26 流式 sources 显示 0.000/空标题

- 根因：checkpoint 序列化把 RetrievalSource 包成 `{"lc":...,"kwargs":{...}}`，前端未解包。
- 修复：API `_unwrap_source()` + 前端 `s.kwargs || s` 双保险。
- 教训：跨 checkpoint 边界取数必须防御性解包（AgentResult 变 dict 同源问题）。

## 三、历史坑（联调与 P2 阶段，均已修复）

| 坑 | 修复 |
|---|---|
| SQLAlchemy 2.x 原生 SQL 缺 `text()`，服务起不来 | 全部 `text()` 包装 |
| JSONB `= ANY(col)` 非法导致待审列表 500 | 改 `col ? 'value'` |
| `operator.add` reducer 断点恢复残留上轮结果 | 可重置 reducer `_resettable_add` |
| checkpoint 反序列化 pydantic → dict，Aggregator 崩溃 | 消费方统一 `model_validate` |
| 同步节点跨事件循环调 DB（asyncpg loop 绑定） | executor 改 async 节点 |
| BM25 降级路径漏 dept_namespace 过滤（跨部门泄露） | 降级链补齐同口径 + `run_p2_namespace` 4 项回归 |
| redis:7-alpine 无 RediSearch；覆盖 command 跳过模块加载 | 换 redis-stack-server + 显式 `--loadmodule` |
| 降级链掩盖配置错误（memory 后端 + 关键词兜底） | `/ready` + 响应暴露后端标识 |
| Send API 在节点返回 list[Send] 报错 | 改在条件边函数返回 |
| Planner JSON 示例 `{}` 与 `.format()` 冲突 | 转义 `{{}}` |
| 审批批准后卡 approved_pending_reauth（种子数据缺 token） | `scripts/fix_seed_approvals.py` 重签 token |
| 前端审批页时间慢 8 小时（PG UTC） | 前端按 UTC 解析朴素时间串 |
