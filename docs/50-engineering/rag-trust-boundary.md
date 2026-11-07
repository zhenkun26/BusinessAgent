# Read-only RAG production trust boundary (F2-06)

Subsequent state (2026-10-22): [factory/status](reranker-selection.md) was completed
in local `fd5511c`; the separately authorized [score admission](score-admission.md) now
rejects invalid numeric data while preserving finite behavior and C17. Deferred/unchanged
statements below describe their dated increment, not a new current backlog. Real model/
semantic/runtime/full RAG/privacy remain BLOCKED; F2-09 pending, C10 OPEN.

## Plan recorded before implementation — 2026-10-21

Parent: local `8e30338`. This increment hardens the knowledge-answer path, including its
effective prompt version, untrusted inputs, model response and downstream publication.
Use only synthetic data and recording doubles; no real model/service, new dependency,
migration, deletion, push/upload, remote CI, main-spec sync or archive. C17 corpus,
evaluator and 115/7 plus 2/4 denominators stay byte-identical. Real runtime/full RAG and
privacy acceptance remain BLOCKED; F2-09 rights pending, C10 OPEN.

### Scope and sequence

1. Add a code-owned, versioned, read-only RAG policy independent of editable default or
   database prompts. Resolve the existing request-pinned/A-B prompt through `get_prompt`,
   validate its allowed placeholder contract and render only fixed data-reference labels
   into that trusted task instruction. Malformed active versions fail closed, without
   database writes, silently replacing the selected version or changing registry routing.
2. Send one system instruction and one JSON human-data envelope. Query, document title/
   body and prior user/assistant text remain data; source identities remain server-side.
   History never becomes system or tool messages. Retain source order and current
   retrieval ACL/publication filtering.
   Bind selected prompt version/hash and boundary version as content-free call metadata.
   Enforce the existing 64 KiB prompt budget before constructing/calling the model.
3. Knowledge generation has no bound tools. Reject tool/function-call payloads, non-text,
   empty/oversized output, missing/malformed/out-of-range citations before returning an
   answer. A single fixed unsupported-context response may omit citations. Citations
   establish membership only, never semantic support. Apply the same data boundary to
   optional coverage self-evaluation; it remains a heuristic, not factual validation.
4. Tag raw RAG model events as candidates and suppress those events from public SSE even
   if an inherited final-answer tag is present. Publish validated text only through the
   existing final-state/lease-owned publication path. Progress/cancellation/backpressure
   contracts remain. Knowledge answers therefore lose provisional per-token display.
5. Preserve validated knowledge text through aggregation: mixed knowledge results use
   deterministic composition, with local citations mapped to the deduplicated final
   source list. Do not let a second model rewrite a guarded knowledge answer. Revalidate
   successful knowledge citation shape at this downstream boundary, including retained
   results; legacy missing/invalid citations fail rather than obtaining false safety credit.
6. Add default/active/A-B/invalid-prompt, data-role, hostile title/history, tool-payload,
   citation, self-evaluation, aggregation/remapping and raw-stream counterexamples using
   actual code with doubles. Retain deliberate semantic false positives in the earlier
   eight-case controls; do not hardcode attack phrases into production or tune C17.
   Run full current offline verification, review sources/provenance, update documentation
   and active OpenSpec, commit locally, bind the final candidate and stop for confirmation.

### Offline acceptance

| Boundary | Required result |
| --- | --- |
| Default and activated registry versions | Same fixed system policy; selected version/hash retained; unsupported template fields rejected before model work |
| Document/query/history role spoofing | Original strings survive only in JSON data; cannot create messages, template fields, tools or authority |
| Model tool requests / malformed citations | Fixed rejection; no tool invocation, provisional SSE answer or accepted answer |
| Valid source membership | Text and source identities/order preserved; no semantic correctness claim |
| Downstream composition | No model rewrite of knowledge; valid citation indices refer to the actual final deduplicated source order |
| Offline entry | Full tests and eight checks PASS without skip/xfail/deselection or weakened security assertions; strict CLI separately BLOCKED if unavailable |
| Delivery | Local reviewed commit/receipt only; real model resistance, runtime/full RAG/privacy remain BLOCKED, F2-09 pending, C10 OPEN |

### Explicit limits and compatibility

Role separation/JSON and a fixed policy influence model behavior; they are not hard
semantic isolation. A fabricated or instruction-following answer with valid citation
syntax can still pass. Independent source-grounded semantic and real-model adversarial
review remain required. No existing self-score becomes a quality or security guarantee.

This slice does not redesign planner routing, execution-tool selection or chitchat/analysis
prompts. Knowledge model output is not an executable instruction; current execution-tool
RBAC, current identity/approval, idempotency and Saga gates remain unchanged. Other agent
prompt boundaries require separately scoped follow-ups; this is not project-wide injection
resistance. F2-05 still blocks private data and unaccepted outbound processing.

No prompt table migration or bulk activation is performed. Existing active knowledge
templates with the documented placeholders continue through the boundary; malformed
templates require an administrator's separately authorized correction. Old history stays
untrusted data; retained successful knowledge answers without valid citations may be
rejected on resume. The API shape remains unchanged. SSE emits progress and the accepted
final answer, rather than exposing a RAG draft that could later fail validation.

## Implementation and offline evidence — 2026-10-21

`app/security/rag_boundary.py` owns `rag-readonly-v1`, selected-template validation,
the JSON envelope and mechanical output/composition checks. Generation passes actual
SystemMessage/HumanMessage objects directly to the existing budgeted model; untrusted
braces are never formatted as template instructions. Selected default/active/A-B versions
retain their version and template SHA-256; the registry/defaults and activation behavior
are unchanged. Invalid selected versions fail before model invocation without fallback.

Context sent to the model contains only server citation index, title and body. Document/
chunk IDs stay in the server-side source map, not provider data or call metadata. History
accepts user/assistant string pairs without role promotion. The combined policy/task/data
uses the existing 64 KiB prompt limit. The coverage evaluator uses its own fixed read-only
scoring policy, separate JSON question/answer and exact integer parsing; its score is not
factual correctness. No bound tool is supplied; structured/malformed call requests and
non-text/empty/oversized or invalid-citation answers are rejected with fixed failures.

Only the exact fixed unsupported-context answer can omit citations. Code-owned confidence
rejection uses that same response. Other successful retained answers need valid citation
membership even on resume. Multi-result knowledge composition uses document/chunk identity
to share the final source order and renumbers references deterministically; it preserves
analysis values and never invokes an aggregation model for knowledge-containing results.
Raw RAG candidate/evaluation events are blocked from SSE even with an inherited final
tag. Progress and the existing final-state publication/backpressure/cancellation path stay.

- **PASS:** **53 new collected cases**, including selected active/default/A-B templates,
  role/brace/history spoofing, budgets, raw and malformed calls, citation failures,
  explicit semantic false positives, actual generation/evaluation, source remapping,
  retained invalid answers and mixed-tag stream suppression. Recording doubles only.
- **PASS:** full current entry: **1355 tests + 484 subtests**, zero skips/xfails/
  deselections/guard denials; 45 existing dependency warnings, Python 3.13.15/macOS arm64,
  coverage 77.26%. All eight checks PASS; Node page 69, credentials 14, seven assets,
  334 reviewed inputs and 440 pending provenance records.
- **PASS:** original C17 offline entry: 29 tests; frozen corpus/manifest/source hashes
  and 115/7 plus 2/4 denominators retained. Local source/diff, 406 document links,
  YAML and manual OpenSpec structure (23 delta files, 126 requirements, 202 scenarios)
  reviewed; manual structure is not strict CLI validation.
- **PASS:** original eight authored controls retain their exact outcomes and denominator;
  their evidence hashes now include the new production boundary and downstream source.
  Unsafe authored text with valid citations still passes the mechanical production guard
  in a limitation test; no model was induced to produce it and no robustness rate is claimed.
- **PASS:** C17 data/documents/manifest/evaluator, default/active registry source, planner,
  execution tools/authority, historical C24, dependencies, CI/Docker and older presentation
  assets remain unchanged. Five existing test modules adapt their data-role or source/
  fixed-refusal fixtures; original intent/token/analysis/privacy/control assertions remain.
- **BLOCKED:** strict OpenSpec CLI (unavailable), real model/semantic/privacy/runtime/full
  RAG, prior runtime matrices and current remote CI. Other agent prompt boundaries still
  require separate scope. F2-06 remains OPEN, F2-09 pending; C10 OPEN.

Precommit evidence: `enterprise-agent/eval/results/offline/f206-boundary-final-review-20261021.json`;
full receipt/log/coverage:
`enterprise-agent/eval/results/offline-pytest-ed2711e649ec4af58232a24930df106f/`.
Precommit binding is BLOCKED while dirty; final local commit identity and clean-candidate
receipt are retained under ignored `eval/results/offline/`. Local CI-mode success remains
offline-only with overall BLOCKED and release/UAT flags false. Review/commit locally,
then wait; no push/upload, model/service execution, deployment, release or archive.

## Subsequently authorized Planner/tool increment — 2026-10-22

The historical read-only slice above is local `8edaf00`. The separately authorized
[Planner/tool proposal boundary](planner-tool-trust-boundary.md) now covers selected
Planner/tool templates, JSON roles, current-request action excerpts and complete tool
batch admission without keyword-created defaults. It does not turn this RAG evidence
into semantic/model/runtime/privacy acceptance; F2-06 remains OPEN and C10 stays OPEN.

## Subsequently authorized non-knowledge composition — 2026-10-22

After local `c0ca3b5`, the separate [result facts/publication increment](nonknowledge-result-boundary.md)
replaces multi-result non-knowledge model rewriting with structured statuses and literal
quoted data. Existing single/knowledge behavior and C17 remain unchanged. Chitchat and
optional reranking are deferred; real semantic/tool/privacy/runtime/full RAG remain
BLOCKED, F2-09 pending and C10 OPEN.

## Subsequently authorized chitchat fallback — 2026-10-22

After local `d5e028c`, the separate [chitchat boundary](chitchat-trust-boundary.md) adds
fixed policy/message JSON, display-name omission, strict bounded responses/fallback and
hidden/literal candidate publication. The dated evidence above remains historical.
Optional reranking stays deferred; C17/authority unchanged, real model/privacy/runtime/
full RAG BLOCKED, F2-09 pending and C10 OPEN.

## Optional LLM rerank follow-up — 2026-10-22

The separately confirmed [optional score/event boundary](llm-rerank-trust-boundary.md)
now covers fixed policy/effective template roles, strict scores, whole-batch coarse fallback
and hidden score candidates. This does not replace the historical evidence above or
validate semantic relevance/model resistance. Cohere/BGE deferred; actual runtime/full
RAG/privacy BLOCKED, F2-09 pending and C10 OPEN.

## Optional Cohere/BGE result follow-up — 2026-10-22

The separately confirmed [result/numerical boundary](optional-rerank-result-boundary.md)
adds complete finite score/vector admission, stable sigmoid/ties, original-source copies
and whole-batch failure. Historical evidence above remains scoped to its earlier revision.
Factory/stage follow-up is deferred; real SDK/model/semantic/runtime/full RAG/privacy stay
BLOCKED, F2-09 pending and C10 OPEN. No integration or source-truth claim follows from scores.
