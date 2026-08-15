# ISSUES · 问题、坑与 backlog

> 问题与坑记录的单一事实源。格式：状态（open/fixed）/ 优先级 / 现象 / 根因 / 修复 / 验证 / 日期。
> 已从运维维护手册第 8 节与临时备忘迁移；新问题追加在「待办与开放问题」，已修复的记入「已修复」。

## 一、待办与开放问题

### I-12 备份恢复演练：MinIO 备份缺口发现与收口（2026-08-05 发现，2026-08-06 复演关闭）

- 状态：fixed（2026-08-06 复演验证通过）· 优先级 P1
- 现象：change load-test-and-dr-drill 首次真实恢复演练（隔离 Compose project `dr-drill`，独立端口/数据卷，未触碰运行中实例）发现：原备份（每日 pg_dump + etcd snapshot）能完整恢复 PG 与 Milvus 元数据，但 MinIO 对象存储（Milvus 向量数据本体）无备份，集合元数据恢复后 load 挂起（loadSegmentCount=0），知识问答数据层不可恢复。
- 第一轮演练记录（2026-08-05，全程计时，环境演练后销毁）：
  - 备份产出：`scripts/backup.sh` 生成 `pg_20260805_183342.sql.gz`（15K）+ `etcd_20260805_183342.db`（404K）。
  - PG 恢复：清库回放零错误；5 张关键表行数与备份时点一致（users 10 / sessions 19 / documents 7 / audit_logs 204 / approval_requests 4）。实测 RTO ≈ 2.5 分钟。
  - etcd 恢复：DEPLOY.md 原文流程（运行中 etcd 上 restore）实测必失败（`data-dir not empty`）；修正流程（停 milvus → 停 etcd → 清数据卷 → 临时容器 restore → 启 etcd → 启 milvus）成功，294 键恢复；净耗时 ≈ 2 分钟。
  - Milvus：元数据恢复后 stats row_count=28 但 segment 缺失、load 挂起 → 发现备份缺口（本条根因）。
- 修复（2026-08-06）：`scripts/backup.sh` 补齐 MinIO + milvus 本地卷整卷 tar 备份（可选 `STOP_MILVUS=1` 严格一致快照）；DEPLOY.md 5.1/5.3 同步三件套口径与完整恢复步骤。
- 第二轮复演验证（2026-08-06，备份 `*_20260806_075802.*` 四件套）：PG 清库回放零错误、行数一致（users 10 / sessions 19 / audit_logs 204）；etcd snapshot 恢复成功；MinIO/milvus 卷解包恢复；**集合 `enterprise_knowledge` load 成功、row_count=28 与备份时点一致、真实 query 返回数据**。**全栈实测 RTO ≈ 194 秒（3.2 分钟，达标线 1h）**；备份时点与演练时点同刻，RPO 实测无数据丢失（日常 RPO≤24h 依赖 crontab 落实，DEPLOY.md 5.2）。
- 验证：两轮演练均用 `deploy/docker-compose.dr-drill.yml` 隔离副本，运行中实例数据零触碰；演练环境均已 `down -v` 销毁。

### I-09 跨机器迁移后本地启动环境缺失（2026-08-04）

- 状态：fixed（已恢复）· 优先级 P2
- 现象：项目从 Windows 拷贝到 macOS 后，登录页/全站请求 Failed to fetch、网站打不开。
- 根因：① 后端未运行（8000 无监听、Docker daemon 未启动）；② 无项目 Python 环境与数据库初始化；③ 旧 uvicorn 仅绑定 127.0.0.1，IPv6 localhost(::1) 与局域网不可达；④ 从加粗文案复制的 URL 带 `**` 后缀导致 404（日志 `GET /ui%2A%2A 404`）。
- 修复：启动 Docker（PG/Redis）→ uv 建 venv 装依赖 → init.sql + 迁移 001/002 → 按 .env `APP_HOST=0.0.0.0` 启动 API；前端 file:// 直开给出明确指引；main.py 增加 URL 尾部 `**` 清洗重定向；新增 macOS 一键启动脚本 `启动智多星.command`。
- 验证：`/health` healthy、登录 200、`/ui` 200、`/ui**` 自动重定向 200。
- 注意：知识问答仍需 Milvus + 本地模型（bge-m3/reranker），`.env` 模型路径为 Windows 路径，本机未配置。

### I-10 本机原生 Redis 与 Docker Redis 端口冲突（2026-08-04）

- 状态：fixed · 优先级 P2
- 现象：限流器报「AUTH called without any password configured」降级内存；checkpointer 降级 PG 后报 NotImplementedError，聊天全部失败。
- 根因：macOS 原生 Homebrew Redis（`homebrew.mxcl.redis`，无密码）监听 127.0.0.1:6379，把 Docker Redis（带 requirepass）在 IPv4 回环上遮蔽；应用连 localhost 时命中原生 Redis，认证必然失败。
- 修复：`brew services stop redis` 解除占用（可逆：`brew services start redis` 恢复）；启动脚本 `启动智多星.command` 增加 6379 冲突自检。
- 验证：限流器「Redis(生产模式)」、Redis Checkpointer 初始化成功、聊天 66ms 返回、`/ready` db/milvus healthy。

### I-11 最终对抗性生产级审查（2026-08-04）

- 状态：fixed（P0/P1 已修）· 优先级 P0
- 内容：12 项漏洞（JWT 默认密钥、认证绕过、默认数据库口令、Redis 密码日志泄漏、禁用用户越权、CORS、PG checkpointer 500、Milvus 表达式注入、审计缓存丢失、配置幻觉、缺 TraceId 等）全部修复并补 18 项测试。
- 详细报告：[生产对抗性审查与部署验收报告.md](生产对抗性审查与部署验收报告.md)
- 验证：36/36 测试通过、1000 并发 0 失败、生产镜像 742MB 冒烟通过、K8s 清单 8 文件校验通过。

### I-01 压测未做

- 状态：fixed（2026-08-06 正式阶梯压测达标）· 优先级 P3
- 现象：功能验证充分，并发承载未知。
- 计划：vegeta/k6 阶梯加压，盯 P95 与 worker 占用；预期瓶颈：云端 LLM rate limit > uvicorn worker > Milvus 内存。
- 落地（2026-08-05，change load-test-and-dr-drill）：工具定 k6（本机无 k6 时 docker `grafana/k6` 兜底）；阶梯脚本 `enterprise-agent/eval/load_test_k6.js` + 入口 `eval/run_load_test.sh` + 报告渲染 `eval/render_load_report.py`，thresholds 对齐 SLA 初值（p95≤2s/p99≤5s/错误率<0.5%，按接口分组），未达标即非零退出。
- 正式压测（2026-08-06，formal 档，9.5 分钟阶梯）：394,463 请求、峰值 675 req/s、checks 100%、整体错误率 0.000%；`/health`（200 VU）p95=190ms/p99=208ms，`/chat/message`（10 VU，完整响应口径）p95=1,431ms/p99=1,651ms，**全部阈值通过（k6 退出码 0）**。报告：`eval/results/loadtest_report_20260806_100427.md`（含瓶颈分析与压测脚本 7 轮迭代史）。
- SLA 校准结论（供 production-readiness-baseline 归档消化）：**初值 p95≤2s/p99≤5s/错误率<0.5% 实测达标，无需调整**；适用前提（单机 dev 形态、单 worker、云端 DeepSeek 供应）与复测方式见报告第 6 节。
- 预期瓶颈复盘：云端 LLM rate limit 本轮并发包线内未触顶；实际第一约束是应用层限流（30 req/min/用户，对话接口的设计上限）；单 worker 在 675 req/s 下仍有大量余量。

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

- 状态：fixed（2026-08-05，change security-hardening-plus）· 优先级 P3
- 现象：Redis 快照随会话数持续增长。
- 修复：`checkpointer.py` 初始化 AsyncRedisSaver 时传入滑动 TTL 配置（`default_ttl` + `refresh_on_read`），每次会话活跃（写入/读取）刷新对应 thread 键过期时间；TTL 走配置项 `CHECKPOINT_TTL_DAYS`（初值 7 天，<=0 关闭）；PG/Memory 降级后端不设 TTL。
- 验证：`tests/test_checkpoint_ttl.py` 2 例断言构造参数；实跑 Redis 冒烟——aput 后 `checkpoint:` 与 `checkpoint_latest:` 键 TTL=604800s；`eval/run_w6_checkpoint` 回归（Redis 主路径初始化成功、TTL 启用日志可见；state_persistence 用例因本机缺 bge-m3 模型未过，与本次改动无关）。

### I-07 token usage 部分采集

- 状态：fixed（2026-08-05，change security-hardening-plus）· 优先级 P3
- 现象：仅 knowledge 提取 tokens_used 落 AgentState，未持久化 sessions.token_count；analysis/execution/aggregator 自身调用未采集。
- 修复：新增 `app/observability/token_usage.py`（LangChain AsyncCallbackHandler + contextvar 请求级累加器），统一 chat model 封装（`app/rag/llm.py` 三处构造点）挂接 callback，覆盖 planner/analysis/execution/aggregator/knowledge 全部调用方；Prometheus counter `agent_llm_tokens_total`（model/token_type）每次调用递增；aggregator 汇总读累加器总量落 `AgentState.tokens_used`；API 层（`/message` 与 `/stream`）写审计 payload 并 fire-and-forget 回写 `sessions.token_count`（失败仅记日志）；knowledge 原有 `usage_metadata` 独立提取口径已移除（改读累加器差值）。
- 验证：`tests/test_token_usage.py` 8 例（双口径提取/Prometheus 递增/aggregator 汇总/回写与失败容错）全绿；W5 对话回归实跑——多任务场景 tokens_used=2514（覆盖 planner+execution+aggregator 调用），全量 89 用例无回归。
- 附带修复：W5 回归暴露重规划回边在 langgraph 1.2.10 下崩溃（`TypeError: unhashable type: 'dict'`）——条件边不支持 `(node, updates)` 元组返回；状态更新（轮次递增/历史追加/agent_results 重置）移至 `planner_node` 重规划分支，`route_after_aggregator` 只返回目标节点；`tests/test_agent_replan.py` 同步更新，W5 实测 2 轮重规划正常结束。

### I-08 长期记忆 user_memories 未接

- 状态：open · 优先级 远期
- 现象：表已建（memory JSONB + memory_type），代码未读写。
- 计划：写入侧 aggregator 后异步抽取；读取侧 planner 注入；需配套遗忘/过期机制。

### I-09 CRM/邮件/SSO 外部联调条件未齐

- 状态：blocked · 优先级 P2 · 关联 `openspec/changes/crm-mail-sso-integration`
- 现象：CRM 创建/删除契约、邮件内部/外部撤回语义、IdP OIDC 端点与 claims、三系统沙箱凭据尚未确认；本地实现只能完成配置隔离、幂等/补偿入口和 SSO 身份映射 schema。
- 处置：所有真实 provider 默认关闭，邮件真实补偿显式返回未完成契约错误；外部条件齐备后按 CRM → 内部邮件 → 外部邮件 → SSO 顺序补契约测试和灰度。
- 解除条件：外部团队提供可验证契约、可达测试环境和凭据，并在 `tasks.md` 完成 1.1-1.4 后重跑相关验收。

## 二、已修复（按日期倒序）

### 2026-08-15 生产镜像 runner 阶段 pip 清理顺序导致 CI 构建失败

- 状态：fixed（代码修复已完成，等待 CI 复跑）· 优先级 P1
- 现象：CI 的 Python 3.11/3.13 单元测试通过，但生产镜像构建在 `Dockerfile.prod:74-75`
  返回 exit code 127。
- 根因：runner 在 `COPY --from=builder /opt/venv /opt/venv` 之前调用
  `/opt/venv/bin/pip`；该路径尚不存在，且前一个命令已经卸载了基础镜像的 pip。
- 修复：`enterprise-agent/Dockerfile.prod` 先清理系统 Python 的 pip，再复制 venv，最后用
  `/opt/venv/bin/python -m pip` 清理 venv 内 pip；新增 `tests/test_dockerfile_prod.py` 固化顺序。
- 验证：相关 Python 测试 10/10 通过、Ruff 通过、OpenSpec strict 校验通过；本机 Docker daemon
  未启动，真实 Docker build 尚待 CI 复跑确认。

### 2026-08-15 灰度方案观察期口径统一

- 状态：fixed（方案已修订，真实灰度未执行）· 优先级 P2
- 现象：原方案 G1/G2 为 1-2 周、G3 为“2 周以上”，与总观察期 2-4 周无法形成可排期的上限。
- 修复：统一为 G1 1 周、G2 1 周、G3 2 周，最短总观察期 4 周；延长必须在 `DECISIONS.md` 留痕。
- 验证：灰度方案核验器返回 `overall_status=passed`、`review_conclusion=conditional`；业务观察阈值仍待产品负责人确认。

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
