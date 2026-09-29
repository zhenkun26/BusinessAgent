## Implementation

- [x] 1. Inspect the current workflow, existing security contract and explicit authorization.
- [x] 2. Capture the baseline publication-order failure and repair build/scan/push order.
- [x] 3. Verify workflow safety and publication-script failure behavior; resolve independent review.
- [x] 4. Update delivery tracking and prepare reviewed artifacts for archive and the accompanying commit.

GitHub integration follows implementation: create the authorized PR, require passing CI
and the repository's approval, then merge and verify main CI/image publication. Report
any external approval blocker without bypassing protection.
