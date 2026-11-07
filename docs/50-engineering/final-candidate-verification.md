# C24 offline final-candidate verification

Date: 2026-10-19. Scope: E0/E1 only. **C24 remains open; overall acceptance is BLOCKED.**
The [ISSUES acceptance criteria](../40-process/ISSUES.md#c24) remain authoritative.
C23 `6de94c6` was pushed to `origin/codex/delivery-ci-gates` and verified before this increment.

## Current F2-10 prerequisite — 2026-10-20

Use the [current offline entry and CI coverage contract](offline-verification.md) for the
current candidate. It covers all Python tests plus both Node entries, assets, build inputs,
pending-source inventory, synthetic RAG controls and safe preflight. Its own reviewed source
manifest and no-skip accounting supersede this historical fixed inventory as the current
entry. The original C24 runner/manifest below remain unchanged and intentionally reject
drift; do not refresh their hashes to imply retrospective acceptance. C24 remains OPEN,
real runtime/full RAG BLOCKED, F2-05 privacy/F2-09 rights pending and C10 OPEN.

## Reproducible entry and evidence identity

Run from the repository root, using Python 3.11+ and an existing Node interpreter:

```bash
# Inventory only; no child execution, Git calls or fixture creation.
python3 -I -B enterprise-agent/scripts/final_candidate.py

# Explicit execution; choose a never-used receipt ID.
python3 -I -B enterprise-agent/scripts/final_candidate.py --execute --record c24-candidate-001

# Receipt/parser regressions, without pytest or plugins.
python3 -I -B enterprise-agent/tests/test_final_candidate.py
```

The [orchestrator](../../enterprise-agent/scripts/final_candidate.py) fixes 31 entries:
29 test suites, the seven-file frontend integrity check and the original five-function
readiness entry. The [source manifest](../../enterprise-agent/scripts/final_candidate_sources.json)
freezes 291 source/config/fixture files. This is an identity inventory, **not permission to
execute every listed file**. Only the fixed entry points execute. The manifest deliberately
excludes the orchestrator itself (the trusted entry, hashed in the receipt), Markdown and
itself; the tracked candidate digest binds all tracked files, including those exclusions.
There is no automatic trust-refresh command. Review changed source/import/side-effect
boundaries before deliberately revising its digest and rerunning affected checks.

Receipts bind HEAD, tracked content digest, dirty state, untracked-file count, historical
mode differences, reviewed source digest, runner hash, Python/Node versions, UTC time,
entry status and test/skip counts. Check source and candidate identity before/after the
sweep. `candidate_binding=PASS` means the content is clean, stable and bound to the commit;
it is **not** application acceptance. A dirty or untracked worktree remains unbound.
Mode-only differences are recorded and preserved, not silently staged or normalized.

Results use exclusive creation under ignored `enterprise-agent/eval/results/final-candidate/`.
No overwrite, append-to-existing, rotation or deletion is performed. Symlink paths and
collisions are refused. A crash or interrupted run without a completed receipt proves
nothing; retain fixtures/partial files, choose a new ID and rerun. Candidate-bound evidence
is generated again after the local commit; its commit hash lives in the ignored receipt
and delivery response, avoiding a self-referential documentation commit.

Exit 0 is inventory-only. Executed checks return 1 if an entry fails, otherwise 2 because
acceptance stays BLOCKED. Missing prerequisites/source drift/record failure also return 2
with a fixed reason. Inspect the JSON, not just the exit code. Empty/wrong/duplicate test
counts, malformed summaries, unexpected skips and failed children cannot be PASS. No raw
stdout/stderr, exception text, environment values, credentials or application payloads are
persisted. Timeouts fail the entry; there is no business retry.

## Current offline coverage and remaining acceptance

The following counts are test methods/cases, not subtests, coverage percentages, independent
requirements or runtime measurements. Multiple suites exercise shared helpers. The seven
asset files and five readiness functions are counted separately from tests.

| Item | Current offline check / passing cases | Uncovered acceptance; entire item remains open |
| --- | --- | --- |
| C01 | Deployment 10 PASS + 1 PyYAML skip; Dockerfile 4 PASS | Actual Compose resolution, same image digest, build/Nginx/login/SSE |
| C02 | Profile 15 + remote adapters 12 PASS | Real embedding/reranker/LLM, quota/cost, installed dependency imports |
| C03 | Bootstrap/migration orchestration 22 PASS | Real PG SQL, concurrent upgrade/rollback and initialization |
| C04 | Session ownership 20 PASS | Real HTTP/PG ownership and races |
| C05 | Runtime authorization 29 PASS | Real JWT crypto, revocation, API/SSE |
| C06 | Credential safety 20 PASS; browser lifecycle included below | Real browser/SSO and historical credential review/remediation |
| C07 | Retrieval authorization 21 PASS | Actual Milvus/SQL filtering and citations |
| C08 | Request context/history/dependencies 23 PASS | Real LangGraph concurrent dispatch/history |
| C09 | Cross-process state 28 PASS | Actual two processes, Redis Lua/TTL/restart |
| C10 | Lifecycle 27 + stale-writer isolation/publication 28 PASS | Real saver/PG locking, two-process expiry races and API/SSE remain BLOCKED; C10 stays open |
| C11 | Approval lifecycle 34 PASS | PG atomic claims/expiry/crash and browser flows |
| C12 | Tool operation safety 41 PASS | PG/HTTP duplicate dispatch and uncertain response |
| C13 | Saga recovery/HTTP compensation 34 PASS | Durable PG/process failure and external inverse effects |
| C14 | Queue/worker 50 PASS | Real locking, worker restart and external dispatch |
| C15 | Knowledge publication 36 PASS | PG/Milvus indexing consistency and full RAG |
| C16 | Analysis adapter 33 PASS | Real CRM snapshots, identity and API/SSE agreement |
| C17 | Quality/metric contracts 29 PASS | Frozen 122-case real-model RAG run, six role controls, semantic review |
| C18 | Reference integration 45 PASS | R01–R20 independent persistent HTTP/application chain |
| C19 | Controlled SSO 37 PASS | S01–S16 real RS256/IdP/browser/Redis/PG |
| C20 | Delivery 45 + credential VM 14 PASS; 7 asset files PASS | B01–B16 actual browser DOM/UI/API role journeys |
| C21 | Observability 45 PASS | O01–O16 disk retention/replay, real faults, traces, firing/resolved alerts |
| C22 | Recovery 46 PASS | D01–D16 actual cold capture/fresh-volume restore, RTO/RPO |
| C23 | Capacity 42 PASS | L01–L16 actual frozen 30-minute workload, queue/resource/cost evidence |
| C24 | Safety 12 + receipt 16 PASS; five functions execute successfully | Complete application regression, E2/E3 and final runtime evidence |
| C25 | Offline reconciliation delivered separately | Git/PR/CI/support/version/document reconciliation and delivery conclusion |

Current C10 follow-up sweep: **818 tests PASS, 1 skipped/BLOCKED**, seven frontend asset/license files
PASS. Five readiness functions execute: three result PASS, two BLOCKED (UAT readiness and
release gate). They do not increase the 818 test count. Synthetic G0 is not application E2E.

## Side effects and trust boundary

- Python children use `-I -B`; no full pytest, conftest/plugin discovery or bytecode/cache writes.
  Node executes only the two reviewed VM entries; `NODE_OPTIONS`/`NODE_V8_COVERAGE` are removed.
  The existing host environment is otherwise inherited so its Git wrapper works; tests use
  synthetic configuration/injected clients, do not read `.env`, and never serialize the environment.
- C01/C02/C03 entries were reviewed for read-only source loading and injected dependencies.
  C04–C23 entry/fixture/import boundaries follow the [side-effect inventory](safe-validation.md).
  HTTP, PG, Redis, Milvus, JWT, LangGraph, Docker and model behaviors are replaced or extracted
  where stated. No service/listener/browser, dependency install, image build or paid API runs.
- C22 creates retained synthetic archive/files under `eval/results/c22-tests-<uuid>/` with
  Docker/chown injected. Safety tests retain `eval/results/safe-validation-tests/<uuid>/`;
  the synthetic symlink there is intentional and never removed. C24 receipt tests retain
  `eval/results/c24-tests-<uuid>/`. These tests may edit their newly created synthetic fixtures;
  they never delete them or modify application/user data. The orchestrator itself creates only
  the optional exclusive receipt and invokes fixed children/Git metadata commands.
- This is trusted local code orchestration, not an OS sandbox. Existing child audit hooks
  provide additional guards but cannot prove all native-code behavior is confined. The host,
  interpreters, Git wrapper, standard libraries and concurrent filesystem editors are trusted.
  Before/after hashes detect drift; they do not prevent transient concurrent edits. Do not edit
  the checkout during a sweep. Do not use this entry to run unreviewed or malicious code.

## Failures found and disposition

The first comprehensive run found an outdated C02 worker-startup test double: C21 added
imports/lifecycle behavior that the isolated extracted function did not have. Add injected
audit/tool initialization, asyncio and DB closure, and expect the current sanitized
`WORKER_FAILED` error for the worker. Still assert the model probe is attempted once,
DB/audit/tools initialization never happens after failure, and worker cleanup occurs.
No application behavior was changed. The repaired 15-case suite and full sweep pass.

An initial ad-hoc launcher stripped the host environment and broke the configured Git
wrapper (exit 126), causing three safety-test errors. The normal environment rerun passes
all 12. The durable runner preserves the host environment and only removes the documented
Node preload/coverage options. Initial failures are retained here; they are not relabelled
as successful runs. The PyYAML skip remains distinct; Ruby parsing is separate E0 evidence,
not execution of that Python test or a Compose engine.

The first Ruby YAML sweep also rejected unquoted colon-bearing flow scalars in the
reference and SSO Compose recipes. Quote only those nine strings and verify the parsed
security options and mount values. All nine reviewed YAML files then parse; this is parser
compatibility/E0 evidence, not Compose interpolation, merge or deployment.

Additional static checks: 214 Python sources compile in memory, three JavaScript sources
pass `node --check`, and two shell wrappers pass `bash -n`. No bytecode or build output
is created. Changed document links and delta structure are checked separately.

## Gates that this increment cannot close

L01–L16, D01–D16, O01–O16, B01–B16, S01–S16, R01–R20, real runtime/full RAG and historical
credentials remain BLOCKED. No enterprise evidence, formal UAT, grey release, production
approval, maximum capacity, monthly SLA or current image security claim is made.

Whole pytest/plugin/temporary-fixture behavior and actual dependency-based imports have not
been reviewed/run under the non-deletion rule. The fixed sweep covers the closeout suites,
not the entire repository test population. The current host lacks Docker/OpenSpec/ruff;
image builds, scanners/current CI, real Linux and `openspec validate --strict` are BLOCKED.
Manual delta structure/link checks are only E0, never a substitute for OpenSpec strict.

Resume runtime acceptance only after separate authorization, isolated Linux resources,
resolved C10 fencing and the prerequisite matrices/observations. Freeze candidate image,
model profile, fixtures and environment again; changed bytes invalidate affected results.
C24 stays open. C25, spec synchronization/archive, push/merge/deployment/release do not
follow automatically from this offline increment.


### C10 follow-up evidence (2026-10-19)

The 28-case fencing entry was reviewed for SQL/clock/saver substitution and side effects
before addition to the fixed inventory. No new skips or collection exclusions were added.
Local full pytest independently passes 900 tests + 232 subtests, zero skips; its retained
receipt and platform limits are in the C10 delivery record. The fixed inventory's existing
`FULL_PYTEST_DEPENDENCIES` gate is a scope limitation of that entry, not a failure of this
separately executed local suite. Remote CI/image results at earlier commits are historical
and do not validate the C10 source changes. Current C10, real runtime/full RAG, all live
matrices, OpenSpec strict and release remain BLOCKED/open.


## Stage-one technical candidate progress — 2026-11-07

This separate dated section does not rewrite historical C24 evidence above. The current
milestone is open-source usability; enterprise pilot evaluation, real-environment pilot
and production use remain later stages. Stage one is not yet accepted or merged.

- Mac arm64 Python 3.13.15 used a previously approved binary-driver adapter. Run-05
  passed 15 actual HTTP checks and 14 focused demo tests after a misleading startup-log
  correction. Two owned containers and two processes exited; data/evidence were retained.
- Run-04 actual browser checks passed login, 你好/您好, explicit unsupported pre-execution
  rejection, current-session history, refresh/login isolation, relogin and logout with
  password/authenticated-content clearing. Run-05 changed logging only, not UI bytes.
- History limitation: backend persistence and session-specific querying are established;
  current-session history can show a snapshot with unknown status, not business success.
  Refresh returns to login; relogin opens a new empty session with no visible recovery
  entry for the previous session. No complete history-management claim is made.
- Linux CI now explicitly requires system libpq5, pure psycopg, and no binary/C package,
  then fresh startup, tracked acceptance and owned stop. Actual Linux results are pending.
- Image publication is disabled by default: explicit manual publish=true on main only,
  behind existing security and C10/native checks. Three publication-policy tests covering
  27 event/ref/input combinations passed. No publication or deployment occurred.
- First full-suite attempt: 2134 collected, 2133 passed plus 640 subtests, one failure in
  an old hard-coded CI needs assertion. Its exact three-dependency assertion was repaired;
  a later full rerun passed as recorded below. This first failure is retained rather than relabeled PASS.
- Source inventory: 457 historical records plus eight new engineering fixtures = 465.
  Registration does not clear prior unknown rights. Maintainer testimony covers only
  three C17 documents (two departmental documents and after-sales policy) and eight CRM
  examples as fictional from creation; it is not evidence for other works or external grants.
- The separately authorized CRM increment now labels eight fictional customers and uses
  NOT-A-PHONE phone placeholders and example.invalid customer email addresses in current
  examples and product material. The internal-mail seed deliberately uses
  fictional-demo-manager@company.internal with a synthetic-data comment, preserving
  the existing private-domain policy. The three tests also checked the real classifier
  AST: the internal recipient is admitted, while external customer/CC cases are rejected
  or classified at their existing boundary; no mail rule was broadened. Three
  focused tests passed; orders/non-contact fields were unchanged by AST comparison. One
  new test source is included in the eight additions above. Expected final pytest count
  is 2137 (2120 + 14 demo + 3 CRM), confirmed by the precommit rerun below. Run-05 predates
  these CRM edits and is not live evidence of all final bytes; the narrow demo denies CRM
  calls. Linux CI must test the final commit. Old C17 documents and unapproved UAT phone
  changes remain outside this replacement scope.

Source uncertainty, full C10/runtime/RAG and enterprise acceptance limitations remain.
The current merge condition is stage-one readiness, not completion of later enterprise
stages, but material distribution-rights blockers cannot be hidden or silently waived.

Retained historical screenshots were not replaced and may still display historical contact details or additional unconfirmed recipients. The text/fixture update is not a claim that all visual examples or their source rights have been cleared.


### Final precommit offline rerun — 2026-11-07T13:05:20Z

The r2 aggregate receipt reports all eight checks PASS: 2137 Python tests plus 640
subtests, Node 80/14, seven assets, 81.8543% coverage and stable sources. Candidate
binding remains BLOCKED because this was a dirty precommit candidate, not a clean
committed or remote-CI result. This does not establish stage-one completion.

The second full-suite attempt had 24 failures caused by the edited demo-seed checksum.
The repair changed only schema_manifest.demo_seed SHA; an old marker is still rejected
without state mutation. All 26 focused bootstrap checks passed. That failed attempt
is retained separately from the successful r2 result, with no skipped checks or lowered
admission gate claimed.

The 39 actual-Gitleaks regression tests passed. Local documentation-link review checked
60 targets with zero missing. Linux native-driver and C10 CI execution remain pending,
as do unknown-source and historical-screenshot decisions. Final committed binding and
remote results must be checked before any conditional merge.

### Staged whitespace inspection

A staged check included newly added files that the earlier unstaged diff check did not
cover. It found extra EOF blank lines in the project-authored fictional-CRM specification;
only those redundant terminal blank lines were removed.

The verified upstream license bytes are preserved: the Fraunces, Manrope and NotoSansSC
license line-21 trailing spaces and the OpenSpec MIT license's extra EOF blank line are
intentional upstream-byte preservation, not silently stripped formatting. Consequently,
a blanket claim that the complete staged diff has no whitespace findings would be
incorrect. Earlier diff-check results describe only their actual inspected scope.
