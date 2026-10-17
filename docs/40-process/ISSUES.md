# ISSUES · 问题、坑与 backlog

> 问题与坑记录的单一事实源。格式：状态（open/fixed）/ 优先级 / 现象 / 根因 / 修复 / 验证 / 日期。
> 已从运维维护手册第 8 节与临时备忘迁移；新问题追加在「待办与开放问题」，已修复的记入「已修复」。

## 一、待办与开放问题

<a id="engineering-closeout"></a>
### 工程交付收尾差距 C01–C25（2026-10-17）

本节是当前工程收尾问题与逐项验收的唯一事实源。调查基线为 `153f78651217eec7544b064446344d27b36085f1`，以下均为 **open，未修复、未按新标准验收**；现状来自 E0 静态调查，不能视为本轮运行时复现。P0/P1 均属于本次工程交付必须处理的范围。

每项日期均为 2026-10-17，计划修复按对应缺口执行，修复与验证记录待逐项实施后补充。源码链接相对本文件；工程验收遵守[交付基线](../50-engineering/engineering-delivery-baseline.md)的证据等级与记录模板，执行依赖以 [ROADMAP](ROADMAP.md#engineering-closeout-stages) 为准。历史 fixed 条目保留当时证据，不自动覆盖本轮新发现。

<a id="c01"></a>
#### C01 · P1 · 部署产物与入口一致

- **现状/证据**：[生产 Compose](../../enterprise-agent/docker-compose.prod.yml) 使用 `Dockerfile` 并挂载源码；CI 构建 `Dockerfile.prod`；[Nginx](../../enterprise-agent/deploy/nginx.conf) 根路径返回文本，未接通 `/ui` 等交付入口。
- **缺口/原因**：构建、验收、运行产物不一致；不能按生产入口复现完整产品。
- **验收**：从文档在隔离 Linux 主机启动同摘要 API/worker 镜像，无源码挂载；从声明的入口完成 UI、登录、SSE、API 文档与健康/就绪访问；内部指标端点采用明确访问边界；记录镜像摘要、入口与启动检查，不以容器 running 代替功能通过。

<a id="c02"></a>
#### C02 · P1 · 模型与依赖 profile 匹配

- **现状/证据**：[Dockerfile.prod](../../enterprise-agent/Dockerfile.prod) 默认不安装 ML，而[配置](../../enterprise-agent/app/config.py)默认使用本地 embedding/reranker；可选 ML 分支的 `--mount` 位于 shell 条件内部，尚无该分支构建通过证据。
- **缺口/原因**：默认配置与镜像能力不匹配；开发/生产依赖集合也需按 checkpoint 等实际路径核对。
- **验收**：选择并记录一套完整模型 profile，包含精确模型标识、依赖、资源与网络条件；候选镜像真实构建、加载 embedding/reranker、完成 LLM 问答；缺失模型/配置时启动或就绪明确失败；文档中的可选配置若未测必须标明不支持或未验收。新增依赖须先确认。

<a id="c03"></a>
#### C03 · P0 · 数据库迁移与初始化

- **现状/证据**：[init.sql](../../enterprise-agent/deploy/init.sql) 混合 schema 与演示账户/业务数据；[database.py](../../enterprise-agent/app/core/database.py) 初始化主要检查连接；已有[迁移目录](../../enterprise-agent/deploy/migrations)但缺少统一版本执行约束。
- **缺口/原因**：空库、已有库升级、重复启动和生产 bootstrap 缺少统一可复现路径。
- **验收**：隔离空库初始化及已有版本副本升级均通过，迁移有版本记录并可重复安全执行；迁移失败不进入 ready；默认交付不自动生成演示账户/默认口令，演示种子显式启用；记录管理员 bootstrap 与回退方法，已有业务数据保留。不对当前库执行迁移。

<a id="c04"></a>
#### C04 · P0 · 会话归属校验

- **现状/证据**：[chat.py](../../enterprise-agent/app/api/chat.py) 普通/流式请求接受 session_id，历史和反馈缺少一致归属校验；取消路径已有 owner/admin 检查。
- **缺口/原因**：会话读写入口未统一按身份授权，存在跨用户读取或修改的静态风险。
- **验收**：A/B 两用户针对普通对话、SSE、历史、反馈、取消交叉访问；未授权请求全部拒绝且不改变 session/checkpoint/反馈数据；合法本人流程通过；管理员例外逐接口定义并测试；不存在与无权访问的响应不泄漏敏感信息。

<a id="c05"></a>
#### C05 · P0 · 认证失败闭合与运行时授权

- **现状/证据**：[rbac.py](../../enterprise-agent/app/security/rbac.py) DB 查询异常时回退 JWT 身份；[config.py](../../enterprise-agent/app/config.py) 生产检查未强制全部认证开关；[approval.py](../../enterprise-agent/app/api/approval.py) 执行阶段的账户有效性检查不足。
- **缺口/原因**：身份存储故障、禁用/降权或等待审批期间权限变化可能继续获得授权。
- **验收**：数据库不可用、账户删除/禁用/降权、token 过期/伪造、危险生产配置分别覆盖；需要最新身份的操作拒绝且不触发业务副作用；审批执行时重新核验发起人及批准人权限；恢复后合法请求通过；不以旧 JWT 身份兜底绕过校验。

<a id="c06"></a>
#### C06 · P0 · 凭证生命周期、脱敏与 HTML 失败安全

- **现状/证据**：[execution.py](../../enterprise-agent/app/agents/execution.py) 将 JWT 写入审批记录，图状态也携带 JWT；[审计](../../enterprise-agent/app/observability/audit.py)与[HTTP 适配](../../enterprise-agent/app/tools/http_adapter.py)存在原文记录路径；[UI](../../enterprise-agent/app/static/index.html)正常路径有 DOMPurify，但渲染异常回退原始内容并交给 v-html。
- **缺口/原因**：持久化凭证与不统一的输出脱敏扩大暴露面；渲染失败路径不安全。
- **验收**：定义可审计的执行授权机制，审批/checkpoint 不持久化可复用明文 JWT；用标记凭证验证 DB、日志、错误响应和审计无泄漏；渲染器/净化器缺失或抛错时只显示安全文本；注入样例不执行脚本；明确浏览器 token 存储与退出/过期行为。

<a id="c07"></a>
#### C07 · P0 · 检索权限与表达式编码

- **现状/证据**：[vector_store.py](../../enterprise-agent/app/rag/vector_store.py) 多处直接拼接角色/部门/类型/文档 ID 表达式；[degradation.py](../../enterprise-agent/app/rag/degradation.py) 部分路径已有转义；ROLE_NAMESPACES 未统一进入主检索。
- **缺口/原因**：各检索/降级路径隔离语义不一致，输入编码不足。
- **验收**：固定角色 × 部门 × 共享区矩阵，向量、关键词和 PG 降级全部遵守；引号、转义、运算符等输入不能扩大权限；结果正文、引用与来源元数据均无越权；manager 跨部门策略明确，声明不支持时必须拒绝，不能仅依赖未接入的常量。

<a id="c08"></a>
#### C08 · P0 · 请求上下文、历史与子任务依赖

- **现状/证据**：[executor.py](../../enterprise-agent/app/graph/executor.py) 缓存 ExecutionAgent 的键不包含会话/token，而实例保存两者；[dispatcher.py](../../enterprise-agent/app/graph/dispatcher.py) Send 子状态不含历史，且未消费 depends_on。
- **缺口/原因**：请求级状态被实例缓存；历史与依赖字段未贯通调度语义。
- **验收**：同用户不同会话、刷新 token 及并发请求不串上下文；多轮知识问答收到正确历史；需要前置结果的任务按依赖执行，或在未支持时明确拒绝；不能静默并行执行有依赖的副作用。完整通用 DAG 可延期。

<a id="c09"></a>
#### C09 · P1 · 跨进程运行状态

- **现状/证据**：[cancellation.py](../../enterprise-agent/app/core/cancellation.py)、[auth.py](../../enterprise-agent/app/api/auth.py) 的 SSO state、[registry.py](../../enterprise-agent/app/prompts/registry.py) 缓存均为进程内；生产 Compose 配置多个 API worker。
- **缺口/原因**：负载分配后取消、SSO 回调与 Prompt 激活可能由另一进程处理。
- **验收**：至少两个 API 进程下，跨进程取消、SSO state 单次消费与 Prompt 新版本可见性通过；重启/过期行为明确。若选择只支持单 API 进程，先确认收窄范围，并同步部署、入口和文档，不能保留多进程支持声明。

<a id="c10"></a>
#### C10 · P1 · checkpoint 持久化与故障语义

- **现状/证据**：[checkpointer.py](../../enterprise-agent/app/graph/checkpointer.py) 缓存初始化时选定的后端；存在 Redis/PG/Memory 路径，Memory 不持久，运行时故障切换与同会话并发一致性尚缺完整证据。
- **缺口/原因**：初始化回退不能证明运行中无损切换，状态留存和并发边界未验收。
- **验收**：真实后端跨进程/重启恢复、TTL、同会话并发写入和后端断连分别验证；记录是否允许切换及如何处理旧状态；持久化不可用必须显式报错/降级且不声称已恢复；支持的 PG 路径按实际安装版本测试。

<a id="c11"></a>
#### C11 · P0 · 审批原子领取、过期与执行状态

- **现状/证据**：[approval.py](../../enterprise-agent/app/api/approval.py) 先读 pending 再执行/更新，缺少原子领取与一致过期判定；失败可能仍记 executed；空工具分支返回二元组而调用方解包三元组。
- **缺口/原因**：重复审批/超时任务竞争可能重复执行，批准和执行成功语义混用。
- **验收**：并发批准、重复请求、拒绝与超时竞争只产生合法的一次状态转换及至多一次业务动作；已过期不能执行；空工具、部分失败、重试/补偿失败均有明确状态；UI/API/审计一致，失败不得显示成功。复用 C12–C14 的恢复证据。

<a id="c12"></a>
#### C12 · P0 · 工具幂等与安全重试

- **现状/证据**：[execution.py](../../enterprise-agent/app/agents/execution.py) request_id 具有秒级碰撞风险；[crm.py](../../enterprise-agent/app/tools/crm.py) 动作索引可能默认 0；[Saga](../../enterprise-agent/app/tools/saga.py)复用 context；[HTTP 适配](../../enterprise-agent/app/tools/http_adapter.py)对写请求也重试；[mail.py](../../enterprise-agent/app/tools/mail.py)缺少充分的回执与幂等保证。
- **缺口/原因**：同一动作重放与不同动作隔离缺少持久身份；网络失败无法区分未执行和已执行未收到响应。
- **验收**：每个逻辑动作有持久唯一 ID；同动作重试复用键，不同动作不共享键；响应丢失/5xx/重启重放至多产生一次外部动作；缺少幂等或查询契约时禁止盲目重试非幂等写入；缺回执不能显示成功；工具网关校验所需角色和审批执行授权。

<a id="c13"></a>
#### C13 · P1 · Saga 持久化与故障恢复

- **现状/证据**：[saga.py](../../enterprise-agent/app/tools/saga.py)主要在内存顺序执行和逆向补偿；[saga_retry.py](../../enterprise-agent/app/core/saga_retry.py)读取 saga_transactions，但应用未发现对应生产写入；重试补偿顺序也需统一。
- **缺口/原因**：恢复消费者与实际执行记录未接通，进程崩溃后无法依靠内存恢复。
- **验收**：真实执行写入事务/步骤/操作 ID/结果与补偿状态；每个关键崩溃点重启后可恢复；按依赖逆序补偿且重试不重复副作用；无法撤回或补偿失败保持人工处理状态，不能报告回滚成功；审计可关联原始执行。

<a id="c14"></a>
#### C14 · P1 · 队列可靠性与 worker 初始化

- **现状/证据**：[task_queue.py](../../enterprise-agent/app/core/task_queue.py) BRPOP 后处理，缺少 ack/in-flight 恢复和死信；应用生产路径未连接 enqueue_task；[worker.py](../../enterprise-agent/app/worker.py)未完整初始化工具注册与 Milvus。
- **缺口/原因**：取出后崩溃可能丢任务，Redis 断连可能终止消费者，空 worker 无法执行其承诺任务。
- **验收**：实际业务生产任务并由独立 worker 消费；取出前后/执行中崩溃、Redis 断连重连、超限失败均可追踪恢复或进入可查询失败队列；结合幂等避免重复副作用；干净启动能执行文档入库与 Saga 恢复，消费者失活可被探测。

<a id="c15"></a>
#### C15 · P1 · 知识发布与索引一致性

- **现状/证据**：[ingest.py](../../enterprise-agent/app/rag/ingest.py)先向量再 PG 记录；[admin.py](../../enterprise-agent/app/api/admin.py)审批/拒绝缺少一致前置状态约束；向量 insert 与内容 hash 未形成完整幂等发布。
- **缺口/原因**：重复审批、拒绝已发布文档、部分入库失败可能留下重复或越权可见内容。
- **验收**：重复/并发发布只产生一个有效版本；更新后旧版本不被检索；拒绝/停用文档不可见；PG 或向量写入任一失败可追踪、重试且不暴露半成品；权限过滤及 ledger/vector 一致性验证通过。采用版本/状态控制，不在验收中自动删除文件或数据卷。

<a id="c16"></a>
#### C16 · P1 · 分析数据适配一致

- **现状/证据**：[analysis.py](../../enterprise-agent/app/agents/analysis.py)调用 get_all_orders/customers；[crm.py](../../enterprise-agent/app/tools/crm.py)这些函数仍返回内置样例，切 HTTP provider 不切换分析来源。
- **缺口/原因**：工具查询与分析报表的数据提供方不一致。
- **验收**：替换参考 CRM 数据后，查询与 Python 聚合数字一致变化；空数据、分页、字段异常、权限和服务故障有明确结果；LLM 不能替造数值；输出注明数据来源和时间范围，Mock 模式显式标识。

<a id="c17"></a>
#### C17 · P1 · RAG 质量与指标口径

- **现状/证据**：[run_eval.py](../../enterprise-agent/eval/run_eval.py)保留 122 条评测，生成失败单独计数但不进入覆盖率分母；[degradation.py](../../enterprise-agent/app/rag/degradation.py)部分名为 BM25 的路径实际为关键词匹配。
- **缺口/原因**：质量指标容易被误读为全样本事实正确率，检索命名与行为不完全一致。
- **验收**：保留全部样本和来源，明确分母、失败/跳过与逐样本归因；关键词覆盖 ≥0.85，同时核对引用正确性、无答案拒答和跨部门负例；不能靠排除失败样本或改宽预期制造通过；按实际算法命名；在 C02 已验收 profile 上复测。

<a id="c18"></a>
#### C18 · P1 · 完整参考 HTTP 业务集成

- **现状/证据**：[CRM/邮件契约测试](../../enterprise-agent/tests/test_crm_mail_external.py)主要用 MockTransport；已有[工单 stub](../../enterprise-agent/eval/ticket_stub_server.py)与工具层 harness；缺完整应用与独立参考服务链路证据。
- **缺口/原因**：工具层契约不能证明登录、规划、审批、外部写入、审计和恢复接通。
- **验收**：先冻结工程基线 §3 契约；通过应用入口在独立参考 HTTP 服务完成查询、创建、更新、审批邮件及失败/补偿；核对服务端持久记录、幂等键和审计；真实网络超时/鉴权失败被正确处理；邮件只到受控收件器，撤回未支持时明确失败。不得勾选真实企业提供方确认任务。

<a id="c19"></a>
#### C19 · P1 · 受控 IdP 的 SSO 完整链路

- **现状/证据**：[auth.py](../../enterprise-agent/app/api/auth.py)已有 OIDC callback/验签/账户映射和[单测](../../enterprise-agent/tests/test_sso_auth.py)，尚缺浏览器与独立 IdP 的完整验收。
- **缺口/原因**：重定向、claims、密钥变化和跨进程状态未形成一体化证据。
- **验收**：受控 IdP 真实签发 token，浏览器完成登录/回调/本地身份映射；错误签名、issuer/audience/nonce/state、过期、重放、轮换和禁用账户分别验证；首次登录最小权限且无映射串号；IdP 故障不削弱本地登录安全；记录为参考环境，非企业 SSO 验收。

<a id="c20"></a>
#### C20 · P1 · UI 角色流程与前端交付

- **现状/证据**：[index.html](../../enterprise-agent/app/static/index.html)使用 CDN 库和 localStorage token；功能已有但当前镜像/入口的完整人工验收缺失。
- **缺口/原因**：依赖版本和可达性、各角色实际操作、错误恢复尚未在目标环境确认。
- **验收**：固定/可托管前端依赖；从交付入口按角色执行登录/退出、流式对话/取消/历史、审批批准/拒绝/失败、适用知识/用户/Prompt 操作；越权按钮及 API 均受保护；断网/过期/重复点击不显示假成功；记录浏览器版本、步骤与实际证据。无 UI 的管理功能可明确文档化 API，不默认新增页面。

<a id="c21"></a>
#### C21 · P1 · 就绪、审计、指标与告警

- **现状/证据**：[main.py](../../enterprise-agent/app/main.py) ready 未按依赖失败返回 503；[metrics.py](../../enterprise-agent/app/observability/metrics.py)存在原始路径标签与进程内统计；[audit.py](../../enterprise-agent/app/observability/audit.py)本地缓存消费有文件删除，API/worker 缓存未形成共享持久恢复；告警接收闭环缺证据。
- **缺口/原因**：进程存活与能服务混淆，审计积压/消费者故障可能不可见，多进程指标可能不完整。
- **验收**：必需依赖失败 ready=503、恢复后 200；worker 故障可见；指标使用稳定路由标签并覆盖支持进程数，SSE 完整耗时口径明确；请求/审批/工具/worker trace 与审计可关联；DB 故障后审计可恢复且不重复/丢失；在不删除文件的路径下运行；受控告警接收器实际收到故障及恢复通知。

<a id="c22"></a>
#### C22 · P1 · 当前版本备份恢复与回退

- **现状/证据**：[backup.sh](../../enterprise-agent/scripts/backup.sh)存在自动删除和暂停后异常未必恢复的路径；已有 2026-08-06 演练记录，但不等于当前候选验收。
- **缺口/原因**：安全执行、失败恢复和当前版本数据一致性需重新验证。
- **验收**：先审查并提供不删除的备份/恢复入口；隔离副本恢复 PG、Milvus 元数据/对象及必要状态，核对记录数、内容和真实检索；失败不会让原服务永久暂停；实测 RTO ≤1h、RPO ≤24h 并明确备份周期；验证应用/迁移回退边界，资产保留交用户处理，不触碰当前业务库。

<a id="c23"></a>
#### C23 · P1 · 规定负载下的性能与容量

- **现状/证据**：[load_test_k6.js](../../enterprise-agent/eval/load_test_k6.js)业务请求主要为问答，断言偏响应结构；历史流量含大量 health，不覆盖完整业务工作负载。
- **缺口/原因**：未形成目标镜像/模型下可重复的业务容量与长链路稳定性证据。
- **验收**：执行前冻结硬件、模型、数据量、角色、并发、业务比例和阈值；至少 30 分钟混合链路运行且校验业务结果；按接口记录 p95/p99/错误率，分开 TTFT、完整响应和队列延迟；记录资源与积压恢复；遵守工程基线 §5，未达标如实 FAIL，不以 health 总吞吐代表业务容量。

<a id="c24"></a>
#### C24 · P1 · 安全验证入口与最终证据分层

- **现状/证据**：既有单测、[eval](../../enterprise-agent/eval)与 CI；[run_ticket_acceptance.py](../../enterprise-agent/eval/run_ticket_acceptance.py)包含 rmtree，备份/临时目录清理也需审查；历史 CI 不覆盖新收尾项完整验收。
- **缺口/原因**：缺少当前最终候选的单元/契约、完整参考环境、人工交互三层证据，部分脚本不能直接按当前安全规则运行。
- **验收**：S1 先建立可安全执行、不删除的验证入口与脱敏记录模板；逐项补针对真实缺陷的回归；S7 对最终候选运行 E1/E2 并完成适用 E3，逐条关联验收标准、提交/镜像与证据；未跑部分明确 BLOCKED；不能只追覆盖率或以 Mock 代替完整链路。前置完成不等于 C24 完成。

<a id="c25"></a>
#### C25 · P1 · Git、文档、OpenSpec 与交付结论

- **现状/证据**：本地为 `codex/delivery-ci-gates` / `153f786`；存在 556 项历史权限差异；部分导航/上下文仍用旧阶段计数，历史归档与当前验收边界需区分。
- **缺口/原因**：提交、PR、文档声明、规格与最终可执行产物尚未形成一个收尾候选。
- **验收**：S0 登记本清单及边界；S7 复核最终 Git/PR 与 CI，完成 C01–C24 证据映射、支持面/版本/迁移/操作文档一致性和 OpenSpec 严格校验；所有本轮变更审阅提交且不夹带历史权限差异；发布版本与归档按实际完成状态处理，推送/合并/发布分别获得授权；工程完成与企业未验证同时写明。S0 文档完成不关闭 C25。

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

### I-13 PR #3 生产镜像依赖漏洞阻断（2026-10-17）

- 状态：fixed（492882c 云端 CI 验证通过；待 PR 集成）· 优先级 P1
- 现象：[CI 39011635217](https://github.com/zhenkun26/BusinessAgent/actions/runs/39011635217) 的 Python 3.11/3.13 检查通过，Trivy 报告 16 个 HIGH、1 个 CRITICAL，生产镜像检查失败。
- 根因：生产依赖清单锁定的 PyJWT、langgraph-sdk、pypdf、urllib3 版本命中已公布漏洞；README 变更未修改这些依赖。
- 修复：生产 pin 分别升级到 2.15.0、0.4.4、6.19.0、2.8.0；开发 requirements 与 pyproject 同步安全下限。PyJWT 2.14.0 仍有后续公告，选择已发布的 2.15.0。
- 验证：三份清单一致性、上游约束、diff 检查通过；[CI 39012279790](https://github.com/zhenkun26/BusinessAgent/actions/runs/39012279790) 在修复提交 `492882c` 上全部通过：Python 3.11/3.13 各 143 测试通过，gitleaks/pip-audit 无发现，生产镜像构建与 Trivy 门禁通过。归档记录提交仍需最终 CI；PR 检查未发布镜像。
- 边界：扫描门槛、漏洞豁免、分支保护均未修改；必需批准审核独立于 CI。详见 [修复记录](../../openspec/changes/archive/2026-10-17-fix-vulnerable-runtime-dependencies/tasks.md)。

### 2026-08-15 生产镜像 runner 阶段 pip 清理顺序导致 CI 构建失败

- 状态：fixed（2026-08-15 CI 验证通过）· 优先级 P1
- 现象：CI 的 Python 3.11/3.13 单元测试通过，但生产镜像构建在 `Dockerfile.prod:74-75`
  返回 exit code 127。
- 根因：runner 在 `COPY --from=builder /opt/venv /opt/venv` 之前调用
  `/opt/venv/bin/pip`；该路径尚不存在，且前一个命令已经卸载了基础镜像的 pip。
- 修复：`enterprise-agent/Dockerfile.prod` 先清理系统 Python 的 pip，再复制 venv，最后用
  `/opt/venv/bin/python -m pip` 清理 venv 内 pip；新增 `tests/test_dockerfile_prod.py` 固化顺序。
- 验证：本地聚焦测试 15/15 通过、Ruff 通过、OpenSpec strict 校验通过；GitHub Actions
  run `31890705614` 的 Python 3.11/3.13 测试、生产 Docker build 与 Trivy HIGH/CRITICAL
  扫描全部通过。

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
