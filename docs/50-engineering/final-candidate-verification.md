# C24 offline final-candidate verification

Date: 2026-10-19. Scope: E0/E1 only. **C24 remains open; overall acceptance is BLOCKED.**
The [ISSUES acceptance criteria](../40-process/ISSUES.md#c24) remain authoritative.
C23 `6de94c6` was pushed to `origin/codex/delivery-ci-gates` and verified before this increment.

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

The [orchestrator](../../enterprise-agent/scripts/final_candidate.py) fixes 30 entries:
28 test suites, the seven-file frontend integrity check and the original five-function
readiness entry. The [source manifest](../../enterprise-agent/scripts/final_candidate_sources.json)
freezes 287 source/config/fixture files. This is an identity inventory, **not permission to
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
| C01 | Deployment 10 PASS + 1 PyYAML skip; Dockerfile 3 PASS | Actual Compose resolution, same image digest, build/Nginx/login/SSE |
| C02 | Profile 15 + remote adapters 12 PASS | Real embedding/reranker/LLM, quota/cost, installed dependency imports |
| C03 | Bootstrap/migration orchestration 22 PASS | Real PG SQL, concurrent upgrade/rollback and initialization |
| C04 | Session ownership 20 PASS | Real HTTP/PG ownership and races |
| C05 | Runtime authorization 29 PASS | Real JWT crypto, revocation, API/SSE |
| C06 | Credential safety 20 PASS; browser lifecycle included below | Real browser/SSO and historical credential review/remediation |
| C07 | Retrieval authorization 21 PASS | Actual Milvus/SQL filtering and citations |
| C08 | Request context/history/dependencies 23 PASS | Real LangGraph concurrent dispatch/history |
| C09 | Cross-process state 28 PASS | Actual two processes, Redis Lua/TTL/restart |
| C10 | Checkpoint durability 27 PASS | Real saver/storage; **lease-expiry write fencing is still unresolved** |
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
| C25 | Not started by this increment | Git/PR/CI/support/version/document reconciliation and delivery conclusion |

Current sweep: **789 tests PASS, 1 skipped/BLOCKED**, seven frontend asset/license files
PASS. Five readiness functions execute: three result PASS, two BLOCKED (UAT readiness and
release gate). They do not increase the 789 test count. Synthetic G0 is not application E2E.

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
