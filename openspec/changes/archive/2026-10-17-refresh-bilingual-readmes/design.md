# Design

## Source and language structure

Use the approved conversation draft and the previously inspected main-branch
source. Do not reuse the previous root README prose. Put the Chinese document in
`README.md` and the full English translation in `README-en.md`. Both documents
link to each other near the title. Translate prose and headings while retaining
identical executable commands, architecture diagrams, and repository targets.

## Navigation

Keep relative repository links and language-specific heading anchors. Include
the product plan, operational guides, development records, repository index,
knowledge samples, and presentation assets so the existing navigation contract
remains covered. Refer to detailed manuals rather than duplicating them.

## Evidence boundaries

Keep the distinctions between implemented workflows, Mock tools, built-in
analysis data, real integration, formal UAT, and production approval. This change
does not claim a clean-environment setup run or new backend test results.

## Worktree and local delivery

Use an isolated worktree based on main because the user's original checkout is
on an unrelated open PR branch with existing executable-bit changes. Commit and
push only the documentation increment. Copy the final two README files back to
`/Users/zhenkun/GitHub/BusinessAgent` and verify all other tracked file bytes and
modes remain unchanged.

## Validation

- Check local Markdown paths and heading anchors.
- Compare executable command blocks, diagrams, environment keys, and link targets.
- Check shell syntax without executing installation or service startup.
- Inspect the resulting document structure and scoped Git diff.
- Verify archive artifacts and completed task records manually.
- Run `git diff --check`; record that OpenSpec CLI strict validation is unavailable.
- After push, verify the remote branch commit matches the local commit.

## Tooling limitation

OpenSpec CLI is not installed on the available command path or discovered local
Node installations. Follow the repository's existing manual documentation-change
record pattern. Manual checks are not a passing OpenSpec CLI validation result.
