# Integrate local delivery candidate with main security

## Why
Current remote main f7d684be1a46758bddddc2d13e2a13a33896ba51 and locally committed engineering candidate edc5c58e5783e5c3035d89a035917cae35cb3ef1 diverge from 065bdf7. The user explicitly includes all 31 local engineering increments beyond remote PR2. A fresh main-based isolated worktree exposes 21 textual conflicts; automatic merges also require semantic review.

## Approved behavior
Approval records a decision only; the original requester must separately confirm execution. Any multi-action failure pauses and logs evidence for human judgment, with no automatic compensation. Unknown execution remains held even when later receipts arrive; new evidence never automatically releases the hold or replays a mutation.

## Scope
Integrate approvals, schema and runtime first, followed by UI, CI, dependencies and documentation, then focused/full offline verification. Preserve local C10 fencing, signed rate-limit identities, fail-closed Redis, budgets, SSE bounds, privacy, RAG trust boundaries and source-evidence distinctions.

## Non-goals
No changes to original worktree, old integration draft, or five independent workflow-document commits. No push, merge to main, deployment, external provider calls, live database migrations, new dependencies, filesystem deletion, main-spec synchronization or archive. Offline results do not close C10/runtime/privacy/rights/release gates.
