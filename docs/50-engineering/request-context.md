# Request context, history and task dependencies

Status: C08 offline implementation delivered; real runtime acceptance **BLOCKED**.
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
tasks remain parallel; priority is not an ordering guarantee. Replanning retains
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
