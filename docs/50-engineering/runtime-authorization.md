# C05 authentication and runtime authorization contract

## Current integrated approval boundary (2026-11-07)

This guidance supersedes conflicting preintegration behavior below. See the
[approved integration change](../../openspec/changes/integrate-local-delivery-security/proposal.md).
Approval records a decision only; the original requester must explicitly confirm with
fresh authentication. Batch decisions are atomic decisions, never batch execution.
Before each dispatch, enforce the exact committed approval, current participant/tool
permissions and UTC deadline. A mixed QUERY + approved ACTION plan fails closed:
run the query separately, then request approval for the action-only plan. Durable action
receipts cannot certify query results.

Stop on failure or unknown effects; never automatically compensate an approval execution.
Retain late receipts as evidence without automatically clearing a manual hold. Legacy
records without trusted provenance stay held; neither reapproval nor replacement requests
are a supported bypass. Authorized `GET /approval/{id}/evidence` (under `/api/v1`)
returns safe per-operation summaries, not a release capability. No release endpoint exists.

Managed schema v9 retains C10 v8 and adds approval guards. Follow
[database bootstrap](../../enterprise-agent/deploy/DATABASE_BOOTSTRAP.md), not the
historical standalone main 009 script directly. No database migration, service or deployment
was run for this documentation alignment. Real runtime/full RAG/C10, privacy and rights
acceptance remain BLOCKED or pending; historical synthetic results do not clear those gates.

## Preintegration contract and evidence (historical scope)

Status: C05 offline increment implemented on 2026-10-17; F2-01 follow-up offline verified
on 2026-10-19 with real PyJWT and in-process ASGI. **Live PostgreSQL/Redis/proxy, API/SSE
and Linux acceptance remain BLOCKED; C05 and C10 remain open.**

F2-02 subsequently changes Redis failure/recovery policy; see [the current cross-process
contract](cross-process-state.md#f2-02-rate-limit-failure-and-recovery-plan--2026-10-19).
The F2-01 evidence below retains its historical scope and counts.

## Request authentication

[RBAC](../../enterprise-agent/app/security/rbac.py) verifies the configured signing
algorithm/key and requires `sub` and `exp`. The subject must be a nonempty string
of at most 64 characters; expiry must be numeric, finite and in Unix timestamp
range 0–253402300799. Missing, malformed, forged or expired credentials return 401.
Existing tokens without expiry must be replaced by logging in again.

With `AUTH_CHECK_DB=true`, every protected request resolves the active account
from `users`. Role and department come from the database, including a null
department; token claims cannot fill missing identity fields. Deleted/disabled
accounts and unrecognized roles return 401. Query, connection/factory or session
failures return fixed 503 errors and a fixed warning without raw exception text.
Recovery requires no restart or cached-denial reset. Failed authentication prevents
the dependent route from running; actual FastAPI dependency/SSE ordering still
needs the live acceptance below.

`AUTH_CHECK_DB=false` remains an explicit **development-only** token-identity
option. It is rejected at request time outside `APP_ENV=dev`, and never applies
to approval execution. Do not use it for revocation/security acceptance.

## F2-01 implementation plan — 2026-10-19

Authorized after audit `edf5f63`; implement only the rate-limit identity trust fix.

1. Add real-PyJWT regression cases for unsigned/forged/expired/malformed subjects,
   missing or invalid expiry, algorithm mismatch, oversized credentials, rotating subjects,
   victim-key poisoning, legitimate identities and downstream identity denial.
2. Reuse `decode_identity_token` without expiry relaxation for limiter subjects. Invalid
   credentials remain in the source-IP bucket; only signed, current, bounded identities
   can select `user:<sub>`. Reject Authorization values over 8192 characters before decoding.
   Accept case-insensitive Bearer schemes consistently with business authentication.
3. Keep login-prefix requests on source IP even with a valid bearer, because a supplied
   token is not the account whose password is being checked. Other verified subjects keep
   separate user quotas, including users sharing one source IP. Do not trust forwarded
   headers here; the ASGI server/proxy determines `request.client`. Anonymous clients on
   one source IP share an existing bucket; reverse-proxy trust policy is not changed.
4. Token verification for quota selection is not account authorization. Run the original
   dependency on protected routes, preserving current-account 401/503 and no route effects.
   Keep existing route limits, bypasses, 429/header format, Redis fallback policy and counter
   semantics. The existing in-memory remaining-header off-by-one is outside this increment.
5. Run failing counterexamples, focused tests, C05 offline evaluation and the full retained
   pytest diagnostic without skips; review source/docs/modes, then local commit only.

Acceptance: one source cannot rotate forged subjects to evade its anonymous quota; forged
subjects cannot consume a victim's user bucket; genuine users are isolated and still need
business authorization. In-process ASGI and real JWT tests provide offline integration
coverage, not live Redis/PostgreSQL/proxy/Linux acceptance. F2-02 and all runtime/full RAG
matrices remain BLOCKED/open; no dependency, schema, deployment or release changes.

## Production startup

Both API and worker validate production configuration before model probes,
database initialization, audit flushing or queue consumption. In `APP_ENV=prod`,
either `AUTH_REQUIRE_PASSWORD=false` or `AUTH_CHECK_DB=false` rejects startup.
Production Compose pins both flags to `true` for both services; `.env.example`
also enables both. Local password-free demonstrations require explicit dev
configuration and are outside the production delivery contract.

## Approval authorization matrix

All account lookups use bound SQL values. Approval checks use `FOR SHARE` in the
request's transaction, locking the distinct participant IDs in sorted order.
The lock is intended to serialize account revocation/role changes against the
authorized execution interval; it does not lock or atomically claim approvals.

| Entry | Fresh identities | Required authority | Token policy |
| --- | --- | --- | --- |
| Single approve | Requester + current approver | Approver's current role in persisted `approver_roles`, or current admin; requester may use **every** planned tool | C06: no stored token is read; decision only enters approved_pending_reauth |
| Batch approve | Both identities for each item | Same checks per item; stale request-level approver role is ignored | C06: no execution during batch decision; requester must resume |
| Resume | Requester + **original persisted approver** | Both active; original approver still authorized and requester still allowed every tool | Explicit fresh bearer credentials required; never fall back to stored token |
| Reject | Current approver | Current approver role still allowed, or current admin | No requester token needed; no tool execution |

Approval role lists must be nonempty lists of known roles, including for admin.
Missing original approver denies resume. Missing/disabled/invalid-role accounts
return 401; lost approval/tool permission returns 403; malformed tool payload
returns 400; identity-store failure returns 503. The helper never defaults a
missing requester to salesperson or shared-company department, and no permissive
exception handler bypasses permission checks. Tools execute as the requester.

C06 supersedes the stored-token execution path: all approved decisions enter
`approved_pending_reauth`, and only requester resume executes. No legacy token is
read, refreshed or written; invalid supplied resume credentials deny execution.
See [credential safety](credential-safety.md) for the current lifecycle and migration
limits. Current-account checks precede approval writes and execution; the token is
validated after lock acquisition, before tools run.

Authorization failure leaves that approval unchanged and calls no tools or result
notifications. Single/resume failures precede success audit. Batch reports safe
per-item errors and may emit an outcome audit; other authorized decisions may
commit. Batch decisions no longer execute tools. Resume's external effects still
cannot be undone by database rollback; atomic claiming remains C11.

## Offline checks and required live acceptance

From the repository root, run the reviewed, write/network-free entry:

```bash
python3 -I -B enterprise-agent/eval/run_c05_runtime_authorization.py
```

The current 29 stdlib tests execute actual RBAC/approval source with dependency injection
and actual configuration/startup function bodies. JWT fixtures drive failure
branches and assert decode options; they **do not implement cryptographic
verification**. Fake SQL asserts predicates, lock intent and ordering, not real
PostgreSQL locking. Real PyJWT tests were added to
[test_rbac_active_check.py](../../enterprise-agent/tests/test_rbac_active_check.py),
and have since passed in the retained declared-dependency local diagnostic. The original
C05 implementation record predates that environment; real services remain unavailable.

In an explicitly authorized isolated candidate, bind commit/image, synthetic
identity IDs and before/after digests, then verify:

1. Real signed/forged/expired/missing-claim tokens; A/B identities; missing,
   disabled, downgraded and restored users. Denial must leave business tables,
   graph/checkpoint state, mock tool outputs and notifications unchanged.
2. Fail the identity connection/query and recover it. Protected HTTP requests
   return 503 before route work/SSE headers or events. No old-token fallback and
   no credentials or connection details appear in responses or warnings.
3. All three execution entries across requester and approver revocation/downgrade,
   including changes between request authentication and execution. Resume must
   reject a missing or revoked original approver and a different token subject.
4. Real PostgreSQL transactions: hold the authorization locks, attempt account
   changes from another connection, verify serialization, exception/session
   teardown and eventual lock release. Measure lock wait during slow tools;
   account changes may wait for already authorized work to finish.
5. Valid single/batch decisions invoke no tools; requester resume reaches only the
   synthetic tool sink. Expired or wrong-subject resume credentials do not execute
   or get persisted. Mixed batches preserve item-level decision denials.
6. API and worker both refuse each unsafe flag before external startup; safe flags
   permit normal startup. Re-run existing password, RBAC, ownership and production
   settings pytest suites using declared dependencies, then Linux deployment checks.

## Explicit limits and adjacent increments

This is admission/approval execution authorization, not mid-flight cancellation of
already admitted graph/SSE work. The development opt-out cannot prove revocation.
C06 now removes new credential persistence; historical stores still need separately
authorized remediation. These increments do not add per-token revocation or
password-change invalidation, complete SSO acceptance (C19), or fix approval expiry,
duplicate concurrent execution, external-effect atomicity or final states (C11).
Holding identity locks across a batch/tool call has an operational wait cost;
real locking, concurrency and throughput are unmeasured. No production-readiness
or release claim follows from offline tests.


## F2-01 delivery evidence — 2026-10-19

The plan above was saved before editing implementation. The middleware now calls the same
`decode_identity_token` as business authentication, with no expiry relaxation. It never
uses `JWTManager.get_expiry` or unsigned payload decoding for quota identity. Login-prefix
requests stay on source IP even with a valid token; invalid credentials on other routes
share the anonymous quota. Valid subjects keep their user quota, with business authentication
still responsible for current-account checks. No database request was added to middleware.

Compatibility: a caller previously using forged, expired, no-expiry or malformed JWT claims
now shares its IP quota. A valid token no longer changes the login quota. Oversized headers
remain anonymous for quota selection; the cap is not a new global HTTP-header rejection
policy. Protected routes still run their original decoder/account lookup. Production proxy
source-address trust, Redis fallback and existing remaining-header arithmetic are unchanged.

| Evidence | Result and boundary |
| --- | --- |
| New tests before implementation | 24 FAIL, 6 PASS: expected counterexamples; retained, not skipped |
| New real-JWT / in-process ASGI cases | 30 PASS within related and full runs; DB rows and failures are doubles |
| Limiter / RBAC / runtime authorization / app-entry regression | 87 tests + 35 subtests PASS; includes the 30 new cases |
| Reviewed C05 eval entry | 29 tests PASS; injected-dependency checks, not a cryptographic runtime test |
| Complete local pytest | 955 tests + 249 subtests PASS; zero skips, xfails or guard denials; 74.11% local line coverage |
| Documentation / scope | 359 local link targets, YAML and manual OpenSpec structure PASS (23 deltas, 111 requirements, 159 scenarios); 220 Python hashes match the full receipt; original modes/unrelated bytes preserved |
| Environment | macOS arm64, Python 3.13.15; retained installed packages match declared production requirements; no installation |
| Real Redis/proxy/PostgreSQL/Linux, remote CI and full RAG | BLOCKED; not run; all prior matrices and C10 remain open |

Retained receipts under `enterprise-agent/eval/results/`:

- Before fix: `ci-pytest-45b0efab85b2412d8458527623e4975d/receipt.json`.
- Focused: `ci-pytest-caf95ba830854c71be94361478274e7f/receipt.json`.
- Full: `ci-pytest-611fbd37489749499a215b3b1eb6b195/receipt.json` plus `runner.py` and coverage.

The full receipt names parent `edf5f63` and hashes the tested working tree, including the
new test file. Final code bytes must match those hashes after documentation updates; a
postcommit binding records the final local commit. No test or security assertion was skipped.
An existing login-key test changed its expected bucket to the newly specified source-IP
policy; the real-token tests independently exercise that contract.

Reproduction with declared test dependencies: from `enterprise-agent/`, run
`python -B -m pytest tests/test_rate_limit_identity.py tests/test_rate_limit.py
 tests/test_rbac_active_check.py tests/test_runtime_authorization.py tests/test_app_entry.py`.
For this workspace's no-deletion/no-network policy, the retained diagnostic runner is the
reviewed execution method: `python3 -I -B <retained runner.py>`, with `-k` used only for the
focused run and no selection filter on the full run. Run C05 from repository root with
`python3 -I -B enterprise-agent/eval/run_c05_runtime_authorization.py`.

Before live acceptance, exercise forged-sub rotation and victim isolation through the real
proxy and Redis, prove the intended client IP is retained, confirm separate genuine users,
and repeat disabled-account/store-outage denials against PostgreSQL. Do not use memory-only
or in-process tests to certify those gates. The historical F2 report remains fixed to
`c57d473`; ISSUES carries the current F2-01 resolution. F2-02 and remaining fixes await the
next confirmation. Local commit only; no push, merge, release, deployment or archive.
