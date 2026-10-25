# FINANCE-QA-02 · Minimal scoring rules — dialogue draft

[Reviewed reference candidates](reference-review.md) · [Exact judgments/probes](session.md) · [Source/version ledger](sources.md)

Status: **QUALITATIVE DOCUMENTARY DRAFT / NOT EXECUTED**. This records the 2026-10-25 guided decisions, without implementing a scorer, changing `eval_set.json`, running a model or calculating an observed score. It is not independent reference validation.

## Fixed scope and units

- Source-only answers under the policy bytes bound in the ledger; use the seven FIN-01–FIN-07 documentary questions and their reviewed reference expectations. No original corpus, C17 denominator or historical score is changed.
- The unit for the overall outcome is one question's original attempt under a later defined run. Predefine the expected behavior sufficiently before counting; source uncertainty does not automatically make a question unscorable.
- The original FIN-N01 is earlier synthetic material. The four hypothetical texts below are scoring exercises, not four new benchmark items. The timeout story is not a real request/run or measured system failure.
- A reference text is not an exact-match string. Required points, supplementary information, calculations, applicability conditions and stated limits must be distinguished; unresolved per-item scoring edges remain open below.

## Separate judgments before an overall result

| Dimension | What to record / boundary |
| --- | --- |
| Content correctness | Whether stated facts, conditions and transparent calculations agree with the question/source. Missing citation is not a factual error. Unsupported extra rules or obligations must not be presented as policy. |
| Necessary-point completeness | Whether the question's required points and expected behavior are covered, within what the supplied source can support. Correct stated facts can coexist with omissions. A justified partial answer is not automatically incomplete. |
| Evidence | Source missing, cited source not supporting the claim, or source supporting the claim are distinct judgments. An existing section label alone is insufficient; the actual clause must support the conclusion. |
| Operation | Record a returned answer separately from timeout/runtime failure. A return alone does not establish semantic correctness or passage. No-answer timeout has non-assessable content/evidence, rather than invented factual-error labels. |
| Overall | Pass only when the question's expected behavior, necessary coverage, content correctness and required evidence support are satisfied. Otherwise keep the applicable reason(s); do not collapse every failure into “factually wrong”. |

These are human-readable draft categories, not newly installed enums, executable checks or numeric weights. Meaning-preserving wording is allowed; this does not excuse omitted conditions or unsupported claims. The no-exact-match note is assistant consolidation, not a separately tested learner decision.

## Minimal decisions supported by the dialogue

1. **Correct content without the required provenance does not pass this task.** Record correct content plus missing evidence. Citation expectations are specific to this source-grounded exercise, not a universal rule for every conversational answer.
2. **Citation existence and citation support differ.** A valid-looking section pointer can fail to support the conclusion; record non-support separately from missing citation and incorrect facts.
3. **Omissions differ from incorrect stated facts.** A supported daily amount can still fail a question that also asks about invoices. Reference coverage is semantic, not just keyword presence.
4. **Partial answerability can yield a fully acceptable response.** Retain supported facts, explain the missing premise/rule and request necessary clarification rather than inventing a value. Known facts must not disappear behind a blanket refusal.
5. **Keep the seven predeclared questions in the denominator once their expected behavior/rules are sufficiently clear.** FIN-02/04/07 are not removed merely because a unique factual result cannot be given. Also summarize by question type.
6. **Keep runtime failures and retries visible.** In the supplied timeout story, record runtime failure plus overall non-passage; content/evidence are non-assessable. Keep the question in the original seven-question denominator. Any retry is a separate linked observation, never a replacement for the original failure.

Whole-answer deduplication is an assistant-consolidated operating note: one question may have several diagnostic labels, but contributes only one overall result to the question denominator. This was not separately exercised with a multi-error candidate.

## Four hypothetical scoring exercises — not system outputs

<a id="sc-01"></a>

### SC-01 · FIN-01

Original assistant-supplied hypothetical candidate, C1 line 587 — verbatim:

> 出差餐补每日100元，不需发票。

Learner judgment, editorial summary: Content correct; source missing; overall not passed. Original response: [FR-S01](session.md#fr-s01).

<a id="sc-02"></a>

### SC-02 · FIN-01

Original assistant-supplied hypothetical candidate, C1 line 603 — verbatim:

> 出差餐补每日100元，不需发票。依据：《财务报销制度》第1.1节“标准流程”。

Learner judgment, editorial summary: Content correct; cited process section does not support meal facts; overall not passed. Not missing evidence or factual error. Original response: [FR-S02](session.md#fr-s02).

<a id="sc-03"></a>

### SC-03 · FIN-01

Original assistant-supplied hypothetical candidate, C1 line 619 — verbatim:

> 依据《财务报销制度》第2.1节，出差餐补每日100元。

Learner judgment, editorial summary: Stated fact correct and supported; invoice point omitted; overall not passed because a required point is missing. Original response: [FR-S03](session.md#fr-s03).

<a id="sc-04"></a>

### SC-04 · FIN-04

Original assistant-supplied hypothetical candidate, C1 line 633 — verbatim:

> 本次提供的《财务报销制度》第2.1节规定，餐补每日100元、不需发票。这份制度未说明不足一天如何计发，因此暂时无法确定半天应报多少，需要澄清计发规则。

Learner judgment, editorial summary: Passed in the exercise: known facts and source-bounded limitation are given; no invented numeric half-day amount is required. Original response: [FR-S04](session.md#fr-s04).

## Hypothetical timeout and reporting

C1 line 669 supplies the following fictional situation, not an observed run:

> 未来按既定题目和配置执行，7题中6题返回答案，另1题请求超时，没有返回答案。

The [learner response FR-S06](session.md#fr-s06) records timeout/runtime failure, overall non-passage, content/evidence not assessable, retention in the seven-question denominator, separate failure totals and independent retry records. No retry actually occurred.

For a later valid, predeclared original run, the proposed overall rate is **overall passing questions / 7**. Also report question-type results and runtime failures; a diagnostic tag is not an extra failed question. This is a prospective formula, not a measured percentage.

The assistant's closing clarification that six returns are not six passes is a derived warning, not a learner-provided six-question score. The scenario determines only one runtime failure; all returned answers still need review. Do not report 6/7 as accuracy from that story.

## Rule provenance

| Rule / refinement | Source and assistance boundary |
| --- | --- |
| Correct content versus absent provenance | [FR-S01](session.md#fr-s01); source-grounded goals and the assistant's agenda already existed, but the learner explicitly supplies this candidate's split judgment |
| Unsupported citation versus absent citation/factual error | [FR-S02](session.md#fr-s02); classification topics and content/evidence/overall fields were prompted; section comparison and explanation are learner-authored |
| Required-point omission versus incorrect stated fact | [FR-S03](session.md#fr-s03); coverage was in the agenda; the specific missing invoice point is identified by the learner |
| Source-bounded completeness and acceptable partial response | [FR-S04](session.md#fr-s04); prior Q015/FIN-04 reasoning and an explicit completeness prompt supplied context |
| Include uncertainty questions, with clear expected behavior, and report by type | [FR-S05](session.md#fr-s05); coach asks the denominator question; learner supplies the condition and per-type reporting |
| Runtime non-assessability and original-attempt/retry preservation | [FR-S06](session.md#fr-s06); timeout scenario supplied, recording and extra retry-preservation detail learner-authored |
| Meaning-preserving references, multiple reason labels/one overall outcome, six returns not six passes | [FR-R01](session.md#fr-r01), assistant consolidation, not extra independent learner statements or operational verification |

## Open edges and execution boundary

- FIN-06 explicitly makes four material categories and printing core, separates invoice compliance, and excludes supervisor approval from mandatory materials-answer points. **Omission of invoice-compliance detail alone was not explicitly graded.** Do not silently turn it into a learner-approved pass/fail rule.
- This conversation does not exhaustively adjudicate every reference sentence's mandatory status, citation rendering/locator alternatives, an empty returned body, invalid configuration/corpus-version drift, reviewer disagreement or unresolved reference interpretations. Intentional missing business input in FIN-07 is a valid question design, not automatically an execution-invalidity case.
- A separately proposed record can retain question/type, policy/reference version, original attempt, content/completeness/evidence judgments, reason/source locators, operational state and retry linkage. Those fields are editorial suggestions, not an implemented schema or a record already populated by execution.
- Another reviewer, later execution environment/model/configuration, repeats, budgets, comparative thresholds and adoption decisions remain unestablished. No trial, scorer implementation, corpus integration, new folder or reconstruction is authorized by this document.
