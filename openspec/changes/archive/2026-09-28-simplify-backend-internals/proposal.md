## Why

A snapshot-bound, independently reviewed audit identified two small internal contracts that
carry no behavior: an unacquired lock in the memory vector store and an unused boolean
returned by the rate limiter factory. Removing them makes the actual implementation clearer.

## What Changes

- FGR-01: remove only the unused asyncio import and memory-store lock initialization.
- FAT-01: return the selected limiter directly at four sites and update its sole caller.
- Add offline rate-limit behavior tests and retain reproducible baseline/final evidence.
- Preserve all existing tests, external contracts, backend selection, fallback and responses.

## Capabilities

### New Capabilities

None. This change adds no supported runtime behavior.

### Modified Capabilities

None. `skip_specs: true` follows the existing engineering-only change convention. Main
specifications remain unchanged; no specification synchronization is required.

## Impact

Production edits are limited to `app/rag/vector_store.py` and `app/middleware/rate_limit.py`.
Tests are limited to new `tests/test_rate_limit.py`. Documentation and verification evidence
are bounded by the approved audit agreement. No dependencies, filesystem deletions, remote
operations, deployment, version bump, or changes to existing work are authorized.

Approval: the user explicitly issued `GO FGR-01 FAT-01` after reviewing the audit.
