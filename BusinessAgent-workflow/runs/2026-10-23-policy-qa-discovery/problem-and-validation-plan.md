# POLICY-QA-01 · Problem definition and next validation plan

[Original dialogue](session.md) · [Sources](sources.md) · [Q015 analysis](q015-analysis.md) · [Record index](../README.md)

Status: consolidated discovery draft and **PROPOSED / NOT STARTED** validation plan. This is live-project planning, not a historical replay. No experiment, model call, dependency installation, reconstruction folder, existing-project modification, or publication is authorized by this plan itself. The separate subsequent user instruction authorizes only the selected document publication, as recorded in the [source ledger](sources.md#local-conversation); the validation plan remains unexecuted.

Subsequent documentation-only follow-up, 2026-10-23: the [first financial-policy reference draft](../2026-10-23-finance-qa-reference-set/reference-set.md) now contains seven questions and one synthetic counterexample, with original answers, assistance history and versioned clauses. This advances reference authoring only; separate review, final scoring/denominator criteria and execution remain pending. The proposed sequence below is retained; it is not a completed test or G2 execution authorization.

## Two problems with different evidence

| Problem | Evidence currently available | Desired change / unresolved question |
| --- | --- | --- |
| Repeated workflow interruptions during packaging/testing | Learner testimony in [PQ-T01–T04](session.md#pq-t01): related fixes trigger repeated scope confirmation and full documentation steps | Proposed goal-based continuity for related bugs/tests/small adjustments, stage-end documentation, and renewed confirmation for substantive scope changes. Which burden comes from OpenSpec, repository instructions or assistant execution has not been independently audited or timed. |
| Policy-QA reliability and technology choices lack a comparable factual baseline | [PQ-T08–T12](session.md#pq-t08): the learner reports insufficient actual testing; source inspection identifies existing retrieval/scoring infrastructure but no fresh result | Establish answer accuracy, completeness, evidence support and appropriate unknown behavior, then compare candidate methods. Do not infer that the old architecture is faulty merely because newer technology exists. |

The actor for this discovery is the project owner/evaluator; the intended answer user is someone consulting enterprise policies. The motivating task is understanding travel-reimbursement materials and limits from supplied policy text. No observed enterprise customer demand, production use, or commercial outcome is claimed.

## Consolidated problem statement — editor-authored draft

BusinessAgent needs a source-comparable evaluation baseline for policy question answering. Without it, the project owner cannot reliably determine whether responses are complete, factually and conditionally correct, supported by their cited clauses, and appropriately limited when evidence is missing. Candidate methods should be compared on the same corpus and tasks to decide what, if anything, merits technical change.

For partly answerable questions, the target is to provide supported information and identify the unresolved part. An indiscriminate refusal is not automatically successful behavior. This extension was made explicit after the Q015/refusal probes; see [PQ-T19–T21](session.md#pq-t19).

This draft synthesizes the learner's answers; it is not their original wording. Original statements remain unchanged in the session.

## Scope, options and the current decision

- First investigation: policy QA using versioned source material and manually grounded references, including the travel-expense scenario. This does not cover every BusinessAgent workflow, live execution tool, or deployment contract.
- LightRAG: conditionally admitted as a candidate for a small controlled comparison after source review, not selected as the replacement architecture. Public preference-evaluation results do not establish our source-only answer correctness or citation support.
- RAGFlow: initial parsing/chunking/source-navigation reference. RAGChecker: older claim-level diagnostic reference. Neither was installed, benchmarked, or selected as mandatory infrastructure.
- Candidate choices remain retain, local correction, further investigation, or redesign based on evidence. “重新设计” at PQ-T13 was followed by the learner's clarification at PQ-T14 that the goal was to investigate newer work; it is not a completed design decision or implementation authorization.
- Future reconstruction, if authorized, uses a separate new folder without OpenSpec. Name, location, minimal scope and architecture remain undecided; the existing BusinessAgent and its historical corpus stay intact.

The learner's proposed confirmation boundary at PQ-T04 is a collaboration design input, not a repeal of current safety instructions or authorization to delete data, add dependencies, publish, or change architecture.

## Basis for the test design

| Design element | Origin |
| --- | --- |
| Manually list materials, conditions and exceptions; cite original text; preserve unknowns | Learner method at [PQ-T10](session.md#pq-t10), after a reference-design question |
| Direct clauses, multiple conditions, exceptions, cross-clause synthesis, absent facts, underspecified inputs and false premises | Learner design at [PQ-T11](session.md#pq-t11), after an open coverage prompt |
| Retain raw question, corpus version, reference, retrieved clauses, supplied model context and final answer | Learner design at [PQ-T12](session.md#pq-t12), after a diagnostic-evidence prompt |
| Comparable scenario/code/data/method/baseline before candidate evaluation | Learner criteria at [PQ-T15/T16](session.md#pq-t15), informed by disclosed research |
| Fix corpus, questions, references, generator/parameters, scoring and context budget; record unavoidable differences; split indexing/query cost | Specific learner controls at [PQ-T17](session.md#pq-t17), within a prompted fair-comparison task |
| Pause for irreproducibility, worse errors/unsupported claims or unjustified cost; retain uncertainty with close results or small samples | Learner stopping conditions at [PQ-T18](session.md#pq-t18) |
| Explicit partial answerability and over-refusal review | Source packet + learner application at PQ-T19; explicit omission check prompted before PQ-T21 |
| Separate holdout, reviewer consistency checks, fair execution order, authorization/visibility parity and operational-failure accounting | Additional assistant planning proposals below; not attributed to the learner as already stated or completed |

## Next work units — plan only

### 1. Review and bind the reference material

Use the existing financial-policy fixture as an initial candidate, not a real company policy claim. Bind the file/version/hash, permitted evidence scope and question IDs. Record whether outside factual knowledge is allowed; this proposed first scope is source-only. If a city classification is later added, bind it as a separate authorized source and a new corpus version, not a silent reinterpretation of Q015.

Create a prospective annotation artifact only in a separately authorized test workspace. It should contain required facts, conditions, exceptions, supporting text/locators, unresolved premises and an answerability label: fully answerable, partially answerable, unanswerable, or clarification required. These labels are proposed review fields, not edits to the current corpus schema.

Q015 is the first reference-audit example, not a model failure. Review the remaining proposed references for similar hidden assumptions before using them to judge outputs. Keep historical C17 data, primary/supplemental denominators and retained receipts unchanged.

### 2. Choose and freeze a small discriminating set

Include the learner's seven question categories above. Bind the supported clauses and known unknowns before looking at outputs. Set size, allocation by category, a revision policy and any held-out examples are **TBD**; no arbitrary universal sample count or pass percentage is imposed here.

For richer or changed references, record why the change was necessary and evaluate under a new plan version. Do not tune references to make one system's observed answer look correct. A separately reserved set is an assistant proposal for reducing test-specific tuning, not a test already performed.

### 3. Specify scoring and denominators before execution

Review required fact/condition coverage, wrong statements, unsupported additions, citation support for each substantive claim, missing-evidence handling and over-refusal. Keep response-level and claim-level counts distinguishable. Keyword and citation-ID checks may help find cases to inspect; they do not replace source entailment review.

Predefine treatment of empty responses, provider errors, timeouts, invalid setup, retries and unavailable retrieval. Report these counts rather than silently removing them from the denominator or calling infrastructure failure a semantic result. Separate reviewer disagreement and ambiguous references from model errors.

Reviewer process, repeat count, sample adequacy and acceptable quality/latency/cost ranges remain **TBD**. A blinded answer ordering and a second human check for disagreements are proposed controls. An automatic judge, if later used, needs validation against the human references; RAGChecker is optional research, not approved installation or scoring authority.

### 4. Establish the existing-scheme baseline in an isolated authorized setting

This unit is not started. Identify the exact local implementation revision, effective model/profile, parser/chunker, embedding/reranker, identity/authorization scope, generation prompt/parameters, context budget and machine/runtime conditions. Static code inspection does not establish which configuration actually ran.

Preserve question, versioned reference, retrieved candidates/selected clauses, actual supplied context, output, source mapping, statuses and resource use as explicitly approved test artifacts. Do not turn this plan into business-payload logging or automatic external telemetry in the existing application.

Use failure categories as investigation routes: source missing/conflicting; relevant clause absent from retrieval; retrieved clause omitted/truncated from model context; provided evidence not used correctly; unsupported citation; inappropriate refusal. A category is not a proven root cause without discriminating evidence.

### 5. Verify the LightRAG candidate and run a matched comparison

First inspect the pinned reproduction materials and determine whether their dependencies, data, scripts and actual prompts are available and consistent. Reading the guide is not reproducing its result. No installation, model call or upstream script execution is included in this documentation increment.

If execution is later authorized, fix the learner's shared corpus/questions/references/generator/parameters/scoring/context budget. Make retrieval and context organization the main comparison target. Preserve equal authorized evidence visibility; broader access must not masquerade as a retrieval improvement.

Record extra graph construction, entity/relationship extraction, keyword generation, prompts, parsers, embedding models or other mandatory changes as part of the actual system difference. Match them where feasible; otherwise limit attribution to the compared configurations, not one isolated algorithm. Fair order/repetition and warm/cold conditions should be agreed before running.

### 6. Account for all costs and compare individual failures

Separate one-time/repeated index-build work, incremental rebuild/update work, and each question's retrieval/context/generation/retry work. Record model calls/tokens, latency and available resource/cost evidence for both stages; state the intended query/update workload before amortizing indexing cost. Workload and cost budget remain **TBD**.

Compare paired cases and question categories as well as aggregates. Inspect regressions in unsupported content, condition accuracy, citation entailment and partial-answer handling even if overall coverage rises. Do not infer our task accuracy from a published overall preference win rate or a better retrieval score.

### 7. Interpret using the learner's stopping rules

| Observation | Planned response / limit |
| --- | --- |
| Setup cannot be reproduced or controlled conditions are not actually comparable | INVALID/BLOCKED; investigate setup, not a verdict that the product hypothesis failed. |
| Same-condition wrong answers, unsupported additions or unsupported citations increase | Pause the candidate; retain failure evidence. The magnitude/tolerance criterion must be settled before data collection. |
| Fewer omissions but confident answers with insufficient evidence persist or worsen | Do not advance on completeness alone. Inspect uncertainty and partial-answer behavior. |
| Index/query cost or latency increases without justified benefit | Pause; acceptable workload, budget and benefit criteria are unresolved. |
| Results are close or the sample is insufficient | INCONCLUSIVE; do not announce superiority or silently expand the success claim. |
| Target quality improves without unacceptable regressions and within agreed constraints | SUPPORTS further bounded validation only for the tested scope, not automatic framework adoption, reconstruction or production readiness. |

Preserve retain/local-fix/redesign/further-investigation options. No framework adoption decision can be derived from this document because no results exist.

## Gates and unresolved inputs

| Gate | Current planning status | Missing before dependent action |
| --- | --- | --- |
| G1 — Problem | Learner articulated the scenario, evidence gap and goals; consolidated wording is editorial synthesis of the dialogue | Resolve the first corpus/reference scope; do not turn this documentation into another mandatory full-PRD cycle |
| G2 — Validation | Detailed plan proposed; **NOT EXECUTION-AUTHORIZED** | Test workspace location, implementation/candidate revisions, exact cases, permitted data/model calls, budget, repeat/denominator rules, review procedure and prospective criteria |
| G3 — Decision | Conditional candidate shortlist; adoption and architecture remain undecided | Actual comparable observations, failure analysis and an owner decision on the next bounded scope |

These are live-project planning gates, not falsely recorded as completed operational approvals or historical replay results. The Q015 refusal alone is SYNTHETIC. Existing project acceptance and rights states remain unchanged.

## Follow-up practice and next checkpoint

- On a fresh source-only problem, ask for the reference before revealing hidden-premise or partial-answer examples. Q015's gap was supplied by the coach, and explicit over-refusal handling needed a follow-up hint.
- Ask the learner to specify workable denominator, repeat and cost/latency decision criteria for the chosen sample. Reporting a dimension and defining a usable decision rule are separate steps.
- Let a new candidate's documented evaluation be inspected before the coach supplies its limitations. Distinguish source-audit reasoning from applying limitations already revealed.
- Measure whether stage-end documentation and grouped in-scope work actually reduce interruption when a future engineering unit is separately authorized; present testimony does not quantify the improvement.

The next concrete checkpoint is to expand the documented Q015 annotation proposal into a small reviewed **reference-and-question set**, with unresolved assumptions and scope explicit, before any baseline run. That set and all execution remain PROPOSED / NOT STARTED. Q015's documented proposal is not a completed benchmark set or a model result.
