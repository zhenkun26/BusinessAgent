# BA-01 · Facilitator guide and staged reveal

Spoilers. Read only after a real first attempt under the [coaching protocol](../../../workflow/coaching.md). Source IDs resolve in [sources](sources.md). Historical facts below are AUTHOR-REPORTED unless labeled otherwise. Proposed experiments are our teaching analysis, not experiments credited to the historical team.

## Packet A — Frame and investigate

Before revealing A, capture the learner's problem statement, at least one competing explanation, a provisional option, and a test that could change it. Elicit missing pieces one question per turn; do not assign a multi-field form immediately. Mark G1/G2 as SIMULATED when the learner confirms their proposed problem and experiment.

Adaptive probes:

- If the answer is only "use cloud": ask what user task is suffering and what improvement matters.
- If GPU contention is treated as established: ask for another explanation and an observation distinguishing them; do not name the adapter.
- If the plan changes several things together: ask what a faster result would actually establish.
- If only latency is measured: ask what failure could make a fast response unusable.

### Reveal A — Historical record

BA-S1 reports an initial move toward cloud for lightweight tasks, based on a mistaken GPU-contention diagnosis. Its July 26 note attributes the delay to an OpenAI-compatible Ollama endpoint ignoring the intended thinking-disable setting. It reports local self-evaluation at 44–94 seconds before switching to native ChatOllama with `reasoning=False`, then 0.2–0.3 seconds, compared with 8.7–18.1 seconds for cloud flash. Lightweight routing returned to local-first; heavier reasoning remained cloud-based.

These are historical source reports, not reproduced measurements. Missing raw samples, versions, and controls prevent treating the figures as a general model ranking or a present-day performance promise.

Ask the learner which of their assumptions changed and which did not. A provisional cloud choice could have been reasonable under an urgent latency constraint, provided the uncertainty, cost, and reversal condition were explicit.

### Analysis A — New teaching interpretation

The decision contains two questions: where the delay originates, and which route is best for each task. A faster cloud result alone does not settle the first question. An independently proposed experiment should hold task/prompt conditions stable where possible, compare the relevant adapters/settings, observe effective configuration, and check both latency and task correctness. If effective settings cannot be observed, retain that limitation.

The trade-off is not "local good, cloud bad." Cloud can reduce local constraints while introducing network/provider dependencies and possible spending/data exposure. Local execution can reduce those dependencies while adding hardware and adapter maintenance. The appropriate weighting depends on the user task.

## Packet B — A new failure type

Release after A has been discussed, before showing B's historical choice:

> A lightweight model can return valid JSON but omit an intended action tool, selecting only an information lookup. The existing fallback activates on an error or an empty response. The user asked for an action as well as information.

Ask: **“这个现象改变了你对‘成功’的定义吗？你会先改哪条判断依据？”** Wait for a response and probe once before revealing B. Do not suggest a cloud-first route in the question.

### Reveal B — Historical record

BA-S1's July 28 note reports that local tool selection omitted `send_email_external` while retaining `query_customer`. Nonempty valid JSON bypassed the empty-result fallback. The historical team changed this task to cloud flash first, retaining local preference elsewhere, and reported restored approval creation with 1.2–1.5-second cloud calls.

This does not establish complete action accuracy, recipient correctness, real mail delivery, or a universal cloud advantage. The brief statement about negligible cost has no measured billing basis supplied here.

### Analysis B — New teaching interpretation

Ask the learner to distinguish parsing, intended action selection, parameters, permissions, approval creation, and execution outcome. Each is a separate observable claim. A stronger proposed evaluation includes omissions, wrong identifiers, refusals, provider failures, and ordinary successful requests. A model's syntactically valid output can still fail the task.

Optional later context, after discussing B: the original authoring inspection reports that BA-S3's plan prohibits keyword-created default recipients and business IDs. BA-S3 is LOCAL-ONLY / NOT PUBLISHED and is not available in this publication. Treat this as a bounded account of later local context, not evidence about the public baseline's contract or implementation. If the source is unavailable, acknowledge the gap and skip its verification; BA-S1/S2 still support the historical exercise. This illustrates why lessons should preserve conditions and dates rather than canonize one old implementation.

## Packet C — Critique the narrative

After B, disclose the BA-S2 limitations from the source ledger. Ask the learner to rewrite one performance/correctness claim so it says only what the evidence supports. A good revision labels historical reports and separates action omission from execution or approval bypass. Do not turn our present critique into a defect the historical team is claimed to have found.

G3 is SIMULATED: ask the learner to confirm their bounded recommendation and what remains unproven. An unresolved result is acceptable.

## Transfer — Synthetic, not a BusinessAgent result

The next task is a low-consequence read-only classifier. Raw user text cannot leave the device, and the task has a different tolerated error cost from external actions. No new benchmark is supplied.

Ask: **“你会保留刚才的选择吗？请说明现在最需要补哪条证据。”** Do not provide the route. Look for a changed constraint affecting the decision, a credible non-cloud alternative, and an appropriate validation plan. Do not demand agreement with a predetermined architecture.

## Retrospective

Use the [retrospective template](../../../templates/retrospective.md). Preserve the first answer, prompts, revisions, and transfer response. Evaluate problem clarity, alternative causes, test validity, and bounded conclusions. Neither memorizing the adapter name nor reproducing the historical timings demonstrates PM capability. At initial case authoring, no learner session had occurred. The subsequent [2026-10-23 replay](../../../runs/2026-10-23-ba-01/session.md) records actual responses and qualitative observations; it is not a measured learning-effectiveness result.
