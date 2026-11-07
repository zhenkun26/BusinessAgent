## ADDED Requirements

### Requirement: Delivery reconciliation identifies the unreleased candidate honestly
The project SHALL distinguish source version, schema version, Git candidate, image identity,
historical evidence and current acceptance; bilingual entry points SHALL agree on current contracts.

#### Scenario: Offline documentation reconciliation finishes before runtime acceptance
- **WHEN** current documentation, version identities and evidence links are reconciled offline
- **THEN** record that bounded work as complete while C25 and release acceptance remain open; retain runtime blockers and observed CI failures

#### Scenario: A historical manual conflicts with a current contract
- **WHEN** an old example describes automatic initialization, model defaults, state fallback or cleanup
- **THEN** label the historical scope and direct current operations to the reviewed contract without rewriting past test evidence as current acceptance

### Requirement: Final candidate offline receipts preserve evidence boundaries
The project SHALL execute only explicitly reviewed offline entries, bind results to
the candidate and reviewed source identity, and retain skipped/unavailable checks.

#### Scenario: Reviewed sources or candidate change during verification
- **WHEN** the frozen source digest differs or the candidate changes during execution
- **THEN** execution or candidate binding is BLOCKED; stale results cannot qualify the new candidate

#### Scenario: Offline regression succeeds with runtime gates unavailable
- **WHEN** the fixed offline suite completes but runtime, browser, load or recovery evidence is absent
- **THEN** only completed E0/E1 checks are PASS; acceptance stays BLOCKED, C10 stays open and release flags stay false

#### Scenario: Suite fails, skips or reports no tests
- **WHEN** a suite fails, emits malformed/zero-count output, or skips a case
- **THEN** record FAIL or an explicit BLOCKED skip, never count the skipped case as passed, and retain the initial failure and rerun disposition

### Requirement: 工程交付与企业现场验证必须分开判定
项目 SHALL 以单组织、Linux 单机 Compose、真实 PostgreSQL/Redis/Milvus、独立 worker 和一套经过验证的模型 profile 作为首轮工程支持边界，并保留正式企业上线的独立门槛。

#### Scenario: 参考环境验收通过
- **WHEN** 受控参考环境的工程验收全部通过
- **THEN** 结论仅可记为「工程交付验收通过，企业现场生产验证未开展」，不得将 formal_uat、release_evidence 或 release_allowed 改为 true

### Requirement: 差距清单必须具有代码证据和可判定验收
项目 SHALL 在 ISSUES 以 C01–C25 记录现状、源文件、缺口、优先级、日期、状态及验收标准；静态发现与运行验证 SHALL 分别标注。

#### Scenario: 开始处理一个 C 项
- **WHEN** 用户确认推进该项
- **THEN** 实施者先复核该项代码基线与依赖，补齐需要的设计和运行时 delta，再按其验收标准处理，不以历史测试代替当前结果

### Requirement: 交付必须按依赖逐项推进
项目 SHALL 按 ROADMAP 的 S0–S7 及阶段内顺序执行，每个 C 项交付后等待用户确认下一项；完成 S0 SHALL NOT 授权运行时代码修改。

#### Scenario: S0 文档检查完成
- **WHEN** S0 计划、边界、验收标准与索引已落盘
- **THEN** 记录文档验证结果并暂停，所有运行时 C 项仍未完成；不自动启动 S1、推送、合并或部署

### Requirement: 支持声明必须对应可运行的完整链路
项目 SHALL 对部署与模型匹配、权限隔离、会话与跨进程状态、审批幂等与恢复、知识与分析数据、参考集成和 UI 分别保留验收证据，详见 C01–C20。

#### Scenario: 仅有局部测试
- **WHEN** 某能力只有 Mock、单进程或工具层测试
- **THEN** 仅声明该证据覆盖范围，完整应用链路或多进程支持保持未验证，不勾选完整交付验收

### Requirement: 运维与容量必须绑定测量条件
项目 SHALL 按 C21–C23 记录健康/就绪、审计、告警、备份恢复、负载与容量证据，并在执行前固定环境、指标定义和阈值。

#### Scenario: 新候选版本准备验收
- **WHEN** 性能或恢复结果来自旧版本、不同模型或不同部署形态
- **THEN** 将其标为历史参考并执行当前候选复测，不能作为新候选已达标证据

### Requirement: 验收记录必须区分证据等级与失败状态
项目 SHALL 按工程基线记录静态、自动化、完整参考环境、人工交互、企业现场证据；每项使用 PASS、FAIL、BLOCKED 或 NOT_APPLICABLE，并按 C24/C25 绑定最终候选提交。

#### Scenario: 验证工具或外部资源缺失
- **WHEN** OpenSpec CLI、运行环境或企业资源缺失
- **THEN** 相应验证记录 BLOCKED，描述影响，不编造测试结果，不将未执行或文档存在记为 PASS

### Requirement: 参考服务不得替代企业资源确认
项目 SHALL 明确受控 HTTP/IdP 的地址、契约、数据与故障模型，禁止向真实收件人发送验收邮件，并保留既有两个企业相关 change 的阻塞任务。

#### Scenario: 参考集成通过而企业沙箱缺失
- **WHEN** C18/C19 参考链路通过但真实提供方未确认
- **THEN** 只记录工程集成证据，真实 CRM/邮件/IdP 联调、UAT、四周灰度与上线签署继续未完成

### Requirement: 验收必须遵守非破坏性边界
项目 SHALL 在执行验证入口前检查副作用，使用隔离数据与追加式证据，不执行文件系统删除，不触碰既有业务数据，不在证据中记录凭证或私有数据。

#### Scenario: 既有脚本包含自动清理
- **WHEN** 验证或恢复脚本包含删除文件、临时目录或数据卷的行为
- **THEN** 不直接运行该路径，先在授权范围内提供不删除的路径；确需删除时解释原因并交由用户处理

### Requirement: 离线安全入口必须显式允许检查并保护证据
项目 SHALL 提供不新增依赖的离线入口，只执行已审查且源码哈希匹配的函数；验证期间禁止文件修改、网络与子进程；记录输入/源码哈希，输出采用固定字段摘要，证据写入只能创建新文件。

#### Scenario: 源码变更或检查未获允许
- **WHEN** 检查源码哈希不匹配、来源是符号链接或调用者指定任意模块/命令
- **THEN** 在执行前拒绝，不自动更新审查清单，不启动未允许的检查

#### Scenario: 证据目标已存在
- **WHEN** 指定 run ID 已存在或结果路径含符号链接
- **THEN** 拒绝写入且保留原文件，不覆盖、不删除、不自动清理

#### Scenario: 准备度仍阻塞
- **WHEN** 核验函数正常返回但真实 UAT 或发布准备度为 blocked
- **THEN** 分别记录执行成功与业务 BLOCKED，入口返回非零阻塞退出码，正式放行仍为 false

#### Scenario: 输出中可能包含敏感数据
- **WHEN** 原始报告细节或异常消息带凭证、地址或业务文本
- **THEN** 入口只输出受控状态、计数与哈希，不持久化原文或环境变量；失败原因使用固定错误码

#### Scenario: CI collection or regression fails
- **WHEN** the candidate CI cannot collect or pass the complete unit-test suite
- **THEN** repair stale test contracts or implementation defects, retain all tests and security assertions, record exact local and remote verification separately, and keep runtime acceptance blocked


### Requirement: Portfolio purpose does not replace engineering acceptance
The project SHALL identify its current purpose as a backend employment portfolio for future
GitHub open-source presentation, with no current customer deployment or commercial operation
plan. Public presentation, engineering runtime acceptance and commercial readiness SHALL
have distinct conclusions; existing runtime and enterprise evidence gaps SHALL remain explicit.

#### Scenario: The project is prepared for a public portfolio
- **WHEN** positioning and public claims are reviewed without real deployment or enterprise validation
- **THEN** disclose implemented, measured and unverified capabilities separately; do not close C10, relabel BLOCKED gates or assert production/commercial success

### Requirement: Multi-expert review is evidence-led and explicitly scheduled
A future authorized review SHALL cover PM, architecture, QA, product, DevOps, security/privacy,
accessibility, open-source/data compliance, performance and i18n, with added AI assurance and
commercial feasibility perspectives. It SHALL emphasize context management, tool safety and
hallucination handling and produce the requested scorecard, role observations and Top 3 actions.

#### Scenario: Only the review protocol has been recorded
- **WHEN** the committee has not reviewed a frozen candidate
- **THEN** mark review tasks NOT STARTED, assign no numeric scores or expert sign-off, and keep proposed fixes deferred until confirmed

#### Scenario: The committee reports a finding
- **WHEN** a defect, strength or commercial hypothesis is included in the report
- **THEN** record source/evidence scope, distinguish confirmed behavior from assumptions, provide an actionable acceptance standard, and map accepted actions to ISSUES and ROADMAP before implementation
### Requirement: Distribution rights evidence shall remain source-traceable
The project SHALL retain versioned license/source evidence for pinned production
dependencies, browser distributions, other declared profiles and scoped sample/media
assets. Unknown provenance and uninspected distributions SHALL remain pending.
Offline inventory integrity SHALL NOT authorize redistribution or close runtime gates.

#### Scenario: A dependency or sample changes
- **WHEN** a covered package version, source file, notice or declaration changes without reviewed inventory updates
- **THEN** the offline verifier fails with inventory drift and does not grant distribution acceptance

#### Scenario: Publisher metadata or synthetic labels are the only evidence
- **WHEN** a package has only release metadata or a sample is labeled synthetic without author confirmation
- **THEN** preserve the declared evidence verbatim, record the missing wheel/source review and keep rights acceptance BLOCKED

#### Scenario: A new covered asset or unsupported approval is introduced
- **WHEN** a new covered file is unregistered or pending evidence is relabeled approved without an accepted evidence contract
- **THEN** the verifier fails, preserving real runtime/full RAG BLOCKED and C10 OPEN

### Requirement: Portfolio claims shall identify their evidence boundaries
The project SHALL provide a candidate-bound source walkthrough and evidence checklist
that distinguishes Mock data/test doubles, controlled reference services, complete
reference-runtime observations and real-provider acceptance. Historical results SHALL
remain bound to their tested revision and shall not imply current or commercial acceptance.

#### Scenario: A presentation is prepared without a runtime environment
- **WHEN** only source and retained offline evidence are available
- **THEN** label the walkthrough NOT EXECUTED, identify substitutions and missing observations, and keep real runtime/full RAG BLOCKED and C10 OPEN

#### Scenario: Older material or source rights are unresolved
- **WHEN** old interview/speech/deck content contains unreviewed claims or pending-rights assets
- **THEN** register it as historical, omit its unsupported claims/assets from the current script and retain F2-09 pending states

#### Scenario: The user authorizes only a bounded local documentation unit
- **WHEN** preparing the script and reusable review workflow under a minimal-exposure scope
- **THEN** preserve older materials, perform local checks and commit locally only; do not upload, push, start live or commercial validation, or advance the next unit implicitly

#### Scenario: Current candidate claims are aligned after further source changes
- **WHEN** an existing source walkthrough is updated for a later local candidate
- **THEN** retain its complete historical body, bind current source claims and retained results to their respective revisions, preserve Mock/reference/live limits and unknown-source pending states, and refresh only the changed document's existing hash and dependent current-manifest hash without changing rules/counts/rights; runtime/full RAG/privacy remain BLOCKED and C10 OPEN


### Requirement: Independent synthetic RAG safety evidence
The system SHALL keep the F2-06 synthetic injection/negative controls separate from
the frozen C17 datasets and denominators. Reports MUST retain per-case source evidence,
input/code identity and authored-control origin; mechanical checks MUST NOT establish
semantic support, real model robustness or runtime acceptance.

#### Scenario: Authored controls are checked offline
- **WHEN** safe and deliberately unsafe fixture outputs are checked without a model
- **THEN** report checker outcomes with semantic review PENDING, model robustness NOT_MEASURED and quality acceptance BLOCKED, without changing any C17 metric

#### Scenario: Observations are incomplete or invalid
- **WHEN** observations are missing, failed, skipped or empty
- **THEN** preserve every expected case and the independent denominator with no pass credit; reject duplicate, unknown or malformed observations

#### Scenario: A citation index is valid but its claim is unsupported
- **WHEN** a literal or citation probe cannot establish semantic support
- **THEN** retain PENDING semantic review and BLOCKED quality acceptance even when every mechanical probe passes


### Requirement: Current offline evidence has complete reviewed coverage
The project SHALL provide a current-candidate offline check inventory shared by local
execution and CI. It MUST cover complete Python collection, both Node suites and reviewed
asset/build/source/control/preflight entries, with exact source/check membership and no
skipped, xfailed or deselected test acceptance. Historical frozen C24 evidence SHALL remain
separate from the current source review.

#### Scenario: A check, source or tool is missing
- **WHEN** required check/source coverage is omitted or a tool/dependency is unavailable
- **THEN** reject the omission or report BLOCKED without pass/skip credit and prevent CI success

#### Scenario: Child evidence is invalid or changes during execution
- **WHEN** a child fails, times out, returns incomplete/contradictory counts, or source/candidate identity drifts
- **THEN** retain safe per-entry failure evidence, fail execution or block binding, and never rewrite reviewed hashes automatically

#### Scenario: All local checks pass on the stable clean candidate
- **WHEN** the explicit CI mode verifies every reviewed offline entry
- **THEN** permit scoped CI execution success while overall acceptance remains BLOCKED, UAT/release flags false, privacy/rights pending and C10 OPEN

#### Scenario: A later documentation commit reports a fresh local run
- **WHEN** the existing eight checks execute on a clean planning commit and result documents are committed afterward
- **THEN** bind actual tested commit/content/source and retained receipt hashes, identify the later commit as documentation only rather than tested evidence, preserve every failure or missing-tool BLOCKED result without changing counts/gates, and retain runtime/full RAG/privacy/rights limits and C10 OPEN without remote action

#### Scenario: Current handover labels are organized without another test run
- **WHEN** a documentation-only unit separates the current route from dated status and instruction snapshots
- **THEN** retain historical commits/counts/receipts and protected code/manifests/C17/rights, distinguish tested and reporting revisions, classify existing blocked gates with prerequisite/exit evidence without changing their states, preserve prior link targets and keep strict CLI/runtime/full RAG/privacy BLOCKED, unknown rights pending and C10 OPEN; no rerun or external action is implied


#### Scenario: Reranker factory and stage follow-up is verified offline
- **WHEN** synthetic provider/cache/interruption/status cases and the complete current offline entry pass
- **THEN** record scoped F2-06 implementation evidence without changing C17 route classifications or denominators; keep model/semantic/runtime/full RAG/privacy and strict CLI acceptance BLOCKED, F2-09 pending and C10 OPEN; stop after reviewed local commit/final receipt without external action


#### Scenario: Score admission has synthetic evidence only
- **WHEN** raw/visible/confidence numerical admission and the current eight-check entry pass offline
- **THEN** record only scoped F2-06 evidence, preserve finite processing/weights/thresholds and C17 categories/denominators, and keep real model/semantic/runtime/full RAG/privacy and strict CLI BLOCKED, F2-09 pending and C10 OPEN; stop at the reviewed local commit/final receipt


### Requirement: Bounded provenance preparation must not grant source rights
A documentation-only provenance worksheet SHALL bind exactly its authorized paths/hashes,
separate repository observations from author responses and accepted rights, and preserve
pending states when evidence is unknown. Preparing a worksheet SHALL NOT change source
bytes, license admission rules, inventory rights status or C17 definitions/denominators.
Git attribution, root license and synthetic labels SHALL NOT substitute for author/upstream
evidence or privacy acceptance.

#### Scenario: Eleven-file backend batch is prepared
- **WHEN** the nine manifest-bound sample documents and two evaluation sets are recorded
- **THEN** retain complete path/hash identities, separate suite counts and unanswered confirmation questions; leave all source rights pending and runtime/full RAG/privacy BLOCKED, C10 OPEN

#### Scenario: A maintainer authorizes preparation only
- **WHEN** no item-specific authorship/source/permission declaration has been supplied
- **THEN** do not populate confirmations, infer redistribution permission, change policy/status or widen to older presentation materials; stop after reviewed local documentation commit

#### Scenario: All eleven source replies are unknown
- **WHEN** the maintainer individually reports that creation process and reference sources cannot presently be recalled for D01–D09/E01–E02
- **THEN** record the replies as received with unknown provenance, preserve path/hash bindings and prior preparation evidence, and leave supporting evidence/rights pending without changing code, corpus, inventory, admission rules or C17 counts; runtime/full RAG/privacy remain BLOCKED and C10 OPEN
