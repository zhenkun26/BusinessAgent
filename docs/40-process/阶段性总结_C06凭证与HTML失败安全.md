# C06 delivery record: credential lifecycle, redaction and HTML failure safety

Date: 2026-10-17. **Offline increment complete; real JWT/PostgreSQL/API/SSE/Linux,
browser/IdP and historical credential remediation remain BLOCKED. C06 remains open.**

The user authorized pushing C05 `9f5397c2911495b7cf1fc1b3ad3c0e289515dd55`
and then implementing C06. Push and exact remote hash were verified at
`origin/codex/delivery-ci-gates`. C06 is delivered as a local commit on the same
branch; C06 push, C07, merge, deployment and release require later confirmation.

## Delivered scope

- Approval decisions now only record approval, entering approved_pending_reauth.
  Requester confirmation with current credentials executes tools after C05 checks.
  Removed stored-token reads, refresh and writes from approval execution, and removed
  JWT from graph/identity/agent/tool contexts. The legacy nullable column and old data
  are preserved, not silently declared clean. Decisions and execution remain auditable.
- Added shared credential redaction at audit DB/local fallback/replay, Loguru record,
  application tracing and external HTTP/tool-result boundaries. Registered configured
  settings secrets, disabled SQL echo/bind-value diagnostics, and replaced public
  exception/validation text with fixed errors. No dependency added.
- Browser tokens live in memory; SSO has a one-time tab-scoped handoff. Password input
  is transmitted transiently and cleared. Logout/401 clears state and aborts streams;
  stale responses cannot restore a previous login. Auth responses disable caching.
  HTML rendering failure escapes source text instead of returning executable HTML.
- Updated C05's tests/specification/contract to the C06 confirmation-only decision
  flow without weakening current-account, role or token-subject checks. Added the
  [C06 contract](../50-engineering/credential-safety.md), historical-remediation gate,
  OpenSpec delta/design/tasks and development trackers. No main-spec sync/archive.

## Verification

| Check | Result | Boundary |
| --- | --- | --- |
| C06 Python credential-safety entry | PASS, 20 tests | Actual source/functions; injected framework/JWT/DB/HTTP/tools; in-memory audit files |
| C06 browser-script Node entry | PASS, 13 cases | Actual inline script in VM; no real browser DOM or real sanitizer |
| Updated C05 authorization suite | PASS, 27 tests | Approval-only decisions plus fresh requester resume; current-identity guards retained |
| C04 ownership entry | PASS, 20 tests | Includes actual shared redactor dependency; no HTTP/PostgreSQL |
| C03 bootstrap suite | PASS, 22 tests | Startup/schema orchestration regression only |
| C02 model-profile suite | PASS, 15 tests | Configuration/startup regression, no paid APIs |
| Existing five-function safe validation | execution PASS; overall BLOCKED, exit 2 | Formal UAT/release remains blocked |
| Python/JS syntax, changed document links, OpenSpec structure/context and Git whitespace | PASS | Not strict CLI or runtime validation |
| Full application pytest / real JWT / FastAPI / PostgreSQL / API/SSE / Linux | BLOCKED | Dependencies/runtime unavailable; no installation or real calls |
| Browser DOM/SSO/exporters and historical remediation | BLOCKED | No browser/IdP, old-store inventory, rotation, cleanup or migration performed |
| OpenSpec strict CLI validation | BLOCKED | CLI unavailable; not installed implicitly |

Initial fixture errors (tool class name and missing app-version stub) were corrected.
Review also caught Vue reserved-prefix data proxying: the authentication epoch now
uses a normal data key, and the VM fixture excludes reserved keys and verifies a
request after login. Compensation failures also sanitize results and use fixed
exception codes before reaching agent/checkpoint output; a marker regression
covers both returned failures and raised exceptions. The final checks above cover
the corrected source. Existing audit utcnow deprecation
warnings remain unrelated to credential safety. No tests performed filesystem
cleanup: audit file operations were replaced by memory buffers and mocks, with an
audit hook blocking actual deletion, writes and network activity.

Final commit/file hashes are recorded separately in ignored
`enterprise-agent/eval/results/c06-static-20261017-01.json`. The 556 pre-existing
file-mode differences remain outside the commit. No dependency installation,
real database/model call, credentials inspection, migration, deletion or release
occurred. Evidence is bounded to the final committed content.

## Limits and stop point

The [contract](../50-engineering/credential-safety.md) lists marker verification,
real browser/SSO checks and separately authorized historic-store remediation.
Old credentials are not erased or revoked by this code change. Redaction recognizes
specific structures/values, not all private prose or arbitrary encodings. External
SDK/server/exporter diagnostics need real verification. Client logout does not
revoke a copied JWT. Already admitted work is not cancelled server-side; duplicate
resume/atomic claiming and final execution states remain C11.

Stop after the local C06 commit. **C07 not started.** C01–C05 runtime blockers,
`formal_uat=false`, `release_evidence=false` and `release_allowed=false` remain.
