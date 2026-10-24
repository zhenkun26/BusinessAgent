# FINANCE-QA-01 · Reference-authoring session

[Reference questions and answers](reference-set.md) · [Sources and version binding](sources.md) · [Run index](../README.md)

## Scope and provenance

- Date: 2026-10-23 in `America/New_York`; original UTC timestamps are on 2026-10-24 and remain unchanged. Timestamp gaps are not measured active-learning time.
- Mode: live-project reference authoring after POLICY-QA-01, not a blind assessment or a third historical case. The learner had already discussed Q015, partial answerability and source-only evaluation.
- Authority: the initial save request authorized seven questions, consolidated reference answers, one synthetic counterexample, source/version bindings and the actual learning exchange as local documents. It did not authorize publication or execution. Subsequent explicit authorization covers the selected document publication described below; no old-corpus edit, test, model call, installation, code or reconstruction is included.
- Original authoring branch/revision: `codex/ai-pm-workflow-v1` / `4819a02e760715513142d0b9a20f9cc52fa58d28`. The existing evaluation set and policy fixture are preserved.
- Source: local conversation `01a167b9-4602-7662-acf6-25e2b71611bf`, stored in two log segments identified in the source ledger. C1 lines 1698–1774 supply the start through the half-day question; C2 lines 8–114 supply the current visible continuation. C1's later shorter terminal answer is not part of this selected conversation path. It is not silently substituted for C2's expanded answer.
- Capture: 25 selected message bodies — one start request, eleven substantive learner messages, twelve assistant final messages including consolidation, and one commentary. The save request at C2 line 121 is authority, not a twelfth learner answer. The null Page-context message, environment instructions, private reasoning, tool outputs and unrelated history are excluded.
- Formatting: preserve wording, punctuation and chronological order. Remove terminal newlines and prefix Markdown blockquotes. Omit one machine-readable memory-citation footer from C1 line 1714, explicitly disclosed here; it is not learner/coaching content. No other conversational wording is rewritten. This publication additionally rebinds exactly eight assistant source-link destinations to the identical pinned public policy as declared below; all learner text is unchanged.
- Authorship: Chinese quoted messages are the originals. English headings/analysis are new editorial material. Consolidated Chinese reference answers in the companion document are editor-authored summaries, not replacements for the learner's answers. These documents do not establish model performance, independent reference validation or retained mastery.

<a id="fq-publication"></a>

## Publication view — 2026-10-23

The user subsequently authorized these selected financial-reference and learning documents for the same pure-document publication branch. The original local authoring branch stays at `372fcc367dfae969bd38e88194af010db18ed156`. Its engineering ancestry, complete raw logs and original local transcript record are retained without upload or modification.

Exactly eight source-link destinations inside assistant quotations are adapted to the byte-identical financial-policy fixture at public revision `065bdf7b31ce1fb6f9007a7e8851be36bfc2280f`:

| Original message | Original local destination suffix | Public destination |
| --- | --- | --- |
| C1 line 1714 | `财务报销制度.md:17` | Same file, `#L17` |
| C1 line 1744 | `财务报销制度.md:25` | Same file, `#L25` |
| C1 line 1760 | `财务报销制度.md` | Same whole file |
| C1 line 1774 | `财务报销制度.md:17` | Same file, `#L17` |
| C2 line 32 | `财务报销制度.md:11` | Same file, `#L11` |
| C2 lines 76, 92 and 114 | `财务报销制度.md` (three links) | Same whole file |

The local prefix was `/Users/zhenkun/GitHub/BusinessAgent/enterprise-agent/eval/sample_docs/`. Link labels, surrounding wording, all questions and all eleven substantive learner messages remain unchanged. This is a declared publication transformation, not a claim that the original messages contained public URLs. The original normalized transcript digest below binds the selected message objects **before** these substitutions; publication verification reverses only these eight changes. The one-footer omission remains as originally disclosed.

## Assistance and judgment map

“Independent” is limited to a particular contribution within the supplied question and prior exposure. Questions, synthetic constraints and often a section pointer were supplied by the assistant. This is not independent problem selection or a new blind source audit.

| Turn | Assistance already supplied | Actual contribution / limit |
| --- | --- | --- |
| [FQ-T01](#fq-t01) | Direct-clause question and section 2.1 pointer; Q015 lesson already known | Independently extracts 100 yuan, daily unit from the header and no invoice requirement. No answer-specific correction needed. |
| [FQ-T02](#fq-t02) | Assistant supplies an explicitly SYNTHETIC answer waiving the claim form and approval | Independently separates supported meal facts from the unsupported exemption and cites the standard process. Learner calls it “部分正确”; the subsequent assistant states the whole-answer rejection rule. |
| [FQ-T03](#fq-t03) | A question deliberately uses the 3000-yuan endpoint, with section 2.2 pointer; no overlap is announced in advance | Identifies overlapping/unspecified endpoint rules and rejects an invented priority. Conservative source-only interpretation, not a real policy-owner clarification. |
| [FQ-T04](#fq-t04) | Synthetic salary 4000, loan 9000, settlement 45 days and section 5.1 | Independently checks purpose, computes the 8000 limit and rejects both amount and deadline. Assistant later names the direct-rule/calculation distinction. |
| [FQ-T05](#fq-t05) | Half-day question and section 2.1 pointer; Q015's missing-rule lesson already available | Initial answer adds day-rounding without a source. Preserve it; do not recast this as correct first-attempt transfer. |
| [FQ-T06](#fq-t06) | Assistant explicitly asks for the source of “不满一日按一日计算” | With prompting, acknowledges inference, retains the daily standard/no-invoice facts and leaves half-day payment unresolved. |
| [FQ-T07](#fq-t07) | Emergency scenario states no previous emergency claim this month and points to section 1.2 | Supplies supported conditions but also invents “暂时” and later supervisor ratification. This is a mixed initial answer, not a fully correct reference. |
| [FQ-T08](#fq-t08) | Assistant asks for the source of later supervisor approval | Responds “合理流程闭环”, a design rationale rather than source evidence. The next assistant message explains the distinction and supplies the corrected reference; do not credit that corrected wording to the learner. |
| [FQ-T09](#fq-t09) | Coach has explained unsupported stricter duties, provided the emergency reference, and requested a preventive check | Proposes sentence-by-sentence comparison, separates direct rules/calculation/inference, explicitly rejects both earlier additions and separates suggestions. A learner-authored method within an explicit reflection prompt, not unprompted discovery of the distinction. |
| [FQ-T10](#fq-t10) | Synthetic 800-yuan entertainment/e-invoice task after the checking-method discussion; whole-fixture pointer | Independently combines the claim form, hospitality form, participant list and printed invoice; notes invoice metadata and separates approval from materials. No claim of delayed or unassisted retention. |
| [FQ-T11](#fq-t11) | Approval question omits amount; the 3000 endpoint has already been discussed | Detects missing input, retains all stated tiers and newly identifies the analogous 1000 endpoint. Credit this specific extension, not first discovery of all boundary issues. |
| [FQ-R01](#fq-r01) | Assistant closing table | Consolidation, not another learner answer or a test/approval receipt. |

## Original exchange

**Learner start request — verbatim** · UTC `2026-10-24T02:23:50.090Z` · source `C1` line `1698`

> 接下来带我基于现有财务报销制度，整理第一组能对照原文的问答和参考答案，把 Q015 的经验用进去。还是一次问一个问题，让我先判断，先不运行测试、不写代码、不开始重构。

**Coach commentary — verbatim** · UTC `2026-10-24T02:23:53.866Z` · source `C1` line `1701`

> 我会先核对现有财务制度和 Q015 记录，再从一道能直接对照条款的问题开始，让你先判断。先在对话中整理，不运行测试、写代码或开始重构。

**Coach message — verbatim** · UTC `2026-10-24T02:24:36.149Z` · source `C1` line `1714`

> 我们先在对话中逐题整理，依据限定为现有[财务报销制度](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md#L17)。沿用 Q015 的经验：不补充制度没写的信息，也不遗漏已经明确的内容。
>
> 第一题先练直接查条款：
>
> > **出差期间，餐补的标准和发票要求是什么？**
>
> 请你先写出这道题的参考答案，并附上支持它的原文；我再针对你的标注追问。

<a id="fq-t01"></a>

### FQ-T01

**Learner response — verbatim** · UTC `2026-10-24T02:25:07.665Z` · source `C1` line `1721`

> 我会写：出差期间餐补为每日100元，不需要发票。依据是制度第2.1节差旅费表，表头注明“标准（每日）”，餐补一行写明“100元”和“不需发票”。

**Coach message — verbatim** · UTC `2026-10-24T02:25:39.926Z` · source `C1` line `1728`

> 第一条参考答案可以保留：金额、每日单位和发票要求都有直接依据。你还注意到了表头中的“每日”，没有只摘取金额。
>
> 再看一个**假设回答，并非实际测试结果**：
>
> > 出差餐补每日100元，不需要发票，因此也不用填写报销单或走审批流程。
>
> **你会如何判定这条回答，并用制度原文说明理由？**

<a id="fq-t02"></a>

### FQ-T02

**Learner response — verbatim** · UTC `2026-10-24T02:25:58.902Z` · source `C1` line `1735`

> 我会判为部分正确：每日100元、不需发票有第2.1节的依据，但“不用填报销单或审批”没有依据。第1.1节的标准流程要求填写《费用报销单》、主管审批和财务审核。不需发票只是材料要求上的规定，不能推导出整个报销流程都可以省略。

**Coach message — verbatim** · UTC `2026-10-24T02:26:49.855Z` · source `C1` line `1744`

> 你的判断有原文支持。标注时可以记为：**金额、发票要求正确；免填报销单和免审批的结论无依据。**整条回答不能因为包含正确关键词就计为答对。
>
> 下一题：
>
> > **单次招待费正好为3000元，应由谁审批？**
>
> 请你先依据[制度第2.2节](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md#L25)，写出参考答案并说明原文依据。

<a id="fq-t03"></a>

### FQ-T03

**Learner response — verbatim** · UTC `2026-10-24T02:27:26.186Z` · source `C1` line `1751`

> 我会标为制度存在边界歧义：第2.2节写“单次1000-3000元：部门负责人审批”，同时又写“单次≥3000元：总经理审批”。3000元涉及两条规定的重叠，原文没有明确边界和优先规则。参考答案应列出这两条依据，说明暂时不能唯一确定，需要进一步澄清，不能自行假定哪条优先。

**Coach message — verbatim** · UTC `2026-10-24T02:28:17.936Z` · source `C1` line `1760`

> 这道参考答案可以保留，标为**“条款边界待澄清”**。你既保留了两条规定，也没有自行设定优先级。与 Q015 缺少城市分类依据不同，这里需要澄清已有条款之间的边界。
>
> 下一道拟定题，情境为假设：
>
> > **员工月薪4000元，因公出差申请借款9000元，计划45天后用报销冲抵，是否符合制度中的借款条件？**
>
> 请你先依据[制度第5.1节](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md)，写出参考答案和原文依据。

<a id="fq-t04"></a>

### FQ-T04

**Learner response — verbatim** · UTC `2026-10-24T02:28:46.666Z` · source `C1` line `1767`

> 我会判为不符合：因公出差符合借款用途，但月薪4000元对应的借款上限是8000元，9000元超限；45天后冲抵也超过30天。依据第5.1节“借款金额≤月薪2倍”和“借款需在30天内归还或报销冲抵”。不能因为用途符合，就忽略金额和期限限制。

**Coach message — verbatim** · UTC `2026-10-24T02:29:30.547Z` · source `C1` line `1774`

> 这条答案覆盖了用途、金额和期限，结论有依据。标注时把**原文规则**与**计算结果**分开：“≤月薪2倍”来自制度，“上限8000元”是结合题目条件算出的结果。
>
> 下一道拟定题，情境为假设：
>
> > **员工只出差半天，餐补应该报多少？**
>
> 请你先依据[制度第2.1节](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md#L17)，写出参考答案和原文依据。

<a id="fq-t05"></a>

### FQ-T05

**Learner response — verbatim** · UTC `2026-10-24T02:31:23.333Z` · source `C2` line `8`

> 按日结算，不满一日的按一日计算

**Coach message — verbatim** · UTC `2026-10-24T02:31:50.904Z` · source `C2` line `15`

> 表头的“每日”明确了标准单位；你还加入了“不足一天按一天算”的规则，这需要单独核对依据。
>
> **你能在制度中找到支持“不满一日按一日计算”的具体原文吗？**

<a id="fq-t06"></a>

### FQ-T06

**Learner response — verbatim** · UTC `2026-10-24T02:32:43.919Z` · source `C2` line `25`

> 我找不到这个依据，刚才是自行推断。制度只规定餐补每日100元、不需发票，没有说明不足一天如何计发。参考答案应保留已知标准，再说明仅凭现有制度无法确定半天报多少，需要进一步澄清计发规则。

**Coach message — verbatim** · UTC `2026-10-24T02:33:21.198Z` · source `C2` line `32`

> 这次修订符合原文范围，这题可标为**部分可回答**：已知每日100元、不需发票；半天如何计发仍待澄清。整理学习过程时，要保留初答中的自行推断，以及经追问后的修订。
>
> 下一道假设题：
>
> > **员工本月尚未办理过紧急报销，现在有一笔紧急费用，能否跳过主管审批？**
>
> 请你先依据[制度第1.2节](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md#L11)，写出参考答案和原文依据。

<a id="fq-t07"></a>

### FQ-T07

**Learner response — verbatim** · UTC `2026-10-24T02:34:39.387Z` · source `C2` line `39`

> 我会写：可以暂时跳过主管审批，但需附加说明，直接由财务总监审批，后续主管补批。依据第1.2节，紧急报销每月限1次，题目已说明本月尚未办理，符合次数限制。跳过主管审批不等于免除所有审批，也不能据此省略其他未明确豁免的流程。

**Coach message — verbatim** · UTC `2026-10-24T02:34:58.454Z` · source `C2` line `44`

> 附加说明、财务总监审批和每月一次限制，都有原文支持。现在核对你增加的一个要求：
>
> **制度中的哪句话规定了“跳过主管审批后，仍需主管补批”？**

<a id="fq-t08"></a>

### FQ-T08

**Learner response — verbatim** · UTC `2026-10-24T02:35:16.863Z` · source `C2` line `51`

> 合理流程闭环

**Coach message — verbatim** · UTC `2026-10-24T02:36:10.172Z` · source `C2` line `60`

> “流程闭环”可以是改进建议，但不能作为现行制度的依据。把补批写进参考答案，会新增原文未规定的义务；**更严格的要求也可能是无依据补充。**
>
> 按原文整理的参考答案可以是：
>
> > 本月尚未办理紧急报销，符合每月限1次的条件；需附加说明，可跳过主管审批，直接由财务总监审批。原文未规定后续主管补批。
>
> **结合“半天按一天计算”和“后续主管补批”这两次补充，你会在编写参考答案时增加哪一步检查，避免把合理推测写成制度要求？**

<a id="fq-t09"></a>

### FQ-T09

**Learner response — verbatim** · UTC `2026-10-24T02:36:31.987Z` · source `C2` line `67`

> 我会把参考答案逐句对照原文，区分直接规定、依据明确条件得出的计算，以及自行推断。像8000元上限要写明计算依据；半天取整、后续补批没有原文支持，就不能写成制度要求。缺失规则标为待澄清，流程改进建议单独列出。

**Coach message — verbatim** · UTC `2026-10-24T02:37:25.142Z` · source `C2` line `76`

> 这套逐句核对方法可以保留：原文规定、条件计算、待澄清事项和改进建议分别记录。接下来实际用一次。
>
> 下一道假设题：
>
> > **员工报销一笔800元的招待费，持有电子发票，按照制度应准备哪些报销材料？**
>
> 请你先依据[现有财务报销制度](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md)，写出参考答案，并逐项附上原文依据。

<a id="fq-t10"></a>

### FQ-T10

**Learner response — verbatim** · UTC `2026-10-24T02:42:39.791Z` · source `C2` line `83`

> 我会列出《费用报销单》（第1.1节）、《招待申请单》和参与人员名单（第2.2节），以及打印后附上的电子发票（第3.1节）。发票还需符合第3.2节的抬头、税号及必要信息要求。800元对应主管审批，但审批属于流程要求，不能替代这些材料。

**Coach message — verbatim** · UTC `2026-10-24T02:43:35.504Z` · source `C2` line `92`

> 这道参考答案可以保留：材料清单、电子发票的打印要求、发票信息要求都有对应依据；你也把审批与材料要求分开了。
>
> 本组再补一道假设题，用户只问：
>
> > **我这笔招待费该找谁审批？**
>
> 请你先依据[现有制度](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md)，写出这道题的参考答案。

<a id="fq-t11"></a>

### FQ-T11

**Learner response — verbatim** · UTC `2026-10-24T02:44:10.850Z` · source `C2` line `99`

> 我会先确认这笔招待费的单次金额，不能直接指定审批人。依据第2.2节，≤1000元由主管审批，1000—3000元由部门负责人审批，≥3000元由总经理审批。但1000元和3000元的边界存在歧义，需要澄清。参考答案应保留现有分级规则，同时说明目前缺少金额，暂时无法唯一确定审批人。

<a id="fq-r01"></a>

### FQ-R01

**Coach message — verbatim** · UTC `2026-10-24T02:46:01.593Z` · source `C2` line `114`

> 这题可以保留。你区分了两个缺口：**用户没有提供金额**，以及**制度的金额边界有歧义**；这次还补出了1000元处的同类问题。
>
> 第一组可以先收束为以下 **7道参考题草稿**。下面是对已讨论内容的编辑汇总，依据均来自[项目内的财务报销制度样本](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md)。
>
> | 题目摘要 | 参考答案要点 | 原文依据 |
> |---|---|---|
> | 餐补标准和发票要求 | 每日100元，不需发票。“每日”来自表头。 | 第2.1节 |
> | 招待费恰好3000元，由谁审批 | 列出“1000—3000元：部门负责人”和“≥3000元：总经理”两条规定；说明边界重叠，不能自行指定优先级。 | 第2.2节 |
> | 月薪4000元，借款9000元，45天后冲抵 | 不符合。用途符合；金额上限为4000×2＝8000元，9000元超限；45天超过30天归还或报销冲抵的期限。 | 第5.1节 |
> | 只出差半天，餐补多少 | **部分可回答**：已知每日100元、不需发票；制度未说明不足一天如何计发，无法确定半天金额。 | 第2.1节 |
> | 本月尚未紧急报销，能否跳过主管审批 | 可跳过，但需附加说明，直接由财务总监审批，每月限1次。原文未规定后续主管补批。 | 第1.2节 |
> | 800元招待费，持电子发票，需要哪些材料 | 《费用报销单》《招待申请单》、参与人员名单，以及打印附后的电子发票；发票还须符合抬头、税号和必要信息要求。 | 第1.1、2.2、3.1、3.2节 |
> | 未说明金额的招待费，由谁审批 | **需要澄清输入**：先确认单次金额，同时提供现有三档规则；注明1000元、3000元边界仍待制度澄清，当前不能唯一指定审批人。 | 第2.2节 |
>
> 另保留一条**假设错误回答**：“餐补不需发票，所以不用填报销单或审批。”它包含正确事实和无依据推断，整题不能计为正确。
>
> 学习过程也要保留：**半天取整是在原文追问后修订的；后续补批是在区分制度要求与流程建议后撤回的。**不把修订后的答案冒充初答。
>
> 目前仅在对话中整理；未写文件、运行测试或开始重构。这组草稿尚未用于判断系统表现。

## What this run establishes

SOURCE-OBSERVED: the selected learner answers and coaching occurred. Direct extraction, bounded calculations and cross-clause assembly are visible in the answers. Half-day rounding and later supervisor approval show that plausible additions can reappear despite earlier discussion; both initial answers and the actual assistance remain in this record.

The seven consolidated references and one counterexample are documentary drafts. The counterexample was assistant-authored, never an actual application output. This is not a model test, benchmark result, completed G2 execution approval or framework choice. Existing corpus, scoring, rights and engineering acceptance remain unchanged.

## Further practice — proposed, not started

- Apply the sentence-by-sentence check to fresh clauses without a source pointer or a coach naming the hidden premise; include both unsupported exemptions and unsupported extra obligations.
- Separate missing user input from missing/conflicting policy rules; retain supported facts rather than replacing every limitation with a blanket refusal.
- Make each required point traceable without treating a matching keyword or valid citation ID as semantic correctness. Keep original clauses separate from editor interpretation and calculated results.
- Seek a separate reference review and settle the later scoring/denominator plan before execution. No numeric success threshold, system result or validated learning-effectiveness claim is supplied here.

## Transcript integrity binding

Canonical selected-message objects use keys `source`, `line`, `timestamp`, `role`, `phase`, `text`, in that order. `source` is C1 or C2 as defined in the source ledger. Compact UTF-8 JSON uses `ensure_ascii=False` and separators `,` and `:` after the declared trailing-newline/footer normalization. SHA-256: `e0a98f8bfd2b3cd855a4d332e52a40d6d4171ef16fa740934473364df7030eeb`. This binds only the original selected conversation path before the eight publication link substitutions, not complete raw logs or the generated Markdown file, and is not independent attestation.
