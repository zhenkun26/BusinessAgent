## Context

Base: 2d4bfc17a34e45907404fdde38857e4cf96ad550. The 556 existing unstaged mode changes
must remain untouched and excluded from commits. OpenSpec CLI and Docker are unavailable
locally; existing standard-library validators can run without installs or side effects.

## Decisions

- Keep historical attempt reports intact; append final delivery results and update current
  navigation/status sources. Reference actual GitHub runs rather than invented test results.
- Use the narrow required-status-check API, preserve all unrelated protection fields, and
  retain before/after/request evidence. The required contexts come from live check-run names.
- Do not enforce new administrator restrictions or weaken the existing one-review rule.
- Reuse offline validators and the fixed G0 fixture. Their structure/Mock evidence must not
  be relabeled as formal UAT, real integration, security acceptance or grey release.
- Bind GATE-01's automatic regression evidence to the tested merge commit; keep GATE-03,
  GATE-04 and GATE-06 blocked. Historical load/DR evidence retains its original applicability.
  Update the existing release-gate test's exact ready/blocked lists to match that evidenced
  document state; keep all overall-blocked and no-formal-release assertions intact.
- Update existing active change task evidence without checking off externally blocked tasks.
  Provide a successor blocker record with exact inputs, responsible roles and acceptance
  criteria; do not invent dates, users, contracts or credentials.

## Validation and Delivery

Read back GitHub protection and compare all fields except required_status_checks. Validate
document links, source/evidence hashes, G0 replay and plan/gate structures. Commit task-only
content on a focused branch, publish a reviewable PR, and preserve normal approval rules.
OpenSpec lifecycle artifacts are checked manually; no CLI validation is claimed.
