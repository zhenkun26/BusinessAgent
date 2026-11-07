# ROADMAP · 里程碑规划

> 进度规划的单一事实源。与 README、openspec change 状态保持一致。
> 更新日期:2026-10-22
> 当前主线：面向 GitHub 开源展示与后端求职，暂无实际客户部署/商业运营计划，沿用真实项目工程流程。C10-R1/R2 已按确认先规划再修复，25 项专项及完整本地 pytest 925 tests + 249 subtests PASS、零跳过；仅本地提交。F2 十二视角定向审核已完成（单代理模拟，候选 `c57d473`）；十一项发现已登记；F2-01 经确认后修复，30 项新增用例与全量 955 tests + 249 subtests PASS、零跳过；F2-02 经确认后完成离线修复，全量 973 tests + 249 subtests PASS；F2-03 执行预算经确认后完成离线增量，全量 1007 tests + 249 subtests PASS；SSE 背压随后经确认完成离线实现，新增 41 项用例，全量 1048 tests + 249 subtests PASS、零跳过；F2-03 运行验收仍 open/BLOCKED。F2-04 随后经确认完成生产构建输入与安装清单核验的离线实现，50 项新增用例，全量 1098 tests + 249 subtests PASS、零跳过；真实重建/扫描验收 BLOCKED。C10 open，真实运行/完整 RAG BLOCKED。
> 先前实施与 CI 记录（保留历史）：C01–C23 离线增量均已推送；C23 同名远端已核验为 `6de94c6`。C24 最终候选离线回归完成（789 项测试 PASS、1 项 PyYAML 跳过/BLOCKED、7 个分发文件 PASS），整项 open；C24 `d8a26b5` 已推送；C25 `fe2ae78` 已推送并核验；其远端 CI 收集 FAIL。后续修复 `b8c4457` 已推送，远端 Python 3.11/3.13 各 871 tests + 225 subtests PASS、零跳过；扫描误报与事件范围修复 `16c882b` 已推送，镜像上下文修复 `0d1a7ce` 已推送，远端 CI 39209313444 全部 PASS（双版本各 872 tests + 225 subtests、零跳过；密钥/依赖扫描、镜像构建/导入/Trivy PASS）。L/D/O/B/S/R、真实运行、完整 RAG 与历史凭证验收继续 BLOCKED；C10 运行隔离与条件发布已完成离线实现，真实租约到期写入竞态验收仍 BLOCKED，整项 open；28 项新增离线测试与本地全量 pytest 900 tests + 232 subtests、零跳过 PASS。本轮仅本地提交，等待确认。各项历史提交与验证记录见下方索引和 ISSUES。

Previous confirmed increment: F2-10 [current offline entry and CI coverage](../50-engineering/offline-verification.md), after local F2-07 `f3a7c2e`. Eight fixed checks/330 reviewed inputs, tracked retained pytest and aligned CI recipe are offline verified: 35 new counterexamples; full 1218 tests + 484 subtests PASS, zero skips/xfails/deselections/guard denials; Node 69/14, seven assets. Historical C24 stays frozen. Real runtime/full RAG and remote CI remain BLOCKED; F2-05 privacy and F2-09 sources pending, C10 OPEN. Local commit only, no push/upload/dispatch, then wait.

<a id="engineering-closeout-stages"></a>
Latest confirmed increment (2026-10-22): F2-10 [current handover entry/historical labels](../50-engineering/delivery-status.md#current-handover)
after local `2ed1d93`. Plan first in the existing delivery document; organize current versus
dated snapshots and exactly fourteen existing blocked-gate prerequisite/evidence routes.
Retain historical commits/counts/receipts, tested `cd34550` and result-documentation
`2ed1d93`; no new suite/run/receipt, code/manifests/C17/rights or old-asset changes.
History/protected-source/receipt review, 339 local targets/47 fragments and YAML/manual
scoped OpenSpec/whitespace PASS; no new full run. Strict CLI/runtime/full RAG/privacy BLOCKED,
unknown rights PENDING, C10 OPEN; F4/commercial tracks do not start. Reviewed local commit
then wait, no push/upload, remote CI, main-spec sync, merge/release, archive or next item.

Previous confirmed increment (2026-10-22): F2-10 [current-candidate reverification](../50-engineering/offline-verification.md#current-candidate-reverification)
after local `4570a08`. Plan first, reviewed local plan commit, unchanged eight-check run
on that clean candidate, then receipt-bound documentation-only results commit. No count/
gate/hash changes or skipped tests. Actual clean tested plan commit `cd34550`: eight
checks PASS, full 1883 tests + 535 subtests, Node 69/14/seven assets; zero skips/xfails/
deselections/guard denials. Tested content/source/receipt hashes verified; 347 inputs,
447 pending rights and C17 unchanged. Execution/binding PASS, overall BLOCKED/UAT-release
false (exit 2). Receipt/immutability/tracking review, 307 local links and YAML/manual
scoped OpenSpec PASS; reviewed documentation-only result commit locally, then wait.
Missing strict CLI stays BLOCKED; unknown-source rights pending, runtime/full RAG/privacy
BLOCKED, C10 OPEN. Local commits only, then wait; no push/upload, remote CI or next item.

Previous confirmed increment (2026-10-22): F2-11 [current-candidate source claims](../../interview/portfolio-walkthrough.md#current-candidate)
after local `ccd3065`; [plan and review](../50-engineering/portfolio-demonstration.md#current-claim-alignment).
Current N01–N09 source/evidence references are separate from the fully preserved fa1fa05
body and historical CI. Retained 1883 tests/535 subtests and eight-check PASS belong to
`6f5bbd9`, with overall BLOCKED; no fresh suite/demo is claimed. Only the existing
walkthrough and its two dependent evidence-hash fields plus documentation/OpenSpec change;
all 447 source rights, rules, code/tests/C17 and old assets remain unchanged. Scoped source/
receipt/history/hash/provenance checks, 449 links/47 anchors and YAML/manual OpenSpec PASS.
Local commit then wait, no push/upload, remote CI, main-spec sync or archive. Runtime/full RAG/
privacy/strict CLI BLOCKED, C10 OPEN; feedback unvalidated, commercial validation DEFERRED.

Previous confirmed increment (2026-10-22): F2-09 [eleven unknown-source responses](../50-engineering/license-provenance.md#backend-c17-unknown-source-responses)
after local `7fad067`. Plan first, then record all eleven item-specific replies as received:
creation process/reference sources cannot presently be recalled and remain unknown.
Update current worksheet/trackers; retain earlier preparation evidence and the blank
template as historical. Supporting provenance/real-data/permission evidence remains
unestablished; all 447 source rights stay PENDING_SOURCE_REVIEW. Code/corpus/inventory/
rules and C17 122/6 are unchanged. Hash/scope/C17/pending-state checks, 350 local links/
10 worksheet anchors, YAML/manual scoped OpenSpec and whitespace PASS. Local commit then wait;
strict CLI/runtime/full RAG/privacy BLOCKED, F2-09/C10 OPEN. No push/upload, remote CI,
main-spec sync, archive or automatic next item.

Previous confirmed increment (2026-10-22): F2-09 [backend/C17 source-confirmation preparation](../50-engineering/license-provenance.md#backend-c17-confirmation-worksheet)
after local `6f5bbd9`. Plan first; eleven path/hash-bound worksheet items cover exactly
nine sample documents and the two separate evaluation sets. Objective repository facts,
unanswered author questions and rights acceptance remain distinct. At preparation, all
eleven replies were NOT PROVIDED; all 447 registered source rights remained PENDING_SOURCE_REVIEW.
C17 primary 122/supplemental 6, categories/metrics and source/code/inventory/rules unchanged.
Binding/immutability review, 346 local links, YAML/manual scoped OpenSpec and whitespace
checks PASS; reviewed local commit only, no new pytest/runtime receipt or external action.
Runtime/full RAG/privacy/strict CLI BLOCKED, F2-09 and C10 OPEN; wait for
confirmation without push/upload, main-spec sync, archive or automatic next item.

Previous confirmed increment (2026-10-22): F2-06 [score admission](../50-engineering/score-admission.md)
after local `fd5511c`. Plan-first finite-real admission before raw score conversion/clipping,
model use and confidence; numeric errors remain failures through the selector. Ordinary
fallback, accepted finite processing/.6 weight/thresholds and C17 unchanged. 100 new tests/
25 subtests; full 1883 tests + 535 subtests PASS, zero skips/xfails/deselections/guard denials.
Eight checks/Node 69/14/seven assets PASS, 347 inputs/447 pending sources; C17 29 PASS.
Old tests/assertions and 74 diagnostic subtests retained. Runtime/full RAG/privacy/strict CLI
BLOCKED, F2-09 pending, C10 OPEN. Reviewed local commit/final receipt then wait; no push/
upload, dependency, real service, main-spec sync, archive or automatic next item.

Previous confirmed increment (2026-10-22): F2-06 [factory selection and status](../50-engineering/reranker-selection.md)
after local `cf43c96`. Plan-first provider/auto admission, profile/configuration-bound cache,
cooperative initialization interrupts and explicit internal fallback reasons; truthful
retrieval/log/trace stages. Five scorer methods, degradation route and C17 unchanged.
68 new tests/8 subtests; full 1783 tests + 510 subtests PASS, zero skips/xfails/deselections/
guard denials; five fewer automatic logging subtests follow consolidated code, no weaker
gate. Eight checks/Node 69/14/seven assets PASS, 345 inputs/446 pending sources; C17 29 PASS.
Runtime/full RAG/privacy/strict CLI BLOCKED, F2-09 pending, C10 OPEN. Reviewed local commit/
final receipt then wait; no push/upload, dependency, main-spec sync, archive or next item.

Previous confirmed increment (2026-10-22): F2-06 [optional Cohere/BGE result boundary](../50-engineering/optional-rerank-result-boundary.md)
after local `22492ab`. Plan-first strict input/complete index-score/vector admission,
finite scalar checks and stable sigmoid/ties; original content/ACL copies, whole-batch
failure and cooperative interruption checks. 108 new tests/10 subtests; full 1715 tests
+ 507 subtests PASS, zero skips/xfails/deselections/guard denials; C17 29 PASS. Eight
current offline checks/Node 69/14/seven assets PASS; 344 reviewed inputs/445 pending sources. Factory/stage follow-up
is deferred; Bailian/LLM/factory/constructors/C17 unchanged. Real SDK/model/runtime/full
RAG/privacy/strict CLI BLOCKED, F2-09 pending, C10 OPEN. Reviewed local commit/final
receipt only, then wait; no push/upload, dependency/install/download or automatic next item.

Previous confirmed increment (2026-10-22): F2-06 [optional LLM rerank boundary](../50-engineering/llm-rerank-trust-boundary.md)
after local `5bbf68b`. Plan-first fixed policy over effective templates, query/text JSON,
strict bounded ASCII score/no-call admission, original source/ACL copies and stable ties.
Any ordinary failure rejects the whole batch for existing coarse/vector fallback;
budget/cancel propagate and raw score candidates stay hidden. 85 new tests/3 subtests;
full 1607 tests + 497 subtests PASS, zero skips/xfails/deselections/guard denials. Eight
checks/Node 69/14/seven assets PASS, 342 inputs/444 pending sources; C17 29 PASS. Valid
poisoned high scores remain a semantic gap; Bailian profile/factory/C17 unchanged,
Cohere/BGE deferred. Runtime/full RAG/privacy/strict CLI BLOCKED, F2-09 pending, C10 OPEN.
Reviewed local commit/final receipt only, then wait; no push/upload or automatic next item.

Previous confirmed increment (2026-10-22): F2-06 [chitchat fallback boundary](../50-engineering/chitchat-trust-boundary.md)
after local `d5e028c`. Plan-first fixed policy/message JSON without names, strict response
admission/fixed fallback, propagated budget/cancel and hidden/literal candidate output.
57 new cases; full 1522 tests + 494 subtests PASS, zero skips/xfails/deselections/guard
denials; one obsolete log-expression subtest removed with its code. Eight checks/Node
69/14/seven assets PASS, 340 inputs/443 pending sources; C17 29 and five parser cases/two
unsafe controls PASS. Optional reranking deferred, runtime/full RAG/privacy/strict CLI
BLOCKED, F2-09 pending, C10 OPEN. Local reviewed commit/final receipt only, then wait;
no push/upload/remote CI, main-spec sync, release, archive or automatic next item.

Previous confirmed increment (2026-10-22): F2-06 [non-knowledge result facts/publication](../50-engineering/nonknowledge-result-boundary.md)
after local `c0ca3b5`. Plan-first deterministic status/data composition replaces summary
model rewriting; retains failures/pending/compensation/unknown outcomes and existing
analysis/knowledge/single-result/C10/SSE contracts. 49 new cases; full 1465 tests + 495
subtests PASS, zero skips/xfails/deselections/guard denials. Eight checks/Node 69/14/seven
assets PASS, 338 inputs/442 pending sources; five bundled-parser cases/two unsafe controls
PASS. Chitchat/reranking deferred; runtime/full RAG/privacy/strict CLI BLOCKED, F2-09 pending,
C10 OPEN. Reviewed local commit/final receipt only, then wait; no external action/next item.

Previous confirmed increment (2026-10-22): F2-06 [Planner/tool trust boundary](../50-engineering/planner-tool-trust-boundary.md)
after local `8edaf00`. Plan-first implementation/offline review covers effective prompt
policy/data roles, request-bound action excerpts, strict complete tool proposals and no
guessed keyword defaults; raw planning streams stay hidden. 61 new cases; full 1416 tests
+ 497 subtests PASS, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/
seven assets PASS, 336 reviewed inputs and 441 pending source records. C17 unchanged;
semantic/model/tool/privacy/runtime/full RAG remain unaccepted, F2-09 pending, C10 OPEN.
Strict CLI unavailable/BLOCKED. Local commit and final candidate receipt only, then wait;
no push/upload/remote CI, merge, release, main-spec sync, archive or automatic next item.

Previous confirmed increment (2026-10-21): F2-06 [read-only RAG trust boundary](../50-engineering/rag-trust-boundary.md)
after local `8e30338`. Selected prompt/data roles, model call/citation guards, raw draft
suppression and citation-aware deterministic knowledge composition are offline verified:
53 new cases; full 1355 tests + 484 subtests, zero skips/xfails/deselections/guard denials;
eight checks/Node 69/14/seven assets PASS, 334 inputs and 440 pending source records.
C17 corpus/denominators and tool authority retained. Semantic/model/other-agent prompt
boundaries, privacy/runtime/full RAG and remote CI remain unaccepted; F2-09 pending,
C10 OPEN. Reviewed local commit/final receipt only, then wait; no push/upload or next item.

Previous confirmed increment (2026-10-21): F2-05 [automatic telemetry admission](../50-engineering/telemetry-admission.md)
after local `c5240ad`. Default-disabled process/effective Settings and API/worker/factory
gates, explicit synthetic OTEL and fixed failures are offline verified: 84 new cases,
full 1302 tests + 484 subtests PASS, zero skips/xfails/deselections/guard denials. Eight
checks, Node 69/14, seven assets, 332 inputs and 439 pending source records PASS. C21
audit/metrics retained; absent optional exporter dependencies not added. Actual SDK/proxy/
provider/privacy/runtime/full RAG and remote CI remain BLOCKED, F2-09 rights pending,
C10 OPEN. Local review/commit only, then wait; no push/upload or automatic next item.

## 当前工程收尾：S0–S7

范围依据：[工程交付基线](../50-engineering/engineering-delivery-baseline.md)。逐项现状与验收唯一记录在 [ISSUES C01–C25](ISSUES.md#engineering-closeout)，任务勾选见 [OpenSpec tasks](../../openspec/changes/engineering-delivery-closeout/tasks.md)。

| 阶段 | 执行顺序 / 依赖 | 阶段出口 | 当前状态 |
| --- | --- | --- | --- |
| S0 冻结范围 | 交付基线、C01–C25、规格、决策与索引 | 文档结构/链接/范围检查；明确验证限制；暂停等待用户确认 | 用户已确认，`05d8d0c` 已推送；CLI 严格校验仍 BLOCKED |
| S1 可复现环境 | C24 安全验证入口前置 → C01 → C02 → C03 | 隔离环境能按文档启动同一候选产物、模型与数据库 | C24 前置完成；C01 配置已修，运行验收 BLOCKED；C02 离线实现已完成，真实 API/Linux 验收 BLOCKED；C03 离线增量 `fc8da91` 已推送，真实 PostgreSQL/Linux 验收 BLOCKED |
| S2 权限与敏感信息 | S1 后，C04 → C05 → C06 → C07 | 会话、身份、凭证、检索边界验收通过后，才进入受控业务写入 | C04 `dbc8236` 已推送；C05 `9f5397c` 已推送；C06 `6955133` 已推送；C07 `ceae708` 已推送，运行验收 BLOCKED；既有浏览器/SSO/历史处置阻塞保留；C08 见 S3 |
| S3 会话与运行状态 | S2 后，C08 → C09 → C10 | 上下文不串用，支持进程数与状态持久化声明符合实测 | C08 `d81c281` 已推送；C09 `079cd62` 已推送；C10 离线增量已完成，真实持久化/双进程/写入竞态验收 BLOCKED |
| S4 执行一致性与恢复 | S3 后，先 C18 参考契约前置，再 C12 → C14 → C13 → C11 | 幂等、队列、Saga 和审批竞争/崩溃验证通过 | C18/C12/C14/C13/C11 已推送；S4 真实运行 BLOCKED |
| S5 数据与参考集成 | S4 后，C15 → C16 → C17 → C18 完整链路 → C19 | 数据来源一致，质量指标透明，参考 HTTP/IdP 经应用入口通过 | C15–C19 已推送；整项 open；S01–S16/真实运行/完整 RAG/R01–R20 BLOCKED |
| S6 用户与运维 | S5 后，C20 → C21 → C22 → C23 | 人工流程、监控/审计、恢复、规定负载测试形成证据 | C20–C23 离线增量完成、整项 open；B/O/D/L 矩阵 BLOCKED；C23 `6de94c6` 已推送 |
| S7 最终候选 | C24 最终回归 → C25 记录收口 → 规格同步/归档检查 | 最终提交/镜像与证据一致，无范围内 P0/P1；严格校验通过 | C24 离线部分完成；完整验收 BLOCKED；C25 已推送；远端双版本各 871 tests PASS；扫描与镜像上下文修复 `0d1a7ce` 已推送，远端 CI 39209313444 全部 PASS（双版本各 872 tests + 225 subtests、零跳过；密钥/依赖扫描、镜像构建/导入/Trivy PASS）；整项 open，未同步/归档 |

本轮 C10 修复见[检查点阶段记录](阶段性总结_C10检查点持久化与故障语义.md#c10-stale-writer-repair--2026-10-19)，仅本地提交，schema v8 未执行。

此前 CI 修复记录：[完整测试与夹具修复](ci-pytest-repair.md)。

### Confirmed follow-up sequence (updated 2026-10-20)

Historical sequence snapshot: the rows below retain their original progress wording and
counts. Current increments are recorded above and in the current handover entry; partial
F2 preparation does not automatically start or complete the separate F4 readiness track.

| Order | Proposed increment | Entry / exit and current state |
| --- | --- | --- |
| F1 | C10-R1 citation parity and C10-R2 valid-history selection | Authorized and implemented after `c0a4464`; plan, fixes, 25 focused cases and complete local suite PASS. FIXED / OFFLINE VERIFIED; local commit only, live acceptance BLOCKED |
| F2 | Multi-expert review from deployment and commercial perspectives | COMPLETE after confirmation at `c57d473`; single-agent twelve-perspective scorecard, source evidence, eleven findings and Top 3. Commercial demand remains PENDING; no runtime acceptance |
| F3 | Triage and bounded remediation | Eleven findings mapped to ISSUES/C items. F2-01 confirmed, FIXED / OFFLINE VERIFIED (30 new cases; full suite 955 tests + 249 subtests, zero skips). F2-02 subsequently confirmed and OFFLINE VERIFIED (18 new cases; full 973 tests + 249 subtests). F2-03 execution-budget slice subsequently confirmed and OFFLINE VERIFIED (34 new cases; full 1007 tests + 249 subtests). SSE subsequently confirmed and OFFLINE VERIFIED (41 new cases; full 1048 tests + 249 subtests). F2-03 runtime acceptance remains OPEN / BLOCKED. F2-04 subsequently confirmed and OFFLINE VERIFIED (50 new cases; full 1098 tests + 249 subtests), image/rebuild acceptance BLOCKED; local commit only, pause before another finding |
| F4 | Public portfolio readiness reconciliation | Honest demonstrations, claims, provenance/licenses, reproducibility and known limitations; no inferred permission to publish/push/merge/release. NOT STARTED |
| Separate evidence track | Current-candidate CI and isolated runtime matrices | Only after appropriate authorization/resources; no deployment or commercialization scheduled by this plan. C10/runtime/full RAG and existing matrices stay BLOCKED/open |

Report: [F2 audit at c57d473](multi-expert-review-c57d473.md).
Details: [committee protocol](../50-engineering/multi-expert-review-plan.md),
[decision 41](DECISIONS.md), [C10 findings](ISSUES.md#c10-r1).
This ordering supersedes any earlier implication that push or deployment follows the last
local commit automatically. Existing S0–S7 acceptance dependencies remain authoritative;
completion of F2 does not complete parent C items; the later confirmation authorized only
F2-01, followed by a separate F2-02 confirmation. Neither offline completion authorizes the
remaining fixes. F2-03 execution budgets were subsequently confirmed and delivered offline.
SSE backpressure was subsequently confirmed and delivered offline on 2026-10-20.
F2-04 reproducibility was separately confirmed and delivered offline (`c518a2a`). F2-09
was then confirmed: the [license/provenance inventory](../50-engineering/license-provenance.md)
and read-only checks are offline verified (36 new cases; full 1134 tests + 249 subtests,
zero skips). Author/upstream rights and final-distribution review remain OPEN / BLOCKED.
F2-11's script/evidence slice was then confirmed: one [source walkthrough](../../interview/portfolio-walkthrough.md)
and [reusable workflow](../50-engineering/portfolio-demonstration.md), with older materials
unchanged and no upload. The whole F2-11 finding remains OPEN; commercial validation is
DEFERRED / NOT STARTED. Its local commit is `8773639`. F2-08 was then separately confirmed: the citation-time/offline slice is implemented; real browser/runtime acceptance remains BLOCKED. F2-08 was committed locally as `39ea39c`. F2-05 was then confirmed: its data-flow/diagnostic slice is offline verified; private-data/provider/automatic-telemetry acceptance stays BLOCKED. F2-05 was committed locally as `4247cdf`. F2-06 was subsequently confirmed and its independent synthetic-control slice is offline verified; model resistance/semantic acceptance remains BLOCKED. F2-06 was committed locally as `182c252`. F2-07 keyboard/names/status was then confirmed and offline verified; actual browser/reader/layout/contrast acceptance remains BLOCKED. F2-07 was committed locally as `f3a7c2e`. F2-10 offline-entry/CI alignment was then confirmed and verified; runtime remains BLOCKED. Wait after the local F2-10 prerequisite commit before another unit. Private-data and runtime gates remain conditional on future use,
not silently waived. Detailed dependencies and effort ranges are in the report.

**执行规则**：阶段只是分组，每次仅推进用户确认的一个 C 项；完成后交付范围、检查、人工验收与限制，等待下一项确认。C24/C18/C25 的前置部分不计整项完成。若运行时契约变化，先补对应 delta/design 再实施。S0 授权不延伸为 S1 实施、安装依赖、推送、合并或部署授权。

真实企业集成、UAT、安全验收、四周灰度与签署继续由既有两个 active change 管理，不以参考服务替代。**C01 目标环境验收保持 BLOCKED**。C21 `40c10d8` 已按本轮授权推送并核验；C22 提供保留式备份恢复/回退离线候选，D01–D16 真实验收 BLOCKED，C22 整项 open。C22 `d70c1b4` 已推送并核验；C23 冻结负载、混合采集和报告离线候选完成，L01–L16 BLOCKED。C23 `6de94c6` 已推送；C24 `d8a26b5` 已推送并核验；C25 离线核对完成、整项 open，本地提交后暂停。C24 远端 CI pytest 收集失败（`_redact_url`），后续修复需另行确认。S1/S2/S3 运行出口与 C10 租约到期后的写入竞态仍未通过，C10 整项 open；本次不解除阻塞、不授权 S4 运行验收。

本轮验证、限制与交付状态见 [S0 阶段总结](阶段性总结_S0工程交付基线.md)。
C25 当前交付边界见 [交付状态](../50-engineering/delivery-status.md)及[阶段记录](阶段性总结_C25离线交付核对.md)。
C24 最终候选离线增量见 [交付记录](阶段性总结_C24最终候选离线验证.md)和[验收映射](../50-engineering/final-candidate-verification.md)。
前置记录见 [C24 前置阶段总结](阶段性总结_C24安全验证前置.md)；五函数核验不等于完整应用回归。
当前记录：[C01 配置交付](阶段性总结_C01部署产物与入口.md)、[C02 模型依赖与阻塞](阶段性总结_C02模型依赖.md)、[C03 迁移与初始化](阶段性总结_C03数据库迁移与初始化.md)、[C04 会话归属](阶段性总结_C04会话归属校验.md)、[C05 认证与运行时授权](阶段性总结_C05认证失败闭合与运行时授权.md)、[C06 凭证与 HTML 安全](阶段性总结_C06凭证与HTML失败安全.md)、[C07 检索权限](阶段性总结_C07检索权限与表达式编码.md)、[C08 请求上下文](阶段性总结_C08请求上下文与子任务依赖.md)、[C09 跨进程状态](阶段性总结_C09跨进程运行状态.md)、[C10 checkpoint](阶段性总结_C10检查点持久化与故障语义.md)、[C18 契约前置](阶段性总结_C18参考契约前置.md)、[C12 工具幂等](阶段性总结_C12工具幂等与安全重试.md)、[C14 队列与 worker](阶段性总结_C14队列可靠性与Worker初始化.md)、[C13 Saga 与补偿](阶段性总结_C13Saga持久化与故障恢复.md)、[C11 审批状态](阶段性总结_C11审批领取与执行状态.md)、[C15 知识发布](阶段性总结_C15知识发布与索引一致性.md)、[C16 分析适配](阶段性总结_C16分析数据适配.md)、[C17 RAG 指标](阶段性总结_C17RAG质量与指标口径.md)、[C18 完整参考 HTTP 候选](阶段性总结_C18完整参考HTTP业务集成.md)、[C19 受控 IdP](阶段性总结_C19受控IdP与SSO完整链路.md)、[C20 前端交付](阶段性总结_C20浏览器角色流程与前端交付.md)、[C21 可观测性](阶段性总结_C21就绪审计指标与告警.md)、[C22 保留式恢复](阶段性总结_C22当前版本备份恢复与回退.md)、[C23 容量证据](阶段性总结_C23规定负载下的性能与容量.md)。

## 一、已完成阶段（历史里程碑）

| 阶段 | 主题 | 状态 | 交付 |
|---|---|---|---|
| W2 | 基础设施 | ✅ | Docker 服务、本地 Embeddings(bge-m3)、配置体系 |
| W3 | RAG + KnowledgeAgent | ✅ | 两阶段检索、三级降级、置信度决策 |
| W4 | 评测体系 | ✅ | eval_set、run_eval、命中率/覆盖率指标 |
| W5 | 多 Agent 并行图 | ✅ | LangGraph Send fan-out、Planner→Executor→Aggregator |
| W6 | Checkpointer 断点恢复 | ✅ | Redis→PG→Memory 三级降级、跨进程恢复、interrupt |
| W7 | ExecutionAgent + 工具 | ✅ | 8 工具、RBAC、Prompt 注入防护、Saga 补偿 |
| W8 | API 层 + 安全 | ✅ | chat/auth/approval、JWT 刷新、批量审批、限流 |
| W9 | 生产化 | ✅ | compose.prod、OpenTelemetry、部署文档、Milvus 真实接入 |
| 整体联调 | 真实基础设施 E2E | ✅ | 17/17 通过，修复 4 个联调 bug |
| P1 | 分析/审批/审计/反馈 | ✅ | AnalysisAgent、审批流打通、审计 6 类事件、反馈循环 |
| P2 | 体验与验证补强 | ✅ | Prompt 版本管理、取消机制、命名空间隔离、sessions 梳理 |
| P2 后续 | 前端与流式 | ✅ | 单文件 SPA、SSE 流式、/metrics、前端 v2/v3、审批进度跟踪 |
| 生产对抗性审查 | 2026-08-04 | ✅ | 12 项漏洞修复、36 项测试、1000 并发 0 失败、生产镜像与 K8s 清单 |
| 业务闭环补全 | 2026-08-04 | ✅ | openspec complete-business-processes 41/41 完成并归档(v1.1.0) |
| 项目归档完结 | 2026-08-04 | ✅ | 两个 change 全部归档、主规格 10 项、v1.2.0 收口 |
| 生产就绪基线 | 2026-08-05 | ✅ | production-readiness-baseline 10/10 归档：边界/SLA/风险清单落规格、checkpoint TTL、token 用量统计、备份脚本 |
| RAG 答案质量 | 2026-08-05 | ✅ | rag-answer-quality 15/15 归档：评测集扩充、答案覆盖率指标与评测脚本 |
| 智能体更名 | 2026-08-06 | ✅ | rename-agent-to-zhiduoxing 7/7 归档：「小A」全量更名「智多星」 |
| 压测与容灾演练 | 2026-08-06 | ✅ | load-test-and-dr-drill 14/14 归档：k6 阶梯压测、备份恢复演练（实测 RTO/RPO）、告警规则与值班预案 |
| 安全加固 | 2026-08-06 | ✅ | security-hardening-plus 21/21 归档：gitleaks/pip-audit/Trivy 三道 CI 扫描、豁免清单、越权测试，主规格 13 项 |
| 工单真实接入试点 | 2026-08-06 | ✅ | ticket-system-integration 16/16 归档：幂等键/补偿真实化/审计回写，stub 沙箱验收 7/7（external-system-integration 规格扩展） |
| G0 UAT 技术彩排回放 | 2026-08-15 | ✅ | uat-replay-harness 9/9 归档：合成 fixture、结构/安全回放器、JSON/Markdown 证据报告 |
| 后端内部简化 | 2026-09-29 | ✅ 已合并并发布 | PR #1 合并为 `2d4bfc1`；Python 3.11/3.13 各 143 项测试通过；仅 FGR-01/FAT-01，OpenSpec 已归档；[交付证据](code-simplification/20260928-backend/cleanup-report.md) |
| CI 镜像发布门禁修复 | 2026-09-29 | ✅ 已合并并发布 | 先扫描后发布同一镜像；主分支 CI `36522224892` 全部通过，GHCR 提交标签与 latest 摘要一致；OpenSpec 已归档，未部署生产；[验证与授权范围](code-simplification/20260928-backend/ci-publication-report.md) |
| 交付收尾与 CI 必需检查 | 2026-09-29 | ✅ 必需检查生效，离线核验完成 | strict 模式绑定三个 GitHub Actions 检查；G0 16/16 通过、GATE-01 自动回归证据就绪；保持真实 UAT/联调/灰度阻塞；[推进记录](交付与离线推进记录-2026-09-29.md) |
| 中英文 README | 2026-10-17 | ✅ PR #3 已合并 | 合并提交 `065bdf7`；中文 README 与完整英文翻译、互链及目录索引；原文档检查见[变更与验证记录](../../openspec/changes/archive/2026-10-17-refresh-bilingual-readmes/tasks.md)，不代表运行验收 |

## 二、进行中

生产上线导向优化（2026-08-05 启动，候选依据见 `优化方向分析-生产上线-2026-08-05.md`）：

| openspec change | 优先级 | 状态 | 范围 |
| --- | --- | --- | --- |
| ~~production-readiness-baseline~~ | P0 | ✅ 已归档 2026-08-05 | 系统边界 / SLA / 风险操作清单落规格（新能力 production-readiness） |
| ~~rag-answer-quality~~ | P0 | ✅ 已归档 2026-08-05 | 评测集扩充 ≥100 条、答案覆盖率目标 ≥0.85（改 knowledge-operations） |
| ~~load-test-and-dr-drill~~ | P1 | ✅ 已归档 2026-08-06 | 阶梯压测 + 备份恢复演练 + 告警值班（新能力 performance-resilience） |
| ~~security-hardening-plus~~ | P1 | ✅ 已归档 2026-08-06 | 密钥管理、CI 漏洞扫描、越权测试、I-06/I-07 收口（新能力 security-operations） |
| ~~ticket-system-integration~~ | P2 | ✅ 已归档 2026-08-06 | 工单真实接入试点：幂等/补偿/审计/联调（改 external-system-integration） |
| ~~fix-vulnerable-runtime-dependencies~~ | P1 | ✅ 已归档，PR #3 已合并 | `492882c` 修复 4 个既有依赖，随 `065bdf7` 合入；既有 CI 证据及限制见[记录](../../openspec/changes/archive/2026-10-17-fix-vulnerable-runtime-dependencies/tasks.md)，不是新收尾基线的验收 |
| engineering-delivery-closeout | P0/P1 | C01 配置已修，运行验收阻塞 | S0/C24 前置已完成；25 项整项验收仍 open，C02 离线实现已完成，真实 API/Linux 验收 BLOCKED；C03 离线增量已推送；C04 `dbc8236` 已推送；C05 `9f5397c` 已推送；C06 `6955133` 已推送；C07 `ceae708` 已推送；C08 `d81c281` 已推送；C09 `079cd62` 已推送；C10 `a57bd4e` 已推送、运行验收 BLOCKED；C18/C12/C14/C13/C11 已推送；C15–C19 已推送；C20–C23 离线增量已推送；C24 离线汇总完成，全部运行矩阵 BLOCKED；C25 离线核对完成，整项 open，远端 CI FAIL |
| crm-mail-sso-integration | P2 | 实施中 9/19 | CRM/邮件/SSO 真实接入（配置、SSO 通用流程与文档已完成；外部契约/沙箱待确认） |
| uat-and-ga-rollout | P3 | 实施中 8/15 | UAT、灰度、上线门槛检查单（灰度方案条件评审通过，最短观察期 4 周；UAT 资源核验仍 BLOCKED） |
| ~~fix-prod-image-pip-removal~~ | P1 | ✅ 已归档 2026-08-15 | 修复生产镜像 runner 阶段 pip 清理顺序；CI run 31890705614 已通过 Python 3.11/3.13、生产镜像构建与 Trivy 扫描 |

## 三、挂起事项（P3，暂不上线）

工程收尾的当前执行顺序见本文件顶部 S0–S7；企业现场所需外部输入继续参考 `下一步执行阻塞清单-2026-09-29.md`。正式 UAT、真实外部接入、真实灰度和全量放行均不得跳过前置证据。

- [x] ~~压测（vegeta/k6）~~（✅ 2026-08-05 随 load-test-and-dr-drill 落地：k6 阶梯压测已执行，报告见 `eval/results/`，SLA 初值已回访，I-01 关闭）
- [ ] UAT + 安全测试（含 Prompt 注入攻击面实测）——已由 uat-and-ga-rollout 提案承接
- [x] ~~`needs_replan` 语义复查~~（✅ 2026-08-04 已随重规划闭环落地：知识无结果/部分覆盖/分析无数据按规格传播并触发回边补检 ≤2 轮）
- [ ] pymilvus 3.1 迁移（ORM API 弃用，已钉 `>=2.4,<3.1` 防误升级）
- [ ] Windows 开发体验：uvicorn reload 偶发卡死，需手动重启

## 四、远期规划（未排期）

- 多租户扩展（命名空间 → 租户隔离）
- TLS 全量开启、密钥管理深化（K8s 清单已就绪，CI 已接入 gitleaks/pip-audit/Trivy）
- 对话压缩（超长会话摘要，历史注入已落地）
- 子任务依赖编排（`SubTask.depends_on` 已定义未消费）
- `ROLE_NAMESPACES` 接入检索路径（manager 跨部门可见性）
- 长期记忆 `user_memories` 读写（表已建未接）
- token 成本报表（用量采集已落地，报表未做）
