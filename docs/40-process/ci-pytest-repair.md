# CI pytest collection and regression repair

Date: 2026-10-19. Change: `engineering-delivery-closeout`, task 7.2.3.
Status: remote follow-up complete; `0d1a7ce` CI PASS. NOT_ACCEPTED_FOR_RELEASE.

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


## Remote CI follow-up — 2026-10-19

The user subsequently authorized pushing `b8c4457542781029333de8c3c930437fb28ef51a`,
following remote CI and repairing exposed failures. The same-name remote hash was verified.
[Run 39208343449](https://github.com/zhenkun26/BusinessAgent/actions/runs/39208343449)
passed **871 tests and 225 subtests, zero skips**, on both Linux Python 3.11 and 3.13.
Reported line coverage was 75% (5934/7944 and 5933/7944 respectively). Both jobs then failed
Gitleaks; pip-audit and Docker/Trivy did not execute. This run remains FAIL.

All 16 findings are source SHA-256 values in the C24 manifest at `d8a26b5`.
For every finding, the manifest line was parsed and its value independently recomputed
from the referenced file's Git blob at that exact commit; all matched. `.gitleaksignore`
records only those immutable commit/path/rule/line fingerprints, following the
[upstream fingerprint mechanism](https://github.com/gitleaks/gitleaks#gitleaksignore).
No whole-file, directory, hash-pattern or rule exception was added. Existing scanner
rules, vulnerability exemptions and test selection are unchanged.

The action's actual log range ended at `fe2ae78`, omitting the event head `b8c4457`.
Upstream `ScanPullRequest` lists only the first API page of commits. Add a second blocking
CLI scan using validated event base/head SHAs, complete history and merge diffs. A missing
or invalid ref fails; a new branch/manual event scans all history reachable from its head.
Disable automatic PR comments, retaining read-only token permissions and scan failure.
The reviewed workflow hash alone was refreshed in the C24 source manifest.

Local Gitleaks 8.24.3 (same version as CI) was downloaded into a fresh retained directory;
the release checksum was verified, with no dependency declaration or global install.
The full `065bdf7..b8c4457` range passes with the 16 fingerprints. A fresh synthetic API-key
value under the same manifest path still returns exit 2 with one finding. Evidence is
retained under `enterprise-agent/eval/results/gitleaks-followup-1a722c4c56ad4ddd98d20ed964e97bc9/`;
reports redact values. No real credential was used or historical credential disposal claimed.
The diagnostic attempt to override fingerprints with an empty file also loaded the root
ignore file; it was not treated as a valid negative control. The remote pre-fix scan supplies
the observed 16-finding baseline.

Follow-up CI, pip-audit and production image/Trivy remain pending at this commit.
Runtime/full RAG and all L/D/O/B/S/R acceptance matrices remain BLOCKED; C10 stays open.
No merge, publication, deployment, tag, spec synchronization or archive is authorized.

Pre-commit checks: workflow YAML and shell syntax PASS; invalid head/base and absent commit
fail closed (3/3). Fixed C24 inventory: 789 tests and seven assets PASS, one existing PyYAML
check BLOCKED; no failed entry. Dirty pre-commit candidate binding is explicitly BLOCKED.


### Follow-up image build failure

[Run 39208901960](https://github.com/zhenkun26/BusinessAgent/actions/runs/39208901960)
on pushed `16c882b` passed both Python jobs, both secret-scan steps and pip-audit.
The production image build then failed: `.dockerignore` excluded the `scripts/` directory,
so Dockerfile COPY could not read `verify_frontend_assets.py` or `recovery_archive.py`.
Trivy did not run. The failure is retained, not relabelled as runtime acceptance.

Replace the directory exclusion with `scripts/*` and two exact file exceptions. All other
scripts, tests, evaluation output and environment files remain excluded. Add a read-only
regression checking the actual Dockerfile COPY sources, file presence, narrow exceptions,
rule ordering and sensitive-file exclusions. The fixed C24 image suite grows from three to
four cases (total 790 passed checks when executed); no prior test is removed. Manually
review and refresh only the two changed source identities. Real image execution still
requires the next CI run; isolated service deployment remains BLOCKED.

Image-context validation: all four image contract cases PASS; fixed offline inventory
790 tests and seven assets PASS, one existing PyYAML check BLOCKED; failed entries zero.


### Verified remote outcome

[Run 39209313444](https://github.com/zhenkun26/BusinessAgent/actions/runs/39209313444)
for head `0d1a7ce2c26bedc4894c957c875648f131eb2993` is **PASS** across all three jobs:

- Linux Python 3.11 and 3.13: **872 tests + 225 subtests each, zero skips/xfails**;
  45 existing warnings; line coverage reported as 75% (5934/7944 and 5933/7944).
- Both Gitleaks steps PASS; the added step explicitly scans through event head `0d1a7ce`.
  Both pip-audit runs report no known vulnerabilities under the unchanged policy.
- Production `INSTALL_ML=0` image build PASS, including final non-root PostgreSQL checkpoint
  and RSA dependency imports and all seven browser distribution/license files.
- Trivy HIGH/CRITICAL gate PASS with zero findings under the existing `ignore-unfixed`
  setting and unchanged vulnerability exemptions. This is not a claim of no possible
  vulnerabilities or coverage of lower severities.
- The PR merge ref used for the image tag is `6ae256b91480154718d4e866f41fb20dfb52e232`;
  the source head is `0d1a7ce`. BuildKit reports image manifest
  `sha256:3078b20d6ec8065eb0ac92bb4a6131a23aba735af7093423433807c9ef3d1a49`
  and config `sha256:955d2612947f1f6523c8aad35da56002ef167943f5d9a8f0120a8c6cfe6d4c6f`.
  These are CI-only build identities, not a published or deployed release. GHCR login and
  publish steps were correctly unexecuted for this PR event; no test was skipped.

The documentation follow-up records this exact successful code candidate. Its own new
commit/run must be reported separately after push; this record does not predict that result.
The two earlier failed runs remain FAIL. All 817 pre-existing tracked files preserve modes;
unrelated bytes and 556 historical mode-only differences are unchanged. Runtime/full RAG,
L/D/O/B/S/R matrices, historical credential handling and OpenSpec strict remain BLOCKED;
C10 fencing and whole C24/C25 acceptance remain open. Stop for user confirmation without
merge, release, deployment, spec synchronization or archive.
