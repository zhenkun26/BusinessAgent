# Engineering delivery status and handover

Historical review: 2026-10-22. Current integration: see [current handover](#current-handover).
**Historical conclusion (2026-10-22): F2-10 HANDOVER ENTRY / HISTORICAL LABELS ORGANIZED; RETAINED EIGHT-CHECK OFFLINE PASS; SOURCE RIGHTS PENDING; MODEL/SEMANTIC/PRIVACY/RUNTIME BLOCKED; NOT_ACCEPTED_FOR_RELEASE.**
C01–C25 remain open as whole acceptance items. No real enterprise users, formal UAT,
grey release or production approval are established. C10 now has an offline implementation of per-run checkpoint isolation and database-owned
publication. Real two-process race acceptance remains BLOCKED; C10 is not closed.

<a id="current-handover"></a>
## Local/main security integration — authorized 2026-11-07

Subsequent review state: [draft PR #8](https://github.com/zhenkun26/BusinessAgent/pull/8)
contains the integrated candidate. Its initial CI stopped on unsafe matrix record naming
before tests or security scans. The authorized repair preserves the safe-ID validator and
full secret-scan coverage while adding exact cryptographic provenance for manifest false
positives. Current local repair evidence is [recorded here](offline-verification.md#review-ci-repair-20261107);
the next remote run failed at Python child startup. A missing results-parent directory
in fresh checkouts was independently reproduced and narrowly repaired; the new candidate
still requires clean-checkout and remote verification. No merge or deployment is performed.

Additional isolated live checks on the application candidate were reported in the PR:
19 approval assertions, 17 initial C10 assertions, 24 C10 fault checks, five controlled
PostgreSQL restart checks and nine loopback transport cases passed. Actual Edge/InPrivate
used the unchanged frontend with a synthetic API. These are scoped observations, not full
API/model/RAG, enterprise UAT, privacy/rights or release acceptance. Application source is
unchanged by the CI repair.


**IMPLEMENTED / CLEAN-COMMIT OFFLINE PASS / NOT ACCEPTED FOR RELEASE.** The isolated candidate starts at remote main
`f7d684be1a46758bddddc2d13e2a13a33896ba51` and incorporates local engineering candidate
`edc5c58e5783e5c3035d89a035917cae35cb3ef1`, including its 31 engineering commits beyond
remote PR #2 head `716f3b533e6a8693e84e6cb76e098dfd0f20af02`. The five later independent
workflow-document commits, original worktree and older integration draft are not modified.
The fresh three-way application exposed 21 textual conflicts; semantic review also covers
automatically merged files. Plan: [integration change](../../openspec/changes/integrate-local-delivery-security/proposal.md).

Confirmed behavior: approval is decision-only, followed by explicit execution confirmation
by the original requester. Failed/uncertain multi-action work stops for human review without
automatic compensation. Late receipts are read-only evidence and cannot release holds or
trigger retries. Mixed query/write approval plans are rejected with instructions to query
first, then submit the actions separately; the durable action-receipt contract cannot certify
a query as a completed external write. No automatic human-hold release endpoint is supplied.

C10 managed v8, local budgets/privacy/RAG boundaries and main identity/security protections
remain in scope. Managed v9 adds main approval provenance without altering historical
migrations. Main security dependency versions remain; their 12 changed package records,
official wheel hashes and locked inputs are reconciled without adding packages.

Frozen unfiltered tests pass: 2116 tests + 640 subtests, exact dependencies, stable source,
zero failures/skips/xfails/deselections/guard denials, 81.89% coverage. All eight precommit
checks pass, including Node 75/14 and seven assets; 360 reviewed inputs, 98 packages and
457 pending-source records. Clean tested commit `a8c4eec42ec2d44cb8b2e4ae433ccbc88e7021fe` has
execution/binding PASS. Its documentation-only results commit does not change tested inputs. Independent review findings were fixed and regression-tested.
See [integration verification](offline-verification.md#integration-verification-20261107). Earlier 1883-test
receipts below remain bound to their original candidate and do not apply to this integration.
Real PostgreSQL/Redis/concurrency/browser/model/provider acceptance, C10, privacy and source
rights remain open/blocked. No migration, service startup, remote CI, push, merge, deployment,
release or deletion is performed. The main secret-scanner regression suite is retained in CI
but cannot be executed unchanged locally under the no-filesystem-deletion restriction.

<a id="historical-handover-20261022"></a>
## Historical handover entry and labels — authorized 2026-10-22

### Plan recorded before organization

Parent: `2ed1d93cd2bb46a07da098e4f4195aaf1dc35df9`. This documentation-only unit
organizes the handover entry and historical status labels. The latest retained full run
still belongs to tested `cd34550`; `2ed1d93` records its results and is not a tested
revision. This unit creates no new test receipt and does not repeat the eight-check run.

1. Keep this section as the current handover route. Link the existing source-bound
   verification record, acceptance register and execution sequence rather than duplicating
   test data or inventing a fresh candidate result.
2. Label the dated baseline snapshots and old C10 instruction paragraph as historical;
   retain their original commits, counts, results and wording. Preserve existing link
   targets when heading labels change. Engineering requirements below those snapshots
   remain normative; only their historical progress wording is being qualified.
3. Route exactly the existing fourteen blocked-gate identifiers by missing decision,
   tool or real-environment evidence, with exit conditions and existing contract links.
   These are classifications, not new acceptance IDs or permissions. Keep source rights
   PENDING, C10 OPEN and real runtime/full RAG/privacy BLOCKED.
4. Synchronize ROADMAP, ISSUES, agent context and the active OpenSpec change. Preserve
   code, checks, manifests, C17, rights, historical receipts and old presentation assets.
   Do not start the separate public-readiness, enterprise or commercial tracks.
5. Compare protected bytes and retained receipt hashes to the parent; check document
   consistency, local links/anchors, YAML, manual scoped OpenSpec structure and whitespace.
   Strict CLI stays BLOCKED; install nothing. Review and commit locally, then wait.

Acceptance: one unambiguous current route; old status snapshots are visibly historical;
all fourteen existing gates have a prerequisite/evidence route without status or threshold
changes; exact retained evidence identities and all protected files stay unchanged.
Only documentation/context/tasks may change. No full regression, runtime/model/service,
push/upload, remote CI, migration, deletion, main-spec sync, merge/release or archive.

The planning snapshot recorded organization/verification as NOT STARTED. The routes below
and the actual document verification record were added afterward.

### Current entry and evidence boundaries

Start with this section for handover; use [ISSUES](../40-process/ISSUES.md) for acceptance,
[ROADMAP](../40-process/ROADMAP.md#engineering-closeout-stages) for execution order and
the [engineering baseline](engineering-delivery-baseline.md) for unchanged requirements.
The [retained verification record](offline-verification.md#current-candidate-reverification)
binds tested commit `cd34550c3b38de4936903acc8f46bc2f1831620b` and its hashes. Result
documentation was committed as `2ed1d93cd2bb46a07da098e4f4195aaf1dc35df9`; the current
documentation-only unit neither retests that commit nor creates a new result receipt.

Retained evidence remains: eight checks PASS, 1883 tests + 535 subtests, Node 69/14 and
seven assets, zero skips/xfails/deselections/guard denials. Those are observations from
the named earlier run, not newly executed checks in this unit. Its overall status stays
BLOCKED and UAT/release flags false. All 447 source records stay PENDING_SOURCE_REVIEW;
the eleven received creation/reference-source replies remain unknown. C10 stays OPEN.

### Existing blocked gates: prerequisites and evidence routes

These are exactly the existing fourteen runner gate IDs, not additional tests or changed
acceptance states. Decision/tool/environment labels route later work and grant no permission
to install, upload, execute or use private data. A decision alone cannot establish observed
runtime behavior. F2-09 rights remain PENDING, C10 OPEN and real runtime/full RAG/privacy
BLOCKED. Required owners/resources must be confirmed before dependent work starts.

| Existing gate ID | Missing prerequisite / work type | Exit evidence and existing contract |
| --- | --- | --- |
| `REAL_RUNTIME_FULL_RAG` | Decision + real environment: approved candidate, stores, target models and bounded synthetic data | Actual authenticated application/store/model chain, fixed per-case corpus/citation evidence and independent semantic review; [RAG contract](rag-quality.md) and [model profile](../../enterprise-agent/deploy/MODEL_PROFILE.md) |
| `C10_TWO_PROCESS_ACCEPTANCE` | Decision + real environment: isolated PostgreSQL/Redis, authorized schema v8 and at least two API processes | Observed late writer after lease expiry, database clock/transaction ownership, publication/history isolation and fault/restart outcomes; [checkpoint contract](checkpoint-durability.md) |
| `F2_05_PRIVACY` | Owner decisions + real capture: purpose, classification, recipients/regions, access, retention and provider-account evidence | Synthetic SDK/proxy/exporter captures plus outage/error/replay/restore paths; private-data admission stays blocked until separately approved; [privacy contract](data-privacy.md) and [telemetry admission](telemetry-admission.md) |
| `F2_09_SOURCE_RIGHTS` | Maintainer/upstream evidence + actual artifact review; eleven replies are already received/unknown | Supporting source/permission evidence and required wheel/OS/bundled notices, without clearance from root license, hashes or synthetic labels; [pending-source ledger](license-provenance.md#backend-c17-unknown-source-responses) |
| `L01-L16` | Approved load/cost plan + real isolated environment | Fixed hardware/model/corpus/concurrency/mix, real timing/resource/cost observations and every original load case; [capacity contract](capacity-evidence.md) |
| `D01-D16` | Approved recovery operation + isolated volumes/processes | Observed cold snapshot, new-volume restoration, failed-operation recovery and rollback/window outcomes without deleting originals; [retained recovery](retained-recovery.md) |
| `O01-O16` | Real services, independent observers and controlled alert receiver | Observed readiness failures, durable audit/replay, metrics and alerts under the original faults; [observability contract](runtime-observability.md) |
| `B01-B16` | Approved real browser/role/IME/assistive-technology environment | Actual served assets and role flows, focus, keyboard/reader/zoom/contrast evidence; VM results do not close rows; [browser matrix](browser-delivery.md) and [accessibility procedure](keyboard-accessibility.md) |
| `S01-S16` | Controlled IdP/TLS, database/Redis/processes and real browser | Real signature/key/state/expiry/fault and browser handoff outcomes for every original subcase; [controlled SSO matrix](controlled-sso.md) |
| `R01-R20` | Isolated persistent reference HTTP service, API/worker and controlled mail sink | Application-entry authorization, durable effects/receipts, idempotency, approval, Saga/fault and audit evidence; [reference integration matrix](reference-integration.md) |
| `HISTORICAL_CREDENTIALS` | Owner-scoped historical handling decisions and authorized operator access | Reviewed rotation/revocation/exposure disposition and evidence without credential dumps or automatic filesystem deletion; [credential contract](credential-safety.md) |
| `CURRENT_REMOTE_CI_IMAGE_SCANS` | Separate remote authorization + build/scanner tooling | Current revision's full CI, actual immutable image/import/installed inventories and scan evidence; old remote PASS does not transfer; [build contract](../../enterprise-agent/deploy/DEPLOY.md) |
| `OPENSPEC_STRICT` | Tooling decision: compatible CLI availability and separately authorized installation if needed | Actual strict CLI validation; manual links/structure/YAML are recorded separately and cannot replace it; [specification authority](#documentation-and-specification-authority) |
| `ENTERPRISE_UAT_RELEASE` | Separate owner/resources/contracts and acceptance authorization | Real enterprise UAT/grey/release evidence in the independent [integration](../../openspec/changes/crm-mail-sso-integration/tasks.md) and [rollout](../../openspec/changes/uat-and-ga-rollout/tasks.md) changes; no commercial/deployment track starts here |

Only the documentation organization is authorized now. Subsequent tool setup, new source
evidence, browser/isolated-runtime execution, current remote CI and any disclosure each
require their applicable authorization. Follow S0–S7 dependencies rather than treating
this routing table as a new execution order. Public-readiness F4 and commercial validation
remain unstarted/deferred as recorded; no parent F2/C item is closed by this unit.

### Documentation verification and delivery — 2026-10-22

- PASS: exactly fourteen existing blocked-gate IDs, in runner order, have prerequisite/
  evidence routes; classifications change no issue state or acceptance threshold.
- PASS: historical baseline excerpts/positioning paragraph, original C10 quotation and
  retained reverification body are preserved. Baseline sections 1–6 remain byte-identical
  to `2ed1d93`; prior heading fragments still resolve through explicit compatibility anchors.
- PASS: all 347 reviewed source hashes match the unchanged manifest; code/tests/workflows,
  manifests, C17, old interview/assets and the full verification record are unchanged.
  Aggregate/child receipt hashes match the retained record; all 447 source rights remain
  PENDING_SOURCE_REVIEW and the eleven received replies remain unknown.
- PASS: 339 local link targets and 47 fragment references, both YAML documents, tracking
  consistency, manual scoped OpenSpec structure and whitespace. These are document/source
  integrity checks, not another execution of the eight-check suite. No new test receipt.
- BLOCKED: strict OpenSpec CLI is unavailable (exit 127); manual checks do not replace it.
  Real runtime/full RAG/privacy and the original matrices remain BLOCKED, F2-10/C10 OPEN.

Plan, organization and review are complete for this bounded unit (tasks 34.1–34.3);
34.4 remains unchecked. Deliver as a reviewed local documentation commit and wait; its
hash is reported in the handoff without rewriting prior test/receipt identities. No
push/upload, remote CI, installation, runtime/model use, public/commercial track,
main-spec synchronization, merge/release, archive or automatic next item.

<a id="current-f2-10-reverification--2026-10-22"></a>
## Retained F2-10 reverification — tested `cd34550`, results `2ed1d93` (2026-10-22)

Plan recorded after `4570a08`; [scope and evidence-binding sequence](offline-verification.md#current-candidate-reverification).
The existing eight checks, 347 inputs and all counters/gates remain unchanged. Review and
commit the plan, execute on that clean candidate, then record actual tested commit/hashes
in a separate documentation-only results commit. Actual clean tested planning commit:
`cd34550c3b38de4936903acc8f46bc2f1831620b`; unchanged eight checks PASS, full 1883 tests +
535 subtests, zero skips/xfails/deselections/guard denials; Node 69/14/seven assets PASS.
Execution/binding PASS, overall BLOCKED/UAT-release false (local execute exit 2). Full
commit/content/source/aggregate and child-receipt hashes are recorded and verified in
the linked record; 347 inputs and C17 unchanged. The later results commit is documentation
only and was not tested by this run. Receipt/immutability/tracking review, 307 local links
and YAML/manual scoped OpenSpec PASS; reviewed result commit locally, then wait.
Missing tooling stays BLOCKED with no skipped-test credit. All 447 rights
pending, eleven replies received/unknown; runtime/full RAG/privacy/strict CLI BLOCKED,
C10 OPEN. Local commits only, then wait; no push/upload, remote CI or next increment.

## Previous F2-11 source presentation alignment — 2026-10-22

Plan first after `ccd3065`; [current source walkthrough](../../interview/portfolio-walkthrough.md#current-candidate)
and [plan/review record](portfolio-demonstration.md#current-claim-alignment). N01–N09 bind
current source claims to explicit limits; the complete fa1fa05 historical body is retained.
The inspected backend/CI at ccd3065 matched the retained tested `6f5bbd9` source, whose
1883 tests/535 subtests and eight checks passed with overall BLOCKED/UAT-release false.
This update only checks sources/records/documents and refreshes two existing evidence
hashes; it creates no fresh full-suite/current-entry or runtime receipt. Scoped claim/
receipt/history/hash/provenance review, all 347 source bindings, 449 links/47 anchors and
YAML/manual OpenSpec/whitespace checks PASS; an initial evidence anchor was fixed/rechecked.

Old interview/speech/deck/font/screenshot bytes, app/test/C17/CI code and all 447 pending
rights remain unchanged; eleven source replies remain received/unknown. No real demo,
timed rehearsal, browser/provider request, independent feedback or commercial validation.
Strict CLI/runtime/full RAG/privacy BLOCKED, C10 OPEN; F2-11 OPEN, commercial validation
DEFERRED / NOT STARTED. Reviewed local commit then wait; no push/upload, remote CI,
merge/release, main-spec sync, archive or automatic next item.

## Previous F2-09 eleven unknown-source responses — 2026-10-22

Plan first after local `7fad067`; [scope, received replies and unresolved gaps](license-provenance.md#backend-c17-unknown-source-responses).
The maintainer replied individually for D01–D09/E01–E02: specific creation process and
reference sources cannot presently be recalled and are recorded as unknown. All eleven
replies are received, while actual provenance, original/adapted/generated classification,
real-data status and publication authority remain unestablished. No supporting source or
permission evidence was supplied with these replies; all 447 source rights retain
PENDING_SOURCE_REVIEW. Code/corpus/inventory/rules and C17 122/6 remain unchanged.

Hashes/unchanged-register/C17/pending-state checks, 350 local link targets/10 worksheet
anchors, YAML/manual scoped OpenSpec and whitespace PASS. Earlier preparation evidence/
template are historical; no new full pytest, eight-check
candidate receipt, CI/image/model or runtime result is claimed. Documentation-only
verification/review and local commit, then wait. Strict OpenSpec CLI remains unavailable /
BLOCKED; real runtime/full RAG/privacy BLOCKED, F2-09/C10 OPEN. No push/upload, remote CI,
main-spec sync, merge, release, archive or automatic next item.

## Previous F2-09 backend/C17 provenance preparation — 2026-10-22

Plan first after local `6f5bbd9`; [scope, eleven-item worksheet and pending answers](license-provenance.md#backend-c17-confirmation-worksheet).
Exactly nine sample documents and two evaluation sets have full path/hash bindings,
objective local observations and individual/common source questions. At preparation,
author responses were NOT PROVIDED; all eleven and all 447 registered source rights remained
PENDING_SOURCE_REVIEW. No code, corpus, manifest, inventory or admission-rule changes;
C17 stays 122 primary/6 supplemental with its existing categories and metrics.

This is documentation preparation, not source confirmation, privacy clearance or a new
model/runtime result. Previous implementation evidence belongs to its tested revision;
the most recent score-admission increment was locally committed as `6f5bbd9` (see
[its evidence](score-admission.md)). No full pytest/current eight-check/CI/image or live
execution is claimed for this prose-only increment. Documentation-only checks and local
review/commit are recorded in the worksheet. Strict OpenSpec CLI remains unavailable /
BLOCKED; F2-09 and C10 OPEN, real runtime/full RAG/privacy BLOCKED. Stop for confirmation
after the local commit; no push/upload, merge, release, main-spec sync or archive.

## Previous F2-06 optional Cohere/BGE result boundary — 2026-10-22

Plan first after local `22492ab`; [scope, compatibility and evidence](optional-rerank-result-boundary.md).
Strict complete Cohere indices/finite scores and BGE vector/cardinality/real-scalar
admission, stable sigmoid/ties and original-source copies. Invalid batches fail for
existing coarse/vector fallback; budget/cancel propagate. Full Cohere text/BGE prefix
payloads retained. No factory/constructor/default-profile/LLM/C17 change.

- **PASS:** 108 new tests/10 subtests; full **1715 tests + 507 subtests**, zero skips/xfails/
  deselections/guard denials; 45 existing warnings. C17 29 PASS. C07 NumPy stub adapts only
  its ndarray type, retaining all authority/source assertions. Eight current offline checks PASS;
  344 reviewed inputs/445 pending sources, Node 69/14/seven assets/98 pins unchanged.
- **Limits:** tests use doubles/existing NumPy; SDK compatibility, model output meaning,
  semantics/privacy/runtime/full RAG and strict CLI BLOCKED. Factory/stage follow-up deferred,
  F2-09 pending and C10 OPEN; valid scores still do not certify relevant/true source content.
- **Delivery:** review/local commit/final receipt only. Precommit
  `offline/f206-optional-rerank-precommit-20261022.json` has binding BLOCKED while dirty;
  final `offline/f206-optional-rerank-final-20261022.json` follows the commit. Overall
  BLOCKED/release/UAT false. No push/upload, dependency/install/download, main-spec sync,
  archive or automatic next item.

## Previous F2-06 optional LLM rerank boundary — 2026-10-22

Plan first after local `5bbf68b`; [scope, compatibility and evidence](llm-rerank-trust-boundary.md).
Fixed policy over selected system/human tasks, separate query/prefix JSON, strict ASCII
0–10/no-call replies, original source/ACL copies and stable ties. Ordinary failures
invalidate the entire batch for existing coarse/vector fallback; interruptions propagate
and score drafts stay hidden. Default profile/factory/Bailian/Cohere/BGE remain unchanged.

- **PASS:** 85 new tests/3 subtests; full **1607 tests + 497 subtests**, zero skips/xfails/
  deselections/guard denials; 45 existing warnings. Eight checks/Node 69/14/seven assets
  PASS, 342 inputs/444 pending sources; C17 29 PASS. The adapted C07 model double retains
  every authority assertion. The initial inventory drift failed honestly, then passed
  after registering scoped test evidence; no weakened gate or diagnostic removal.
- **Limits:** a syntactically valid high score for a poisoned chunk remains possible.
  Scores do not certify truth or model resistance. Cohere/BGE deferred; real model/event
  transport/runtime/full RAG/privacy and strict CLI BLOCKED, F2-09 pending, C10 OPEN.
- **Delivery:** reviewed local commit/final receipt only. Precommit
  `offline/f206-llm-rerank-precommit-20261022.json` has binding BLOCKED while dirty;
  `offline/f206-llm-rerank-final-20261022.json` follows the local commit. Overall BLOCKED,
  release/UAT false; no push/upload/remote CI, main-spec sync, archive or next item.

## Previous F2-06 chitchat fallback boundary — 2026-10-22

Plan first after local `d5e028c`; [scope, compatibility and evidence](chitchat-trust-boundary.md).
Fixed read-only System policy/separate message JSON, no display-name interpolation,
strict text/native-call/size admission and one fixed failure fallback. Budget/cancellation
propagate; candidate chunks stay hidden even with inherited final tags. Generated replies
are labeled literal chat data, not business-state evidence. No tool or summary authority.

- **PASS:** 57 new cases; full **1522 tests + 494 subtests**, zero skips/xfails/deselections/
  guard denials, 45 existing warnings. One removed length log explains one fewer automatic
  diagnostic subtest (80 to 79); no existing assertions changed. Eight checks/Node 69/14/
  seven assets PASS, 340 inputs/443 pending sources. C17 29 and five parser cases/two unsafe
  controls PASS. Non-chitchat aggregation AST and other authority/frozen inputs unchanged.
- **Limits:** a short false claim can pass text admission; the label is not a semantic
  verifier. Messages may contain private data despite username omission. Optional reranking
  deferred; real model/browser/API/runtime/full RAG/privacy and strict CLI BLOCKED,
  F2-09 pending, C10 OPEN. Chitchat confidence remains a heuristic.
- **Delivery:** reviewed local commit/final receipt only; precommit
  `offline/f206-chitchat-precommit-20261022.json` execution PASS/binding BLOCKED while dirty.
  Final `offline/f206-chitchat-final-20261022.json` follows the local commit; overall
  BLOCKED/release/UAT false. No push/upload/remote CI, merge, release, main-spec sync,
  archive or automatic next item; wait for confirmation.

## Previous F2-06 non-knowledge result boundary — 2026-10-22

Plan first after local `c0ca3b5`; [scope, compatibility and evidence](nonknowledge-result-boundary.md).
Multiple non-knowledge results now use structured-status composition without a summary
model or draft stream. Pending approvals, direct calls, Saga compensation/unresolved
results and all failures remain distinct. Action prose is literal quoted data; analysis
numbers, single-result/knowledge behavior and request/C10/SSE publication remain intact.

- **PASS:** 49 new cases; full **1465 tests + 495 subtests**, zero skips/xfails/deselections/
  guard denials, 45 existing warnings. Two removed logging expressions explain two fewer
  automatic diagnostic subtests (82 to 80), with no weaker assertions. Eight checks/Node
  69/14/seven assets PASS; 338 inputs/442 pending sources. C17 29 PASS, frozen inputs and
  denominators unchanged. Five bundled-parser cases/two unsafe controls PASS.
- **Limits:** snapshot status is not a fresh provider query. Single-call false outcomes
  cannot distinguish failure from unknown effects; no prose-based guessing. Single/mixed
  knowledge paths retain previous behavior. Chitchat/reranking deferred; real model/tool/
  runtime/full RAG/privacy BLOCKED, F2-09 pending, C10 OPEN; strict CLI unavailable/BLOCKED.
- **Delivery:** reviewed local commit and final candidate receipt only. Precommit receipt
  `offline/f206-results-complete-review-20261022.json` execution PASS/binding BLOCKED while
  dirty; final `offline/f206-results-final-20261022.json` follows the local commit. Overall
  BLOCKED, release/UAT false. No push/upload/remote CI, merge, release, main-spec sync,
  archive or automatic next item; wait for confirmation.

## Previous F2-06 Planner/tool proposal boundary — 2026-10-22

Plan first after local `8edaf00`; [scope, compatibility and evidence](planner-tool-trust-boundary.md).
Fixed selected-template policy and JSON data roles cover Planner and tool selection.
Action tasks must quote the current request; executor and selector recheck the binding.
Strict complete proposals and parameter/role checks precede approval/dispatch; empty or
failed selection no longer creates keyword-derived recipients/IDs. Planning draft streams
are hidden. Existing current-identity gateway/approval/idempotency/Saga authority is retained.

- **PASS:** 61 new cases; full **1416 tests + 497 subtests**, zero skips/xfails/deselections/
  guard denials, 45 existing dependency warnings; eight checks/Node 69/14/seven assets PASS.
  Reviewed 336 source inputs and 441 pending-source records. C17 contracts 29 PASS; frozen
  corpus/evaluator/denominators and historical C24 inputs unchanged. No new dependency.
- **Limit:** literal excerpts and schema/allowlist checks do not prove user intent or
  semantic correctness. A wrong identifier remains a deliberate admitted-proposal example.
  Provider payload now explicitly includes current request plus its task/catalog; privacy
  acceptance remains BLOCKED. Other agent prompts and real model/tool/full RAG unaccepted.
- **Delivery:** single-agent local diff/manual structure review; strict CLI unavailable /
  BLOCKED. Precommit `offline/f206-planning-review-20261022.json` execution PASS, binding
  BLOCKED while dirty; final local candidate receipt `offline/f206-planning-final-20261022.json`
  follows the reviewed local commit. Overall remains BLOCKED, release/UAT false. No push,
  upload, remote CI, merge, release, main-spec sync or archive. F2-09 pending, C10 OPEN;
  stop and wait for confirmation.

## Previous F2-06 read-only RAG production boundary — 2026-10-21

Plan first after local `8e30338`; [scope, compatibility and evidence](rag-trust-boundary.md).
Fixed policy covers effective knowledge prompt versions and JSON data roles; raw call/
citation failures stop before answer publication. Draft/evaluation SSE text is suppressed;
knowledge composition retains text without model rewriting and maps final source indices.

- **PASS:** 53 new cases; full **1355 tests + 484 subtests**, zero skips/xfails/deselections/
  guard denials, 45 existing dependency warnings. Eight checks PASS; Node 69/14, seven
  assets, 334 reviewed inputs and 440 pending source records. Valid-citation semantic
  false positives remain explicit; no model resistance/factual score is claimed.
- **PASS:** C17 inputs/evaluator/denominators, current registry/defaults, planner/tool
  authority, dependencies/CI/Docker and historical C24 retained. Five old fixtures adapt
  to data roles and valid source/refusal contracts with original assertions preserved.
- **OPEN / BLOCKED:** other agent prompt boundaries, actual model/adversarial/semantic/
  privacy/runtime/full RAG and all prior live matrices/current remote CI. Strict OpenSpec
  CLI unavailable; F2-09 rights pending, C10 OPEN. F2-06 and parent items remain OPEN.

Reviewed local commit and final clean-candidate offline receipt only, then wait.
No push/upload, real model/service, new dependency, migration, deployment, merge,
release, main-spec sync or archive.

## Previous F2-05 automatic telemetry admission — 2026-10-21

Plan first after local `c5240ad`; [policy, limits and retained evidence](telemetry-admission.md).
Default-disabled process/effective Settings validation runs before covered SDK/client
imports and model probes; API/worker and tracing factories recheck cached configuration.
Only explicit synthetic OTEL is admitted. Unknown SDK export/capture options and requested
SDK failures stop with fixed errors; no configuration/endpoint/exception echo.

- **PASS:** 84 new tests; full **1302 tests + 484 subtests**, zero skips/xfails/deselections/
  guard denials, 45 existing dependency warnings. Eight current checks PASS, Node 69/14,
  seven assets, 332 reviewed inputs, 439 pending-source records.
- **PASS:** C21 audit/replay/readiness/metrics/service bytes and existing assertions
  preserved. Five older startup/queue fixtures model the new dependency/binding. No
  dependency, schema, CI/Docker, C17 or historical C24 recipe changes.
- **LIMIT:** pinned production inventory lacks the optional OTLP exporter and requests/
  Redis instrumentors. Nothing installed/added; explicit enablement fails closed when
  unavailable. Recording doubles do not prove operational tracing or privacy.
- **OPEN / BLOCKED:** real SDK/proxy/provider/privacy, runtime/full RAG, C10 two-process,
  original L/D/O/B/S/R matrices, current remote CI and strict OpenSpec CLI (unavailable).
  F2-09 rights pending; C10 OPEN. Whole parent acceptance is not closed.

Reviewed local commit and final clean-candidate offline receipt only, then wait.
No push/upload, real service/model, new dependency, migration, deployment, merge,
release, main-spec sync or archive.

## Previous F2-10 offline entry and CI prerequisite — 2026-10-20

Plan first after `f3a7c2e`; [current inventory, retained writes and evidence](offline-verification.md).
Eight explicit checks cover full Python tests, both Node suites, assets, build inputs,
pending-source integrity, synthetic RAG controls and safe preflight. The same command is
in the local CI recipe. Historical C24 source inventory/runner and business behavior remain
unchanged. No remote workflow, artifact upload, image build or service/model is executed.

- **PASS:** 35 new omission/tool/failure/drift/no-skip/record/CI counterexamples; full
  **1218 tests + 484 subtests**, zero skips/xfails/deselections/guard denials; 45 existing
  dependency warnings. Node 69/14 and seven assets PASS. All eight checks execution PASS.
- **PASS:** 330 current source/config/data/workflow inputs reviewed; source/provenance
  integrity (438 pending records), original modes/diff/link/manual OpenSpec review.
  Existing security/image/scanner gates retained; missing coverage now fails the CI job.
- Precommit run remains binding BLOCKED while dirty. Exact final-commit identity and
  clean CI-mode receipt are retained under ignored `eval/results/offline/`; CI-mode
  exit success represents offline execution only, with overall acceptance BLOCKED.
- **OPEN / BLOCKED:** current remote CI/image/scans, strict OpenSpec CLI (unavailable),
  real runtime/full RAG, L/D/O/B/S/R and historical credential gates. F2-05 privacy and
  F2-09 rights pending; C10 OPEN. F2-10/C24/C25 remain OPEN as whole acceptance items.

Local review/commit and final-candidate local recheck only, then wait. No push/upload/
dispatch, dependency addition, migration, merge, release, deployment, main-spec sync or archive.

## Previous F2-07 keyboard, control names and status at `f3a7c2e` — 2026-10-20

Plan first after `182c252`; [scope, evidence and B15 subcases](keyboard-accessibility.md).
Existing page actions now use native keyboard controls, associated/contextual labels,
composition-aware Enter, visible/owned focus and fixed request lifecycle summaries.
Per-token answers/timers remain outside live regions; stream validation controls completion.

- **PASS:** 21 new Node VM/compile cases (69 page cases total); 14 existing credential/
  sanitizer cases; all seven retained distribution/license assets. The old credential fixture
  now supplies Vue's `$nextTick` and `$refs`; no test skip or weaker security assertion.
- **PASS:** 8 new Python source tests/46 subtests; full **1183 tests + 484 subtests**, zero
  skips/xfails/guard denials, 45 existing dependency warnings. Declared versions matched;
  test source stayed stable. VM/compile/source checks do not establish native DOM behavior.
- **PASS:** pending-source inventory integrity (437 records), source/diff/link/manual OpenSpec
  review; safe_validate execution PASS with overall BLOCKED. Strict CLI unavailable/BLOCKED.
- **OPEN / BLOCKED:** actual browser/IME/keyboard/reader/200% zoom/contrast, B01–B16, real
  runtime/full RAG and current remote CI. F2-05 privacy, F2-09 source rights and C10 real
  two-process acceptance remain unaccepted; C10 stays OPEN. F2-07 remains OPEN as a whole.

Local review and commit only, then wait. No push/upload, dependency, migration, model/service
call, merge, deployment, release, main-spec sync, archive or automatic next item.

## Previous F2-06 RAG injection and negative controls at `182c252` — 2026-10-20

Plan first after `4247cdf`; [eight synthetic controls and evidence boundaries](rag-safety-controls.md).
Three evaluation files and one test module are added; production prompts/code and all C17
corpus/evaluator bytes remain unchanged. No model, service or private data was used.

- **PASS:** 19 new Python tests/47 subtests; focused 48 tests + 47 subtests; full **1175 tests
  + 438 subtests**, zero skips/xfails/guard denials, 45 existing dependency warnings.
  Original C17 offline entry: 29 tests PASS; original 115/7 and 2/4 denominators unchanged.
- **PASS:** synthetic checker entry: eight safe/unsafe pairs match declared mechanical
  expectations. This does not measure model resistance or semantic support. Actual generation
  method/default-prompt assembly was characterized with local doubles, not a full pipeline.
- **PASS:** inventory integrity (436 pending records), frozen-byte/source/diff/link/manual
  OpenSpec review; safe_validate execution PASS with overall BLOCKED. Strict CLI unavailable.
- **OPEN / BLOCKED:** F2-06/C17 real model/adversarial and independent semantic acceptance;
  F2-05 privacy/provider/automatic telemetry; F2-09 source rights; real runtime/full RAG,
  previous live matrices and C10 two-process acceptance. C10 remains OPEN.

Local review and commit only, then wait. No push/upload, migration, dependency, merge,
release, deployment, main-spec sync, archive or next increment is performed or authorized.

## Previous F2-05 data-flow and privacy boundary at `4247cdf` — 2026-10-20

Plan first after `39ea39c`; [data categories, recipients and admission boundary](data-privacy.md).
53 covered operational log calls omit content/identity/exception bodies. Application-owned
manual tracing uses fixed names and typed metadata; prompts, results, ACLs, audit/replay and
business persistence retain their behavior. This is not general PII classification.

- **PASS:** 17 new synthetic Python tests; focused 75 tests + 164 subtests;
  full **1156 tests + 391 subtests**, zero skips/xfails/guard denials, 45 dependency deprecation warnings.
  C06 20, C08 23, C17 29 and C21 45 offline cases PASS.
- **PASS:** pending-source inventory integrity (432 entries), safe_validate execution;
  its overall result remains BLOCKED. No dependency, schema, database or provider changes.
- **OPEN / BLOCKED:** F2-05 private-data admission; provider retention/training/region/terms,
  real egress, automatic SDK/proxy logging, cross-store audit/replay/backup disposal, current
  remote CI and strict OpenSpec CLI. Source-level maps and synthetic captures do not waive them.
- F2-09 sources remain pending; C10 OPEN; real runtime/two-process/full RAG and existing
  live matrices remain BLOCKED. No real service/exporter call, upload or deletion performed.

Local review and commit only, then wait. No push/upload, merge, deployment, release,
main-spec sync, archive or commercial validation.

## Previous F2-08 citation time at `39ea39c` — 2026-10-20

Plan first after `8773639`; [contract and evidence](citation-time.md). New citation epoch
seconds become aware UTC at source construction. Existing naive history keeps its fields
and absent offset; no timezone inference or database migration. Existing UI code is unchanged.

- **PASS:** 51 focused tests + 68 subtests; complete local pytest **1139 tests + 288 subtests**,
  zero skips/xfails/guard denials (45 dependency deprecation warnings). Five new Python
  tests and 39 new subtests; 48 Node VM cases, including three new timezone cases.
- Real Redis serializer with service/handler doubles is offline evidence, not a live Redis
  round trip. Current Chinese UI scope retained; VM formatting is not browser evidence.
- Inventory now covers 431 pending sources; only the new fixture and three changed test
  hashes are refreshed. All author/upstream rights remain pending. No dependency, database,
  deployment, frontend asset, old interview/deck or language-framework changes.
- Real browser/runtime/two-process/full RAG, prior live matrices and strict OpenSpec CLI
  remain BLOCKED; F2-08 whole finding and C10 remain OPEN. No current remote CI claim.

Local review and commit only; wait before the next increment. No push/upload, merge,
release, deployment, main-spec sync or archive. Commercial validation remains deferred.

## Previous F2-11 presentation preparation at `8773639` — 2026-10-20

Plan first after `fa1fa05`; one [source walkthrough/evidence checklist](../../interview/portfolio-walkthrough.md)
and a [reusable bounded-review workflow](portfolio-demonstration.md). The user's scope
refinement keeps old interview notes, speech, HTML deck and assets unchanged. No upload.

- **PASS (E0/integrity):** local source/claim/link/inventory/manual OpenSpec-structure checks. No new application
  behavior, dependency, runtime rehearsal or full pytest run. The 1134/249 result below
  remains the previous F2-09 baseline's evidence, not a fresh test result for this slice.
- F2-09 current inventory adds one pending source record (430 total); no source or license
  is cleared. Independent audience feedback is unvalidated; commercial validation is
  DEFERRED / NOT STARTED. F2-11 remains OPEN as a whole finding.
- Real runtime/full RAG, all prior live matrices and strict OpenSpec CLI remain BLOCKED;
  C10 remains OPEN. Local commit only, then wait; no push, upload, merge, publication,
  deployment, main-spec sync or archive.

## Previous F2-09 license and source inventory at `fa1fa05` — 2026-10-20

Plan first after `c518a2a`, then 98 production package declarations, 3 browser packages,
429 scoped source/data/media records, 32 dependency/profile/tool declaration inputs and
[third-party notice index](../../THIRD_PARTY_NOTICES.md). No application, dependency or
packaging change. [Plan, confirmation queue and evidence](license-provenance.md).

- **PASS:** 36 new offline cases; full 1134 tests + 249 subtests, zero skips/xfails/guard
  denials. Inventory, unchanged F2-04 inputs and 7 frontend distribution files verify.
- **OPEN / BLOCKED:** author/source confirmation, 217 font binaries, 18 screenshots,
  actual Linux wheel/native/OS notice inventory and compatibility/distribution review.
  Publisher metadata and synthetic labels are recorded without inventing rights.
- **BLOCKED:** strict OpenSpec CLI, real runtime/two-process/full RAG and prior acceptance
  matrices; C10 remains OPEN. No current remote CI/build/security-scan claim.

Local commit only, then wait. No push, merge, publication, deployment, main-spec sync,
archive or next finding. Offline integrity does not authorize redistribution.

## Previous F2-04 build inputs at `c518a2a` — 2026-10-20

Plan first, then reviewed Python/frontend digests, dated signed Debian sources, 98 exact
Python pins/114 compatible wheel hashes, and final installed-set verification with CI
image inventory/identity artifacts. Range upgrades are removed. NumPy is fixed at 2.4.6
for current 3.11/3.13 support; no new dependency or schema. Previous SSE commit: `e3831b3`.

- **PASS:** 50 new offline cases; full 1098 tests + 249 subtests, zero skips/xfails/guard
  denials; read-only input and four Dockerfile checks; safe_validate execution PASS with
  overall BLOCKED. Source/diff, syntax/link/manual OpenSpec and preservation checks pass.
- **PASS:** public metadata lookup/digest chain for official images and declared wheels;
  this is input provenance, not installed-image evidence. [Plan, update procedure and
  receipts](../../enterprise-agent/deploy/DEPLOY.md#f2-04-offline-delivery-evidence--2026-10-20).
- **OPEN / BLOCKED:** F2-04 two-build/image/scan acceptance, real runtime/full RAG and C10.
  The contract covers production Linux amd64/Python 3.13 only; experimental profiles and
  floating CI test/toolchain inputs are disclosed separately. No identical OCI byte claim.
- **BLOCKED:** actual Linux installation/build/import/inventory/security scans, current
  remote CI and strict OpenSpec CLI; all preceding runtime gates remain unchanged.

Stop after local commit, no push/merge/release/deployment/spec sync/archive or next finding.

## Previous F2-03 SSE slice at `e3831b3` — 2026-10-20

Plan first, then bounded SSE queue/bytes/frame sizes, independent terminals, pre-publication
final validation, cooperative send/lifetime limits and explicit producer cleanup. Fixed
error/cancel paths cannot deadlock on a full queue; failures after acknowledged publication
do not downgrade completed state. The execution slice remains at `d52707f`.

- **PASS:** 41 new cases; related 120 tests + 45 subtests; full retained pytest 1048 tests +
  249 subtests, zero skips/xfails/guard denials, 75.64% coverage; five related guarded eval
  entries pass 124 overlapping cases. Review findings were fixed and rerun.
- **PASS:** source/diff review, Python 3.11 syntax, local links, YAML/manual OpenSpec shape,
  original modes and unrelated work preservation; evidence binds tested code to the local
  commit. [Limits, failed runs and receipts](request-context.md#f2-03-sse-delivery-evidence--2026-10-20).
- **OPEN / BLOCKED:** F2-03 runtime acceptance and C10. No process-wide RSS bound, guaranteed
  cancellation of hostile I/O, transport delivery or rollback of committed effects is claimed.
- **BLOCKED:** real two-process/API/SSE/browser/proxy/store/provider/Linux and full RAG;
  prior acceptance matrices, current remote CI and strict OpenSpec CLI remain unaccepted.

Local commit only; no new dependency declaration or schema. Existing declared wheels were
restored in an isolated temporary dependency view. Wait for confirmation before another
finding or remote action; no push/merge/release/deployment/spec sync/archive.

## Previous F2-03 execution-budget slice at `d52707f` — 2026-10-19

Plan saved before implementation, then request-owned task/concurrency/history/model
admission budgets added. Fixed failures bypass ordinary fallbacks and prevent successful
checkpoint publication. The 120-second deadline checks new admissions and final success;
it does not force-stop in-flight synchronous I/O or provide SSE backpressure.

- **PASS:** 34 new focused cases; final full pytest 1007 tests + 249 subtests, zero skips,
  xfails or guard denials; 75.12% local coverage. Eight related offline eval entries pass
  224 overlapping test executions. Initial fixture/import failures were corrected and rerun.
- **PASS:** diff/source review and pre-commit checks; see [plan, contract and retained
  evidence](request-context.md#f2-03-delivery-evidence--2026-10-19).
- **OPEN at that delivery:** F2-03 as a whole; SSE then required separate confirmation (subsequently delivered above). C10 remains open.
- **BLOCKED:** real runtime/two-process/provider/Linux, full RAG and prior acceptance matrices,
  current remote CI and strict OpenSpec CLI. No new dependency or schema.

Local commit only, no push/merge/release/spec sync/archive. Stop for confirmation; do not
continue to SSE or another finding automatically. The SSE slice was later separately confirmed above.

## Previous F2-02 fix at `23309f7` — 2026-10-19

Plan saved before implementation, then Redis rate-limit failure policy and recovery updated.
Non-dev returns fixed 503 without memory admissions; dev retains and labels local windows.
Per-process five-second cooldown/single probe, bounded calls, zero SDK retries and failure
ordering permit recovery without restart. Unique transactional observations prevent equal
request timestamps from overwriting each other. F2-01 identity policy remains intact.

- **PASS:** 3 expected pre-fix counterexamples; 18 new recovery cases within 61 focused tests.
- **PASS:** C09 offline eval 28 tests; full local pytest 973 tests + 249 subtests, zero skips,
  xfails or guard denials; 74.54% local line coverage on macOS arm64 Python 3.13.15.
- Source hashes, documentation, manual OpenSpec structure and original modes are checked
  before commit; results and limitations are in [the delivery evidence](cross-process-state.md#f2-02-delivery-evidence--2026-10-19).
- **BLOCKED:** actual Redis/proxy/two-process/Linux/runtime, current remote CI, strict OpenSpec
  CLI and full RAG; prior L/D/O/B/S/R and credential gates remain. C10 is open.

Full receipt: `enterprise-agent/eval/results/ci-pytest-ca8ea48b96c1485eb1fc588ab7063f51/receipt.json`.
No dependencies, schemas, deployment or other service behavior changed. The historical audit
is unchanged; ISSUES carries current resolutions. At that delivery, the next step was separate confirmation of a bounded F2-03
resource-budget slice (now recorded above). Review/local commit only; no push, merge, release or archive.

## Previous F2-01 fix at `6832527` — 2026-10-19

After confirmation, implement only the limiter identity trust finding. Shared signed-token
validation replaces unsigned sub parsing; login remains source-IP based, oversized credentials
cannot reach middleware JWT decoding, and business current-account checks remain mandatory.
The bounded plan and evidence are in [the authorization contract](runtime-authorization.md#f2-01-delivery-evidence--2026-10-19).

- **PASS:** expected red run (24 failing counterexamples, 6 passing cases), followed by all
  30 new cases passing; related 87 tests + 35 subtests and C05 eval 29 tests PASS.
- **PASS:** full retained pytest 955 tests + 249 subtests, zero skips/xfails/guard denials;
  74.11% local line coverage, macOS arm64 Python 3.13.15 with declared dependency view.
- **PASS:** final application/test/eval bytes bound to the full receipt; document links,
  YAML/manual OpenSpec structure and original modes/unrelated bytes checked before commit.
- **BLOCKED:** real Redis/proxy/PostgreSQL/API/Linux, current remote CI, strict OpenSpec CLI,
  previous live matrices and full RAG. C10 stays open; quota tests are not account-store UAT.

Full receipt: `enterprise-agent/eval/results/ci-pytest-611fbd37489749499a215b3b1eb6b195/receipt.json`.
No dependencies, schemas, Redis degradation policy or deployment settings changed. F2-02
is the proposed next increment, awaiting confirmation. Review/local commit only; no push,
merge, release, deployment, main-spec sync or archive.

## Previous F2 audit at `edf5f63` — 2026-10-19

After confirmation, freeze `c57d4738e3abe75c640a90896fe2d993ac37efc1` and complete
[the twelve-perspective report](../40-process/multi-expert-review-c57d473.md). This is one
agent simulating roles, not independent expert certification. Eleven findings are registered
in ISSUES with parent C items, triggers and acceptance criteria. F2-01 is a confirmed offline
rate-limit identity defect: unverified JWT sub can rotate buckets or consume a target key.
It does not establish application-authentication bypass. No application fix is included.

- **PASS:** isolated actual-source limiter reproduction; 11 rotated unsigned subjects reach
  the downstream 401 double, versus 429 on the 11th anonymous request; victim-key exhaustion
  rejects before downstream. No live HTTP/Redis/account, network, write or deletion action.
- **PASS:** 219 Python hashes still match the retained full-suite binding at `c57d473`.
  The 925 tests + 249 subtests result is prior evidence, not a new full-suite run.
- Document links, YAML, manual OpenSpec structure and unchanged code/modes are checked for
  this documentation increment; detailed results are recorded in the report validation section.
- **BLOCKED:** OpenSpec strict CLI (unavailable), current remote CI, all live matrices,
  real two-process/runtime/full RAG, and commercial/enterprise acceptance. C10 stays open.

F2 is complete; F3 triage is recorded but implementation awaits confirmation. Recommend
F2-01 as the next bounded increment, keeping Redis degradation F2-02 separate. Only local
review/documentation commit; no push, merge, publication, deployment, spec sync or archive.

## Previous C10-R1/R2 follow-up at `c57d473` — 2026-10-19

Following explicit confirmation after `c0a4464`, the implementation plan was recorded in
[the checkpoint contract](checkpoint-durability.md) and OpenSpec before code changes.
R1 shares validated JSON-safe source projection across message, SSE and owned history;
invalid sources cannot publish success. R2 filters before counting eligible turns, under
one 100-snapshot/five-second budget, preserving privacy/failure/fencing guarantees.
Raw checkpoint state, schema and dependencies are unchanged. The history snapshot API
adds public `sources`; malformed persisted citations now return a fixed checkpoint error.

- **PASS:** 25 new focused offline cases, including installed Redis serializer round-trips.
- **PASS:** complete local pytest **925 tests + 249 subtests**, zero skips, zero guard
  denials, 74.02% local line coverage; macOS arm64 Python 3.13.15, declared dependency view.
- **PASS:** final application/test/eval bytes match the full-suite receipt after document updates.
- **PASS:** document links, YAML, diff checks and manual OpenSpec structure (23 deltas,
  110 requirements, 156 scenarios); original modes and unrelated tracked bytes preserved.
- **BLOCKED:** current remote CI, OpenSpec strict CLI, actual dual-process/store/API/Linux,
  all prior live matrices and full RAG; parent C10 and runtime task 3.3.2 remain unchecked.

Full-suite receipt: `enterprise-agent/eval/results/ci-pytest-7eae3e64ad024471a4d6acdf2110dc3b/receipt.json`.
This precommit receipt records parent `c0a4464` plus tested source hashes, including new
untracked Python tests/entry. A retained postcommit binding will compare those same code
bytes to the final commit without claiming a fresh CI/runtime run. The initial full run
found one state-shape regression (924 passed, one failed); the implementation was fixed
without changing or skipping its existing assertion. Earlier failed receipts are retained.
See [full follow-up record](../40-process/阶段性总结_C10检查点持久化与故障语义.md#c10-r1r2-follow-up--2026-10-19).

That increment stopped at local commit with the committee review pending. The subsequently
confirmed F2 scope and results are recorded above; no historical runtime evidence is upgraded.

## Historical planning decision at `c0a4464` — 2026-10-19

The user confirmed a future GitHub open-source/backend-employment portfolio, with no current
customer deployment or commercial operation plan. Retain real-project engineering discipline
and separate public presentation from runtime/commercial acceptance. Record C10-R1/R2 as
open deferred findings at `6396252`; the original 900-test/232-subtest result does not cover
the two review counterexamples. No code fix or full expert review is performed this turn.
The ten-perspective review plus AI assurance/commercial feasibility is **PLANNED / NOT STARTED**,
without scores. See [the protocol](multi-expert-review-plan.md) and ROADMAP F1–F4.

This document-only increment is locally reviewed/committed; no push or public action.
Historical test/CI counts below stay bound to their named source candidates, not this new
planning revision. Real two-process/runtime/full RAG and all prior live matrices remain
BLOCKED; C10 and the enterprise changes remain open. No published claim of deployment,
revenue, users, SLA or certification is authorized or substantiated by the new purpose.

Planning-increment validation: document links and YAML PASS; manual OpenSpec structure
PASS (23 deltas, 108 requirements, 152 scenarios); all 12 review roles and the requested
report sections are present. Future repair/review tasks remain unchecked. Application,
dependency, deployment, main-spec and archive bytes are unchanged; original file modes
and unrelated content are preserved. No application tests were rerun for this document-only
change. Strict CLI validation remains BLOCKED; no committee scores or new runtime evidence.

## Candidate and version identity

| Identity | Verified value / boundary |
| --- | --- |
| Working branch | `codex/delivery-ci-gates`; reuse existing integration roles |
| C24 pushed candidate | `d8a26b5726cb7ffce6747b677804c7c3403bd763`, same-name origin verified |
| C25 pushed increment | `fe2ae78b5102cc9cc2c4e08e4939da20fd53720e`, same-name origin verified |
| CI repair increment | `b8c4457542781029333de8c3c930437fb28ef51a` pushed; scanner follow-up `16c882b` and image-context fix `0d1a7ce2c26bedc4894c957c875648f131eb2993` pushed |
| Main at inspection | Local/main, origin/main and remote main all `065bdf7b31ce1fb6f9007a7e8851be36bfc2280f`; ancestor of C24 |
| Source/package version | `app/__init__.py` and `pyproject.toml`: `1.3.0`; closeout changes remain Unreleased |
| Historical tag | `v1.3.0` resolves locally to `731864087d081c58324e17824c79a0afffc385a1`; it does not identify this candidate |
| Database schema | Ordered migrations v1–v8 with pinned checksums; startup does not apply them |
| Image | CI-only build/import/Trivy PASS at `0d1a7ce`; digest in repair record; deployment acceptance BLOCKED |
| Document versions | Older v1.5/v3.7 headers identify document revisions/history, not application releases |
| OpenSpec | 15 main specs, 15 archived changes, three active changes; current deltas remain active/unsynchronized |
| Local preservation | 556 existing mode-only differences retained; excluded from the task commit |

Do not bump a version, move a tag or infer a release from a local documentation commit.
A source version cannot distinguish unreleased builds: use commit + image digest + schema
checksums + model/fixture identity for future runtime acceptance. A CI-only image was built
and scanned; no image was published or deployed, no PR merged,
and no specifications synchronized or archived in this increment.

## Earlier C10 isolation increment at `6396252`

The 2026-10-19 implementation isolates each physical checkpoint thread and atomically
publishes an exact checkpoint ID with terminal status and token totals under a PostgreSQL
owner/lease guard. It replaces unowned asynchronous token/status writes. History reads
accepted pointers with read-only legacy fallback; missing referenced data fails closed.
The full local suite passes 900 tests + 232 subtests with zero skips; 28 new deterministic
fencing cases supplement the earlier 27 lifecycle cases. No real stores or model calls.
Schema v8, drain/upgrade requirements and acceptance scenarios are in the
[checkpoint contract](checkpoint-durability.md). C10 remains open.

## Git and CI observation

Read-only GitHub observations on 2026-10-19:

- [PR #2](https://github.com/zhenkun26/BusinessAgent/pull/2),
  `docs: close delivery records and advance offline readiness`, remains OPEN against `main`;
  inspected head `d8a26b5`, `mergeStateStatus=BLOCKED`, `reviewDecision=REVIEW_REQUIRED`.
  Its title predates the expanded closeout implementation; update scope/title/body only in
  a separately authorized remote PR update. No review approval or merge was submitted.
- [C24 CI run 39204305429](https://github.com/zhenkun26/BusinessAgent/actions/runs/39204305429)
  is **FAIL**: both Python 3.11 and 3.13 test jobs failed, production image build skipped.
  Both fail collection at `tests/test_security_hardening.py`, which imports removed
  `_redact_url` from `app.graph.checkpointer` (`ImportError`). Local source confirms that
  stale import. Subsequent local full-suite repair is recorded below; the old run remains FAIL.
- [C23 CI run 39202178839](https://github.com/zhenkun26/BusinessAgent/actions/runs/39202178839)
  also failed collection in that file. This is observed failure, not an unrun BLOCKED check.
- [C25 CI run 39205591288](https://github.com/zhenkun26/BusinessAgent/actions/runs/39205591288)
  at pushed `fe2ae78` also fails the same import in Python 3.11/3.13 (logs verified).
- The separately authorized local CI repair passes **871 tests + 225 subtests, zero skips**,
  with **73.40% local line coverage**. It replaces stale contracts and separates shared
  fixtures from test classes; all 440 original test bodies across the 13 fixture-related
  files remain identical. No CI gate, production behavior or dependency declaration changed.
  See [repair record and environment](../40-process/ci-pytest-repair.md).
- [Repair CI 39208343449](https://github.com/zhenkun26/BusinessAgent/actions/runs/39208343449)
  on `b8c4457`: Linux Python 3.11/3.13 each pass **871 tests + 225 subtests, zero skips**,
  with 75% reported coverage. Gitleaks then fails on 16 verified source-hash false positives.
  Scanner follow-up `16c882b` adds only exact historical fingerprints and a complete
  event-head scan. Run 39208901960 passes both test/security jobs but fails Docker COPY
  because the build context excludes two required scripts. Narrow context exceptions and
  one additional regression are implemented in `0d1a7ce`.
- [CI 39209313444](https://github.com/zhenkun26/BusinessAgent/actions/runs/39209313444)
  on `0d1a7ce` is **PASS**: each Python version runs **872 tests + 225 subtests, zero skips**,
  Gitleaks and pip-audit pass, production image build/non-root imports/assets pass, and
  Trivy HIGH/CRITICAL reports zero findings under its unchanged policy. No image is published.
  See the repair record for PR merge-ref/image digest identities and retained limitations.

The historical fixed offline inventory did not collect this legacy pytest file. Its 789
passing cases
and CI collection failure measure different scopes; neither cancels the other. Retain the
failure explicitly in [ISSUES C24/C25](../40-process/ISSUES.md#c24). The local repair now
covers the complete pytest suite separately, without skips or collection exclusions;
the image-context regression increases the current fixed inventory to 790 passing tests
plus its one separately BLOCKED PyYAML check; full remote pytest has zero skipped tests.

## Support and migration map

These are implemented candidate contracts and target boundaries, not measured support claims.

| Area / items | Source and current authority | Current boundary / remaining acceptance |
| --- | --- | --- |
| Deployment C01 | `docker-compose.prod.yml`, [deployment guide](../../enterprise-agent/deploy/DEPLOY.md) | Single organization, single Linux host, immutable shared API/worker image; real entry/image acceptance BLOCKED; K8s/multihost HA outside target |
| Models C02 | `.env.example`, `app/rag/model_profile.py`, [profile](../../enterprise-agent/deploy/MODEL_PROFILE.md) | Beijing embedding/rerank; Flash default, Pro complex tasks; separate collection and credentials; paid probes opt-in; no actual API/quotas/cost/latency acceptance |
| Schema C03 | `deploy/schema_manifest.json`, [bootstrap guide](../../enterprise-agent/deploy/DATABASE_BOOTSTRAP.md) | Explicit apply/status/admin; old stores only approved isolated copies; no automatic DDL, universal account or historical-token migration |
| Identity C04–C07 | [session](session-ownership.md), [authorization](runtime-authorization.md), [credentials](credential-safety.md), [retrieval](retrieval-authorization.md) | Owned sessions, current role/department authorization, no stored JWT, fail-closed rendering; actual JWT/PG/Milvus/browser/history remediation BLOCKED |
| State C08–C10 | [context](request-context.md), [coordination](cross-process-state.md), [checkpoint](checkpoint-durability.md) | Independent subtasks only; explicit Redis/PG backend, no fallback; real two-process semantics and **C10 write fencing open** |
| Execution C11–C14 | [approval](approval-execution.md), [operations](tool-operation-safety.md), [Saga](saga-recovery.md), [queue](queue-reliability.md) | Persisted claims/identities/jobs, conservative uncertainty, linked HTTP inverses; requester resume/current authorization; real locks/crashes/HTTP effects unverified |
| Knowledge C15/C17 | [publication](knowledge-publication.md), [quality](rag-quality.md) | Explicit publication visibility; legacy unversioned data needs reviewed reimport; 122 quality cases plus six role controls require actual model/store and semantic acceptance |
| Analysis C16 | `app/agents/analysis.py`, `app/tools/analysis_data.py`, [adapter](analysis-data.md) | CRM provider-aligned bounded snapshot, deterministic Python report; Mock is synthetic, HTTP real acceptance BLOCKED; no arbitrary SQL/BI support |
| Reference C18/C19 | [business HTTP](reference-integration.md), [controlled SSO](controlled-sso.md) | Independent reference CRM/ticket/mail/IdP are candidates, not actual enterprise SaaS/SMTP/IdP acceptance; R01–R20/S01–S16 BLOCKED |
| Browser C20 | [browser delivery](browser-delivery.md) | Verified current identity, local assets, transient tokens, API-only management where documented; B01–B16 BLOCKED |
| Observability C21 | [runtime observability](runtime-observability.md) | Schema v7, retained shared audit store/replay, process readiness/metrics/alerts; O01–O16 BLOCKED |
| Recovery C22 | [retained recovery](retained-recovery.md) | Current-version cold capture, fresh-volume restore, explicit compatible rollback; no hot backup/PITR/destructive cleanup; D01–D16/RTO/RPO BLOCKED |
| Capacity C23 | [capacity](capacity-evidence.md) | Proposed frozen mixed workload, separate TTFT/full response/queue timing; no measured maximum capacity or SLA; L01–L16 BLOCKED |
| Evidence C24/C25 | [fixed verification and per-item counts](final-candidate-verification.md), [ISSUES](../40-process/ISSUES.md#engineering-closeout) | E0/E1 receipts are not E2/E3/E4, full pytest, image scans or release acceptance |

Compatibility changes are Unreleased: authentication/session guards, task `202` responses,
approval resume/claim semantics, knowledge visibility, explicit migrations, external model
profile and immutable deployment require the current guides. Historical claims of unchanged
API behavior in the August changelog do not apply to these closeout changes. Do not run old
schema SQL, direct unversioned ingestion, default-user demonstrations or cleanup recipes on
current data. Preserve old BGE collections/volumes and historical credential evidence.

## Increment provenance

All listed commits are ancestors of the pushed C24 candidate. These are delivered
increments, not closed acceptance items. Each record retains its original evidence scope.

| Item | Commit | Delivery record |
| --- | --- | --- |
| C01 | `2a9c364` | [Record](../40-process/阶段性总结_C01部署产物与入口.md) |
| C02 | `42bfc7f` | [Record](../40-process/阶段性总结_C02模型依赖.md) |
| C03 | `fc8da91` | [Record](../40-process/阶段性总结_C03数据库迁移与初始化.md) |
| C04 | `dbc8236` | [Record](../40-process/阶段性总结_C04会话归属校验.md) |
| C05 | `9f5397c` | [Record](../40-process/阶段性总结_C05认证失败闭合与运行时授权.md) |
| C06 | `6955133` | [Record](../40-process/阶段性总结_C06凭证与HTML失败安全.md) |
| C07 | `ceae708` | [Record](../40-process/阶段性总结_C07检索权限与表达式编码.md) |
| C08 | `d81c281` | [Record](../40-process/阶段性总结_C08请求上下文与子任务依赖.md) |
| C09 | `079cd62` | [Record](../40-process/阶段性总结_C09跨进程运行状态.md) |
| C10 | `a57bd4e` | [Record](../40-process/阶段性总结_C10检查点持久化与故障语义.md) |
| C11 | `8bb6241` | [Record](../40-process/阶段性总结_C11审批领取与执行状态.md) |
| C12 | `21b5287` | [Record](../40-process/阶段性总结_C12工具幂等与安全重试.md) |
| C13 | `c42dcf8` | [Record](../40-process/阶段性总结_C13Saga持久化与故障恢复.md) |
| C14 | `59a5c14` | [Record](../40-process/阶段性总结_C14队列可靠性与Worker初始化.md) |
| C15 | `0c0c5f9` | [Record](../40-process/阶段性总结_C15知识发布与索引一致性.md) |
| C16 | `bb81833` | [Record](../40-process/阶段性总结_C16分析数据适配.md) |
| C17 | `cd49d78` | [Record](../40-process/阶段性总结_C17RAG质量与指标口径.md) |
| C18 | `bd04a12` | [Record](../40-process/阶段性总结_C18完整参考HTTP业务集成.md) |
| C19 | `4afe54b` | [Record](../40-process/阶段性总结_C19受控IdP与SSO完整链路.md) |
| C20 | `44bfcb0` | [Record](../40-process/阶段性总结_C20浏览器角色流程与前端交付.md) |
| C21 | `40c10d8` | [Record](../40-process/阶段性总结_C21就绪审计指标与告警.md) |
| C22 | `d70c1b4` | [Record](../40-process/阶段性总结_C22当前版本备份恢复与回退.md) |
| C23 | `6de94c6` | [Record](../40-process/阶段性总结_C23规定负载下的性能与容量.md) |
| C24 | `d8a26b5` | [Record](../40-process/阶段性总结_C24最终候选离线验证.md) |

S0 `05d8d0c`, safety prework `a329603` and the C18 contract prework `317aa7f` remain
separate earlier increments; they do not replace final runtime acceptance.

## Documentation and specification authority

1. Current executable source/config/schema establishes implemented behavior.
2. [Engineering baseline](engineering-delivery-baseline.md) establishes the target support scope;
   [ISSUES](../40-process/ISSUES.md#engineering-closeout) establishes acceptance, and
   [ROADMAP](../40-process/ROADMAP.md#engineering-closeout-stages) establishes sequence.
3. Current engineering contracts linked above govern model, migration, UI and operations.
   Chinese/English root READMEs have equivalent current setup and boundary statements.
4. July/August manuals, W-stage measurements, archived OpenSpec changes and interview
   assets preserve historical/design/demo context. Their old model names, fallback paths,
   timings, sample accounts and completion ticks are not current acceptance or instructions.
   Entry banners route operators to this map; histories are retained, not rewritten as new results.
5. `engineering-delivery-closeout` delta requirements represent this unfinished candidate.
   Main specifications retain the published historical baseline until authorized completion
   and synchronization. Do not mistake an intentional active delta/main difference for
   permission to rewrite main specs or archive incomplete work.

`openspec` is unavailable on the current PATH. Manual structure/link/checksum checks are
E0 only; strict CLI validation remains BLOCKED. The three active changes remain independent:
engineering closeout, real CRM/mail/SSO integration, and UAT/grey rollout. The latter two
cannot be closed with reference-environment success.

## Remaining work and handover boundary

| Gate | Status | Evidence required before changing the status |
| --- | --- | --- |
| C24/C25 pushed full pytest | **FAIL (historical runs)** | Preserve original failure; local repair does not rewrite previous CI evidence |
| Latest retained F2-10 full offline run | **PASS (offline only)** | Tested `cd34550`, recorded by `2ed1d93`: eight checks, 1883 tests + 535 subtests, Node 69/14/seven assets; complete hashes in the retained verification record; no new run in this unit |
| Historical C10-R1/R2 local full pytest | **PASS** | 925 tests + 249 subtests, zero skips/guard denials; retained source-hashed receipt, macOS Python 3.13; not Linux/runtime acceptance |
| Historical repaired remote full pytest | **PASS** | `0d1a7ce`: Linux Python 3.11/3.13 each 872 tests + 225 subtests, zero skips |
| C10 lease-expiry write fencing | **OPEN** | Isolation/publication implementation and 28 new offline tests PASS; verify late writers with actual processes/storage, migration v8 and faults |
| L01–L16 / D01–D16 / O01–O16 / B01–B16 / S01–S16 / R01–R20 | **BLOCKED** | Exact isolated Linux candidate, independent services/observers, faults and each matrix's acceptance evidence |
| Real runtime and full RAG / historical credentials | **BLOCKED** | Actual store/model/identity/browser chain, fixed corpus/semantic review, separately authorized historical handling |
| Historical CI image build, dependency imports and security scans | **PASS** | Run 39209313444 at `0d1a7ce`; CI-only image, not deployment acceptance |
| OpenSpec strict | **BLOCKED** | CLI unavailable; manual structure checks do not substitute for strict validation |
| C25 full reconciliation / engineering acceptance | **OPEN / BLOCKED** | Reconcile final accepted commit/image/runtime evidence, review and remaining P0/P1 issues |
| Enterprise UAT / grey / production | **BLOCKED** | Real resources, ownership, external contracts, observation and approval in their independent changes |

### Historical C10 instruction snapshot — 2026-10-19

The quotation below preserves the old instruction context and its original revision. It
does not describe the current authorized unit; use the [current handover entry](#current-handover).

> The current authorized increment is the C10 stale-writer repair, based on `716f3b5`.
> Its local tests do not transfer earlier remote CI/image results to this modified candidate.
> Current-candidate remote CI, image and strict-tooling checks remain BLOCKED/unrun. Additive
> schema v8 has not been applied. See the [C10 delivery record](../40-process/阶段性总结_C10检查点持久化与故障语义.md).
> Review and commit locally, then wait for confirmation. No push, merge, release, deployment,
> spec synchronization or archive is authorized by this increment.
