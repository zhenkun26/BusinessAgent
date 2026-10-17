# C05 authentication and runtime authorization contract

Status: offline increment implemented on 2026-10-17. **Real JWT/FastAPI,
PostgreSQL, API/SSE and Linux acceptance BLOCKED; C05 remains open.**

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

The 27 stdlib tests execute actual RBAC/approval source with dependency injection
and actual configuration/startup function bodies. JWT fixtures drive failure
branches and assert decode options; they **do not implement cryptographic
verification**. Fake SQL asserts predicates, lock intent and ordering, not real
PostgreSQL locking. Real PyJWT tests were added to
[test_rbac_active_check.py](../../enterprise-agent/tests/test_rbac_active_check.py),
but application dependencies and full pytest execution are unavailable locally.

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
