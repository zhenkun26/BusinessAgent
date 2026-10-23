# EXT-01 · Facilitator guide and staged reveal

Spoilers. Open after a real first attempt under the [coaching protocol](../../../workflow/coaching.md). Sources are pinned in [sources](sources.md). The learner can reasonably choose differently from the author if their constraints and evidence justify it.

## Packet A — Process choice

Before revealing A, obtain the learner's target use situation, options, one explicit trade-off, and a validation plan. Ask only for what their answer lacks, one question per turn. Record G1/G2 as SIMULATED where confirmed.

Possible probes, chosen adaptively:

- If the learner starts with document structure: ask what task a user is trying to complete.
- If consistency is the only objective: ask what happens when someone enters halfway through.
- If flexibility is the only objective: ask how a necessary obligation would remain visible.
- If more steps are assumed safer: ask what evidence would show that people can actually follow them.

### Reveal A — Author-reported change

EXT-S1/S2 describe an August 9 plan in which process depth could pass from an upstream skill or be classified independently. EXT-S3 reports that Dean subsequently rejected this coupling: skills recommend a depth, allow user override, and explain omissions when the user chooses less coverage. It also reports independent entry and backward movement through the workflow.

The stated rationale is proportional process and less coupling. The record does not demonstrate improved adoption, completion rates, or business outcomes. Those remain unmeasured in this case.

### Analysis A — Our options and trade-offs

Compare, rather than automatically endorse, these possibilities:

| Proposed option | Benefit | Cost or unresolved risk |
| --- | --- | --- |
| One fixed sequence | Predictable coverage and vocabulary | Small tasks can inherit unnecessary work; midstream entry becomes difficult |
| Mandatory upstream depth | Consistency across stages | Wrong early classification can persist; standalone use needs special handling |
| Local recommendation with explicit override | Context-sensitive entry and user control | Repeated definitions may drift; users may omit material coverage |
| A concise shared contract with independent tasks | Shared vocabulary with lighter navigation | Contract and entry conditions still need maintenance; could recreate coupling if enforced mechanically |

These alternatives are teaching analysis, not a claim that the historical team formally evaluated this exact table. Ask the learner which cost matters most for their selected users, and how that priority could be wrong.

A proposed validation could observe users completing a narrow task and a complex task under alternative interaction designs. Look at completion of necessary decisions, missed obligations, unnecessary work, confusion, and reasons for abandoning steps. Agree on success criteria before observing. Do not equate user satisfaction alone with safe or complete handling.

## Packet B — Green checks and a release question

After discussing A, reveal this setup without its outcome:

> A repository has validation for skill definitions and references. Its generated catalog and distributable packages are separate outputs. A maintainer must decide whether green checks justify presenting the release as coherent to users.

Ask: **“你会先找哪条证据，判断用户拿到的内容和源码是否一致？”** Wait for the learner and a targeted follow-up. Do not immediately name the historical fix.

### Reveal B — Author-reported gap and adjustment

EXT-S3 reports that generated catalog/distribution content could be stale while existing checks passed. It describes adding a separate freshness check based on content rather than ZIP bytes, because regenerated archives carry changing timestamps. The check was kept outside an existing validation call chain that would otherwise block the rebuild needed to repair staleness. The author reports testing with a temporary added skill; we have not rerun it.

### Analysis B — Test the proposed check

Ask the learner to define a failure the existing checks miss and the expected behavior of their new check. A proposed evaluation should include stale output, coherent output, and unchanged content with different packaging timestamps. A useful check detects meaningful drift without creating noise or preventing the repair procedure.

This is a test-design lesson, not a direction to add tools to BusinessAgent. The historical temporary-file cleanup does not authorize deletion here. Describe counterexamples and retain records under current workspace rules.

## Packet C — Limits and decision

Ask the learner to separate these claims: a new check is described; its author reports verification; users benefit from the design; business results improved. Only the first two are supported by this packet, and at different evidence levels.

The upstream customer scenarios are explicitly fictional. Do not use their financial or retention figures as success evidence. Confirm a bounded G3 recommendation as SIMULATED, including what observation would be needed before claiming the process helps real users.

## Transfer — Synthetic, not an upstream event

A small team handles an internal feature retirement, but one contract requires a specific notice period. They ask to use the lightest workflow.

Ask: **“你会怎样减少流程负担，同时保留这项已知义务？什么需要确认，什么可以省？”** Wait before giving feedback. Look for selective simplification rather than either full bureaucracy or removal of every gate. This is an invented scenario, not a claim about the upstream fictional universes or a legal recommendation.

## Retrospective and comparison

Use the [retrospective template](../../../templates/retrospective.md). Compare with BA-01 only after its reveal: both cases contain an attractive surface signal that does not prove the intended outcome. Also ask where the analogy fails: pipeline freshness and probabilistic action correctness require different measurements.

Record whether the learner identifies that distinction without a hint. The authoring assistant's walkthrough is not a learner trial, and no learning-effectiveness result is claimed.
