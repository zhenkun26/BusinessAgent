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
