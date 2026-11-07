# Design

Use a dedicated open-source quickstart rather than presenting the historical full infrastructure instructions as a verified starter. Add a prominent README link and capability boundary. Only document executable commands supplied and actually validated by the runtime worker; distinguish a synthetic API substitute from the real application and real RAG. Keep historical operational guidance, clearly labeled.

The starter must avoid production credentials/data, restrict listening/external effects as designed, and provide an explicit stop procedure without deleting retained user data. Explain prerequisites, expected output, data location and limitations.

Stage two (enterprise pilot evaluation) chooses a narrow business problem, success criteria, data permissions and feasibility. Stage three (real-environment pilot) validates an agreed scope with real users and approved sandboxes. Stage four (production use) adds operational ownership, recovery, security/privacy approvals and staged rollout. None is automatically complete because stage one passes.

Source provenance findings are recorded by the rights workstream; a root MIT declaration is not evidence for every asset. Do not duplicate or overwrite its per-file conclusions.

## Approved narrow starter design

The proposed profile is explicitly MODEL_PROFILE=synthetic-demo-v1 and is accepted only
with APP_ENV=dev; production configuration must reject it. It exercises actual
FastAPI authentication/JWT, LangGraph, PostgreSQL persistence/audit and a worker, using
independent loopback PostgreSQL and Redis. It does not import old demo seeds or
documents with unknown provenance.

Only fixed greetings and the authenticated user's own history are in scope. Other chat,
approval and business actions must reject clearly. Every LLM entry must reject without
network access; cloud models, Ollama, embedding, reranking and external tools are disabled.
Milvus and MinIO are not prerequisites for this narrow profile. A visible demo banner
must distinguish synthetic output from full product or RAG acceptance.

The launcher must create independent configuration and new test accounts without reading
private .env files. Worker observation host/port may be configurable with unchanged
ordinary defaults so this profile can bind entirely to loopback. Stop retains data and
does not delete fixtures. Implementation and actual startup evidence remain pending.

Use existing production dependencies, without a new binary psycopg demo dependency.
The pure psycopg distribution additionally requires native libpq available to its dynamic
loader. Installing Python requirements alone is not a complete setup. Platform-specific
libpq instructions and a successful import preflight must be verified before publication.

## Truthful UI and native-driver verification plan

Before the UI edits: DemoBoundary injects a fixed server-owned
data-businessagent-profile=synthetic-demo-v1 HTML attribute, never a query/storage
toggle. Vue reads only that marker to show synthetic greeting/history text and hide
business navigation. Only this profile plus HTTP 403, DEMO_UNSUPPORTED_OPERATION and
a matching response profile header establishes the specific unsupported/not-executed
message. Generic 403, production errors and uncertain outcomes retain their existing
human-hold semantics. Add Node regressions for both profile and non-profile paths.

Before the CI edits: add an independent Linux synthetic-demo job with existing production
pins, no binary psycopg extra. Preflight must establish psycopg.pq.__impl__ == python,
absence of psycopg_binary and psycopg_c distributions, and available system libpq.
Start a fresh real API/worker/PostgreSQL/Redis demo and run the tracked
scripts/check_synthetic_demo.py acceptance tool, including candidate source binding.
The acceptance tool validates the run identity, loopback addresses/ports, database
identity, receipt and owned container labels before acting. It reports redacted driver
implementation/libpq version, actual JWT/greeting/history/SSE/second-user isolation and
unsupported-operation results without tokens or passwords.

The CI job must always stop only its owned services, without deletion. Upload only
acceptance-*.json, never private logs, private-state.json, test credentials or broad
result-directory globs. Parent owns ci.yml; runtime worker owns the acceptance tool;
UI worker owns index.html and its browser tests.

Mac adapter evidence (Python 3.13.15, 41 tests plus 20 subtests, final run-03 HTTP
checks) uses an earlier approved binary driver adapter and is not proof of the native
libpq path. Browser-discovered misleading messages are undergoing repair. Linux,
final UI and fresh-candidate results remain pending until actually verified.
