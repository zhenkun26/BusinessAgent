# Tool operation safety (C12)

Status: offline implementation candidate, 2026-10-17. Real PostgreSQL, HTTP,
LangGraph, approval/API/SSE and isolated Linux acceptance remain **BLOCKED**.
Reference: [business-reference-v1](reference-business-contract.md).

## Identity and persistence

`tool_executions` retains one execution UUIDv4 and the normalized ordered plan.
Its unique scope hashes authenticated user, session, request, graph task slot and
partition (`direct` or `approval`). `tool_operations` retains one UUIDv4 per slot,
intent, frozen wire request, state and receipt. Identical actions in separate slots
or new user requests remain distinct. Repeating the same scope requires an identical
plan; a changed replan fails closed. This is not semantic deduplication of separately
submitted user messages. A replan must not invent another task ID to replay uncertain
business work; full graph/queue recovery and replan policy require C13/C14 acceptance.

Creation and approval both persist identities before tool dispatch. Approval payloads
retain those IDs and normalized targets. Resume uses the original IDs after fresh
requester-token and current participant checks; legacy approvals without IDs return
409 `APPROVAL_ACTION_IDENTITY_REQUIRED`. They need review and a new approval only
after checking that no prior effect exists. Tokens never enter these records.
Credential-shaped action content is rejected rather than stored with a changed hash.
Business payloads/receipts are retained application data: restrict database access and
include them in the future backup/retention policy; no TTL or automatic cleanup.

Migration `002_tool_operations.sql` is additive and checksum-pinned in the existing
manifest. The v1 baseline bytes are unchanged. API/worker schema checks now require
v2; operators must use the existing explicit C03 bootstrap path on an authorized
isolated database before startup. No migration was run in this increment. Never
restore an older action ledger alongside newer provider effects and blindly retry;
stop traffic and reconcile before recovery (C22).

## Dispatch and uncertain outcomes

The gateway checks current DB identity/role on every action, including replay, and
cannot bypass action RBAC through `skip_rbac`. It verifies persisted owner/session,
tool, parameters and current provider/endpoint/run/principal against the frozen intent.
External mail additionally needs a transient authorization scope issued by the
fresh-token approval execution path, bound to the exact stored calls. Context flags,
service credentials or administrator role alone do not grant this scope. C11 still
owns approval expiry, atomic decision/claim and truthful API/UI execution statuses.

Before external mutation, freeze the canonical wire body and If-Match, then commit
an atomic `prepared -> dispatched` update. Only its winner sends. The claim is never
reset or automatically reclaimed. Dispatched/unknown re-entry queries the original
`/operations/{uuid}`; it does not send again. Receipt persistence must succeed before
reporting success. If local persistence fails after send, the retained dispatch claim
prevents a duplicate send on recovery.

A crash after claim but before send can leave no external effect and an unknown local
outcome. This intentionally requires reconciliation rather than unsafe automatic
re-execution. A 404 observation is not proof that an earlier write cannot commit.
The code permits **zero automatic mutation retries**, even for the reference profile;
this is stricter than its maximum permitted retry budget. No general exactly-once,
queue ownership or complete Saga recovery claim is made.

Each transport attempt has a five-second total asyncio deadline, bounded 64 KiB JSON
stream, no redirects, no duplicate keys/non-finite/floating values. Read retries are
capped at two (1s/2s backoff); writes always attempt once. Reconciliation is bounded
by 30 seconds and polls no faster than once a second. 401/403/409/422/428/501 stop;
unknown/invalid receipts never become success. The HTTP error alone is not a rollback
receipt. An unknown action stops downstream work and automatic inverse writes.

## Forward adapters and configuration

No dependency is added. Existing per-service provider switches remain in use,
including the now-respected ticket override. HTTP business adapters require explicit:

```dotenv
TOOL_REFERENCE_PROFILE=business-reference-v1
TOOL_REFERENCE_RUN_ID=<operator-provisioned-UUIDv4>
TOOL_REFERENCE_PRINCIPAL=<stable-service-principal-label>
```

Use existing CRM/TICKET/MAIL base URLs and separate environment credentials.
Plain HTTP is accepted only for the reserved `reference-crm`, `reference-ticket`,
`reference-mail` hosts; other endpoints require HTTPS, `/api/v1`, no URL credentials,
query or fragment. The principal label identifies the operator-provisioned binding
for each service; it is not authentication. Rotating a token for the same principal
does not change identity. Changing principal/run/provider/endpoint requires resolving
all in-flight operations first; old operations refuse changed configuration. An
unproven vendor profile is disabled, with no fallback to mock. No services are started
by setting these variables. Compose already passes the environment file to API/worker.

- CRM defaults resolve assignee before hashing; projected customer fields are
  allowlisted. Order integer minor units/currency are retained and mapped to the
  existing `amount` display value; analytics consistency remains C16.
- Ticket update reads the authorized resource version, freezes it, then sends
  If-Match with the original operation key. A concurrent winning freeze supplies
  the retained precondition; no version refresh is used to overwrite a conflict.
  Explicit null assignee is preserved; omitted fields remain omitted.
- Mail captures only the reference allowlist; both to/cc are checked. Internal scope
  excludes the synthetic external customer and external scope requires approval.
  Attachments accept only `fixture-brief-v1`; no file/URL fetching. Recipient count
  is distinct to+cc. The answer says captured, not delivered to a real mailbox.
- Success requires matching status/profile and a complete committed receipt bound
  to operation/run/service/hash/resource/version/effect. Create/update/capture use
  `created`/`updated`/`captured`; missing IDs or mismatched content cannot succeed.

Mock remains a development demonstration. It passes through action identity and
current authorization gates, but its business objects and compensation are process
memory. It cannot prove provider persistence or complete restart recovery.

## Recovery boundary and verification

Legacy HTTP compensation cannot establish an independent durable inverse identity,
so CRM/ticket/mail inverse methods now return `DURABLE_COMPENSATION_REQUIRED` without
HTTP writes. Missing evidence is failure, not a successful no-op. Compensation errors
are not displayed as a completed rollback. C13 now implements the linked-ID/versioned
HTTP inverse path exclusively through its verified [Saga journal](saga-recovery.md).
Unjournaled direct compensation stays denied; real provider acceptance is still BLOCKED.

Reviewed offline command, from repository root (Python 3.11+):

```bash
python3.13 -I -B enterprise-agent/eval/run_c12_tool_operation_safety.py
```

The stdlib suite executes actual store/gateway/HTTP/receipt/Saga functions with injected
SQL/transport/identity doubles and an audit hook denying network, filesystem writes,
deletion and subprocesses. It tests orchestration, not PostgreSQL locks/constraints,
httpx transport, real JWT/Pydantic/LangGraph or independent provider ledgers. Existing
pytest contracts were updated, but full pytest remains unexecuted; its temporary-file
cleanup and dependency requirements are outside this safe entry. Do not run the old
service harness, audit-cache cleanup, migrations or live API tests automatically.

See [C12 delivery record](../40-process/阶段性总结_C12工具幂等与安全重试.md)
for counts and acceptance gaps. C10 fencing, C18 R01–R20, all earlier runtime/browser/
SSO/history blockers, enterprise UAT and release remain open. C14/C13 offline candidates
are implemented; real queue/Saga integration remains BLOCKED.
