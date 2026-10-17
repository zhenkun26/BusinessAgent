# Fix vulnerable runtime dependencies

## Why

PR #3 CI run 39011635217 passed both Python test jobs but failed the production
image's Trivy gate with 16 HIGH and 1 CRITICAL findings. The affected packages
are existing runtime dependencies, not the README changes.

## What Changes

- Upgrade production pins for PyJWT, langgraph-sdk, pypdf, and urllib3.
- Align the existing development installation manifests with the patched floors.
- Verify dependency compatibility, existing application tests, and image scanning.
- Preserve the existing security checks and exemptions without weakening them.

## Capabilities

This repairs the existing security-operations requirement to block vulnerable
images. No capability or policy changes are introduced; skip_specs is true.

## Impact

The user authorized fixing the CI failure, pushing corrections, and merging
PR #3. Keep the approved READMEs intact. No new package is introduced; explicit
floors for langgraph-sdk and urllib3 constrain already-installed dependencies.
The required approval remains a separate GitHub merge condition.
