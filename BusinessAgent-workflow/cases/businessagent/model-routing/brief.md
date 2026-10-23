# BA-01 · Model routing judgment

Learner packet A · No outcome reveal · Read with the [coaching protocol](../../../workflow/coaching.md).

## Context available for the first attempt

A team is building an assistant that classifies requests, retrieves knowledge, analyzes data, and proposes actions. Different steps use local or cloud models. A frequent local evaluation step has been reported as taking tens of seconds. The team suspects shared GPU load and is considering moving more lightweight work to the cloud.

The record available to you is incomplete: there is no full raw benchmark, controlled workload description, or complete contemporary discussion. It does not yet justify a root-cause conclusion. Costs, speed, correctness, and dependency exposure all matter, but their priorities need to be stated for the actual task.

You are acting as the PM at this decision point. This is a reconstructed information cutoff based on later project records; it is not a verbatim meeting transcript or proof of exactly what was known at a particular minute. No model or service calls are authorized by this exercise.

## First question

**你会把团队现在要作的决定定义成什么问题？先用自己的话说，暂时不用套模板。**

Assistant: stop here and wait. Do not suggest a preferred provider, name an adapter fix, or show historical timings. Preserve the actual answer before asking one question about its most important gap.

The later discussion will cover alternatives, a validation plan, a second task with different failure costs, and a transfer exercise. The learner may have seen the earlier conversation's history; record that exposure rather than grading recall as independent reasoning.
