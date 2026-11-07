# Repair review-branch CI gates

## Why
PR #8 CI rejects matrix record IDs containing dots before any check runs. Pre-push Gitleaks also reports verified source-manifest SHA256 values under new integration fingerprints. Neither failure may be labeled PASS or bypassed.

## Scope
Correct CI record naming without relaxing path validation. Add regression coverage. Preserve full-history and exact-tree secret scanning; handle manifest findings only through narrowly scoped independently recomputed source evidence and negative controls. Reconcile reviewed source/inventory hashes, run focused/full checks, independently review, commit and push to this PR, and inspect actual remote CI. No merge/deploy, broad secret-rule suppression, data deletion or unrelated application changes.

## Authorization
The owner authorized continuing PR/CI investigation, fixes, pushes and verification; final merge remains the owner's decision.
