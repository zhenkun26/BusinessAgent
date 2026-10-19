# CI pytest collection and regression repair

Date: 2026-10-19. Change: `engineering-delivery-closeout`, task 7.2.3.
Status: local repair delivered; remote verification pending. NOT_ACCEPTED_FOR_RELEASE.

## Authorization and Git

C25 `fe2ae78b5102cc9cc2c4e08e4939da20fd53720e` was pushed to
`origin/codex/delivery-ci-gates`; `ls-remote` returned that exact hash. The user then
explicitly authorized fixing `_redact_url` collection and subsequent failures without
skipping tests. This repair ends at a reviewed local commit; its push awaits confirmation.
No merge, release, deployment, tag, spec synchronization or archive was performed.

[C25 CI run 39205591288](https://github.com/zhenkun26/BusinessAgent/actions/runs/39205591288)
failed collection in Python 3.11 and 3.13 at the stale import. C24/C23 failures remain
historical FAIL, not relabelled by this local result. A new remote run is required after
separate push authorization; image build and vulnerability scans remain unverified.

## Changes and retained coverage

| Failure | Repair and assertion boundary |
| --- | --- |
| Removed private `_redact_url` import | Test shared `redact_text`/`REDACTED`; require credentials absent and URL host/path preserved. No obsolete production alias restored. |
| pytest discovers inherited cases against incompatible derived fixtures | Split six reusable fixture classes from concrete test classes; seven derived suites inherit fixture-only bases. All 440 original test-method ASTs in 13 files are identical. Each original case remains in its owning suite; no collection filter, skip, xfail or test deletion. |
| Client request-ID passthrough assertion | Require fresh server-owned UUID v4 IDs and reject client-selected identity, matching C21. The redirect unit fixture explicitly uses an in-memory limiter, avoiding an unintended Redis probe. |
| PostgreSQL retrieval fixtures predate C15/C17 | Include chunk identity and published snapshot, enter real publication scope, and retain namespace/role/status assertions. Database unavailability must raise its fixed error instead of pretending the search was empty. |
| Legacy Saga retry assumptions | Exercise current UUID journal ownership, reverse compensation order, unknown-result retention, legacy rejection and busy-owner rejection. C13/C18 suites retain full inverse receipt/fault assertions. |
| Tool parameter failure assertion | Require `TOOL_PARAMETERS_INVALID` and explicitly prove execution was not awaited. |
| Nested audit-hook test collisions | Unit-call the policy for synthetic OS events; test actual hook registration and suppressed denial with a retained file whose original bytes must survive. No deletion is invoked. |

Production application code, requirements, CI workflow and test-selection configuration
are unchanged. The 21 affected test/fixture hashes were manually reviewed and refreshed
in the existing 287-source C24 manifest; the fixed suite inventory is unchanged.

## Verification and environment

- **PASS:** complete local pytest discovery and execution: **871 tests, 225 subtests,
  zero skips/xfails**. Existing PyYAML deployment parsing also runs in this environment.
- **PASS:** coverage-instrumented full run: **73.40% lines (5831/7944)**. Coverage API uses
  memory-only data and writes a fresh XML report, avoiding coverage database cleanup.
  This is local coverage, not the remote pytest-cov job result.
- **PASS:** AST equality for the 440 methods moved/retargeted by fixture separation.
  Original C24 suite counts remain intact. Two additional Saga ownership/legacy cases
  supplement the updated existing retry cases.
- **PASS/BLOCKED:** unchanged fixed offline runner: **789 tests PASS**, seven assets PASS,
  five readiness functions execute; the default isolated interpreter still lacks PyYAML,
  so its one pre-existing skip remains explicitly BLOCKED. The full pytest run above
  executes that check with installed PyYAML; no new skip was added to either path.
- **PASS:** reviewed diff, 287 source-manifest identities, 343 document links and preservation
  checks. Final commit binding is recorded by the post-commit local receipts.
- **BLOCKED:** Python 3.11/Linux matrix, fresh CI, production image/import checks/scans,
  OpenSpec strict, real runtime/full RAG and all L/D/O/B/S/R acceptance matrices.

The old local virtual environment has packages but no usable Python executable. Local
verification uses mise Python 3.13.15 with an additive retained dependency view. Existing
packages are reused; eight already-declared missing/outdated packages were downloaded as
compatible wheels from PyPI, hash-verified and extracted into a fresh overlay. All production
requirement constraints match in the verification process. No project dependency was added,
no original virtual environment was changed, and no installer cleanup was executed.
This macOS package view is not proof of Linux ABI/import behavior or a clean CI installation.

The reviewed diagnostic runner is retained with each receipt. It explicitly loads
pytest-asyncio, disables plugin autoload/cache/default temp cleanup and bytecode, supplies
fresh retained tmp_path fixtures, clears project setting environment keys, disables dotenv,
and changes cwd to a fresh ignored directory before application imports. urllib3 normally
binds IPv6 loopback during import; that probe was initially intercepted. The final local
runner declares IPv6 unavailable only while importing urllib3, restores the host flag,
and keeps the network guard active. This changes diagnostic dependency setup only, not
test selection or production behavior; real networking remains unverified. Its audit hook
rejects filesystem deletion/rename, real network operations, writes outside retained results
and child processes other than the two reviewed read-only Git queries. It is a guard for
reviewed trusted tests, not an OS sandbox. Any unexpected guard denial makes the diagnostic
invocation fail, even if pytest passes; the final verified run has zero guard denials.
No test subset is selected. Only structured
counts, identities, package versions and coverage are persisted; raw logs are not retained.

Worktree evidence: `enterprise-agent/eval/results/ci-pytest-3881da878d644fa488dc6aca7db9e70e/`
contains `receipt.json`, `coverage.xml`, retained fixtures and the exact diagnostic `runner.py`.
The final full-suite receipt is produced again after commit with source hashes; the final
fixed-inventory receipt is `enterprise-agent/eval/results/final-candidate/ci-repair-final-20261019-02.json`.
These are ignored local evidence, not committed artifacts or production acceptance.

The 45 existing warnings concern short synthetic JWT keys and Starlette/httpx/cookie
deprecations; no warning filter or new dependency was added to hide them. They do not
represent an executed real IdP/browser acceptance scenario.

## Delivery boundary

The pre-edit snapshot covers 816 tracked files; all unrelated content and all modes are
preserved, including 556 historical mode-only differences. Runtime/full RAG remain BLOCKED;
C10 lease-expiry writing remains an unresolved implementation defect. C24/C25 whole items
and the independent enterprise integration/UAT changes stay open. Wait for confirmation.
