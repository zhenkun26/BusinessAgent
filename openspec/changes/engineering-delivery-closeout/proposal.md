## Why

项目已有多 Agent、检索、审批、外部适配与部署资产，但代码静态复核仍发现权限、执行一致性和可复现部署缺口。历史 CI、Mock 契约和阶段归档不能证明当前完整系统可交付；项目也没有真实企业用户、业务联调与灰度证据。

用户确认以「可独立部署、完整执行、可重复验证的企业应用工程交付」为收尾目标，并授权先完成 S0 文档与规格，之后逐项确认推进。

## What Changes

- 建立工程交付基线，冻结支持范围、参考服务边界、证据等级和完成条件。
- 在 ISSUES 登记 C01–C25 的当前证据、缺口、验收标准；在 ROADMAP 维护 S0–S7 顺序与依赖。
- 本 change 的 S0 仅落盘计划；后续任务保持未执行，每项须用户确认后进入实施。
- 保留真实接入与正式 UAT 两个既有 change 的未完成任务及生产放行阻塞状态。

## Capabilities

### New Capabilities

- `capacity-evidence`: C23 frozen mixed workloads, separate timing and bounded capacity claims.

- `retained-recovery`: C22 cold backup plans, new-volume restore, source resumption and evidence-bound rollback.

- `runtime-observability`: C21 dependency readiness, retained audit replay, process-complete metrics and controlled alert delivery.

- `browser-delivery`: C20 pinned self-hosted assets, current-identity UI flows and truthful failure/acceptance states.

- `controlled-sso`: C19 independent retained issuer, strict RS256/PKCE identity mapping and isolated browser acceptance.

- `analysis-data`: C16 provider-aligned snapshot reads, bounded aggregation and deterministic reporting.

- `engineering-delivery`: 工程交付范围、逐项验收证据、顺序推进及与企业现场生产验证的隔离规则。
- `deployment-artifacts`: C01 的同摘要镜像部署、生产入口路由、流式透传与内部指标边界。

- `model-profile`: C02 生产模型方案、依赖契约、启动推理探针与失败闭合。

- `database-bootstrap`: C03 explicit migrations, schema readiness and isolated administrator/demo bootstrap.
- `session-ownership`: C04 persisted chat-session ownership, explicit administrator exceptions and authorization before side effects.

- `runtime-authorization`: C05 current identity and approval authorization.
- `credential-safety`: C06 transient credentials, redacted diagnostics and safe HTML fallback.
- `retrieval-authorization`: C07 shared retrieval scope, safe expression literals and result guards.
- `request-context`: C08 per-dispatch agents, request-bound history and explicit dependency rejection.
- `cross-process-state`: C09 shared cancellation leases, single-use SSO state and request-scoped prompt snapshots.
- `checkpoint-durability`: C10 explicit backend selection, managed saver lifetime and fail-closed persistence semantics.
- `tool-operation-safety`: C12 durable action identity, one-way dispatch, receipt validation and runtime gateway authorization.
- `durable-task-queue`: C14 transactional PostgreSQL jobs, ownership, retained failures and fail-closed worker initialization.
- `reference-business-contract`: C18 prework defining the controlled CRM/ticket/mail contract, failure evidence and handoff to C12-C14/C11 and S5.

### Modified Capabilities

C14 adds modified deltas for `knowledge-operations` (asynchronous approval) and
`external-system-integration` (worker recovery boundaries). Main specs remain
unchanged until the complete change is accepted and synced.

## Impact

- S0 仅修改项目文档、OpenSpec context 与本 change。2026-10-17 用户进一步授权 C24 前置：新增离线安全验证入口、针对入口的回归测试及证据模板；不改应用业务行为、依赖、部署配置或版本号。
- 当前代码基线：`153f78651217eec7544b064446344d27b36085f1`。
- 差距事实源：[ISSUES](../../../docs/40-process/ISSUES.md#engineering-closeout)。
- 排期事实源：[ROADMAP](../../../docs/40-process/ROADMAP.md#engineering-closeout-stages)。
- 交付契约：[工程交付基线](../../../docs/50-engineering/engineering-delivery-baseline.md)。
- S0 文档提交 `05d8d0c` 已按用户单独授权推送到同名远端分支；该授权不延伸为 C24 新提交的推送。合并、发布、部署或外部消息/业务写入不在本轮范围；不新增依赖、不执行删除。

2026-10-17 后续授权：C24 提交 `a329603` 已推送到同名远端；本轮推进 C01，修改生产 Compose、Nginx、部署契约检查及文档，不扩展到 C02 模型、C03 迁移或 C09 多进程一致性。用户随后授权 C01 配置修复独立提交并推送到同名远端分支，再推进 C02；当时 C03 尚未授权（后续授权见下文）。真实运行验收缺少 Docker/Nginx 时保留 BLOCKED，不提前勾选整项。

C02 scope (confirmed 2026-10-17): replace the provisional local candidate with Beijing Bailian embedding/reranking and official DeepSeek Flash/Pro services. Implement separate credentials, bounded remote adapters, profile/startup validation, isolated vector collection configuration and slim-image alignment; retain approved libpq5/checkpoint checks. This increment includes documentation and offline verification only. Real API calls and isolated Linux acceptance remain BLOCKED; C02 remains open; the then-pending C03 authorization is recorded separately below.

C03 authorization (2026-10-17): C02 commit `42bfc7f6f3033c5eb5e06fb6d497a92dad86a039` was pushed and the remote branch hash verified. Implement C03 without touching the current database; real API/Linux acceptance remains BLOCKED. C04 and C03 push are not authorized.

C04 authorization (2026-10-17): the user approved pushing C03 and implementing C04. C03 `fc8da91534a64737fae32d76b81ed00580f5093e` was pushed to the same remote branch and its hash verified. Real PostgreSQL/API/Linux acceptance remains BLOCKED; deliver C04 locally and pause. No C04 push, C05 work, deployment or release is authorized.

## C05 authorization update (2026-10-17)

The user authorized pushing C04 `dbc8236` to the same remote branch and then
implementing C05 only. The push was verified at origin/codex/delivery-ci-gates.
C05 includes fail-closed identity resolution, production authentication gates and
approval execution reauthorization. Real PostgreSQL/API/SSE/Linux acceptance stays
BLOCKED. C05 push and C06 require later confirmation. No new dependencies or live calls.

## C06 authorization update (2026-10-17)

C05 `9f5397c` was pushed and verified on origin/codex/delivery-ci-gates under
explicit user authorization. Implement C06 only: remove reusable credentials from
approval/checkpoint inputs, use explicit requester confirmation after approval,
redact diagnostics and fail safely on HTML rendering errors. No new dependencies,
real calls, historical-data cleanup or deployment; C06 push and C07 await confirmation.


## C07 authorization update (2026-10-17)

The user authorized pushing C06 `6955133` and implementing C07 only. The same
remote branch was verified at that commit. Unify retrieval authorization and
expression encoding across memory/vector/keyword/PostgreSQL paths; validate
results before reranking, generation and citations. No new dependencies, live
services, indexing, data cleanup or deployment. Prior runtime/browser/SSO/history
blockers remain; C07 push and C08 require later confirmation.

## C08 authorization update (2026-10-17)

The user authorized pushing C07 `ceae708` and implementing C08 only. The remote
branch hash was verified. Deliver request isolation, history propagation and
fail-closed dependency handling with offline tests. Real Milvus/JWT/PostgreSQL/
API/SSE/Linux/browser/SSO and historical credential acceptance remain BLOCKED.
C08 push and C09 await confirmation; no dependencies, live calls or cleanup.

## C09 authorization update (2026-10-17)

C08 `d81c2814f9c1ffe74956f62f10ddff4a3fc5525c` was pushed and verified on the
same remote branch under explicit user authorization. Implement C09 only, using
already declared Redis/SQLAlchemy dependencies. Keep real LangGraph/Milvus/JWT/
PostgreSQL/API/SSE/Linux/browser/SSO and historical credential acceptance BLOCKED.
Real Redis multi-process acceptance is also BLOCKED. Do not push C09 or start C10.

C10 authorization (2026-10-17): C09 `079cd621a07be97be3861a0ae54668c373b547d6` was pushed and verified on the same remote branch. Implement C10 offline only, preserve all real-service blockers, commit locally and stop before C18 prework or any further item. C10 push requires separate confirmation.

## C18 prework authorization (2026-10-17)

C10 `a57bd4ed001d86d2da304e890d01da1e7e76db41` was pushed and verified on the
same remote branch. The user authorized only C18 reference-contract prework next.
Freeze a versioned project-controlled contract and acceptance matrix in documents
and OpenSpec; no runtime code, service startup, network business calls, dependencies,
real recipients or enterprise-provider confirmations. C10 remains open with the
lease-expiry write race and all real-runtime blockers. Stop after the local document
increment; C12 and further push require subsequent confirmation.

## C12 authorization update (2026-10-17)

C18 prework `317aa7f` was pushed to the same remote branch. The user authorized
C12 implementation, documentation and offline verification only. Add capability
`tool-operation-safety`: durable action identity, guarded dispatch, strict reference
receipts, read-only reconciliation and gateway authorization. Do not run services,
install dependencies, migrate current stores or start C14/C13/C11. C10 remains open.
C12 push requires separate confirmation.

## C14 authorization update (2026-10-17)

C12 `21b5287` was pushed and its same-name remote branch verified. Implement C14
offline only, using existing PostgreSQL dependencies and an additive migration.
Keep live acceptance BLOCKED, C10 fencing open and HTTP compensation deferred to C13.
Stop after local delivery; C14 push and subsequent work require confirmation.

## Authorized C13 increment

Persist Saga execution and recovery evidence, connect C14's transactional worker to
the journal, and implement previously deferred linked HTTP compensation. Deliver offline
verification and explicit live blockers, then stop before C11. C14 commit `59a5c14` was
pushed to the same remote branch; C13 remains local pending separate push authorization.

## Authorized C11 increment

C13 `c42dcf8` is pushed to the same branch. Implement atomic approval decisions/execution
claiming, expiry and evidence-based final status, with UI/docs/offline tests. Preserve
runtime BLOCKED, C10 open and C21 audit replay deferred; stop before C15. C11 push requires
separate authorization.

## Authorized C15 increment

C11 `8bb6241` was pushed and verified on the same remote branch. Implement C15 only:
versioned publication, index/ledger visibility, guarded retry and deactivation, with
docs/offline tests. No dependencies, live calls, migrations or deletion. C10 remains
open, C21 audit replay deferred. Stop after local delivery before C16; no C15 push.

## Authorized C16 increment

C15 `0c0c5f9` was pushed and the same remote branch verified. Implement C16 only:
CRM-provider-aligned analysis, versioned paginated reference read contract, current
authorization, validated integer money and deterministic reports with provenance.
No new dependencies, live calls, deployment or migration. Runtime/full RAG acceptance
remains BLOCKED; C10 stays open and C21 audit replay deferred. Stop locally before C17.

## Authorized C17 increment

C16 `bb81833` was pushed and the identical remote branch verified. Implement C17 only:
freeze the original 122 cases and nine sources; add a separate role-control suite;
make full eligible denominators, missing/failed/skipped states and evidence explicit;
evaluate the actual KnowledgeAgent and name retrieval algorithms truthfully.
No live model calls, ingestion, stores, installations or runtime acceptance this turn.
Quality tuning requires real per-case diagnosis; no widened labels or deleted samples.
C02/full RAG/runtime acceptance stays BLOCKED, C10 open, audit replay C21. Stop after
the local C17 commit before push or C18 full integration.

## Authorized C18 implementation increment (2026-10-18)

C17 `cd49d78` was pushed and the identical remote branch verified. Implement C18's
independent controlled CRM/ticket/mail services, persistent reference ledger, isolated
build/deployment recipe, application-entry evidence harness and offline verification.
Use Python's declared-runtime standard library; no new dependency or service installation.
Do not start services, call APIs/models, migrate current stores, delete files or send mail.
Full R01-R20 execution, real runtime/full RAG remain BLOCKED. Preserve C10's write race
and C21 audit replay. Stop after the local C18 increment before its push or C19.

## Authorized C19 increment — 2026-10-18

C18 bd04a120daf6695f5b735bcd73733c0e2def07b1 is pushed and remote-verified. Implement
C19 only: independent controlled OIDC issuer, strict application verification/mapping,
private TLS deployment and retained browser acceptance procedures/evidence, with offline
checks. Real browser/IdP/JWT/PG/Redis/Linux and full RAG remain BLOCKED; C18 R01–R20,
C10 fencing and C21 audit replay remain open. Stop at a local commit before push/C20.

Dependency approval required before editing dependency manifests: existing PyJWT is
installed without its crypto extra; the production lock has no cryptography backend.
RS256 signing/verification needs PyJWT[crypto] and an explicit reviewed cryptography pin
(with its declared transitive dependencies). Proposed scope is dependency declarations
and image import probes only; no local installation, image build, key generation or
real signing/API/browser execution. Do not replace asymmetric verification with HS256
or custom cryptography to avoid this approval. Independent work can proceed meanwhile.

Approval received on 2026-10-18: add PyJWT[crypto], cryptography==50.0.2, cffi==2.1.1
and pycparser==3.11 declarations and import probes. PyPI metadata confirms the dependency
edges; resolution, installation, build, vulnerability scan and real cryptography are unrun.
The existing PyJWT pin stays 2.15.0. This supersedes the approval-pending state above.

## Authorized C20 increment — 2026-10-18

C19 `4afe54bda9cfd581870d84ced50fb5dd86687c75` was pushed and remote-verified.
The user authorized C20 browser role flows and frontend delivery only. Vendor the three
already-used browser libraries at exact registry versions, with licenses/checksums; no new
framework or package installation. Fix current-identity gates, stale async results, repeated
actions, interrupted streams/cancellation and misleading fixture fallbacks. Document API-only
administration and a complete role/browser acceptance matrix. Source/VM checks cannot close
real browser/PG/JWT/API/SSE/Linux, S01–S16, R01–R20 or full RAG. Preserve C10/C21; stop after
a local C20 commit, before its push or C21. No app/service launch, paid call or data cleanup.


## Authorized C21 increment — 2026-10-18

C20 `44bfcb072e2f01373cd3a0d42398ed6ffe6eba5d` was pushed and remote-verified.
The user authorized C21 including previously deferred non-deleting audit replay. Implement
bounded dependency readiness, a shared retained SQLite audit outbox with stable PostgreSQL
identity, request/task correlation, per-process ASGI metrics and a controlled alert receiver.
Use existing packages and standard-library SQLite; no new dependency, local service launch,
real API call, migration, filesystem deletion or production notification. Record offline
verification separately; B01–B16/S01–S16/R01–R20/full RAG/real runtime stay BLOCKED and C10
writing stays open. Stop at a local C21 commit before push/C22.

2026-10-18 C22 authorization: C21 `40c10d8` was pushed and verified on the same-name
remote branch. Implement current-version backup/recovery/rollback entry points, documentation
and offline fault tests. No real backup, stop/start, restore, Docker, database or external API
execution on this host. C22 ends at a local commit, then waits; no C23 or new dependencies.
Prior O/B/S/R/full-RAG gates remain BLOCKED and C10 writing remains open.


## Authorized C23 increment — 2026-10-19

C22 `d70c1b4` was pushed and the same-name remote hash verified. Implement C23 frozen
workload validation, opt-in mixed application measurement, fail-closed offline reporting
and tests. No real load, API/model call, deployment, installation or deletion this turn.
C23 ends at a local commit; D/O/B/S/R/runtime/full RAG stay BLOCKED and C10 remains open.
No C24 final candidate, merge, release or C23 push is authorized.

## Authorized C24 offline candidate increment — 2026-10-19

The subsequent authorization pushes C23 `6de94c6` to the same-name remote (verified),
then permits C24 offline final-candidate checks, documentation and a local commit.
Provide an explicit reviewed suite inventory, source-bound retained receipts and current
E0/E1 evidence. Repair stale test doubles discovered by this sweep without weakening
their behavioral assertions. Quote ambiguous flow scalars found by static YAML checks
without changing intended deployment values. Do not run full pytest/plugins, live services, containers,
models, browsers, load or cleanup. L/D/O/B/S/R, runtime/full RAG and historical-credential
acceptance remain BLOCKED; C10 lease-expiry fencing remains open. C24 is not fully closed;
C25, C24 push, merge, release, spec synchronization and archive await authorization.

## Authorized C25 offline reconciliation — 2026-10-19

Subsequent authorization pushes C24 `d8a26b5` to the same-name remote (verified), then
permits C25 Git/documentation/OpenSpec/delivery-conclusion work that can be completed
offline. Reconcile bilingual entry points, current model/schema/state/operation contracts,
navigation and unreleased version identity; retain historical evidence with explicit scope.
Inspect PR/CI metadata read-only, without dispatching or changing CI. Do not fix runtime
behavior or dependency/security/CI failures under this documentation increment. Record
observed failures and missing verification separately. Leave application version/tags,
main specifications and archive directories unchanged. End at a local commit and wait;
no C25 push, merge, release, deployment, spec synchronization or archive is authorized.
All L/D/O/B/S/R/runtime/full-RAG gates stay BLOCKED; C10 write fencing remains open.
