## Context

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
