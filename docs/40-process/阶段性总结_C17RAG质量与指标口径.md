# C17 RAG quality and metric semantics — offline increment

Date: 2026-10-17. Branch: `codex/delivery-ci-gates`.

C16 `bb818336b4c67c5878329a5354c7eac4e7fe27ad` was pushed to the same remote branch and
verified. This increment implements C17 only and stops after a local commit. C17 remains
open; real runtime, accepted C02 profile and complete RAG acceptance remain **BLOCKED**.
C10 lease-expiry write fencing is unresolved. Audit replay remains C21. No C18 full
integration, release, enterprise UAT, main-spec sync or change archive is authorized.

## Changes

- Frozen hashes preserve 122 original cases and nine source documents. Six separately
  scored department controls add two positive and four negative cases without diluting
  the primary denominator. Source IDs, roles, ACLs and provenance are explicit.
- Metric v2 retains failed, skipped, empty and missing rows. Normal-answer coverage divides
  by all 115 original eligible cases; success-only mean is diagnostic. Mechanical keyword,
  citation and behavior-marker checks remain separate from factual/semantic correctness.
- Runtime entry captures the actual KnowledgeAgent retrieval and final decision. Prompt
  versions/hashes, model configuration and corpus generations accompany per-case evidence.
  Default is offline; runtime opt-in requires an existing, exact, published isolated corpus.
  No ingestion/reset/migration/collection creation or report overwrite is performed.
- Fallback labels identify keyword scan and PG fulltext/ILIKE. A backend outage returns a
  service failure, not a knowledge-gap refusal. Existing ACL/publication gates remain.
- C17 OpenSpec deltas, tasks, acceptance contract and delivery records are synchronized.

See [metric contract and runtime procedure](../50-engineering/rag-quality.md).

## Verification

| Check | Result | Evidence boundary |
| --- | --- | --- |
| C17 reviewed entry | PASS, 29 cases | Actual source, injected stores/models; no measured RAG score |
| C07 retrieval authorization | PASS, 21 cases | Fixed PG failure contract; role/type/namespace guards retained |
| C15 publication | PASS, 36 cases | Existing generation visibility and publication controls |
| C02 remote models | PASS, 12 cases | Remote failure must not enter keyword fallback |
| C06 diagnostic safety | PASS, 20 cases | Existing sanitization contracts |
| C08 request context | PASS, 23 cases | History and invocation boundaries |
| Safe validator | Execution PASS, overall BLOCKED | Expected exit 2, UAT/release flags false |
| AST, added/changed links, OpenSpec structure, diff | PASS | Static only; five pre-existing README broken links remain for C25, not strict CLI validation |
| Real profile / PG / Milvus / API / SSE / Linux / full RAG | BLOCKED | No services, credentials, ingestion, model calls or corpus runs |
| Full pytest / strict OpenSpec CLI | BLOCKED | Local runtime dependencies/CLI unavailable; no installation |

29 focused + 112 related cases pass. The prior C07 expectation that a PG outage returns
an empty list was replaced with a fixed-error assertion for the intentional C17 contract.
C06 emits the pre-existing `datetime.utcnow` warning; it is not a test failure.

## Limitations and handoff

Five existing README links target old root-level documents and remain unchanged for C25.
No measured coverage, citation correctness or refusal appropriateness is claimed. Mechanical
PASS never closes C17. Human semantic review and accepted C02 runtime evidence are required;
the runner cannot manufacture them. Exact corpus preflight is not transaction-wide snapshot
isolation. Keep publishers stopped in the dedicated environment. ACL cases use component
roles and do not prove JWT/API enforcement. Confidence rules and retrieval quality were
not tuned without real per-case evidence. C15 runtime/full RAG and prior blockers persist.

The old simplified-generation runner and success-only report schema are superseded; retained
historical reports are not comparable. Byte-preserved inputs and a final-commit/hash receipt
allow review of the increment. Preserve the existing 556 mode-only changes. No dependency,
existing migration, business record, data volume or historical evidence was changed.
`formal_uat=false`, `release_evidence=false`, `release_allowed=false`.

Stop after the local C17 commit. C17 push and C18 full integration require the next confirmation.
