# Planner and tool-selection trust boundary

## Authorized plan (2026-10-22, before implementation)

Baseline: local `8edaf00`; F2-06 remains OPEN. This increment covers Planner chitchat,
intent classification, decomposition, knowledge-only replanning and execution tool
selection. Synthetic data/doubles only; no model/service requests, dependency additions,
C17 corpus/evaluator/denominator changes, database migration, push or upload.

1. Separate code-owned policy and the effective default/active/A-B task template from
   JSON human data. Current request, authorized history, proposed task text and server
   tool descriptions are data, never role changes or permission grants. Validate template
   slots/version, bounded strings and text-only responses before consuming a proposal.
   Retain only fixed boundary/template version/hash metadata, not business content.
2. Reject malformed/ambiguous JSON, unknown intent/task/tool/authority fields, native
   model calls and partial malformed plans without retrying into executable defaults.
   Preserve raw task-count/dependency budgets. Execution/approval descriptions must be
   literal excerpts of the current request, checked again before execution; history and
   replan hints cannot supply a new actionable request. Replanning stays knowledge-only.
3. Tool selection receives both the original request and the bounded task proposal as
   distinct data. Offer only role-allowed registered tools; validate the complete proposed
   batch and parameter schemas before any approval or dispatch. Remove keyword-created
   default recipients/business IDs: empty output or provider failure executes nothing.
   Model output cannot assign operation IDs, identity, permissions or approval state.
   Preserve current-identity gateway checks, approval, idempotency and Saga authority.
4. Verify real source with recording model/store/tool doubles: hostile history/task/tool
   descriptions, selected prompt versions, role separation, malformed/native responses,
   dependency/budget failures, whole-batch rejection, no fallback side effects and positive
   routing. Run the complete current offline entry without skips or lower gates, review
   source/provenance inputs, synchronize tracking/OpenSpec, commit locally, then bind the
   clean candidate and stop for confirmation.

## Acceptance and compatibility

Offline PASS requires observable System/Human separation, intact JSON data, rejection
before model/approval/tool dispatch where applicable, complete valid proposals through
existing authority gates, and no changed C17 bytes or denominators. Legacy malformed
templates and permissive prose/fenced/duplicate-key responses are deliberately rejected.
Action task paraphrases must be resubmitted as literal request excerpts; no automatic
guessing replaces a rejected/empty tool proposal.

JSON roles and literal excerpts are mechanical boundaries, not semantic intent proof.
A schema-valid allowed-tool proposal can still be semantically wrong. Provider resistance,
actual browser/API/tool behavior, privacy, real runtime and full RAG remain BLOCKED.
F2-09 sources remain pending; C10 stays OPEN. Other agent prompts and commercial validation
are outside this increment. Strict OpenSpec CLI validation remains BLOCKED while unavailable;
manual structure checks must be labeled separately. No main-spec sync or archive.

## Precommit review extension

Tag covered model calls as planning candidates and suppress
their raw stream chunks even if an inherited tag says final answer. Also reject unknown
parameter keys and non-finite numeric proposals before any batch dispatch. These are
mechanical admission/publication checks, not semantic filtering.

## Implementation and evidence — 2026-10-22

- `planning_boundary.py` supplies fixed policy, selected-template slot/version/hash checks,
  JSON data roles and strict text/JSON admission. Chitchat accepts only exact yes/no
  answers; classification rejects unknown fields/intents, decomposition rejects invalid
  members before deduplication. Existing raw-task/dependency/execution budgets remain.
- Action excerpts are checked after proposal parsing, again before agent creation and
  at selection. The executor binds `original_request` from request-owned state; history
  remains reference data and replan hints can only create a knowledge task. Literal
  containment does not distinguish quoted instructions from actual intent.
- Selection offers registered role-allowed tools and checks every member, schema and
  parameter key before returning a batch. Unknown authority fields/native calls fail;
  empty/provider-failed selection performs no action. Removed keyword defaults included
  fabricated recipient, customer/order and assignee values. No partial RBAC filtering
  survives to dispatch. The existing gateway/approval/idempotency/Saga source is unchanged.
- Covered calls carry `planning_candidate` and fixed prompt identity metadata. Raw chunks
  stay hidden even with an inherited `final_answer` tag. This does not validate other
  agents' output or prove the selected template/model will obey instruction precedence.

| Offline evidence | Result and limit |
|---|---|
| New actual-source synthetic regressions | 61 collected cases, plus 13 added subtests; hostile roles/history/catalog, default/active/A-B templates, proposal rejection, request binding, no guessed actions, positive gateway/approval routing, role change and stream suppression |
| Full Python suite | 1416 tests + 497 subtests PASS; zero skips/xfails/deselections/guard denials; 45 existing dependency warnings; 77.96% local line coverage |
| Current eight-check entry | All PASS; Node 69/14, seven browser assets, 98 production pins; 336 reviewed inputs and 441 pending-source records |
| C17 | 29 existing contract tests PASS; corpus, evaluator, sample documents and original denominators unchanged; eight separate synthetic RAG controls unchanged |
| Semantic counterexample | A schema-valid offered `lookup` with the wrong identifier is deliberately admitted as a proposal; no execution occurs in that test. Semantic resistance remains NOT MEASURED |
| Environment | macOS arm64/Python 3.13.15. Prior temporary environment was absent; a fresh ignored runtime reuses 107 cached declared/test dependency distributions via a read-only path view, no download/install or new dependency |
| Formal acceptance | Real model/tool/browser/runtime/full RAG/privacy BLOCKED; F2-09 rights pending, C10 OPEN; strict OpenSpec CLI unavailable/BLOCKED |

The current source inventory adds only the policy and synthetic test modules. The provenance
inventory adds that test file and refreshes the existing context fixture; no source rights
are approved. The fixture now supplies literal current-request action text for concurrency
tests and shares the real `PlanRejected` class; existing assertions remain intact.

Precommit receipt: `enterprise-agent/eval/results/offline/f206-planning-review-20261022.json`;
full log/coverage: `enterprise-agent/eval/results/offline-pytest-b53f4a7f6882411aafb310cc40b42201/`.
Its execution is PASS and binding BLOCKED while changes are uncommitted. The final clean
local candidate receipt will be retained at
`enterprise-agent/eval/results/offline/f206-planning-final-20261022.json` after the reviewed
local commit. Local CI-mode success is scoped offline; overall BLOCKED/release/UAT false
must remain. Stop after that receipt; no push/upload, merge, release or automatic next item.

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
