# Controlled business reference contract

Profile: **business-reference-v1**. Frozen design, 2026-10-17, C18 prework.
**Target service contract: independent services are not implemented or accepted.**
C12 now supplies an offline-verified forward adapter candidate; see [C12 operations](tool-operation-safety.md).
Source baseline: C10 `a57bd4ed001d86d2da304e890d01da1e7e76db41`.

This contract supplies the decisions needed by C12, C14, C13 and C11. C18 full
application acceptance remains in S5. Real CRM/mail provider agreements, C19 OIDC,
UAT and release gates remain separate. No API, service, model or recipient was called
for this document. C10's lease-expiry checkpoint write race remains in C10.

## 1. Reference environment and authority

The future reference profile contains three independent HTTP services with persistent
records, outside the BusinessAgent process. The following are **planned internal
addresses**, not deployed/reachable endpoints or credentials:

| Service | Base URL in the isolated Compose network | Existing application setting |
| --- | --- | --- |
| CRM | `http://reference-crm:8080/api/v1` | `CRM_API_BASE`, `CRM_API_TOKEN`, `CRM_TOOL_PROVIDER=http` |
| Ticket | `http://reference-ticket:8080/api/v1` | `TICKET_API_BASE`, `TICKET_API_TOKEN`, `TICKET_TOOL_PROVIDER=http` |
| Mail sink | `http://reference-mail:8080/api/v1` | `MAIL_API_BASE`, `MAIL_API_TOKEN`, `MAIL_TOOL_PROVIDER=http` |

These names/ports reserve the contract shape only; later deployment must check
conflicts, record actual topology and image digests, and keep traffic on an isolated
network. No public port or enterprise hostname is authorized. HTTPS is required if
traffic leaves that controlled network; no redirect or cross-origin credential forwarding.

Each service requires a distinct environment-issued bearer credential, with read,
write and compensation permissions. Missing/invalid credential: 401; valid credential
without permission: 403. Never use application JWTs as service credentials or accept
client-supplied role headers as authorization. Application identity/RBAC and fresh
approval checks remain mandatory before HTTP dispatch (C05/C11/C12); service tokens
alone do not prove end-user authorization. External mail requires a valid approved
frozen action and fresh requester resume; an administrator role alone does not bypass
that gate. Compromised application credentials and
multi-tenant isolation are not solved by this single-organization reference profile.

All business and observation requests carry `X-Reference-Run-Id` (UUID). The run is
pre-provisioned through a separate operator-only interface with synthetic data and
an authenticated service-principal binding; it cannot be created by business requests.
Cross-run/principal lookups return 404 without disclosure. No unauthenticated reset,
list-all, fault-control or stats route. A public health route may expose readiness
only, without records, tokens or counters. Use a fresh run, never erase earlier runs.

The mail service has **no SMTP relay, MX lookup or external-send implementation** and
its network policy denies egress. Accept only the explicit run allowlist, initially
`employee@reference.invalid`, `manager@reference.invalid`, `customer@reference.invalid`.
These are synthetic strings stored in the sink. Both `to` and `cc` must be allowlisted;
unknown recipient rejects the entire send, with zero partial capture. Internal versus
external scope still exercises application approval policy; it does not enable real
external delivery. Attachments use manifest IDs such as `fixture-brief-v1`, never local
filesystem paths or URLs. Do not fetch attachments supplied by a model/user.

## 2. Common wire format

- UTF-8 JSON object requests and responses, maximum body 64 KiB; unknown fields,
  duplicate JSON keys, non-finite/floating numbers, malformed types and invalid enum
  values reject with 422 before effects. Explicit defaults are described below.
- Resource IDs are opaque `[A-Za-z0-9_-]{1,64}`; encode path segments, reject slash,
  percent-encoded slash and traversal rather than constructing arbitrary URLs.
- GET uses `Accept: application/json`; writes also use `Content-Type: application/json`.
  All requests include the bearer and run headers. Each transport attempt has a fresh
  `X-Request-Id` UUID for diagnostics; this is distinct from logical operation identity.
- Every mutation requires `Idempotency-Key: ba-ref-v1:<operation_uuid>` (UUIDv4), including
  DELETE and compensation. No key is generated inside an HTTP retry. Invalid/missing
  key rejects with 422. Keys and full body hashes are persisted before the first I/O.
- Updates/compensations require `If-Match: "<resource_version>"`, an integer version
  observed from a prior authorized read. Missing precondition: 428; stale version:
  409 `VERSION_CONFLICT`. Replay deduplication precedes rechecking that precondition,
  so an already committed operation can return its original receipt.
- Success must match the method's documented status, schema, operation ID, resource
  ID and version. Empty/non-JSON 2xx, malformed/mismatched receipts, 3xx and unrecognized
  status codes are not success. Existing permissive adapters must change in C12.

Error envelope: `{"error":{"code":"VERSION_CONFLICT","operation_id":null}}`.
Codes are bounded identifiers; no exception text, credentials or echoed payloads.
A null operation ID means no durable operation was registered, not that every network
failure proves no business action. Responses contain `X-Reference-Profile: business-reference-v1`.

## 3. Routes, business fields and receipts

Paths below are relative to the service base URL. Field constraints are reference
choices; do not present them as real-vendor guarantees. All returned objects include
opaque ID and integer `version >= 1`. Timestamps are UTC ISO-8601 strings.

| ID | Service / method / path | Request | Required success response |
| --- | --- | --- | --- |
| B01 | CRM GET `/customers/{id}` | Optional `fields` comma-separated allowlisted names | 200 `{customer:{customer_id,version,...}}`; always include ID/version |
| B02 | CRM GET `/orders/{id}` | `include_items=0` or `1`, default 0 | 200 `{order:{order_id,customer_id,amount_minor,currency,status,version,items?}}` |
| B03 | CRM POST `/crm_tasks` | `customer_id`, `title`; defaults `description=""`, `priority=1`; resolved `assignee`; `due_date` null or YYYY-MM-DD | 201 `{task:{task_id,...,status:"open",version:1},operation:{...}}` |
| B04 | Ticket POST `/tickets` | `title`; defaults `description=""`, `customer_id=null`, `priority="normal"`, `category="general"` | 201 `{ticket:{ticket_id,...,status:"open",version:1},operation:{...}}` |
| B05 | Ticket GET `/tickets/{id}` | No body | 200 `{ticket:{ticket_id,status,priority,assignee,comments,version,...}}` |
| B06 | Ticket PATCH `/tickets/{id}` | At least one of `status`, `priority`, `assignee`, `comment`; `If-Match` | 200 `{ticket:{...},operation:{...,before:{...},after_version:N}}` |
| B07 | Mail POST `/send` | `scope` internal/external, `to`, `subject`, `body`; `cc=[]`, `attachments=[]` defaults | 201 `{message_id,receipt_state:"captured",recipients:N,operation:{...}}` |
| B08 | Each GET `/operations/{operation_uuid}` | Authorized run/principal, no body | 200 `{operation:{...},result:{original_business_envelope}}`; pending result is null |
| B09 | Mail GET `/messages/{id}` | No body | 200 `{message_id,receipt_state,version,recipients:[synthetic addresses]}` |
| B10 | CRM DELETE `/crm_tasks/{id}` | `If-Match`, `X-Compensates-Operation: <forward_uuid>`, no body | 200 `{task:{task_id,status:"deleted",version:N},operation:{...}}`; retained tombstone |
| B11 | Ticket PATCH `/tickets/{id}` (compensation) | B06 headers plus `X-Compensates-Operation`; closure fields or `{restore_operation_id:"<forward_uuid>"}` | 200 `{ticket:{...},operation:{...}}`; see compensation conditions |
| B12 | Mail POST `/messages/{id}/recall` | Internal-scope original, `If-Match`, compensation header; `{}` | 200 `{message_id,receipt_state:"recalled",operation:{...}}` only after sink state change |
| B13 | Mail POST `/messages/{id}/recall_requests` | External-scope original, `If-Match`, compensation header; `{}` | 202 `{message_id,receipt_state:"recall_requested",operation:{...}}`; never recalled |

CRM customer projected fields: `name`, `contact`, `phone`, `email`, `industry`, `level`;
all synthetic. Order `amount_minor` is an integer, currency is a three-letter code,
status is pending/completed/cancelled/refunded, item fields are `sku`, `name`, `qty`
(positive integer), `price_minor` (nonnegative integer). `include_items=0` omits items.
This exact money format differs from existing fixture `amount` floats; C12 maps tool
output explicitly, and C16 owns future analysis/summary consistency. No new CRM
analytics endpoint or dashboard claim is included; C16 must extend/version the profile
before testing analysis facts against these same source records.

CRM title 1–200 characters, description at most 2000, priority integer 0–5. Assignee
must be a seeded user; resolve the application's default requester before hashing.
Ticket title 1–200, description at most 5000, category 1–64, customer/assignee must
exist when present. Priority: low/normal/high/urgent. Status: open/in_progress/resolved/
closed; reopening closed via ordinary update is rejected (409 `STATE_CONFLICT`).
Comment is 1–2000 characters and creates a retained comment ID once per operation.
Null assignee explicitly unassigns; omitted fields remain unchanged. Empty PATCH rejects.

Mail `to` contains 1–50 unique addresses, `cc` at most 50, subject 1–500, body at most
20000 characters. This profile stores/displays plain text, never executes HTML.
Attachments must reference known synthetic manifest IDs; unknown IDs reject before
capture. `recipients` is the count of distinct `to + cc` addresses, not delivery count.

The durable `operation` object requires `operation_id`, `run_id`, `service`,
`request_hash`, `state` (pending/committed/rejected), `resource_id` (null until known),
`after_version` (null until known), `created_at`, `completed_at` (null while pending),
`effect` and `compensates_operation_id` (null for forward work). Rejected entries
also carry a fixed `error_code`. C12 makes the forward effect spellings explicit: `created` for B03/B04, `updated`
for B06, and `captured` for B07; no other effect proves those operations complete.
A committed recall-request operation means the
request was recorded; its effect is `recall_requested`, not reversed delivery.

Writes must return ID, version and complete operation receipt. A success-shaped
response without those fields is an **unknown outcome**, not proof of failure/no
side effect. `ToolResult` keeps its existing output envelope (`customer`, `order`,
`task`, `ticket`, or `message_id`); C12 will add validated operation evidence in
side effects and durable recovery storage. Mapping data must not disappear in redaction.

## 4. Durable identity, atomicity and replay

Application side (C12/C14/C13): persist UUIDv4 `execution_id` and one UUIDv4
`operation_id` for each approved logical action before dispatch. Freeze provider,
run, endpoint, normalized payload, precondition and payload hash with that action.
Reusing the same conversation, second or tool name never makes two actions identical.
Approval/resume, queue redelivery, HTTP retry and process restart reuse the same stored
identity. Missing identity or changed frozen payload denies dispatch; no default action
index, truncated key, new random suffix or identity reconstructed from a new request.
Bearer refresh does not change action identity; reauthorization still applies.

The service key space is `(run_id, service_principal_id, operation_id)` across all
mutation routes of that service. The fingerprint is SHA-256 of UTF-8 JSON for
`{profile,method,path,body,if_match,compensates_operation_id}`, with recursively sorted
keys, compact separators, no ASCII escaping and no Unicode normalization. `path` uses
validated decoded resource IDs; body has schema defaults resolved; no secret/auth or
transport-attempt headers enter the hash. Null versus omitted fields normalize only
where the schema states a default. Arrays preserve order. Services recompute the hash.

| Existing ledger state | Same key and fingerprint | Same key, different fingerprint |
| --- | --- | --- |
| None | Register pending operation atomically, then execute once | Not applicable until registration |
| pending | 202 with pending operation; no second executor | 409 `IDEMPOTENCY_CONFLICT`, zero new effect |
| committed | Original status/body plus `Idempotency-Replayed: true`; original resource/version | 409 `IDEMPOTENCY_CONFLICT`, zero new effect |
| rejected | Original rejection; no new execution | 409 `IDEMPOTENCY_CONFLICT`, zero new effect |

The service commits business effects and committed receipt in **one durable
transaction**; persist attempts separately without duplicating effects. Unique ledger
constraints and recovery of pending claims must survive service restart and concurrent
requests. Pending recovery must inspect transaction state, never rerun a possibly
committed effect blindly. A transient failure before effect may leave pending; it
must not be recorded as a terminal successful operation. No batch endpoint: partial
success means multiple logical operations in an application workflow, not a partially
captured recipient list or a half-applied single PATCH.

Retain run business records, operation receipts, tombstones and compensation links
without automatic TTL/reset for this reference profile. C18 later chooses and proves
a transactional storage implementation; this document does not install one. Restoring
an older ledger while business effects survive, changing run/store identity or losing
ledger integrity makes automatic replay unsafe: stop and reconcile, do not mint new
keys. This is a scoped reference guarantee, not universal exactly-once delivery.

## 5. Failure and retry decision table

Reference acceptance uses a five-second total client attempt deadline, at most two
retries for permitted cases, delays 1s then 2s, and a 30-second reconciliation budget.
These are test-profile budgets, not measured SLAs. C12 must implement a true total
attempt bound; current httpx timeout settings alone do not prove it. Poll outcome
at most once per second. On exhausted budget persist `unknown` at application level
for recovery/operator review; never report rollback or successful compensation.

| Result | Application interpretation / permitted next step |
| --- | --- |
| Valid terminal receipt | Confirm corresponding effect only; never infer actual email delivery |
| 202 pending | Accepted, not complete; query B08 within budget; no downstream success-dependent action |
| 401 / 403 | Stop; no retry, no fallback to mock, no token/body in logs |
| 404 resource | Terminal not found for that read; zero mutation |
| 404 operation | No receipt observed at that instant; not proof of no in-flight write; only same-key replay under this proven reference contract |
| 409 version/state/idempotency conflict, 422, 428 | Stop unchanged; no automatic refreshed-version overwrite or new operation key |
| 429 | Retry reads within budget; writes query first, then only same-key replay under proven contract; never bypass budgets |
| 501 `RECALL_UNSUPPORTED` | Terminal unsupported capability; no retry or claim of compensation |
| Timeout/disconnect/other 5xx, including post-commit response loss | Outcome unknown; query retained operation. Retry a mutation only with original identity and proven atomic dedupe, never a new key |
| Invalid JSON/receipt, 204 without required receipt, 3xx | Protocol failure/unknown outcome for writes; no blind retry or redirect, query operation |
| Unproven real-provider idempotency or unavailable query contract | Disable automatic mutation retry; persist unknown and reconcile manually |

Queries can retry within budgets because they do not mutate business records. Forward
and compensation writes use the same safety rules. A known rejection may be corrected
only as a new explicitly approved action after reconciliation, not an automatic rekey.
Per-system provider toggles remain explicit operational decisions: do not switch an
in-flight or unknown HTTP action to mock and call it successful.

## 6. Compensation and retained evidence

Create a separate durable compensation operation ID, linked to the forward ID and
its receipt; freeze its payload and precondition before first I/O. Persist both
intent and each observed result. Retry the same compensation ID after transport or
worker failure. Missing forward receipt/before-image is unresolved, not a no-op success.
C13 compensates known committed reversible steps in reverse dependency/order; unknown
steps must first be reconciled. C11 and C14 must not race another forward executor.

| Forward action | Permitted compensation and terminal proof | Conflict/unsupported behavior |
| --- | --- | --- |
| CRM create | B10 verifies original create ownership and version; retains task as deleted tombstone plus receipt | A later task change rejects 409; unknown ID/receipt cannot mean successfully deleted |
| Ticket create | B11 sets closed plus `closure_reason:"saga_compensation"`, linked to original create/version | Later unrelated update rejects; retains ticket/history, no physical removal |
| Ticket update | Service atomically records before-image with B06 receipt; B11 restore_operation_id must match its compensation header and uses the saved image under original after-version | Later update rejects 409. Retain original comments; mark original comment superseded by compensation and append linked explanation rather than erase history |
| Internal mail capture | B12 marks the controlled sink record recalled if still eligible; require terminal recalled receipt | This proves only sink recall; unsupported/released state rejects without claim of recall |
| External mail capture | B13 records a recall request; 202 is truthful `recall_requested` | Not fully compensated. Unsupported capability returns 501 `RECALL_UNSUPPORTED`; retain visible manual follow-up |

B11 has a separate compensation schema: create reversal accepts only
`status="closed"` and `closure_reason="saga_compensation"`; update reversal accepts
only `restore_operation_id`. The service derives the old field values and comment
markers from the retained forward receipt, including comment-only updates; the
ordinary B06 nonempty-update rule does not reject this explicit reversal operation.
No client-provided arbitrary before-image can overwrite a resource. The conservative
v1 rule also rejects a changed version caused by another operation or compensation
in the same workflow; C13 must expose manual reconciliation rather than silently
refresh If-Match. R13's automatic inverse path uses distinct resources. General
same-resource multi-step inverse composition would require a versioned lineage
contract extension, not an unreviewed relaxation of the conflict check.

No filesystem deletion is part of this contract. HTTP DELETE denotes a business
state transition only, with retained tombstones. The existing enterprise specification
requires a real CRM deletion contract; the reference tombstone does not certify that
vendor behavior. No current data, historical credential or backup is cleaned up.

## 7. Fault controls and future acceptance

Faults are installed by an authenticated operator on a separate control interface,
scoped to run, operation and attempt/phase. They are not triggered by natural-language
titles, arbitrary user headers or public business routes. Persist fault schedule and
redacted attempt log. Freeze implementation detail/control routing before S5 execution;
no control endpoint is deployed now. Service restart must preserve the business ledger.

Every future case records application candidate/image and resolved packages, reference
profile/service digest/schema, synthetic fixture hash, run/operation/attempt IDs,
request hash, response/status, independent ledger effect count, resource versions,
application audit and approval/queue/Saga states. Sanitized evidence is retained; no
credentials or full real-user payloads. The existing ticket harness is not authorized
for execution because it starts services and removes audit-cache directories.

| Case | Fault/input and required oracle | Implementation/acceptance owner | Status |
| --- | --- | --- | --- |
| R01 | Query customer/order, projection/items and absent ID; exact synthetic values and no mutation | C12 mapping; C18 S5 | BLOCKED |
| R02 | Login → plan → CRM/ticket create/update; expected record/receipt/version linked to audit | C12/C18 S5 | BLOCKED |
| R03 | Same operation retry, approval resume and worker redelivery; exactly one effect and original receipt | C12/C14/C11/C18 S5 | BLOCKED |
| R04 | Two distinct actions with identical body; distinct IDs and two effects | C12/C18 S5 | BLOCKED |
| R05 | Same key changed payload/path/precondition; 409 and zero extra effects | C12/C18 S5 | BLOCKED |
| R06 | Parallel same-key writes; one owner, pending/replay responses, one committed effect | C12/C14/C18 S5 | BLOCKED |
| R07 | Commit then drop socket / return 503; query/replay resolves original receipt, no duplicate | C12/C18 S5 | BLOCKED |
| R08 | Pre-commit delay/503 and pending owner crash; bounded retries/recovery, truthful pending/unknown | C12/C14/C18 S5 | BLOCKED |
| R09 | 401/403, malformed key/payload, stale If-Match and unknown recipient; no effect/no blind retry | C12/C18 S5 | BLOCKED |
| R10 | Malformed 2xx, missing ID, mismatched receipt, 3xx and 429; never false success | C12/C18 S5 | BLOCKED |
| R11 | Reference process restart after commit and before replay; same persisted receipt/effect count | C18 S5 | BLOCKED |
| R12 | Application/worker crash around dispatch and receipt persistence; reconcile before new work | C12/C14/C13/C18 S5 | BLOCKED |
| R13 | Multi-step partial success; reverse committed reversible steps with retained before-images | C13/C18 S5 | BLOCKED |
| R14 | Compensation timeout/503 after commit, then worker restart; same compensation ID, one inverse effect | C13/C14/C18 S5 | BLOCKED |
| R15 | Unrelated later update before compensation; 409 and later edit preserved | C13/C18 S5 | BLOCKED |
| R16 | Internal capture and eligible sink recall; captured/recalled receipts, no egress | C12/C13/C18 S5 | BLOCKED |
| R17 | External mail before approval, duplicate/expired approval and stale authority; zero unauthorized capture; valid fresh resume captures once | C11/C12/C18 S5 | BLOCKED |
| R18 | External recall requested/unsupported; never displayed as recalled or fully compensated | C13/C18 S5 | BLOCKED |
| R19 | Cross-run/principal read/replay and unauthorized fault/reset attempts; no disclosure/effect | C18 S5 | BLOCKED |
| R20 | Application audit/queue/provider unavailable or ledger restore mismatch; unknown visible, no mock fallback/rekey or release claim | C12/C14/C13/C18 S5 | BLOCKED |

C18 full PASS requires all applicable cases through the application entry, a separate
reference process with real persistence and real transport failures, plus the relevant
C12/C14/C13/C11 implementations. A MockTransport result, static case list or tool-only
stub does not pass these cases. No waiver of C10, browser/SSO, Milvus/JWT/PG/Linux or
enterprise-resource blockers. `formal_uat=false`, `release_evidence=false`,
`release_allowed=false` remain mandatory.

## 8. Current-code gap and handoff

| Current evidence at source baseline | Gap relative to this target | Next owner |
| --- | --- | --- |
| [CRM](../../enterprise-agent/app/tools/crm.py) builds keys from execution/request plus index default, permits absent task ID | Durable per-action identity, collision prevention, strict receipt and money/projection mapping | C12 |
| [Ticket](../../enterprise-agent/app/tools/ticket.py) creates a random key suffix; update has no key and records empty old_values | Stable forward/update IDs, GET/version precondition, before-image and conditional compensation | C12 then C13 |
| [Mail](../../enterprise-agent/app/tools/mail.py) has no send key and accepts absent message ID; real recall currently fails explicitly | Stable send identity/receipt query, controlled recipients, truthful recall states | C12 then C13; full sink C18 S5 |
| [HTTP adapter](../../enterprise-agent/app/tools/http_adapter.py) retries writes on timeout/5xx and accepts non-JSON/some non-2xx results | Operation-aware retry/deadline/unknown state, strict schema/status and redirect handling | C12 |
| [Saga](../../enterprise-agent/app/tools/saga.py) and [retry worker](../../enterprise-agent/app/core/saga_retry.py) do not establish a complete durable forward/compensation record path | Durable intent/receipt/linkage and restart reconciliation, correct final state | C13 after C14 |
| [Approval](../../enterprise-agent/app/api/approval.py) retains C11 atomic-claim/expiry gaps | One authorized execution claimant, frozen payload/IDs, truthful decision/execution states | C11 after C12-C14 |
| [Legacy stub](../../enterprise-agent/eval/ticket_stub_server.py) has in-memory ledger, unprotected reset/stats and title-triggered faults | Independent durable services, authenticated observation/fault controls, no reset cleanup | C18 S5; legacy assets retained |
| [Existing contract tests](../../enterprise-agent/tests/test_crm_mail_external.py) and [ticket tests](../../enterprise-agent/tests/test_ticket_external.py) use injected HTTP | Evidence boundary only; do not equate them with complete application acceptance | C18 S5 |
| [Checkpoint contract](checkpoint-durability.md) retains lease-expiry write race | Reference dedupe cannot fence checkpoint writes or close C10 | C10, unchanged |

Prework is complete when B01–B13, identity/failure/compensation rules, R01–R20 and this
gap map are frozen with static links checked. C12 implementation was authorized on 2026-10-17; its delivery is recorded separately; C18 S5 and real vendor tasks remain unchecked. Version this profile
before making incompatible endpoint, identity, retention or receipt changes; never
silently weaken it to fit an implementation or passing fixture.
