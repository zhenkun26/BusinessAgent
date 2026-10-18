# C14 delivery: retained jobs and worker initialization

Date: 2026-10-17. Baseline: C12 `21b528702091b4056d1b5e15350026e90ed7bb7a`.
Branch: `codex/delivery-ci-gates`. C12 was pushed to the same remote branch and its
hash verified. This C14 increment is local; push and subsequent items require user
confirmation. No merge, deployment, live call or existing-store migration is authorized.

## Delivered scope

- Replaced unused Redis List transport with retained PostgreSQL jobs and additive
  checksum-pinned migration v3. No dependencies added; v1/v2 SQL bytes unchanged.
- Atomic knowledge approval producer, queued document state and acceptance audit, stable replay identity,
  HTTP 202 receipt and admin-only task/failure/consumer metadata queries.
- Exclusive claims, owner/deadline CAS, bounded pre-dispatch recovery/backoff, retained
  done/dead rows, current reviewer/input checks and no blind replay after dispatch.
- Cold-worker model/schema/audit/tool/vector initialization, progress heartbeats,
  supervision, reconnect and cooperative SIGTERM/resource shutdown.
- Explicit refusal of Saga recovery until C13; legacy deleting audit replay is not
  invoked. C15 vector/ledger consistency remains open. Updated API examples and delta
  specs reflect the asynchronous contract; main specs are not synced or archived.

Detailed behavior and future matrix: [queue contract](../50-engineering/queue-reliability.md).

## Verification

| Check | Status | Evidence and limit |
| --- | --- | --- |
| C14 source orchestration | PASS | 43 stdlib tests with SQL, services and handlers injected; no real PostgreSQL/Milvus |
| C12 tool operation safety | PASS | 41 offline tests; original operation/receipt boundaries retained |
| C03 migration/startup | PASS | 22 offline tests with v3 manifest; SQL locking/constraints not executed |
| C05 runtime authorization | PASS | 29 offline tests; production startup gates retained |
| C06 credential safety | PASS | 20 offline tests; safe worker diagnostics preserved |
| Syntax / diff / artifacts | PASS | 10 changed Python files parsed, 14 new local link targets checked, three migration hashes verified and v1/v2 bytes preserved; three delta structures checked |
| Safe validation entry | BLOCKED overall | Five reviewed functions execute PASS; expected exit 2; formal UAT/release remain false |
| Full pytest / actual framework | BLOCKED | Missing runtime packages; no install, unrestricted cache/temporary cleanup or live service use |
| OpenSpec strict CLI | BLOCKED | CLI unavailable; local structure/link checks are not strict validation |
| PostgreSQL/Redis/process/Milvus/API/Linux | BLOCKED | No live execution, fault injection, schema change or model call performed |
| Saga / audit recovery | BLOCKED | C13 durable compensation and C21 non-deleting audit replay remain prerequisites |

The first C03 regression run exposed an outdated worker fixture: it expected a raw
schema exception and did not inject newly initialized modules/cleanup. Updated it to
assert the safe worker error, no audit/consumer startup, and database closure; all
22 passed on rerun. Existing HTTP tests now expect 202 and queued-state rejection,
but the full pytest framework suite was not executed. Source-level route tests are
included in the 43 C14 cases and do not prove real FastAPI/JWT transport behavior.

## Delivery and acceptance boundary

Task 4.3.1 is the offline candidate only. Parent 4.3/C14 remains open; 4.3.2 requires
real SQL concurrency, process death, reconnect, cold worker and end-to-end ingestion,
plus deferred C13 Saga integration. This is conservative dispatch with manual
reconciliation, not automatic recovery of every running business action. Dead does
not mean rollback or proof that an old synchronous write stopped.

The migration was not applied. Legacy Redis entries and local audit caches were not
touched. No files/data were deleted and existing executable-mode differences remain
outside this increment. C10 lease-expiry write fencing is not closed; HTTP compensation
remains deferred to C13. C13 and C11 were not advanced. All prior real JWT/PostgreSQL/
API/SSE/Linux/LangGraph/Milvus/Redis/browser/SSO/history blockers remain in force.
`formal_uat=false`, `release_evidence=false`, `release_allowed=false`.


## Subsequent authorized handoff

C14 commit `59a5c14fbd41969438afea99f7c59d30b2e35a75` was pushed and verified on
`origin/codex/delivery-ci-gates` on 2026-10-17. The following authorized
[C13 increment](阶段性总结_C13Saga持久化与故障恢复.md) supplies the Saga producer,
linked HTTP compensation and bounded reconciliation candidate. This updates the earlier
C13_REQUIRED handoff; it does not retroactively turn C14 offline evidence into live
acceptance. C14 real acceptance remains BLOCKED, C10 remains open and audit replay stays C21.
