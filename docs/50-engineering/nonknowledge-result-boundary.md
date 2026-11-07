# Non-knowledge result facts and publication boundary

## Authorized plan — 2026-10-22, before implementation

Baseline: local `c0ca3b5`. F2-06 remains OPEN. This increment replaces model rewriting
of multiple non-knowledge results with bounded deterministic composition. Only synthetic
fixtures/doubles are allowed. No real model/service, new dependency, C17 input/evaluator/
denominator change, database migration, push/upload, main-spec sync or archive.

1. Treat execution/approval status as server-owned structured evidence. `success=true`
   alone cannot mean an operation completed: pending approval uses that flag too. Render
   direct-call, Saga and approval branches separately, retaining partial success, failure,
   pending, reported compensation and unresolved outcomes. Keep all failed results.
2. Treat action result prose and identifiers as display data. Quote/escape that content
   so embedded instructions, Markdown images/links, headings or HTML cannot become a
   trusted status banner or a new operation. Unknown/missing/conflicting status evidence
   stays explicitly unverified; malformed field types fail with a fixed boundary error.
   Do not stringify opaque objects, silently drop a bad member or truncate business text.
3. Remove the active model summary helper and its raw draft stream path. The historical
   `aggregator_aggregate` registry/default records remain, but are not selected by this
   path. No replacement model, tool, approval, compensation or retry is initiated.
   Final answers retain existing request binding, C10 ownership and SSE frame admission.
4. Preserve single-result behavior and knowledge citation/remapping. Analysis reports
   retain their deterministic text/numbers when composed with action results. Chitchat,
   optional reranking, parameter/intent semantics and actual provider effects are deferred.
5. Add actual-source synthetic counterexamples and positive cases: pending with success,
   mixed/all failure, compensation/manual/unknown states, malicious prose, missing/bad
   fields, older records, checkpoint dictionaries, zero model calls and final publication.
   Run the complete current offline entry without skips/weaker gates; review scoped
   hashes/provenance/docs/OpenSpec, commit locally, bind the clean candidate, then wait.

## Compatibility and evidence limits

The existing single-tool wrapper does not retain a complete structured distinction
between rejected/failed/unknown provider outcomes. A false success flag therefore means
"not confirmed successful; check actual effects", never proof that nothing happened.
No free-text parser will invent that missing evidence. Missing durable Saga terminal state
cannot establish completion of the group. Reported compensation covers only confirmed
steps, not an atomic rollback or reversal of delivered email.

Use existing task-count and text/frame budgets. Reject oversized or invalid composition
before answer request binding/publication; final SSE size/ownership checks remain separate.
No new public response fields or storage schemas are introduced. Confidence remains the
existing agent confidence heuristic and does not certify action completion.

Offline PASS requires each retained result to have an unambiguous data/status boundary,
no model or execution side effect during composition, intact analysis/knowledge contracts,
and final request/lease publication still enforced. It does not verify provider truth,
model resistance, real API/browser/runtime/full RAG or privacy. Those remain BLOCKED;
F2-09 sources pending, C10 OPEN. Strict OpenSpec CLI is unavailable/BLOCKED; manual
structure checks are separate. Stop after reviewed local commit/final receipt.

## Implementation and evidence

Implemented in `app/security/result_boundary.py` and `app/graph/aggregator.py`. The
historical summary prompt/default/version records are unchanged and no longer selected
by multi-result composition. Chitchat function source and AST are unchanged;
reranking, tool authorization/approval/idempotency/Saga, knowledge citation and C10/SSE
publication source remain unchanged. Mixed knowledge and single-result paths retain their
previous behavior; this increment does not normalize every action display in the system.

| Structured evidence | Display boundary |
|---|---|
| Direct call true/false | Reports call success, or unconfirmed success with possible failure/unknown effects; neither proves completion of other branches |
| Approval pending with IDs/tools and success | Awaiting approval/requester confirmation, explicitly not executed |
| Direct/Saga result plus approvals | Direct and approval branches remain separate; incomplete approval metadata stays unverified |
| Saga succeeded | Reports orchestration completion; individual effects remain subject to step records |
| Saga compensated | Reports compensation of confirmed successful steps, never success of the original operation |
| Manual/unresolved/conflicting/missing state | Explicitly unverified or requiring reconciliation; no inferred rollback or guessed completion |
| Invalid metadata/member or oversized composition | Fixed rejection before answer binding; no partial member omission or business-text truncation |

Action prose and identifiers use indented literal code inside blockquotes. This retains
text while disabling Markdown interpretation/autolinks. CR/CRLF are normalized before
line quoting. Analysis text/numbers stay intact. The existing four-task/64 KiB text
budgets and final SSE envelope admission remain distinct; no new public fields or limits.
Statuses describe the supplied result snapshot, not a fresh database/provider status query.

- **PASS:** 49 new collected cases; full **1465 tests + 495 subtests**, zero skips/xfails/
  deselections/guard denials; 45 existing dependency warnings, 78.28% local line coverage.
  Two auto-enumerated diagnostic subtests disappear with the two removed summary logging
  expressions (82 to 80 calls in the covered scope); no test assertion/gate was weakened.
  Existing knowledge/analysis no-model assertions now guard the actual model factory.
- **PASS:** eight current offline checks; Node 69/14, seven browser assets, 98 production
  pins, 338 reviewed source inputs and 442 pending-source records. C17 29 contract tests
  PASS; original C17 corpus/evaluator/denominators and separate eight RAG controls unchanged.
- **PASS:** five actual bundled Marked parser samples (Markdown, HTML, CR, autolinks,
  fences) keep hostile data inside literal quotes and create no active link/image/script/
  heading. Two unsafe controls prove the parser checks detect escaped-data failures.
  This is local parser evidence, not browser/accessibility acceptance.
- **Review history:** the first size counterexample was below budget and was retained as
  a positive case; clear over-budget inputs cover bytes and quote expansion. The parser
  exposed GFM autolinking despite punctuation escaping; literal code replaced that approach.
  A whitespace-only expansion fixture was corrected to contain actual text. Failed receipts
  remain local; none were skipped or relabeled as passing.
- **BLOCKED:** real model/tool semantics, API/browser/runtime/full RAG/privacy, strict
  OpenSpec CLI; F2-09 rights pending and C10 OPEN. No service/model/dependency installation.

Precommit receipt: `enterprise-agent/eval/results/offline/f206-results-complete-review-20261022.json`;
full pytest/log/coverage: `enterprise-agent/eval/results/offline-pytest-f45db457b9074cd3b822cfd966c8c66d/`.
Parser receipt: `enterprise-agent/eval/results/f206-results-parser-review-v2-20261022.json`.
Precommit binding is BLOCKED while dirty. The reviewed local commit will be checked with
`eval/results/offline/f206-results-final-20261022.json`; local CI-mode success is scoped
offline only, overall BLOCKED and release/UAT false. Stop afterward, no push/upload or next item.

## Subsequently authorized chitchat fallback — 2026-10-22

After local `d5e028c`, the separate [chitchat boundary](chitchat-trust-boundary.md) adds
fixed policy/message JSON, display-name omission, strict bounded responses/fallback and
hidden/literal candidate publication. The dated evidence above remains historical.
Optional reranking stays deferred; C17/authority unchanged, real model/privacy/runtime/
full RAG BLOCKED, F2-09 pending and C10 OPEN.
