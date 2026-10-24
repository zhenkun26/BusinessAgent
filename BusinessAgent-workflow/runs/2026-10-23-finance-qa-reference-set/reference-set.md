# FINANCE-QA-01 · First financial-policy reference set

[Original answers and coaching](session.md) · [Policy version and original clauses](sources.md) · [Run index](../README.md)

Status: **DOCUMENTARY DRAFT — NOT EXECUTED**. Seven questions and one assistant-authored synthetic counterexample, consolidated from the learner-first conversation on 2026-10-23 (`America/New_York`). These identifiers belong only to this document; nothing is added to the existing evaluation dataset or scorer.

## Evidence scope and authorship

- Answer only from the financial-policy fixture bound in the source ledger: local revision `4819a02e760715513142d0b9a20f9cc52fa58d28`, SHA-256 `b781104c86183f631f7b761fd8d1b8b3fe4d44205e69bdb04927a8a1500ccd56`. Its bytes match the pinned public counterpart. It is a project sample, without an explicit policy-effective date/version or established real-enterprise authority.
- Chinese questions retain their original wording. Chinese reference answers below are **editor-consolidated drafts**, not verbatim learner responses or observed model outputs. English annotations distinguish original rules, transparent calculations and bounded interpretations. Exact learner wording and prompts remain in the session.
- Prior Q015 exposure is known. This is assisted reference authoring, not a blind assessment or proof that a system or learner generalizes reliably.
- Partial answerability, missing input and policy ambiguity are distinct. Preserve supported information while naming the unresolved part. A response containing some correct facts can still fail the proposed whole-answer standard if it adds an unsupported exemption or extra obligation.
- Review notes below are prospective qualitative expectations. No score, threshold, benchmark denominator, model call, application test, annotation-agreement result or execution approval is created here.

| Document ID | Focus | Answerability in the supplied scope |
| --- | --- | --- |
| [FIN-01](#fin-01) | Direct clause extraction and table-header unit | Fully answerable |
| [FIN-02](#fin-02) | Hospitality approval at 3000 yuan | Policy endpoint clarification needed; stated rules can be reported |
| [FIN-03](#fin-03) | Multiple loan conditions and arithmetic | Fully answerable for the stated conditions |
| [FIN-04](#fin-04) | Half-day meal allowance | Partially answerable; payment rule is missing |
| [FIN-05](#fin-05) | Emergency exception and its conditions | Conditionally answerable; no invented later ratification |
| [FIN-06](#fin-06) | Materials across several clauses | Answerable for the described claim |
| [FIN-07](#fin-07) | Approval request without amount | User-input clarification needed; endpoint ambiguity is a separate issue |
| [FIN-N01](#fin-n01) | Supported facts followed by an unsupported exemption | Synthetic negative control, not an eighth question or actual system result |

<a id="fin-01"></a>

## FIN-01 · Daily meal allowance and invoice

**Original question**

> 出差期间，餐补的标准和发票要求是什么？

**Consolidated reference answer**

> 出差期间餐补为每日100元，不需发票。依据第2.1节差旅费表：表头为“标准(每日)”，餐补一行为“100 元”“不需发票”。

- Source: [P-03, section 2.1, lines 17–23](sources.md#p-03), particularly header line 18 and meal row line 22.
- SOURCE-OBSERVED: amount and invoice requirement are in the row; the daily unit comes from the header. No calculation is needed.
- Proposed review: preserve amount, time unit and invoice exception. Do not infer that claim forms or approval are waived; see FIN-N01.
- Attribution: [FQ-T01](session.md#fq-t01) supplies these details before any answer-specific correction. The assistant supplied the question and section pointer; prior Q015 exposure remains relevant.

<a id="fin-02"></a>

## FIN-02 · Hospitality claim exactly at 3000 yuan

**Original question**

> 单次招待费正好为3000元，应由谁审批？

**Consolidated reference answer**

> 现有制度写明“单次1000-3000元：部门负责人审批”和“单次≥3000元：总经理审批”。3000元处存在需要澄清的边界问题，原文没有说明区间端点或优先规则。仅依据这份制度，暂时不能唯一确定审批人；应保留两条规定并进一步澄清。

- Source: [P-04, section 2.2, lines 25–29](sources.md#p-04), especially lines 27–28.
- SOURCE-OBSERVED: both tier strings appear in the fixture. INFERENCE: the range's endpoint semantics/priority are not explicit, so this conservative source-only reference withholds a unique assignment. This is not a verified policy-owner interpretation or an amendment to the rule.
- Proposed review: identify the relevant rules and limitation; do not silently decide that a stricter role, later line or familiar business convention automatically takes priority. A blanket refusal that omits both known rules is incomplete.
- Attribution: [FQ-T03](session.md#fq-t03) identifies this issue before the coach names it. The question deliberately supplied the endpoint and a section pointer; this is not unprompted discovery across the entire policy.

<a id="fin-03"></a>

## FIN-03 · Loan amount and settlement period

**Original question**

> 员工月薪4000元，因公出差申请借款9000元，计划45天后用报销冲抵，是否符合制度中的借款条件？

**Consolidated reference answer**

> 不符合。因公出差符合可申请借款的用途，但制度要求借款金额不超过月薪2倍，因此本题上限为4000×2＝8000元，9000元超限；制度还要求30天内归还或报销冲抵，45天后冲抵也超过期限。用途符合不能替代金额和期限要求。

| Claim type | Trace |
| --- | --- |
| SOURCE-OBSERVED rules | [P-07, section 5.1, lines 68–71](sources.md#p-07): business travel/purchasing, amount ≤ twice monthly salary, repayment or expense offset within 30 days |
| Question-supplied inputs | Monthly salary 4000, loan 9000 and settlement at 45 days are SYNTHETIC scenario inputs, not facts from a real employee |
| Transparent calculation | 4000 × 2 = 8000; 9000 > 8000; 45 > 30 |
| Bounded conclusion | The proposed amount and deadline fail the stated conditions; no actual loan application, approval or transfer occurred |

- Proposed review: check all three conditions. Do not label the request compliant merely because its purpose is eligible; do not change “days” into “working days”.
- Attribution: [FQ-T04](session.md#fq-t04) independently performs the calculation and both comparisons within the supplied scenario. The assistant subsequently explains how to label direct rules versus derived results.

<a id="fin-04"></a>

## FIN-04 · Half-day meal allowance

**Original question**

> 员工只出差半天，餐补应该报多少？

**Consolidated reference answer**

> 制度规定餐补每日100元、不需发票，但没有说明不足一天如何计发。因此可以提供已知标准，暂时不能仅凭这份制度确定半天应报多少，需要进一步澄清计发规则。

- Source: [P-03, section 2.1, lines 17–23](sources.md#p-03). The absence conclusion is scoped to the complete inspected 89-line fixture, not every possible company document.
- SOURCE-OBSERVED: daily standard and invoice exception. UNKNOWN: half-day treatment. No authorized calculation maps “half a day” to a payment amount in this source.
- Proposed review: retain known facts and the missing rule. Do not invent rounding up, proportional payment or a zero entitlement; do not treat this as wholly unanswerable and omit all supported information.
- Attribution: initial [FQ-T05](session.md#fq-t05) says “按日结算，不满一日的按一日计算”. After the coach asks for the exact rule, [FQ-T06](session.md#fq-t06) explicitly acknowledges the unsupported inference and revises. The corrected reference is **prompted revision**, not correct first-attempt transfer.

<a id="fin-05"></a>

## FIN-05 · Emergency claim without supervisor approval

**Original question**

> 员工本月尚未办理过紧急报销，现在有一笔紧急费用，能否跳过主管审批？

**Consolidated reference answer**

> 可以按制度规定的紧急报销路径跳过主管审批，但需附加说明，直接由财务总监审批，紧急报销每月限1次；题目已说明本月尚未办理。原文未规定后续主管补批要求。

- Source: [P-02, section 1.2, lines 11–13](sources.md#p-02). The monthly-history premise is supplied by the SYNTHETIC question.
- SOURCE-OBSERVED: explanation, permitted supervisor exception, CFO approval and monthly limit. INFERENCE: the stated count premise satisfies that particular limit; it is not a receipt that an application was approved or paid.
- Proposed review: keep the conditions and actual approval role. Do not add “temporarily” or mandatory later supervisor ratification, and do not infer that all other claim steps are waived. “The supplied text does not require later ratification” does not establish that all other policies prohibit it.
- Attribution: [FQ-T07](session.md#fq-t07) includes supported facts but invents later ratification. [FQ-T08](session.md#fq-t08) offers “合理流程闭环” when asked for evidence. The **assistant then explains and supplies the corrected reference**. [FQ-T09](session.md#fq-t09) later explicitly rejects the addition and proposes a checking method; preserve this order.

<a id="fin-06"></a>

## FIN-06 · Entertainment-claim materials with an e-invoice

**Original question**

> 员工报销一笔800元的招待费，持有电子发票，按照制度应准备哪些报销材料？

**Consolidated reference answer**

> 应准备《费用报销单》《招待申请单》、参与人员名单，以及打印后附上的电子发票。发票抬头、税号应符合第3.2节的要求，并包含开票日期、商品明细、金额和税率。800元对应主管审批，但审批是流程要求，不能替代上述材料。

| Required point | Original source |
| --- | --- |
| Expense claim form | [P-01, section 1.1, line 6](sources.md#p-01) |
| Hospitality application and participant list | [P-04, section 2.2, line 29](sources.md#p-04) |
| E-invoice printed and attached | [P-05, section 3.1, line 40](sources.md#p-05) |
| Invoice title/tax ID plus date, item details, amount and tax rate | [P-06, section 3.2, lines 42–45](sources.md#p-06); company/tax strings there are fixture placeholders |
| Supervisor role for 800 yuan | [P-04, line 26](sources.md#p-04); contextual process information, not a substitute material |

- Proposed review: cover all four material categories and retain the printing condition. Keep invoice information requirements separate from approving authority; do not silently add an unsupported extra form or omit a common claim form because this is a special expense type.
- Attribution: [FQ-T10](session.md#fq-t10) assembles the forms, participant list, printing requirement and metadata category without a question-specific correction. It follows the coached checking-method discussion. This editorial reference expands “必要信息” into the four fields explicitly listed in the original clause; the expansion is not attributed as a verbatim learner enumeration.

<a id="fin-07"></a>

## FIN-07 · Hospitality approval without a stated amount

**Original question**

> 我这笔招待费该找谁审批？

**Consolidated reference answer**

> 需要先确认这笔招待费的单次金额，当前不能直接指定审批人。现有制度写明：单次≤1000元由主管审批，1000-3000元由部门负责人审批，≥3000元由总经理审批。1000元和3000元处的区间端点、适用边界仍需澄清；应提供已知分级规则，并根据补充的金额判断是否还涉及边界问题。

- Source: [P-04, section 2.2, lines 25–29](sources.md#p-04). No amount is supplied in this question; do not import the 800 or 3000 yuan from a different item.
- Missing-input issue: ask for the single-claim amount. Policy-interpretation issue: the endpoint/priority wording is not explicit. These are separate causes of uncertainty; a non-boundary amount can be routed using the stated tiers once known, without declaring the entire policy unusable.
- Proposed review: preserve the known tiers and ask for the missing amount. Do not invent a default approver or collapse user-input clarification and policy-owner clarification into one vague refusal.
- Attribution: [FQ-T11](session.md#fq-t11) identifies missing input and all tiers, then adds the 1000-yuan endpoint after earlier exposure to the 3000-yuan discussion. Credit the new analogous boundary check, not first discovery of the already-discussed 3000 issue.

<a id="fin-n01"></a>

## FIN-N01 · Synthetic unsupported process exemption

This is the single assistant-authored **SYNTHETIC counterexample**, supplied during FIN-01 coaching. It is not an application response, model failure observation or eighth QA item.

**Original hypothetical answer — verbatim**

> 出差餐补每日100元，不需要发票，因此也不用填写报销单或走审批流程。

| Part | Source comparison | Proposed judgment |
| --- | --- | --- |
| Daily 100 yuan; no invoice | Supported by [P-03](sources.md#p-03) | Supported facts |
| Therefore no claim form or approval | No such exemption in the meal row; the standard process in [P-01](sources.md#p-01) requires form, supervisor approval and finance review | Unsupported exemption; whole answer does not meet the proposed correctness standard |

The learner's original [FQ-T02](session.md#fq-t02) calls it “部分正确” and explains the unsupported inference. The coach then explicitly states that correct keywords do not make the whole response correct. Keep those attribution steps distinct. This is different from FIN-04's valid partial answer, which retains known facts **without adding an unsupported conclusion**.

## Use limits and next work

- Seven documentary references and one negative example are now drafted. They have not been independently reviewed, executed, encoded into a scorer or accepted as a final benchmark.
- Preserve originals: do not rewrite the policy, `eval_set.json`, Q015, the C17 corpus/denominators, retained scores or historical learner answers. Any later dataset integration needs its own authorization and versioned rationale.
- Original clauses can support more than one meaning-preserving answer. Proposed review should assess fact/condition coverage, source support and bounded uncertainty, rather than demand these exact reference strings or keyword presence alone.
- Separate input gaps, policy gaps/ambiguity, unsupported additions and unnecessary refusal when later defining scoring. Final annotation procedures, numerical criteria, system configuration, budget and execution permission remain unresolved.
- A separate source review can challenge these references, particularly endpoint interpretations and completeness. No comparison with LightRAG or another framework, held-out learning check, user trial or reconstruction starts from this document.
