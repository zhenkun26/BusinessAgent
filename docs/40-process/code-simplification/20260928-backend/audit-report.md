# Backend simplification audit

## Agreement and snapshot

- Objective: preserve supported behavior while reducing evidenced maintenance overhead.
- Confirmed audit scope: backend Python in `enterprise-agent/app`, `tests`, and `eval`.
- Excluded cleanup targets: static frontend, deployment, interview assets and historical docs.
- Base: `main@5446a70cd60cf4e0729cb21bbc82b45aa6ec43c1`.
- Initial state: 556 unstaged mode changes from 100644 to 100755; no content, staged or
  untracked changes. Revalidated before implementation. Preserve all existing modes.
- Audit authorization: user confirmed the proposed read-only scope with `授权许可`.
- Implementation authorization: exact user response `GO FGR-01 FAT-01`.
- No authorization for new dependencies, filesystem deletion, push, PR, merge or deployment.
- Evidence stays in this directory; existing ROADMAP and navigation indexes track delivery.

## Independent judgments

Fresh Astra finders `finder_graph_rag` and `finder_api_tools` examined separate responsibilities.
Fresh Astra `independent_reviewer` challenged candidates; the lead read all four target files
and adjudicated the findings. Agent agreement supports inspection, not runtime correctness.

| ID | Category | Finder | Independent review | Lead | Authorization | Approval |
|---|---|---|---|---|---|---|
| FGR-01 | Dead private state | Supported | Supported | Accept | Eligible | Approved |
| FAT-01 | Redundant internal return protocol | Supported | Supported | Accept | Eligible | Approved |
| FGR-02 | Public convenience wrapper | Unresolved | Unresolved | Retain | Individual confirmation required | Not approved |
| LEV-01 | Test-only forwarding helper | Supported by lead finder | Supported | Retain: negligible benefit | Eligible | Not approved |

### FGR-01

At base `app/rag/vector_store.py:11,110`, the asyncio import only constructs `_lock`.
The complete file contains no acquisition, release or use; store methods are synchronous.
The protocol at lines 71-94, factory at 356-374, retriever and ingestion consumers use only
the supported store methods. Searches of exports, configuration, reflection/serialization
and packaging found no lock consumer or registration mechanism.

Counterargument: private fields can be accessed externally and future code might need a
lock. However, the current unacquired lock protects nothing. Removing it clarifies actual
behavior; it does not fix or improve thread safety. Benefit is small; risk is low.

Permanent boundary: remove only the import and initialization. No diagnostic edits.
Acceptance: equivalent memory-store construction, dimension rejection, add/search/filter,
memory-only document removal and stats, plus syntax and exact diff review.

### FAT-01

At base `app/middleware/rate_limit.py:146,148,161,166`, four factory returns contain a
boolean discarded by the sole caller at line 211. The caller's `is_redis` is never read.
`main.py:164` registers the public middleware, not this factory; package initialization,
manifest, whole-repository references and dynamic/patch searches show no other consumer.

Counterargument: the flag could express the selected backend or be used by external tests.
No supported use was found. `_use_redis` already retains operational state and must remain.
Benefit is removal of an unnecessary return convention; risk is low but needs branch tests.

Permanent boundary: four return expressions and the caller assignment; new
`tests/test_rate_limit.py` with fake Redis/request dependencies. Keep the await outside the
existing try; preserve initialization, logs, cache reuse, failover, quotas and responses.
No diagnostic edits. No dependency on FGR-01. Acceptance covers first/cached Redis and
memory paths, runtime failure, rejection/headers, route limits and exception propagation.

### Retained candidates and false-positive controls

- FGR-02: `app/rag/retriever.py:210-224`, `EnterpriseRAGRetriever.retrieve_with_text` has
  no identified internal caller, but exposes a distinct public tuple API. Removing it can
  cause external AttributeError/unpacking failures. External ownership is unresolved;
  its 15-line maintenance cost does not justify compatibility risk. No edits authorized.
- LEV-01: `tests/test_http_adapter.py:11-13,29,58,84` is an undecorated, unregistered,
  unpatched one-line MockTransport wrapper. Inlining preserves construction timing and
  exceptions; nevertheless the lead retained it because the benefit is negligible.
- Retain the settings constructor (observable initialization/failure timing), vector-store
  and reranker protocols (multiple implementations and injection), LLM/checkpointer helpers
  (lifecycle/compatibility), minimum-delay queue wrapper, JWT policy and worker validation.
- No test-removal candidate was accepted. No fault injection or restoration experiment
  is necessary. No whole-file removal was proposed for implementation.
- Separate pre-existing defect, not approved: `app/api/approval.py:55` returns two values
  for empty tool_calls while callers at 272,370,657 unpack three. Static finding only.

## Coverage and limitations

Inventoried Python files: app 63 (13,165 lines), tests 31 (3,848), eval 25 (6,721).
Completely read: app 51, tests 10, eval 5. Full-file reading does not establish that every
symbol's execution graph was audited; only four candidate targets received independent
challenge. Audit coverage is not test coverage.

Production files not completely read: `app/__init__.py`, `graph/planner.py`,
`agents/{__init__,analysis,execution}.py`, `rag/{__init__,document_loader,embeddings}.py`,
`observability/{__init__,audit}.py`, `prompts/defaults.py`, and `tools/crm.py` (mock-data
lines 71-244 unexamined). Other files in the two finder scopes were read in full.

Tests fully read: conftest, test_degradation_pg_tsvector, test_task_queue,
test_security_hardening, test_http_adapter, test_app_entry, test_uat_plan,
test_uat_execution_readiness, test_grey_release_plan and test_release_gate.
Eval fully read: diag_recall and the four validate_{uat_plan,uat_execution_readiness,
grey_release_plan,release_gate} scripts. run_eval, run_w6_checkpoint and
run_ticket_acceptance were partial; remaining tests/eval received searches only.

Before GO, no tests or project imports ran and no reports were persisted. Default Python
lacked dependencies; venv package files existed without its Python executable. After GO,
a guarded import probe successfully reused the existing packages with Python 3.13.15.
No installation or environment modification was needed. Full-suite and integration
verification must not silently execute known deletion paths in audit cache flushing or
the ticket harness. OpenSpec CLI, ruff and mypy availability must be reported honestly.
