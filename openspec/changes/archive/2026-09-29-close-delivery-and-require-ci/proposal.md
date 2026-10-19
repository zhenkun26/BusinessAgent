## Why

PR #1 and its image publication completed, but repository delivery tracking still says
validation and merge are pending. Main branch protection also does not require the CI
checks that already run. The remaining UAT/integration records need current offline
evidence without pretending external resources or production approval exist.

## What Changes

1. Reconcile delivery records with merged commit 2d4bfc1, successful main CI 36522224892,
   and the GHCR version whose commit and latest tags share a digest.
2. Require the two Python jobs and production-image job on main, bound to GitHub Actions
   app 15368, with strict up-to-date checking. Preserve other protection settings.
3. Refresh offline UAT/grey-release/release-gate and G0 replay evidence, record current
   automated regression results, and make remaining external inputs actionable.

## Capabilities and Scope

No new runtime capability or specification contract. This engineering follow-up enforces
existing security/release requirements; `skip_specs: true`. No application/dependency
changes, filesystem deletion, real external writes or production deployment.

The user explicitly authorized documentation updates and required CI configuration, then
confirmed external resources are not ready and only offline work should proceed. PR #1's
administrator exception was one-time; it does not authorize bypassing review on a new PR.
