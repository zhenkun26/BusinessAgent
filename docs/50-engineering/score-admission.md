# Coarse-score and confidence numerical admission

## Authorized plan — 2026-10-22, before implementation

Baseline: local `fd5511c`. Scope: F2-06 numeric type/finiteness admission before existing
score conversion, clipping, model use and confidence decisions. Synthetic values and
in-process store/model doubles only. No real model/service, new dependency, SDK/ML install,
download, migration, push/upload, remote CI, main-spec sync or archive. Real runtime/full
RAG/privacy remain BLOCKED; F2-09 source rights pending and C10 OPEN. Review, local commit,
final candidate receipt, then wait for confirmation.

The read-only review found that current min/max clipping turns NaN, positive infinity and
booleans into 1.0. Memory retrieval clips after float conversion; Milvus converts its score
without a finite check. Confidence combination/decision can therefore label an invalid
input high and skip the hint. This is a synthetic local counterexample, not evidence that
real Milvus emitted such values or that the selected Bailian profile was compromised.

1. Add one standard-library admission helper for real, float-representable finite numeric
   scalars; reject booleans, strings, null, opaque/structured/complex values and NaN/Infinity
   with fixed error text. Accept normal Python and existing NumPy real scalars. Never
   stringify rejected inputs or infer a valid score by coercing text/clamping non-finite data.
2. Validate authorized memory/Milvus raw scores before their existing float conversion,
   sorting/truncation or clipping. Preserve their distinct finite-score behavior: memory
   clips to [0,1], Milvus retains its finite COSINE score (including negative values).
   Do not change normalization, ordering/ties, top-k, ACL/publication filters or backend choice.
3. Guard visible coarse and returned rerank results in the retriever, plus knowledge-agent
   results before generation and final publication. Invalid batches are not partially
   salvaged by dropping rows or substituting zero. Existing controlled failure/fallback
   paths stay distinct from successful empty retrieval; valid fallback results remain
   available. Numeric admission errors propagate through the degradation selector instead
   of becoming a successful no-answer if a later path is empty; ordinary backend-failure
   fallback stays unchanged. Direct generation also refuses invalid scores before model calls.
4. Validate confidence retrieval/self-evaluation inputs and used weights/intermediate sums
   before existing arithmetic/clipping. Retain original accepted numeric operands, arithmetic
   order, 0.6 weight, scene thresholds, rejection/skip thresholds and optional self-score
   semantics. This is numeric admission, not probability calibration or factual validation.
5. Add actual-source synthetic counterexamples: first/non-first bad rows, raw scalar types,
   NaN/Infinity, NumPy scalars, ACL/visibility ordering, coarse/passthrough/rerank fallback,
   no generation or final invalid sources, unchanged finite arithmetic/clipping/decisions,
   failure/empty distinctions and cooperative budget/cancellation. Retain previous assertions.
   Run complete current eight-check verification and the guarded C17 offline entry; no
   skips, weakened gates or C17 corpus/evaluator/categories/denominator changes.
6. Synchronize affected source/provenance records, status/index documents and existing
   OpenSpec artifacts. Correct the stale current F2-09 source count and clarify historical
   deferred statements without rewriting their original evidence. Review links/YAML/manual
   spec structure, scope and file modes; strict OpenSpec CLI remains BLOCKED if unavailable.
7. Make one reviewed local Conventional Commit, retain clean/stable final-candidate offline
   evidence and stop. No following unit, environment acceptance or publication is authorized.

## Acceptance and compatibility

| Case | Required outcome |
| --- | --- |
| Invalid raw score/type in an authorized batch | Fixed rejection before conversion/clipping; no silent row omission or synthetic score |
| Valid finite memory/Milvus scores | Existing conversion, clip/raw COSINE, ordering and permission behavior retained |
| Invalid visible coarse scores | No reranker invocation; existing controlled degradation remains distinguishable from empty results |
| Invalid scoring response | Existing optional whole-batch coarse fallback / required remote failure, without invalid result publication |
| Invalid knowledge result, including non-first rows | No model generation or invalid final sources; fixed service failure, not a fabricated refusal |
| Invalid confidence input or non-finite intermediate | Fixed rejection instead of high confidence or skip-hint success |
| Valid finite confidence inputs | Same original arithmetic, decisions, weight and thresholds; confidence remains heuristic |
| C17 and evidence | Frozen metric definitions/categories/denominators, all expected cases retained; offline success never closes F2-06 or C10 |

No embedding validation redesign, model relevance tuning, threshold changes, confidence
calibration, semantic judge, automatic backend recovery or new public result fields are
included. Real SDK/model/semantic/latency/resource/browser/runtime/full RAG/privacy and
strict OpenSpec acceptance remain separate and BLOCKED; source rights remain pending.

## Implementation and verification

The stdlib helper `app/rag/score_admission.py` admits real float-representable finite
scalars (including ordinary NumPy scalars), rejects bool/text/null/structured/complex/
non-finite values with `RAG_SCORE_INVALID`, and never renders rejected input. Missing
source scores have the same fixed error. Interrupted numeric conversion propagates.
The result-batch guard checks all rows without mutation, omission or zero substitution.

Memory/Milvus adapters validate ACL-eligible raw scores before the original conversion,
sort/top-k and memory-only clipping. Retriever checks follow its current ACL/publication
filters, before reranking and after scoring/fallback. A coarse numeric failure invokes no
reranker. Optional bad scoring still falls back to a complete valid coarse batch; required
remote scoring failure remains fatal. A mutated invalid coarse batch cannot escape via
that fallback. No new backend selection, retry or recovery behavior is introduced.

The degradation selector validates authorized primary/fallback batches and propagates
numeric errors alongside access errors. This prevents an invalid batch from becoming a
successful empty result. Ordinary source outages may still use the existing keyword/PG
fallback, and valid empty results retain stage none. Route names and C17 accounting remain
unchanged; the selector's error handling is intentionally changed only for numeric admission.

Knowledge run checks every result before generation and again afterward, preventing
post-await mutations from publishing invalid sources. Direct generation also checks before
prompt/model work. Knowledge run's existing safe service failure remains the public result:
no invalid sources, no fabricated no-answer and no new API fields. Confidence validates
scores, used self-score/weight operands and the weighted intermediate before clipping.
The original accepted operands and arithmetic order are retained; the default .6 weight,
scene thresholds, rejection .2 and skip .9 remain unchanged. It is still a heuristic.

| Evidence | Outcome and limits |
| --- | --- |
| New actual-source synthetic cases | 100 tests + 25 subtests PASS: scalar types/NumPy, NaN/Infinity, batch/ACL/visibility, raw store and injected paths, valid clipping/order/threshold compatibility, no generation/invalid sources, controlled fallback and interruptions |
| Full local suite | 1883 tests + 535 subtests PASS, zero skips/xfails/deselections/guard denials; 45 existing warnings; Python 3.13.15/macOS arm64; 80.26% local line coverage |
| Current offline entry | All eight checks PASS, 347 reviewed inputs/447 pending source records; Node 69/14, seven assets and 98 production pins; dirty precommit binding BLOCKED |
| Guarded C17 entry | 29 existing contract cases PASS; corpus/evaluator/categories/denominators unchanged, no measured RAG quality |
| Compatibility and review | Exact legacy finite arithmetic and scene boundary cases PASS; all prior test files/assertions, scorer/factory/profile, prompts and C17 bytes unchanged; no dependency, schema, C10, audit/metrics or SSE change |
| Formal acceptance | Real SDK/model/semantic/runtime/full RAG/privacy/strict CLI BLOCKED; F2-09 rights pending, C10 OPEN, F2-06 stays OPEN |

The first diagnostic collected 1881 tests (before two final scalar/memory regressions)
and failed only because the newly covered test file was not registered in provenance.
Scoped registration fixed that failure; no tests were skipped or assertions weakened.
Existing 74 diagnostic-expression subtests remain unchanged. The current source manifest
registers only the five affected production files, new helper/test and provenance hashes;
historical C24, C17 inputs and eight synthetic-control pairs remain frozen.

Retained local evidence:
- Initial diagnostic: `eval/results/f206-score-diagnostic-20261022.log`.
- Precommit receipt: `eval/results/offline/f206-score-precommit-20261022.json`.
- C17: `eval/results/f206-score-c17-20261022.log`.
- Final clean-candidate receipt after reviewed local commit:
  `eval/results/offline/f206-score-final-20261022.json`.

Manual links/YAML/OpenSpec structure review is separate from the unavailable strict CLI.
Final receipt identifies the checked commit without a self-referential documentation
commit. Local CI-mode success is offline-only; overall BLOCKED and UAT/release flags false.
No live model/service, dependency install, migration, push/upload, remote CI, main-spec sync,
release or archive. Stop after the reviewed local commit/final receipt and wait.
