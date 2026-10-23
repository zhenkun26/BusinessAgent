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
| GitHub references and selective adoption | [References](references/repositories.md) |
| Delivery scope, checks, and remaining validation | [Delivery record](workflow/delivery.md) |

Six composable templates: [problem](templates/problem.md), [options](templates/options.md), [experiment](templates/experiment.md), [observations](templates/observations.md), [decision](templates/decision.md), and [retrospective](templates/retrospective.md). A small decision can use one document. Unknowns remain unknown; completing every field is not a gate.

## The two cases

- **BA-01: model routing judgment.** [Start](cases/businessagent/model-routing/brief.md). Practice competing explanations, experiment design, and task-specific decisions. Historical outcomes are in a separate file; do not open it before attempting the exercise.
- **EXT-01: process depth and delivery checks.** [Start](cases/external/process-sizing/brief.md). Practice proportional process, evidence boundaries, and missed checks. Sources are public repository plans and handovers; their fictional customer stories are not commercial evidence.

## Use and records

Start in conversation. Once saving is authorized, create `runs/<date>-<topic>/session.md` containing the case, mode, exposure, original answers, hints, revisions, and G1/G2/G3 confirmations. Add templates only as needed. Do not precreate empty runs or learning profiles, or record AI-written answers as learner achievements.

Authored documents are primarily English. Preserve Chinese entry points, coaching prompts, learner responses, and original Chinese excerpts. This is a manual conversational workflow; answer separation and status checks are not enforced by software.

## Current and future boundaries

This increment adds only workflow documents, templates, two cases, and source indexes in this directory. Existing BusinessAgent code, documentation, OpenSpec, acceptance conclusions, and unrelated local changes remain untouched.

The publication version contains only these 21 documents and is prepared from the already-public `main`. Two later case sources are local-only evidence and are not included in this branch; the ledger distinguishes public material, local material, and the user's account. The original local documentation branch and its engineering history are retained and are not uploaded with this publication.

The user's 2026-10-23 direction is to conduct a future reconstruction in a separate new folder using this workflow without OpenSpec. Its name, location, architecture, and migration plan remain undecided. This increment creates no reconstruction folder, copies no code, and starts no refactor. Existing repository rules remain in place for that project; this directory does not repeal them. The workflow itself has no OpenSpec dependency.

Document checks do not establish learning effectiveness. A real learner session remains necessary. Original-project runtime acceptance and future reconstruction are outside this delivery.
