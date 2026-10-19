## Context

C16 design: use the effective CRM tool provider for analysis; extend business-reference-v1
with the separately versioned `crm-analysis-v1` read schema. Read bounded orders/customers
pages under one stable run-bound snapshot, rejecting incomplete/duplicate/changing data.
Refresh the caller's database identity before reads and delivery. Finance reads only orders;
customer IDs come from authorized orders, never a hidden customer-directory read. The
reference profile retains existing single-organization tool-level permissions; no claim
of department row-level isolation is added. Sum integer minor units by currency and expose
explicit order-status/time semantics. Customer lifetime revenue is unavailable, not an
order-amount substitute. Deterministic plans support known customer IDs and explicit ISO
date intervals; unsupported time semantics fail closed. Render tables directly and preserve
them through multi-agent aggregation; no LLM-generated numerical report or extra-data loop.
At C16 delivery, reference service implementation was deferred to C18. The authorized C18
candidate is specified below; complete runtime verification remains BLOCKED.

用户希望练手项目形成可执行的企业应用工程交付，当前没有企业现场资源。S0 使用本轮及前一轮代码调查，基线为 `153f786`；静态发现须在对应实施项补充可复现验证，不能直接标为运行时测试失败或已修复。

本地存在 556 项既有文件模式差异，内容基线干净。S0 沿用 `codex/delivery-ci-gates`，只提交本轮文档内容，不纳入权限变化。OpenSpec CLI 本机不可用，按仓库 spec-driven 格式手工创建，严格校验记录为 BLOCKED，不安装工具替代用户决策。

## Goals / Non-Goals

- 目标：可审核的边界、25 项差距和逐项验收契约，明确依赖、证据及暂停点。
- S0 非目标：修复代码或执行运行时验收。后续 C24 前置仅新增验证入口与其测试；启服务、调用模型、发邮件、连企业系统、升级依赖、执行迁移/备份、发布生产或归档整个 change 仍不在本轮范围。

## Decisions

1. **单一事实源**：ISSUES 管问题与逐项验收，ROADMAP 管阶段顺序，DECISIONS 管边界决策，工程基线管通用交付契约，tasks 管实施勾选。其他文档引用这些位置，避免复制出多套状态。
2. **受限支持面**：单组织、Linux 单机 Compose、真实 PostgreSQL/Redis/Milvus、独立 worker、一套明确的模型 profile。具体镜像和模型版本、资源需求在 C01/C02 选定并实测，选定前不声称 profile 可用。多租户、多主机 HA、K8s 交付不纳入首轮。
3. **参考集成**：独立受控 HTTP 服务用于 CRM/工单/邮件，真实签名与浏览器重定向的受控 IdP 用于 SSO；邮件只进入受控收件器。该证据高于进程内 Mock，但不等同企业提供方认可。决策 16 的真实企业切换前置条件保留。
4. **安全与恢复优先**：S1 先补安全的验证入口；S2 后才做受控业务写入；S4 先冻结参考契约，再完成幂等、队列与持久化恢复，最后验证审批竞态。完整依赖顺序见 ROADMAP。
5. **声明必须可验证**：多进程支持需要跨进程证据；否则收窄配置与说明，不能以单进程测试支撑多实例承诺。完整 DAG 可延期，但必须显式处理或拒绝未支持的依赖。
6. **授权分段**：S0 文件完成后暂停，C01–C25 全部仍 open。用户每次确认一个 C 项；该项需先补运行时 delta（如涉及契约变化）、实现和验证，再交付结果并等待下一项确认。C24/C25 允许按 ROADMAP 分阶段推进，但最终验收前不得整体打勾。
7. **既有 change 的关系**：本 change 负责参考环境与工程收尾；`crm-mail-sso-integration` 负责企业契约与真实提供方联调，`uat-and-ga-rollout` 负责真实 UAT/灰度/放行。共享代码将来可引用同一证据，但不能因此勾选企业资源任务。

## Risks / Trade-offs

- 单机方案不承诺 HA 或长期 SLA；性能与恢复数据只适用于记录的环境、负载和版本。
- 25 项范围较大，采用逐项确认而非一次性全部实施；发现新阻塞时回到计划，不临时扩展依赖或支持面。
- 历史文档存在较强的生产化表述；保留历史证据语境，当前判断以本基线为准，完整对外措辞复核由 C25 收口。
- 现有备份、验收脚本及运行时审计缓存清理有删除行为；不得直接用于本轮验证，后续先审查并提供不删除的执行路径。环境和残留资产由用户决定如何处理。

## Validation Plan

S0 只做文档结构、链接/锚点、C01–C25 映射、S0–S7 顺序、任务勾选与 Git 范围检查。严格 CLI 校验不可用时单独记录 BLOCKED；不得用自制结构检查冒充 `openspec validate --strict`。

S1–S7 以工程基线的证据模板逐项执行；最终验收绑定最终候选提交与镜像摘要。归档前必须满足规格同步、全部任务验收和 CLI 严格校验；本轮不修改主规格、不归档。

## C24 前置设计（2026-10-17，用户已授权任务 1.1）

- 新增标准库入口 `scripts/safe_validate.py`，仅允许五个已审查函数：UAT 计划、执行准备度、灰度计划、发布门槛和 G0 fixture 回放。不运行这些模块的 CLI，不接受任意模块、命令或应用测试选择。
- 审查范围固化为源码 SHA-256 清单；任何函数模块漂移或符号链接均在导入前阻断，新增检查先做副作用复审。直接编译已经校验的源码字节，不使用可能过时的 pyc。
- 验证函数执行期间启用 Python audit hook，拒绝文件写入/删除/改名/目录及权限变更、socket、子进程与动态库加载。关闭 bytecode 写入；只读取固定输入。该 guard 是已审查代码的纵深保护，不是运行任意不可信 Python 的安全沙箱。
- 默认只输出结构化摘要；可选 run ID 在固定 ignored 结果目录独占创建 JSON，已有文件/符号链接拒绝，重复执行不会覆盖或清理任何资产。输出只保留固定检查 ID、状态/数量、哈希与受控元数据，不持久化原始报告文本、异常内容、环境变量、用户路径或业务 payload。
- 记录检查是否成功执行与业务准备度两个维度。退出码 0=全部 PASS，1=检查 FAIL，2=前置或业务 BLOCKED；真实资源未齐必须保持 BLOCKED，不能因函数正常返回而放行。
- 回归用标准库 unittest 直接运行，不加载 pytest/plugin/缓存/临时目录管理器。测试数据写到唯一保留目录，无 tearDown 删除；验证拒绝删除事件时使用 `sys.audit` 事件探针，不执行删除系统调用。
- C24 整项仍 open；本轮只完成安全入口、脚本副作用清单、证据模板及自身回归。全量应用测试、容器/浏览器/外部参考服务纳入入口前必须另做副作用审查。

## C01 设计（2026-10-17，用户已授权任务 1.2）

- API 与 worker 只从同一个必填 `BUSINESSAGENT_IMAGE=registry/repository@sha256:...` 运行。生产 Compose 不含 build，不覆盖 `/app` 源码；CI 继续用已有 `Dockerfile.prod` 构建/扫描候选，部署不二次构建。
- 用标准库脚本读取 Compose 渲染后的 JSON，拒绝 tag、不同镜像、本地 build、源码覆盖与应用宿主端口；只输出固定检查名/布尔结果，不回显渲染后的秘密值。不自动调用 Docker、不新增依赖、不写文件。
- Nginx 保持 HTTP→HTTPS，根路径重定向 `/ui/`；显式代理 `/ui`、`/ui/`、`/api/`、`/health`、`/ready`、`/docs`、`/docs/oauth2-redirect`、`/redoc`、`/openapi.json`。未知路由 404。API 关闭响应缓冲、缓存及压缩干扰，清除无条件 WebSocket Upgrade；保留原路径、查询参数和转发头。
- `/metrics` 只允许 Compose 网络内 Prometheus 直接读取 `api:8000`，公共入口返回 404；API 不发布宿主端口。worker 禁用从 API 镜像继承的 HTTP 探针，避免检查不存在的 worker:8000；真实 worker 就绪/告警由 C14/C21 承接，不伪造健康信号。
- 统一部署命令的工作目录和 `--env-file .env.prod`，区分 Compose 插值与容器 env_file；明确镜像身份核验与操作步骤。保留现有进程数，不在 C01 改判 C09 支持范围。
- 验证分层：本机标准库契约/变异测试及现有 Ruby 标准库 YAML 解析仅作静态证据；真实 Compose 渲染、Nginx 配置检查、镜像身份、浏览器登录/SSE/健康与就绪需隔离 Linux 环境实测。Docker/Nginx 当前缺失，模型/初始化也受 C02/C03 影响；静态通过不关闭 C01。
- 现有 Dockerfile/备份/worker 审计存在清理路径，本轮不执行构建、服务启动或清理。完整运行前需对实际执行路径复审，沿用 C24 非删除约束。

## C02 design (external profile authorized 2026-10-17)

- Selected profile `bailian-deepseek-v1`: Beijing Bailian text-embedding-v4 / 1024 dimensions and qwen3-rerank, official DeepSeek Flash for default tasks and Pro for complex planning/report/aggregation. Explicit configuration works in native development and isolated Linux; legacy local development remains available only outside this profile.
- Independent embedding/reranking/LLM credentials and endpoint settings. Bailian accepts only HTTPS Beijing public or workspace endpoints; DeepSeek uses its official HTTPS endpoint. No new SDK dependency: use the existing httpx package for Bailian JSON contracts.
- Embeddings use string inputs in batches of at most 10, explicit dimensions and float encoding. Validate response cardinality, indices, order, finite nonzero vectors. Reranking uses DashScope input.query/input.documents and parameters.top_n; validate unique indices and finite scores within [0,1], preserve source metadata. Conservative UTF-8 byte caps (8192 embedding, 4000 per rerank query/document) reject oversized input without truncation. These are application limits, not tokenizer or cost estimates.
- HTTP timeout defaults to 30 seconds per transport operation, at most two retries with bounded backoff for transport errors, 408/429/5xx. No redirects, retries for authentication/validation errors, or raw provider error text. Runtime remote rerank failures propagate through retriever and degradation chain; existing unrelated business fallback/quality semantics remain C17 work.
- Configuration validation is offline. Production requires explicit MODEL_STARTUP_PROBES_ENABLED=true before any paid startup requests; false fails before database/audit/queue initialization. Development startup validates the selected profile but never probes. Opted-in startup tests query/document embedding, one rerank, Flash and Pro with synthetic text and small output caps. No service starts or API requests occur in this implementation turn.
- Both DeepSeek clients explicitly disable thinking mode: the current LangChain tool history does not preserve reasoning_content. Pro still serves complex tasks; enabling reasoning/tool-loop changes needs separate real protocol verification. Flash is used for ordinary knowledge generation and helper calls; no implicit Ollama or Pro fallback within the remote router.
- Use the dedicated collection enterprise_knowledge_bailian_v4_1024_v1; reject the historical collection even though dimensions match. Preserve all prior collections and model volumes; do not run indexing/migration. Populate a new collection from reviewed source documents only in a separately authorized acceptance session. No claim of cryptographic vector provenance is made by naming alone.
- CI/default Docker use INSTALL_ML=0, pip check, approved libpq5 and non-root checkpoint import checks. The optional ML recipe remains available for legacy development, not accepted as a production profile. No packages installed, images built, files deleted, models downloaded, or inference run here.
- One API process and one worker, provisional limits/reservations of 2 GiB each; these are resource budgets, not measured minima. Full infrastructure capacity remains C23 and multi-process semantics remain C09.
- Offline fake transport/factory/startup and deployment checks are E0/E1 evidence only. Real API calls, Linux candidate build/scan/import/runtime acceptance and OpenSpec CLI strict validation remain BLOCKED. C02 parent task stays open. At the C02 delivery gate, push and C03 were not authorized; the subsequent C03 authorization below supersedes that gate.

## C03 design (authorized 2026-10-17)

- Keep the existing init.sql path as a schema-only, checksum-pinned baseline. Preserve historical migrations 001-005 as historical artifacts; the runner never globs them, particularly the unsafe shared-password backfills. Move complete demo fixtures to demo_seed.sql, replacing the embedded shared password with a transaction-local parameter supplied by the operator.
- Package deploy/schema_manifest.json with ordered migration IDs, SHA-256 values and required column/index contracts. Use the already declared psycopg driver; no new dependency or installation. `python -m app.core.db_bootstrap plan` is offline; status is read-only; apply/admin/demo are explicit write commands with a required --execute flag. Commands never invoke application startup, models, Redis or Milvus.
- Each write operation uses one transaction and a PostgreSQL transaction advisory lock, with connection/statement/lock timeouts. Record all pending versions atomically; refuse missing/changed/unknown history. Reject symlink/path escapes and modified packaged SQL before connecting. Repeat application skips applied versions. Existing populated legacy schemas need --adopt-legacy; partial/unknown baselines fail. No down/drop/truncate/delete path is provided.
- The baseline creates missing tables, adds only known historical document/SSO columns, then checks missing passwords before enforcing NOT NULL and required indexes. Preserve valid legacy passwords and all business rows; no default-password backfill. Missing credentials or incompatible data/structure cause rollback and operator review, not silent repair.
- API/worker init_db checks the exact ledger and required columns/types/index uniqueness under a shared advisory lock before exposing the pool. Health rechecks the same contract; failure disposes an unpublished pool and returns fixed errors. No DDL runs on application startup. Full continuous readiness remains C21.
- Administrator bootstrap requires operator environment values and a 12+ character / at most 72-byte bcrypt password. It refuses any existing admin, never resets/reactivates accounts, and requires password authentication in production. Development demo bootstrap additionally requires explicit --allow-demo, mock business providers and empty application tables; a seed ledger prevents duplicate audit/memory/feedback rows. Both use parameterized values and fixed result codes.
- Remove automatic init.sql mounts from both Compose variants. Include manifest and demo artifact in the same production image; explicit migration/admin commands run from that digest before API/worker startup. Production Compose enables password authentication; no wider C05 authorization work is implied.
- Offline fake connection/transaction tests verify orchestration and failure boundaries, not PostgreSQL SQL execution. Isolated PostgreSQL acceptance remains BLOCKED without Docker/psql; do not execute current database connections or paid API calls. Preserve 556 pre-existing mode differences. Commit only the C03 offline increment and pause; C04 and further push require user confirmation.

## C04 design (authorized 2026-10-17)

- Centralize ownership lookup in `app/security/session_access.py`, using parameterized SQL against sessions. Persisted ownership is authoritative; never trust ID prefixes, caller-provided user IDs or checkpoint presence. Missing/foreign/invalid IDs return fixed 404 `SESSION_NOT_AVAILABLE`; query failures return fixed 503 `SESSION_ACCESS_UNAVAILABLE`.
- Message, stream, history and feedback are owner-only for every role. Preserve only the existing admin cross-user cancel privilege; managers get no override. The current identity dependency remains unchanged and its fail-open/freshness risks stay in C05, not silently treated as solved.
- New message/stream sessions require omitted/null ID and use `sess_` plus full UUID hex, avoiding user-ID leakage and exceeding VARCHAR(64). Explicit unknown/empty/oversized IDs are rejected. Insert with DO NOTHING/RETURNING; collision never adopts an existing row. Continuation checks ownership first and repeats the owner predicate in UPDATE/RETURNING to close the lookup/update race. Commit the authorized row before audit or graph work.
- Both message and stream run the same preparation helper before graph imports, audit, cancellation registration or StreamingResponse construction. History authorizes before importing/obtaining a checkpointer, with authorized row status as the miss fallback. Auth errors remain outside broad graph/history exception handling.
- Feedback removes its session-placeholder upsert, requires an owned row with FOR SHARE in the same transaction as feedback/draft insertion, then follows existing business logic. Cancellation authorizes with a shared row lock before touching the process-local task registry. Ownership is immutable in existing application APIs; concurrent ownership reassignment outside the application and cross-process cancellation remain unsupported and require separate operational controls/C09 work.
- Add standard-library offline adversarial tests using the actual API module with injected framework/database/graph dependencies. Exercise A/B/manager/admin denial, identical missing/foreign responses, safe database failure, legal flows, collision and race refusal, and no side effects on rejection. Provide a dedicated reviewed eval entry without filesystem cleanup or real connections. These tests are not FastAPI validation, HTTP transport, PostgreSQL locking or live authentication acceptance.
- Update development trackers before the local commit; keep C04 parent and live subtask unchecked, preserve PostgreSQL/API/Linux/OpenSpec strict blockers, and wait for confirmation before C05 or C04 push. No new dependencies, package installs, services, migration or deletions.

## C05 design: current identity and approval authorization

Use shared strict JWT decoding and active-account resolution in rbac.py. Identity
query failure returns a fixed 503; absent/disabled/invalid-role identities return
401. Only explicit development mode may opt out of request database checks;
approvals always query the database. Production API and worker require both auth
flags before initializing external resources.

Approval decisions and resumes share a guard: resolve requester and approver in
sorted ID order with FOR SHARE in the existing transaction, validate current
approver roles and every planned tool against requester ROLE_TOOLS, and bind a
verified token subject to requester_id. Repeat the guard at execution. Expired
signed or absent stored tokens may use the existing pending-reauth transition;
forged/mismatched tokens cannot. Resume requires an explicit bearer token and
rechecks the recorded approver. Authorization errors precede business writes,
tools and notifications; batch items fail individually with sanitized errors.

This is transaction-scoped authorization, not approval claiming or external-effect
atomicity. C11 owns concurrent duplicate execution, partial batches and final
execution states; C06 owns persisted credentials and general redaction. No claim
of mid-flight cancellation for already authorized work is made. Real PostgreSQL
lock semantics and real JWT/HTTP integration remain blocked.

## C06 design: transient authorization and output boundaries

Approval decisions always enter approved_pending_reauth, after C05 participant
authorization. Resume alone executes tools with a fresh requester bearer, verifying
its subject and rechecking the original approver. No token is read from or written
to approval rows; the legacy nullable column remains for schema compatibility.
Remove JWT from UserInput and ExecutionAgent context/cache, so authentication
credentials never enter new graph/checkpoint state. No server-side delegated token
or new encryption key/dependency is introduced. Existing rows/checkpoints/backups
need separately authorized inventory and revocation/retention work, not automatic
cleanup. C11 atomic claiming and duplicate execution remain out of scope.

Use a stdlib recursive redactor at audit persistence (before truncation, including
local fallback/replay), tool output and HTTP response boundaries. Sensitive field
names, bearer/JWT/credential assignments, URL userinfo and configured environment
secret values are masked. API/worker Loguru records are sanitized; exception
tracebacks/locals are suppressed. Public exception paths use fixed error codes.
Do not claim arbitrary text privacy or retroactive cleaning of historical logs.

Browser tokens stay in application memory; SSO uses a one-time tab-scoped handoff
consumed and cleared on UI load. Legacy browser auth keys are cleared, logout/401
clears state and aborts streaming, refresh requires login. Password is transient.
Markdown output is sanitized only when both libraries work; otherwise return
HTML-escaped original text. Missing/throwing libraries must never return raw HTML.
All verification remains offline; real JWT/PG/API/SSE/Linux/browser acceptance is
BLOCKED and C07 is not started.


## C07 design: shared retrieval authorization and expression literals

Use ROLE_NAMESPACES as the single role grant source. Ordinary roles see only their
current department intersected with that grant plus shared_company; absent/empty
department means shared-only, never unrestricted. Nonempty invalid or disallowed
departments and missing/unknown roles raise a fixed authorization error before
models or stores. Managers explicitly see the four configured departments plus
shared_company; admins retain wildcard namespaces. All roles, including admin,
must match document access_roles and active status. Invalid document ACL metadata
fails closed. Namespace/role context comes from C05 current identity, not user text.

Centralize a resolved scope, Milvus quoted string encoder and result predicate.
Encode every dynamic role/namespace/type/document ID; reject empty/control/oversized
values. SQL values remain bound parameters with JSON serialization for role arrays,
namespace/type arrays passed as JSONB, and literal LIKE wildcard escaping. None
means no document-type narrowing; an empty type list means no documents. There is
no unfiltered or inactive-document mode on user retrieval methods.

Apply the same scope in vector and keyword expressions and PostgreSQL fallback,
including doc_types through every fallback. Fetch ACL metadata for defensive
post-filtering before text scoring, external reranking, LLM generation and citation
construction. Preserve ACL fields through all rerankers. Invalid authorization
must not trigger a broader fallback; database errors return no documents. Document
ID delete expressions are encoded but no delete operation is executed here.

Tests execute actual source with injected collections/sessions/models and a small
in-memory numeric double; validate the role/department/shared matrix, malicious
literals, missing ACL fields and fallback equivalence. This does not prove Milvus
parser/PG SQL behavior or real JWT/API/browser/Linux acceptance. No external calls,
new packages, current-store access or filesystem deletion. Keep C07 open until
isolated live matrix and output-leakage acceptance; stop before C08.

## C08 design: request ownership and bounded scheduling

Create a fresh agent for every dispatched task; only lower-level model/store
factories may retain reusable services. Pass the authenticated user, current role,
department, conversation ID and request ID to ExecutionAgent. JWT stays outside
graph state. Each Send receives independent copies of identity, task and history.

Reset answer/replan/error fields at each entry. Aggregation binds completed answers
to their request ID. Load history from the same checkpointer used for invocation,
requiring matching answer/request IDs, user, conversation and current role/department.
Deduplicate by request ID, not question text. Skip unbound legacy snapshots and
current-request snapshots; do not migrate or delete them. Keep a bounded snapshot
scan; failures yield empty history. Bind the compiled graph cache to saver identity
as well as backend so replacement does not split history and invocation stores.
This is not same-session write serialization
or checkpoint durability; those remain C10.

Only independent fan-out is supported. Preserve declared dependencies before any
deduplication, then reject the entire plan before Send when any dependency is
present or malformed. The planner must not swallow this rejection into a fallback.
Use a dedicated terminal rejection node with a fixed message and no tool/model
execution. Add a code-owned decomposition instruction after the registry template
so existing active templates receive the dependency contract. Models may still
misclassify unstated dependencies; no general DAG or semantic proof is claimed.

Offline tests use actual source with injected framework/models/checkpointers,
including overlapping requests, isolated child histories, repeated questions,
stale/foreign snapshots, rejection and independent/replan compatibility. Real
LangGraph/API/SSE/checkpoint execution stays BLOCKED. Stop after local C08 delivery.

## C09 design: shared ephemeral coordination and prompt snapshots

Use the existing Redis dependency with bounded connection/command timeouts, fixed
versioned key prefixes and hashed session/state identifiers. No in-memory fallback
for cancellation or SSO. New chat work reserves a 30-second renewable session lease
before starting graph work; conflicting work receives 409. A per-task watcher polls
at 0.5 seconds, renews only its own lease, and cancels the owning task on a matching
request. Lease loss/store failure aborts with a fixed unavailable error. Atomic Lua
scripts bind cancellation and cleanup to the lease token, preventing late cleanup
or old cancellation from affecting the next run. Cancellation means accepted signal,
not rollback or completion; blocking work may outlive cooperative cancellation.
Worker death leaves an expiring lease; no automatic replay or exactly-once claim.

SSO login stores only random nonce under a hashed random state key for 600 seconds
with SET NX EX. Callback validates the browser cookie before atomic GETDEL, including
IdP-error callbacks. Unknown/expired/replayed states deny; store failures return 503
without exchanging a code or issuing a token. No filesystem/current-store cleanup.

Each persistent graph invocation loads active prompt versions once from PostgreSQL
into a ContextVar snapshot before any planner/agent execution. Threads/child tasks
inherit it; a running invocation stays pinned while later invocations on any worker
read committed activation/traffic changes. Database failure aborts instead of using
stale process cache. Non-persistent developer runs can explicitly use code/cache
defaults. Existing local cache remains for non-graph consumers, replaced atomically.
No Redis invalidation race, background polling or new schema/dependency is needed.

The current production Compose already uses one API worker as a provisional C01/C02
candidate; the original C09 investigation wording is stale. Keep that deployment
unchanged pending real two-process acceptance, without deciding to narrow the C09
target. No HA, full checkpoint consistency, queue/Saga recovery or capacity claims.
Offline tests use separate module instances over shared in-memory doubles; real
Redis Lua/TTL/GETDEL, SQL, context propagation and HTTP/SSE/SSO remain BLOCKED.

## C10 design: explicit persistence and failure boundaries

Select exactly one configured checkpoint backend (`redis` default, `postgres`, or
explicit `memory` only in development). No initialization/runtime failover, automatic
state copying, retries of graph execution or claims of recovery on an empty store.
All API workers must use the same backend/store/TTL; changing it requires stopped
traffic, a separate migration decision and isolated acceptance. Unknown backend or
memory outside development fails closed.

Serialize singleton initialization with an async lock and publish only after a
bounded read probe succeeds. Own saver resources through an AsyncExitStack; close
on failed initialization, cancellation and shutdown, and invalidate graph caches.
Redis retains the existing index setup and sliding TTL contract (days -> minutes).
Postgres uses its async context manager and `setup()` API; provisioning is a separate
explicit `setup-postgres --execute` command, never implicit relational DDL at API
startup. Its regular path probes pre-provisioned tables without suppressing errors.
Connection/setup/read bounds and fixed errors must not expose DSNs or exceptions.
No dependency additions, current-store access or setup execution in this increment.

Initialize the selected saver before API startup yields. History read errors stop
graph execution rather than masquerading as an empty history. Missing/expired
history stays distinct from a transport failure; no retroactive migration/deletion.
An SSE final snapshot must exist and match the current request and identity before
success is emitted; tokens remain provisional until final. Message/history return
fixed persistence failures; streamed failures emit an error. Graph write exceptions
propagate as failures with no automatic retry/switch or rollback claim.

C09 leases are still the API admission mechanism. They are not fencing tokens for
checkpoint writes: expiry, event-loop stalls and direct graph invocations do not
establish unconditional same-session serialization. Keep real two-process concurrent
write, crash, TTL, backend-loss, restart and actual installed saver-version tests
BLOCKED. Preserve checkpoint/business history; no arbitrary recovery/replay endpoint,
queue/Saga/approval work, backend switch or deployment worker-count change. A cached
backend label is not a continuous health probe; full readiness remains C21.

## C18 prework design: a versioned reference contract before recovery implementation

Freeze `business-reference-v1` as a target specification for independent controlled
CRM, ticket and mail HTTP services. It is not the current stub or a real vendor API.
Document wire requests/responses, configured service identity, run isolation, durable
operation ledger and receipts, same-key/body conflict rules, uncertain-outcome queries,
version-checked compensation and a capture-only mail sink. IdP remains C19.

Retain existing business route/output names where practical; explicitly list required
adapter changes instead of claiming compatibility. Keep reference service persistence
independent of application checkpoint/queue state. No automatic retention/reset or
filesystem deletion; CRM DELETE represents a retained business tombstone. Preserve
all prior evidence/fixtures and require a fresh isolated run for future acceptance.

Use durable per-action IDs, persisted before I/O, with separate linked compensation
IDs. Atomic service-side deduplication and effect/receipt commits define the reference
contract, while C12 owns application IDs/retries/receipt validation, C14 durable queue
ownership, C13 Saga recovery and C11 approval state. Do not implement those tasks now.
Reference contract cases must cover same/different payloads, concurrent requests,
response loss after commit, 401/403/5xx, invalid receipts, partial workflow failure,
compensation conflict/failure and mail recall-request versus actual recall.

The prework exit is a reviewed contract, field/route map, fault/evidence matrix and
explicit owner for each known implementation gap. No behavioral tests are claimed
for a document-only change. Full C18 application-to-independent-service acceptance
remains task 5.4 in S5; enterprise CRM/mail confirmations and C19 OIDC remain separate.
C10's lease-expiry race stays in C10 and does not become a reference-service guarantee.

## C12 design: persisted actions and conservative dispatch

Persist a UUIDv4 execution and per-slot UUIDv4 operations in PostgreSQL before tool
I/O. Bind the unique logical scope to authenticated user/session/request/task and
approval ID; freeze the normalized plan, provider, endpoint, run and principal. A
replayed scope must match its original plan, never silently regenerate actions.
Graph task IDs distinguish fan-out; changed replans for the same scope fail closed.
New user requests are new intentions, not transport retries. Queue/Saga recovery
will consume these retained IDs in C14/C13; they are not implemented here.

Use an additive checksum-pinned migration. No startup DDL, TTL, deletion or current
database execution. Persist the exact wire fingerprint/precondition before a CAS
prepared -> dispatched claim. Never reclaim that claim to send another mutation,
even after crash. Re-entry queries the original reference operation within bounded
budgets, or returns unknown. A crash before send can therefore require manual
reconciliation. This intentionally trades availability for no blind write retry.
Reads may retry twice; HTTP mutations are attempted once. All attempts have a total
deadline, no redirects and strict bounded JSON. A valid complete receipt is required
for success. Unproven HTTP profiles deny mutation, never fallback to mock.

Gate every action on current DB identity/role and mandatory prepared operation ID;
ignore skip_rbac for actions. External mail also requires an in-process authorization
scope issued only after the existing fresh requester-token/approver checks, bound
to the frozen approval calls. No bearer is persisted. C11 still owns atomic approval
claim/expiry/final state; C12 does not declare those races solved.

Implement forward CRM/ticket/mail reference mapping, strict operation/resource/version
checks, ticket version read frozen before PATCH, synthetic recipients and explicit
mail capture wording. Unsafe legacy HTTP compensation is disabled pending C13's
persistent linked compensation intents; missing evidence must fail, not succeed.
Stop downstream work and automatic inverse writes on unknown outcomes. Mock remains
a development demonstration and cannot establish external durability. Runtime
PostgreSQL/HTTP/LangGraph/Linux and OpenSpec CLI validation remain BLOCKED.

## C14 design: transactional jobs and conservative recovery

Replace the unused Redis List transport with PostgreSQL jobs in the same database
as business state. Knowledge approval locks a draft document and atomically records
a stable job plus queued status; repeated identical approval returns the same job,
changed parameters conflict. The response is 202 queued, never ingestion success.
Store only document identity, snapshot hash, reviewer and explicit publication options,
not file paths, tokens or raw content. Expose admin-only metadata/status queries.

Use SKIP LOCKED claims, database clock deadlines and random ownership tokens. Retain
all jobs; no destructive ack, TTL or cleanup. A lease before dispatch can be reclaimed
with bounded delayed attempts. Persist running before invoking any handler. Expired
running tasks, handler exceptions/timeouts and ambiguous results become retained dead
jobs for reconciliation, never blind replay. Ownership/deadline CAS fences queue state
only, not external writes. This is not exactly-once delivery or C10 fencing.

Worker verifies models/schema, initializes audit/tools and the configured vector backend
before consuming. Consumers reconnect to PostgreSQL with bounded backoff, heartbeat their
own progress in the database, and are supervised for unexpected return. Cancel children
and close resources on partial startup, failure and shutdown. Do not replay audit cache
files in this worker until C21 supplies an approved non-deleting recovery path.

Knowledge jobs revalidate the reviewer and frozen document before ingestion, and reject
zero chunks. Existing vector/ledger publication gaps remain C15, so dispatched jobs cannot
be automatically retried. Saga jobs fail closed with C13_REQUIRED until durable inverse
identities and a real producer exist; initialization is delivered, full Saga recovery is
explicitly blocked. Legacy Redis Lists are neither drained nor deleted; inspection and
import require a separate authorized plan. Redis remains for checkpoint/cancellation/SSO.

Offline tests exercise actual orchestration with injected SQL/handlers/services. Real SQL
locking, process death, PostgreSQL/Redis outages, Milvus and Linux acceptance remain BLOCKED.

## C13 design: durable inverse identities and conservative restart

The authorized C13 increment supersedes C14's C13_REQUIRED placeholder. Implement the
contract in `docs/50-engineering/saga-recovery.md`: new versioned Saga journal and atomic
recovery jobs; exact C12 plan binding; database ownership and guarded action claims;
no automatic forward continuation after restart; original-ID reconciliation before
reverse-order compensation; separate persisted inverse UUID/request/receipt per action.
All five reference inverse shapes are supported, with strict forward linkage and frozen
versions. Unknown outcomes and recall requests cannot report complete compensation.
Saga-only bounded queue retry is safe only through these retained dispatch claims;
knowledge jobs keep C14's conservative policy. Legacy Saga rows are not converted.
No new dependency, live service, migration execution or filesystem deletion. C10/C21
remain outside this increment. Real acceptance and OpenSpec CLI remain BLOCKED.

## C11 design: atomic approval decisions and one-way execution claims

Lock approval rows and use status/deadline predicates with RETURNING for every transition.
Approval expiry applies to pending and approved_pending_reauth, using database UTC time;
null legacy deadlines fail closed. Batch decisions are all-or-nothing, lock distinct IDs
in sorted order, reject duplicates and never execute tools. Approval, execution success
and compensation success remain different states.

Resume checks a fresh requester bearer and both current participants, binds the exact C12
plan/owner/session, then commits a unique execution binding and random claim before tool
I/O. Release identity locks before HTTP. Repeat resume never dispatches an already claimed
execution. A five-minute observation deadline marks execution_unknown, never releases or
reclaims it. Late completion may settle the same claim; expiry after a valid claim is not
cancellation of a sent request. Current tool authorization still applies per C05/C12.

Resolve state from retained C12 receipts / C13 journal: executed, execution_failed,
compensated, compensation_failed or execution_unknown. Worker reconciliation reads only
stored evidence and never mints JWT, approval scope or forward operations. Legacy executed
rows without new evidence remain historical/unverified, not re-certified by this increment.

Write transition audit events in the same database transaction as state changes. Notifications
are best-effort observations and cannot change committed outcomes; no automatic notification
retry or C21 cache replay. Add v5 schema fields/index without changing v1-v4 bytes. No live
migration/service/model calls, dependency addition or deletion. Stop after local C11 delivery.

## C15: publish immutable generations through a PostgreSQL visibility boundary

Persist a publication generation and frozen chunk plan before embedding/vector writes.
Use generation-specific chunk IDs and upsert, never delete old generations. Only a
complete acknowledged write may atomically switch the document to active and bind its
active generation. Pending work hides the old version. Identical retries reuse the
same generation; conflicting inputs while indexing are rejected. A disabled document
cannot be reactivated by a late worker. Recheck source and reviewer at activation.

All application retrieval runs in a fresh, bounded PostgreSQL visibility snapshot,
including vector candidates before reranking, keyword and PG fallback. Match chunk IDs
and canonical content/ACL against the current active generation; stale, partial and
legacy unversioned rows are not eligible. Database failure fails closed, with no cached
visibility fallback. A request admitted before deactivation may finish; this is not
revocation of already-produced answers. Snapshot bounds and post-filter recall limits
are documented and require C17/full runtime evaluation.

Add migration v6 without rewriting v1-v5. Retain failed publications and dead tasks.
An admin may explicitly retry a dead knowledge job using the same immutable plan;
no generic queue reset or automatic mutation replay. Add guarded deactivation and
metadata status routes. This does not change C10 checkpoint fencing or C21 audit replay.

## C17 quality evidence and execution boundary

Use a versioned, standard-library metric core and a separate explicit runtime CLI.
Freeze input/source hashes and IDs; keep 122 primary cases and six supplemental ACL
controls separately denominated. Missing evidence remains a row with zero credit.
Normal-answer coverage uses all eligible cases, failures/skips included. Mechanical
keyword, citation-index and refusal-marker checks are proxies, never factual accuracy.
Manual semantic citation/refusal review and accepted C02 profile remain mandatory.
Capture the actual KnowledgeAgent degradation call and final decision, without duplicate
retrieval or a parallel prompt implementation. Preserve role, source/chunk IDs, stage,
status, safe failure code, attribution, prompts/config and source hashes. Exact source
identity replaces substring title hits. Runtime requires an isolated published corpus,
read-only preflight, existing Milvus collection and a fresh output file; no auto ingest,
reset, schema creation or report overwrite. Offline default never imports the app.
Keep vector, bounded keyword scan and PG fulltext/ILIKE stages distinct. A database
outage must not become a successful no-answer refusal. Do not tune retrieval thresholds
or prompts without measured full-corpus failures. Report v2 is not comparable to the
old success-only metric and does not grant merge, release or enterprise UAT acceptance.

## C18 independent reference implementation

Implement an isolated standard-library HTTP service package, deployed as three separate
processes from one reference image with per-service SQLite databases and distinct credentials. Share no
application adapter implementation. Use transactions for business state and receipts,
retained before-images/tombstones, exact wire validation and run/principal isolation.
A pending operation has no committed effect because effect and terminal receipt share
one transaction; same-key recovery is safe only under matching store identity/schema.
PERSIST journal, memory temporary storage, no WAL cleanup/reset/delete/vacuum endpoints.
No claim of production database HA or general exactly-once behavior.

Freeze control-v1 on a separate authenticated listener: append-only run provisioning,
operation/attempt/phase-scoped faults and bounded evidence reads. No business-header or
natural-language fault trigger. Service credentials and operator credential are separate;
reference mail is a captured record only, with allowlisted recipients/attachment IDs and
an internal Docker network without public ports or egress. Application authority remains
C05/C11; external captured mail still requires actual approval plus requester resume.

Provide business-reference-v1 B01-B13 and the crm-analysis-v1 snapshot extension against
immutable seeded customer/order records. Snapshots bind run/principal/range and retain
source identity; task/ticket/mail effects cannot silently alter source analytics.
Keep the frozen R01-R20 matrix as runtime acceptance. Provide an opt-in application-entry
transcript runner (login/message/approval/resume) with independent service evidence and
separate operator observations for restart, concurrent faults and application
PG/audit/queue/Saga correlation. It cannot grant full PASS from tool-only service tests
or response text. Known operation IDs are required before arming targeted faults; no
production planner bypass or unscoped next-request fault shortcut is introduced.
Offline tests use actual in-memory SQLite and injected transport, not disk durability,
real sockets, actual JWT/PG/LLM or deployment acceptance. All runtime cases remain open.

The application exposes two admin-only, read-only observation endpoints: reference-profile
returns credential-free configuration booleans and run identity; reference-evidence returns
bounded per-session operation/request hashes and approval/Saga/queue/audit metadata, omitting
payloads and credentials. Reads are parameterized, time/row bounded and explicitly non-atomic.
The collector checks expected service/store UUIDs and stable fixture hashes before business
messages. These identities do not attest an image or backup freshness. Missing audit is never
repaired (C21), and collector OBSERVED never closes a runtime case. SQLite uses PERSIST/FULL
and memory temporary storage; physical crash/savepoint retention is an unexecuted Linux gate.

## C19 controlled OIDC reference design — 2026-10-18

The user approved adding PyJWT[crypto], cryptography==50.0.2 and required transitive
pins plus image import checks, without installation/build/signing/live IdP execution.
Use a separate retained SQLite-backed issuer with environment-provided synthetic user
credentials, RSA private keys and distinct operator/client secrets. Provide HTTPS
/discovery, /authorize, /authenticate, /token, /jwks and private operator evidence/key
rotation/fault controls. Exact client/redirect bindings, S256 PKCE, hashed one-use codes,
short expiry and browser-bound form submission are mandatory. No arbitrary redirect,
automatic key generation, public reset, cleanup or enterprise IdP impersonation.

Application verification pins RS256 independently of token headers, exact nonempty kid,
RSA signing public keys, unique matching key and validated issuer/audience/azp/nonce/time.
Fetch only configured HTTPS endpoints with bounded JSON and no redirects; token exchange
is not retried blindly. Keep the raw issuer/sub identity exact, reject overlength or
malformed identity instead of truncating, and never link by email/username. New accounts
use salesperson and configured default department only, never remote role/department
claims or privileged defaults; existing local role/disable state remains authoritative.
Extend shared single-use state with a PKCE verifier; old nonce-only state cannot satisfy
the new callback. Missing Redis or crypto fails closed, without weakening local login.

Provide isolated TLS/CA/hostname recipes using existing Python/Nginx images, and a
browser/operator scenario record with all SSO runtime cases BLOCKED by default. Offline
source/in-memory storage/crypto-double checks are explicitly not real signatures or a
browser. Real rotation, restart, JWT/PG/Redis, browser handoff and deny cases require the
same application candidate and independent issuer; no claims of OIDC certification,
enterprise federation, UAT or release. C18 R01-R20, full RAG, C10 and C21 remain unchanged.

## C20 browser delivery design — 2026-10-18

Keep the existing Vue global-build UI and backend routes. Self-host the already referenced
Vue/Marked/DOMPurify distributions with exact versions, registry tarball integrity, per-file
hashes/SRI and license files. Missing Vue leaves a visible static boot failure; missing Markdown
or sanitizer keeps C06 escaped-text fallback. No remote script/CDN fallback or new build stack.

Treat login/SSO roles as provisional until `/auth/me` confirms current identity. Snapshot auth
and conversation generations around asynchronous operations; stale responses cannot reinsert
private data after logout or session change. Role-gate management views and methods, retain
backend authority and refresh identity before privileged mutations. Serialize repeated actions
locally, distinguish request failure/unknown outcome from a confirmed result, and never auto-retry
mutations. A cancelled prompt performs no write. Empty, loading and unavailable lists are distinct.

Require a terminal SSE event; truncated/malformed/mismatched streams remain incomplete with
partial output explicitly labelled. Accepted cancellation is a request, not confirmed completion;
do not abort the stream and fabricate cancellation. Use bounded response/time/frame budgets.
Keep the static business examples but label them as synthetic and independent of current provider
data; remove the live document ledger's fixture fallback. User/knowledge mutations without UI stay
documented authenticated API workflows. A role × flow matrix covers positive, denied, stale,
duplicate, timeout, renderer and dependency failure cases, all runtime BLOCKED until observed.


## C21 runtime observability design — 2026-10-18

Readiness probes are bounded and return sanitized component states plus 503 if a required
store/checkpointer/tool/worker/audit dependency is unavailable; health stays liveness only.
No paid model calls on probes. API and worker share a retained local SQLite outbox on one
Linux filesystem. Each connection enforces PERSIST/FULL and memory temp storage; no cleanup,
WAL lifecycle, VACUUM or deletion. New audits are retained before PostgreSQL submission;
a UUID unique index deduplicates retries after ambiguous commit. Acknowledgement updates the
retained record only after commit. Batch replay is ordered/bounded with failed records deferred
so one poison record cannot starve others. Legacy unkeyed JSON stays retained and requires
explicit reconciliation before import; old database duplicates cannot be inferred away.

Use context variables for server-generated request IDs and worker task IDs; enrich sanitized
audit records and keep IDs out of metric labels. Pure ASGI metrics observe response start,
last body and exceptions/disconnects using route templates, not raw paths. Scrape each API
container and the independent worker separately; one process per container, at least two API
containers in the isolated acceptance overlay. No shared multiprocess-file cleanup or false
single-scrape aggregation. K8s/multi-host remain outside accepted profile.

A dedicated internal monitor probes required targets and retains fault/resolution transitions
and pending deliveries in SQLite. Fixed authenticated webhook delivery has bounded attempts
per tick and stable event IDs; the independent receiver retains deduplicated receipts. No email,
Slack or actual notification is sent this turn. Existing Prometheus rules remain separate;
new component rules and accurate full-response/SSE units do not claim TTFT or measured SLA.
Receiver/monitor image recipes reuse the application image and installed dependencies.
Physical durability, process faults, retention, complete traces and receiver receipt/recovery
are runtime gates; offline memory/injected checks cannot close C21 or earlier cases.

C21 implementation review also moves FastAPI instrumentation before middleware-stack build,
keeps worker signal ownership in its supervisor, packages every manifest SQL file, and updates
the deployment checker for shared retained volumes and the worker-specific probe. Removed
unproduced metric families are not zero-valued quality evidence. Both audit stores failing
can lose an event; process-local unretained observation makes readiness unhealthy but is not
repair or a durable loss inventory. The monitor cannot self-report its own outage. The frozen
O01–O16 matrix in docs/50-engineering/runtime-observability.md remains BLOCKED. Only 6.2.1 is
complete; 6.2, C10 and prior runtime acceptance remain open. No push or C22 this increment.


## C22 retained cold recovery design — 2026-10-18

Use a standard-library, plan-first controller and a packaged archive helper. Freeze a
sanitized Docker inventory (container IDs, project/service labels, image IDs, states and
named mounts) and current schema-manifest hash. Reject writable binds, shared writers,
missing core volumes, anonymous state and mutable helper images. A reviewed plan digest
and exact isolated project are mandatory before execution. Execution is not authorized
on this host; injected command runners cover offline behavior.

Capture all project named volumes, including PostgreSQL, Redis, etcd, MinIO, Milvus, audit,
optional reference/IdP/monitor state and monitoring volumes. Cold physical snapshots require
all source containers stopped, all writers excluded and original runtime image identities
retained. Check stopped state before/after each copy; metadata/hash every regular file and
directory. No live tar consistency claim, partial-DB restore or migration downgrade. External
writers/automation and storage lifecycle require a separately reviewed isolation boundary.

Always attempt to restart originally running containers after partial stop/copy failure;
record each failure independently and retain partial artifacts. SIGKILL/host failure cannot
run finally: a plan-bound resume command must support explicit recovery. Never start a
container originally stopped. A restarted process is not application-ready or accepted.

Restore only to a fresh target project and never-existing named volumes. Validate the complete
bundle, schema and archive paths/types/content before any volume creation. Reject symlinks,
hardlinks, traversal, duplicate members and unexpected targets. Retain helper containers,
volumes, journals, partial outputs and source bytes; no rm/down/volume removal/cleanup.
Helpers use the exact application image, no network and narrowly scoped data mounts.
Restoration does not start applications or dispatch copied queue/Saga work. The operator must
provision matching images/config/secrets and reconcile external effects before activation.

A 12-hour cold-backup cadence is an unactivated proposal, not measured RPO. Record snapshot age from
the beginning of quiescence, and RTO through independently verified service/business recovery,
not extraction completion. RTO <= 1h / RPO <= 24h stay BLOCKED pending D01–D16. Rollback needs
an explicitly compatible schema plus retained old image, or a separate full snapshot clone;
never overwrite source state or run older applications on newer schema. No downgrade DDL.


## C23 frozen capacity evidence design — 2026-10-19

Provide a standard-library runner, plan validator and pure report functions. Draft plans
contain unresolved hardware/image/data identities and cannot execute. Execution requires
an explicit flag and the exact canonical plan digest confirmed before the run. The target
is the fixed internal application/reference network; no arbitrary URLs, provisioning,
cleanup, application startup or credential persistence. Existing service readiness and
synthetic fixture/identity provisioning are operator prerequisites, never inferred.

Use a deterministic open-loop arrival schedule for at least 1800 seconds with a frozen
Q&A/analysis/approved-mail mix and bounded concurrent work. Do not count health traffic.
Each scheduled slot remains in the denominator, including missed launches, errors, 429s
and incomplete requests. No automatic business retry or new key after uncertainty.
Each flow uses a fresh session. Approval follows requester chat, distinct approver decision
and requester resume; independent reference receipt and application evidence are mandatory.

Measure client monotonic full response and first nonempty user-facing SSE token separately;
headers/progress/final alone do not establish TTFT. Record bounded template-labelled HTTP
phases separately from total workflow latency, including failures. Fixed nearest-rank
percentiles use completed timed attempts; expose missing/censored samples and fixed total
failure denominator. Retain p95 <=2s, p99 <=5s, error <0.5% historical baseline without
post-hoc relaxation. Missing observations, semantic review, actual queue timings, resource
time series, quota/cost and backlog recovery keep full acceptance BLOCKED.

Persist only allowlisted counters, statuses, elapsed times and hashes. No answers, prompts,
credentials, raw provider records or exception text in measured outputs. Write records
exclusively to a fresh retained directory; interrupted runs cannot become PASS. Plan
identities are declarations until independently verified. No measured maximum capacity or
monthly SLA claim from one load point; all L01–L16 runtime cases remain BLOCKED this turn.

## C24 offline candidate evidence design — 2026-10-19

Keep the original five-function safety entry independent. Add a standard-library
orchestrator with fixed reviewed commands, expected suite counts and a frozen source
digest. No discovery-based execution, user-supplied commands, automatic trust refresh,
installation, application startup or cleanup. A source mismatch blocks execution.
Children run sequentially with bounded timeouts; Python uses -I -B and Node preload
options are removed. Preserve the host environment required by its Git wrapper; never
serialize environment values or raw test output. This is trusted reviewed-code
orchestration, not a security sandbox. C22/safety test fixtures are retained explicitly.

Record HEAD, tracked content identity, untracked-file count, source digest, interpreter
versions, per-entry PASS/FAIL/BLOCKED and exact executed/skipped counts. Check candidate
and source identities before and after execution. Dirty/untracked content cannot be
labelled a committed candidate. A nonzero failure, zero/wrong test count, malformed
output or unexpected skip cannot become PASS. Expected missing PyYAML is separately
BLOCKED, not a passed case. Git-only mode changes are reported separately and preserved.
Write only exclusive receipts under ignored eval/results, refusing symlink paths and
collisions. Report overall acceptance BLOCKED even when all available offline checks
pass. Post-commit rerun binds evidence to the delivered local commit without a circular
documentation commit. Whole pytest, actual dependency imports, image/scanner/CI results,
OpenSpec strict, E2/E3/E4 and C10 are explicit uncovered gates.

## C25 offline delivery reconciliation — 2026-10-19

Use the current source and schema manifest as authority for present behavior; use ISSUES
for acceptance and ROADMAP/tasks for sequencing. Root READMEs describe current setup and
support boundaries in both languages, not chronological progress logs. Older detailed
manuals keep their historical examples and measurements but prominently route current
operations to reviewed engineering contracts; correct conflicting current instructions.
Record a source-to-document matrix and an explicit NOT_ACCEPTED_FOR_RELEASE conclusion.

Application version 1.3.0 remains the existing source/tag baseline, not a tag for the
closeout candidate. Schema v7, document revision labels, Git commits and image digests are
different identities. Update Unreleased only; do not invent a new release or image digest.
The active change's deltas remain unsynchronized while runtime requirements are open.
Static structure checks cannot replace the unavailable OpenSpec CLI strict validation.

PR/CI metadata is a time-bound read-only observation. A failed job remains FAIL; missing,
pending or unrun candidate checks remain BLOCKED. Neither historical green CI nor the
C24 offline receipt proves the new commit's CI or E2/E3. Preserve 556 mode-only differences,
snapshot tracked content/modes, commit only documents, then rerun the existing fixed C24
entry to bind the final documentation candidate without editing its source allowlist.
