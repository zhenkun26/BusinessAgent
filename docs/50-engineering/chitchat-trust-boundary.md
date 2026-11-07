# Chitchat fallback trust boundary

## Authorized plan — 2026-10-22, before implementation

Baseline: local `d5e028c`. F2-06 remains OPEN. Scope: the aggregator's chitchat fallback,
its local canned replies and candidate stream publication. Only synthetic data/doubles;
no real model/service, dependency, C17 input/evaluator/denominator change, migration,
push/upload, main-spec sync or archive. Optional reranking stays deferred.

1. Replace message/name interpolation with a fixed code-owned read-only chitchat System
   policy and a separate human JSON message. Do not send username/history/tool catalogs,
   identity or credentials to the fallback model. Remove display-name interpolation from
   canned replies too; retain the existing helper's username argument for caller compatibility.
   This deliberately gives up name personalization without changing authentication identity.
2. Keep the existing 120-character model-response ceiling. Admit only nonempty bounded
   UTF-8 text; reject native/invalid/legacy tool/function calls, structured/opaque content,
   JSON object/array proposals and fenced replies. Never stringify objects or salvage
   malformed output. Ordinary provider/response failures use one fixed local fallback,
   with no retries, tools or other model. Budget exhaustion and cancellation must propagate.
3. Tag the call as `chitchat_candidate`, retain only fixed policy/boundary identity metadata,
   and hide candidate chunks even with inherited final-answer tags. Validated generated
   text is labeled chitchat, not business-state evidence, and quoted as literal code so
   GFM autolinks, images, HTML and CR/fence payloads cannot become active markup or status.
   Retain existing answer-request binding, C10 ownership and final SSE admission.
4. Test actual source with synthetic providers/stores: role spoofing, hostile/opaque names,
   malformed/native responses, exact size boundaries, provider failure, budget/cancellation,
   deterministic canned replies, no new execution, inherited stream tags and final binding.
   Check actual bundled Markdown parsing, full current offline inventory and frozen C17.
   Review scoped provenance/docs/OpenSpec, commit locally, bind the clean candidate, stop.

## Acceptance and compatibility

Canned branches remain local and their Chinese persona/capability text stays intact except
for removal of the untrusted display name. Generated replies acquire a fixed chitchat label
and literal quote. No registry/default/version database changes or new public response
fields are introduced: this fallback policy was code-owned before this increment too.
Input/model/context/output budgets remain enforced; they are not swallowed into a
successful fallback. Display-name omission minimizes payloads but does not anonymize the
message. Literal rendering is not DLP, semantic verification or proof of model obedience.

A plain, short false business claim can still satisfy the mechanical response contract;
the fixed label keeps it from becoming authoritative execution evidence. Test that limit
explicitly rather than claiming a business-truth detector. Real model resistance/semantics,
browser/API/runtime/full RAG/privacy remain BLOCKED; F2-09 rights pending, C10 OPEN.
Strict OpenSpec CLI remains unavailable/BLOCKED, separate from manual structure checks.
No automatic next increment after the reviewed local commit and final candidate receipt.

## Implementation and evidence

Implemented in `app/security/chitchat_boundary.py`, the aggregator's two chitchat helpers
and the graph's private candidate tag filter. The public reply helper keeps its username
argument but does not inspect/interpolate it. No registry/default/version records change.
Non-chitchat aggregation and answer binding are AST-equivalent to the parent candidate;
knowledge/analysis/tool/approval/idempotency/Saga/C10/SSE admission source stays unchanged.

| Case | Mechanical behavior |
|---|---|
| Local persona branch | Fixed Chinese reply without display-name interpolation; no model |
| Model attempt | Fixed System policy plus human JSON containing only `message`; one existing lite model attempt |
| Native/legacy calls, non-text, invalid UTF-8, empty/overlong/JSON/fenced reply | Fixed local fallback, no retry/tool action or content in diagnostic logs |
| Budget exhausted before/after factory/call | Propagated failure, no successful fallback; cancellation also propagates |
| Valid text | Existing 120-character body limit; fixed chitchat label and literal quoted code; never an execution receipt |
| Raw stream with candidate/final tags | Candidate chunk suppressed; existing request-bound final publication remains |

The input remains within existing 16 KiB UTF-8 and 64 KiB prompt budgets, including JSON
expansion; aggregate call/output/deadline guards remain independent. No new public fields
or dependencies. Confidence retains the existing chitchat heuristic and is not a truth
score. Removing display names minimizes one field, not the private content of the message.

- **PASS:** 57 new actual-source synthetic tests; full **1522 tests + 494 subtests**,
  zero skips/xfails/deselections/guard denials; 45 existing dependency warnings, 78.86%
  local line coverage. The obsolete response-length log expression is removed, reducing
  automatic diagnostic subtests by one (80 to 79 expressions); no test assertion is removed.
- **PASS:** eight current offline checks, Node 69/14, seven assets, 98 production pins;
  340 reviewed inputs and 443 pending-source records. C17 29 contract tests PASS; original
  corpus/evaluator/denominators and eight authored RAG controls unchanged.
- **PASS:** five actual bundled Marked parser cases (markup, HTML, CR, autolinks and fences)
  plus two unsafe controls; no active links/images/scripts/headings and hostile text stays
  inside literal quotes. This is parser evidence, not real browser/assistive-tech acceptance.
- **Explicit limitation:** a short false statement about sending mail/passing approval
  satisfies the mechanical text contract and remains quoted under the chitchat disclaimer.
  This is not a semantic classifier or measured resistance result. No tool/approval/runtime
  effect or real provider behavior is inferred. Optional reranking stays deferred.
- **BLOCKED:** real model/semantic/browser/API/runtime/full RAG/privacy and strict OpenSpec
  CLI; F2-09 source/rights review pending, C10 OPEN. Existing C21 audit/metrics retained.

Precommit receipt: `enterprise-agent/eval/results/offline/f206-chitchat-precommit-20261022.json`;
full log/coverage: `enterprise-agent/eval/results/offline-pytest-74927649f61a4804af9a9fbc1a2bc795/`.
Parser receipt: `enterprise-agent/eval/results/f206-chitchat-parser-review-20261022.json`.
Precommit binding is BLOCKED while dirty. The reviewed local commit will be bound by
`eval/results/offline/f206-chitchat-final-20261022.json`; local CI-mode success remains
scoped offline, overall BLOCKED and release/UAT false. Stop afterward, no external action.

## Optional LLM rerank follow-up — 2026-10-22

The separately confirmed [optional score/event boundary](llm-rerank-trust-boundary.md)
now covers fixed policy/effective template roles, strict scores, whole-batch coarse fallback
and hidden score candidates. This does not replace the historical evidence above or
validate semantic relevance/model resistance. Cohere/BGE deferred; actual runtime/full
RAG/privacy BLOCKED, F2-09 pending and C10 OPEN.
