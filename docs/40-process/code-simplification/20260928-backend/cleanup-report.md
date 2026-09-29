# Backend simplification delivery

## Progress and deliverables

Base: `5446a70cd60cf4e0729cb21bbc82b45aa6ec43c1`.
Branch: `codex/simplify-backend-internals`.
Approval: `GO FGR-01 FAT-01`. Both units are implemented, locally verified and independently
reviewed without blocking findings. Delivery is the accompanying task-only local commit;
its hash is reported in chat and available from Git, rather than recorded in another commit.

| ID | Authorization | Approval | Implementation | Benefit |
|---|---|---|---|---|
| FGR-01 | Eligible | Approved | Verified | Removes misleading, never-acquired lock state |
| FAT-01 | Eligible | Approved | Verified | Removes unused private factory return flag |
| FGR-02 | Individual confirmation required | Not approved | Retained | Public tuple API compatibility preserved |
| LEV-01 | Eligible | Not approved | Retained | Avoids work with negligible maintenance benefit |

Production changes are exactly two removed lines in vector_store.py and five expression
changes in rate_limit.py. Existing tests are unchanged. Nine new parameter-expanded limiter
cases (six functions) cover actual backend selection and middleware behavior, alongside
four unchanged HTTP adapter tests. No dependencies, environment configuration or modes were
changed, and no files were deleted. No push, PR, merge or deployment occurred.

## Verification

Commands ran from the repository root, using existing dependency files:

```sh
PYTHONPATH=enterprise-agent/.venv/lib/python3.13/site-packages python -B docs/40-process/code-simplification/20260928-backend/verify.py baseline-03
PYTHONPATH=enterprise-agent/.venv/lib/python3.13/site-packages python -B docs/40-process/code-simplification/20260928-backend/verify.py final
```

The harness changes its working directory to `enterprise-agent`. Both commands exited 0.
Python 3.13.15; pytest 9.1.1; pytest-asyncio 1.4.0; coverage 7.15.3; NumPy 2.5.1;
FastAPI 0.141.1. No installation was needed. Source/harness hashes and exact pytest arguments
are recorded in JSON. `baseline-03.json` is the accepted pre-edit baseline; `final.json` is
the corresponding post-edit result. Test and harness hashes match between those runs.

| Check | Accepted baseline | Final |
|---|---|---|
| Focused pytest collected/passed/failed/skipped/xfail | 13 / 13 / 0 / 0 / 0 | 13 / 13 / 0 / 0 / 0 |
| Pure-memory vector checks | 8 groups passed | 8 groups passed |
| vector_store.py covered/total executable lines | 112 / 171 | 110 / 169 |
| rate_limit.py covered/total executable lines | 83 / 125 | 83 / 125 |
| AST parse of two targets, new tests and harness | Passed | Passed |
| Blocked side-effect events | 0 | 0 |

The two removed executable lines were covered: the import and lock constructor. The lower
vector numerator/denominator reflects those removals, not lost execution of retained code.
These are focused module line metrics using identical settings, not whole-suite coverage.
Coverage exclusion defaults are unchanged and recorded in JSON; no thresholds were changed.

The harness disables pytest disk capture, cache, temporary-directory and logging plugins,
and disables automatic third-party plugin loading except the explicit asyncio plugin.
Coverage stays in memory, without pytest-cov's erase/save lifecycle. A Python audit hook
rejects known deletion/network events and writes outside the phase JSON. This contains
the inspected Python paths; it is not a universal sandbox for native code or subprocesses.

## Baseline failures and resolution

All attempts ran before production edits; the accepted baseline hashes match the base commit.

| Evidence | Result | Classification and response |
|---|---|---|
| baseline.json | Exit 3; no tests collected | Harness containment: pytest logging attempted a file open (its default null-device handler). The guard stopped it. Disabled the unused logging plugin; did not relax the write guard. |
| baseline-02.json | Exit 1; 10 passed, 3 failed | New tests expected ideal remaining counts 1/0, but actual base returned 0/-1. Inspected the original source and obtained independent review before correcting only the new characterization expectations. |
| baseline-03.json | Exit 0; 13 passed | Accepted baseline on unchanged production source, with exact existing behavior asserted. |

The memory limiter aliases `recent` into its stored list, appends to it, then computes
`limit - len(recent) - 1`. The remaining header is therefore one low. This is a pre-existing
behavior defect, not caused by FAT-01. The new tests explicitly characterize it; they do not
claim the values are semantically correct. Fixing it is outside this approval. Existing
assertions were not weakened, no tests were removed, and no failure was skipped.

The independent implementation reviewer agreed that exact baseline characterization is the
appropriate behavior-preserving acceptance basis and retains meaningful real-memory state
and rejection coverage. Initial failures remain recorded rather than overwritten.

## Review, restoration and evidence retention

The audit used two fresh Astra finders and an independent adversarial reviewer. A different
fresh Astra implementation reviewer checked baseline attribution and the final production
files, tests, harness, exact diff and source hashes. Final verdict: no blocking findings.
The lead also verified exact approved transformations and unchanged contents of all 31
pre-existing test files. `scope-check.json` records the boundary and retained-coverage checks.

No temporary production edits, injected faults or test-removal experiments occurred.
There was consequently no restoration step to perform. No approved candidate was reversed.

Canonical versioned evidence: audit-report.md, this report, verify.py, baseline.json,
baseline-02.json, baseline-03.json, final.json and scope-check.json. Runtime `*.log` files are retained locally
but ignored and not committed, consistent with repository log policy; their relevant error
causes and counts are captured above and in JSON. Reproduction uses the named base, the
retained harness and the same new characterization tests, never mutated production code.

## Limitations and follow-ups

- Full pytest/CI was not run. Known audit-cache and ticket-harness paths delete files;
  unrelated service/LLM/Milvus paths were not executed. Focused checks are sufficient for
  the approved local transformations, not a production readiness or release judgment.
- Python 3.11 CI, Docker builds, security scanners and live integration evaluation were not
  run; this refactor changes neither dependencies nor deployment contracts.
- ruff, mypy and OpenSpec CLI are unavailable. AST/diff/manual artifact checks are not
  substitutes for a passing lint/type-check/`openspec validate --strict` result.
- The existing virtual environment still lacks its Python entry point; explicit existing
  site-packages reuse was limited to these commands and did not repair the environment.
- The existing approval empty-tool return-arity defect noted in the audit is untouched.
  The newly identified remaining-header defect is also untouched. Both are outside scope.
- The OpenSpec change is archived at
  `openspec/changes/archive/2026-09-28-simplify-backend-internals/`. Artifacts were manually
  checked against the existing skip-specs engineering convention; no CLI result is claimed.
- Pre-existing 556 executable-mode changes remain outside the task-only commit. Filesystem
  permissions are preserved; only staged task entries use the original tracked 100644 mode.
- Push and PR creation require separate explicit authorization.
