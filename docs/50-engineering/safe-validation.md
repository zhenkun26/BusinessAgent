# C24 离线安全验证入口

> 前置：2026-10-17；2026-10-19 追加[最终候选离线汇总](final-candidate-verification.md)。两者均不构成全量应用验收或解除企业现场阻塞。
> 入口：[safe_validate.py](../../enterprise-agent/scripts/safe_validate.py)；回归：[test_safe_validation.py](../../enterprise-agent/tests/test_safe_validation.py)。Python 3.11+ 标准库，无新增依赖。

## 1. 使用方法

以下命令从仓库根目录执行，`-I` 隔离 Python 用户环境，`-B` 禁止 bytecode 写入。入口自行定位仓库，不读取 `.env`，不加载应用或 pytest 插件。

```bash
# 只列出允许的检查，不执行检查。
python3 -I -B enterprise-agent/scripts/safe_validate.py --list

# 默认五项，只向 stdout 输出固定字段 JSON，不创建证据文件。
python3 -I -B enterprise-agent/scripts/safe_validate.py

# 只跑 G0 结构回放；不是应用 E2E。
python3 -I -B enterprise-agent/scripts/safe_validate.py --check g0-replay

# 可选：用新的 run ID 独占创建一份证据，不重复使用已有 ID。
python3 -I -B enterprise-agent/scripts/safe_validate.py --record c24-review-001

# 入口自身回归；测试夹具保留，不执行清理。
python3 -I -B enterprise-agent/tests/test_safe_validation.py
```

退出码：`0` = 所选检查结果全部 PASS；`1` = 至少一项 FAIL；`2` = BLOCKED（准备度未齐、来源未审查、执行或记录失败）。当前默认五项的预期是 **exit 2**：函数执行成功，但 UAT 准备度与正式发布仍 BLOCKED。不能把它改成 exit 0 来使门禁变绿。

JSON 中 `execution_status` 描述函数是否完成，`result_status` 描述检查结果；`overall_status` 按 FAIL 优先、其次 BLOCKED 合并。阻塞前置/记录失败时输出固定错误码，不输出异常原文。参数格式错误由 argparse 返回 2；不要把凭证作为参数传入。

`--record RUN_ID` 仅写到 `enterprise-agent/eval/results/safe-validation/RUN_ID.json`。只允许字母、数字、连字符与下划线；文件已存在、路径含符号链接或权限不足即拒绝。全部结果与测试夹具受现有 ignore 规则保护；重复执行生成的新资产保留给用户处理，无自动轮换/覆盖/删除。

## 2. 允许范围与副作用审查

| 入口 / 资产 | 实际副作用与依赖 | 本轮处理 |
| --- | --- | --- |
| `validate_uat_plan` 函数 | 读 UAT Markdown 与 fixture，返回字典；CLI 可覆盖指定报告 | 允许函数，禁用其 CLI 写报告路径 |
| `validate_uat_execution_readiness` 函数 | 读 UAT Markdown，返回资源准备度；CLI 可写报告 | 允许函数，保留真实资源 BLOCKED |
| `validate_grey_release_plan` 函数 | 读灰度 Markdown，校验结构；CLI 可写报告 | 允许函数，不执行灰度 |
| `validate_release_gate` 函数 | 读门槛 Markdown，并检查所引用路径是否存在 | 允许函数；这不校验历史外部证据真伪/新鲜度，不允许据此正式放行 |
| `run_replay` 函数 | 只处理已载入的合成 fixture，返回字典；CLI 默认写固定结果文件 | 允许函数；fixture 保留 false 安全标记，E1 合成回放不等于 E2 应用验收 |
| `generate_uat_simulation.py` CLI | 写入指定或默认 fixture，可能覆盖既有内容 | 不纳入入口；使用现有 fixture，不重新生成 |
| `run_ticket_acceptance.py` | 启动受控服务/调用工具，并在结束路径 `shutil.rmtree` 审计缓存 | 不直接运行；完整参考集成由 C18 前复审 |
| `scripts/backup.sh` / `scripts/recovery.py` / `recovery_archive.py` | C22 wrapper 转发显式计划；实际执行会 stop/start、创建保留容器/卷、读写完整归档，helper 以受限 root 保留 UID/GID | 本轮仅注入 Docker 与合成文件测试；不调用真实控制器、Docker 或当前数据；完整副作用/物理恢复 D01–D16 BLOCKED |
| 历史 k6 | 网络负载；C23 wrapper 已改为默认只读计划，不再默认启动 Docker/k6 | 不纳入本离线入口；当前副作用见下方 `run_capacity.py` 行 |
| `app/observability/audit.py` / `retained.py` | C21 改为共享 SQLite PERSIST/FULL、PG 去重与保留式确认；真实路径仍会建目录/写 DB 和日志 | 仅内存注入测试已执行；真实文件系统/并发/崩溃副作用须 O01–O16 复验，不授权导入或启动应用 |
| `eval/run_c22_retained_recovery.py` | 实际控制/归档代码，Docker 注入；只在新建 `eval/results/c22-tests-<uuid>/` 保留合成文件，chown 注入；hook 拒绝网络、子进程、删除/改名/链接以及夹具外写入/权限变更 | C22 允许根目录 `python3.13 -I -B enterprise-agent/eval/run_c22_retained_recovery.py`；不安装、不清理夹具、不运行 Docker/真实 DB/备份恢复；不扩展五函数白名单 |
| `eval/run_c21_runtime_observability.py` | 实际审计/SQLite 内存/就绪/ASGI/监控接收函数；PG/HTTP/框架注入；hook 拒绝文件 DB、网络、文件写入/删除与子进程 | C21 允许根目录 `python3.13 -I -B enterprise-agent/eval/run_c21_runtime_observability.py`；不启动应用/listener/磁盘 store，不扩展五函数白名单；物理保留与真实告警 BLOCKED |
| `app.observability.monitor` / `receiver` / `legacy_audit` | 真实运行会建目录/写保留 DB、访问内部 HTTP/监听端口，历史导入会读取可能敏感的审核副本 | 本轮均未执行；须单独隔离授权和历史凭证审核；不执行已有原始 JSON，不自动删除/清理 |
| `eval/run_c12_tool_operation_safety.py` | 实际动作存储/网关/HTTP/回执/审批建单/Saga 函数；SQL、HTTP、身份全注入，audit hook 禁止网络/文件写入/删除/子进程 | C12 专项审查允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c12_tool_operation_safety.py`；不加入五函数白名单，不证明真实 PG/HTTP/完整恢复 |
| `eval/run_c14_queue_reliability.py` | 实际队列/producer/worker/路由函数；SQL、模型、Milvus、身份替身；audit hook 拒绝网络、文件写入/删除及子进程 | C14 专项允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c14_queue_reliability.py`；不加入五函数白名单，不证明真实锁/故障/进程/框架 |
| `eval/run_c19_controlled_sso.py` | 实际 IdP/claims/state/mapping 代码，内存 SQLite、JWT/HTTP/PG 替身；audit hook 禁止文件 DB、网络、文件写入/删除、子进程 | C19 专项允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c19_controlled_sso.py`；不加载真实密码学后端或启动服务，不扩展五函数白名单 |
| `reference_idp.server` / `.acceptance` | server 真实 TLS/签名/持久 DB；acceptance 默认只输出 BLOCKED 计划，可只读校验 64 KiB 脱敏观察 JSON，但不认证结果 | server 本轮不执行；运行须单独授权并复审 C21/文件保留；acceptance 无网络、无写入，真实 S01–S16 BLOCKED |
| `eval/run_c18_reference_integration.py` | 独立服务真实代码与内存 SQLite；应用/HTTP/PG/身份注入；audit hook 拒绝文件数据库、网络、文件修改/删除及子进程 | C18 专项允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c18_reference_integration.py`；不扩展五函数白名单，不启动 listener/Docker/运行采集器；R01–R20 BLOCKED |
| `reference_service.server` / `reference_service.acceptance --execute` | 独立端口、持久 DB、故障控制；实际应用登录/对话/审批/恢复会写业务记录并可能调用付费 LLM；采集器仅新建证据文件，不覆盖/清理 | 本轮只审阅配方/代码；不执行。隔离运行须按 reference-integration.md 处理前置与 C21 保留式审计路径；O01–O16 尚未验收 |
| `eval/run_c17_rag_quality.py` | 实际指标、降级、Agent/评测编排；SQL/模型注入；audit hook 拒绝网络、文件修改/删除及子进程 | C17 专项允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c17_rag_quality.py`；不扩展五函数白名单，不执行 `run_eval --execute`；真实质量 BLOCKED |
| `eval/run_c16_analysis_data.py` | 实际分析/参考查询/身份/图函数；SQL/HTTP 注入；audit hook 拒绝网络、写入/删除、子进程 | C16 专项允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c16_analysis_data.py`；不加入五函数白名单，不替代真实参考服务/PG/JWT/API/SSE 验收 |
| `eval/run_c15_knowledge_publication.py` | 实际发布/入库/可见性/检索/路由函数；SQL/向量/模型替身；audit hook 拒绝网络、写入/删除、子进程 | C15 专项允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c15_knowledge_publication.py`；不加入五函数白名单，不替代真实 PG/Milvus 或完整 RAG 质量验收 |
| `eval/run_c11_approval_execution.py` | 实际审批 API/状态/扫描/通知与回执校验；SQL/JWT/工具替身，audit hook 禁止网络、写入/删除及子进程 | C11 专项允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c11_approval_execution.py`；不加入五函数白名单，不证明真实锁/框架/浏览器 |
| `eval/run_c13_saga_recovery.py` | 实际 Saga 日志/协调/恢复/回执代码；SQL/HTTP/身份替身；audit hook 禁止网络、文件写入/删除及子进程 | C13 专项允许：根目录 `python3.13 -I -B enterprise-agent/eval/run_c13_saga_recovery.py`；不加入五函数白名单，不证明真实 PG/HTTP/进程故障 |
| `eval/run_c10_checkpoint_durability.py` | 实际 checkpoint 生命周期、历史/API 函数；saver/框架/SQL 全部注入替身，audit hook 禁止文件写入/删除/网络/子进程 | C10 专项审查允许：Python 3.11+ `-I -B` 从根目录运行；不连接存储、不执行 schema setup、不证明真实持久化 |
| `eval/run_c09_cross_process_state.py` | 实际协调/Prompt/图入口/SSO 函数与独立模块实例；Redis/Lua/SQL 为共享内存替身，审计钩子禁止写入/删除/网络 | C09 单独审查允许：根目录 `python3 -I -B enterprise-agent/eval/run_c09_cross_process_state.py`；不加入五函数白名单，不证明真实进程隔离、TTL、Lua、HTTP/SSE/SSO |
| `eval/run_c08_request_context.py` | 实际图节点、历史与执行上下文代码；框架/模型/存储为替身，审计钩子禁止写入/删除/网络；并发仅在内存事件循环 | C08 单独审查允许：根目录 `python3 -I -B enterprise-agent/eval/run_c08_request_context.py`；不加入五函数白名单，不代表真实 LangGraph/JWT/SQL/API/SSE 验收 |
| `eval/run_c07_retrieval_authorization.py` | 执行实际检索/重排代码，模型与存储为替身；数值计算替身仅提供分数；审计钩子禁止真实写入/删除/网络；文档删除调用仅落到 Mock | C07 单独审查允许：根目录 `python3 -I -B enterprise-agent/eval/run_c07_retrieval_authorization.py`；不加入五函数白名单，不代表真实 Milvus/SQL/API 验收 |
| `eval/run_c06_credential_safety.py` | 执行实际源代码/函数；DB/HTTP/审计文件均注入内存替身，审计钩子禁止真实写入、删除及网络 | C06 单独审查允许：根目录 `python3 -I -B enterprise-agent/eval/run_c06_credential_safety.py`；不代表真实 JWT/PG/HTTP/历史清理 |
| `tests/test_browser_credential_safety.cjs` | 只读页面源码，在 Node VM 内以假浏览器对象执行；不联网、不写文件、不启动浏览器 | C06 单独审查允许：根目录 `node enterprise-agent/tests/test_browser_credential_safety.cjs`；不代表真实 DOM/净化器/SSO/SSE 验收 |
| `tests/test_browser_delivery.cjs` | 只读实际页面与固定分发文件；VM/HTTP/计时器替身、实际 Marked VM 解析；不启动应用/浏览器、不联网、写入或删除 | C20 单独审查允许：根目录 `node enterprise-agent/tests/test_browser_delivery.cjs`；Vue/DOMPurify 仅语法与引用检查，不证明真实 DOM/授权/SSO/SSE；不扩展五函数白名单 |
| `scripts/verify_frontend_assets.py` | 标准库只读 HTML/manifest/JS/licenses，校验路径、SHA-256/SRI 与本地引用；无应用导入、网络、写入/删除 | C20 允许根目录 `python3.13 -I -B enterprise-agent/scripts/verify_frontend_assets.py enterprise-agent/app/static`；镜像构建有同入口配方但本轮未构建；不等于漏洞扫描或浏览器加载证据 |
| `eval/run_c05_runtime_authorization.py` | 标准库执行 C05 实际源代码/启动函数；注入 JWT/框架/DB/工具，无真实连接、文件写入或清理 | C05 单独审查允许：仓库根目录 `python3 -I -B enterprise-agent/eval/run_c05_runtime_authorization.py`；不加入五函数白名单，不代表真实密码学/HTTP/PG 验收 |
| `eval/run_c04_session_ownership.py` | 标准库加载 C04 unittest；依赖注入，内存数据库/图/审计，无真实网络、文件写入或清理 | C04 单独审查允许：仓库根目录执行 `python3 -I -B enterprise-agent/eval/run_c04_session_ownership.py`；不加入原五函数白名单，不代表真实 HTTP/PG 验收 |
| `eval/run_c23_capacity_evidence.py` | 标准库加载 C23 实际计划/报告/SSE/采集器代码；注入时钟/HTTP，独立参考服务仅内存 SQLite；audit hook 禁止 socket、子进程、磁盘 DB、文件修改/删除 | C23 仅授权 `python3.13 -I -B enterprise-agent/eval/run_c23_capacity_evidence.py`；不加入五函数白名单，不执行真实负载 |
| `eval/run_capacity.py` / `eval/run_load_test.sh` | 无 execute 时只读计划；summarize 只读保留报告；显式执行会创建新输出目录、调用 HTTPS/参考 API/付费模型并持久写会话/审批/审计/邮件 sink | 本轮不执行 runtime；需先按 C23 冻结计划和隔离边界重新审查并明确授权。旧 k6 仅历史入口，不受安全白名单覆盖 |
| `scripts/final_candidate.py` | 固定 30 项子进程、只读 Git/源码；检查源哈希/候选身份，捕获并丢弃原始输出；可独占新建 ignored 回执 | C24 单独审查允许；不是五函数白名单扩展，不是 OS 沙箱；细节见 [C24 契约](final-candidate-verification.md) |
| C01–C03 独立测试、`test_dockerfile_prod.py` | 已复审只读源文件与 AST/依赖注入；Dockerfile 三函数只做文本断言；不导入生产设置或安装 PyYAML | C24 固定汇总允许 `-I -B`；缺失 PyYAML 的检查仍 skip/BLOCKED |
| `tests/test_final_candidate.py` | 子进程全注入；在新建 `eval/results/c24-tests-<uuid>/` 写入保留合成夹具，hook 拒绝网络/真实子进程/删除及夹具外写入 | C24 允许独立执行；不清理，不覆盖既有证据 |
| 其他 eval / scripts | 可能启动应用、模型、写 DB/向量库、网络或覆盖报告 | 默认不允许，逐项审查，不能仅凭脚本名认定安全 |
| 全量 pytest | 项目 conftest 本身为内存 mock，但插件、cache、tmp_path 生命周期不在五函数审查范围内 | 本轮不运行；入口测试用独立 unittest，夹具追加保留 |

五份函数模块的 SHA-256 固化在入口 `REVIEWED`。源码修改必须复审导入、文件/网络/进程副作用，再更新哈希与对应测试；不能提供“自动信任当前源码”的开关。验证输入固定为两份计划与 fixture，报告记录输入和源码哈希；执行前后哈希变化会阻断结果。

## 3. 保护机制与限制

- 验证阶段启用 audit hook：禁止文件写入、删除、改名、建目录、权限修改、链接、环境变量修改、socket、子进程与动态库加载；执行前只运行固定的只读 Git 元数据命令，记录提交和 tracked 内容是否修改。
- 函数只从已校验的源码字节编译加载，不用 `.pyc` 或其 `__main__`；来源/输入与证据路径含符号链接时拒绝。生产端点、数据库、模型、应用配置均不在允许范围。
- 输出只取固定检查 ID、枚举状态、布尔值、序号计数与哈希；丢弃原始详情、函数 stdout/stderr 与异常消息，不转储环境变量或绝对路径。失败检查的序号对应已记录哈希的原始函数检查列表，可离线定位。
- 这是已审查函数的保护入口，**不是恶意 Python 代码的隔离沙箱**；audit hook 不保证拦截所有底层 OS 行为。宿主、标准库、入口自身和文件系统并发编辑者属于信任边界，不能用它运行任意脚本或声明完整权限沙箱。
- `tracked_content_dirty` 不涵盖 untracked 文件；源码/输入 SHA-256 记录实际执行内容。解释结果时必须同时核对提交与哈希，不把脏工作区证据说成最终提交验证。
- 结果哈希证明本次读取的字节，不证明内容业务真实或当前 CI 状态；本入口始终 `formal_uat=false`、`release_evidence=false`、`release_allowed=false`。

## 4. 扩展与证据模板

新增检查前，先记录所需环境、输入、输出、副作用、回收行为及失败路径；审核通过后再加入显式允许列表。应用/HTTP/容器检查不能直接加入本离线函数入口；应在对应 C 项设计其隔离执行方案。当前受控结果不构成 C24 最终回归完成。

每轮以[验收证据模板](../40-process/模板-工程验收证据.md)记录范围、命令/步骤、预期/实际、证据等级、状态及复验条件；摘要写入对应阶段总结，原始受控 JSON 保留在 ignored 目录。入库前人工复核脱敏，不提交原始日志、凭证或真实用户数据。
