# BA-01 and EXT-01 · Cross-case retrospective — 2026-10-23

[Record index](README.md) · [BA-01 original exchange](2026-10-23-ba-01/session.md) · [EXT-01 original exchange](2026-10-23-ext-01/session.md)

## What this record can establish

SOURCE-OBSERVED: eighteen learner answers and the associated coaching/reveals were recorded in this conversation. The answers below remain in their session files; this document is newly authored analysis, not a replacement transcript. Both exercises were guided and the learner had prior exposure to case material. No study of learning effectiveness, blind test, delayed recall test, live product experiment, or independent reproduction was performed.

“Independently proposed” is local to the specific idea: the coach may have selected the topic. “With prompting” does not make the learner's concrete plan an AI-authored answer. The distinction is whether the coach supplied the idea, the dimension to consider, or merely an open question.

## Observed reasoning and assistance

| Area | Learner evidence | Assistance and bounded interpretation |
| --- | --- | --- |
| Separating symptoms and causes | [BA-T01](2026-10-23-ba-01/session.md#ba-t01): “但还不能确定是 GPU 的问题” | Independently rejects causal certainty within a brief that already supplied the GPU hypothesis and local/cloud options. Does not establish independent discovery of those options. |
| Framing a user task | [BA-T02](2026-10-23-ba-01/session.md#ba-t02) adds blocking, abandonment, and resubmission; [EXT-T01](2026-10-23-ext-01/session.md#ext-t01) starts with affected users and readiness beyond a notice | BA's user-impact dimension was explicitly prompted. EXT's first answer supplies the selected small-feature scenario and balances omitted preparation against unnecessary process. No actual user behavior was measured. |
| Alternatives and causal testing | [BA-T03/T04](2026-10-23-ba-01/session.md#ba-t03): competing causes, timing segments, fixed-model/input-task comparison with varied context length and repeated runs | Coach requests alternatives and then an experiment. The concrete comparison and repetitions are learner-authored; the learning topic was not unprompted. |
| Protecting quality while optimizing | [BA-T05](2026-10-23-ba-01/session.md#ba-t05): reference answers, missed/wrong judgments, rejection of speedups with quality loss | Prompted extension: the coach explicitly introduced the quality trade-off. It must not be counted as present in the earlier latency-only proposal. |
| Revising a diagnosis | [BA-T06](2026-10-23-ba-01/session.md#ba-t06): inspect effective request behavior, compare adapters | After reveal: the ignored setting was supplied by the historical record. The learner explains how to incorporate it, not how they independently discovered it. |
| Proposing a different intervention | [BA-T08](2026-10-23-ba-01/session.md#ba-t08): action-completeness checking before choosing a replacement model | Independently proposed specific intervention after an open improvement question; historical cloud-first tool selection was still withheld. The coach had already cautioned against assuming a model change was necessary. |
| Challenging a checker | [BA-T09](2026-10-23-ba-01/session.md#ba-t09): human action labels, deliberately incomplete/wrong outputs, sampling accepted outputs | Coach supplied the correlated-error concern. The concrete independent reference and negative controls were proposed by the learner. They were not executed. |
| Risk-based process trimming | [EXT-T02](2026-10-23-ext-01/session.md#ext-t02): critical dependencies, verified alternatives, migration, commitments | Prompted extension: “few users” was challenged by the coach. The learner supplied concrete dependency/impact criteria and conditional decisions. |
| Testing workflow usefulness | [EXT-T03](2026-10-23-ext-01/session.md#ext-t03): full/simplified comparisons, task time, friction, predefined necessary preparation | The coach requested lower burden without omissions. The experiment structure and rejection condition came from the learner; effectiveness remains unknown. |
| Following evidence to the delivery boundary | [EXT-T04/T05](2026-10-23-ext-01/session.md#ext-t04): inspect actual artifacts and their source revision; introduce unbuilt source changes, expect failure, regenerate and expect success | The brief explicitly asks about source/artifact consistency, and the next prompt requests a counterexample. Concrete inspections and the failure–repair sequence are learner-authored, not evidence of spontaneous discovery or an executed check. |
| Limiting claims | [EXT-T06](2026-10-23-ext-01/session.md#ext-t06) separates recorded design, reported checks, independent reproduction, and user/business outcomes | The distinction was requested after the coach had described evidence limits. Demonstrated with prompting, not an independent audit of raw receipts. |
| Adapting to new constraints | [BA-T10](2026-10-23-ba-01/session.md#ba-t10): local/rules, reduced retry burden, no winner without data; [EXT-T07](2026-10-23-ext-01/session.md#ext-t07): notice deadline, recipients, owner, proof, impact-based simplification | Demonstrated in synthetic transfer. The no-egress and notice obligations were provided. The learner's responses are their own; no live action or legal determination was authorized. |
| Knowing where an analogy fails | [EXT-T08](2026-10-23-ext-01/session.md#ext-t08): semantic intent correctness versus source/artifact consistency | Coach requested a comparison but did not name this distinction. The learner articulated it after both historical reveals. Timestamp noise had already been disclosed and is not an independently discovered edge case. |

## Historical decisions and the learner's alternatives

BA-01's [source ledger](2026-10-23-ba-01/session.md#sources-and-historical-comparison) binds the local retrospective and public counterpart. AUTHOR-REPORTED: a July 26 adapter/setting correction changed lightweight routing back to local-first; a July 28 valid-but-incomplete tool proposal led to a cloud-first exception for tool selection. These are two task-specific adjustments, not proof of one universally superior model route. The learner's completeness checker is PROPOSED; it must not be credited to that historical team. Individual ownership of each old decision is not established by the learner's role-play.

EXT-01's [source ledger](../cases/external/process-sizing/sources.md) binds the August 9 plan and August 10 handover at one upstream revision. AUTHOR-REPORTED: the initial depth-propagation design was changed to local recommendations, user override, visible omitted coverage, and independent entry; separately, generated artifacts were found outside existing checks and a new check was described. SOURCE-OBSERVED: the handover lists membership/count/package-coverage checks and content-level rather than ZIP-byte comparison. This is not a demonstrated guarantee that every payload byte semantically matches source. The learner's user trial and full regenerate-and-recheck experiment remain PROPOSED.

INFERENCE: independent workflow entry can reduce unnecessary prerequisites while increasing the burden of keeping duplicated definitions consistent. This is our trade-off analysis grounded in the described design; no adoption or measured maintenance-cost result was supplied.

The shared lesson is to test the result the user needs rather than infer it from a convenient passing signal. The limit of that analogy is equally important: exact artifact comparisons can be deterministic within a defined scope, while intended-action correctness needs a defensible semantic reference and representative cases. Neither approach alone establishes user value or production readiness.

## Next practice — ordered proposals, not started

| Priority | Practice prompt / setup | Why it is next | Evidence to look for before considering it demonstrated |
| --- | --- | --- | --- |
| 1 | Given a new small latency problem, ask only for an investigation plan; withhold the quality reminder and outcome | BA-T05 added quality after a direct hint | Learner independently includes user impact, credible causes, a distinguishing test, quality/failure costs, and conditions that would change the choice. Do not grade agreement with a preset architecture. |
| 2 | Before choosing retry, fallback, or human confirmation, define observable acceptance criteria and what counts in the denominator | BA-R01 introduced confirmation burden; no learner response tested that lesson | A proposed plan includes latency distribution, task correctness, false accepts/rejects, timeout/retry treatment, and confirmation frequency/interruption cost. Any numeric limits need task-specific justification, not invented universal thresholds. |
| 3 | Design a fair trial of full and simplified workflows on matched cases | EXT-T03 proposes a useful contrast but does not control participant familiarity, order, or case difficulty | Necessary outcomes derive from actual dependencies/known obligations rather than every step in the full workflow; the plan addresses confounders and includes both low- and high-impact situations. |
| 4 | Specify delivery-check counterexamples for a missing new skill, an existing skill with stale content, an obsolete extra artifact, and unchanged content with changed packaging metadata | EXT-T05 gives the main stale-artifact counterexample; timestamps and call-chain placement were revealed later | State expected failure/pass, exact check scope, and a repair path that remains runnable. Do not claim membership/count checks establish payload equality. No implementation is authorized by this prompt. |
| 5 | Rewrite one BA speech claim using only the evidence available, then revisit one lesson after a delay in a new scenario | BA's separate speech-claim critique and delayed reuse were not performed | Preserve attribution, historical dates, raw-data limits, and distinctions between selection, approval creation, execution, and user benefit. Record whether the later decision actually changes; do not prefill success. |

These are practice priorities, not a mandatory five-stage workflow. Start one exercise only when requested; give one question at a time, withhold its answer, and record the exact assistance again. No new code, experiment execution, service call, or BusinessAgent reconstruction is implied.

## Coaching retrospective

The exchanges show actual learner responses before each historical reveal and preserve the learner's alternative to the historical route. They also reveal opportunities to improve coaching:

- BA used several probes before reveal A; future sessions should ask only about consequential gaps rather than turn every case into a long fixed checklist.
- EXT included one commentary that announced a historical reveal before the validation-plan answer was obtained; the reveal itself remained withheld until afterward. Future progress messages should match the actual stage.
- Quoted closing feedback sometimes compresses prompted reasoning into fluent summaries. The assistance tables above are more specific; the original feedback is preserved, not silently rewritten.

Completed: two guided conversations and their documentation. Not yet demonstrated: retained learning without hints, independent live investigation, measured workflow benefit, or successful implementation. These limits do not erase the reasoning visible in the answers.
