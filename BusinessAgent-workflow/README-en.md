# AI-PM learning and practice workflow · v1

[简体中文](README.md)

Practice problem definition, trade-offs, validation, and retrospectives using real decision records. Preserve the learner's judgment first, ask a targeted question next, and reveal historical reasoning afterward. Continuing, revising, investigating, and stopping are all legitimate outcomes.

## Start here

Give the assistant this instruction; no installation is needed:

> Coach me through BA-01 using BusinessAgent-workflow/workflow/coaching.md. Initially read only coaching.md, human-gates.md, and cases/businessagent/model-routing/brief.md. Do not read review.md, sources.md, or linked historical outcomes. Present the initial situation and one open question, then wait for my judgment. Do not fill in my answer, write files automatically, or execute experiments.

For `EXT-01`, use `cases/external/process-sizing/brief.md`. The learner has already seen some earlier analysis; record prior exposure honestly and assess transfer through changed scenarios rather than calling the exercise blind.

## Reading route

| Topic | Entry |
| --- | --- |
| Stages, inputs, outputs, and proportional depth | [Lifecycle](workflow/lifecycle.md) |
| Judgment before questions and historical reveal | [Coaching](workflow/coaching.md) |
| Three human gates and execution authority | [Human gates](workflow/human-gates.md) |
| Sources, attribution, dates, and result limits | [Evidence policy](workflow/evidence-policy.md) |
| Two cases and learning objectives | [Case index](cases/index.md) |
| Learning and project-discovery records | [Learning records](runs/README.md) · [Combined retrospective](runs/2026-10-23-retrospective.md) |
| GitHub references and selective adoption | [References](references/repositories.md) |
| Delivery scope, checks, and remaining validation | [Delivery record](workflow/delivery.md) |

Six composable templates: [problem](templates/problem.md), [options](templates/options.md), [experiment](templates/experiment.md), [observations](templates/observations.md), [decision](templates/decision.md), and [retrospective](templates/retrospective.md). A small decision can use one document. Unknowns remain unknown; completing every field is not a gate.

## The two cases

- **BA-01: model routing judgment.** [Start](cases/businessagent/model-routing/brief.md). Practice competing explanations, experiment design, and task-specific decisions. Historical outcomes are in a separate file; do not open it before attempting the exercise.
- **EXT-01: process depth and delivery checks.** [Start](cases/external/process-sizing/brief.md). Practice proportional process, evidence boundaries, and missed checks. Sources are public repository plans and handovers; their fictional customer stories are not commercial evidence.

## Use and records

Start in conversation. Once saving is authorized, create `runs/<date>-<topic>/session.md` containing the case, mode, exposure, original answers, hints, revisions, and G1/G2/G3 confirmations. Add templates only as needed. Do not precreate empty runs or learning profiles, or record AI-written answers as learner achievements.

Authored documents are primarily English. Preserve Chinese entry points, coaching prompts, learner responses, and original Chinese excerpts. This is a manual conversational workflow; answer separation and status checks are not enforced by software.

The 2026-10-23 [BA-01](runs/2026-10-23-ba-01/session.md) and [EXT-01](runs/2026-10-23-ext-01/session.md) runs were saved under subsequent authorization: eighteen original answers, coaching questions, historical reveals, and retrospectives are retained. Specific independently proposed reasoning, prompted extensions, revisions after historical reveal, and synthetic transfer are distinguished. These records contain answers and are not initial packets for a new exercise. Subsequent explicit authorization covers publication of these selected learning records on the documentation-only branch; the full local conversation log remains unpublished.

The later [policy-QA problem-definition and technical-research conversation](runs/2026-10-23-policy-qa-discovery/session.md) was separately authorized for local recording and then explicitly authorized for this documentation-only publication: 21 answers and their exact coaching, with a [problem / unexecuted validation plan](runs/2026-10-23-policy-qa-discovery/problem-and-validation-plan.md), [versioned sources](runs/2026-10-23-policy-qa-discovery/sources.md), and [Q015 analysis](runs/2026-10-23-policy-qa-discovery/q015-analysis.md). It is live-project discovery, not an additional historical case. LightRAG remains an unverified candidate; Q015 is reference-evidence review. No tests or reconstruction were started in this discovery round.

The [first financial-policy reference set](runs/2026-10-23-finance-qa-reference-set/reference-set.md) was first authorized for local documentation and subsequently authorized for this selected document publication: seven questions, reference answers and one synthetic counterexample, with [original answers and coaching](runs/2026-10-23-finance-qa-reference-set/session.md) and [policy version / original clauses](runs/2026-10-23-finance-qa-reference-set/sources.md). Eleven substantive learner messages retain initial answers, unsupported inferences, prompted revisions and method reflection; editorial consolidation does not replace original wording. This is a documentary draft, not a corpus addition or executed test. Publication covers only the selected documents; the full raw logs remain local.

## Current and future boundaries

The initial increment added only workflow documents, templates, two cases, and source indexes in this directory. Subsequent authorization adds the two case-learning records, combined retrospective, policy-QA discovery record and first financial-policy reference set, still as documentation only. Existing BusinessAgent code, documentation, OpenSpec, acceptance conclusions, and unrelated local changes remain untouched.

The publication branch is based on the already-public `main` and adds only 32 documents under `BusinessAgent-workflow`: the initial 21, four earlier learning-record and retrospective documents, four policy-QA discovery documents, and three financial-reference and learning-record documents. Unpublished later case sources and implementation versions remain local-only evidence and are not included in this branch; the ledgers distinguish public material, local material, and the user's account. The original local documentation branch and its engineering history are retained and are not uploaded with this publication.

The user's 2026-10-23 direction is to conduct a future reconstruction in a separate new folder using this workflow without OpenSpec. Its name, location, architecture, and migration plan remain undecided. This increment creates no reconstruction folder, copies no code, and starts no refactor. Existing repository rules remain in place for that project; this directory does not repeal them. The workflow itself has no OpenSpec dependency.

The two case replays, policy-QA discovery and first reference-authoring round now have conversational and documentary records. This supports observations about answers and assistance, not validated retention, system accuracy or workflow benefit. The first references still need separate review and the test plan remains unexecuted. Original-project runtime acceptance and future reconstruction are outside this delivery.
