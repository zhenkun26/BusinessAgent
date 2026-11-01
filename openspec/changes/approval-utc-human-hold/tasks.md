# Tasks

- [x] Review public-main baseline and preserve old negative-control evidence outside this patch.
- [x] Select server-owned database provenance and retain the human-review policy.
- [x] Implement the immutable contract column without new signing configuration.
- [x] Prepare the standalone atomic/repeatable 009 increment and pure negative controls.
- [x] Complete the application regression baseline (320 tests + 71 subtests), scanner regression (26), and independent source review.
- [x] Obtain authorization for isolated synthetic database execution and successful-fixture cleanup.
- [x] Complete actual PostgreSQL core acceptance: 25 mandatory checks in each of two independent synthetic fixtures; retain explicit coverage limits.
- [x] Integrate the exact tested harness type correction and an old-query negative control; preserve production code/SQL bytes.
- [ ] Complete review and CI on the final publication revision before considering merge.
- [ ] Separately plan full application acceptance and any rollout: stop old executors and explicitly install 009 in new or existing databases.
