## 0. S0：交付计划与边界（本轮授权）

- [x] 0.1 建立 proposal、design、engineering-delivery delta 与本任务清单。
- [x] 0.2 落盘工程基线；ISSUES 登记 C01–C25；ROADMAP 登记 S0–S7；DECISIONS 追加边界决策。
- [x] 0.3 更新索引、OpenSpec context 与阶段总结，检查链接/锚点、覆盖关系和只改文档的范围。
- [x] 0.4 记录验证限制，完成本地文档交付后暂停，等待用户确认 S1 首项；不启动运行时代码工作。

S0 验证：83 个本轮链接/锚点、25 个 C 项映射、8 个阶段、8 条需求结构通过；仅文档与 OpenSpec context 改动。OpenSpec CLI 严格校验 BLOCKED，不计为通过；完整记录见 `docs/40-process/阶段性总结_S0工程交付基线.md`（仓库相对路径）。

## 1. S1：可复现环境（1.1 完成；1.2 配置独立交付、运行验收阻塞；1.3 外部模型方案已确认，离线增量完成、真实 API/Linux 验收阻塞）

- [x] 1.1 C24 前置部分：安全验证入口与证据模板；本项只完成前置，C24 最终状态仍 open。<!-- evidence: enterprise-agent/scripts/safe_validate.py; docs/40-process/阶段性总结_C24安全验证前置.md; 12 stdlib regression tests PASS; offline execution PASS, UAT/release BLOCKED -->
- [ ] 1.2 C01 部署产物与入口一致。<!-- configuration implemented; target-runtime acceptance BLOCKED; do not close based on static checks -->
  - [x] 1.2.1 冻结 deployment-artifacts delta，统一镜像/入口配置，补契约检查和部署说明；离线 8 项通过，PyYAML 测试 1 项跳过，另用系统 Ruby 标准库完成真实 YAML 解析与模型契约检查。
  - [ ] 1.2.2 在隔离 Linux 环境完成 Compose 渲染、Nginx 校验、候选镜像身份、UI/登录/SSE/健康/就绪/指标边界验收并记录证据。<!-- BLOCKED: no Docker/Nginx here; model/bootstrap dependencies remain C02/C03; see docs/40-process/阶段性总结_C01部署产物与入口.md -->
- [ ] 1.3 C02 模型与依赖 profile 匹配。
  - [x] 1.3.1 Implement the approved Beijing Bailian / DeepSeek profile, remote adapters, slim build, configuration/startup gates, documentation and offline regressions. 27 offline model/transport tests PASS; real API and Linux acceptance remain BLOCKED.
  - [x] 1.3.2 用户已批准 libpq5；补齐 runner 安装、失败即停止及最终非 root runtime 导入探针，2 项新增静态回归 PASS。实际镜像构建/导入仍由 1.3.3 验收。
  - [ ] 1.3.3 隔离候选真实构建/扫描、模型推理与 LLM 问答、资源测量及缺失配置负例验收。<!-- BLOCKED; see docs/40-process/阶段性总结_C02模型依赖.md -->
- [ ] 1.4 C03 数据库迁移与初始化。
  - [x] 1.4.1 Implement the version/checksum runner, schema-only baseline, explicit admin/demo bootstrap, startup guards, documentation and offline checks. 22 fake orchestration/startup tests PASS; real PostgreSQL/Linux acceptance remains BLOCKED.
  - [ ] 1.4.2 Verify empty PostgreSQL initialization, legacy-copy upgrades, repeated/concurrent runs, rollback and login in isolated Linux. <!-- BLOCKED: no local Docker/PostgreSQL; never migrate the current database -->

## 2. S2：权限与敏感信息（C04 离线增量完成，运行验收阻塞；C05 离线增量完成，运行验收阻塞；C06 离线增量完成，运行验收阻塞；C07 离线增量完成，运行验收阻塞；后续待授权）

- [ ] 2.1 C04 会话归属校验。
  - [x] 2.1.1 Implement persisted ownership guards for message/stream/history/feedback/cancel, explicit admin policy, safe creation, offline adversarial tests and documentation. 20 offline tests PASS; real HTTP/PostgreSQL acceptance remains BLOCKED.
  - [ ] 2.1.2 Verify A/B/admin HTTP/SSE flows, PostgreSQL concurrency/rollback and unchanged checkpoint/business data in the isolated runtime. <!-- BLOCKED: current database and real API/Linux services remain out of scope -->
- [ ] 2.2 C05 认证失败闭合与运行时授权。
  - [x] 2.2.1 Implement fail-closed identity resolution, production auth gates, approval reauthorization, offline tests and delivery documentation. 27 offline tests PASS; real JWT/HTTP/PostgreSQL/Linux acceptance remains BLOCKED.
  - [ ] 2.2.2 Verify real JWT/FastAPI, PostgreSQL revocation/locking, API/SSE and Linux startup in the isolated candidate. <!-- BLOCKED: no live API/database/deployment authorization -->
- [ ] 2.3 C06 凭证、脱敏与 HTML 失败安全。
  - [x] 2.3.1 Implement transient approval/graph credentials, redaction boundaries, browser lifecycle and safe Markdown fallback; add offline evidence and docs. 20 Python tests and 13 browser-script VM cases PASS; live/historical acceptance remains BLOCKED.
  - [ ] 2.3.2 Verify real JWT/PostgreSQL/API/SSE/Linux/browser flows and historical credential remediation in an explicitly authorized isolated candidate. <!-- BLOCKED; no current data cleanup -->
- [ ] 2.4 C07 检索权限与表达式编码。
  - [x] 2.4.1 Implement shared scope, encoded expressions, ACL result guards, offline matrix tests and documentation. 21 C07 tests PASS; live acceptance remains BLOCKED.
  - [ ] 2.4.2 Verify real Milvus/PostgreSQL filtering and API/SSE output/citations in isolated Linux. <!-- BLOCKED; no current store access -->

## 3. S3：会话与运行状态（C08/C09 离线增量完成、运行验收阻塞；C10 离线增量完成、运行与写入竞态验收阻塞）

- [ ] 3.1 C08 请求上下文、历史和依赖语义。
  - [x] 3.1.1 Implement per-dispatch context, request-bound history, dependency rejection, offline tests and documentation. 23 C08 and 88 related tests PASS; real runtime acceptance remains BLOCKED.
  - [ ] 3.1.2 Verify real LangGraph concurrent conversations, JWT refresh, PostgreSQL checkpoint history and API/SSE rejection in isolated Linux. <!-- BLOCKED; prior runtime/browser/SSO/history blockers remain -->
- [ ] 3.2 C09 跨进程状态或明确支持限制。
  - [x] 3.2.1 Implement shared cancellation/SSO state and request prompt snapshots, offline failure/race checks and documentation. 28 focused and 111 related tests PASS; live two-process acceptance remains BLOCKED.
  - [ ] 3.2.2 Verify at least two API processes, Redis atomicity/expiry/restart/failure, PostgreSQL prompt visibility and real HTTP/SSE/SSO flows in isolated Linux. <!-- BLOCKED; no live service authorization -->
- [ ] 3.3 C10 checkpoint 持久化和故障语义。
  - [x] 3.3.1 Implement explicit backend policy, lifecycle/provisioning, failure semantics, offline tests and documentation. 27 focused and 139 related tests PASS; this does not solve lease-expiry write fencing.
  - [x] 3.3.3 Implement stale-writer isolation, database-clock write ownership, atomic checkpoint/session publication, additive schema v8, 28 offline race tests and documentation. Local full pytest 900 tests + 232 subtests PASS, zero skips; fixed inventory 818 PASS + 1 existing PyYAML BLOCKED. Local commit only, C10 remains open.
  - [x] 3.3.4 Resolve C10-R1: shared validated JSON-safe citation projection for message/SSE/history, actual Redis serializer round-trips and malformed-source refusal before publication. Included in 25 focused cases and 925-test/249-subtest local suite PASS; live acceptance BLOCKED.
  - [x] 3.3.5 Resolve C10-R2: filter before counting valid turns, shared 100-snapshot/five-second budget, early stop/iterator closure, legacy and fixed failures. Included in 25 focused cases and full 925-test/249-subtest local suite PASS, zero skips. Parent 3.3/runtime 3.3.2 remain open; no live acceptance.
  - [ ] 3.3.2 Verify actual saver versions, two-process/restart durability, TTL, same-session writes and outages on isolated Linux. <!-- BLOCKED; no real services or current-store operations -->

## 4. S4：执行一致性与恢复（C18 契约前置已推送；C12 已推送；C14 已推送；C13 已推送；C11 已推送，真实运行阻塞）

- [x] 4.1 C18 前置部分：冻结参考系统幂等、失败和补偿契约，C18 完整验收留 S5。 business-reference-v1 documents 13 interface rows, durable identity/receipts, compensation and 20 future cases; static checks only, no runtime implementation or acceptance.
- [ ] 4.2 C12 工具幂等与安全重试。
  - [x] 4.2.1 Implement persisted identities, dispatch claims, receipt validation, gateway authorization, docs and offline verification. 41 focused and 94 related tests PASS; no runtime acceptance or full Saga/queue/approval recovery claim.
  - [ ] 4.2.2 Verify real PostgreSQL concurrency/crash, HTTP response loss and complete application replay in isolated Linux. <!-- BLOCKED; no live service authorization -->
- [ ] 4.3 C14 队列可靠性与 worker 初始化。
  - [x] 4.3.1 Implement transactional jobs, guarded ownership/recovery, producer/status routes, worker initialization and offline validation. 43 focused + 112 related offline tests PASS; full Saga/audit recovery remains C13/C21.
  - [ ] 4.3.2 Verify real PostgreSQL concurrency, process crashes, outages, Milvus ingestion and Linux startup; integrate Saga recovery after C13. <!-- BLOCKED; not closed by doubles -->
- [ ] 4.4 C13 Saga 持久化与故障恢复。
  - [x] 4.4.1 Implement a versioned Saga journal, atomic recovery jobs, linked HTTP inverse identities, conservative restart reconciliation, offline tests and delivery records. 34 focused + 185 related tests PASS; real acceptance remains BLOCKED.
  - [ ] 4.4.2 Verify PostgreSQL locking/crashes, independent reference HTTP services, response loss, inverse conflicts and worker restart in isolated Linux. <!-- BLOCKED; C10 fencing and C21 audit replay remain separate -->
- [ ] 4.5 C11 审批原子领取、过期与执行状态。
  - [x] 4.5.1 Implement guarded decisions, one-way execution claims, expiry, truthful result states, atomic audit events, UI labels and offline verification. 34 focused + 210 related cases PASS; local only.
  - [ ] 4.5.2 Verify real PostgreSQL/JWT/API/browser concurrency, timeout races and crash recovery in isolated Linux. <!-- BLOCKED; C10/C21 unchanged -->

## 5. S5：数据与参考集成（C15–C19 已推送；运行阻塞；C20 离线增量完成）

- [ ] 5.1 C15 知识发布与索引一致性。
  - [x] 5.1.1 Implement immutable publication records, deterministic chunk upsert, atomic activation, retrieval visibility guards, retained retry/deactivation, documentation and offline verification. 36 focused + 148 related tests PASS; local only.
  - [ ] 5.1.2 Verify real PostgreSQL/Milvus concurrency, partial writes, restarts, indexing visibility and full RAG regression in isolated Linux. <!-- BLOCKED; C10/C21 unchanged -->
- [ ] 5.2 C16 分析数据适配。
  - [x] 5.2.1 Implement CRM-provider-aligned snapshot reads, current authorization, bounded pagination, exact aggregation and deterministic reporting with docs/offline tests. 33 focused + 149 related cases PASS; local only.
  - [ ] 5.2.2 Verify real reference CRM/PG/JWT/API/SSE/Linux snapshots, query/analysis agreement and failure/permission behavior. <!-- BLOCKED; C10 open, C21 deferred, C15 full RAG unchanged -->
- [ ] 5.3 C17 RAG 质量与指标口径。
  - [x] 5.3.1 Freeze all 122 cases/nine sources, add six separate role controls, implement fixed-denominator metrics, actual-agent evaluation, truthful fallback/error semantics, docs and offline checks. 29 focused + 112 related cases PASS; no measured quality claim.
  - [ ] 5.3.2 Run the full frozen corpus on the accepted C02 profile in isolated Linux; verify coverage >=0.85, all citation semantics, no-answer/clarification and department controls. <!-- BLOCKED; offline mechanical tests do not close C17 -->
- [ ] 5.4 C18 完整参考 HTTP 集成。 <!-- BLOCKED: business-reference-v1 R01-R20 require independent persistent services and complete application evidence; prework is not acceptance -->
  - [x] 5.4.1 Implement independent B01–B13/analysis services, retained transactional stores, isolated authenticated controls, image/Compose recipes, admin observation and opt-in application transcript; 45 focused + 162 related offline cases PASS. No new dependency or live execution.
  - [ ] 5.4.2 Verify Linux images/network, physical persistence and all R01–R20 through login/planning/approval/tool/queue/Saga/audit with independent services and real transport/process faults. <!-- BLOCKED; collector OBSERVED is not case PASS; C10 open, C21 deferred, full RAG unchanged -->
- [ ] 5.5 C19 受控 IdP 的 SSO 完整链路。
  - [x] 5.5.1 Implement independent retained issuer, strict RS256/PKCE/mapping, approved dependency declarations, HTTPS recipes, browser acceptance plan and offline checks. 37 focused + 136 related cases PASS; no real crypto/browser or installation.
  - [ ] 5.5.2 Verify all S01–S16 including real signing, browser handoff, PostgreSQL identity, Redis across API processes, rotation, faults and disk restart in isolated Linux. <!-- BLOCKED; R01–R20/full RAG/C10/C21 unchanged; operator reports are not acceptance -->

## 6. S6：用户操作与运维（C20–C23 离线增量完成、运行阻塞）

- [ ] 6.1 C20 浏览器角色流程与前端交付。
  - [x] 6.1.1 Pin and self-host existing browser assets with licenses/integrity, verify current identity, isolate asynchronous UI state, guard mutations, report truthful stream/action outcomes, and document UI/API-only roles. 45 focused + 134 related offline cases PASS; no browser/application launch.
  - [ ] 6.1.2 Verify B01–B16 on the delivered Linux/Nginx entry with actual browsers, all roles and independent server evidence. <!-- BLOCKED; S01–S16/R01–R20/full RAG/C10/C21 unchanged -->
- [ ] 6.2 C21 就绪、审计、指标和告警。
  - [x] 6.2.1 Implement bounded readiness, internal worker observations, retained audit identity/replay, reviewed legacy import, request/task correlation, process scrapes and controlled alert receipt candidate. 45 focused + 362 related offline cases PASS; one PyYAML case skipped, separate Ruby YAML parse PASS. C21 `40c10d8` pushed under subsequent authorization; real acceptance remains blocked.
  - [ ] 6.2.2 Verify O01–O16 with actual Linux processes/stores, faults, traces, Prometheus and independent firing/resolved receipts. <!-- BLOCKED; B01–B16/S01–S16/R01–R20/full RAG/historical credentials remain blocked; C10 writing remains open -->
- [ ] 6.3 C22 备份恢复与回退。
  - [x] 6.3.1 Provide reviewed-plan cold capture, retained archive validation, failure resumption, fresh-volume restore, rollback/window planning and documentation. 46 focused + 77 related offline cases PASS; one PyYAML case skipped. No real Docker/store/recovery execution; C22 d70c1b4 pushed under subsequent authorization.
  - [ ] 6.3.2 Execute D01–D16 on the exact isolated Linux candidate with independent PG/content/retrieval/external-effect evidence and measured RTO/RPO. <!-- BLOCKED; O/B/S/R/full RAG/historical gates preserved; C10 remains open -->
- [ ] 6.4 C23 规定负载下的性能与容量。
  - [x] 6.4.1 Implement frozen plan, bounded mixed runner, independent business checks, separate timings and offline reporting/tests. 42 focused + 186 related cases PASS; no live load. C23 `6de94c6` subsequently pushed and verified.
  - [ ] 6.4.2 Confirm actual workload/thresholds then execute L01–L16 in isolated Linux, including >=30 minutes, semantics, queue/resource/recovery and cost evidence. <!-- BLOCKED; D/O/B/S/R/full RAG and C10 unchanged -->

## 7. S7：最终候选收口（C24 离线部分完成；完整验收阻塞；C25 离线部分完成；整项 open）

- [ ] 7.1 C24 最终候选自动化、参考环境与人工验收回归。
  - [x] 7.1.1 Review fixed offline entries, repair stale fixtures/YAML scalar quoting, add source/candidate-bound retained receipts and acceptance mapping. 789 tests PASS, one PyYAML skip/BLOCKED; seven assets PASS; five readiness functions execute with real gates BLOCKED. C24 `d8a26b5` subsequently pushed and verified; full CI collection FAIL recorded in C25.
  - [ ] 7.1.2 Verify the exact image/dependencies, full application/E2/E3 and all L/D/O/B/S/R/full-RAG/historical gates; retain C10 fencing unresolved until implemented and verified. <!-- BLOCKED; full pytest/current build/scans/CI/OpenSpec strict are not provided by E0/E1 -->
- [ ] 7.2 C25 Git/文档/版本/支持边界一致性检查与交付结论。
  - [x] 7.2.1 Reconcile Git provenance, bilingual entry points, current/historical documentation, source/schema/version identities, active delta scope and offline delivery conclusion. Record C24 remote CI collection FAIL explicitly; docs-only local commit, no release/archive.
  - [ ] 7.2.2 Resolve remaining CI/P0/P1/runtime gates and reconcile the final accepted commit/image with strict validation and independent E2/E3 evidence. <!-- BLOCKED; historical C25 CI FAIL retained; 0d1a7ce remote CI PASS does not close runtime/strict acceptance; C10 remains open; no merge/release/sync/archive authorized -->
- [x] 7.2.3 Repair stale CI collection and subsequent full-suite failures without skipping tests. Local full pytest: 871 tests and 225 subtests PASS, zero skips; 73.40% line coverage. C25 fe2ae78 and repair b8c4457 pushed. Remote Linux 3.11/3.13 each pass 871 tests and 225 subtests; subsequent scan repair is tracked in 7.2.4. Runtime/full RAG remain BLOCKED; C10 open.
- [x] 7.2.4 Push `b8c4457` and follow CI without skipped tests or weakened gates. Exact source-hash fingerprints and complete event-range scan: `16c882b`; required runtime script build context plus regression: `0d1a7ce`. Run 39209313444 PASS: each Python matrix 872 tests + 225 subtests, secret/dependency scans, image/import/assets/Trivy PASS. Runtime/full RAG BLOCKED, C10 open; no merge/release/archive.

- [ ] 7.3 运行 OpenSpec 严格校验，完成 delta 同步及归档前检查；仅在所有工程验收满足且用户确认后归档，真实企业两个 change 继续独立管理。

逐项验收唯一入口：[ISSUES C01–C25](../../../docs/40-process/ISSUES.md#engineering-closeout)。
阶段顺序唯一入口：[ROADMAP S0–S7](../../../docs/40-process/ROADMAP.md#engineering-closeout-stages)。
S0 完成不代表上述 25 项完成；不将 CLI 未执行记录为严格校验成功。


## 8. Portfolio positioning and committee review

- [x] 8.1 Record the confirmed backend-job/GitHub portfolio purpose, no current deployment/commercial operation plan, retained engineering gates, deferred C10-R1/R2 and the review protocol in project documents and existing OpenSpec artifacts. This checkbox records planning, not review results.
- [x] 8.2 After explicit confirmation, review frozen `c57d473` from the ten requested perspectives plus AI assurance and commercial/customer operations. Single-agent role simulation; scorecard, 2–3 observations per role and Top 3 recorded in `docs/40-process/multi-expert-review-c57d473.md`; commercial demand PENDING, no runtime approval.
- [x] 8.3 Triage/deduplication of F2-01–F2-11 into ISSUES/ROADMAP is complete, with distinct public/runtime/commercial gates. F2-01 and the separately confirmed F2-02 are tracked in sections 9–10, and the separately confirmed F2-03 execution slice in section 11; remaining remediation remains PENDING, without closing existing runtime gates.
- [ ] 8.4 Reconcile public portfolio claims, demonstrations, license/data attribution and reproducibility with the final reviewed candidate. Does not authorize public publication, push, merge, release, deployment, spec sync or archive; engineering and enterprise acceptance remain separate.


## 9. F2-01 rate-limit identity (authorized 2026-10-19)

- [x] 9.1 Record the bounded plan, trust boundary, compatibility and acceptance criteria before implementation.
- [x] 9.2 Add failing real-JWT/ASGI counterexamples and implement shared verification, bounded parsing and source-bound login quotas.
- [x] 9.3 Focused 87 tests + 35 subtests, C05 eval 29 tests and full local pytest 955 tests + 249 subtests PASS, zero skips/guard denials. Diff/document review and source binding complete; local commit only, no live acceptance.
- [ ] 9.4 Separately authorized live Redis/proxy/PostgreSQL/API/Linux verification; remains BLOCKED, not covered by offline completion.


## 10. F2-02 Redis rate-limit failure and recovery (authorized 2026-10-19)

- [x] 10.1 Record failure policy, recovery/concurrency design, limits and acceptance before implementation.
- [x] 10.2 Implement non-dev 503, labeled dev fallback, bounded single-probe recovery and safe shared accounting; add offline counterexamples and regressions.
- [x] 10.3 Focused 61 tests, C09 eval 28 tests and full local pytest 973 tests + 249 subtests PASS, zero skips/guard denials. Documents, source binding and diff reviewed; local commit only, no push or live acceptance.
- [ ] 10.4 Real two-process Redis/proxy/Linux failure/recovery acceptance remains BLOCKED; no parent C item closes from offline tests.


## 11. F2-03 execution resources (authorized 2026-10-19)

- [x] 11.1 Record limits, ownership, failure semantics, exclusions and acceptance before code.
- [x] 11.2 Implement task/concurrency/history/model admission budgets and safe failure propagation.
- [x] 11.3 Add 34 new offline cases; full pytest 1007 tests + 249 subtests and eight related eval entries PASS, zero skips. Review source/diff/documents and bind evidence before local commit only; no push.
- [ ] 11.4 Real provider/process/capacity/full RAG acceptance remains BLOCKED; C10 stays open.
- [x] 11.5 SSE backpressure was separately confirmed on 2026-10-20; implementation and offline evidence are tracked in section 12. Runtime acceptance remains separate.


## 12. F2-03 SSE backpressure (authorized 2026-10-20)

- [x] 12.1 Record capacity, terminal/publication ordering, timeouts, cleanup and offline acceptance before implementation.
- [x] 12.2 Implement bounded buffering, terminal slot, pre-publication size guard and cooperative transport/cleanup bounds.
- [x] 12.3 Verify 41 new failure/cancel/ASGI cases; full 1048 tests + 249 subtests and five related eval entries PASS, zero skips. Review source/docs/manual OpenSpec structure and bind evidence before local commit only; no push. Strict CLI unavailable/BLOCKED.
- [ ] 12.4 Real browser/proxy/Linux/store/capacity/full RAG acceptance remains BLOCKED; C10 stays open. No automatic next finding or remote action.


## 13. F2-04 build and dependency reproducibility (authorized 2026-10-20)

- [x] 13.1 Record supported production profile, immutable inputs, inventory contract and evidence boundaries before implementation.
- [x] 13.2 Pin reviewed production image/OS/wheel inputs; remove range upgrades; verify installed inventory and retain CI evidence.
- [x] 13.3 Add 50 offline adversarial cases; full 1098 tests + 249 subtests PASS, zero skips; input/Dockerfile/safe preflight execution checks PASS. Review source/docs/manual OpenSpec and bind tested bytes before local commit only. Strict CLI unavailable/BLOCKED.
- [ ] 13.4 Two clean Linux builds, final imports/inventory/security scans and real runtime/full RAG remain BLOCKED; C10 open. No automatic next increment or remote action.

## 14. F2-09 license and data provenance (authorized 2026-10-20)

- [x] 14.1 Record scope, evidence levels and offline acceptance before implementation in `docs/50-engineering/license-provenance.md`.
- [x] 14.2 Inventory pinned dependencies, vendored/distribution assets and data sources; retain actual notices and explicit unresolved rights.
- [x] 14.3 Read-only integrity and 36 new negative/regression cases; full 1134 tests + 249 subtests PASS, zero skips. Review and synchronize documentation; local commit only. Strict OpenSpec CLI unavailable/BLOCKED.
- [ ] 14.4 Obtain author/source confirmations and actual distribution license/notice review; BLOCKED. Real runtime/full RAG remain BLOCKED; C10 OPEN.

## 15. F2-11 demonstration script and evidence (authorized 2026-10-20)

- [x] 15.1 Record the documentation-only plan and acceptance boundaries before implementation in `docs/50-engineering/portfolio-demonstration.md`.
- [x] 15.2 Write one candidate-bound walkthrough/evidence checklist; distinguish Mock, reference and real runtime; register older materials as historical without editing them. Document the reusable bounded-review workflow.
- [x] 15.3 Local source/links/inventory/manual OpenSpec checks PASS; strict CLI unavailable/BLOCKED. Synchronize trackers and commit locally only; no push/upload, full test or runtime claim.
- [ ] 15.4 Obtain independent presentation feedback if separately authorized; commercial validation remains DEFERRED / NOT STARTED. F2-09 rights pending; runtime/full RAG BLOCKED; C10 OPEN.

## 16. F2-08 citation time and offline regression (authorized 2026-10-20)

- [x] 16.1 Record new UTC citation contract and legacy-naive compatibility before implementation in `docs/50-engineering/citation-time.md`.
- [x] 16.2 Make new citation timestamps UTC-aware; verify generation, JSON/history and UI formatter offline without reinterpreting historical data.
- [x] 16.3 Review and relevant checks PASS: full 1139 tests + 288 subtests, zero skips; Node VM 48 cases, C10 27 and C17 29 PASS. Pending provenance refreshed and documents/OpenSpec synchronized; strict CLI unavailable/BLOCKED. Local commit only, no push/upload.
- [ ] 16.4 Real browser/runtime/full RAG remain BLOCKED; F2-09 rights pending and C10 OPEN. No migration or automatic next item.

## 17. F2-05 data flow and privacy boundaries (authorized 2026-10-20)

- [x] 17.1 Record the bounded synthetic-only plan and admission/verification limits before implementation in `docs/50-engineering/data-privacy.md`.
- [x] 17.2 Minimize covered operational logs and manual trace metadata; verify synthetic counterexamples and actual adapter payload boundaries offline.
- [x] 17.3 Data-flow/access/retention/disposal/provider requirements documented; 17 new tests, full 1156 tests + 391 subtests PASS, zero skips; C06/C08/C17/C21 offline entries PASS. Review and synchronize OpenSpec/trackers/pending provenance; local commit only. Strict CLI remains unavailable/BLOCKED.
- [ ] 17.4 Private-data/provider/automatic-telemetry and real runtime/full RAG acceptance remain BLOCKED; F2-09 sources pending, C10 OPEN. No next item or external action without confirmation.

## 18. F2-06 RAG injection and negative offline controls (authorized 2026-10-20)

- [x] 18.1 Record the bounded synthetic-only plan before implementation in `docs/50-engineering/rag-safety-controls.md`.
- [x] 18.2 Add independent synthetic injection/negative controls and truthful mechanical evidence; characterize actual generation with local doubles without changing production behavior or C17 denominators.
- [x] 18.3 Offline regressions and review PASS: 19 new tests/47 subtests; full 1175 tests + 438 subtests, zero skips; C17 29 PASS. Frozen inputs/denominators and pending provenance preserved; docs/trackers synchronized. Strict CLI unavailable/BLOCKED; local commit only, no push/upload.
- [ ] 18.4 Real model/adversarial/semantic/full RAG acceptance remains BLOCKED; F2-05 privacy and F2-09 sources pending, C10 OPEN. No automatic next item.


## 19. F2-07 keyboard, control names and statuses (authorized 2026-10-20)

- [x] 19.1 Record the bounded plan and offline/live acceptance distinction before implementation in `docs/50-engineering/keyboard-accessibility.md`.
- [x] 19.2 Repair native controls, names, composition handling, owned focus and truthful non-token status announcements.
- [x] 19.3 Offline verification and review PASS: 21 new Node cases (69 total), credential VM 14, seven assets; 8 new Python tests/46 subtests, full 1183 tests + 484 subtests, zero skips. Trackers/pending inventory/OpenSpec synchronized; strict CLI unavailable/BLOCKED. Local commit only, no push/upload.
- [ ] 19.4 Actual browser/keyboard/reader/zoom/contrast/runtime/full RAG acceptance remains BLOCKED; F2-05 privacy and F2-09 sources pending, C10 OPEN. No automatic next item.


## 20. F2-10 prerequisite: current offline entry and CI (authorized 2026-10-20)

- [x] 20.1 Record explicit coverage, failure/binding semantics and exclusions before implementation in `docs/50-engineering/offline-verification.md`.
- [x] 20.2 Implement current reviewed entry and retained full-pytest helper; align local CI recipe without weakening existing security or acceptance gates.
- [x] 20.3 Offline verification/review PASS: 35 new counterexamples, full 1218 tests + 484 subtests with zero skips/xfails/deselections/guard denials; eight checks including Node 69/14 and seven assets PASS. Current source/declaration/provenance/docs/OpenSpec synchronized; strict CLI unavailable/BLOCKED. Reviewed local commit and final clean-candidate receipt only.
- [ ] 20.4 Remote CI, real runtime/full RAG, F2-05 privacy and F2-09 rights remain BLOCKED/pending; C10 OPEN. No push/upload/dispatch or automatic next item.

## 21. F2-05 automatic telemetry admission (authorized 2026-10-21)

- [x] 21.1 Record the bounded configuration/startup plan before implementation in `docs/50-engineering/telemetry-admission.md`.
- [x] 21.2 Enforce default-disabled configuration and explicit synthetic OTEL admission before dependency import, effective Settings, API/worker startup and tracing factories; preserve C21 audit/metrics. Missing optional SDKs fail closed; no new dependencies.
- [x] 21.3 Synthetic offline verification/review PASS: 84 new cases; full 1302 tests + 484 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS. Reviewed 332 inputs/439 pending-source records, documentation and OpenSpec synchronized; strict CLI unavailable/BLOCKED. Local commit/final-candidate receipt only.
- [ ] 21.4 Actual telemetry/provider/privacy, real runtime/full RAG remain BLOCKED; F2-09 rights pending, C10 OPEN. No push/upload, new dependency, main-spec sync, archive or automatic next item.

## 22. F2-06 read-only RAG production trust boundary (authorized 2026-10-21)

- [x] 22.1 Record minimal scope, compatibility, publication and semantic limits before implementation in `docs/50-engineering/rag-trust-boundary.md`.
- [x] 22.2 Apply fixed policy to effective knowledge prompt versions and untrusted data; reject tool/citation failures, suppress raw drafts and preserve knowledge through deterministic citation-aware aggregation. Source IDs remain server-side; fixed coverage scoring is not factual validation.
- [x] 22.3 Synthetic verification/review PASS: 53 new cases; full 1355 tests + 484 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS. C17 frozen; 334 inputs/440 pending sources reviewed and docs/OpenSpec synchronized. Strict CLI unavailable/BLOCKED; local commit/final-candidate receipt only.
- [ ] 22.4 Real-model/adversarial/semantic/runtime/full RAG/privacy acceptance remains BLOCKED; F2-09 rights pending, C10 OPEN. Other agent prompt boundaries remain separate; no automatic next item or external action.

## 23. F2-06 Planner and tool-selection trust boundary (authorized 2026-10-22)

- [x] 23.1 Record scope, compatibility, authority and acceptance before implementation in `docs/50-engineering/planner-tool-trust-boundary.md`.
- [x] 23.2 Implement effective-template policy/data separation, strict Planner/tool proposals, current-request action excerpts, knowledge-only replan and no guessed fallback actions; retain downstream authority and C17.
- [x] 23.3 Synthetic offline/review PASS: 61 new cases; full 1416 tests + 497 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS, 336 inputs/441 pending sources. C17 unchanged; documentation/YAML/manual OpenSpec structure reviewed, strict CLI unavailable/BLOCKED. Local reviewed commit/final-candidate receipt only.
- [ ] 23.4 Real model/semantic/tool/runtime/full RAG/privacy acceptance remains BLOCKED; F2-09 pending and C10 OPEN. No push/upload, dependency, main-spec sync, archive or automatic next item.

## 24. F2-06 non-knowledge result facts and publication (authorized 2026-10-22)

- [x] 24.1 Record scope, structured status authority, compatibility and acceptance before implementation in `docs/50-engineering/nonknowledge-result-boundary.md`.
- [x] 24.2 Replace multi-result non-knowledge model rewriting with bounded deterministic status/data composition; retain all failure/pending/compensation/unknown outcomes, existing single/knowledge/analysis contracts and C10/SSE publication. Chitchat/reranking deferred.
- [x] 24.3 Actual-source offline/review PASS: 49 new cases; full 1465 tests + 495 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS, 338 inputs/442 pending sources. C17 29 and five parser cases/two unsafe controls PASS; docs/YAML/manual OpenSpec reviewed, strict CLI unavailable/BLOCKED. Reviewed local commit/final-candidate receipt only.
- [ ] 24.4 Real model/tool/semantic/runtime/full RAG/privacy acceptance remains BLOCKED; F2-09 pending and C10 OPEN. No push/upload, new dependency, C17 change, main-spec sync, archive or automatic next item.

## 25. F2-06 chitchat fallback trust boundary (authorized 2026-10-22)

- [x] 25.1 Record scope, compatibility, response/publication authority and acceptance before implementation in `docs/50-engineering/chitchat-trust-boundary.md`.
- [x] 25.2 Implement fixed policy/JSON data roles without names, strict bounded text/native-call admission, deterministic fallback and hidden/literal generated replies; retain budget/cancellation/request/C10/SSE contracts. Optional reranking deferred.
- [x] 25.3 Actual-source offline/review PASS: 57 new cases; full 1522 tests + 494 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS, 340 inputs/443 pending sources. C17 29 and five parser cases/two unsafe controls PASS; docs/YAML/manual OpenSpec reviewed, strict CLI unavailable/BLOCKED. Reviewed local commit/final-candidate receipt only.
- [ ] 25.4 Real model/semantic/browser/runtime/full RAG/privacy remain BLOCKED; F2-09 pending and C10 OPEN. No push/upload, dependency, C17 change, main-spec sync, archive or automatic next item.

## 26. F2-06 optional LLM rerank score and event boundary (authorized 2026-10-22)

- [x] 26.1 Record scope, whole-batch fallback, compatibility and acceptance before implementation in `docs/50-engineering/llm-rerank-trust-boundary.md`.
- [x] 26.2 Implement effective-template policy/JSON roles, strict bounded score/no-call responses, original-candidate preservation, whole-batch fallback and hidden score candidates; retain budgets and downstream authority. Cohere/BGE deferred.
- [x] 26.3 Actual-source offline/review PASS: 85 new tests/3 subtests; full 1607 tests + 497 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS, 342 inputs/444 pending sources, C17 29 PASS. Initial inventory drift failed before scoped registration; authority assertions retained. Docs/YAML/manual OpenSpec reviewed, strict CLI unavailable/BLOCKED. Reviewed local commit/final-candidate receipt only.
- [ ] 26.4 Real model/semantic/runtime/full RAG/privacy remain BLOCKED; F2-09 pending and C10 OPEN. No push/upload, new dependency, C17 change, main-spec sync, archive or automatic next item.

## 27. F2-06 optional Cohere/BGE result admission and numerical safety (authorized 2026-10-22)

- [x] 27.1 Record input/result contracts, numerical compatibility, whole-batch fallback and limits before implementation in `docs/50-engineering/optional-rerank-result-boundary.md`.
- [x] 27.2 Implement complete Cohere/index/score and BGE/vector/finite-scalar admission, stable sigmoid/ties and original-source copies; retain budgets/cancel and existing retriever fallback. Factory/stage changes deferred.
- [x] 27.3 Actual-source offline/review PASS: 108 new tests/10 subtests; full 1715 tests + 507 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS, 344 inputs/445 pending sources, C17 29 PASS. Factory/constructors/Bailian/LLM/C17 and existing C07 authority assertions unchanged. Docs/YAML/manual OpenSpec reviewed, strict CLI unavailable/BLOCKED. Reviewed local commit/final receipt only.
- [ ] 27.4 Real SDK/model/semantic/runtime/full RAG/privacy remain BLOCKED; factory/stage follow-up separately authorized in section 28, F2-09 pending and C10 OPEN. No dependency/install/download, push/upload, C17 change, main-spec sync, archive or automatic next item.


## 28. F2-06 factory selection and degradation status (authorized 2026-10-22)

- [x] 28.1 Record selection, cache/profile admission, interruption and stage/C17 compatibility before implementation in `docs/50-engineering/reranker-selection.md`.
- [x] 28.2 Implement fixed provider/selection state, configuration-bound cache admission, interruption propagation and truthful retrieval/log/trace stages; preserve production fail-closed and degradation/C17 semantics.
- [x] 28.3 Synthetic verification/review PASS: 68 new tests/8 subtests; full 1783 tests + 510 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS, 345 inputs/446 pending sources, C17 29 PASS. Five consolidated log expressions account for five fewer automatic subtests; prior assertions/five scorer methods/degradation route/C17 retained. Docs/YAML/manual OpenSpec reviewed; strict CLI unavailable/BLOCKED. Reviewed local commit/final receipt only, then wait.
- [ ] 28.4 Real SDK/model/semantic/runtime/full RAG/privacy remain BLOCKED; F2-09 pending and C10 OPEN. No new dependency, push/upload, C17 change, main-spec sync, archive or automatic next item.


## 29. F2-06 coarse-score and confidence numerical admission (authorized 2026-10-22)

- [x] 29.1 Record raw/visible score admission, unchanged finite handling/weights/thresholds, failure paths and C17 compatibility before implementation in `docs/50-engineering/score-admission.md`.
- [x] 29.2 Implement fixed finite-real admission at store/retriever/knowledge/confidence boundaries without changing legal-score processing, existing authority/fallback semantics or C17.
- [x] 29.3 Synthetic verification/review PASS: 100 new tests/25 subtests; full 1883 tests + 535 subtests, zero skips/xfails/deselections/guard denials; eight checks/Node 69/14/seven assets PASS, 347 inputs/447 pending sources; C17 29 PASS. Exact finite arithmetic/scene compatibility, prior tests/assertions and 74 diagnostics retained; initial inventory drift fixed by scoped registration. Docs/links/YAML/manual OpenSpec reviewed; strict CLI unavailable/BLOCKED. Reviewed local commit/final receipt only, then wait.
- [ ] 29.4 Real SDK/model/semantic/runtime/full RAG/privacy/strict CLI remain BLOCKED; F2-09 pending, C10 OPEN. No dependency, real service, push/upload, C17 change, main-spec sync, archive or automatic next item.


## 30. F2-09 backend samples/C17 provenance preparation (authorized 2026-10-22)

- [x] 30.1 Record the eleven-file documentation-only scope, evidence/rights separation, immutable inputs and acceptance before preparing the worksheet in `docs/50-engineering/license-provenance.md`.
- [x] 30.2 Prepare nine sample/two suite path/hash records, objective local observations and unanswered item/group author questions; retain all pending states without code, corpus, inventory or rights-rule changes.
- [x] 30.3 Scope/binding/immutability review PASS: eleven current/manifest/inventory hashes, four references, local path histories, unchanged 122/6 counts and 447 pending states; 346 local links, YAML/manual scoped OpenSpec and whitespace checks PASS. Tracking documents reconciled; reviewed local documentation commit only, no fresh pytest/runtime claim.
- [ ] 30.4 Supporting author/upstream provenance/permission evidence remains pending (unknown-source replies recorded in section 31); rights/privacy/runtime/full RAG/strict CLI remain pending or BLOCKED, F2-09/C10 OPEN; no push/upload, main-spec sync, archive or automatic next item.

## 31. F2-09 eleven unknown-source responses (authorized 2026-10-22)

- [x] 31.1 Record the plan, exact eleven-item scope, reply/evidence/rights separation and immutable-input acceptance before updating responses in `docs/50-engineering/license-provenance.md`.
- [x] 31.2 Record all eleven received replies as creation/reference sources unknown; update active wording and trackers while preserving prior preparation evidence/template and pending rights, without source/corpus/inventory/rule changes.
- [x] 31.3 Documentation-only verification/review PASS: eleven received/unknown rows, unchanged register/template, eleven current/C17/inventory/baseline hashes, four references, C17 122/6 and all 447 pending states; 350 local links/10 worksheet anchors, YAML/manual scoped OpenSpec and whitespace. Reviewed local documentation commit only, no new pytest/runtime receipt; strict CLI unavailable/BLOCKED.
- [ ] 31.4 Provenance evidence/rights remain pending, runtime/full RAG/privacy/strict CLI BLOCKED, F2-09/C10 OPEN; no push/upload, remote CI, main-spec sync, archive or automatic next item.

## 32. F2-11 current-candidate presentation claims (authorized 2026-10-22)

- [x] 32.1 Record scope, exclusions, historical preservation, evidence levels/revision bindings and exact hash-refresh acceptance before editing in `docs/50-engineering/portfolio-demonstration.md`.
- [x] 32.2 Align the existing walkthrough/current source claims and evidence references, preserve its full historical body and every other old asset, and refresh only its inventory hash/dependent current-manifest inventory hash without rights/rule/code/C17 changes.
- [x] 32.3 Scoped verification/review PASS: nine claim groups/eight named retained tests, source/receipt binding, full historical body/other asset/code preservation, exact two-field hash diff, 347 current inputs/447 pending rights and read-only provenance; 449 local links/47 anchors, YAML/manual scoped OpenSpec/whitespace. Initial anchor failure fixed/rechecked. Trackers synchronized; reviewed local commit only, no fresh suite/demo, strict CLI unavailable/BLOCKED.
- [ ] 32.4 Unknown sources remain pending; runtime/full RAG/privacy/strict CLI BLOCKED, C10 OPEN, F2-11 feedback unvalidated and commercial validation DEFERRED / NOT STARTED; no push/upload, remote CI, main-spec sync, archive or automatic next item.

## 33. F2-10 current-candidate offline reverification and evidence binding (authorized 2026-10-22)

- [x] 33.1 Record the fixed eight-check scope, immutable inputs, no-skip/no-weaker-gate acceptance and clean tested-commit versus later report-commit sequence before execution in `docs/50-engineering/offline-verification.md`.
- [x] 33.2 Unchanged eight checks PASS on clean plan commit `cd34550c3b38de4936903acc8f46bc2f1831620b`: full 1883 tests + 535 subtests, Node 69/14/seven assets; zero skips/xfails/deselections/guard denials. Commit/content/source/aggregate and child-receipt hashes verified, 347 inputs/447 pending rights and C17 unchanged. Execution/binding PASS, overall BLOCKED/UAT-release false, exit 2; strict CLI unavailable/BLOCKED. Complete bindings in `docs/50-engineering/offline-verification.md`.
- [x] 33.3 Receipt/hash/Git-tree/source/immutability and tracking review, 307 local links, YAML/manual scoped OpenSpec and whitespace PASS. Only reports/context/tasks change after the tested commit; no code/manifests/C17/rights changes. Reviewed local documentation-only result commit, explicitly separate from tested `cd34550`, then wait; strict CLI still BLOCKED.
- [ ] 33.4 Real runtime/full RAG/privacy, strict CLI/current remote CI/image/scans, L/D/O/B/S/R matrices, historical credentials and UAT/release remain BLOCKED; unknown-source rights pending, F2-10/C10 OPEN. No push/upload, remote CI, dependency, main-spec sync, archive or automatic next item.

## 34. F2-10 current handover entry and historical labels (authorized 2026-10-22)

- [x] 34.1 Record the documentation-only plan, history/protected-input preservation, existing-gate routing and no-rerun acceptance before organization in `docs/50-engineering/delivery-status.md`.
- [x] 34.2 Organize the current handover route, visible historical labels and exact fourteen-gate decision/tool/environment register; synchronize tracking/OpenSpec without changing code, manifests, C17, rights or receipts.
- [x] 34.3 Historical excerpts/quotation/retained run and normative baseline preserved; protected code/manifests/C17/rights/assets/347 source inputs and receipt hashes unchanged, 447 rights pending. Exact fourteen-gate register, 339 local targets/47 fragments, both YAML documents, manual scoped OpenSpec/tracking and whitespace PASS; strict CLI unavailable/BLOCKED. Reviewed local documentation commit only, no full rerun/new receipt, then wait.
- [ ] 34.4 Strict CLI, current remote CI/image/scans, real runtime/full RAG/privacy, original matrices, historical credentials and enterprise acceptance remain BLOCKED; unknown rights pending, F2-10/C10 OPEN. No install, push/upload, remote CI, main-spec sync, public/commercial track, merge/release, archive or automatic next item.
