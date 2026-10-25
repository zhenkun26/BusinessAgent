# FINANCE-QA-02 · Original references and review revisions

[Exact learning exchange](session.md) · [Minimal scoring draft](scoring-rules.md) · [Sources/version preservation](sources.md)

Status: **ASSISTED DOCUMENT REVIEW / REVISED CANDIDATES**, not independent validation, a scored benchmark or an existing-dataset edit. Date: 2026-10-25, `America/New_York`.

## What is preserved and what is new

The [original reference draft](../2026-10-23-finance-qa-reference-set/reference-set.md) is byte-identical to the source at local starting revision `372fcc3`. All three original local run files remain unchanged in the authoring checkout; this publication also leaves their three previously published counterparts unchanged from `b735937`. The source ledger distinguishes original local hashes from earlier published session/ledger transformations. Each original question and reference block is repeated below verbatim for comparison. “Original”/“revised”, or v1/v2, are editorial document labels, not policy versions or machine-data releases.

Chinese revised candidates below are **editor-authored renderings of the review opinions**. They are not verbatim learner answers or observed system responses. Exact answers/probes are in the session. Same-assistant review and prior exposure are disclosed; “independent contribution” concerns a specific supplied-task judgment, not independent reviewer certification.

Evidence is limited to the same 89-line policy fixture: SHA-256 `b781104c86183f631f7b761fd8d1b8b3fe4d44205e69bdb04927a8a1500ccd56`, Git blob `005c008cbb238b09b9af5d174aa55a3174f00fa5`. The [source ledger](sources.md) binds local/public revisions and the original draft hash. There is no explicit effective company-policy version/date.

| Item | Review disposition | Learner response |
| --- | --- | --- |
| [FIN-01](#review-fin-01) | KEEP — original answer retained | [FR-A01](session.md#fr-a01) |
| [FIN-02](#review-fin-02) | REVISE — narrow the endpoint statement | [FR-A02](session.md#fr-a02) |
| [FIN-03](#review-fin-03) | KEEP — original rule/calculation chain retained | [FR-A03](session.md#fr-a03) |
| [FIN-04](#review-fin-04) | KEEP SUBSTANCE — make the inspected-source scope explicit | [FR-A04](session.md#fr-a04) |
| [FIN-05](#review-fin-05) | REVISE — bound the no-ratification statement | [FR-A05](session.md#fr-a05) |
| [FIN-06](#review-fin-06) | RESTRUCTURE — core materials, compliance and process layers | [FR-A06](session.md#fr-a06) |
| [FIN-07](#review-fin-07) | REVISE — separate missing amount from endpoint interpretation | [FR-A07](session.md#fr-a07) |

<a id="review-fin-01"></a>

## FIN-01

**Original question — verbatim**

> 出差期间，餐补的标准和发票要求是什么？

**Original reference — verbatim, retained**

> 出差期间餐补为每日100元，不需发票。依据第2.1节差旅费表：表头为“标准(每日)”，餐补一行为“100 元”“不需发票”。

**Review disposition:** KEEP — original answer retained.

**Revision opinion / rationale:** Header supplies the daily unit; row supplies amount/no-invoice facts. No additional exemption follows. This review keeps the original answer text.

**Revised reference candidate — editorial consolidation**

> 出差期间餐补为每日100元，不需发票。依据第2.1节差旅费表：表头为“标准(每日)”，餐补一行为“100 元”“不需发票”。

Original clause bindings: [P-03](../2026-10-23-finance-qa-reference-set/sources.md#p-03). Review response and assistance: [FR-A01](session.md#fr-a01).

<a id="review-fin-02"></a>

## FIN-02

**Original question — verbatim**

> 单次招待费正好为3000元，应由谁审批？

**Original reference — verbatim, retained**

> 现有制度写明“单次1000-3000元：部门负责人审批”和“单次≥3000元：总经理审批”。3000元处存在需要澄清的边界问题，原文没有说明区间端点或优先规则。仅依据这份制度，暂时不能唯一确定审批人；应保留两条规定并进一步澄清。

**Review disposition:** REVISE — narrow the endpoint statement.

**Revision opinion / rationale:** The old phrase that the source does not explain interval endpoints is too broad: ≥3000 explicitly includes 3000. The remaining issue concerns the middle range's upper endpoint and possible overlap/priority. This is a source-only conservative interpretation, not a policy-owner ruling.

**Revised reference candidate — editorial consolidation**

> 本次提供的制度写明“单次1000-3000元：部门负责人审批”和“单次≥3000元：总经理审批”。“≥3000元”明确包含3000元；需要澄清的是“1000-3000元”是否包含3000元，以及两条规定可能重叠时的优先关系。仅依据当前这份制度，暂时不能唯一指定审批人，应保留两条依据并说明上述限制。

Original clause bindings: [P-04](../2026-10-23-finance-qa-reference-set/sources.md#p-04). Review response and assistance: [FR-A02](session.md#fr-a02).

<a id="review-fin-03"></a>

## FIN-03

**Original question — verbatim**

> 员工月薪4000元，因公出差申请借款9000元，计划45天后用报销冲抵，是否符合制度中的借款条件？

**Original reference — verbatim, retained**

> 不符合。因公出差符合可申请借款的用途，但制度要求借款金额不超过月薪2倍，因此本题上限为4000×2＝8000元，9000元超限；制度还要求30天内归还或报销冲抵，45天后冲抵也超过期限。用途符合不能替代金额和期限要求。

**Review disposition:** KEEP — original rule/calculation chain retained.

**Revision opinion / rationale:** Purpose is eligible, 4000 × 2 = 8000, 9000 exceeds the amount limit and 45 exceeds 30 days. Inputs are fictional and arithmetic is distinct from the original rule. No approval/payment is claimed.

**Revised reference candidate — editorial consolidation**

> 不符合。因公出差符合可申请借款的用途，但制度要求借款金额不超过月薪2倍，因此本题上限为4000×2＝8000元，9000元超限；制度还要求30天内归还或报销冲抵，45天后冲抵也超过期限。用途符合不能替代金额和期限要求。

Original clause bindings: [P-07](../2026-10-23-finance-qa-reference-set/sources.md#p-07). Review response and assistance: [FR-A03](session.md#fr-a03).

<a id="review-fin-04"></a>

## FIN-04

**Original question — verbatim**

> 员工只出差半天，餐补应该报多少？

**Original reference — verbatim, retained**

> 制度规定餐补每日100元、不需发票，但没有说明不足一天如何计发。因此可以提供已知标准，暂时不能仅凭这份制度确定半天应报多少，需要进一步澄清计发规则。

**Review disposition:** KEEP SUBSTANCE — make the inspected-source scope explicit.

**Revision opinion / rationale:** Learner proposes checking the same-version full document, not just the table row; the assistant then performs the source read. The original reference is retained in substance, with an editorial scope clarification for standalone use. Do not turn a proposed learner method into a completed learner inspection or infer what other documents contain.

**Revised reference candidate — editorial consolidation**

> 本次提供且已核对的这份制度规定，餐补每日100元、不需发票，但未说明不足一天如何计发。因此应保留已知标准，暂时不能仅凭这份制度确定半天应报多少，需要进一步澄清计发规则。

Original clause bindings: [P-03](../2026-10-23-finance-qa-reference-set/sources.md#p-03). Review response and assistance: [FR-A04](session.md#fr-a04).

<a id="review-fin-05"></a>

## FIN-05

**Original question — verbatim**

> 员工本月尚未办理过紧急报销，现在有一笔紧急费用，能否跳过主管审批？

**Original reference — verbatim, retained**

> 可以按制度规定的紧急报销路径跳过主管审批，但需附加说明，直接由财务总监审批，紧急报销每月限1次；题目已说明本月尚未办理。原文未规定后续主管补批要求。

**Review disposition:** REVISE — bound the no-ratification statement.

**Revision opinion / rationale:** Keep explanation, CFO approval and monthly limit. The narrower final sentence does not prohibit later approval, create mandatory ratification or waive other unexempted steps. Scope was explicitly prompted by the coach.

**Revised reference candidate — editorial consolidation**

> 可以按制度规定的紧急报销路径跳过主管审批，但需附加说明，直接由财务总监审批，紧急报销每月限1次；题目已说明本月尚未办理。在本次提供的这份制度中，未见后续主管补批要求。

Original clause bindings: [P-02](../2026-10-23-finance-qa-reference-set/sources.md#p-02). Review response and assistance: [FR-A05](session.md#fr-a05).

<a id="review-fin-06"></a>

## FIN-06

**Original question — verbatim**

> 员工报销一笔800元的招待费，持有电子发票，按照制度应准备哪些报销材料？

**Original reference — verbatim, retained**

> 应准备《费用报销单》《招待申请单》、参与人员名单，以及打印后附上的电子发票。发票抬头、税号应符合第3.2节的要求，并包含开票日期、商品明细、金额和税率。800元对应主管审批，但审批是流程要求，不能替代上述材料。

**Review disposition:** RESTRUCTURE — core materials, compliance and process layers.

**Revision opinion / rationale:** Four material categories and printing are core. Compliance information is separately presented; approval is explicitly not a mandatory materials-answer point. The original table heading “Required point” groups core and contextual rows, so do not mechanically turn every old table row into a pass condition. Whether omission of compliance detail alone fails was not explicitly adjudicated; retain that edge as open.

**Revised reference candidate — editorial consolidation**

> 核心材料：《费用报销单》《招待申请单》、参与人员名单，以及打印后附上的电子发票；打印要求不能省略。
>
> 发票合规说明：发票抬头、税号应符合第3.2节的要求，并包含开票日期、商品明细、金额和税率。
>
> 流程补充：800元对应主管审批；审批不能替代上述材料，也不作为本题材料清单的必答要点。

Original clause bindings: [P-01](../2026-10-23-finance-qa-reference-set/sources.md#p-01) · [P-04](../2026-10-23-finance-qa-reference-set/sources.md#p-04) · [P-05](../2026-10-23-finance-qa-reference-set/sources.md#p-05) · [P-06](../2026-10-23-finance-qa-reference-set/sources.md#p-06). Review response and assistance: [FR-A06](session.md#fr-a06).

<a id="review-fin-07"></a>

## FIN-07

**Original question — verbatim**

> 我这笔招待费该找谁审批？

**Original reference — verbatim, retained**

> 需要先确认这笔招待费的单次金额，当前不能直接指定审批人。现有制度写明：单次≤1000元由主管审批，1000-3000元由部门负责人审批，≥3000元由总经理审批。1000元和3000元处的区间端点、适用边界仍需澄清；应提供已知分级规则，并根据补充的金额判断是否还涉及边界问题。

**Review disposition:** REVISE — separate missing amount from endpoint interpretation.

**Revision opinion / rationale:** ≤1000 and ≥3000 have explicit endpoints; the middle range's endpoints/overlap priority need clarification. Missing amount is the immediate input gap; non-boundary routing becomes possible when the amount is supplied. This extends FR-A02 rather than independently discovering the endpoint issue anew.

**Revised reference candidate — editorial consolidation**

> 需要先确认这笔招待费的单次金额，当前不能直接指定审批人。现有制度写明：单次≤1000元由主管审批，1000-3000元由部门负责人审批，≥3000元由总经理审批。“≤1000元”和“≥3000元”的端点明确；需要澄清的是“1000-3000元”是否包含两端，以及可能重叠时的优先关系。补充金额后，非边界金额可以按规则判断，不能把边界问题扩大为所有金额都无法确定。

Original clause bindings: [P-04](../2026-10-23-finance-qa-reference-set/sources.md#p-04). Review response and assistance: [FR-A07](session.md#fr-a07).

## Scope of the review outcome

The review distinguishes directly explicit endpoints from unresolved interpretation, missing input from policy uncertainty, source-scoped absence from universal absence, and core answer points from supplementary process information. It does not amend the actual policy or resolve the author's intent.

FIN-06 compliance-detail scoring, the precise treatment of valid alternative phrasings and future execution-invalidity cases are not fully adjudicated by the thirteen responses. They remain explicit draft edges in the scoring document rather than silently becoming learner-approved rules. Existing FIN-N01 remains earlier synthetic teaching material; it is not executed or added to the corpus here.

No original reference is overwritten, no final benchmark is declared, and no system score, runtime result, independent-review agreement or framework-adoption conclusion is produced.
