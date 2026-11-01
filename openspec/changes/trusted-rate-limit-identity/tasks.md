## Local work

- [x] Record scope/design before implementation.
- [x] Record regression tests failing against unchanged old implementation.
- [x] Implement trusted quota identity and update intended login expectation.
- [x] Pass focused/full offline regression and independent security review.
- [x] Retain exact baseline, evidence and integration limitations.

PR4 baseline: `3cf49540920745f988bf58bf5ea7381da16744ef`.
Old implementation: 18 security-test failures, 6 positive-control passes. The separate
scheme-capitalization correction first produced 2 failures. Final Python 3.12.14:
35 focused checks passed independently; full suite 214 tests + 28 subtests passed,
36 warnings, 7.10 seconds. No tests skipped. Independent security review found no blocker.
Evidence is retained outside the source checkout in `businessagent-audit-evidence`.
No remote CI was run for this local patch. Existing PR4 CI covers Python 3.11/3.13 only;
the 3.12 results are local. Redis, real proxy chain and multi-process behavior remain
unverified; this patch does not change their existing policies.

## Deferred

- [ ] Redis/multi-process and actual proxy-chain acceptance in an authorized isolated environment.
- [ ] Remote publication, merge and deployment require their own concrete approval.
