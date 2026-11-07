# Request context, history and task dependencies

Status (2026-10-20): C08 and both F2-03 execution/SSE slices implemented and offline verified.
F2-03 runtime acceptance remains OPEN / BLOCKED; C10 is not closed.
This contract covers one graph invocation and independent task fan-out. It does
not establish checkpoint durability, same-session serialization or multi-worker support.

## Context ownership

Every dispatch creates a fresh knowledge, analysis or execution agent. Model/store
factories may still share their underlying services. ExecutionAgent receives the
current user ID, role, department, conversation ID and request ID. Standalone
construction without a request ID generates a UUID. JWT never enters these fields;
authentication and refreshed identity resolution remain the C05/C06 boundary.

Each Send carries separate copies of UserInput, SubTask and history. Knowledge
agents receive that history through their existing run interface. Independent
tasks remain parallel within two request-owned executor slots; priority is not an ordering guarantee. Replanning retains
the request/history, resets results and keeps the existing two-round cap.

## Answer ownership and history compatibility

Entry clears inherited answer, sources, confidence, error, plan error and replan
reason. Aggregation sets answer_request_id only for an answered, non-replanning
result. History requires agreement between this marker, channel request_id and
saved UserInput.request_id; it excludes the current request. Saved user, session,
role and department must match current identity. Ownership checks still run before
graph access through C04; this history filter is an additional context boundary.

History deduplicates by request ID, so identical questions in separate requests
remain separate turns. Ordinary dict, model object and constructor-envelope inputs
are supported. Both graph entry points supply their selected saver; compiled graphs
are cached by backend and saver identity to avoid reading history from a replacement
saver while invoking a graph bound to its predecessor.

Read at most 100 newest snapshots and return at most five matching answered turns,
oldest first. The async wait is limited to five seconds; C10 now aborts on read
failure instead of returning empty history. A synchronous saver read already running in a worker thread may finish
later, and driver timeouts still require C10 runtime validation. Async iterators
are closed after bounded scans. More than 100 intervening snapshots can omit older
turns. **Legacy answers without the ownership marker are excluded from model
context**, not modified or deleted; existing history-display APIs are unchanged.
Role/department changes also remove unmatched turns from subsequent model context.
Document ACL changes within an unchanged role are not retroactive history revocation.

## Supported scheduling contract

Only independent graph subtasks are supported. Any nonempty depends_on list rejects
the entire plan, including missing/self/cyclic references. An explicitly non-list
value (including null, empty string, object, number or boolean) also rejects.
Omitted depends_on remains compatible with independent legacy output. Raw output
is checked before malformed task skipping and deduplication; no dependency is
silently removed, renumbered or converted into a fallback plan. The dispatcher
checks again before creating the first Send, including the chitchat route.

The terminal plan_rejected node returns TASK_PLAN_REJECTED and this user guidance:
“当前不支持自动执行含前置依赖的任务计划。请按先后顺序分别提交任务。”
It produces no agent results, sources, approvals, tool calls or replan. Planner
classification/decomposition can already have used models; rejection adds no model
call. API normal responses and SSE final-state reads expose the fixed answer;
SSE can report plan_rejected progress. This is a completed refusal, not a tool success.

The default decomposition prompt and a code-owned suffix applied to active registry
templates request explicit dependencies and prohibit flattening ordered actions.
No live prompt rows are changed. **Model classification/omitted dependencies are
not proven correct**; undeclared semantic dependencies and dependencies inside a
single ExecutionAgent tool plan are not a general DAG. Users should submit ordered
business actions separately. Real model rejection cases remain part of acceptance.

## Verification and remaining acceptance

Run the reviewed, write/network-denied entry from repository root:

```bash
python3 -I -B enterprise-agent/eval/run_c08_request_context.py
```

The 23 tests execute actual planner/dispatcher/executor/history/aggregation/entry
code with injected framework, model and store doubles; state enums/initialization
and ExecutionAgent methods are source-extracted. They do not load real Pydantic,
LangGraph, JWT, SQLAlchemy or model providers. No service starts or dependency installs.

| Isolated acceptance case | Pass criterion | Current status |
| --- | --- | --- |
| Same-user, different sessions, overlapping requests | Tool/audit/approval context uses each request's user/session/request ID; zero cross-request history mutations | BLOCKED |
| Token refresh and role/department change | Real JWT resolves current identity; matched history only; no credential enters checkpoints | BLOCKED |
| Repeated questions, failed turns and legacy snapshots | Real saver returns correctly paired distinct turns; stale/unbound/foreign/current request excluded | BLOCKED |
| Independent fan-out and replan | Real LangGraph merges results once, carries history and honors existing replan cap | BLOCKED |
| Dependent and malformed plans | Lookup/write, missing/self/cyclic dependency cases return fixed HTTP/SSE refusal with zero agent/tool/approval effects | BLOCKED |
| Real model intent/dependency representation | Ordered natural-language requests preserve dependencies or safely refuse; active prompt versions included | BLOCKED |
| Saver failure/replacement and API/SSE behavior | C10 bounded read failure; graph/history use the same saver; no stale final answer exposed | BLOCKED |

Record candidate commit/image, isolated configuration, redacted requests/events and
zero-effect assertions. C01–C07 Milvus/JWT/PG/API/SSE/Linux/browser/SSO and historical
credential blockers remain. C09/C10, general DAG, live data cleanup, merge/deploy/
release are outside this increment. See the [C08 record](../40-process/阶段性总结_C08请求上下文与子任务依赖.md).

C10 supersedes the original read-failure fallback with fail-closed history access; see
[checkpoint contract](checkpoint-durability.md). Its real acceptance remains blocked.


## C10 checkpoint publication follow-up (2026-10-19)

The logical session remains the identity/history key. A persistent graph invocation now
requires an active C10 owned-run context and writes a unique physical checkpoint thread.
History reads accepted exact checkpoint pointers, then bounded read-only legacy history
while fewer than five accepted publications exist. Identity/role/department filtering and
fresh request state remain in force. Missing referenced data fails closed. See the
[checkpoint contract](checkpoint-durability.md) for schema v8 and the still-BLOCKED real
cross-process/race acceptance; direct unowned persistent graph calls now fail.


## F2-03 execution-budget plan — 2026-10-19

Authorization: execution resources only, plan before code, review and local commit;
SSE backpressure is a separate future increment. F2-03 as a whole stays OPEN. Runtime,
full RAG and C10 acceptance remain BLOCKED/open. No dependency, schema or deployment change.

Implementation steps and acceptance:

1. Add one request-owned, thread-safe budget shared across graph nodes, fan-out and replans.
   Reject more than four raw tasks before deduplication and before any Send; allow at most
   twelve dispatched tasks per invocation and two active executor nodes per request.
2. Bound current user input to 16 KiB UTF-8 before graph execution. Keep the newest five
   authorized history turns, with user text at 2000 UTF-8 bytes and assistant text at 800
   bytes per turn; never mutate persisted history. Truncation is explicitly marked.
3. At the real LangChain chat-model start boundary, reserve at most sixteen logical model
   calls, 64 KiB serialized messages per call and 256 KiB cumulative messages per request.
   These are byte budgets, not tokenizer estimates. Cap model output at 1024 tokens per
   call, single completion; existing OpenAI SDK retries are capped at two (at most 48 HTTP
   attempts for sixteen calls). Failed/admitted calls consume reservations without refunds.
   Embedding/reranker HTTP adapters retain their separate existing bounds; this is not a
   monetary or full-process memory budget.
4. Use a 120-second monotonic admission deadline, checked before new model/task/tool or
   approval work and final success. This is cooperative: in-flight synchronous provider
   work is not forcibly killed. Closing/cancelling a request latches its budget closed so
   inherited late worker contexts cannot admit fresh work. Existing external side effects
   are not rolled back by budget cancellation; C12/C13 recovery rules still apply.
5. Budget exceptions must bypass model/agent/retrieval fallback paths. Normal chat returns
   fixed 422 EXECUTION_BUDGET_EXCEEDED with failed state; stream sends the existing error
   event shape and never publishes success after exhaustion. No SSE queue/backpressure,
   disconnect protocol or terminal ordering redesign in this increment.
6. Offline verification must exercise boundary/over-limit inputs and plans, real LangChain
   sync/async callback enforcement, parallel reservations, request isolation, replans,
   executor concurrency/cancellation, fallback propagation and both graph/API entries.
   Run related C08 checks and full retained pytest with zero skipped tests. Inspect diff,
   document links, OpenSpec structure and original file modes before local commit.

These initial code-owned limits are deliberately conservative portfolio defaults, not
capacity measurements or proof of provider billing/latency. Real model quality under
truncation, SDK/network cancellation, multi-process load and full RAG remain BLOCKED.
SSE bounded queue/bytes/full-queue cancellation and total transport lifetime await the
next explicit confirmation. Standalone model diagnostics outside graph scope retain their
existing call accounting; router output caps apply to their constructed models in all scopes.
All router models carry the guard for scoped graph execution.


## F2-03 operating contract and limitations

Budgets are code-owned in `app/core/execution_budget.py`; no new environment setting or
store is introduced. The concurrency limit is per graph request, not a fleet-wide worker
or API capacity limit. Cached model clients share a stateless callback; the ContextVar
holds the invocation's lock/counters/slots and is never serialized into checkpoints.

The model boundary counts UTF-8 JSON of complete LangChain message objects, including
system prompts, current question, bounded history, retrieved text and intermediate
answers. It rejects an oversized prompt intact rather than silently stripping source
material. Callback errors are fatal, and fallback handlers check the latched request
budget before rules, secondary models or retrieval fallback. All admitted attempts remain
charged locally on errors; SDK-internal retry attempts are not separate logical calls.
At most 16384 completion tokens are requested across sixteen logical calls (up to three
OpenAI HTTP attempts each); this is neither actual usage nor a guaranteed monetary cap.
Provider adherence and real token/cost/latency remain unverified.

History is copied, not erased or reclassified: authorization filtering precedes trimming.
Retained checkpoint bodies and history-display API payloads are unchanged. Truncation
can reduce answer quality; real long-context/grounding evaluation is still required.
A fixed 422/error event asks clients to reduce request complexity. Streaming tokens that
precede a later refusal are partial output; no final success or accepted checkpoint is
published for that failed request. Already-started tools/approvals may have effects:
existing operation IDs and durable Saga reconciliation remain authoritative. Budget
closure does not claim transaction rollback or preemption of an in-flight call.

SSE queue bounds, byte accounting, backpressure and transport deadline are explicitly
unchanged. The next slice must test a full queue, slow/disconnected consumer, cancellation
and terminal delivery under bounded resources. F2-03 and C10 remain open until their own
remaining implementation and real acceptance criteria are met.


## F2-03 delivery evidence — 2026-10-19

Execution-resource implementation and offline review are complete; local commit only.
SSE backpressure is deferred, so **F2-03 remains OPEN / PARTIAL OFFLINE VERIFIED**.

- 34 new focused cases PASS: input/task/message/cumulative/output boundaries, atomic
  reservations, request isolation, closed inherited contexts, history copy/truncation,
  executor slots/cancelled waiters, pre-provider sync/async callbacks, real LangGraph
  propagation with synthetic agents, router/provider parameters and normal/stream errors.
- Related focused run: 97 tests + 36 subtests PASS (before the last two provider-parameter
  cases); final full retained pytest: **1007 tests + 249 subtests PASS**, zero skips,
  xfails or guard denials, **75.12%** local line coverage. macOS arm64/Python 3.13.15,
  existing declared dependency view, no install/network/model/store calls.
- Independent reviewed eval entries PASS: C04 20, C05 29, C07 21, C08 23, C10 durability
  27, C12 41, C13 34 and C17 29 (224 executions, overlapping the full suite).
  Standalone source-fixture imports initially failed after the shared module was added;
  their entry points now resolve the stdlib policy, including preloading before C12/C13
  replace the core package. The first C13 run was interrupted after its import failure
  prevented the test barrier from opening; the corrected run completes. No tests skipped.
- Two early new-test fixture names were corrected to actual role/tool names. Initial
  failures and later receipts are retained, not presented as passing evidence.
- Final full receipt: `enterprise-agent/eval/results/ci-pytest-1db97d6d1fc848e1b65b902944735254/receipt.json`.
  Review/document checks and commit binding are retained alongside it. Python app/test/eval
  hashes bind the tested bytes to the local commit; this is not remote CI or image evidence.
- Diff review, Python 3.11 syntax, local document links, YAML/manual delta structure and
  original file modes/unrelated bytes are checked before commit. OpenSpec CLI is unavailable;
  strict CLI validation remains BLOCKED, not replaced by manual syntax checks.

No dependency/schema changes, real API calls, model downloads, installations, migrations
or deployment were performed. Real two-process/provider/API/SSE/Linux, L/D/O/B/S/R,
historical credential and full RAG gates stay BLOCKED; C10 remains OPEN. The deadline
is admission-only and does not bound in-flight sync I/O or SSE transport lifetime.
Next: wait for explicit confirmation of the separate SSE backpressure slice. No push,
merge, release, spec sync, archive or next finding is authorized by this delivery.


## F2-03 SSE backpressure plan — 2026-10-20

Subsequent F2-06 [read-only RAG boundary](rag-trust-boundary.md) withholds knowledge
draft/evaluation tokens, including inherited final tags. Knowledge answers arrive in
the existing accepted final event; progress/cancellation/backpressure and eligible
non-RAG token paths remain. This prevents draft publication before citation/call checks;
it does not establish semantic or real-browser acceptance.

Confirmed scope: finish the previously deferred SSE implementation, following execution
budget commit `d52707f`. Plan first, then code, offline checks, document/OpenSpec review and
local commit. No push, merge, release, deployment, spec sync, archive or next finding.

1. Replace the unbounded event queue with one event-loop-owned channel: at most 64 queued
   data events and 256 KiB encoded UTF-8 SSE data, with a 64 KiB cap per complete frame.
   Admission waits for space for at most five seconds. An oversized frame fails with
   STREAM_EVENT_TOO_LARGE; a stalled buffer fails with STREAM_BACKPRESSURE_TIMEOUT.
   No data event is silently dropped while the stream remains successful.
2. Reserve an independent single terminal slot (also <=64 KiB). Normal completion drains
   accepted data before final. Failure/cancellation discards pending partial data, publishes
   exactly one terminal event and wakes waiters without waiting for data-queue capacity.
   EOF uses channel state, never an enqueued sentinel. Disconnect closes all admissions.
3. Validate/serialize the final payload before committing the accepted checkpoint pointer.
   Failed buffer/final admission cannot publish success. A completed database publication
   is distinct from delivery: disconnect/send/audit failure after commit cannot roll back
   external effects or overwrite completed state. Retain C10 conditional fencing.
4. Start the producer lazily on consumption, so an abandoned/unstarted response owns no
   graph task. Protect actual ASGI sends (including response headers) with a five-second
   cooperative timeout and impose a 180-second stream-response lifetime. Timeout/disconnect
   closes the channel, cancels the producer and explicitly closes its async graph generator.
   No terminal delivery is promised to a disconnected or transport-stalled client.
5. Bound status/audit/release cleanup and producer join separately (five seconds each),
   always resetting request context in a finally block. Observe late tasks and log only
   fixed failure codes if I/O suppresses cancellation; do not claim Python can kill such I/O.
   The application-buffer bound excludes one producer frame, one in-flight send frame,
   the terminal slot, framework/provider/socket buffers and Python object overhead.
6. Add offline tests for item/UTF-8 byte boundaries, oversized progress/final frames,
   producer backpressure, draining, full-queue errors/cancellation, timeout/disconnect
   before first body and mid-stream, real ASGI 2.0/2.4 behavior, failure during cleanup,
   publication ordering, task/context release and existing API compatibility. Re-run
   relevant standalone eval entries and full retained pytest without skips.

These are initial limits, not measured capacity. Real browsers/proxies/Linux/shared
stores, cancellation-resistant SDK I/O, commit-ack ambiguity and complete RAG remain
BLOCKED; C10 remains open. F2-03 implementation may be marked offline verified after this
slice, while its parent/runtime acceptance stays open. No new dependency or schema.


## F2-03 SSE delivery evidence — 2026-10-20

The plan above is implemented; review and offline checks are complete. Execution budgets
were delivered in `d52707f`; the SSE slice is a separate local increment. The dated
2026-10-19 deferrals above describe that earlier slice, not the current authorization.

| Resource / outcome | Implemented contract |
| --- | --- |
| Queued data | At most 64 frames and 256 KiB serialized UTF-8 SSE bytes, enforced together |
| Frame / terminal | At most 64 KiB including `data: ` and trailing newlines; one independent terminal slot |
| Admission | Wait at most 5 seconds; fixed STREAM_BACKPRESSURE_TIMEOUT or STREAM_EVENT_TOO_LARGE failure |
| Success | Drain admitted data before final; encode final from the validated snapshot before conditional database publication |
| Error / cancellation | Invalidate queued partial output; terminal and EOF never wait for a queue slot |
| Transport | Actual ASGI header/body sends have a cooperative 5-second limit; response lifetime 180 seconds, then cleanup |
| Cleanup | Status, audit and release each have a 5-second wait; producer join has a separate 5-second wait, then a bounded fallback release |
| Ownership | Lazy producer; disconnect before scheduling/first instruction still releases the lease; graph closes and prompt context resets in its owning task |
| Commit versus delivery | Acknowledged publication remains completed even if send, audit or lease-watch exit fails afterward |

The byte bound covers retained serialized data, not whole-process RSS. It excludes the
pending producer frame, in-flight send, terminal slot, source objects/encoding allocations,
LangGraph/provider/framework/socket buffers and Python object overhead. No fleet-wide
admission or monetary bound is claimed. Timeouts require a responsive event loop and
cooperative I/O; they cannot preempt blocking synchronous code. A cancellation-resistant
producer or cleanup task is retained/observed until it exits; context reset can only run
when the producer reaches its finally block. Disconnect closes admission and attempts an
independent lease release after the join limit, but release failure is not proof of remote
revocation. Finite join waits do not establish a bound on all retained background tasks.
A response never invoked by ASGI starts no graph; its already reserved lease still depends
on response cleanup or lease expiry. Setup before response creation is not covered by the
180-second response lifetime. No terminal delivery or effect rollback is promised after
transport failure; commit-ack ambiguity remains part of C10 runtime acceptance.

- **PASS:** 41 new offline cases; related run 120 tests + 45 subtests, then full retained
  pytest **1048 tests + 249 subtests**, zero skips, xfails or guard denials; **75.64%** line
  coverage. macOS arm64/Python 3.13.15, actual Starlette ASGI 2.0/2.4 response paths with
  synthetic sends/receives, checkpoints, leases and providers. This is not a live socket,
  browser, proxy or shared-store acceptance test.
- **PASS:** independent guarded eval entries C04 20, C05 29, C08 23, C10 durability 27 and
  C10 follow-ups 25 (124 executions overlapping the full suite). No skips or service access.
- Review/tests corrected a full-buffer disconnect classification race, pre-start producer
  cancellation cleanup and terminal delivery after acknowledged commit but failing watch
  exit. Initial fixture synchronization/media-type failures and the actual Starlette 2.4
  ClientDisconnect wrapping of send timeouts were fixed and rerun; failed receipts retained.
- Full receipt: `enterprise-agent/eval/results/ci-pytest-7d7ffbb7e7a14a10b7318d6fabc4bb22/receipt.json`.
  Review checks, related eval logs and commit binding are retained alongside it. All tested
  app/test/eval Python bytes must match the final local commit; later documentation edits
  are validated separately. This is local evidence, not remote CI.
- Existing temporary dependency paths had disappeared. Eight already declared wheels were
  downloaded from official PyPI, SHA-256 checked and unpacked into a retained isolated view;
  production requirement versions match. No dependency declaration, schema, machine-wide
  installation, model download or real business/provider API call was added. Test processes
  denied network, destructive cleanup and writes outside retained result locations.
- Source/diff review, Python 3.11 syntax, local document links, YAML/manual OpenSpec shape,
  original modes and unrelated bytes are checked before commit. Strict OpenSpec CLI remains
  **BLOCKED** because the CLI is unavailable; manual checks do not replace it.

F2-03 is **IMPLEMENTED / OFFLINE VERIFIED; runtime acceptance OPEN / BLOCKED**. Real
browser/proxy/API/SSE/Linux/two-process/store/provider, L/D/O/B/S/R matrices, historical
credential handling and full RAG remain BLOCKED. C10 is OPEN. Stop after the local commit
and wait for confirmation; no push, merge, release, deployment, spec sync, archive or next
finding is authorized by this increment.
