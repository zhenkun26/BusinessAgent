# Decision lifecycle

Version: v1 · Designed on 2026-10-23 · Manual, documentation-only workflow.

## Unit of work

Use one decision unit: one question whose answer changes what happens next. State the user outcome, current alternatives, constraints, and the cost of being wrong. "Build an AI platform" is too broad; "Should this action require a confirmation step?" can be a decision unit.

Start with a short session header: ID, owner, learning or live-project mode, prior exposure, decision question, scope, authorized actions, current stage, and unresolved questions. Conversation is sufficient unless saving has been authorized.

## Stages

| Stage | Inputs | Learner / assistant work | Output and exit condition |
| --- | --- | --- | --- |
| 0. Establish context | Source records, task, constraints | Learner clarifies role and intent; assistant distinguishes source statements, inference, and unknowns | Source IDs, dates, attribution, and information cutoff; unknowns explicit |
| 1. Frame the problem | Context and current user journey | Learner states the problem before assistant critique; compare symptoms and causes | [Problem](../templates/problem.md): user, situation, current alternative, consequence, desired outcome, non-goals; G1 |
| 2. Compare options | Problem and constraints | Learner proposes alternatives; assistant tests omissions and opposing evidence | [Options](../templates/options.md): include doing nothing, and non-AI alternatives where credible; explicit costs and reversal conditions |
| 3. Design validation | Decision-critical uncertainty | Learner predicts results and names disconfirming evidence; assistant checks whether the experiment separates explanations | [Experiment](../templates/experiment.md): comparison, measurement, denominator, failure rules, limits; G2 |
| 4. Observe | Confirmed plan and authorized environment | Collect raw results without changing the original hypothesis; record deviations | [Observations](../templates/observations.md): source/versions, results, failures, missing data; failed setup is not product evidence |
| 5. Decide | Plan plus observations | Learner interprets first; assistant challenges causal attribution and generalization | [Decision](../templates/decision.md): adopt, revise, investigate, stop, or defer; G3 |
| 6. Reflect and transfer | Original prediction, hints, revised decision | Explain what changed and test the reasoning in a different situation | [Retrospective](../templates/retrospective.md): learning, counterexample, limits, next retrieval trigger |
| 7. Handoff, if authorized | Confirmed decision and scope | Translate into implementation boundaries and observable acceptance scenarios | A concise handoff linking the decision, exclusions, dependencies, and unresolved evidence; no automatic implementation |

The assistant does not fill every stage in one response. Apply the [coaching turn protocol](coaching.md). Confirmation rules are in [human gates](human-gates.md).

## Branches and re-entry

- Weak problem evidence: return to context or problem definition; do not invent customers or demand.
- Several plausible causes: compare them before selecting a fix. A reversible diagnostic can test a hypothesis without proving it already true.
- Invalid measurement or missing environment: repair the experiment or mark BLOCKED. Do not count that as a failed product hypothesis.
- Disconfirming evidence: update the decision with a new dated entry; preserve the original reasoning.
- Sufficient evidence to stop: record the reason and revisit trigger. A stopped idea need not produce a PRD or backlog.
- At handoff: a product recommendation does not authorize code, spending, uploads, or release.

## Right-sized use

For a narrow reversible question, use a single note with problem, alternatives, evidence, decision, and lesson. Link existing evidence instead of copying it. For uncertain or consequential decisions, expand only the weak parts into separate templates. The learner may choose a lighter route; name the specific uncertainty left uncovered.

Do not require numerical prioritization when inputs are guesses. A ranked list with reasons and uncertainty is better than fabricated scores. Define success criteria from the task's consequences and constraints; no universal accuracy percentage or sample count is prescribed here.

## Learning and real-project modes

Case replay uses a reconstructed information cutoff. Historical sources may be retrospective; this does not prove what someone knew minute by minute. Record exposure and use a synthetic transfer problem when the outcome is already known.

Live-project work uses current evidence and real authorization. Simulated users, AI opinions, and generated data can help explore a hypothesis but cannot establish actual demand, willingness to pay, or production reliability.

## Future engineering handoff

The future reconstruction will use this lightweight process in a separate folder without OpenSpec, as directed by the user. Prefer a sibling location outside the existing BusinessAgent tree, with its own scoped instructions, so the old project's OpenSpec rules are not accidentally inherited. The actual location is a future kickoff decision. A handoff can be a section of the decision note: approved behavior, observable scenarios, non-goals, data/permission boundaries, migration constraints, verification plan, and unresolved risks. Add implementation tasks only when implementation is authorized.

This increment does not create that folder, decide its architecture, alter existing BusinessAgent rules, or transfer its acceptance claims. The current user's documentation-only scope overrides the existing repository's general OpenSpec document workflow for this new package; existing OpenSpec files are untouched.
