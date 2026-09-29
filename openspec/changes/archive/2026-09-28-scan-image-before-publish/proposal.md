## Why

The existing CI publishes the production image and moves `latest` before Trivy scans
it. A failed scan can therefore leave a rejected image available in GHCR. This
violates the existing security-operations requirement that scans block publication.

## What Changes

- Build and load the image without publishing it.
- Scan the local image identified by the current commit, with registry fallback disabled.
- Only after a successful scan, authenticate and push that same image under its commit
  tag and `latest`, without rebuilding it. PRs continue to build and scan only.
- Retain the scan report on failure and preserve the current vulnerability policy.
- Fetch complete history in the test job so gitleaks can scan the PR commit range;
  the first cloud run exposed the existing shallow-checkout failure.

## Capabilities

No new capabilities. `skip_specs: true` follows the engineering-fix convention:
this enforces the existing security-operations contract without changing it.

## Impact and Authorization

Scope: `.github/workflows/ci.yml`, verification evidence, OpenSpec artifacts and existing
delivery tracking. No application, dependency, branch-protection or deployment changes.

The user explicitly permits this CI repair, temporary cleanup in cloud CI, PR creation,
protected-branch merge and image publication. Local deletion remains prohibited;
production deployment is not authorized. Preserve all 556 unrelated mode changes.
