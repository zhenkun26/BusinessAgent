# Optional Cohere/BGE result admission and numerical safety

Subsequent state (2026-10-22): [factory/status](reranker-selection.md) was completed
in local `fd5511c`; the separately authorized [score admission](score-admission.md) now
rejects invalid numeric data while preserving finite behavior and C17. Deferred/unchanged
statements below describe their dated increment, not a new current backlog. Real model/
semantic/runtime/full RAG/privacy remain BLOCKED; F2-09 pending, C10 OPEN.

## Authorized plan — 2026-10-22, before implementation

Baseline: local `22492ab`. F2-06 stays OPEN. Scope: result/input admission and cooperative
interruption guards inside the existing Cohere/BGE rerank methods. Factory selection,
initialization fallback and stage-label correction are deferred. The selected Bailian
profile, optional LLM boundary, graph/publication and C17 remain unchanged. Synthetic
providers and existing NumPy only; no SDK/ML install, model download, real model/service,
new dependency, migration, push/upload, remote CI, main-spec sync or archive.

1. Validate positive non-boolean integer `top_n`, list candidates, and nonempty UTF-8
   query/candidate text before backend work. Empty candidate lists keep the no-call empty
   result. Preserve Cohere full text and BGE's existing first-1000-character input prefix;
   do not change content in returned sources. No new billing or hard I/O budget is claimed.
2. Admit Cohere list rows with explicit index/relevance_score fields (dictionary or
   attribute rows). Require exactly `min(top_n, candidate_count)` rows, unique integer
   indices in range, and finite real scores in [0, 1]. Reject booleans, strings, missing
   fields and invalid rows instead of skipping/coercing them or using coarse scores.
   Sort by score descending with original input position as the stable tie breaker.
3. Admit BGE one-dimensional list/tuple/NumPy score vectors with exactly one finite real
   scalar per candidate, including normal NumPy numeric scalars. Reject booleans, numeric
   strings, structured/non-scalar values, NaN/Infinity and count/shape mismatch. Preserve
   the existing logits-to-sigmoid contract with an overflow-safe formula; extreme finite
   values may saturate safely but non-finite values are never clamped into valid scores.
4. Return only copies of original candidates with new scores and independent ACL lists.
   Any ordinary validation/provider failure rejects the entire batch with one fixed error;
   the existing non-remote retriever owns coarse fallback/stage `vector`, including its
   existing policy tiebreak. Do not return partial results, retry or select another backend.
   Check the existing request budget before/after backend work and propagate budget/cancel.
5. Test actual adapter/retriever source using synthetic SDK/predict doubles and existing
   NumPy: valid arrays/rows, input/shape/index/count/value failures, extreme numerics, stable
   ties, original full content/source/ACL copies, complete fallback and interruption guards.
   Retain all earlier authority assertions. Full current offline entry and unchanged C17
   contract checks must pass without skips, xfails, deselections or weakened gates.
6. Update only affected source/provenance records, docs/status and existing OpenSpec
   artifacts. Review source/diff, frozen scopes, links, YAML/manual OpenSpec and modes;
   make one local commit, retain clean-candidate offline evidence and stop for confirmation.

## Acceptance, compatibility and explicit limits

Successful Cohere results are complete, uniquely bound to offered candidates and use one
score scale. Successful BGE results preserve the existing numerical meaning and stable
input ties. Input candidates remain unchanged; original IDs, full text and permission
metadata never come from returned provider prose. Invalid batches fail instead of being
partially salvaged. Valid full-text/prefix payloads are preserved, not anonymized.

The reviewed offline runtime lacks Cohere/ML packages; synthetic doubles establish the
local contract only. The existing SDK method and constructor stay unchanged, and no real
compatibility claim is made. BGE logits versus preactivated output must be checked against
an exact SDK/model revision later; this increment does not recalibrate it or alter C17
thresholds/denominators. Valid high scores can still be semantically wrong. Model resistance,
actual latency/memory, hard cancellation, provider timeout/retry/retention, model provenance
and SDK/event/runtime/full RAG/privacy acceptance stay BLOCKED. Factory fallback labeling
remains deferred, F2-09 rights pending and C10 OPEN. C21 audit/metrics are retained.
Strict OpenSpec CLI remains unavailable/BLOCKED, distinct from manual structure checks.
No automatic next item or external action after the reviewed local commit/final receipt.

## Verification record

Implemented in `app/security/rerank_results.py` and the existing BGE/Cohere `rerank`
methods. Input query/full candidate text must be nonempty UTF-8; candidates are a list,
top_n is a positive Python integer, and empty candidates remain a no-call empty result.
Cohere keeps its current SDK construction/method and full-text payload. BGE keeps the
1000-character input prefix. Source results preserve full original content and independent
ACL lists. Malformed data is not coerced, skipped or repaired using coarse scores.

Cohere admits complete list results with dict/attribute rows, unique in-range Python
integer indices and finite real [0, 1] scores. BGE admits 1-D list/tuple/NumPy vectors
with exact cardinality and finite float-representable real scalars, including ordinary
NumPy numeric scalars. Booleans, numeric strings, arrays-as-scalars, NaN/Infinity and
wrong shapes/counts fail the whole batch. Stable sigmoid handles finite extremes;
non-finite values are rejected. Ties use original candidate position.

Each method checks the existing execution budget before/after backend work and returns
only original-source copies. Ordinary exceptions become `OPTIONAL_RERANK_RESULT_REJECTED`
without raw provider content or new diagnostics; no retry/backend switch or partial output.
The existing non-remote retriever owns whole-batch coarse fallback/stage `vector` and
policy tiebreak. Budget/cancel exceptions propagate. These are cooperative checks, not
new provider billing counters or hard I/O termination.

| Evidence | Result and limits |
|---|---|
| New actual-source synthetic tests | **108 tests + 10 subtests PASS**: dict/attribute rows, NumPy scalar/vector shapes, indices/counts/non-finite values, stable ties/extreme logits, preserved source copies/payloads, provider errors and interruption/fallback paths |
| Full current pytest | **1715 tests + 507 subtests PASS**, zero skips/xfails/deselections/guard denials; 45 existing warnings; 79.45% local line coverage |
| Existing C07 fixture | Added the existing NumPy ndarray type to its isolated module stub; all authority/source/ACL assertions are unchanged |
| Unified offline entry | Eight checks PASS; 344 reviewed inputs/445 pending sources, Node 69/14, seven assets and 98 production pins; dirty binding BLOCKED |
| C17 | 29 contract tests PASS; corpus/evaluator/denominators and the eight authored RAG controls unchanged |
| Scope review | Bailian/LLM/passthrough/factory and BGE/Cohere constructors are AST-identical to the parent; graph/retriever/visibility/authorization/C10/final SSE unchanged |
| Formal acceptance | Real SDK/model/semantic/runtime/full RAG/privacy BLOCKED; factory/stage follow-up deferred, F2-09 pending and C10 OPEN |

No SDK or ML dependency was installed and no model was downloaded. Only synthetic SDK/
predict doubles and existing NumPy were used. A valid high score can still select a
semantically wrong or poisoned candidate; structural/finite checks cannot establish
relevance truth or model resistance. The existing SDK method is not certified compatible;
real BGE output semantics still require a pinned SDK/model check. C21 audit/metrics and
all live matrices remain unchanged. Manual OpenSpec review does not replace the absent
strict CLI, which remains BLOCKED.

Diagnostic log: `eval/results/f206-optional-rerank-diagnostic-20261022.log`;
full evidence: `eval/results/offline-pytest-62108944ea274b418425a269b6facc25/`.
C17 log: `eval/results/f206-optional-rerank-c17-20261022.log`.
Precommit unified receipt: `eval/results/offline/f206-optional-rerank-precommit-20261022.json`.
Dirty precommit binding stays BLOCKED. After the reviewed local commit, retain
`eval/results/offline/f206-optional-rerank-final-20261022.json` for clean/stable candidate
binding; local CI-mode success remains offline-only, overall BLOCKED, release/UAT false.
Stop afterward; no push/upload or automatic next increment.


Subsequent authorization (2026-10-22): the separately planned
[factory selection/status increment](reranker-selection.md) now handles the deferred
factory/stage slice after `cf43c96`. Historical evidence above describes this result/
numerical increment only; its five scorer method bodies remain unchanged by that follow-up.
Real SDK/model/semantic/runtime/full RAG/privacy remain BLOCKED; F2-09 pending, C10 OPEN.
