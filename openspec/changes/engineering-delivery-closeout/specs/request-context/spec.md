## ADDED Requirements

### Requirement: Optional Cohere and BGE results are complete candidate-bound scores
Optional Cohere/BGE reranking SHALL validate input types/text and positive integer top_n
before backend work. Cohere SHALL admit only a complete unique/in-range integer index set
with finite real [0, 1] scores. BGE SHALL admit one finite real scalar per candidate in a
one-dimensional vector and use stable sigmoid without accepting non-finite values. Both
SHALL preserve original full content/source/ACL metadata, stable input ties, whole-batch
failure and budget/cancel propagation. No result SHALL authorize actions or certify
relevance truth, SDK compatibility, privacy or runtime acceptance.

#### Scenario: Invalid result or extreme finite model output
- **WHEN** results have invalid indices, count/shape mismatch, coerced/structured/non-finite
  values, or BGE returns extreme finite logits
- **THEN** invalid batches fail completely for existing coarse fallback, finite extremes
  convert without overflow, and only original candidates can appear in successful output

#### Scenario: Interrupted optional backend
- **WHEN** the budget expires or cancellation occurs before/after backend work
- **THEN** scoring cannot become a successful fallback; factory/stage follow-up, real SDK/
  semantic/runtime/full RAG/privacy/F2-09 acceptance and C10 remain deferred or open

### Requirement: Optional LLM rerank scores have no instruction or publication authority
Optional LLM reranking SHALL place fixed read-only policy above validated effective task
templates and separate JSON query/candidate data. Replies SHALL contain only a bounded
ASCII integer 0–10 with no native/legacy calls or structured content. Scored results SHALL
preserve original candidate identity/content/ACL metadata and stable ties. Any ordinary
failure SHALL invalidate the whole scoring batch for existing coarse/vector fallback;
budget exhaustion/cancellation SHALL propagate. Raw score candidates SHALL remain hidden
even with inherited final tags. These checks SHALL NOT establish relevance truth, model
resistance, real acceptance or permission to execute tools.

#### Scenario: Hostile data or invalid score during a batch
- **WHEN** query/chunk/template data spoofs instructions or any model response is invalid
- **THEN** data roles remain fixed, no tools execute, no partial or mixed-scale scores
  escape, and the existing retriever returns coarse results with stage `vector`

#### Scenario: Valid scores, exhaustion or inherited stream tags
- **WHEN** scores pass admission, the request budget/cancellation interrupts scoring,
  or score events inherit a final-answer tag
- **THEN** only original candidates can be reordered, interruptions cannot become successful
  fallback, score drafts stay hidden, and runtime/full RAG/privacy/F2-09/C10 gates remain open

### Requirement: Chitchat fallback has no business or tool authority
The chitchat fallback SHALL separate fixed read-only System instructions from bounded
human message JSON without display names/history/identity/tool catalogs. Canned replies
SHALL NOT interpolate display names. Responses SHALL admit only nonempty UTF-8 text of
at most 120 characters without native/legacy calls, structured content, JSON object/array
proposals or fences. Ordinary failures SHALL use fixed local text without retry/tools;
budget exhaustion and cancellation SHALL propagate. Raw candidate streams SHALL remain
hidden even with inherited final tags. Generated replies SHALL be labeled/literal data
before existing request/C10/SSE publication; this SHALL NOT certify semantic truth.

#### Scenario: Hostile name, message or response
- **WHEN** a name/message spoofs roles, a model returns calls/invalid content, or reply data
  contains markup or a short false completion claim
- **THEN** names cannot enter replies/model payloads, message roles remain fixed, invalid
  responses use local fallback, and admitted prose cannot grant business/tool authority

#### Scenario: Deadline, cancellation or final-publication failure
- **WHEN** the budget expires, generation is cancelled, or ownership/frame admission fails
- **THEN** no successful fallback/publication bypasses that failure, and real acceptance,
  optional reranking, F2-09 and C10 remain open or deferred as recorded

### Requirement: Non-knowledge composition preserves structured action evidence
Multiple non-knowledge results in non-chitchat aggregation SHALL be composed without a
model call or new execution
side effect. Status SHALL derive from structured stage/approval/Saga evidence, never
free text or success alone. All failed/pending/compensation/unresolved results SHALL
remain visible; missing/conflicting evidence SHALL remain unverified. Malformed/oversized
composition SHALL fail before answer binding/publication. Action prose/identifiers SHALL
be quoted and escaped display data. Existing single-result, knowledge citation, analysis
facts, request binding, C10 ownership and SSE frame checks SHALL remain authoritative.

#### Scenario: Pending approval and hostile tool prose
- **WHEN** a successful pending-approval result or tool text claims all operations completed
- **THEN** the structured status remains pending/unverified as applicable, prose cannot
  become a trusted status or new operation, and no summary model or draft tokens are produced

#### Scenario: Failed or ambiguous group and invalid evidence
- **WHEN** multiple results fail, Saga compensation is unresolved, or status fields are invalid
- **THEN** each valid outcome remains distinguishable, unknown effects are not called reversed,
  malformed composition cannot publish success, and real acceptance/C10 remain open

### Requirement: Planner and tool proposals preserve request authority
Covered Planner and tool-selection calls SHALL separate code-owned policy and validated
effective templates from bounded human JSON current request/history/task/catalog data.
They SHALL reject native calls, malformed or ambiguous proposals and unknown authority
fields without executable fallback. Action task descriptions SHALL be literal current
request excerpts, checked again before dispatch; replanning SHALL remain knowledge-only.
Tool selection SHALL validate the complete offered-tool/parameter batch before approval
or dispatch, without generated default recipients or business IDs. Raw planning candidate
streams SHALL NOT become public answer tokens, including with inherited final-answer tags. Existing current
identity, RBAC, approval, idempotency and Saga SHALL remain authoritative.

#### Scenario: Hostile history or model proposal attempts action escalation
- **WHEN** history/tool descriptions contain role spoofing, or a proposed action is not
  a literal request excerpt, supplies authority fields or includes an invalid batch member
- **THEN** data cannot change message roles or server authority and rejected proposals
  cannot reach approval/tool dispatch or keyword-based default actions

#### Scenario: Synthetic mechanical checks pass
- **WHEN** the covered source passes offline role/shape/batch/dispatch regressions
- **THEN** semantic correctness and real model/tool/runtime/full RAG/privacy remain
  unaccepted, C17 is unchanged, F2-09 sources remain pending and C10 stays open

### Requirement: Agent context belongs to one dispatched task
Agents SHALL NOT cache request-bearing instances across dispatches. Execution
context SHALL carry the current authenticated identity, conversation and request
ID without credentials. Send state SHALL contain independent identity/task/history copies.

#### Scenario: Overlapping requests from the same user
- **WHEN** two requests use different conversations or refreshed identity attributes
- **THEN** each task sees only its own context and cannot mutate another task's history

### Requirement: History contains request-bound answers
History SHALL use the invocation checkpointer, validate answer/request identity and
current user/conversation/role/department, and deduplicate by request ID. New entries
SHALL clear inherited answer/replan/error fields. Legacy unbound snapshots SHALL be
skipped without modification. History loading SHALL be bounded and fail to empty.

#### Scenario: Repeated questions and stale answers
- **WHEN** distinct completed requests repeat a question or an unfinished snapshot
  inherits an earlier answer
- **THEN** repeated completed turns remain distinct and the mismatched answer is excluded

### Requirement: Unsupported dependencies reject before fan-out
Any declared dependency or malformed dependency field SHALL reject the entire plan
before agents, tools or approvals execute. Parsing/deduplication SHALL NOT silently
discard dependencies. Rejection SHALL return a fixed terminal explanation with no
replan. Independent tasks SHALL retain fan-out behavior.

#### Scenario: Dependent action after a lookup
- **WHEN** a plan declares that a write needs a lookup result
- **THEN** no subtask runs and the user is asked to submit ordered steps separately

### Requirement: Offline delivery does not close runtime acceptance
C08 SHALL remain open until isolated real LangGraph/API/SSE/JWT/checkpoint acceptance.
Same-session concurrency consistency and general DAG scheduling are outside this increment.

#### Scenario: Offline regressions pass
- **WHEN** C08 is committed locally
- **THEN** live acceptance remains BLOCKED and C08 push and C09 await confirmation


### Requirement: Execution resources have request-owned admission budgets
Graph requests SHALL share a thread-safe budget across nodes and replans: four raw tasks
per plan, twelve dispatches, two active executors, sixteen logical model calls, 64 KiB
serialized messages per call, 256 KiB cumulative messages and 1024 output tokens per call.
Input SHALL be limited to 16 KiB UTF-8. Only the newest five authorized history turns SHALL
enter model context, with 2000 user and 800 assistant UTF-8 bytes per turn and visible
truncation markers. A 120-second monotonic admission deadline SHALL reject new work and
success after expiry; it SHALL NOT be represented as forced cancellation of in-flight I/O.
Budget exhaustion SHALL bypass fallback, fail the request with a fixed code and prevent
successful checkpoint publication. Scope exit SHALL close inherited budget references.

#### Scenario: Excessive model plan or prompt
- **WHEN** raw task count, prompt bytes, cumulative calls or admission time exceed the budget
- **THEN** the offending operation is refused before dispatch/provider execution, without
  silently trimming business tasks or converting the refusal into rule-based tool execution

#### Scenario: Parallel tasks and subsequent requests
- **WHEN** tasks overlap or a graph replans while another independent request starts
- **THEN** the first request shares atomic reservations and at most two executor slots,
  while the second receives fresh counters; cancellation releases slots and closes scope

#### Scenario: Offline execution-budget tests pass
- **WHEN** execution resource regressions pass without real providers or deployed processes
- **THEN** runtime/full RAG remain BLOCKED and C10/F2-03 runtime acceptance stay open;
  SSE implementation requires its own authorization and evidence rather than inheriting
  completion from the execution slice (subsequently authorized below)


### Requirement: SSE buffering and terminal delivery are bounded
SSE streams SHALL admit at most 64 queued data frames and 256 KiB encoded UTF-8 data;
each frame and the independent terminal slot SHALL be at most 64 KiB. Queue admission
and actual ASGI sends SHALL have five-second cooperative bounds, and the response SHALL
have a 180-second lifetime. Successful streams SHALL drain accepted data before final;
failure/cancel SHALL invalidate queued partial data and publish at most one terminal
without blocking on data capacity. Disconnection SHALL close admissions and cancel/join
its lazily started producer with bounded cleanup. Final frame validation SHALL precede
checkpoint publication. A post-commit delivery failure SHALL NOT rewrite completed state.

#### Scenario: Slow consumer fills the data buffer
- **WHEN** the item or byte capacity remains exhausted beyond the admission wait
- **THEN** the producer fails with a fixed backpressure error, no final success is published,
  and terminal/cleanup completion never depends on a free data slot

#### Scenario: Oversized final or cancellation at full capacity
- **WHEN** a final frame exceeds the limit or an active full stream is cancelled
- **THEN** the oversized final cannot be published, cancellation can terminate without a
  queue sentinel, and context/lease cleanup is attempted within explicit time bounds

#### Scenario: Client disappears or cannot accept a send
- **WHEN** ASGI reports disconnect, send stalls, or the stream lifetime expires
- **THEN** admissions close and producer cleanup is observed, without promising terminal
  receipt or rollback of already committed effects; real runtime and C10 remain unaccepted
