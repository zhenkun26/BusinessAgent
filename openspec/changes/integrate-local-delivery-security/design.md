# Integration design

Use a fresh worktree based on verified main and apply only ancestor-to-edc5c58 engineering delta. Review every conflict against both sides, not blanket ours/theirs. Preserve main immutable server UTC approval contracts, verified expiry, human holds, current identity and permissions, exact approver roles, committed claims, and capability scopes bound to exact approved calls. Maintain local two-phase approvals. Never automatically compensate or clear uncertain/partial failures.

Retain managed migrations v1-v8 unchanged, including C10 fencing. Introduce managed v9 approval provenance equivalent to main standalone009 inside the runner transaction; keep standalone history. Verify database guard definitions/readiness and stop older executors before any eventual rollout. No live SQL in this integration.

Preserve strict production mail recipients/header checks, non-dev password/demo-hash protection, local SSO requirements and explicit synthetic reference-profile isolation. Retain local C10 checkpoint publication and ownership boundaries. Reconcile main and local independently implemented verified-token quotas without weakening fail-closed recovery.

Retain main full-event/history and exact-tree secret scanning plus audited dependencies. Reconcile local locked inputs/inventories deliberately; historical receipts remain immutable, newly changed inputs require new reviewed evidence. No broad suppressions or weakened assertions.

Test only with retained outputs, no network or filesystem deletion, using existing reviewed runner and declared available dependencies. Record blocked tooling/runtime acceptance separately from failed and passed offline checks. Local commit only after review and sufficient validation; no publication.
