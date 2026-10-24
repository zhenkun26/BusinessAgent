# Q015 · Source-only reference review and partial answerability

[Session](session.md#pq-t19) · [Sources L1/L2/L3](sources.md#existing-businessagent-material) · [Future validation plan](problem-and-validation-plan.md)

Status: document/annotation analysis, not a model test. The existing policy fixture, Q015 record, scorer, 122-case corpus, historical receipts and acceptance states remain unchanged. The interpretation below applies to the proposed **answer only from the supplied policy** scope; it does not declare Q015 universally wrong under every possible knowledge policy.

## Observed material

SOURCE-OBSERVED: the inspected [financial-policy fixture, section 2.1](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md#L17) lists lodging at 500 yuan daily and 800 yuan for first-tier cities. The complete inspected fixture does not specify a city-classification table or establish Shanghai's category.

SOURCE-OBSERVED: [Q015](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/eval_set.json#L194) asks “去上海出差住宿费每天能报多少”. Its expected keywords are “800 元” and “一线城市”; these are keyword annotations, not a complete reference answer. Public/local bytes and SHA-256 bindings are in the source ledger.

INFERENCE under the proposed source-only scope: directly assigning 800 yuan imports a city-classification premise not established by that fixture. This is an **unsupported conclusion in the chosen evidence scope**, not a claim that Shanghai is factually outside the first-tier category in the real world. Assigning 500 yuan unconditionally would likewise require resolving whether the exception applies.

## Learner progression and assistance

| Step | Actual contribution | Assistance already supplied |
| --- | --- | --- |
| [PQ-T19](session.md#pq-t19) | Learner marks the answer partial, preserves both standards, identifies the missing classification basis, and rejects “800” as the unique correctness condition | Coach supplied the clause, existing keywords, and the fact that the fixture lacks city classification. Credit the learner's application of the scope, not independent discovery of this source gap. |
| [PQ-T20](session.md#pq-t20) | Learner first criticizes the hypothetical refusal as too brief and asks for an explanation | Coach supplied the invented output “资料不足，无法回答”. No actual system generated it. |
| [PQ-T21](session.md#pq-t21) | Learner explicitly requires giving known standards before explaining the unresolved city classification | Coach directly prompted for omitted source-confirmed information. The learner had already included those standards in PQ-T19; this turn makes the over-refusal criterion explicit after a hint. |

The original Chinese answers and exact questions are retained in the session. This page is editorial analysis, not a rewritten transcript or a claim that the learner independently found every issue.

## Proposed annotation — outside the existing corpus

PROPOSED answerability label: **partially answerable**. This is a new analysis label, not an edit to the old test schema.

| Field | Proposed content |
| --- | --- |
| Supported fact A | Lodging standard is 500 yuan per day. |
| Supported fact B | The listed first-tier-city standard is 800 yuan per day. |
| Unresolved premise | Whether Shanghai is in the policy's first-tier category / which tier applies. |
| Required behavior | Present known standards with their conditions; explain the missing premise; withhold a definitive Shanghai allowance. |
| Evidence binding | Original table row in section 2.1; any future classification reference must be separately identified and approved as part of a new corpus version. |
| Useful next information | An applicable company-recognized city classification or an explicit policy rule resolving the tier. Do not silently substitute model memory for policy authority. |

An editor-authored rendering of the learner's reasoning, **not an original learner quotation**, is:

> 这份制度列出的住宿费标准为每日500元，一线城市每日800元。但制度没有提供上海适用档位的分类依据，因此仅凭这份制度无法确定应适用哪档，需要补充相应的分类规则。

The quantities are source facts within a project fixture; this is not advice about a real employer's reimbursement policy.

## Proposed review dimensions

| Response behavior | How to record it in a future review |
| --- | --- |
| Gives both standards, preserves the condition, explains the unresolved premise, and cites the table | Meets this proposed reference within the specified scope, subject to review of the actual response. |
| Definitively says “Shanghai is 800” using only this fixture | Unsupported premise, even if the answer sounds plausible or includes expected keywords. |
| Definitively chooses 500 without resolving the exception | Unsupported applicability decision; recording the number alone is insufficient. |
| Only says “资料不足，无法回答” | SYNTHETIC example from the conversation: misses supported facts and does not explain the specific limitation. Do not count all refusals as successful uncertainty handling. |
| Gives both numbers but uses an unrelated citation | Content and citation support are separate judgments; a real citation ID alone is insufficient. This row is an additional proposed counterexample, not an observed response. |

Keyword presence cannot distinguish a correctly qualified answer from an unsupported definitive answer that uses the same words. L3's inspected local scorer also retains a `manual_review_required` outcome; this analysis does **not** claim that the existing harness automatically certified semantic correctness or that an actual Q015 run failed.

## Consequences for the next plan

- Audit the proposed reference answers before scoring outputs. Keep supported facts, applicability conditions and unresolved premises explicit.
- Score answer completeness, factual/conditional correctness, evidence support, and uncertainty behavior separately. A blank refusal can avoid unsupported claims while still omitting useful supported content.
- Keep this prospective annotation separate from historical C17 data and denominators. A future approved dataset revision needs its own version and rationale; do not rewrite retained results retroactively.
- Test whether reviewers can distinguish complete, partial and unsupported answers consistently. This remains unperformed.

No executable test, dataset change, prompt change, rerun, model response, or performance result is produced by this page.
