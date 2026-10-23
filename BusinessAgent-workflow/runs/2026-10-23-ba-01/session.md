# BA-01 · Recorded learner session — 2026-10-23

[Learning records](../README.md) · [Cross-case retrospective](../2026-10-23-retrospective.md) · [Case source ledger](../../cases/businessagent/model-routing/sources.md)

## Scope and provenance

- Mode: guided historical replay followed by a SYNTHETIC transfer task. Prior exposure to earlier case analysis was explicitly acknowledged; this was not a blind assessment.
- The initial save was authorized after both exercises. It preserved the real exchange without inventing a fresh learner attempt or authorizing execution, refactoring, publication, or a new folder. Subsequent publication authorization is recorded separately below.
- Underlying conversation log: `01a167b9-4602-7662-acf6-25e2b71611bf`, LOCAL-ONLY / NOT PUBLISHED. Selected user-visible messages below are published under subsequent explicit authorization. Local transcript locator: `rollout-2026-10-23T04-37-28-01a167b9-4602-7662-acf6-25e2b71611bf_01a167e8-6df8-7d53-81c0-e6219c2230ec.jsonl`, message selection from lines 314–480. No public URL for the complete raw log is available.
- Original user-visible wording is retained. Terminal newline removal and Markdown blockquote prefixes are applied; this publication additionally rebinds exactly three assistant source-link destinations as documented below. All learner-answer text is unchanged. Source line numbers and UTC timestamps locate each message. Tool output, private reasoning, environment instructions, and unrelated conversation are excluded.
- Ten learner answers, eleven assistant final messages including the closing retrospective, three assistant commentary messages, and the learner's start request are retained. Three historical source links inside assistant quotations point to the identical section in the pinned public counterpart; the original local record retains the original destinations.
- Chinese quotes are the original conversation. All new analysis is labeled outside the quotes. An assistant paraphrase or suggested formulation inside a quoted retrospective is still the assistant's writing, not a learner answer.

## Publication view — 2026-10-23

Subsequent user authorization covers these selected learning records on the documentation-only branch. The original local branch and its complete transcript record remain unchanged. The full JSONL log, private reasoning, and engineering commits are not included.

Only source-link destinations in the quoted assistant messages were adapted for public navigation: BA-T06 and BA-R01's original local product-document line 342 now link to public line 339; BA-T10's original local line 349 now links to public line 346. All bind section 4.2.2 at public revision `065bdf7b31ce1fb6f9007a7e8851be36bfc2280f`; its text equals the original local section. Labels, surrounding wording, questions, and all ten learner answers are unchanged. This is an explicit publication transformation, not a claim that the original message contained these public URLs.

## Assistance map

“Independently proposed” means the learner supplied that reasoning without the coach already supplying that specific answer. It does not mean unprompted topic selection, no previous exposure, or demonstrated mastery. Capability labels follow the [coaching protocol](../../workflow/coaching.md).

| Turn | Stage / assistance already supplied | Learner contribution and bounded assessment |
| --- | --- | --- |
| [BA-T01](#ba-t01) | A0; brief already names slowness, GPU suspicion, and local/cloud options | Independently distinguishes observed latency from an unconfirmed cause and defers solution choice. Does not independently discover the options supplied in the brief. |
| [BA-T02](#ba-t02) | A1; coach explicitly requests user-impact evidence | With prompting: proposes blocking, end-to-end waiting, abandonment, resubmission, and complaints as observable signals. None were measured. |
| [BA-T03](#ba-t03) | Probe explicitly requests competing causes | With prompting on breadth; independently supplies model/input/output/queue hypotheses and a timing breakdown. |
| [BA-T04](#ba-t04) | Coach asks for one small controlled experiment and mentions input/output effects | Independently constructs the specific single-variable context-length comparison, fixed conditions, repetition, and a bounded interpretation. The experiment topic was prompted. |
| [BA-T05](#ba-t05) | Coach explicitly introduces speed-versus-quality risk | With prompting: adds reference answers, paired quality comparison, missed/wrong judgments, information retention, and rejection of a harmful speedup. |
| [BA-T06](#ba-t06) | Historical reveal A explicitly explains the ignored parameter and adapter change | After reveal: prioritizes checking effective request behavior and comparing adapters. This is an evidence-informed revision, not independent root-cause discovery. |
| [BA-T07](#ba-t07) | Packet B supplies valid JSON with an omitted send action; coach asks what success means | With the failure exposed, specifies action coverage, parameters, ordering, and approval. Selection, approval creation, and execution need distinct receipts. |
| [BA-T08](#ba-t08) | Coach asks for an improvement and says changing models is not yet established | Independently proposes an action-completeness checker before deciding whether to replace the model. Historical cloud-first selection has not yet been revealed. |
| [BA-T09](#ba-t09) | Coach explicitly raises correlated omissions by the checker and selector | With prompting: independently designs human action labels, injected wrong/incomplete outputs, and sampling of accepted outputs. The need to validate the checker was supplied. |
| [BA-T10](#ba-t10) | Reveal B; SYNTHETIC low-risk read-only task, no raw text leaving device, no benchmark | Demonstrated in transfer: excludes cloud, proposes rules/local model comparison, lighter checks, bounded retry burden, and no winner without data. Constraints were supplied; response was learner-authored. |
| [BA-R01](#ba-r01) | Assistant closing synthesis | Feedback and proposed next practice, not an additional learner response or proof of implementation. |

## Original exchange

**Learner start request — verbatim** · UTC `2026-10-23T10:08:15.103Z` · local transcript line `314`

> 先带我走一遍 BA-01 模型路由案例，一次问一个问题，让我先判断，再针对我的回答追问，最后对照真实决策过程复盘。

**Coach commentary — verbatim** · UTC `2026-10-23T10:08:23.136Z` · local transcript line `317`

> 我们按“你先判断、我再追问”的顺序来，最后再对照真实记录复盘。你前面已经接触过部分结果，这轮会重点看判断依据，而不是能否记住历史答案。


<a id="ba-t01"></a>

### BA-T01

**Coach message — verbatim** · UTC `2026-10-23T10:08:39.429Z` · local transcript line `326`

> 先回到这个决策点：
>
> 团队正在做一个业务助手，包含请求分类、知识检索、数据分析和操作执行，不同环节使用本地或云端模型。
>
> 现在，一个频繁调用的**本地评估环节耗时数十秒**。团队怀疑是 GPU 资源争用，正在考虑把更多轻量任务迁到云端。但手头没有完整的对照测试，真正的原因还没确认。
>
> 你是负责这个阶段的 PM。
>
> **你会把团队现在需要解决的问题定义成什么？先用自己的话说，不用套模板。**

**Learner response — verbatim** · UTC `2026-10-23T11:36:33.183Z` · local transcript line `333`

> 我觉得现在的问题是本地评估太慢，可能影响用户体验，但还不能确定是 GPU 的问题。应该先找出慢的原因，再决定是优化本地还是迁到云端。


<a id="ba-t02"></a>

### BA-T02

**Coach message — verbatim** · UTC `2026-10-23T11:36:53.179Z` · local transcript line `338`

> 你已经把“评估慢”这个现象与“GPU 争用”这个原因假设分开，也保留了优化本地和迁云两种选择。
>
> 目前还需要弄清楚的是：你说的“可能影响用户体验”，实际影响有多大。
>
> **你会收集什么证据，判断这段耗时是否已经严重到需要优先解决？**

**Learner response — verbatim** · UTC `2026-10-23T11:37:20.741Z` · local transcript line `345`

> 我会先看这个评估环节是否阻塞用户拿到结果，再看整体响应时间，以及用户有没有中途退出、重复提交或反馈等待太久。如果用户每次都要等几十秒才能继续操作，我觉得就应该优先解决。


<a id="ba-t03"></a>

### BA-T03

**Coach message — verbatim** · UTC `2026-10-23T11:37:34.096Z` · local transcript line `350`

> 你把“某个环节慢”连接到了用户能否继续完成任务，并提出了阻塞、退出、重复提交等可观察信号。这让优先级判断有了依据。
>
> 接下来进入原因判断。GPU 争用目前只是一个候选解释。
>
> **除了 GPU 争用，你还会考虑哪些可能导致这个评估环节变慢的原因？**

**Learner response — verbatim** · UTC `2026-10-23T11:43:00.193Z` · local transcript line `357`

> 除了 GPU 争用，也可能是模型本身推理慢、输入上下文太长、生成内容太多，或者请求在排队。我会先把耗时拆成排队、模型加载、推理和结果处理几段，看看时间主要花在哪里。


<a id="ba-t04"></a>

### BA-T04

**Coach message — verbatim** · UTC `2026-10-23T11:43:19.753Z` · local transcript line `362`

> 你提出了几种竞争解释，也给出了分段计时的定位办法。这里要注意：发现时间花在“推理”上，还不能直接断定模型本身慢，输入长度和生成量也可能影响这一段。
>
> **如果现在只能做一个小型对照实验，你会怎样设计它，来验证你最怀疑的那个原因？**

**Learner response — verbatim** · UTC `2026-10-23T11:54:27.866Z` · local transcript line `369`

> 我会先验证是不是输入太长。用同一个模型和同一个评估任务，只改变上下文长度，其他参数保持不变，分别重复跑几次，比较推理耗时。如果短输入明显更快，就说明上下文长度可能是重要因素；如果差别不大，再查其他原因。


<a id="ba-t05"></a>

### BA-T05

**Coach message — verbatim** · UTC `2026-10-23T11:54:51.830Z` · local transcript line `374`

> 这个实验有明确的变量控制和重复测量，你也把结论限定为“可能是重要因素”，保留了其他解释。
>
> 还需要检查一个取舍：缩短上下文可能提速，也可能删掉评估所需的信息。
>
> **你会怎样验证提速没有以评估质量下降为代价？**

**Learner response — verbatim** · UTC `2026-10-23T11:56:45.849Z` · local transcript line `381`

> 我会准备一组有参考答案的评估样本，分别用长、短上下文测试，同时比较耗时和评估结果，重点看有没有漏判、误判。缩短时尽量保留任务所需的关键信息。如果只是更快但结果明显变差，就不能直接采用。

**Coach commentary — verbatim** · UTC `2026-10-23T11:57:11.286Z` · local transcript line `386`

> 你已经把速度和质量放进同一组验证，还明确了不能直接采用的情况。现在可以对照第一轮真实决策，看看历史记录能给你的排查方案补充什么。


<a id="ba-t06"></a>

### BA-T06

**Coach message — verbatim** · UTC `2026-10-23T11:57:30.796Z` · local transcript line `396`

> 真实记录里，团队经历了这样一次调整：
>
> 1. **最初判断**：怀疑 GPU 争用，把轻量任务迁到云端。
> 2. **后来发现**：调用接口没有让“关闭思考”的参数实际生效，模型仍在生成思考内容。
> 3. **调整后**：改用原生调用方式，记录中的本地自评耗时从 **44–94 秒降到 0.2–0.3 秒**，于是轻量任务恢复本地优先，较重的推理任务仍留在云端。[原始记录](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/docs/20-product/产品文档.md#L339)
>
> 这些是历史文档报告的结果，缺少完整原始测试数据，不能直接当成今天的性能承诺。
>
> 你的实验能够检验上下文长度的影响。这段历史又补充了一个排查角度：**我们以为已经固定的参数，实际上有没有生效。**
>
> **看到这段过程后，你会怎样调整自己刚才的排查方案？**

**Learner response — verbatim** · UTC `2026-10-23T11:57:55.389Z` · local transcript line `403`

> 我会先确认参数在实际请求中有没有生效，比如关闭思考后是否仍在生成思考内容，而不只看配置文件。再用同一个模型、同一组输入对比不同调用方式，同时检查耗时和结果质量，排除接口或配置问题后，再继续验证上下文长度的影响。


<a id="ba-t07"></a>

### BA-T07

**Coach message — verbatim** · UTC `2026-10-23T11:58:12.766Z` · local transcript line `408`

> 你把检查推进到了实际运行行为，并保留了速度和质量的对照。这样，“配置保持不变”才有了可核验的含义。
>
> 进入第二个决策点：用户要求“查询客户信息，并发送邮件”，本地模型返回了**合法、非空的 JSON，但只选择查询，漏掉了发送动作**。原来的回退机制只有在报错或返回空结果时才启用，因此没有触发。
>
> **在这个场景里，你会怎样定义工具选择这一步真正的“成功”？**

**Learner response — verbatim** · UTC `2026-10-23T11:59:08.103Z` · local transcript line `415`

> 我觉得不能只看 JSON 合法、非空，还要看是否完整覆盖用户的意图。这个例子里应该选对查询和发送两个动作，参数和执行顺序也要正确；如果发送需要审批，就应进入审批流程。漏掉动作或选错工具，都应该算工具选择失败。


<a id="ba-t08"></a>

### BA-T08

**Coach message — verbatim** · UTC `2026-10-23T11:59:31.595Z` · local transcript line `420`

> 你的成功标准已经落到用户任务上了。这里可以分层验收：工具选择检查动作、参数和依赖；审批是否建立、动作是否执行，则需要后续链路的证据。
>
> 现在还不能仅凭这个失败，就认定必须换模型。
>
> **你会优先尝试哪一种改进方案，来降低“格式正确但漏掉动作”的风险？请说明选择它的理由。**

**Learner response — verbatim** · UTC `2026-10-23T12:01:03.741Z` · local transcript line `427`

> 我会先增加动作完整性校验，把用户要求的动作和模型选出的工具逐项对照，发现遗漏就重试或触发回退，而不只检查 JSON。这样能先补上失败识别的缺口，再用包含多动作请求的测试样本，判断是否还需要换模型。


<a id="ba-t09"></a>

### BA-T09

**Coach message — verbatim** · UTC `2026-10-23T12:01:15.551Z` · local transcript line `432`

> 你优先补上了“识别失败”的缺口，并准备通过测试再决定是否换模型。这个方案的代价是多了一层校验，而校验器本身也可能漏掉用户意图。
>
> **你会怎样验证这层校验，避免它和工具选择模型漏掉同一个动作，却仍把结果判为“完整”？**

**Learner response — verbatim** · UTC `2026-10-23T12:02:13.786Z` · local transcript line `439`

> 我会用人工标注的动作清单作为独立参考，准备多动作和容易遗漏步骤的样本，再故意给出缺动作或选错工具的结果，检查校验器能否识别。同时抽查被判为“完整”的结果，避免两个模型漏掉同一个动作却互相认可。

**Coach commentary — verbatim** · UTC `2026-10-23T12:02:40.011Z` · local transcript line `444`

> 你为校验器引入了人工参照、故意构造的错误结果，以及对“通过项”的抽查。这些能帮助检验校验器本身，而不只是让两个模型互相认可。现在对照第二轮真实选择，再做一个变化情境练习。


<a id="ba-t10"></a>

### BA-T10

**Coach message — verbatim** · UTC `2026-10-23T12:03:02.708Z` · local transcript line `454`

> 历史团队选择了另一条路径：**仅把工具选择环节改为云端优先，其他轻量任务仍保持本地优先。** 文档报告审批建单恢复，云端调用约 1.2–1.5 秒。[原始记录](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/docs/20-product/产品文档.md#L346)
>
> 对照你的方案：
>
> | 路径 | 优先解决什么 | 还需要验证什么 |
> |---|---|---|
> | 历史选择：调整模型路由 | 降低已观察到的动作遗漏 | 更广样本中的正确率、参数错误及成本 |
> | 你的选择：增加完整性校验 | 识别“格式正确但任务不完整” | 校验器漏判、误判，以及新增延迟和重试成本 |
>
> 两条路径可以组合。现有历史记录只支持“报告了建单恢复”，不足以证明所有动作都正确，更不能证明真实邮件已经发送。
>
> 最后做一个**虚构的迁移练习**：任务变成低风险的只读文本分类，原始文本不得离开设备，目前没有新的测试数据。
>
> **面对这些变化，你会怎样调整刚才的方案？**

**Learner response — verbatim** · UTC `2026-10-23T12:03:34.208Z` · local transcript line `461`

> 我会先排除云端方案，比较本地小模型和规则分类。低风险只读任务可以采用更轻量的校验和抽查，不确定时让用户确认，避免反复重试增加延迟。再用人工标注的样本比较准确率和耗时，没有测试数据前，不直接认定哪个方案最好。


<a id="ba-r01"></a>

### BA-R01

**Coach message — verbatim** · UTC `2026-10-23T12:04:17.083Z` · local transcript line `468`

> 这轮 BA-01 已走完。你的迁移回答体现了一个关键能力：**约束和任务风险变化后，你会重新选择方案，并保留“尚无数据，暂不下结论”的状态。**
>
> 回看真实决策过程：
>
> - **第一次调整**：团队把慢归因于 GPU，迁到云端；后来发现调用参数未实际生效，修正后恢复轻量任务本地优先。这里值得学的是：确认运行事实，并为原选择保留改判空间。
> - **第二次调整**：本地模型出现“合法 JSON 但漏动作”，团队仅将工具选择改为云端优先。你的方案则先补完整性校验。两者可以组合，但历史记录没有提供足够证据，证明哪种组合整体最优。[真实记录](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/docs/20-product/产品文档.md#L339)
>
> **这次你的思考过程，可以这样复盘：**
>
> | 能力 | 本轮实际表现 | 提示的作用 |
> |---|---|---|
> | 问题定义 | 一开始就区分了“评估慢”和“GPU 争用假设”；随后把问题落实到用户等待、退出和重复提交 | 用户影响是在追问后具体化的 |
> | 决策取舍 | 提出先补失败识别，再判断是否换模型；迁移时主动比较规则与本地模型，并减少重试 | 方案由你提出，没有照搬历史选择 |
> | 验证设计 | 主动提出单变量对照、重复测量；进一步加入质量检查、人工标注、错误样本和通过项抽查 | 质量代价与校验器可靠性是在提示后补齐的 |
> | 复盘迁移 | 看过历史后，增加“参数实际生效”的检查；新情境中根据隐私约束和风险重新裁剪方案 | 已展示情境迁移，但还不是实际项目中的验证结果 |
>
> 你最初的思路是：
>
> > 先找出慢的原因，再决定优化本地还是迁到云端。
>
> 经过这一轮，它变得更完整了：
>
> > **先确认用户受到什么影响，再定位原因；用能区分解释的实验，同时观察收益和代价；根据任务与约束作选择，并说明什么证据会让自己改判。**
>
> 还有一个值得继续打磨的点：**“不确定时让用户确认”也有成本。** 后续实验应把确认频率和用户被打断的负担纳入观察，避免只是把模型的判断成本转给用户。准确率、延迟与确认负担的可接受范围，也应在实验前约定。
>
> 目前能确认的是，你在这次对话中展示了上述推理过程；实际实验尚未执行，因此还不能判断方案效果。这一轮的价值，是你已经能解释自己的选择、识别验证漏洞，并在条件变化时调整判断。

## Sources and historical comparison

The [original case ledger](../../cases/businessagent/model-routing/sources.md) preserves its local authoring revision. Availability below is explicit; a local hash is not a public source.

| Source | Binding / availability | What was actually used in this replay |
| --- | --- | --- |
| BA-S1 | PUBLIC: [product document, section 4.2.2](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/docs/20-product/产品文档.md). Local counterpart at `edc5c58e5783e5c3035d89a035917cae35cb3ef1`, lines 342–352; public section lines 339–349. | Reveal A at BA-T06 and reveal B at BA-T10. Dates July 26/28 are reported within the retrospective document, not first-publication dates. |
| BA-S2 | PUBLIC: [speech notes, P21–P22](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/interview/产品介绍网页/演讲提示词.md). | Background source in the case ledger; a separate learner critique of the speech was not conducted. Repetition of the performance story is not independent corroboration. |
| BA-S3 / BA-S4 | LOCAL-ONLY / NOT PUBLISHED: `docs/50-engineering/planner-tool-trust-boundary.md` and `docs/50-engineering/delivery-status.md` at the local authoring revision. | Background only. Not presented as a new learner packet here; no new runtime acceptance claim or public availability is inferred. |
| BA-U1 | LOCAL-ONLY user testimony in this conversation before the exercise. | Taro led early product/main engineering; the learner led middle/later packaging, closeout, launch preparation, and testing. The replay's “you are the PM” is role-play, not historical authorship attribution. |

SOURCE-OBSERVED: BA-S1 section 4.2.2 is byte-identical at the public and local bindings; the whole files differ. Public BA-S1 SHA-256: `7f81faffc369255739890267dc498503885cde9e6cdd315bc0320d4e7f726731`; local BA-S1: `d154cbab5a7248e523825d7f17cfcf11dcf2ea616b162fc0b5c51b8cec4778a6`. BA-S2 is identical at both bindings: `f2e7970814769d99c5a979123063afadd23983c3ca6280afa398bcc06137697c`.

AUTHOR-REPORTED: the July 26 note says an ignored thinking-disable setting was diagnosed, a native adapter was used, and local self-evaluation fell from 44–94 seconds to 0.2–0.3 seconds; lightweight tasks returned to local-first. The July 28 note reports a valid-but-incomplete tool proposal, a cloud-first exception for tool selection, approval creation restored, and 1.2–1.5-second calls. Raw datasets, controlled reproduction, current rankings, full action accuracy, and cost measurements are absent.

PROPOSED: BA-T08/T09's completeness checker and independent human labels are the learner's proposed route, not a historical implementation credited to the team. Neither this proposal nor the historical routing change is established as the best overall solution. Approval creation does not establish real email delivery. The speech's cost-reduction and approval-bypass claims were not validated by this replay.

## Simulated gates and actual limits

| Gate | Evidence from the learner | Status in this replay |
| --- | --- | --- |
| G1 — Problem | BA-T01/T02: user-impact framing and unresolved cause | SIMULATED: a proposed problem, no measured user impact or real stakeholder approval. |
| G2 — Validation | BA-T04/T05/T09: proposed contrasts and counterexamples | SIMULATED / incomplete for execution: sample size, operational thresholds, budget, and allowed live actions were not agreed. No experiments ran. |
| G3 — Decision | BA-T06 revises diagnosis; BA-T08 proposes checking; BA-T10 withholds a winner | SIMULATED provisional recommendations. No operational decision to change routing, add a checker, spend, upload, or refactor. |

The actual dialogue did not conduct the facilitator guide's separate speech-claim critique or explicit operational gate confirmations. Those steps are not backfilled as completed. This recording contains no benchmark, observed user behavior, or learning-retention result.

## Follow-up practice — proposed, not completed

- **Before a quality prompt:** independently define success, failure costs, and acceptable latency/quality ranges for a new task. BA-T05's quality dimension was coach-supplied.
- **Before a historical diagnosis:** list observable effective settings and a distinguishing test. BA-T06's adapter diagnosis was revealed, not discovered by the learner.
- **Checker limits:** include wrong parameters/identifiers and missing prerequisites, examine both false accepts and false rejects, and keep a held-out set separate from checker tuning. BA-T09 covered omitted/wrong tools, not every semantic failure.
- **Human-confirmation burden:** define how to observe confirmation frequency, task interruption, and unnecessary retries before recommending escalation. The coach introduced this cost only in BA-R01; no later learner response demonstrates it yet.
- **Bounded source claims:** rewrite one speech claim from BA-S2 using only its supporting evidence. This was not attempted in the original replay.

See the [cross-case practice plan](../2026-10-23-retrospective.md) for a small next exercise; none is started by saving this record.

## Transcript integrity binding

The selected public-facing message objects use keys `line`, `timestamp`, `role`, `phase`, `text`, in that order; canonical JSON uses UTF-8, `ensure_ascii=False`, separators `,` and `:`, and the normalization described above. SHA-256: `db5e3274120b8029c1979d922eb4a6d8d787dd9f26355b6cd85f86f4bc09c11f`. This binds the original local selected-message objects before the three publication link substitutions, not the published Markdown or the entire evolving log. The original record remains at local-only commit `c322935c0678ff3ae9af856b20cb1214c21fcdcb`; the publication transformation is separately declared above. It is not an independent attestation.
