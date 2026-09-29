## Context

Base: `5446a70cd60cf4e0729cb21bbc82b45aa6ec43c1`. The workspace contains 556 pre-existing
executable-mode changes and no content changes. They must remain uncommitted and untouched.

## Goals / Non-Goals

Preserve supported behavior while removing only the two approved internal redundancies.
Do not remove tests, public methods, files, or other unused symbols. In particular retain
`retrieve_with_text`, the HTTP-test helper, and the unrelated approval return-value defect.

## Decisions

1. Remove the lock allocation, not the vector-store protocol or its implementations.
   No method acquires the lock; this makes no new concurrency guarantee.
2. Remove only the factory's returned boolean. Keep `_use_redis`, every state transition,
   probe, log and fallback. Keep the factory await outside the middleware's existing try.
3. Characterize behavior before production edits using pure memory tests and fake Redis.
   Run the same checks after editing; do not inject faults or weaken surviving tests.
4. Reuse the installed CPython 3.13 runtime with the existing venv site-packages through
   an explicit path. Do not repair or reinstall the venv. Disable pytest cache, temporary
   directory, disk-capture and auto-loaded plugins. Keep coverage in memory.
5. Retain baseline/final JSON and command logs. Guard the verification process against
   filesystem deletion, network connections and unapproved writes.

## Risks / Trade-offs

The audit cannot exclude hypothetical external consumers of private attributes/functions.
No supported such consumers were identified. Full CI contains prohibited deletion paths
and is not part of the safe focused run; report that limitation explicitly.

The OpenSpec CLI is unavailable on PATH and in checked Node installation locations.
Prepare the conventional artifacts manually and check their contents; do not report CLI
validation as passed. The existing `skip_specs` engineering-change convention is retained.

## Evidence

`docs/40-process/code-simplification/20260928-backend/` contains the agreement, audit,
authorization, safe verification harness and execution results.
