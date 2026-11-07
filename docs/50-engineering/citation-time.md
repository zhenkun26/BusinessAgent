# Citation time contract

## F2-08 plan — authorized 2026-10-20

Baseline: `8773639`. Record this plan before implementation. Scope is newly generated
citation timestamps and offline regression, not a global date/time migration.

1. Convert retrieval `updated_at` Unix seconds to an explicitly UTC-aware datetime at
   the KnowledgeAgent source-construction boundary. JSON must retain an explicit UTC
   offset (`Z` or `+00:00`) and the represented instant.
2. Preserve the existing RetrievalSource schema and checkpoint projection. Historical
   naive datetime/string values retain their wall-clock fields and lack of offset.
   Their original timezone is unknown: do not infer UTC, use the current server zone
   to reinterpret them, backfill records or silently claim an absolute instant.
   Already-aware historical values keep their instant and existing supported offset.
3. Test the actual generation path with retrieval/model doubles under UTC,
   America/New_York and Asia/Shanghai, including DST transitions, cross-day times,
   zero/fractional epochs and malformed epochs. Test JSON/Redis-serializer/history
   projection and existing ownership/invalid-source boundaries.
4. Exercise the existing UI `fmtTime` method with Node VM doubles under explicit
   timezone settings. Preserve its separate, documented approval-time compatibility:
   naive approval timestamps are treated as UTC. Do not apply that assumption to legacy
   naive citations. Only change the formatter if a scoped regression requires it.
5. Update relevant contracts, OpenSpec and delivery trackers; refresh only changed/new
   F2-09 inventory entries without clearing provenance. Review and commit locally only.

### Acceptance and exclusions

- The same epoch produces the same UTC instant/JSON value in different server timezones.
- Citation serialization and history projection preserve aware instants; legacy naive
  values remain naive, with no guessed zone, migration or historic output rewrite.
- Invalid/non-finite/out-of-range epochs retain the existing safe agent failure behavior;
  no partial successful citation list is published.
- UI formatting tests cover explicit offsets, legacy approval input, empty/invalid input
  and local DST/cross-day behavior. Node VM tests are not browser acceptance.
- Current UI language remains Chinese; English documentation is not English UI support.
  No translation framework, new dependency, schema migration, database connection,
  provider call, old-deck edit or new citation date UI is included.
- Real browser/runtime/full RAG remain BLOCKED; C10 OPEN; F2-09 source rights pending.
  No push, upload, merge, release, main-spec sync, archive or automatic next increment.

## Implemented contract

The only application behavior change is `KnowledgeAgent.run` using
`datetime.fromtimestamp(r.updated_at, tz=timezone.utc)`. The upstream value remains Unix
seconds; no units or storage schema change. `RetrievalSource` and public checkpoint
projection are unchanged.

| Input path | Public representation | Interpretation |
| --- | --- | --- |
| Newly generated epoch citation | `2026-10-20T00:15:00Z` | Explicit UTC instant, independent of server zone |
| Historical aware citation | `2026-10-20T08:15:00+08:00` | Existing supported offset and instant retained |
| Historical naive citation | `2026-11-01T01:30:00` | Wall-clock fields retained; original zone/instant unknown |

Compatibility preserves datetime semantics, not the byte spelling of an input string:
the existing Pydantic JSON projection may normalize separators or fractional precision.
It must not introduce an offset for a naive value. Consumers must not sort mixed
naive/aware history as if every timestamp represented a known absolute instant.
Determining legacy instants requires separate source/timezone evidence and authorization.

Current chat citations render title and score, not time. Existing `fmtTime` is used by
approval views; aware values render in the viewer's local zone, while naive approval
values retain their existing UTC assumption. That assumption does **not** establish a
timezone for legacy citation data. The UI remains Chinese, and this increment makes no
English UI or general localization claim.

## Offline delivery evidence — 2026-10-20

| Check | Result and evidence limit |
| --- | --- |
| New generation/compatibility regressions | Five new Python tests plus 39 new subtests: three server zones, DST/cross-day/zero/fractional epochs, invalid epochs, empty retrieval, and naive/aware serializer-handler parity |
| Focused Python selection | **PASS: 51 tests + 68 subtests** (`citation_time`, `checkpoint_followups`, `retrieval_authorization`) |
| Full local pytest | **PASS: 1139 tests + 288 subtests**, zero skips/xfails/guard denials; Python 3.13.15/macOS arm64; 45 dependency deprecation warnings |
| Existing frontend method | **PASS: 48 Node VM cases**, including three new timezone cases; no production HTML change or browser rendering |
| `eval/run_c10_followups.py` | **PASS: 27 tests**, zero guard denials; actual Redis serializer, service/store doubles |
| `eval/run_c17_rag_quality.py` | **PASS: 29 tests**; no provider call or measured semantic quality |
| `scripts/verify_license_inventory.py` | **PASS:** 431 pending sources, 98 production packages, 3 browser packages, 32 declaration inputs; no rights clearance |
| `scripts/safe_validate.py` | Execution **PASS**, overall **BLOCKED** (expected exit 2); UAT/release evidence absent |

Paths in the table are relative to `enterprise-agent/`. Tests use synthetic data and
already-declared dependencies. The retained isolated runner disables dotenv/implicit
pytest plugins and cache cleanup, denies network/deletion, and permits test output only
under ignored `eval/results/`. Source hashes remained stable during the full run.
No database, Redis service, model provider, browser or Linux environment was started.

Local evidence is retained under
`enterprise-agent/eval/results/ci-pytest-3c202720f02e47a69e3528b8302d6f41/`:
`receipt.json`, `runner.py`, coverage, validation logs and final commit binding. These
ignored, host-specific receipts are not uploaded or release attestations. The baseline
in the test receipt is `8773639` plus the tested worktree hashes; documentation-only
updates after the run are checked separately before commit.

Review includes production/test diffs, source inventory boundaries, documentation links,
YAML/manual delta-spec structure, and preservation of original modes/unrelated bytes.
Strict OpenSpec CLI is unavailable and **BLOCKED**; manual checks do not replace it.
Real browser display, current remote CI, real two-process/runtime/full RAG and prior
acceptance matrices remain **BLOCKED**. F2-08 remains open for live acceptance; F2-09
sources remain pending; C10 stays **OPEN**. Local commit only, then wait.
