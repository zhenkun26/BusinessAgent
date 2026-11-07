# Portfolio positioning and multi-expert review plan

Decision date: 2026-10-19. Updated 2026-10-20. Status: **F2 AUDIT COMPLETE; F2-01–F2-04 OFFLINE VERIFIED; IMAGE/RUNTIME BLOCKED**.
This document defines the reusable review protocol. The separate
[report for c57d473](../40-process/multi-expert-review-c57d473.md) records twelve simulated
perspectives, evidence-limited scores and eleven findings; it is not release approval.
Authority: [delivery baseline](engineering-delivery-baseline.md),
[ISSUES](../40-process/ISSUES.md#c10), [ROADMAP](../40-process/ROADMAP.md), and the active
`engineering-delivery-closeout` change. The initial plan was documentation-only; the separately
authorized C10-R1/R2 follow-up is now implemented/offline verified. F2 was subsequently
confirmed and completed without application changes. The subsequently confirmed F2-01
fix is [implemented/offline verified](runtime-authorization.md#f2-01-delivery-evidence--2026-10-19);
F2-02 was then confirmed and [offline verified](cross-process-state.md#f2-02-delivery-evidence--2026-10-19).
F2-03 execution budgets were subsequently confirmed and [offline verified](request-context.md#f2-03-delivery-evidence--2026-10-19).
SSE backpressure was separately confirmed and [offline verified](request-context.md#f2-03-sse-delivery-evidence--2026-10-20):
41 new cases, full suite 1048 tests + 249 subtests PASS, zero skips. F2-03 runtime acceptance
stays OPEN / BLOCKED. F2-04 was subsequently confirmed and implemented/offline verified:
50 new cases, full 1098 tests + 249 subtests PASS, zero skips; actual image/rebuild/security
acceptance stays BLOCKED. See [build evidence](../../enterprise-agent/deploy/DEPLOY.md#f2-04-offline-delivery-evidence--2026-10-20).
F2-09 was subsequently confirmed and its [inventory increment](license-provenance.md)
is offline verified: 36 new cases; full 1134 tests + 249 subtests PASS, zero skips.
Author/upstream provenance and actual distribution rights remain OPEN / BLOCKED.
F2-11's script/evidence slice was subsequently confirmed: one
[source walkthrough](../../interview/portfolio-walkthrough.md) and a
[reusable bounded-review workflow](portfolio-demonstration.md), with old materials unchanged
and no upload. Script preparation is not feedback, runtime or commercial validation;
commercial work is DEFERRED / NOT STARTED. Remaining work awaits confirmation.
F2-08 citation-time/offline regression was then separately confirmed and is implemented:
[contract and evidence](citation-time.md), full 1139 tests + 288 subtests and 48 Node VM
cases PASS. Legacy naive timestamps remain unzoned; no database migration. Browser/runtime
acceptance remains BLOCKED; F2-09 rights pending, C10 OPEN. Local commit, then wait.
F2-05 data-flow/logging/external-service boundaries were then separately confirmed and
implemented/offline verified after `39ea39c`: 17 new cases and full 1156 tests + 391 subtests
PASS, zero skips. [Scope and remaining admission gates](data-privacy.md). No private-data
or provider acceptance; synthetic-only local commit, then wait. C10 remains OPEN.
F2-06 injection/negative offline controls were subsequently confirmed after `4247cdf`:
eight independent synthetic cases, 19 new tests/47 subtests and full 1175 tests + 438
subtests PASS, zero skips. [Scope and limits](rag-safety-controls.md). C17 input bytes and
denominators unchanged; production injection defenses and real-model/semantic acceptance
remain unverified. F2-05 privacy, F2-09 sources and C10 gates remain open; local commit only.
F2-07 keyboard/names/status slice was subsequently confirmed after `182c252` and is
offline verified: 21 new Node cases (69 total), 8 new Python cases/46 subtests; full 1183
tests + 484 subtests PASS, zero skips. [Plan and remaining B15 acceptance](keyboard-accessibility.md).
Actual browser/reader/zoom/contrast/runtime/full RAG remain BLOCKED; F2-05 privacy and
F2-09 sources pending, C10 OPEN. Local commit only, then wait.
F2-10 current offline-entry/CI prerequisite was subsequently confirmed after `f3a7c2e`:
eight checks and tracked retained pytest, 35 new counterexamples; full 1218 tests + 484
subtests PASS, zero skips/xfails/deselections/guard denials. [Coverage and scope](offline-verification.md).
Historical C24 stays frozen; current remote CI and runtime/full RAG remain BLOCKED,
F2-05 privacy/F2-09 sources pending, C10 OPEN. Local commit only, then wait.
The frozen F2 report retains its original findings.

## Purpose and limits

BusinessAgent is a backend engineering portfolio for future GitHub open-source presentation
and job applications. There are no current plans for customer deployment or commercial
operation. Apply real project discipline to scope, design decisions, review, security,
testing, traceability, acceptance and handover; do not invent customers, revenue, uptime,
enterprise usage, production incidents or approvals to make the portfolio appear deployed.

Separate three conclusions:

| Conclusion | Evidence and boundary |
| --- | --- |
| Suitable for public portfolio presentation | Review public claims, code/data/dependency redistribution rights, secret exposure, reproducible instructions, demonstrations and disclosed limitations; publication still needs authorization |
| Engineering runtime acceptance | C01–C25 and their applicable E1/E2/E3 evidence; source/CI success alone does not close real storage, process, API, browser, recovery, load or RAG gates |
| Commercial/enterprise readiness | A future hypothetical assessment of adoption, economics and operations; actual customer integration/UAT/grey release and E4 evidence remain independently BLOCKED |

Portfolio presentation may describe unfinished engineering work honestly. It does not
require pretending that enterprise deployment is scheduled, and it does not authorize
weakening existing technical acceptance criteria. Existing runtime and full RAG blockers
remain BLOCKED; C10 remains open. Deferral is a scheduling choice, not PASS or automatic
NOT_APPLICABLE. Do not add SaaS billing, multitenancy or HA solely to look enterprise-ready.

## Registered follow-ups

The prior review at `63962523b067406142d9fa1268aac8193e47047b` identified two P2 defects.
Their authoritative details and acceptance criteria are in ISSUES as **C10-R1** (citation
serialization parity) and **C10-R2** (valid-history selection). Following separate user
confirmation, both are now FIXED / OFFLINE VERIFIED: 25 focused cases and a complete local
suite of 925 tests + 249 subtests pass with zero skips. The original 900-test receipt did
not cover these defects; the new evidence and plan are in the C10 follow-up record and
checkpoint contract. Live acceptance remains BLOCKED; C10 is open.

The committee should re-check them against its frozen candidate, not merely repeat this
review. Previous minimal reproductions used the installed Redis serializer without a
Redis connection and in-memory publication/history doubles; neither is live acceptance.

## Review entry and workflow

1. Obtain authorization for the review scope, freeze commit/schema/dependency identities,
   and inventory available evidence and known limitations. Review is read-only by default;
   agree separately to any test with storage, network, browser or process side effects.
2. Review each of the ten requested perspectives plus the two additions below. Record
   evidence before assigning a score. If multiple agents participate, identify their
   actual roles and consolidate disagreements; role simulation is not ten independent
   human experts or professional certification. No subagents are started by this plan.
3. Reproduce important findings safely where possible. Separate confirmed defects,
   unverified risks, historical findings and positive observations. De-duplicate findings
   across roles while retaining cross-cutting implications and dissent.
4. Produce the required scorecard, 2–3 observations per role and Top 3 actions. Every
   finding needs a source location, trigger, consequence, evidence level, priority,
   recommended action and testable acceptance standard. Missing evidence is explicit.
5. Map accepted findings to existing C items; propose a new item only if no item fits.
   Record dependencies, effort range/uncertainty, owner assignment (unassigned until agreed),
   and whether it blocks public presentation, runtime acceptance or commercialization.
   User confirmation selects one bounded implementation increment at a time.
6. Re-review changed paths and regenerate affected evidence at the final candidate. Git
   push, public presentation, merge, release, deployment and archive remain separate
   actions requiring the corresponding authorization. Stop after the authorized scope.

Entry does not require running paid models or real business systems. A static committee
report can finish with E2–E4 gaps; it cannot issue runtime/commercial approval from E0/E1.
There is no imposed deadline or budget for deployment or commercialization.

## Required perspectives and concrete observation points

These are review questions and evidence targets, not current findings or scores.

| Perspective | Required observations (2–3 per role) | Evidence targets |
| --- | --- | --- |
| 1. Project manager (PM) | Whether the portfolio MVP has a coherent backend learning/demo scope and explicit non-goals; whether dependencies/risks and per-increment entry/exit conditions are actionable; whether claims and actual delivery status agree | ROADMAP, ISSUES, DECISIONS, OpenSpec tasks, Git/evidence records |
| 2. Software architect | Boundaries among HTTP/API/SSE, graph, tools, queues and storage; ownership of state, transactions, asynchronous cancellation and process concurrency; whether SOLID/dependency inversion improves testability without unnecessary abstraction | chat/graph/fencing, approval/Saga/task queue, adapter contracts |
| 3. QA engineer | Whether fixtures and assertions can detect real contract regressions rather than only match doubles; whether CI includes a reliable minimum and complete regression without hidden skips; whether faults, uncertainty and concurrency have reproducible oracles | test/eval entries, CI, fault matrices, source-bound receipts, C10-R1/R2 |
| 4. Product manager | First clone/configuration/login/use journey and shortest useful backend workflow; whether empty/error/cancelled/partial states are truthful and actionable; whether scenarios have measurable acceptance and clearly identified mock/reference data | bilingual README, API/OpenAPI, role flows, frontend guide, C18/C19 reference scenarios |
| 5. DevOps engineer | Reproducible dependency/image/schema/model identity and artifact provenance/signing policy; explicit migration/upgrade gates and consistent API/worker packaging; observability, retained restore/rollback and incident procedures | Docker/Compose/CI, schema manifest, C21/C22 runbooks and evidence |
| 6. Security and privacy engineer | End-to-end sensitive-data/credential flow and log/history retention; least-privilege identity/role/department and tool approval boundaries; prompt injection, tool misuse, SSRF and fail-closed behavior under dependency failure | auth/RBAC/retrieval/tool paths, secrets handling, redaction, audit records and negative tests |
| 7. Interaction/accessibility specialist (A11y) | Keyboard focus/order and conflicts in login/chat/approval; screen-reader labels, dynamic SSE announcements and error recovery; zoom/text sizing, contrast and non-color-only state indicators | delivered browser UI and B01–B16 plus separately planned keyboard/screen-reader checks |
| 8. Open-source licensing and data compliance | Compatibility and redistribution conditions for direct/transitive dependencies and vendored assets; provenance/permission for sample documents, evaluation sets, models and generated demo data; completeness of LICENSE/NOTICE/attribution and externally sent data boundaries | dependency/asset inventories, license texts, dataset provenance and configured provider terms; future source verification required |
| 9. Performance engineer | Budgets for CPU/RAM/startup, connection pools and retained data; TTFT versus final latency, queue/backpressure, cancellation and realistic p95/p99 workloads; leaks/orphan growth and token/provider cost under bounded load | C23 workload/report, metrics, C10 retention, task queues and resource observations |
| 10. Internationalization specialist (i18n) | Hardcoded user-facing copy and error codes; layout/encoding and long-language text tolerance; dates/time zones/numbers/money/sorting and parity of bilingual documentation | README pair, UI/API messages, CRM analysis formatting, timestamp/money contracts |
| 11. AI Agent assurance specialist (addition) | Context token budget, truncation/history isolation and malicious retrieved content; tool authorization/idempotency/approval/compensation under multi-step failures; hallucination/abstention/citation quality, grounding and evaluation contamination | C07/C08/C10/C11/C12/C13/C17, source citations, role controls and semantic-review evidence |
| 12. Commercial feasibility and customer operations specialist (addition) | Specific hypothetical buyer/user problem and simpler non-agent alternatives; adoption/integration/support effort and measurable value; unit economics, external service terms, operational ownership and what evidence would be needed before a pilot | scenario/assumption register, measured versus hypothetical costs, support/deployment contracts; no fabricated demand or revenue |

Adapt the supplied prompt to this AI backend: IMK/input-method-specific IPC and mobile
battery checks are not assumed relevant. Assess HTTP/event/queue contracts and server
resource cost instead. A justified NOT_APPLICABLE needs a recorded scope rationale;
browser accessibility remains relevant even though the backend is the portfolio focus.
Internationalization review does not mandate adding unsupported languages.

Give extra attention to **context-window management, tool-call safety and hallucination
handling** across architecture, QA, security, product and the AI role. A serious issue in
these areas cannot be hidden by averaging good documentation or UI scores. Multi-agent
orchestration must justify its complexity against a simpler workflow/RAG baseline.

## Scoring and evidence rules

Use a separate 1–5 maturity score per role, with candidate identity and evidence confidence:
1 = observed fundamental deficiencies; 2 = major unresolved weaknesses; 3 = a coherent
baseline with material gaps; 4 = broadly verified within the stated scope with limited
gaps; 5 = the agreed scope is thoroughly supported by reproducible evidence and clear limits.
No score implies enterprise adoption, compliance certification, revenue or production SLA.

Use **PENDING** rather than an invented numeric score when a role has not been reviewed or
evidence is insufficient. Mark a particular non-applicable check with its rationale, not
an automatic high score for the entire role. Do not issue a global average as a release
decision. Priorities: P0 immediate safety/data/privilege risk; P1 major correctness or
delivery blocker; P2 functional/reliability gap; P3 lower-impact improvement. State the
affected decision gate and any proposed deferral, not merely a severity label.

Commercial assumptions need a validation method and sensitivity range. Costs must separate
measured token/storage/compute/integration/support inputs from estimates. Future provider
pricing, license/legal terms and market claims must use dated authoritative sources;
no legal or market verification is asserted by this plan.

## Reusable report format

The user-facing report uses Simplified Chinese and the requested structure below.
Project planning remains primarily English. The completed F2 report follows this format;
future reviews must freeze a new candidate and refresh evidence rather than copy scores.

```markdown
### 1. 总体评分卡

审核候选：<commit / schema / dependency identity>
范围与证据：<E0–E4、未执行项、角色模拟或实际参与方式>

| 视角 | 评分 (1–5 / PENDING) | 核心结论（一句话，含关键证据限制） |
| :--- | :---: | :--- |
| <逐行列出十个指定角色及两个补充角色> | <尚未审核不填数字> | <证据支持的结论> |

### 2. 详细审核意见

- **<专家角色>**：
  - **严重问题**：<已确认事实；文件/行、触发条件、影响、优先级、证据；没有则明确没有>
  - **改进建议**：<具体修正、依赖、验收标准或需验证的假设>
  - **做得好的地方**：<有证据的优点及其适用边界>

### 3. 关键风险与行动建议 (Top 3)

1. <风险、关联 issue、影响的门槛、最小下一步、验收标准>
2. <同上；区分修复与补证据>
3. <同上；不以凑数代替事实>
```

Keep 2–3 substantive observations per role; do not manufacture a severe issue or a positive
finding to fill a template. Add a compact handover stating outstanding decisions, retained
BLOCKED gates and the next proposed increment. Professional, objective, direct language;
no promotional claims, courtesy scores or invented expert sign-off.

## Historical exit of the initial planning increment (`c0a4464`)

Positioning, C10-R1/R2 and this protocol are recorded and cross-linked; no committee review,
code fix, live test or commercialization work starts. Validate document links, OpenSpec
structure/YAML and unchanged code/modes. OpenSpec strict remains BLOCKED without the CLI.
Review and commit the documentation locally, then wait for user confirmation; no push.
