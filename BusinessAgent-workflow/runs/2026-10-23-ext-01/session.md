# EXT-01 learning session — Process sizing and missing delivery checks

## Record scope and authority

- Case: [EXT-01 brief](../../cases/external/process-sizing/brief.md), [facilitator guide](../../cases/external/process-sizing/review.md), and [source ledger](../../cases/external/process-sizing/sources.md).
- Session date: 2026-10-23. Exact UTC timestamps and source line numbers below come from the local conversation message records; no missing time is inferred.
- Mode: learner-first case replay, one question at a time, followed by historical comparison and synthetic transfer. Prior exposure to the case package or its outcomes is possible; this was not a blind assessment.
- Capture basis: a scoped extraction of the local conversation message records, restricted to `response_item` / `message`, learner text, and assistant `commentary` or `final_answer` text. It contains the start request, all eight learner answers, all nine assistant final messages, and four assistant progress comments. No reasoning, tool output, environment injection, or complete raw log is copied. The transcript preserves original wording, Markdown, and links; only trailing newlines are removed. Structural labels and English analysis are editor additions, not conversation text.
- Authorization: the user requested saving both case-learning processes as documentation under `BusinessAgent-workflow`. That initial save authorization did not authorize experiments, upstream execution, dependency installation, publication, or reconstruction. Subsequent explicit authorization covers publication of this selected learning record; the other exclusions remain. Existing BusinessAgent implementation remains outside scope.
- G1/G2/G3 below are `SIMULATED`. No case answer creates operational permission or experimental evidence. No global memory or learner profile is created by this record.

## Local conversation source

- Raw source log status: `LOCAL-ONLY / NOT PUBLISHED`; there is no public URL for the full log. The selected user-visible transcript below is published under subsequent explicit authorization.
- Session ID: `01a167b9-4602-7662-acf6-25e2b71611bf`.
- Source basename: `rollout-2026-10-23T04-37-28-01a167b9-4602-7662-acf6-25e2b71611bf_01a167e8-6df8-7d53-81c0-e6219c2230ec.jsonl`.
- Scoped source interval: JSONL lines 481–637. The documentation request begins afterward and is authority for this record, not part of the exercise.
- Each source locator below refers to this basename and gives its original one-based line and UTC timestamp. The raw local conversation file is retained outside this documentation package.

## Reading the assistance labels

`Independently proposed reasoning` means a specific idea was supplied by the learner rather than already supplied in that question. It does not mean the topic was unprompted, the learner had no prior exposure, or the idea has been tested. `Prompted extension` means the assistant directed attention to a dimension before the learner developed it. `After historical reveal` identifies answers made with the disclosed historical information available. `Synthetic transfer` identifies an invented changed scenario rather than an upstream event.

The original assistant feedback is retained as dialogue, including statements of encouragement. The evidence assessment later in this file is deliberately narrower than any broad conversational praise. A0 is the initial answer; subsequent A1–A7 labels index later attempts, not corrected replacements for A0.

## Original dialogue

<a id="ext-start"></a>
### EXT-START — Learner request

Local source line `481` · `2026-10-23T12:06:41.602Z` · role `user`.

**Learner — original start request**

接下来带我走一遍 EXT-01 流程裁剪与验证遗漏案例，还是一次问一个问题，让我先判断，再针对我的回答追问，最后对照真实记录复盘。

<a id="ext-t01"></a>
### EXT-T01 — BRIEF → A0: Define the problem

Assistance available: the initial packet already named retirement preparation, varied task sizes, three process depths, and the absence of observed user trials. No later historical outcome was revealed in this turn.

Local source line `484` · `2026-10-23T12:06:46.084Z` · role `assistant` · phase `commentary`.

**Assistant — original commentary**

我先核对 EXT-01 的案例简报和练习规则，再从第一个判断开始；真实记录等你作答后逐步展开。

Local source line `495` · `2026-10-23T12:07:04.377Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

我们先回到方案评审时，只看当时已知的信息。

一个公开的 PM 技能库，原来主要帮助使用者撰写**产品下线通知**。现在计划把支持范围扩展到：判断是否具备下线条件、内部准备、相关方协调，以及对外沟通。

使用场景差异很大：有人只是停用一个小功能，也有人要下线整个产品。方案因此提出三种流程深度：可以沿用前一步选好的深度，也可以在单独使用某个技能时重新判断。设计者希望整套指导保持一致，但目前没有真实用户走完这套流程的观察记录。

**你认为，这套流程首先应该帮助使用者解决什么问题？请选一个你认为最重要的使用情境来说明。**

Local source line `502` · `2026-10-23T12:07:37.306Z` · role `user`.

**Learner — original answer A0**

我觉得这套流程首先要帮助负责人弄清下线会影响谁、需要做哪些准备，避免只发通知却遗漏用户迁移或内部协调。我会先关注小功能下线：既要确认有没有用户依赖它、哪些步骤不能省，也要避免为了一个小改动走完整套复杂流程。

**Editor annotation:** The learner selected a small-feature retirement and proposed checking user dependency and migration omissions. The brief had already introduced preparation and the contrast between small and large retirements; do not credit discovery of those dimensions as unprompted. The chosen priority and articulation of the coverage-versus-burden trade-off were the learner's reasoning within that brief.

<a id="ext-t02"></a>
### EXT-T02 — PROBE → A1: Decide what can be omitted

Assistance label: `Prompted extension`, before historical reveal.

Local source line `507` · `2026-10-23T12:07:49.902Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

你把问题从“把通知写好”推进到了“让下线准备完整”，同时考虑了小功能承担复杂流程的成本。

这里还需要一个裁剪依据：**功能小，不一定意味着下线影响小。**

假设负责人说：“这个功能用的人很少，发个通知就可以下线。”**你会收集什么信息，判断哪些准备步骤可以省、哪些必须保留？**

Local source line `514` · `2026-10-23T12:08:43.794Z` · role `user`.

**Learner — original answer A1**

我会先看剩下的用户是谁、是否依赖它完成关键任务、有没有替代方案，以及下线是否涉及数据迁移、对外承诺或其他团队的系统。使用人数少不代表影响小。如果没有关键依赖、替代方案也验证可用，可以简化协调；如果会让用户无法继续工作，就必须保留迁移和确认步骤。

**Editor annotation:** The assistant explicitly supplied the distinction between small size and small impact, so the learner's repetition of that distinction is assisted. The specific criteria—critical tasks, verified alternatives, data migration, external commitments, and other-team dependencies—and the conditional simplification rule were supplied by the learner in response to the probe.

<a id="ext-t03"></a>
### EXT-T03 — PROBE → A2: Propose a user trial

Assistance label: `Prompted extension`, before historical reveal. The requested comparison already included reduced burden and retained preparation coverage.

Local source line `517` · `2026-10-23T12:08:46.594Z` · role `assistant` · phase `commentary`.

**Assistant — original commentary**

你已经把裁剪依据落到了依赖、替代方案和影响上。我先核对对应的历史记录，再展开这一阶段的真实决策。

Local source line `527` · `2026-10-23T12:09:01.958Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

你的裁剪依据已经比较明确：**看依赖和后果，而不是只看使用人数**；“替代方案验证可用”也比“有替代方案”多了一层证据要求。

现在还需要验证：负责人实际使用这套流程时，能否识别这些情况，并据此保留必要步骤。

**你会怎样做一个小规模验证，判断简化后的流程是否既减少了负担，又没有漏掉关键准备？**

Local source line `534` · `2026-10-23T12:09:31.828Z` · role `user`.

**Learner — original answer A2**

我会选几个影响不同的小功能下线案例，让几位负责人分别试用完整和简化流程，比较完成时间、卡住的地方和遗漏的准备事项。提前根据案例列出必须保留的步骤，再检查他们的结果。如果只是更快，却漏掉迁移或对外承诺，就需要调整，不能直接推广。

**Editor annotation:** The learner constructed a full-versus-simplified comparison, selected differing case impacts, and proposed defining necessary steps before checking results. These are specific design contributions within a prompted validation task. The joint concern for effort and omissions had already been named by the assistant. This is a `PROPOSED` experiment; there are no participants, observations, acceptance thresholds, or execution results in this session.

<a id="ext-t04"></a>
### EXT-T04 — REVEAL A → Packet B → A3: Inspect delivered artifacts

Assistance labels: `After historical reveal` for process-depth decisions; a new delivery-evidence packet and targeted consistency question are supplied before the answer. The historical delivery fix has not yet been revealed.

Local source line `539` · `2026-10-23T12:09:42.519Z` · role `assistant` · phase `commentary`.

**Assistant — original commentary**

你把“更快”和“准备完整”放进了同一次验证，并提前定义了不能遗漏的事项。接下来我会对照原始交接记录，展开流程设计的调整，再进入“检查通过是否足以交付”的问题。

Local source line `557` · `2026-10-23T12:10:19.995Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

你的验证方案同时观察了时间、使用障碍和必要事项的遗漏，并提前设定了判断依据。它可以检验“流程更轻是否仍然够用”。

现在展开这一阶段的真实记录：

- **原计划**：流程深度可以从上游步骤传下来；单独使用某个技能时，再自行判断。[8 月 9 日方案](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/docs/maintenance/2026-08-09-eol-suite-plan.md)
- **后续调整**：据交接记录，Dean 拒绝了这种依赖关系。每个技能自行推荐深度，让用户选择或中途调整；选择更轻的流程时，明确说明哪些事项将不被覆盖。各技能也允许独立进入、回到前面的阶段。[8 月 10 日交接记录](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/10AUG26.md#where-we-deviated-from-the-plan-and-why)

你强调的是**凭影响决定哪些准备不能省**；作者进一步处理了**用户如何选择和调整流程**。这种设计增加了灵活性，也留下了用户可能删减过度的问题。你的试用方案可以帮助检验这一点，但原记录没有提供真实用户完成率或遗漏率的对照结果。

接下来进入交付阶段：项目已有检查覆盖技能定义和引用关系，检查结果均通过；但供用户浏览的技能目录，以及下载安装的分发包，是另外生成的产物。

**你会先找哪条证据，判断用户实际拿到的内容与这次修改后的源码是否一致？**

Local source line `564` · `2026-10-23T12:10:41.739Z` · role `user`.

**Learner — original answer A3**

我会先查看用户实际下载的分发包和浏览的目录，选这次新增或修改的技能，核对是否包含它、内容是否与对应源码一致，再确认产物是基于哪个提交生成的。源码检查通过只能说明检查范围内没发现问题，不能证明用户拿到的内容已经更新。

**Editor annotation:** The prompt explicitly identified the generated catalog, downloadable package, and source-to-delivery consistency question. Do not label those as independently discovered check targets. The learner added concrete membership/content checks for changed skills and commit provenance. No artifact was actually downloaded or compared in this exercise.

<a id="ext-t05"></a>
### EXT-T05 — PROBE → A4: Design a counterexample and repair check

Assistance label: `Prompted extension`; the assistant explicitly requested deliberate errors and expected check behavior. Historical delivery-check details remained unrevealed.

Local source line `569` · `2026-10-23T12:10:57.870Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

你把验收对象放到了用户实际接触的目录和分发包上，也注意到了产物对应的提交。这让“源码正确”和“交付内容正确”有了各自的证据。

接下来需要验证这项一致性检查本身是否可靠。

**假设要把这项核对变成每次发布的固定检查，你会故意制造什么错误，并期待检查给出什么结果，来证明它能发现原有源码检查遗漏的问题？**

Local source line `576` · `2026-10-23T12:13:15.632Z` · role `user`.

**Learner — original answer A4**

我会在源码里新增或修改一个技能，但故意不更新目录和分发包。预期原有源码检查仍能通过，而新的一致性检查必须报错，指出缺失或过期的内容。重新生成产物后再检查，应该恢复通过。

**Editor annotation:** Counterexample testing itself was prompted. The learner supplied the specific stale-output mutation, differentiated old/new check expectations, requested actionable errors, and added the regeneration-to-pass step. That last step is part of the learner's proposed test, not an upstream run observed here. No source mutation, generation, check execution, or cleanup took place.

<a id="ext-t06"></a>
### EXT-T06 — REVEAL B → A5: Bound the report to available evidence

Assistance labels: `After historical reveal` and `Prompted extension`. The assistant supplies timestamp noise, repair-path placement, and the limitation on independent reproduction before asking for a report.

Local source line `581` · `2026-10-23T12:13:29.751Z` · role `assistant` · phase `commentary`.

**Assistant — original commentary**

你把“故意制造不一致”和“修复后恢复通过”连成了一条验证链。我会对照原始记录，展开当时补检查时遇到的两个细节。

Local source line `593` · `2026-10-23T12:13:58.709Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

你的反例能够直接区分：**源码检查通过，是否意味着交付产物也已更新。**“重新生成后恢复通过”还验证了修复路径。

真实记录中确实出现过这个缺口：原有检查通过，但目录和分发产物仍然过期。作者随后增加了专门检查，并处理了两个细节：

- **比较有意义的内容，避免只比较 ZIP 文件字节。**重新打包会改变时间戳，字节不同未必代表内容错误。
- **检查的位置不能阻止修复。**生成分发包的命令会调用原有校验；如果把新检查塞进去，就可能因为“旧产物过期”而阻止生成新产物。因此，它被安排为独立检查步骤。

作者报告，用临时新增技能触发了四项具体报错，恢复原状态后检查重新通过。我们没有独立复跑，也不能把这段记录等同于你提出的完整“重新生成并验证”实验。[原始交接记录](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/10AUG26.md#the-ci-hole-closed)

**如果现在要向团队汇报这次流程与检查的改动，你会怎样表述已有证据支持的结论，以及尚不能声称的效果？**

Local source line `600` · `2026-10-23T12:14:20.465Z` · role `user`.

**Learner — original answer A5**

我会说，根据记录，流程增加了按情境调整的能力，检查也补充了对目录和分发产物的覆盖。作者报告反例能触发报错，但我们还没有独立复跑完整修复流程。现在不能认定用户完成得更快、遗漏更少或业务效果更好，这些还需要真实用户试用和对照数据。

**Editor annotation:** The answer demonstrates bounded reporting after those evidence distinctions were explicitly taught. It is not independent discovery of the upstream limitation. The opening assistant sentence about the learner's repair path uses result-like wording; it is preserved verbatim, but the proposed repair test was not executed and supplies no PASS evidence. The final retrospective correctly retains this distinction.

<a id="ext-t07"></a>
### EXT-T07 — SYNTHETIC TRANSFER → A6: Keep a known obligation

Assistance label: `Synthetic transfer` after historical reveal. The prompt explicitly supplies both the desire for a lightweight process and a confirmed notice obligation; identifying that obligation is not an independent learner discovery.

Local source line `605` · `2026-10-23T12:14:32.076Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

你把三种证据分开了：记录描述的设计变化、作者报告的检查结果，以及尚未验证的用户和业务效果。这个结论保留了改动的价值，也没有扩大证据范围。

最后做一个**虚构的迁移练习**：

一个小团队准备下线内部功能，希望采用最轻的流程。但已确认存在一项合同义务：必须提前一段约定时间通知使用方。

**你会怎样裁剪这次下线流程，在减少工作量的同时确保这项义务得到落实？**

Local source line `612` · `2026-10-23T12:16:54.519Z` · role `user`.

**Learner — original answer A6**

我会保留通知期限、通知对象、责任人和通知凭证，把下线日期安排在约定通知期之后。其他步骤按实际影响裁剪：没有数据迁移或跨团队依赖的，就不做完整协调，用一张简短清单确认必要事项完成。流程可以简化，但不能因为是内部小功能就省掉已知的合同义务。

**Editor annotation:** The learner operationalized the supplied obligation with ownership, recipients, schedule, and evidence, and conditionally reduced unrelated coordination. This is `demonstrated in transfer`, with the constraint itself provided. No real contract was reviewed, no legal conclusion was made, and no notice or retirement was authorized.

<a id="ext-t08"></a>
### EXT-T08 — CROSS-CASE REFLECTION → A7: Distinguish validation methods

Assistance label: prompted cross-case comparison after both cases' reveals. The assistant supplies the two failure examples but does not name the semantic-versus-deterministic distinction in this question.

Local source line `617` · `2026-10-23T12:17:18.047Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

你把已知义务落实到了期限、对象、责任人和凭证，同时按实际依赖裁剪其他工作。这体现了“保留必要结果、减少实现负担”的判断。

最后把两个案例放在一起复盘：

- **BA-01**：模型输出合法 JSON，却漏掉用户要求的动作。
- **EXT-01**：源码检查通过，用户拿到的目录或分发包却可能没有更新。

**这两类问题在设计验证方法时，你认为最重要的区别是什么？**

Local source line `624` · `2026-10-23T12:18:04.977Z` · role `user`.

**Learner — original answer A7**

我觉得 BA-01 要验证模型选出的动作是否完整符合用户意图，需要人工标注、多样化样本和误判分析，格式检查不够。EXT-01 主要验证源码与交付产物是否一致，可以比较版本、文件清单和实际内容，同时排除打包时间戳这类无关差异。前者偏语义正确性，后者更适合确定性的自动检查。

**Editor annotation:** The learner articulated the central distinction without that label being supplied in this question. Its ingredients were already available from the two coached cases, including timestamp noise from EXT-T06 and human reference samples from BA-01. Record this as a reasoned synthesis after teaching, not an unexposed independent assessment. Deterministic delivery comparison also does not establish that the source content or user-facing workflow is good.

<a id="ext-t09"></a>
### EXT-T09 — REFLECT: Original assistant retrospective

No further learner answer followed this retrospective before the user authorized documentation. This assistant synthesis is not a learner response, approval, or additional experiment result.

Local source line `631` · `2026-10-23T12:18:55.983Z` · role `assistant` · phase `final_answer`.

**Assistant — original message**

EXT-01 这一轮可以收束了。你最后的区分很准确：**BA-01 需要判断动作是否符合用户意图；EXT-01 的产物一致性可以更多依靠确定性检查。**两者都要检查用户最终得到的结果，但不能照搬同一套验证方法。

对照真实记录，决策经历了三步：

1. **8 月 9 日：先追求流程一致性。**原方案允许从上游传递流程深度，单独使用时再自行判断。[原始方案](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/docs/maintenance/2026-08-09-eol-suite-plan.md)
2. **8 月 10 日：调整为用户可选择的独立技能。**技能推荐深度，允许调整，并说明简化后未覆盖的事项；支持中途进入和回到前面的阶段。作者接受了各技能重复定义规则的维护成本，以减少步骤之间的依赖。[设计调整记录](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/10AUG26.md#where-we-deviated-from-the-plan-and-why)
3. **随后补齐交付检查。**发现原检查未覆盖目录和分发产物后，增加专门检查，同时避免时间戳误报，以及检查阻止重新生成产物的问题。作者报告了反例验证，但我们没有独立复跑。[验证遗漏与修复记录](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/10AUG26.md#the-ci-hole-closed)

你的判断过程与这些记录可以这样对照：

| 环节 | 你在本轮展示的判断 |
|---|---|
| 问题定义 | 首轮就把目标从“发通知”推进到“完成下线准备”，并选择小功能下线作为具体情境。 |
| 决策取舍 | 追问后明确用关键依赖、替代方案、迁移和承诺决定裁剪；没有把人数少直接当成影响小。 |
| 验证设计 | 在验证问题的提示下，你自己提出完整与简化流程的对照、预先确定必要事项，以及“制造过期产物→报错→重新生成→通过”的验证链。 |
| 复盘与迁移 | 你区分了作者报告和实际效果；在虚构情境中保留已知义务，并在跨案例比较中说出了语义验证与确定性检查的区别。 |

**你提出的用户试用方案，是对原记录中证据缺口的补充。**它还没有执行，不能写成作者已经验证了流程更快、更完整。

下一次值得补强的是对照实验的公平性：负责人熟练程度、案例难度和试用顺序，都可能让简化流程显得更快。把这些因素控制好，才能更有把握地判断改善究竟来自哪里。

这轮最值得带走的判断是：**裁剪流程时，先明确必须完成的结果；设计检查时，让“结果没有达成”的情况确实能够触发失败。**

## Provenance and claim boundaries

The historical packet comes from public records pinned to `deanpeters/Product-Manager-Skills` commit `cfcb697f14b8891d8b3ec43c16c3547df3e70e13`, inspected for the case on 2026-10-23. Its commit timestamp is 2026-10-16T01:51:11Z. August 9 and August 10 are dates reported in the documents; this reconstruction does not assert the first publication time or recover a verbatim upstream design meeting.

| Source | Where used | Supported claim and limit |
| --- | --- | --- |
| [EXT-S1 — August 9 handover](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/09AUG26.md) | Background and chronology | Author-reported plan approval and research; not an independent user study. |
| [EXT-S2 — August 9 plan](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/docs/maintenance/2026-08-09-eol-suite-plan.md) | EXT-T01, EXT-T04, EXT-T09 | Planned depth propagation, standalone classification, and verification. A plan is not execution evidence. |
| [EXT-S3 — August 10 handover](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/10AUG26.md) | EXT-T04, EXT-T06, EXT-T09 | Author-reported changes, stale artifacts, check placement, content comparison, and counterexample behavior. No independent reproduction is claimed. |
| [EXT-S4 — License](https://github.com/deanpeters/Product-Manager-Skills/blob/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/LICENSE) | Source-use boundary | Upstream is marked CC BY-NC-SA 4.0. Links and original educational analysis do not grant rights to redistribute all upstream materials. |
| This saved conversation, EXT-T01–EXT-T09 | Learner and assistant quotations | Direct record of what was said in the exercise. It proves neither implementation nor user/business outcomes. |

The upstream fictional customer scenarios are not real customer evidence. This record does not copy private training decks or upstream skill implementations. The English annotations and comparison criteria are editorial teaching analysis, not additional statements by Dean or the learner.

| Claim type | Application in this session |
| --- | --- |
| `SOURCE-OBSERVED` | The cited public documents contain the described plan and retrospective accounts, as scoped by the case source ledger. |
| `AUTHOR-REPORTED` | Upstream plan changes, initially passing checks despite stale outputs, the later counterexample checks, and reported restored checking behavior. |
| `PROPOSED` | Learner's full-versus-simplified user trial and stale-output-to-regeneration test chain. Neither was executed. |
| `SYNTHETIC` | Internal-feature retirement with an already-known notice obligation in EXT-T07. |
| `INFERENCE` | Teaching comparisons, risks of over-simplification, and capability observations based on the quoted answers and assistance history. |
| `UNKNOWN` | Real workflow completion/omission rates, comparative business outcomes, independent upstream test reproduction, and durable improvement in the learner's future work. |

The original EXT-T09 statement that the author accepted repeated-definition maintenance cost is our `INFERENCE` about the trade-off in the recorded choice to inline rules; it is not a directly quoted author cost assessment. The public handover describes content-level checking rather than ZIP-byte equality, but its listed checks cover catalog membership/count, per-skill ZIP presence/no orphans, pack presence, and CATALOG mentions. That is not proof of exhaustive file-by-file payload equality with current source. The learner’s requested content comparison is a proposed broader verification need.

The timestamp-noise and check-placement details were revealed by the assistant in EXT-T06. They must not be attributed to the learner as discoveries in EXT-T05. The learner's desired regeneration-to-pass test must not be silently substituted for the author's reported temporary-skill test and restoration procedure.

## Simulated human gates

No formal operational gate approval was requested or recorded during the conversation. This table maps the available reasoning to the workflow gates without inventing approvals.

| Gate | Mode / date / proposed owner | Reasoning on record | Status and unresolved conditions |
| --- | --- | --- | --- |
| G1 — Problem | `SIMULATED`; recorded 2026-10-23; learner acting as hypothetical reviewer | EXT-T01/T02: small-feature retirement, identify dependent users and necessary preparation, reduce unnecessary work. | Problem framing articulated; no real owner, customer demand, scope approval, or retirement is established. |
| G2 — Validation | `SIMULATED`; recorded 2026-10-23; learner acting as hypothetical reviewer | EXT-T03: compare full and simplified workflows with necessary steps defined beforehand. EXT-T05: stale output should fail and regenerated coherent output should pass. | Plans proposed; acceptance ranges, fair allocation/order, budget, data/environment permissions, and execution observations are absent. |
| G3 — Decision | `SIMULATED`; recorded 2026-10-23; learner acting as hypothetical reviewer | EXT-T06: report design/check coverage and author-reported counterexamples, withhold user/business claims. EXT-T07: preserve the supplied obligation while simplifying unrelated work. | Bounded recommendations only; no real adoption, release, reconstruction, or operational approval. |

## Learning observations with assistance accounted for

| Capability | Evidence | Assessment and limit |
| --- | --- | --- |
| Define a concrete user problem | A0: “我会先关注小功能下线” and “确认有没有用户依赖它”. | `Demonstrated independently` within a brief that already supplied retirement preparation and varied scope. The learner selected a situation and stated its trade-off; the general preparation theme was not an unprompted discovery. |
| Size process by consequences | A1 specifies critical tasks, verified alternatives, migration, commitments, and other-team dependencies. | `Demonstrated with prompting`. The assistant explicitly challenged the size/impact shortcut before these criteria were supplied. |
| Design a comparison before implementation | A2 compares full and simplified workflows and predefines required steps. | `Demonstrated with prompting`. The assistant asked for validation of effort and omissions; concrete trial mechanics were learner-authored. Fair assignment, order effects, sample adequacy, and decision thresholds remain unresolved. |
| Check what the user actually receives | A3 adds membership/content checks and the generating commit. | `Demonstrated with prompting`. The assistant named the catalog/package and consistency target; the learner operationalized them. No actual artifact inspection occurred. |
| Test a check with failure and repair conditions | A4 describes leaving outputs stale, expected errors, and regeneration restoring a pass. | `Demonstrated with prompting`. The request for a counterexample came from the assistant; the specific test chain came from the learner. Only a proposed experiment is evidenced. |
| Keep claims within evidence | A5 distinguishes recorded changes, author-reported checks, independent reproduction, and user/business effects. | `Demonstrated with prompting`, after explicit evidence-limit teaching in the reveal. No independent source audit by the learner is established. |
| Transfer to a constrained situation | A6 includes recipients, owner, notice timing, proof, and a minimal checklist. | `Demonstrated in transfer`. The known obligation was supplied in the fictional prompt; the learner supplied its operational handling. |
| Compare different verification problems | A7 distinguishes semantic correctness from deterministic source/artifact consistency. | Reasoned synthesis in a prompted cross-case comparison after teaching. The distinction label was learner-supplied in that turn; the examples and timestamp caveat were already known. No blind or durable mastery claim is supported. |

## Follow-up practice, not started

These are proposed future exercises, not approved engineering tasks or newly collected evidence. Future coaching should again ask one question at a time and preserve the answer before revealing an example.

1. **Fair comparisons.** EXT-T03 proposes full-versus-simplified trials but does not address skill differences, case difficulty, order, or carry-over learning. In a changed scenario, ask the learner to design the allocation and order before offering counterbalancing examples. Observe whether they independently identify competing explanations for a faster result.
2. **Decision criteria before results.** The learner names omissions that would block promotion, but not how much extra time, uncertainty, or partial completion would change the decision. Ask for an explicit adopt/revise/defer rule tied to the chosen users and consequences; do not impose arbitrary numerical thresholds.
3. **False positives and repairability.** EXT-T05 proposes a meaningful failure and repair test. Timestamp-only differences and a check that prevents rebuilding were supplied later by the assistant. Use a fresh artifact type and ask for both false-positive cases and a repair path before teaching these failure modes again.
4. **Sufficiency of deterministic checks.** EXT-T08 correctly distinguishes artifact consistency from semantic selection. A fresh case should ask what a perfectly synchronized but incorrect source would still fail to prove. This tests whether the learner separates delivery integrity from product usefulness without being given that distinction in advance.
5. **Evidence gathering beyond a retrospective.** EXT-T06 states the reporting boundary after a reveal. A future source exercise can ask which concrete receipt, user observation, or reproducible run would reduce a chosen uncertainty. Reporting a limitation and obtaining the missing evidence are separate capabilities.

No exercise above has been run. This session supplies dialogue evidence of reasoning with its recorded assistance; it supplies no measured learning gain, user trial, release acceptance, or reconstruction authorization.
