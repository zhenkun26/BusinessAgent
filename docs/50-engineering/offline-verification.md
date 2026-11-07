# Current-candidate offline verification and CI coverage (F2-10 prerequisite)


<a id="review-ci-repair-20261107"></a>
## Draft PR #8 CI repair — 2026-11-07

The owner authorized continuing PR/CI fixes and pushes; final merge remains their decision.
[Initial CI run](https://github.com/zhenkun26/BusinessAgent/actions/runs/42360437018)
failed before tests because matrix record IDs contained dots rejected by the existing
safe-ID validator. The matrix now supplies ci-3-11 and ci-3-13 without relaxing validation.

The secret scanner still runs actual event history and exact tracked-tree Gitleaks.
It retains raw findings and classifies only exact sources-map entries whose SHA256 can be
recomputed from regular Git blobs. Seven scan-visible raw historical preimages (56,707
bytes) preserve verifiable evidence for the frozen C24 manifest across the squashed import.
They are inert evidence, never imported or executed. No broad path/rule/regex ignore was added.
The single archived JWT marker additionally requires the exact blob, location and value hash,
synthetic payload and invalid 14-byte HS256 signature; changed or valid credentials remain findings.

Verification before commit:
- 39 actual-Gitleaks regression tests PASS, including archived proof tampering, source/manifest
  secrets, valid JWT/neighboring secret negatives, strict dual coordinate modes for existing-entry
  history/tree findings, and original history/tree coverage controls.
- All eight offline checks PASS; 2118 Python tests + 640 subtests, 81.89% coverage,
  Node 75/14 and seven frontend assets. Source stable, no guard denials/skips/xfails/deselections.
- Reviewed inventory: 368 inputs, 98 production packages and unchanged 457 pending source records.
- Aggregate receipt: enterprise-agent/eval/results/offline/ci-repair-precommit-20261107.json.
  Dirty precommit binding correctly remains BLOCKED.
- Independent code/evidence review found no remaining blocker. A separate isolated scan candidate
  passed both history and exact tree with raw reports preserved; this is not the final commit
  or remote CI result. Final committed scanning and remote verification remain required.

Earlier security-test fixture runs used checkout that removed branch-only synthetic files.
The corrected suite uses retained per-branch worktrees and does not delete fixture files.
No original project or user data was deleted. Earlier diagnostics remain separate evidence.
This repair does not change application behavior or close runtime, rights, UAT or release gates.


### Fresh-checkout startup repair

The first repair was published as 0c539ee0918aff75051e7baedfc61e6c02dd939c.
Its clean local eight-check receipt passed (2118 tests + 640 subtests), and its
committed full-history/exact-tree scans passed after retaining and classifying
44/42 raw findings respectively; neither result implied remote CI success.

[The next CI run](https://github.com/zhenkun26/BusinessAgent/actions/runs/42362838030)
passed record admission but failed the Python child on both versions; the other
seven offline checks passed. Security/audit/image steps were not reached. The run
tested merge d48559032d80f05f3d4f63d85ea4822bece8d8d8. No child traceback was
published, so it is not evidence that all possible Python failures are understood.

Independent inspection reproduced a deterministic fresh-checkout startup defect:
eval/results is ignored and absent in a new checkout, but the child attempted to
create its UUID directory without creating missing parents. The aggregate creates
its record parent only after the child finishes. Existing local evidence directories
masked this condition.

The narrow repair creates missing parents while retaining exclusive run-directory
creation. Two new regression tests cover missing parents and collision refusal with
original evidence preserved. Forty focused tests passed with zero guard denials;
independent static review found no blocker. Expected full count is 2120, with the
same 640 subtests and unchanged Node/assets/package/rights gates. No raw child log
publication or relaxed result parsing is added. Precommit execution passed all eight checks (2120 tests + 640 subtests); dirty binding
and source stability correctly remained blocked because documentation was edited during
that run. Receipt: enterprise-agent/eval/results/offline/ci-fresh-parent-precommit-20261107.json.
A fresh retained clean worktree and subsequent remote CI must verify the final commit.


### Dependency audit follow-up

Commit 1dcd3d9dcffff7d7ac60e1b2cf168b6f93a0a26a passed all eight checks
in a new retained local checkout with no initial results directory (2120 tests plus
640 subtests, clean/stable binding). Its committed full-history/tree scans passed.
[Remote run 42363479117](https://github.com/zhenkun26/BusinessAgent/actions/runs/42363479117)
then passed both Python 3.11/3.13 offline checks, coverage uploads, all 39 scanner
regressions and actual PR history/tree scans. Actual merge checkout was
0e8ec6f520fcaac2cc870a96106b7726d974f9a4. History retained 86 raw findings
(84 verified source hashes and two invalid synthetic markers); tree retained 42
(41 verified hashes and one marker). No unclassified finding remained.

Both jobs failed pip-audit on two published vulnerabilities:
- msgpack 1.2.1: CVE-2026-114613 / GHSA-j586-36cw-2gc2, High (CVSS 3.1 7.5),
  malformed map-key handling can leak C-extension memory; fixed in 1.2.3.
- setuptools 83.0.0: GHSA-xmj3-9gf7-h52w, Low (CVSS 4.0 1.0),
  Windows legacy wheel namespace-metadata path traversal; fixed in 84.1.0.
  This is not evidence of exploitation in the Linux production image.

Official reviewed advisories:
https://github.com/advisories/GHSA-j586-36cw-2gc2
https://github.com/advisories/GHSA-xmj3-9gf7-h52w

The msgpack vendor advisory header lists 1.2.2, while the reviewed database range is
below 1.2.3; the audit blocks the pinned 1.2.1. The remediation upgrades to the fixed
version rather than introducing an exemption. The planned minimal update binds both
official package metadata and exact Linux wheel hashes, retaining 98 packages and
457 pending source-rights records. New-version compatibility, full tests, remote audit
and image checks remain required. The failed run never started its dependent image job.

Local fixed-version verification: all eight checks PASS, 2120 tests plus 640 subtests,
81.89% coverage, Node 75/14 and seven assets. Source stability PASS; dirty precommit
binding remains BLOCKED. Receipt:
enterprise-agent/eval/results/offline/ci-dependency-precommit-20261107.json.
The new isolated Python environment excludes both old package cache roots and resolves
exactly one distribution of each fixed version. It preserves the old environment.
Independent review verified official raw metadata and wheel bytes, all lock/build/license
bindings and all 98 installed pins. No extra dependency or vulnerability exemption was
added. New metadata hashes bind retained responses; changing public metadata does not
revalidate historical response hashes. These macOS checks do not substitute for remote
pip-audit, both supported Python versions or the final Linux image.


<a id="integration-verification-20261107"></a>
## Authorized main/local integration — 2026-11-07

Scope: main `f7d684b` plus engineering candidate `edc5c58` and its 31 local increments.
The separate five workflow-document commits, original worktree, old integration draft
and historical receipts are preserved. See the
[integration plan](../../openspec/changes/integrate-local-delivery-security/proposal.md).

The reviewed current manifest has 360 inputs (13 added, 47 changed, none removed),
including main secret-scanner source/tests. Required counts are 2116 Python tests,
Node 75/14, seven frontend files, 98 production packages and 457 pending source records.

### Precommit evidence

- Full unfiltered Python 3.13.15: 2116 passed + 640 subtests, 81.89% coverage,
  no failures/skips/xfails/deselections or guard denials, exact production dependencies.
- All eight checks PASS: Python, page/credential VM, frontend assets, build inputs,
  provenance integrity, synthetic RAG controls and safe preflight.
- Source stable; dirty precommit candidate binding correctly remains BLOCKED.
- Full receipt: `enterprise-agent/eval/results/offline-pytest-bf11ca1952774dd5b68c3b64d3a49cb3/receipt.json`.
- Aggregate: `enterprise-agent/eval/results/offline/integration-precommit-20261107.json`.
- Aggregate child: `enterprise-agent/eval/results/offline-pytest-db8951e52fab44b19caa820b88a676e5/receipt.json`.
- Earlier interrupted/partial diagnostic runs remain unchanged, not relabeled as passes.
  Source hashes were rechecked after the computer reconnected and still match.

Independent source review findings concerning unresolved forward-Saga holds and external-mail
classification were fixed with negative controls. Tests cover late-receipt non-release,
scope/plan substitution, deadline crossing, missing committed claims and evidence-panel races.

The planned clean local commit verification is now complete; the exact binding follows.


### Clean integration commit verification

Tested commit: `a8c4eec42ec2d44cb8b2e4ae433ccbc88e7021fe`.
All eight checks PASS; candidate binding PASS, clean before/after and source stable.
Full suite: **2116 tests + 640 subtests**, zero failed/skipped/xfail/deselected outcomes
or guard denials; exact production dependency match; coverage 81.89%. Node 75/14 and
seven frontend assets PASS. All 360 current input hashes match the reviewed manifest.
No runtime acceptance or rights status changed; overall BLOCKED / UAT-release false
and exit 2 are deliberate, distinct from the successful offline execution/binding.

- Aggregate receipt: `enterprise-agent/eval/results/offline/integration-clean-20261107-a8c4eec.json`
- Aggregate SHA-256: `2db835608e4c2ecbb08d5ca6ecc102273b9a34215216bad604a39fdb93cdd53c`
- Child receipt: `enterprise-agent/eval/results/offline-pytest-6d6314f3872e4b2095f622aab904b2c6/receipt.json`
- Child SHA-256: `ca8a61397ad6321b2e1262c229bfd426693473dd6c557029854e4c6e43d154d5`
- Candidate content SHA-256: `3f62b9beb8b64034d34f6d5d197ce61c47222a7476649106d8f971c673075251`
- Reviewed manifest SHA-256: `e10f1c25db1ff9604ba0286188e3ebd743d91935d03aebf76baf4be84dcc997d`

This result is recorded in a subsequent documentation-only commit. That commit is not the
tested revision; unchanged source hashes establish that no application, test, dependency
or verification inputs changed afterward. The working branch remains local with no push,
main merge, deployment or archive. Existing upstream license text retains its original
whitespace rather than rewriting third-party legal material.

### Limits and release boundary

C10 remains OPEN; source rights remain PENDING. Real PostgreSQL guards/transactions,
Redis/process races, browser/reader/accessibility, SDK/model/provider calls, Linux image
builds/scans and remote CI remain unverified. No database migration, service startup,
push, merge, deployment, new dependency or filesystem deletion was performed.
The main secret-scanner regression suite is retained in CI but cannot run unchanged
locally because it deletes fixtures; pipeline/source integrity was checked instead.
OpenSpec CLI is unavailable; manual structure/link checks are not strict CLI validation.
Evidence display is read-only and does not provide automated human-hold release.
The earlier October records below are historical and do not certify this integration.

<a id="current-candidate-reverification"></a>
## Historical candidate reverification — plan recorded 2026-10-22

Authorized parent: `4570a082a82f197578fc569a467e94c0150e5491`. This increment
re-executes the existing eight checks and binds fresh local evidence; it changes no
application/test/check code, counts, source manifests, CI recipes or acceptance rules.
Historical receipts, C24 inputs, C17 corpus/evaluator/categories/denominators and old
presentation assets remain unchanged. All 447 source rights remain pending; the eleven
maintainer responses remain received with creation/reference sources unknown.

### Sequence and evidence binding

1. Record this plan and the scoped OpenSpec tasks, review the documentation-only diff,
   and create a local planning commit so the tested candidate starts clean. That commit
   includes the delivered F2-11 alignment rather than reusing a historical test receipt.
2. Reuse the existing Python 3.13.15 declared-dependency runtime and installed Node; run
   the unchanged `offline_verify.py --execute --record FRESH_ID` once. Retain all ignored
   receipts, fixtures, coverage and diagnostic output under `enterprise-agent/eval/results/`.
   No download, installation, private data, provider/service call or filesystem deletion.
3. Inspect every child result, exact inventory/counts, before/after candidate stability,
   full collected test outcomes and guard denials. Missing tools/dependencies remain
   BLOCKED; failures remain FAIL. Do not skip tests, refresh hashes, change counters or
   lower gates to obtain success. If blocked/failed, record the actual result and stop
   short of claiming successful reverification; code fixes require a separate scope.
4. Record the actual tested full commit, aggregate content hash, reviewed source-manifest
   hash and receipt/child-receipt SHA-256 values in this document. Match them to the
   retained bytes and unchanged 347 reviewed inputs. Receipt paths remain local evidence,
   not uploaded artifacts or redistributable provenance clearance.
5. Synchronize tracking documents and the active OpenSpec change, review links/YAML/
   scoped requirements and the final diff, then make a separate local results commit.
   This later documentation commit is not the tested revision. Compare it to the tested
   commit to establish documentation-only changes; do not relabel an older run or rerun
   the whole suite merely to chase a self-referential report commit hash. Then wait.

### Acceptance for this bounded increment

| Check | Unchanged required evidence |
| --- | --- |
| `python` | Full 1883 tests; zero failed/skipped/xfail/deselected outcomes or guard denials, stable source and matching declared production requirements |
| `node-page` / `node-credentials` | Exact 69 / 14 VM/static cases; no browser acceptance claim |
| `frontend-assets` | Seven distribution/license files pass integrity checks |
| `build-inputs` | Existing reviewed recipe and 98 production pins; installed Linux image remains BLOCKED |
| `provenance` | Integrity passes with all 447 source records still pending; no rights inference |
| `rag-controls` | Eight independent safe/unsafe pairs; model resistance NOT_MEASURED and semantic review PENDING; C17 unchanged |
| `safe-preflight` | Five existing subchecks retain their PASS/BLOCKED split; overall acceptance BLOCKED and all UAT/release flags false |
| Candidate binding | Receipt identifies the actual clean, stable tested commit, content and reviewed-source hashes; later result-documentation commit is explicitly separate |

Existing local execute exit 2 is expected when execution/binding PASS but overall
acceptance stays BLOCKED. OpenSpec CLI is unavailable at planning time (exit 127);
strict validation stays BLOCKED, with manual document/YAML review reported separately.
Real runtime/full RAG/privacy, C10 two-process acceptance, L/D/O/B/S/R matrices,
historical credentials, current remote CI/image/scans and enterprise UAT/release remain
BLOCKED. F2-09 rights stay PENDING and C10 OPEN. No push/upload, remote CI, main-spec
sync, merge, deployment, release, archive, commercial validation or automatic next item.

The planning snapshot at `cd34550` recorded execution/result review as NOT RUN. The
following observations were added afterward and do not change that tested snapshot.

### Actual execution and immutable receipt binding — 2026-10-22

The unchanged local entry ran once using `--execute --record f210-reverify-20261022-cd34550`
on the clean planning commit. Every existing check passed, source/candidate identity stayed
stable and candidate binding passed. Exit **2** preserves overall **BLOCKED**; `formal_uat`,
`release_allowed` and `release_evidence` are all false. `--ci` was not used; no remote CI ran.

| Identity | Actual value |
| --- | --- |
| Tested full commit / clean state | `cd34550c3b38de4936903acc8f46bc2f1831620b` / `true` |
| Receipt timestamp (UTC) | `2026-10-22T16:29:13.362370+00:00` |
| Candidate content SHA-256 | `c1021b7cb603bb0004c53449309d82731d1ffcc5febae579c08a8639f3c22629` |
| Reviewed source-manifest SHA-256 (`sources_sha256`) | `c20ee921e9c495be07652eae727be7c172b9555a14e7a0a3816067088c946413` |
| Aggregate receipt SHA-256 | `4bb421eeabddd7a790fefca7aec932f8cb8eefc35e83d93c54ec44a2a849d9b2` |
| Full Python child receipt SHA-256 | `43f47409235512562929f3f19fa51a86ba1be00f6ba979a87d6da317a0405cb6` |

Aggregate receipt: `enterprise-agent/eval/results/offline/f210-reverify-20261022-cd34550.json`.
Python child receipt: `enterprise-agent/eval/results/offline-pytest-1700360f9a34429ca30bd179b42fe7c0/receipt.json`.
Both receipts, diagnostic log, fixtures and coverage remain ignored/local; a fresh clone
does not include these artifacts. Their hashes identify retained bytes, not external
attestation, runtime acceptance or source rights. Reconstructing all 888 tracked files
from the tested Git tree independently reproduced the candidate content hash. The child
receipt's complete 347-file source map also matches the unchanged reviewed manifest.

| Existing check | Observed result | Evidence limit |
| --- | --- | --- |
| `python` | PASS: 1883 collected/unique/passed tests + 535 passed subtests; zero failures, skips, xfails, deselections or guard denials; declared production versions match; coverage 80.25893430344533%; 45 dependency warnings | Existing Python 3.13.15/macOS runtime only; no new tests or changed expected count |
| `node-page` | PASS: 69 cases | VM/static/template compilation only |
| `node-credentials` | PASS: 14 cases | VM only |
| `frontend-assets` | PASS: seven distribution/license files | Retained integrity, no served-browser proof |
| `build-inputs` | PASS: existing recipes/98 production pins | Actual Linux install/image/two-build acceptance BLOCKED |
| `provenance` | PASS: integrity with all 447 source records still `PENDING_SOURCE_REVIEW` | Eleven replies remain received/unknown; no rights clearance |
| `rag-controls` | PASS: eight authored safe/unsafe pairs meet the existing checker contract | Model resistance NOT_MEASURED, semantics PENDING; not a real pipeline run |
| `safe-preflight` | PASS: unchanged five-subcheck contract, including blocked readiness/release | Overall acceptance BLOCKED and UAT/release flags false |

Receipt/hash/source/C17 verification PASS: primary 122 unique cases (115 answer, five
refuse, two clarify), supplemental six (two answer, four refuse), nine document bindings
and frozen evaluator/metrics/denominators unchanged. The source-manifest, license inventory,
all tracked backend/tests/workflows, historical C24 inputs and all interview/assets are
byte-identical to the authorized parent. Prior receipt identities remain historical; no
gate, counter, corpus or rights state was changed.

Final review PASS: receipt/source/candidate bindings, immutable inputs, tracking consistency,
307 local link targets, YAML/manual scoped OpenSpec and whitespace. OpenSpec tasks 33.1–33.3
are complete for this bounded increment; 33.4 remains unchecked. The reviewed local results
commit contains only reports/context/tasks and is explicitly **not** the tested commit;
its exact identity will be reported in the handoff without rewriting this receipt. OpenSpec
strict CLI remains unavailable/BLOCKED. All previously listed real/privacy/rights/C10 and
release limitations remain in force; F2-10/C24/C25 and C10 stay OPEN.

## Previous F2-11 documentation-only update

Documentation-only F2-11 update after local `ccd3065` (2026-10-22): the existing
[walkthrough](../../interview/portfolio-walkthrough.md#current-candidate) now distinguishes
current source from retained `6f5bbd9` test evidence and historical CI. Only that document's
pending inventory hash and the dependent inventory hash in the current 347-input source
map change. Checks, expected counts, membership and rules remain unchanged. The old
eight-check receipt/source-manifest hash remains historical; this update does not run
the full entry or create a fresh candidate receipt. Scoped provenance/source integrity
and document review are recorded in the [alignment record](portfolio-demonstration.md#current-claim-alignment).
Runtime/full RAG/privacy and strict CLI remain BLOCKED, source rights pending, C10 OPEN.

## Plan recorded before implementation — 2026-10-20

Parent: `f3a7c2e`. This unit aligns repository-local offline checks and CI recipes. It
performs no push, upload, workflow dispatch, image build, application startup, service/model
call, migration or deletion. No new dependencies or toolchain-wide version freeze. Real
runtime/full RAG remain BLOCKED; F2-05 privacy and F2-09 sources pending; C10 OPEN.

### Design and implementation sequence

Current reviewed extension (2026-10-22, after `fd5511c`): F2-06
[score admission](score-admission.md); 100 new tests/25 subtests, full 1883 tests + 535
subtests PASS, zero skips/xfails/deselections/guard denials; eight checks PASS. 347 inputs/
447 pending sources; Node 69/14/seven assets unchanged. Only five affected production
files, the new helper/test and provenance are rebound; old tests, scorer/factory/profile,
C17 and historical C24 remain frozen. Numeric failure propagation changes only invalid
score handling, preserving finite behavior and C17 categories/denominators. Final local
receipt: `eval/results/offline/f206-score-final-20261022.json`; overall BLOCKED/release/UAT false.

Previous reviewed extension (2026-10-22, after `cf43c96`): F2-06
[factory selection/status](reranker-selection.md); 68 new tests/8 subtests, full 1783 tests
+ 510 subtests PASS, zero skips/xfails/deselections/guard denials. Eight checks PASS, 345
inputs/446 pending sources; Node 69/14/seven assets unchanged. Only reviewed factory/
retriever/config comments, two adapted isolated fixtures, new tests and provenance are
rebound. Five scorer methods, historical C24, degradation route and C17 stay frozen.
Final local receipt: `eval/results/offline/f206-selection-final-20261022.json`;
overall BLOCKED/release/UAT false. Missing strict OpenSpec CLI remains BLOCKED.

Previous reviewed extension (2026-10-22, after `22492ab`): F2-06
[optional Cohere/BGE result boundary](optional-rerank-result-boundary.md); 108 new tests/
10 subtests, full 1715 tests + 507 subtests PASS, zero skips/xfails/deselections/guard denials.
Eight current offline checks PASS; 344 reviewed inputs/445 pending sources. Only reranker,
C07 NumPy stub/provenance and new result-admission/test modules are rebound. Historical
C24/C17/eight-control inputs remain frozen; factory/constructors/Bailian/LLM unchanged.
Final local receipt: `eval/results/offline/f206-optional-rerank-final-20261022.json`;
overall BLOCKED/release/UAT false.

Previous reviewed extension (2026-10-22, after `5bbf68b`): F2-06
[optional LLM rerank boundary](llm-rerank-trust-boundary.md); 85 new tests/3 subtests,
full 1607 tests + 497 subtests PASS, zero skips/xfails/deselections/guard denials. Eight
checks PASS, 342 reviewed inputs/444 pending sources. Only graph/reranker/retriever,
adapted C07 test/provenance and new boundary/test modules are rebound; frozen C24/C17/
eight-control inputs remain. Final local receipt:
`eval/results/offline/f206-llm-rerank-final-20261022.json`; overall BLOCKED/release/UAT false.

Previous reviewed extension (2026-10-22, after `d5e028c`): F2-06
[chitchat fallback boundary](chitchat-trust-boundary.md); 57 new cases, full 1522 tests +
494 subtests PASS, zero skips/xfails/deselections/guard denials. One obsolete length-log
expression removes its automatic subtest, with no weaker gate. Eight checks PASS, 340
reviewed inputs/443 pending sources. Only aggregator/graph/provenance and the new chitchat/
test modules are rebound; frozen C24/C17/eight-control inputs remain. Final local candidate
receipt: `eval/results/offline/f206-chitchat-final-20261022.json`; overall BLOCKED/release/UAT false.

Previous reviewed extension (2026-10-22, after `c0ca3b5`): F2-06
[non-knowledge result boundary](nonknowledge-result-boundary.md); 49 new cases, full
1465 tests + 495 subtests PASS, zero skips/xfails/deselections/guard denials. Two obsolete
logging-expression subtests disappear with the removed summary helper; no weaker gate.
Eight checks PASS; 338 reviewed inputs/442 pending sources. Only aggregator, two existing
tests, provenance inventory and the new result/test modules are rebound. Historical C24,
C17 and eight-control inputs stay frozen; final local candidate receipt is
`eval/results/offline/f206-results-final-20261022.json`, with overall BLOCKED/release/UAT false.

Previous reviewed extension (2026-10-22, after `8edaf00`): F2-06
[Planner/tool proposal boundary](planner-tool-trust-boundary.md); 61 new cases, full
1416 tests + 497 subtests PASS, zero skips/xfails/deselections/guard denials. Eight checks
PASS, 336 reviewed inputs / 441 pending-source records. Only the reviewed five existing
production modules, context fixture, provenance inventory and two new modules are rebound.
All check commands, frozen C24 and C17/eight-control bytes remain unchanged. Final local
clean candidate receipt: `eval/results/offline/f206-planning-final-20261022.json`;
CI-mode success remains offline only with overall BLOCKED and release/UAT false.

Previous reviewed extension (2026-10-21, after `8e30338`): F2-06
[read-only RAG boundary](rag-trust-boundary.md) is included in full Python coverage and
the original eight synthetic controls. That slice reviewed 334 inputs / 1355 Python
cases / 440 pending source records. Historical verification below is not a new runtime
claim; all eight commands, failure semantics and frozen C24 inputs remain unchanged.

Previous reviewed extension (2026-10-21): F2-05 [automatic telemetry admission](telemetry-admission.md)
adds policy/startup/Settings/factory coverage to the existing full Python check. The eight
commands and all failure/blocked/no-skip semantics are retained; historical verification
counts below describe F2-10 at `c5240ad`. That historical telemetry inventory is recorded
in its document; the current inventory is `scripts/offline_sources.json`. No legacy C24 refresh.

1. Preserve `scripts/final_candidate.py` and its frozen source manifest as historical C24
   evidence; do not bless source drift by replacing its hashes. Add one current-candidate
   entry with an explicit reviewed source manifest and fixed check inventory.
2. The current entry covers: complete Python tests (including all F2 modules), both Node
   page/credential entries, seven browser assets, production build inputs, pending source
   inventory, independent synthetic RAG controls, and safe_validate. It does not silently
   discover arbitrary executables or run old live eval scripts. Validate exact entry sets,
   counts and current source coverage before any child; additional/unreviewed source fails.
3. Move the reviewed retained pytest diagnostic policy into a repository-local helper:
   declared installed production/test dependencies only, no automatic dotenv/plugin/cache/
   cleanup, retained fixtures/coverage, denied network/deletion and bounded write paths.
   Execute the whole test directory with no filter/deselection switch. Report collected,
   passed, skipped/xfail/deselected/failure counts and guard denials; require zero exceptions.
4. Bind input/source hashes and before/after Git state to receipts. Preserve individual
   failures, reject omitted/duplicate/unknown results, source drift, stale counts, malformed
   output and contradictory release/acceptance flags. Missing tools/dependencies are BLOCKED
   with no success or skip credit; child failure/timeouts fail the execution gate.
5. CI invokes the same tracked entry, including Node, instead of relying on Python-only
   discovery for CJS. Keep security/image/import/scanner gates and existing coverage
   artifact obligations. Existing runner Node is required; add no third-party action.
6. CLI default remains plan-only. Explicit execution returns 1 for failure and 2 while
   real acceptance is BLOCKED. An explicit CI mode returns 0 only for complete offline
   checks on a stable clean candidate, while the JSON still states overall BLOCKED and
   all release/UAT flags false. This is scoped execution success, never acceptance approval.
7. Add missing-entry/tool/child-failure/drift and no-skip/malformed-result counterexamples;
   execute focused and full offline checks with installed declared dependencies. Review
   diff, side effects, unchanged business/C17 behavior, documents and OpenSpec. Commit
   locally, retain a final-candidate receipt, and stop for confirmation.

### Offline exit criteria

| Condition | Required outcome |
| --- | --- |
| Missing or extra check/source | Reject before child execution; no omission-based PASS |
| Tool/dependency missing | Explicit BLOCKED with no skipped-test credit; CI must fail |
| Child failure or timeout | FAIL even if another child passes or output contains PASS |
| Invalid counts/skip/xfail/deselection | FAIL; exact reviewed inventory and full test collection required |
| Source changes before/during execution | Reject or block binding; never rewrite reviewed hashes automatically |
| CI alignment | Actual tracked command covers Python, Node and named integrity/control entries; security/scanner/image gates retained |
| Evidence boundary | Offline execution separated from overall BLOCKED, privacy/rights/runtime/full RAG and C10 remain unresolved |
| Delivery | Reviewed local commit and source-bound receipt; no remote action or next increment |

## Implementation and verification

The plan above preceded implementation. The current entry is
`enterprise-agent/scripts/offline_verify.py`; `scripts/offline_sources.json` records
330 original backend/workflow source/config/data inputs and the exact eight checks
(332 inputs after the reviewed F2-05 telemetry extension).
It includes new/untracked non-ignored code when assessing coverage; added/omitted files,
unknown checks, incomplete F2 mapping and changed hashes require a fresh explicit review.
There is no auto-refresh switch. Source membership is an integrity contract, not permission
to execute every file: only the eight fixed commands are executed, never runtime evals.

The historical C24 entry/manifest and its 31 checks remain byte-for-byte unchanged. Its
old 45-case Node expectation and source drift must not be presented as current acceptance.
Current coverage is complete Python collection plus the named supplemental checks below.
Multiple checks overlap; their counts must not be summed as independent requirements.

| Check | Current coverage | Result boundary |
| --- | --- | --- |
| `python` | All 1883 tests, including C01–C25 and current F2 test modules | Zero skip/xfail/deselection/failure/guard-denial credit; local Python 3.13.15/macOS arm64 |
| `node-page` | 69 C20/F2-08/F2-07 cases, actual page methods and Vue template compilation | VM/static/compile, no DOM/browser |
| `node-credentials` | 14 memory-token/sanitizer/credential cases | VM only |
| `frontend-assets` | Seven retained JS/license files | Hash/SRI integrity, not actual served-image proof |
| `build-inputs` | 98 production package pins and reviewed build recipe inputs | No image build, OS install or installed-image acceptance |
| `provenance` | 447 pending source records and declaration integrity | Includes F2-11 walkthrough integrity; no authorship, rights or wording approval |
| `rag-controls` | Eight independent safe/unsafe synthetic pairs, exact case IDs/outcomes | Checker agreement; model robustness NOT_MEASURED, semantics PENDING |
| `safe-preflight` | Original five plan/readiness functions | Execution PASS while runtime/UAT/release remain BLOCKED |

### Commands and exit semantics

Use Python 3.11+ with the already declared production and test dependencies installed,
plus an existing Node interpreter. No dependency installation happens in these commands.
From the repository root:

```bash
# Plan only: no children, dependency imports or fixture creation.
python -I -B enterprise-agent/scripts/offline_verify.py

# Explicit local run; use a fresh receipt name. Overall acceptance stays BLOCKED (exit 2).
python -I -B enterprise-agent/scripts/offline_verify.py --execute --record local-candidate-001

# Same checks; scoped CI success only on complete, stable, clean offline evidence.
python -I -B enterprise-agent/scripts/offline_verify.py --ci --record ci-candidate-001
```

| Situation | JSON evidence | Exit |
| --- | --- | --- |
| Plan-only invocation | PLAN_ONLY | 0 |
| Child failure, timeout, malformed/omitted/duplicate evidence | execution FAIL; no release approval | 1 |
| Missing tool/dependency or source/record preflight failure | BLOCKED, no pass/skip credit | 2 |
| Checks pass but worktree is dirty or source/candidate changes | binding BLOCKED | 2 |
| Local execute passes on a stable clean candidate | execution/binding PASS, overall BLOCKED | 2 |
| CI mode passes on a stable clean candidate | execution/binding PASS, overall BLOCKED; all UAT/release flags false | 0 |

CI mode changes only the execution exit convention. It neither removes any blocked gate
nor converts reference/offline evidence into runtime or release acceptance. The existing
secret scan, complete Git-event scan, dependency audit, Docker dependency/import/inventory
and Trivy gates remain in the workflow. Docker still depends on the test job. Coverage
upload now follows the retained coverage path and missing files fail the job. No workflow,
remote artifact upload or scanner/image execution occurred in this increment; current
remote CI and Linux Python 3.11/3.13 outcomes remain unverified.

### Retained pytest and side effects

The tracked helper replaces reliance on a personal `/tmp` runner for reproducible commands.
It invokes the whole test directory without a filter option, disables automatic plugins,
pytest cache and default temporary cleanup, explicitly loads asyncio and retains fixtures
and coverage below ignored `enterprise-agent/eval/results/offline-pytest-<uuid>/` paths.
It checks installed declared production versions and required test tooling; absence blocks.
It disables dotenv and inherited application/telemetry/filter settings in that child process.
No credential values, environment maps or raw child output enter the aggregate JSON.

The diagnostic audit guard denies deletion/rename, network, arbitrary subprocesses,
private-env reads and writes outside retained results. Required read-only Git observations
are explicitly allowed. Existing symlink-escape tests may create links only when both ends
remain inside retained results; no link cleanup or outside target is permitted. Tests then
verify that the application inventory/receipt validators reject those links. The first
integration run correctly failed on an overbroad link guard; it was corrected at the
retained-fixture boundary without skipping or changing the existing assertions.

urllib3's import-time IPv6 bind probe is disabled only for this diagnostic process.
Synthetic pytest logs, node IDs, source hashes, summary and coverage are retained locally;
actual network/IPv6/host behavior is not tested. These are trusted reviewed checks with
process-level audit guards, not an OS sandbox for arbitrary untrusted code.

### Verification — 2026-10-20

- PASS: **35 new counterexample/regression tests** covering check/source omissions, missing
  executables/dependencies, failure/timeout precedence, exact/full/no-skip counts, duplicate
  JSON/Node/RAG evidence, environment preloads, source/identity drift, retained link bounds,
  CI scope and record collisions. No existing test assertion was removed or weakened.
- PASS: current entry's **eight checks**, full **1218 tests + 484 subtests**, zero skips,
  xfails, deselections or guard denials; 45 existing dependency warnings; backend coverage
  76.46%. Node 69/14 and seven retained assets PASS. Declared installed versions matched.
- PASS: source and original-mode preservation; legacy C24, application behavior, C17
  corpus/denominators and older interview/speech/deck assets unchanged. Pending rights
  remain pending. Local links/YAML/manual OpenSpec structure reviewed; strict CLI unavailable.
- Precommit run `f210-complete` has execution PASS/source stable with binding BLOCKED due
  to authorized uncommitted changes. The final clean-commit `--ci` receipt is retained under
  `enterprise-agent/eval/results/offline/f210-final-candidate.json`; its commit identity is
  reported in the handoff, without a self-referential documentation commit.
- Local execution reused the existing declared dependency view in a fresh retained Python
  runtime path; no packages were downloaded/installed. Other Python/OS/CI environments must
  run the same entry before claiming their results. Test/audit tools and CI runner versions
  remain outside F2-04's fully fixed production image profile.

F2-10/C24/C25 remain OPEN. Real runtime/full RAG, C10 two-process acceptance, L/D/O/B/S/R
matrices, historical credentials, current remote CI/image/scans and strict OpenSpec remain
BLOCKED. F2-05 private-data/provider/telemetry acceptance and F2-09 source rights remain
pending. No provider/service/image execution, migration, push/upload/dispatch, merge,
release, deployment, main-spec sync, archive or automatic next increment. Stop after the
reviewed local commit and wait for confirmation.
