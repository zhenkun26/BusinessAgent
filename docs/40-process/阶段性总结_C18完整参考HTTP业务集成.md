# C18 complete reference HTTP integration — offline increment

Date: 2026-10-18. Branch: `codex/delivery-ci-gates`.

C17 `cd49d788ed4ecea00e9db22d414917f91f32a886` was pushed to the same remote branch and
verified against `git ls-remote`. The user authorized C18 implementation, documentation and
offline verification while retaining real runtime/full RAG BLOCKED. This increment stops at a
local commit; its push and C19 require the next confirmation. C18/task 5.4 remains open.

## Delivered scope

- Independent standard-library CRM, ticket and mail HTTP services implement B01–B13 and
  `crm-analysis-v1`. Each has a distinct persistent store identity, run/principal grants,
  strict inputs, original receipts, conditional compensation and synthetic mail capture.
- Effects/terminal receipts share a SQLite transaction. Pending registration is retained;
  a writer-transaction recheck prevents duplicate terminal execution. Rejections roll back
  tentative effects through a savepoint before recording a retained no-effect receipt.
- Separate authenticated operator listener supplies fresh-run provisioning, retained evidence
  and immutable operation/attempt/phase fault schedules. No reset, SMTP, real recipient send,
  arbitrary attachment fetch or cleanup path was added.
- Isolated image/Compose/env recipes supply three retained service volumes and an evidence
  collector. `.env.reference` is ignored; credentials are blank placeholders, not defaults.
- Application reference calls explicitly send JSON Accept/Content-Type, including bodyless
  DELETE compensation. Admin-only profile/evidence endpoints expose bounded IDs/states/hashes,
  with payload and credential omission and no audit replay.
- Opt-in collector uses actual login/chat/approval/resume routes, checks run/store/fixture
  identity, retains per-step/application/provider evidence and stops on ambiguity. Its default
  performs no network or write. OBSERVED transcript steps never close R01–R20.
- OpenSpec design/delta/tasks, roadmap, issue criteria, authority context and documentation
  indexes are synchronized. No main-spec sync/archive, release or later C item was started.

See [implementation, isolation and acceptance guide](../50-engineering/reference-integration.md)
and the unchanged [R01–R20 contract](../50-engineering/reference-business-contract.md).

## Verification

| Check | Result | Boundary |
| --- | --- | --- |
| C18 reviewed entry | PASS, 45 cases | Actual service code with in-memory SQLite; actual app functions with injected HTTP/PG/identity; fake transport objects |
| C12 tool operation safety | PASS, 41 cases | Existing operation, receipt and HTTP fail-closed contracts |
| C13 Saga recovery | PASS, 34 cases | Retained forward/inverse IDs, conditional compensation and recovery orchestration |
| C11 approval execution | PASS, 34 cases | Atomic claim, expiry, fresh authority and truthful states |
| C16 analysis data | PASS, 33 cases | Query/provider alignment, bounded snapshots and exact arithmetic |
| C06 credential safety | PASS, 20 cases | Credential/diagnostic sanitization; pre-existing datetime.utcnow warning retained |
| AST, changed links, OpenSpec structure and diff | PASS | Static checks only, not strict OpenSpec CLI or Docker validation |
| Safe validator | Execution PASS, overall BLOCKED | Expected exit 2; UAT/release flags false |
| Docker build/Compose, disk SQLite restart and real transport faults | BLOCKED | No Docker/Linux/physical ledger execution this turn |
| Actual application R01–R20, model/JWT/PG/API/SSE/worker/audit and full RAG | BLOCKED | No services, paid calls, migrations or real recipients |
| Full pytest / strict OpenSpec CLI | BLOCKED | Dependencies/CLI unavailable; no installation |

45 focused + 162 related cases pass. The focused checks include actual gateway reconciliation
of an independent committed reference effect after injected 503, actual analysis page parsing,
transaction rollback/terminal recheck, identity/permission denial, compensation/version conflicts,
strict framing, collector no-network default, ambiguous approval refusal and evidence bounds.
They are not physical crash, socket, PostgreSQL isolation, JWT or complete graph evidence.
All 316 checked local links introduce no new broken target; five pre-existing links in the
backend README remain for C25. Strict CLI/YAML/Compose validation was not available.

## Retained limitations and handoff

All 20 runtime cases remain BLOCKED; every missing subcase stays visible. The shipped transcript
is a happy-path observation plan with scoped fault support, not automatic full-case certification.
Planner business semantics, negative protocol/app pairing, process crash placement and audit/
queue/compensation completeness need the isolated operator procedures in the guide. Actual
image identities need operator attestation; store UUIDs do not prove backup freshness. SQLite
PERSIST and FULL settings are unmeasured physical durability/retention choices. Observe the
filesystem during normal/savepoint/crash behavior before accepting them. Run one replica per
service; no performance/HA claim is made. The application evidence read is non-atomic.

C10's lease-expiry checkpoint write race stays in C10 and is not closed by reference dedupe.
Audit cache deletion/replay is unchanged and deferred to C21; the existing application audit
path must be reviewed before a runtime launch under the non-deletion policy. Full RAG,
Milvus/Redis/LangGraph/JWT/PG/API/SSE/Linux, browser/SSO, historical credential disposition,
real-enterprise resources and formal UAT remain blocked. C15/C16/C17 remain open. Legacy
`run_ticket_acceptance.py` remains excluded. No files, volumes or historical evidence were
removed; no dependency was installed or added. The 556 existing mode-only changes are preserved.

The final-commit/source-hash receipt is retained under ignored `enterprise-agent/eval/results/`.
`formal_uat=false`, `release_evidence=false`, `release_allowed=false`.
Stop after the C18 local commit; wait for confirmation before pushing it or starting C19.
