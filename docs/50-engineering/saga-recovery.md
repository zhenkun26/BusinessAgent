# Saga persistence and recovery

Status: C13 implementation candidate; real PostgreSQL, HTTP and Linux acceptance BLOCKED.

## Contract

Persist the full ordered C12 execution plan, identity-only context, original operation IDs
and distinct inverse UUIDs before forward I/O. Create its retained recovery job in the
same PostgreSQL transaction. The Saga ID is the execution UUID. Migration 004 adds new
tables; legacy `saga_transactions` rows are retained and are not trusted recovery input.
No startup DDL, migration execution, cleanup, tokens or credential snapshots are allowed.

A database lease and owner token guard journal transitions. The foreground owner may
execute the original plan once. After interruption, recovery aborts the remaining plan,
cancels still-prepared forward operations, and reconciles dispatched operations using
their original IDs. It never resumes new forward actions or manufactures approval scope.
Unknown outcomes block every inverse. A provider 404 is not proof of no side effect.

Compensate committed actions in reverse order, stopping at the first unresolved inverse.
Freeze each inverse request, original after-version and forward link before dispatch;
claim each inverse once. Lost responses are reconciled by ID, never replayed under a
new key. Current actor permission and provider target must still match. Revocation,
configuration drift, unavailable tools and unprovable mock outcomes require intervention.
The durable inverse of an approved external send is limited to its original receipt;
it does not grant permission for another send. Recall requests are not completed recalls.

The reference contract supports CRM tombstones, ticket closure, server-side restoration
from the retained before-image, internal capture recall and external recall requests.
Use `X-Compensates-Operation` and the frozen `If-Match`; never refresh a conflicting
version. An external `recall_requested` receipt remains manual, never compensated.
Same-resource inverse version conflicts also remain manual in this profile.

Saga recovery jobs may be retried at most four times because their handler only reconciles
claimed writes and claims previously undispatched inverses. Knowledge ingestion retains
C14's no-replay-after-dispatch policy. Exhausted/unknown jobs remain retained and visible;
no automatic reset or infinite retry. Audit cache replay remains C21. These claims do not
solve C10's checkpoint write race or provide exactly-once delivery.

## Acceptance

Offline: exercise actual coordination and protocol code with isolated in-memory doubles:
atomic plan/job setup; identity conflicts; duplicate/stale owners; cancellation before
dispatch; original-ID reconciliation; reverse ordering; partial inverse failure; all five
HTTP inverse shapes; before-image/version/link validation; lost-response reuse; recall
pending; authorization/target changes; legacy rejection; queue attempt exhaustion.

Runtime (BLOCKED): apply migration 004 only in an authorized isolated PostgreSQL copy;
crash before/after every forward/inverse claim, remote effect and receipt commit; run two
workers; validate concurrent locks, lease expiry and task/run handoff; exercise reference
R13/R14/R19/R20 and retain database/HTTP evidence without secrets. Do not close C13 from
offline doubles. Operator remediation of dead/manual rows requires a separate reviewed
plan; no generic replay endpoint or destructive reset is provided.


## Operation and verification

Run the reviewed offline suite from the repository root:
`python3.13 -I -B enterprise-agent/eval/run_c13_saga_recovery.py`.
It uses no third-party installation or live stores and denies network, filesystem writes,
deletions and subprocesses. The 34 cases pass; see the
[C13 delivery record](../40-process/阶段性总结_C13Saga持久化与故障恢复.md) for related checks.

`SagaResult.saga_id/state` and execution-agent metadata identify the retained execution.
Admin `GET /api/v1/admin/sagas/{saga_id}` exposes the run, step operation/compensation states
and associated job attempts/error, but no payloads or ownership secrets. If the job is
`dead` while the Saga is `aborting`, recovery exhausted its budget; this is not success.
A renewal runs every 20 seconds against a 120-second lease; setup/journal/claim transactions
have ten-second deadlines. Queue attempts are also bounded by the existing 300-second
handler timeout. Cancellation is cooperative; a sent request can still complete later.
The receipt/dispatch identities, not lease expiry, prevent automatic duplicate writes.
