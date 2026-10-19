# Approval decisions, claims and retained outcomes

C11 offline candidate, 2026-10-17. Real PostgreSQL/JWT/API/browser/Linux acceptance
remains BLOCKED. This contract complements [tool operations](tool-operation-safety.md),
[Saga recovery](saga-recovery.md) and [queue reliability](queue-reliability.md).

## Transaction and identity contract

- A decision locks its approval row, rechecks current authority, then updates only a
  pending request with an unexpired deadline. Approval is `approved_pending_reauth`,
  never execution. Rejection does not need a requester credential.
- Batch decisions reject duplicate IDs, lock distinct rows in sorted order, and commit
  every decision together. A missing, expired, already-decided or unauthorized member
  rolls back the entire batch. The response reports zero succeeded members. Commit
  acknowledgment failure returns 503; inspect retained rows before repeating decisions.
- Resume requires the original requester and a fresh Bearer JWT, current requester
  permission and current original approver authority. It binds the exact complete C12
  plan, owner, session and operation IDs. Empty/malformed/legacy plans fail closed.
- The database uniquely binds one execution UUID to one approval. Conditional update
  records an execution claim, `executing`, and an observation deadline before tool I/O.
  A failed/uncertain claim commit never invokes a tool. Participant identity locks are
  released before external work; the existing tool gateway still rechecks authority.
- Repeated resume of an executing, unknown or final claim only returns existing status.
  Claims and operation IDs are never cleared, rekeyed or automatically replayed.
  Cancellation/crash leaves the claim for observation. There is no reset/requeue API.

## Expiry and reconciliation

Both `pending` and `approved_pending_reauth` expire using database wall-clock time.
The legacy timestamp column is interpreted as UTC; missing deadlines expire closed.
The conditional write checks time again after authorization/plan binding. A deadline
crossing that check rejects the request; the worker subsequently materializes timeout.

Once claimed, execution has a five-minute **observation deadline**, not a renewable
lease or cancellation guarantee. A request claimed before approval expiry may finish
later. The worker's existing 60-second maintenance loop scans at most 100 rows using
`FOR UPDATE SKIP LOCKED`, with least-recently-checked ordering. It expires unclaimed
requests and reads stored C12/C13 evidence for expired executing or unknown claims.
It never sends a forward operation, inverse HTTP request or manufactures user authority.
The separate C13 recovery worker owns Saga compensation. Late evidence may settle an
unknown claim. An unresolved claim is retained indefinitely for operator reconciliation.

## State meanings

| Status | Evidence / action | User meaning |
| --- | --- | --- |
| pending | No decision | Await approval |
| approved_pending_reauth | Valid approval, no execution claim | Requester must confirm before expiry |
| rejected / timeout | No valid execution claim | No execution from this approval |
| executing | Committed claim | In progress; do not submit a new equivalent operation |
| executed | Succeeded Saga, or one committed operation with a valid receipt | Execution confirmed under the selected provider profile |
| execution_failed | Finished invocation left only prepared/rejected operations, or all rejected | No confirmed successful action; claim remains retained |
| execution_unknown | Missing/in-flight/uncertain evidence | Reconcile; never infer success or retry blindly |
| compensated | C13 journal confirms all required inverses | Forward execution failed and was compensated |
| compensation_failed | C13 journal requires manual intervention | Compensation unresolved, not a success |

A stored HTTP receipt is checked against the actual C18 strict receipt validator. Mock
success is only mock-profile evidence. Multiple operations without a Saga journal cannot
be certified successful. Historical `executed` rows are preserved but not retroactively
certified by this migration; only new claimed executions follow this evidence contract.

API responses, UI labels and conversational approval-query labels distinguish these
states. Transition events are inserted into `audit_logs` in the same transaction as the
state update. Their `success` flag is true only for confirmed execution; it does not
mean that an approval/rejection HTTP request failed. Payloads contain safe identifiers,
state and actor, not credentials, full tool payloads or raw exception strings.

Notifications run after commit. A notification failure cannot roll back a decision or
relabel execution. The current internal-mail helper supports mock recording only and
refuses HTTP configuration; `mock_recorded` is not inbox delivery, and missing receipts
record `unavailable`. Durable real notification delivery remains a separate runtime/
integration gap; this increment does not claim it. C21 provides retained audit replay;
real O01–O16 replay acceptance remains BLOCKED.

## Schema and rollout boundary

[Migration 005](../../enterprise-agent/deploy/005_approval_execution.sql) adds execution
identity, claim, deadline, fixed error and last-observation columns plus indexes.
C11 introduced v5; the current complete manifest requires v1–v7 before API/worker startup.
No implicit DDL, historical token
migration or historical status rewrite occurs. Apply only through the explicitly
approved [bootstrap procedure](../../enterprise-agent/deploy/DATABASE_BOOTSTRAP.md) in
an isolated Linux/PostgreSQL copy. This turn did not execute migrations or access stores.

## Acceptance matrix

All real scenarios below remain BLOCKED; offline doubles/VM checks are supporting
implementation evidence and do not establish PostgreSQL isolation or framework behavior.

| Scenario | Required independent evidence |
| --- | --- |
| Empty install and v4→v5, repeat bootstrap, failure rollback | Actual catalog/checksums/history; old rows unchanged; API/worker refuse missing v5 |
| Two processes approve/reject/expire the same request | One legal transition and one matching atomic audit record |
| Two fresh-JWT requester resumes | One execution claim and at most one independently observed business mutation |
| Deadline crossed during auth/binding; missing legacy deadline | No new claim/effect; eventual timeout |
| Batch valid plus missing/expired/revoked member | No partial decisions/audits; duplicate IDs fail before writes |
| Kill before/after claim commit and effect/receipt commit | Retained identity; no blind forward resend; unknown remains visible |
| DB outage, uncertain commit acknowledgment and audit insertion failure | No invocation before confirmed claim; fixed safe error; retained committed state |
| Tool failure, partial Saga, inverse conflict/recall request | Consistent API/UI/conversation/audit failure or compensation state |
| Observation deadline while original task still runs | No reclaim; late evidence may settle same claim without a new action |
| More than 100 unresolved rows plus new timeouts | Bounded SKIP LOCKED scan and eventual coverage; no starvation in sustained load |
| Notification lookup/transport/audit unavailable | Main outcome retained; no false delivery; independent transport acceptance still required |
| Browser refresh/relogin and revoked requester/original approver | Accurate labels; no confirmation button for claimed states; current authorization enforced |

C10 checkpoint write fencing remains open. No enterprise UAT or release claim follows
from C11. Stop after local delivery and await user confirmation before C15.
