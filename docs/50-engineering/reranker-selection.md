# Reranker selection and degradation status consistency

Subsequent state (2026-10-22): [score admission](score-admission.md) extends the
numeric boundary after local `fd5511c`; factory/scorer behavior is unchanged by that
follow-up. The evidence below remains the dated factory increment. Real runtime/full RAG/
privacy remain BLOCKED; F2-09 pending, C10 OPEN.

## Authorized plan — 2026-10-22, before implementation

Baseline: local `cf43c96`. This F2-06 increment fixes factory admission and truthful
retrieval status using synthetic constructors/backends only. No real model/service,
SDK/ML install/download, new dependency, database migration, push/upload, remote CI,
main-spec sync or archive. Real runtime/full RAG/privacy remain BLOCKED; F2-09 source
rights pending and C10 OPEN. Review, local commit, retained candidate receipt, then wait.

1. Admit only bailian/local_bge/cohere/llm/passthrough/auto (case-insensitive legacy
   spelling). Reject empty/unknown providers with a fixed configuration error before
   backend work or cached reuse. Keep auto = Cohere when its key is present, otherwise
   passthrough; do not invent a backend priority/retry chain.
2. Validate the selected remote profile before cached reuse. Bind the singleton to its
   relevant process configuration; identical configuration reuses it, changed configuration
   requires restart with a fixed error. Keep credentials/fingerprints internal. This is
   conditional drift protection, not a claim of an existing runtime hot-switch exploit.
3. Record fixed internal requested/effective backend and selection reason. Distinguish
   explicit passthrough, auto without credentials, optional initialization failure and
   per-call failure. Retain the concrete Bailian type required by startup probes. No
   new public endpoint, database schema or business-result fields are needed.
4. Only actual successful scoring emits retrieval stage rerank and rerank success
   attributes. Passthrough/optional invocation fallback use vector; logs use neutral
   retrieval-result wording. Preserve the separate DegradationResult.stage vector route
   and all C17 corpus/evaluator/classifications/denominators, ACL/publication/source
   guards and policy tiebreak behavior. C21 audit/metrics remain unchanged.
5. Check the request budget before cache access/construction and before cache publication.
   Explicitly propagate budget and cancellation exceptions; interrupted construction must
   not cache a backend or a successful fallback. Ordinary optional init failure keeps the
   existing passthrough policy; required Bailian/profile failures remain fatal. These are
   cooperative guards, not hard constructor cancellation or resource-reclamation claims.
6. Add actual-source offline counterexamples for selection, cold/warm profile admission,
   configuration drift, initialization errors/interruptions, status/trace consistency,
   invocation fallback and unchanged degradation/C17 semantics. Run the complete eight
   current checks without skips or weaker gates. Review affected inventory hashes only;
   preserve frozen historical C24, C17 and independent synthetic-control inputs.
7. Synchronize existing status documents, index, provenance and OpenSpec artifacts. Review
   links/YAML/manual spec structure and original file modes; strict CLI absence remains
   BLOCKED. Make one reviewed local commit and retain a final clean-candidate receipt.

## Acceptance and explicit exclusions

| Trigger | Required result |
| --- | --- |
| Unknown/empty provider, including a warm cache | Fixed configuration failure, no backend call |
| Valid remote profile / invalid profile with cached development backend | Bailian only / fixed rejection; no production passthrough |
| Same process configuration / changed relevant configuration | Reuse / fixed restart-required error, no implicit hot switching |
| Explicit passthrough / auto without key / optional init failure | Distinct internal reasons, vector stage, no false rerank-success trace |
| Successful scorer / ordinary optional invocation failure | Rerank stage / vector stage plus fixed failure reason |
| Budget/cancel before or during initialization | Propagate; no interrupted backend/fallback admitted to cache |
| Existing degradation-chain and C17 evaluation | Route categories, corpus/evaluator/denominators unchanged |
| Delivery | Offline evidence only; F2-06 remains OPEN, all existing BLOCKED gates retained |

No automatic retry/recovery daemon, backend chain expansion, general cache manager,
concurrent cold-start certification, score calibration, new telemetry exporter or privacy
approval is included. Real SDK/model compatibility, relevance/adversarial resistance,
constructor resource lifetime, actual timeout/cancellation and Linux/multi-process
acceptance remain unproven. No requirement is removed merely because offline checks pass.

## Implementation and verification

The factory now validates known provider and remote-profile settings before cached
reuse. A private SHA-256 binding covers environment/profile and provider-specific model,
endpoint, credential, device or transport settings. It is not exported or logged. Changes
require a restart to adopt new configuration; no in-process configuration control API is
provided. Same configuration keeps the selected backend, including an initialization
fallback, until process restart. Automatic recovery and concurrent cold initialization
remain outside this increment.

Concrete backend classes retain their startup-probe identity and initialize immutable
`RerankerSelection` metadata. The retriever's internal `rerank_status` records requested
provider, effective provider and reason. It is not added to a business API, execution
receipt or C17 report. No candidates means no backend call/status. Injected custom test/
development backends without this metadata retain an explicit injected identity.

| Reason | Meaning and retrieval behavior |
| --- | --- |
| none | Backend selected; successful scoring reports rerank |
| disabled | Explicit passthrough; vector, without a rerank span/success attributes |
| auto_no_credentials | Existing auto rule selected passthrough; vector |
| initialization_failed | Ordinary optional constructor failure selected cached passthrough; vector |
| invocation_failed | Ordinary optional scoring failure; per-call coarse/vector fallback, original selection unchanged |

Unknown settings fail with `RERANKER_CONFIGURATION_INVALID`. A changed cache binding
fails with `RERANKER_CONFIGURATION_CHANGED`; an invalid remote profile fails with
`MODEL_PROFILE_INVALID`, including a warm development cache. Required Bailian loading
fails with `MODEL_RERANKER_LOAD_FAILED` in remote and explicit legacy selection. Errors
and logs use fixed text; no raw provider exception or model/credential value is emitted.
Explicit budget/concurrent-future cancellation propagates; asyncio cancellation also
propagates as BaseException. Checks run before construction/cache access and publication.
They cannot forcibly interrupt blocking model/SDK code or reclaim its resources.

The final retrieval log uses neutral result wording. Only scoring has a rag.rerank span
and success attributes; the final stage records vector/rerank truthfully. The unchanged
DegradationChain still reports vector for its primary route, whether scoring occurred
inside it or not. All five rerank method bodies, model profile/probes, publication/ACL
policy and C17 evaluation/corpus remain unchanged.

| Evidence | Outcome and limitations |
| --- | --- |
| New synthetic coverage | 68 new tests + 8 subtests: provider/auto mapping, fixed errors, cold/warm profile checks, configuration drift, initialization budget/cancellation, truthful stages/traces, ACL/source preservation and unchanged primary route |
| Complete local pytest | 1783 tests + 510 subtests PASS; zero skips/xfails/deselections/guard denials; 45 existing warnings; local Python 3.13.15, 79.83% line coverage |
| Diagnostic subtest difference | Consolidating seven factory logging expressions into two removes five automatic diagnostic subtests (79 to 74); eight new explicit subtests produce net +3; no gate/assertion weakened |
| Current offline entry | Eight checks PASS, 345 reviewed inputs/446 pending source records, Node 69/14, seven assets and 98 production pins; dirty precommit binding remains BLOCKED |
| C17 | 29 existing contract cases included in the full suite; separate guarded offline entry checked before commit; corpus/evaluator/categories/denominators unchanged |
| Scope review | Five rerank methods AST-identical to parent; all prior ACL/remote-failure assertions retained; two isolated fixtures receive only the new internal metadata type |
| Acceptance | Real SDK/model/semantic/runtime/full RAG/privacy and strict OpenSpec CLI BLOCKED; F2-09 pending, C10 OPEN, F2-06 remains OPEN |

The initial diagnostic collected 1783 tests and failed on new-source inventory drift and
one old AST fixture missing RerankerSelection. Scoped inventory registration and adding
that type fixed these failures without skipping tests or changing existing assertions.
No dependency was installed, no real service called and no inherited secrets were used
in synthetic tests. Rights status remains pending for all registered source records.

Retained local evidence:
- Initial diagnostic: `eval/results/f206-selection-diagnostic-20261022.log`.
- Precommit receipt: `eval/results/offline/f206-selection-precommit-20261022.json`.
- C17: `eval/results/f206-selection-c17-20261022.log`.
- After review/commit, final clean-candidate receipt:
  `eval/results/offline/f206-selection-final-20261022.json`.

The final receipt, rather than this document, identifies the checked commit. CI-mode
success is scoped offline execution only; overall acceptance stays BLOCKED and all
release/UAT flags false. Stop after the local reviewed commit/final receipt; wait for
confirmation. No push/upload, main-spec sync, release, archive or automatic next item.
