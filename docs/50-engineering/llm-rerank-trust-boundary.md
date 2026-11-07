# Optional LLM rerank score and event trust boundary

Subsequent state (2026-10-22): [factory/status](reranker-selection.md) was completed
in local `fd5511c`; the separately authorized [score admission](score-admission.md) now
rejects invalid numeric data while preserving finite behavior and C17. Deferred/unchanged
statements below describe their dated increment, not a new current backlog. Real model/
semantic/runtime/full RAG/privacy remain BLOCKED; F2-09 pending, C10 OPEN.

## Authorized plan — 2026-10-22, before implementation

Baseline: local `5bbf68b`. F2-06 stays OPEN. Scope: only optional development
`LLMReranker` scoring and candidate events. The selected Bailian production profile,
Cohere/BGE implementations and factory-selection behavior remain unchanged. Synthetic
providers/stores only; no real model/service, dependency, migration, C17 corpus/evaluator/
denominator change, push/upload, remote CI, main-spec sync or archive.

1. Put a code-owned read-only scoring policy above both effective registry templates
   (default, active and A/B). Validate supported template slots and integer version IDs;
   interpolate fixed data references only. Send query and the existing first-1000-character
   candidate prefix as separate human JSON; omit identities, source IDs and tool catalogs.
   Keep selected version/hash metadata without prompt/business text and retain registry
   authority/request snapshots. Do not rewrite defaults or migrate prompt records.
2. Admit only UTF-8 text containing one ASCII integer 0–10 after surrounding whitespace.
   Reject native/invalid/legacy calls, structured/opaque/oversized content, numeric salvage,
   signs, fractions, explanations, JSON and fences. Never stringify unknown objects or
   execute proposed tools. Valid scores remain normalized by dividing by ten.
3. Return only scored copies of the original candidates, preserving source/ACL metadata,
   full content and stable ties. On any invalid score/template or ordinary provider error,
   abandon the whole scoring batch with a fixed error; the existing non-remote retriever
   falls back to original coarse results with stage `vector`. Never mix coarse and LLM
   scores, retry, switch models or return a partial rerank. Existing remote failure behavior
   remains closed. Budget exhaustion and cancellation propagate instead of falling back.
4. Add `rerank_candidate` metadata tags and suppress raw score events even with inherited
   `final_answer` tags. Preserve other eligible stream tokens and request/C10/final SSE
   publication. Use existing shared model-call/prompt/deadline limits; do not enlarge them.
5. Test actual source with synthetic models and stores: effective versions/data roles,
   hostile templates/query/chunks, score boundaries and native/opaque response rejection,
   complete-batch fallback/stage, source/ACL identity, budget/cancellation and inherited
   stream tags. Adapt only obsolete test doubles while preserving their authority assertions.
   Run the full reviewed eight-check offline entry and unchanged C17 contract tests;
   synchronize source/provenance inventories, docs and existing OpenSpec artifacts.
6. Review scope/diff, local links, YAML/manual OpenSpec structure and preserved file modes;
   commit locally, bind a clean/stable candidate with a retained offline receipt, and stop.

## Acceptance and compatibility

This deliberately rejects outputs formerly converted by collecting digits and replaces
per-candidate mixed-score fallback with whole-batch coarse fallback in the existing
retriever. Direct callers receive the fixed batch error. Empty candidates still return no
results without a model. Valid 0–10 scores, stable ties, full original content and ACL/source
metadata remain. The optional model factory and Cohere/BGE are not expanded or enabled.
The existing 16-call request budget can stop a large optional candidate set; this increment
does not promise every configured retrieval fan-out fits it or establish a hard I/O timeout.

A valid score is a relevance heuristic, not source truth, proof of model obedience or
permission. A poisoned chunk can still receive a syntactically valid high score. Record
that negative control explicitly. Real model/semantic/event-transport/runtime/full RAG/
privacy and unavailable strict OpenSpec CLI remain BLOCKED; F2-09 rights pending, C10 OPEN.
C21 audit/metrics and downstream authorization/visibility/publication remain authoritative.
No automatic next item after the reviewed local commit and final-candidate receipt.

## Verification record

Implemented in `app/security/rerank_boundary.py`, `LLMReranker`, the retriever's explicit
interruption branch and graph candidate filter. Fixed policy wraps both effective task
versions; supported slots become fixed references and human JSON contains only query/text.
The existing 1000-character candidate prefix is retained. No source IDs or identity fields
are sent. Score admission accepts only bounded UTF-8 text matching ASCII 0–10 after trim;
no numeric salvage or tool/structured/opaque output. Scores only reorder original copies,
including full content and separate ACL lists; ties are stable.

Ordinary failures raise one fixed batch error, not partial scores. The existing non-remote
retriever falls back to coarse data with `stage=vector`; its policy-scene tiebreak remains.
An explicit interruption branch prevents even an externally raised budget/cancel exception
from becoming coarse fallback at that boundary. Existing graph budgets and callback limits
remain; synchronous provider I/O still has cooperative, not hard-stop, cancellation semantics.
Bailian/BGE/Cohere/passthrough implementations and `get_reranker` are AST-identical to the
parent. Defaults/registry, source visibility/ACL rules, knowledge generation, approvals,
idempotency/Saga, C10 and final SSE admission remain unchanged.

| Evidence | Result and limits |
|---|---|
| Actual-source synthetic cases | **85 new tests + 3 subtests PASS**: default/active/A-B roles, strict scores/calls, exact input and shared 16-call admission, ties/source copies, second-candidate failure, actual retriever stage and inherited stream tags |
| Full current pytest | **1607 tests + 497 subtests PASS**, zero skips/xfails/deselections/guard denials; 45 existing warnings, 79.25% local line coverage |
| Existing C07 fixture | Adapted old chain mock to direct messages/config and valid templates/versions; every existing source/ACL assertion remains |
| Current offline entry | Eight checks PASS; Node 69/14, seven assets, 98 production pins; 342 reviewed inputs and 444 pending-source records |
| C17 | 29 contract tests PASS; corpus/evaluator/denominators and eight authored RAG controls unchanged |
| Semantic negative control | A synthetic poisoned chunk receives a valid `10` and remains selectable; format admission proves no relevance truth/model resistance |
| Review | Source/frozen-scope/AST/diff, local links, YAML/manual OpenSpec; strict CLI unavailable/BLOCKED |
| Overall acceptance | Real model/semantic/event transport/runtime/full RAG/privacy BLOCKED; Cohere/BGE deferred, F2-09 pending, C10 OPEN |

The first full diagnostic retained one expected source-inventory drift failure before the
new test and adapted C07 fixture were registered. No check was skipped or weakened; the
complete suite and eight checks passed after the scoped inventory update. Covered diagnostic
expressions remain 79; the three additional subtests exercise interruption types.

Retained diagnostic: `eval/results/f206-llm-rerank-diagnostic-20261022.log`.
Precommit receipt: `eval/results/offline/f206-llm-rerank-precommit-20261022.json`;
C17 log: `eval/results/f206-llm-rerank-c17-20261022.log`. Dirty precommit binding stays
BLOCKED. After the reviewed local commit, bind a clean/stable candidate to
`eval/results/offline/f206-llm-rerank-final-20261022.json`; local CI-mode success is offline
only, overall BLOCKED with release/UAT false. Stop afterward; no external action.

## Optional Cohere/BGE result follow-up — 2026-10-22

The separately confirmed [result/numerical boundary](optional-rerank-result-boundary.md)
adds complete finite score/vector admission, stable sigmoid/ties, original-source copies
and whole-batch failure. Historical evidence above remains scoped to its earlier revision.
Factory/stage follow-up is deferred; real SDK/model/semantic/runtime/full RAG/privacy stay
BLOCKED, F2-09 pending and C10 OPEN. No integration or source-truth claim follows from scores.
