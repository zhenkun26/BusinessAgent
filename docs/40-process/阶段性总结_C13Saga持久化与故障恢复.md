# C13 Saga persistence and fault recovery

Date: 2026-10-17. Change: `engineering-delivery-closeout`, task 4.4.1.
Delivery: local implementation/documentation/offline increment; C13 remains open.

## Authorization and preceding delivery

The user authorized pushing C14 to the same branch, then implementing C13 including
previously deferred HTTP compensation, and stopping before the next item. C14 commit
`59a5c14fbd41969438afea99f7c59d30b2e35a75` was pushed to
`origin/codex/delivery-ci-gates`; `git ls-remote` confirmed that exact remote head before
C13 work. C13 push is not included in this authorization.

No live APIs, stores, models, service startup, migration execution, dependency additions,
filesystem deletion, merge, deployment or release. Preserve the pre-existing executable
mode differences; Git review/staging uses `core.fileMode=false` without changing config.

## Delivered behavior

- Migration 004 and manifest add `saga_runs` / `saga_steps`; v1–v3 bytes and legacy
  `saga_transactions` stay intact. API/worker require the new schema before work.
- Bind the complete ordered Saga plan to its C12 execution UUID and forward operation IDs.
  Persist identity-only context, step definitions and distinct compensation UUIDs before
  effects. Create the retained C14 recovery job in that same transaction.
- Guard dispatch, journal transitions and inverses with database ownership/lease checks.
  Attachment and forward claims share the execution-row lock. Existing claims are never
  reset. Lease expiry cannot retract a request already sent; this is not C10 fencing.
- Persist results and expose Saga identity/state in execution output. Admin-only
  `GET /api/v1/admin/sagas/{saga_id}` returns step/job metadata without payloads, receipts,
  credentials or owner tokens. Job exhaustion remains visible beside unresolved Saga state.
- Recovery cancels prepared forward claims, queries original uncertain IDs, and only then
  compensates confirmed committed actions in reverse order. No fresh forward continuation,
  invented approval scope, replayed mutation or changed operation key after restart.
- Enable the five reference HTTP inverse shapes through the verified journal gateway:
  CRM retained tombstone, ticket closure, ticket server-side before-image restoration,
  internal mail capture recall, external mail recall request. Direct legacy compensation
  calls remain denied because they cannot establish this durable authorization.
- Validate linked receipts, hashes, service/run/resource IDs, fixed versions and restored
  values/comments. Preserve original `If-Match`; conflicts, unsupported operations,
  authorization/target drift and external recall requests cannot report full compensation.
- Saga-only queue retries are bounded by four claims and retain all evidence. Unknown
  outcomes query the same identity on later attempts; knowledge jobs still do not replay
  after dispatch. Mock inverse recovery is explicitly manual because mock resources are
  not durable; legacy rows/IDs are never executed or silently converted.

## Verification

| Check | Result | Meaning |
| --- | --- | --- |
| C13 reviewed offline entry | PASS, 34 tests | Actual coordinator/store/recovery/protocol code; SQL/HTTP/identity doubles |
| C12 action safety | PASS, 41 tests | Original identity/dispatch/receipt and approval-scope regression |
| C14 queue/worker | PASS, 50 tests | Includes Saga bounded retries, handler mapping and admin status projection |
| C03 migration/startup | PASS, 22 tests | Manifest/order/orchestration; not a real PostgreSQL migration |
| C05 authorization | PASS, 29 tests | Existing current-user/approval guards with doubles |
| C06 credential safety | PASS, 20 tests | Fixed recovery diagnostics and existing redaction boundaries |
| C08 execution context | PASS, 23 tests | Existing request/subtask scope regression |
| Safe five-function validator | Execution PASS; delivery BLOCKED | UAT/release flags remain false; expected exit 2 |
| Local source, checksum, new links and OpenSpec structure | PASS | 16 Python sources parsed, 276 valid local links, four migration hashes; not strict CLI validation |
| Real PostgreSQL/HTTP/two-process/Linux/API/SSE | BLOCKED | No live invocation or environment changes |
| OpenSpec strict CLI / full pytest framework | BLOCKED | CLI/dependencies unavailable; legacy pytest cleanup paths not authorized |

34 focused and 185 related offline tests pass. The safe entries deny network, subprocess,
filesystem writes and deletion through audit hooks. Tests do not prove SQL isolation,
locks, real FastAPI/JWT/Pydantic behavior, independent provider persistence or crash timing.
A C12 timeout fixture initially intercepted the new claim deadline because it patched
the shared asyncio module. Scoped that test double to the reconciliation gateway and
reran the suite. Link review also identified five already-broken legacy README links;
no new broken links were introduced and unrelated navigation cleanup was deferred.

Retain an exclusive local evidence receipt under ignored `enterprise-agent/eval/results/`
with final commit and source hashes; it is not release evidence.

## Remaining acceptance and stop point

C13 task 4.4.2 stays BLOCKED: isolated v3→v4/empty bootstrap and rollback, two workers,
crash before/after each forward/inverse claim and provider effect/receipt commit, late
responses, conflicts, permission revocation, partial compensation and independent ledger
verification. Same-resource inverse version conflicts require manual reconciliation in
this profile. Claim-before-send gaps without a provider receipt also remain unresolved;
no blind resend is safe. Dead jobs have no automatic reset/requeue endpoint.

C10 lease-expiry checkpoint write race remains open. C21 owns non-deleting audit replay;
the worker still does not flush legacy cache files. C11 approval final-state correctness
is not changed by this increment. C18 independent services and all earlier runtime,
browser/SSO/historical-credential, enterprise UAT and release blockers remain unchanged.
No main-spec sync or archive. Stop after the local C13 commit and await confirmation;
do not start C11. `formal_uat=false`, `release_evidence=false`, `release_allowed=false`.

## Subsequent authorized handoff

The user subsequently authorized pushing C13 and starting C11. Commit
`c42dcf808cd1fca9889beee534c1d41cde4d1650` was pushed to the same remote branch and
its exact head verified. Earlier local-only wording records the original delivery gate.
C13 runtime acceptance remains BLOCKED. See [C11 delivery](阶段性总结_C11审批领取与执行状态.md).
