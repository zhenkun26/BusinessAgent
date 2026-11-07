# BusinessAgent 项目说明

## 项目概览

本仓库是「智多星——企业级多智能体平台」的工程实践项目：基于
LangChain + LangGraph + Milvus 构建的多 Agent 系统。当前没有真实企业使用，工程验证与企业现场生产验证须分开记录；交付边界见 `docs/50-engineering/engineering-delivery-baseline.md`。后端代码位于
`enterprise-agent/`，文档统一存放在 `docs/`（六大层分类），面试与演示资产
独立存放在 `interview/`。

## Current purpose and next-work boundary (2026-10-22)

This is a backend engineering portfolio for future GitHub open-source presentation and
job applications; no customer deployment or commercial operation is currently planned.
Use real-project scope/review/test/acceptance discipline without inventing enterprise usage
or lowering evidence gates. C10 isolation was implemented in local commit `6396252`;
C10-R1/R2 follow-ups after planning commit `c0a4464` are now fixed/offline verified
(25 focused cases; full local pytest 925 tests + 249 subtests, zero skips).
The confirmed F2 review of `c57d473` is complete as a single-agent, twelve-perspective
audit; see `docs/40-process/multi-expert-review-c57d473.md`. Eleven findings are registered
in ISSUES. The subsequently confirmed F2-01 (unverified JWT quota identity) is now fixed/
offline verified: shared signed-token validation, source-IP login quota, bounded parsing;
30 new cases and full suite 955 tests + 249 subtests PASS, zero skips. F2-02 was then confirmed:
non-dev Redis failures return 503, dev fallback is labeled, cooldown/single-probe recovery
and unique shared observations are implemented. 18 new cases and full suite 973 tests +
249 subtests PASS, zero skips. See `docs/50-engineering/cross-process-state.md`.
The C10 follow-up fixes normalize citation
projections and select eligible history within shared scan/time budgets. Real runtime/
two-process/full RAG remain BLOCKED and C10 open. The subsequently confirmed F2-03
execution-budget slice is implemented/offline verified: 34 new cases, full suite 1007 tests
+ 249 subtests PASS, zero skips. See `docs/50-engineering/request-context.md` for limits and
cooperative deadline semantics. That execution slice was committed locally as `d52707f`.
The separately confirmed SSE slice is now implemented/offline verified: 41 new cases, full
suite 1048 tests + 249 subtests PASS, zero skips; bounded data/frame/terminal admission,
cooperative send/lifetime limits and producer cleanup. F2-03 runtime acceptance stays OPEN /
BLOCKED; SSE was locally committed as `e3831b3`. F2-04 was then confirmed and implemented/
offline verified: reviewed production image/frontend/snapshot/wheel inputs, final installed
inventory and CI evidence wiring; 50 new cases, full 1098 tests + 249 subtests PASS, zero
skips. See enterprise-agent/deploy/DEPLOY.md for scope/update procedure. Actual Linux install/two-build/
inventory/scans remain BLOCKED; F2-04 acceptance OPEN, C10 open. F2-04 local commit is
`c518a2a`. F2-09 was subsequently confirmed and its inventory increment is offline verified:
98 production packages, 3 browser packages, 429 scoped source/data/media files and 32
profile/tool declaration files; 36 new cases and full 1134 tests + 249 subtests PASS,
zero skips. See docs/50-engineering/license-provenance.md. Author/upstream and final
wheel/image notice reviews remain pending; F2-09 rights acceptance stays OPEN / BLOCKED.
F2-09 local commit is `fa1fa05`. F2-11 script/evidence was subsequently authorized:
one source walkthrough and a reusable bounded-review workflow, with historical materials
preserved unchanged and no project-content upload. Local source/link/inventory/manual OpenSpec checks PASS; source/claims/evidence remain
separate from runtime and commercial acceptance. No full test or live rehearsal this round. Commercial validation DEFERRED / NOT STARTED;
F2-09 rights pending (430 source records after adding the walkthrough), C10 OPEN.
F2-11 local commit is `8773639`. F2-08 citation time was subsequently authorized and is
implemented/offline verified: new epoch-derived citations use aware UTC; legacy naive
values retain unknown timezone semantics without migration. Five new Python tests plus
39 new subtests; full 1139 tests + 288 subtests PASS, zero skips; Node VM 48 cases PASS.
See docs/50-engineering/citation-time.md. F2-08 live/browser acceptance remains OPEN /
BLOCKED; F2-09 rights pending (431 source records), real runtime/full RAG BLOCKED, C10 OPEN.
F2-08 local commit is `39ea39c`. F2-05 data-flow/logging/external-privacy slice was then
confirmed and implemented/offline verified: 53 covered diagnostic calls omit business text,
manual traces use fixed names/typed metadata, and provider payload/retention gaps are explicit.
17 new cases; full 1156 tests + 391 subtests PASS, zero skips. See
`docs/50-engineering/data-privacy.md`. Private-data/provider/automatic-telemetry acceptance
remains BLOCKED; F2-05 OPEN, F2-09 rights pending (432 source records), C10 OPEN.
F2-05 local commit is `4247cdf`. F2-06 injection/negative controls were then confirmed:
eight separate synthetic cases and authored safe/unsafe outputs, with unchanged C17 corpus,
metrics and production prompts. 19 new tests/47 subtests; full 1175 tests + 438 subtests
PASS, zero skips; C17 29 cases PASS. See `docs/50-engineering/rag-safety-controls.md`.
Checker PASS is not model resistance; real adversarial/semantic/full RAG acceptance BLOCKED,
F2-05 privacy and F2-09 rights pending (436 source records), C10 OPEN.
F2-06 local commit is `182c252`. F2-07 keyboard/names/status slice was then confirmed:
native controls/labels, composition-safe Enter, visible/owned focus and bounded lifecycle
announcements implemented/offline verified. 21 new Node cases (69 total), 8 new Python
cases/46 subtests; full 1183 tests + 484 subtests PASS, zero skips. Credential VM 14 and
seven browser assets PASS. See `docs/50-engineering/keyboard-accessibility.md`.
Real browser/reader/zoom/contrast/runtime/full RAG acceptance stays BLOCKED; F2-07 OPEN,
F2-05 privacy and F2-09 rights pending (437 source records), C10 OPEN.
F2-07 local commit is `f3a7c2e`. F2-10 current offline-entry/CI prerequisite was then
confirmed: explicit eight-check current inventory, 330 reviewed backend/workflow inputs,
tracked retained full-pytest helper and shared CI command; historical C24 remains frozen.
35 new counterexamples; full 1218 tests + 484 subtests PASS, zero skips/xfails/deselections/
guard denials; Node 69/14 and seven assets PASS. See `docs/50-engineering/offline-verification.md`.
No remote CI, image or live execution; runtime/full RAG BLOCKED, F2-05 privacy and F2-09
rights pending (438 source records), C10 OPEN. CI-mode exit success is scoped offline only.
F2-10 local commit is `c5240ad`. F2-05 automatic telemetry admission was subsequently
confirmed on 2026-10-21: plan first, default-disabled inherited/effective configuration,
package/API/worker/factory guards, explicit synthetic OTEL and fixed failure handling.
84 new cases; full 1302 tests + 484 subtests PASS, zero skips/xfails/deselections/guard
denials; eight checks/Node 69/14/seven assets PASS, 332 reviewed inputs and 439 pending
source records. See `docs/50-engineering/telemetry-admission.md`. C21 audit/metrics retained;
optional exporter/client instrumentors absent/not added, explicit SDK unavailability
fails closed. Actual telemetry/privacy/runtime/full RAG remain BLOCKED, F2-09 rights
pending, C10 OPEN. F2-05 telemetry local commit is `8e30338`. The subsequently confirmed
F2-06 read-only RAG production boundary is implemented/offline verified after plan-first:
effective default/active/A-B policy, JSON input roles, tool/citation rejection, hidden draft
events and deterministic knowledge composition. 53 new cases; full 1355 tests + 484 subtests
PASS, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets
PASS, 334 reviewed inputs and 440 pending source records. See
`docs/50-engineering/rag-trust-boundary.md`. C17 data/evaluator/denominators and current
registry/tool authority remain unchanged; source IDs stay server-side. Other agent prompt
boundaries and real semantic/model/privacy/runtime/full RAG remain unaccepted, F2-09
pending, C10 OPEN. That increment stopped after the reviewed local RAG boundary commit `8edaf00` and final-candidate
receipt; no push/upload, new dependency, main-spec sync, archive or automatic next item. Offline
evidence is not live Redis/proxy/database acceptance or independent certification.


The separately confirmed F2-06 Planner/tool-selection increment (2026-10-22) after
`8edaf00` is implemented/offline verified after plan-first: effective prompt policy/JSON
roles, strict text/complete proposals, literal current-request action excerpts checked
before execution, no keyword-created recipients/IDs and hidden planning candidate streams.
61 new cases; full 1416 tests + 497 subtests PASS, zero skips/xfails/deselections/guard
denials; eight checks/Node 69/14/seven assets PASS, 336 reviewed inputs and 441 pending
source records. See `docs/50-engineering/planner-tool-trust-boundary.md`. C17 bytes and
denominators, current-identity gateway/RBAC/approval/idempotency/Saga authority retained.
Schema-valid wrong-identifier proposals are an explicit semantic gap; other agent prompts
and actual model/tool/privacy/runtime/full RAG remain unaccepted/BLOCKED, F2-09 pending,
C10 OPEN. Strict OpenSpec CLI unavailable/BLOCKED. Local review/commit and final candidate
receipt only, then wait. No push/upload, dependency, main-spec sync, archive or next item.


The subsequently confirmed F2-06 non-knowledge result facts/publication increment after
local `c0ca3b5` is implemented/offline verified after plan-first: deterministic structured
statuses/literal quoted action data, no summary model/draft, all failures retained and
existing single/knowledge/analysis/C10/SSE contracts preserved. 49 new cases; full 1465
tests + 495 subtests PASS, zero skips/xfails/deselections/guard denials; two removed summary
logging expressions explain two fewer diagnostic subtests (82 to 80), with no weaker gate.
Eight checks/Node 69/14/seven assets PASS, 338 inputs/442 pending sources; C17 29 and five
bundled-parser cases/two unsafe controls PASS. See `docs/50-engineering/nonknowledge-result-boundary.md`.
Statuses describe supplied snapshots, not fresh provider truth; missing single-call/Saga
evidence stays unverified. Chitchat/reranking deferred; real semantic/tool/privacy/runtime/
full RAG and strict CLI BLOCKED, F2-09 pending, C10 OPEN. Stop after reviewed local commit
and final clean-candidate receipt; no push/upload, dependency, C17 change, main-spec sync,
archive or automatic next item. Wait for confirmation.


The subsequently confirmed F2-06 chitchat fallback boundary after local `d5e028c` is
implemented/offline verified after plan-first: fixed read-only System/message JSON,
no username interpolation, strict 120-character text/native-call admission and fixed
failure fallback. Budget/cancellation propagate; candidate drafts stay hidden and valid
replies are labeled literal chat data. 57 new cases; full 1522 tests + 494 subtests PASS,
zero skips/xfails/deselections/guard denials; one obsolete length-log expression explains
one fewer automatic subtest (80 to 79), no weaker gate. Eight checks/Node 69/14/seven
assets PASS, 340 inputs/443 pending sources; C17 29 and five parser cases/two unsafe
controls PASS. See `docs/50-engineering/chitchat-trust-boundary.md`. Non-chitchat aggregate
AST/authority/C17 retained. Short false claims remain mechanically admissible, never
execution receipts; confidence remains heuristic. Optional reranking deferred; actual
model/browser/API/privacy/runtime/full RAG and strict CLI BLOCKED, F2-09 pending, C10 OPEN.
Stop after reviewed local commit/final clean-candidate receipt; no push/upload, dependency,
C17 change, main-spec sync, archive or automatic next item. Wait for confirmation.

The subsequently confirmed F2-06 optional LLM rerank increment after local `5bbf68b`
is implemented/offline verified after plan-first: fixed policy over effective templates,
query/prefix JSON, strict score-only/no-call admission, original candidate/ACL copies and
stable ties. Ordinary failures reject the complete batch for existing coarse/vector
fallback; budget/cancel propagate and score candidates stay hidden. 85 new tests/3 subtests;
full 1607 tests + 497 subtests PASS, zero skips/xfails/deselections/guard denials; eight
checks/Node 69/14/seven assets PASS, 342 inputs/444 pending sources, C17 29 PASS. See
`docs/50-engineering/llm-rerank-trust-boundary.md`. Initial inventory drift failed before
scoped registration, then full checks passed; existing authority assertions/79 diagnostics
retained. A valid poisoned high score is still a semantic gap. Default profile/factory/
Bailian/Cohere/BGE/C17 unchanged; Cohere/BGE follow-up deferred. Real model/event transport/
runtime/full RAG/privacy/strict CLI BLOCKED, F2-09 pending, C10 OPEN. Stop after reviewed
local commit/final receipt; no push/upload, dependency, main-spec sync, archive or next item.

The subsequently confirmed F2-06 Cohere/BGE result/numerical increment after local
`22492ab` is implemented/offline verified after plan-first: strict complete index/score
and vector/cardinality/finite-real admission, stable sigmoid/ties and original-source/ACL
copies. Ordinary failures reject whole batches for existing coarse/vector fallback;
budget/cancel propagate. 108 new tests/10 subtests; full 1715 tests + 507 subtests PASS,
zero skips/xfails/deselections/guard denials, C17 29 PASS. Eight current offline checks/Node 69/14/seven assets PASS;
344 reviewed inputs/445 pending sources. See `docs/50-engineering/optional-rerank-result-boundary.md`.
C07 NumPy ndarray fixture retains all authority assertions; diagnostics remain 79.
Bailian/LLM/factory/constructors/C17 unchanged; factory/stage follow-up deferred. No SDK/ML
install/download or real model use. Actual SDK/model/semantic/runtime/full RAG/privacy/
strict CLI BLOCKED, F2-09 pending, C10 OPEN. Stop after reviewed local commit/final receipt;
no push/upload, dependency, C17 change, main-spec sync, archive or automatic next item.

F2-06 factory selection/status increment (2026-10-22), after local `cf43c96`, is
implemented/offline verified after plan-first. Known providers/current auto mapping,
profile/configuration-bound cache admission and initialization interruption propagation;
fixed internal selection reasons and truthful retrieval/log/trace stages. All five rerank
methods, degradation route and C17 corpus/evaluator/categories/denominators unchanged.
68 new tests/8 subtests; full 1783 tests + 510 subtests PASS, zero skips/xfails/deselections/
guard denials; five consolidated log expressions explain five fewer automatic diagnostic
subtests (79 to 74), no weaker gate. Eight current offline checks/Node 69/14/seven assets
PASS, 345 reviewed inputs/446 pending sources; separate C17 29 PASS. See
`docs/50-engineering/reranker-selection.md`. Two isolated fixtures only gain the metadata
type; initial inventory/AST-fixture failures fixed without skipping or assertion changes.
Real SDK/model/semantic/runtime/full RAG/privacy/strict CLI BLOCKED, F2-09 pending, C10 OPEN.
Stop after reviewed local commit/final-candidate receipt; no dependency/service, push/upload,
main-spec sync, release, archive or automatic next item. Wait for confirmation.

The subsequently confirmed F2-06 score-admission increment (2026-10-22), after local
`fd5511c`, is implemented/offline verified after plan-first. Stdlib finite-real admission
at raw store, visible retrieval/degradation, knowledge and confidence boundaries; no
NaN/Infinity/bool/text promotion to high confidence. Numeric failures cannot become empty
success; ordinary source/optional-rerank fallback remains. Accepted finite processing,
original arithmetic/.6 weight/thresholds, scorer/factory/profile/prompts and C17 unchanged.
100 new tests/25 subtests; full 1883 tests + 535 subtests PASS, zero skips/xfails/deselections/
guard denials; eight checks/Node 69/14/seven assets PASS, 347 inputs/447 pending sources;
C17 29 PASS. All old test files/assertions and 74 diagnostic subtests retained. See
`docs/50-engineering/score-admission.md`. Real SDK/model/semantic/runtime/full RAG/privacy/
strict CLI BLOCKED, F2-09 rights pending, C10 OPEN. Stop after reviewed local commit/final
receipt; no dependency/service, push/upload, main-spec sync, release, archive or next item.
Wait for confirmation.

The subsequently confirmed F2-09 backend/C17 provenance-preparation increment
(2026-10-22), after local `6f5bbd9`, is documentation only, with its plan recorded before
the worksheet in `docs/50-engineering/license-provenance.md`. Exactly nine samples and
two suites have complete path/hash bindings, objective local observations, item/common
questions and an unanswered response form. No author declaration or rights clearance is
inferred; all 447 source records remain PENDING_SOURCE_REVIEW. Code/corpus/inventory/
admission rules and C17 primary 122/supplemental 6 remain unchanged. Documentation checks
only; no fresh pytest/runtime receipt. Strict CLI/runtime/full RAG/privacy remain BLOCKED,
F2-09 and C10 OPEN. Reviewed local documentation commit, then wait; no push/upload,
external lookup, main-spec sync, merge, release, archive or automatic next item.

The subsequently confirmed F2-09 unknown-source response increment (2026-10-22), after
local `7fad067`, records all eleven item-specific maintainer replies as received with
creation process/reference sources not presently recalled (unknown). Plan precedes the
response ledger in `docs/50-engineering/license-provenance.md`. Current worksheet/trackers
are updated; prior preparation evidence and blank template remain historical. Supporting
provenance/permission/real-data evidence stays unestablished; all 447 rights remain pending.
No code/corpus/inventory/admission-rule/rights or C17 122/6 changes. Documentation-only
checks/review/local commit, then wait; no fresh pytest/runtime receipt. Strict CLI/runtime/
full RAG/privacy BLOCKED, F2-09/C10 OPEN. No push/upload, remote CI, main-spec sync, merge,
release, archive or automatic next item.

The subsequently confirmed F2-11 current-candidate claim alignment (2026-10-22), after
local `ccd3065`, updates the existing source walkthrough with current N01–N09 references
and preserves its complete fa1fa05 body. Plan precedes edits in
`docs/50-engineering/portfolio-demonstration.md`. Retained 1883 tests/535 subtests and
eight-check PASS belong to 6f5bbd9 with overall BLOCKED; no fresh suite/demo is claimed.
Only the walkthrough pending-source SHA-256 and dependent current-manifest inventory hash
are refreshed; counts/rules/rights/app/tests/C17/CI and old assets remain unchanged.
All 447 source rights pending, eleven replies received/unknown; strict CLI/runtime/full
RAG/privacy BLOCKED, C10 OPEN. F2-11 feedback unvalidated, commercial validation DEFERRED.
Review/local commit then wait; no push/upload, remote CI, main-spec sync, merge, release,
archive or automatic next item.

The confirmed F2-10 current-candidate reverification increment (2026-10-22), after local
`4570a08`, records its plan in `docs/50-engineering/offline-verification.md` before
execution. Review/commit the plan locally, run the unchanged eight checks on that clean
commit, then make a separate receipt-bound documentation-only results commit. No skips,
changed counts/gates, source refresh or new dependency; missing tools stay BLOCKED.
Actual clean tested plan commit `cd34550`: all eight checks PASS, full 1883 tests + 535
subtests, Node 69/14/seven assets; zero skips/xfails/deselections/guard denials. Receipt
commit/content/source/aggregate and child hashes verified, 347 inputs/447 pending rights
and C17 unchanged; execution/binding PASS, overall BLOCKED/UAT-release false (exit 2).
The later result commit is documentation only, not the tested revision. Receipt/immutability/
tracking review, 307 local links and YAML/manual scoped OpenSpec PASS; reviewed result
commit locally, then wait. Unknown-source rights pending;
runtime/full RAG/privacy/strict CLI BLOCKED, C10 OPEN. Stop after local result commit;
no push/upload, remote CI, main-spec sync, merge/release, archive or automatic next item.

The confirmed F2-10 handover/history-label unit (2026-10-22), after local `2ed1d93`,
records its plan before organization in `docs/50-engineering/delivery-status.md`.
Use that document's `current-handover` anchor for current progress; baseline/C10 and
ROADMAP dated snapshots retain original wording/counts. Exactly fourteen existing blocked
gates are routed by missing decisions/tools/environment evidence, without status changes.
Retained tests belong to `cd34550`, results to `2ed1d93`; no full rerun/new receipt or
code/manifests/C17/rights/old-asset changes. Historical/protected-source/receipt review,
339 local targets/47 fragments, both YAML documents and manual scoped OpenSpec/whitespace
PASS; 347 reviewed inputs/447 pending rights unchanged.
Strict CLI/runtime/full RAG/privacy BLOCKED, unknown rights PENDING, C10 OPEN; F4/commercial
tracks remain unstarted/deferred. Reviewed local commit then wait; no push/upload,
remote CI, install, main-spec sync, merge/release, archive or automatic next item.

## 目录结构

- `enterprise-agent/`：FastAPI 后端主工程，包含 `app/`（API、Agent、Graph、
  RAG、工具、安全、可观测性）、`eval/`（W2-W9 评测脚本）、`deploy/`（部署配置）、
  `README.md`
- `docs/`：统一文档体系，按六大层分类（产品方案 / 产品文档 / 操作手册 /
  过程记录 / 工程文档 / 知识数据库 + 归档层），每层有 README 索引
- `interview/`：面试与演示资产独立体系（面试备稿 + 产品介绍网页）
- `openspec/`：openspec 变更与主规格（需求演进规范化）
- 根目录保留：`README.md`（导航入口）、`contents.md`（目录索引）、
  `CHANGELOG.md`（版本变更）、`启动智多星.bat`（一键启动）

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
- 版本管理：项目版本单一事实源为 `enterprise-agent/app/__init__.py` 的 `__version__`（语义化版本）；升级时同步 `pyproject.toml`、`CHANGELOG.md`、核心文档版本头并打 Git tag `vX.Y.Z`。

## openspec 管控

- 需求与文档演进一律走 openspec 生命周期：explore → propose → apply → archive，
  流程规则单一事实源为 `openspec/specs/openspec-normalization/spec.md`。
- AI 工具集成：Kimi Code（`.kimi-code/skills/`）与 Codex（`.codex/skills/`）均已
  由 `openspec init` 生成 6 个工作流 skill；CLI 升级后用 `openspec update` 刷新。
- 主规格 15 项见 `openspec/specs/`（2026-10-17）；新需求在 `openspec/changes/` 下开启 change。
- 当前工程收尾 change 为 `engineering-delivery-closeout`：S0/C24 前置已完成并推送；C01 配置独立提交 `2a9c364` 已推送，运行验收 BLOCKED；C02 外部模型增量 `42bfc7f` 已推送，真实 API/Linux 验收 BLOCKED；C03 增量 `fc8da91` 已推送，真实 PostgreSQL/API/Linux 验收 BLOCKED；C04 会话归属增量 `dbc8236` 已推送，真实 HTTP/PG 验收 BLOCKED；C05 增量 `9f5397c` 已推送；C06 `6955133` 已推送；C07 `ceae708` 已推送；C08 `d81c281` 已推送；C09 `079cd62` 已推送；C10 `a57bd4e` 已推送（此前 27 项专项 + 139 项相关回归 PASS），真实双进程/Redis/LangGraph/Milvus/JWT/API/SSE/PG/Linux 验收 BLOCKED，浏览器/SSO 与历史凭证处置阻塞保留；2026-10-19 C10 已实现每次运行独立 checkpoint 线程、数据库时钟写所有权、同事务指针/终态/token 发布；新增 28 项离线验证与本地完整 pytest 900 tests + 232 subtests（零跳过）PASS。schema v8 仅声明未执行；真实双进程/运行/完整 RAG 仍 BLOCKED，C10 整项 open；本轮审阅后本地提交，不推送、合并、发布或归档。C18 参考契约前置 `317aa7f` 已推送；C12 `21b5287` 已推送；C14 `59a5c14` 已推送；C13 `c42dcf8` 已推送；C11 `8bb6241` 已推送；C15 `0c0c5f9` 已推送；C16 `bb81833` 已推送；C17 `cd49d78` 已推送；C18 `bd04a12` 已推送并核验；C19 `4afe54b` 已推送并核验同名远端；C20 `44bfcb0` 已推送并核验同名远端；C21 `40c10d8` 已推送并核验同名远端；C22 计划先行/停写物理卷备份/新卷恢复/失败恢复源进程/回退与窗口核算离线候选完成（46 项专项 + 77 项相关回归 PASS，另 1 项 PyYAML 检查跳过）；D01–D16、O01–O16、B01–B16、S01–S16、R01–R20、真实运行与完整 RAG 验收 BLOCKED；C15/C16/C17/C18/C19/C20/C21/C22 整项 open，C10 写入竞态不关闭。C22 `d70c1b4` 已推送并核验；C23 冻结负载/混合采集/保守报告离线候选完成（42 项专项 + 186 项相关回归 PASS），L01–L16 运行验收 BLOCKED，C23 整项 open。C23 `6de94c6` 已按后续授权推送并核验；C24 最终候选离线增量完成（789 项测试 PASS、1 项 PyYAML 跳过/BLOCKED、7 个分发文件 PASS），C24 整项 open。C24 `d8a26b5` 已推送并核验；C25 离线 Git/双语文档/版本/规格/交付结论核对完成，整项 open。C25 `fe2ae78` 已推送并核验；该远端 CI 仍为 `_redact_url` 收集 FAIL。后续 CI 修复 `b8c4457` 已推送；远端 Python 3.11/3.13 各 871 tests + 225 subtests PASS、零跳过。Gitleaks 命中 16 个已核验源码哈希误报；精确历史指纹与完整事件范围扫描修复 `16c882b` 已推送，镜像上下文修复 `0d1a7ce` 已推送，远端 CI 39209313444 全部 PASS（双版本各 872 tests + 225 subtests、零跳过；密钥/依赖扫描、镜像构建/导入/Trivy PASS）。真实运行/完整 RAG 仍 BLOCKED，C10 open。详见 `docs/40-process/ci-pytest-repair.md`；不合并、发布、同步或归档。顺序以 ROADMAP 为准，验收以 ISSUES C01–C25 为准。真实企业接入与 UAT/灰度两个 change 保持独立，不以参考环境通过替代。
- Current-candidate offline coverage uses `python -I -B enterprise-agent/scripts/offline_verify.py` (plan-only); `--execute --record FRESH_ID` runs reviewed local checks, and `--ci` permits scoped success only on complete clean/stable evidence. See `docs/50-engineering/offline-verification.md` for retained writes and blocked acceptance. Historical C24 runner/manifest remain frozen; do not auto-refresh them. No command installs dependencies or authorizes runtime/remote work.
- 离线前置核验使用 `python3 -I -B enterprise-agent/scripts/safe_validate.py`（仓库根目录）；默认只输出摘要，exit 2 可表示真实 UAT/发布仍阻塞，不等于入口失败。副作用范围见 `docs/50-engineering/safe-validation.md`；其他脚本不得自动视为已通过安全审查。

## 关键文档

- [enterprise-agent/README.md](enterprise-agent/README.md)
- [contents.md](contents.md)（全仓库目录树索引）
- [docs/20-product/产品文档.md](docs/20-product/产品文档.md)
- [docs/30-guides/运维维护手册.md](docs/30-guides/运维维护手册.md)
- [docs/30-guides/产品使用手册-前端版.md](docs/30-guides/产品使用手册-前端版.md)
- [docs/30-guides/使用案例手册.md](docs/30-guides/使用案例手册.md)
- [docs/40-process/ROADMAP.md](docs/40-process/ROADMAP.md)（里程碑规划）
- [docs/40-process/ISSUES.md](docs/40-process/ISSUES.md)（问题与坑记录）
- [docs/40-process/DECISIONS.md](docs/40-process/DECISIONS.md)（设计决策记录）
