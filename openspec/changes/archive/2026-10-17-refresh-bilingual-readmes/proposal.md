# Refresh the Chinese and English repository introductions

## Why

The user approved a source-grounded README draft and requested a Chinese
`README.md`, a complete English `README-en.md`, and a GitHub push.
Visitors need equivalent explanations of the use cases, architecture, setup,
verification commands, and current delivery boundaries in either language.

## What Changes

- Replace the root README with the approved Chinese introduction.
- Add a full English translation with reciprocal language links.
- Keep the same commands, paths, diagrams, capabilities, and limitations in both.
- Update the existing repository index and development tracking document.

## Capabilities

No application or specification behavior changes. This is a documentation-only
presentation change; `README.md` remains the canonical navigation entry and
`README-en.md` is its translation. The existing `skip_specs: true` convention
applies.

## Impact

Only root README files, `contents.md`, `docs/40-process/ROADMAP.md`, and this
change record are in scope. No dependencies, backend code, deployment settings,
release version, or production-readiness gates change.

## Authorization

The user authorized local file creation and push to the repository. Delivery uses
a focused branch from verified main commit `2d4bfc17a34e45907404fdde38857e4cf96ad550`.
The existing PR #2 branch and unrelated working-copy file modes are preserved.
Merging, deploying, and releasing are outside this authorization.
