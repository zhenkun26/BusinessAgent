# Automatic telemetry configuration and startup admission (F2-05)

## Plan recorded before implementation — 2026-10-21

Parent candidate: `c5240ad`. This authorized increment uses synthetic data only, with no
real service/model/exporter calls, new dependencies, migration, deletion, push or upload.
It does not approve private data, provider terms, actual egress or runtime/full RAG.
F2-09 sources remain pending; C10 stays OPEN. C21 audit/replay and Prometheus metrics
must retain their existing behavior and acceptance criteria.

### Scope and sequence

1. Add a standard-library-only telemetry policy. Check inherited process configuration
   before application dependencies import, then check effective Settings input (including
   dotenv and constructor values) before clients, model probes or workers start. Repeat
   checks at API/worker startup and tracing factories so cached settings cannot bypass
   a changed environment. Never print configuration values or exception bodies.
2. Default `TELEMETRY_MODE=disabled`. OTEL is off; LangSmith tracing aliases, generic
   exporters, automatic bootstrap/capture and unreviewed OTLP options are rejected when
   active or malformed. Explicitly false aliases cannot hide another true alias.
3. Retain the existing project-owned OTEL path only with `TELEMETRY_MODE=synthetic`,
   `OTEL_ENABLED=true` and an explicit validated collector endpoint. This is operator
   intent for synthetic reference diagnostics, not privacy acceptance. No mode enables
   LangSmith tracing, SDK auto-bootstrap, arbitrary callbacks or arbitrary exporter
   options. Collector transport uses HTTPS or plain HTTP to loopback/the reference
   `jaeger` service, without URL credentials/query/fragment or inherited auth headers.
4. Gate FastAPI registration and OTEL construction with the same policy; preserve C21
   registration timing when explicitly admitted. Reject contradictory/changed process
   configuration rather than silently overwriting environment or continuing untraced
   after an explicitly requested exporter fails. Keep errors fixed and content-free.
5. Add synthetic configuration, import/startup ordering, actual Settings/factory and
   safe-error regressions. Verify disabled paths never construct exporters/instrumentors;
   admitted OTEL is tested only with recording doubles. Exercise existing C21 audit,
   metrics, readiness and worker tests and the complete current offline entry without
   skipped tests or lowered gates. Review only affected source/provenance hashes; retain
   historical C24 manifests and C17 corpus/evaluator unchanged.
6. Synchronize delivery trackers and active OpenSpec artifacts; review the diff and
   evidence, commit locally and stop. No remote CI, publication, main-spec sync or archive.

### Offline acceptance

| Case | Expected evidence |
| --- | --- |
| Defaults / explicitly disabled | No exporter, callback or instrumentation construction at covered factories |
| Inherited aliases / malformed / conflicting input | Fixed rejection before covered clients/model probes/worker work; no raw configuration in errors |
| Effective dotenv / constructor input | Same policy as inherited process input; SDK-affecting settings cannot evade the gate through ignored extra fields |
| Explicit synthetic OTEL | Existing instrumentation registration timing and audit/metrics preserved; recording doubles only |
| Collector / SDK construction failure | Fixed failure, no secret or endpoint echo; no silent degraded success |
| Process configuration changes | Rejected at subsequent admission boundaries even with cached settings/tracer |
| Verification | Relevant regressions and full current offline inventory pass with zero skips/xfails/deselections; strict CLI separately BLOCKED if unavailable |
| Delivery | Local commit only; real runtime/full RAG/privacy BLOCKED, F2-09 pending, C10 OPEN |

### Limits

The current pinned production inventory contains the OTEL API/SDK and FastAPI
instrumentor, but not `opentelemetry-exporter-otlp-proto-grpc`,
`opentelemetry-instrumentation-requests` or `opentelemetry-instrumentation-redis`.
No dependency is added or installed here. Thus admitted configuration is not a claim
that this image can export traces: explicit enablement with missing SDK components
fails closed with `TELEMETRY_INITIALIZATION_FAILED`. Audit/replay/readiness/Prometheus
remain independent. A usable real collector/exporter profile requires a separately
reviewed dependency/environment increment and actual C21 acceptance.

This is a configuration/admission boundary for the enumerated application entry points
and declared SDK configuration, not an OS egress firewall or a general PII scrubber.
An instrumented Python launcher, injected programmatic callbacks/context, or a process
that exported before importing the application cannot be made safe retrospectively.
Use the normal project entry points with a clean process; do not use `opentelemetry-instrument`
or external auto-instrumentation wrappers. Synthetic mode can still export synthetic HTTP,
database and exception metadata through existing automatic instrumentors. Actual SDK/proxy
capture, collector access/retention and all private-data admission require separate real
evidence; no default retention or no-training promise is introduced.

## Implemented contract

`app/observability/telemetry_policy.py` uses only the standard library. Normal `app.*`
imports check the process before SDK imports. API and worker imports, API creation,
both startup functions and tracing factories recheck effective Settings and a private
process-configuration digest; a cached Settings/tracer cannot bypass changed process
telemetry. Effective-input validation runs before Pydantic can render rejected telemetry
inputs, including dotenv extra keys ignored by ordinary Settings fields. It does not
read a second private env file, rewrite environment variables or auto-enable SDKs.

| Configuration | Admission |
| --- | --- |
| `TELEMETRY_MODE=disabled`, OTEL absent/false | Default; factories construct no application SDK exporter/instrumentor |
| `TELEMETRY_MODE=synthetic`, `OTEL_ENABLED=true`, explicit collector | Configuration admitted only; actual SDK availability/capture/runtime remain unaccepted |
| `LANGCHAIN_`/`LANGSMITH_` `TRACING`, `TRACING_V2`, `OTEL_ENABLED`, `OTEL_ONLY` | Absent or explicit false only; every alias checked independently |
| Generic `OTEL_TRACES_EXPORTER`, `OTEL_METRICS_EXPORTER`, `OTEL_LOGS_EXPORTER` | If set, `none` only; project-owned explicit OTLP construction is separate |
| `OTEL_SDK_DISABLED` | Must agree with the effective enablement, including SDK-only process options omitted from Settings fields |
| Other nonempty `OTEL_`/`TELEMETRY_` options or SDK tracing/OTEL/callback options | Rejected; includes resource attributes, capture headers, alternate OTLP endpoints/auth headers and bootstrap configurators |
| Dormant LangSmith API keys/project/endpoint names | Do not enable tracing; never emitted in diagnostics; process changes invalidate cached admission |
| Malformed switches, invalid modes, conflicting inputs, preloaded OTEL auto-launcher | Fixed rejection before covered initialization |

Requested tracing initialization precedes model probes/database startup in both API and
worker; missing optional SDKs therefore reject before that external work. Worker supervisor
errors remain fixed, without weakening audit/metrics.

Only literal `true`/`false` (case/outer whitespace normalized) or constructor booleans
are accepted for switches. Collector URLs require an explicit port, no path except `/`,
userinfo, query, fragment, whitespace or control characters. HTTPS is allowed for an
explicit synthetic recipient; HTTP is restricted to `localhost`, `127.0.0.1`, `::1` or
the reference `jaeger` name. This is not DNS/egress certification. Put all three enabling
values together in the process environment; inherited process input is checked before
dotenv. A complete synthetic dotenv configuration also works when process input is
independently valid. False constructor values cannot hide enabled process aliases.

Synthetic OTEL retains C21 pre-start FastAPI registration plus the existing manual and
client instrumentors. Resource metadata uses fixed service names/version and bounded
environment names without automatic resource detection; collector URLs/SDK exceptions
are no longer logged. SDK failure is fixed, the constructed provider is shut down and
initialization failure is latched until restart. No automatic telemetry/privacy acceptance
is inferred from this configuration policy.

## Offline verification and delivery — 2026-10-21

- PASS: **84 new collected cases** cover independent SDK aliases, malformed/conflicting
  configuration, collector URLs, actual Settings/dotenv extras, SDK-only process options,
  cached changes, package/API/worker ordering, disabled/admitted factories, safe SDK/
  import failures, provider closure and failure latching. Admitted factories use recording
  doubles only; no real exporter/client/collector is constructed or invoked.
- PASS: complete current entry: **1302 tests + 484 subtests**, zero skips, xfails,
  deselections or guard denials; 45 existing dependency warnings; Python 3.13.15/macOS
  arm64, coverage 76.76%. Node page 69, credentials 14 and seven browser assets PASS.
  All eight execution checks PASS, with 332 reviewed inputs and 439 pending source records.
- PASS: existing C21 audit/replay/metrics/readiness/service bytes are unchanged. Original
  assertions remain; five older startup/queue fixtures now provide the new dependency or
  disabled Settings binding. The first integration run exposed those fixture omissions
  and the expected pending-source inventory drift; they were repaired, not skipped.
  Later review added SDK-only conflict, malformed input and failure-latching cases.
  The retained pytest diagnostic clears `TELEMETRY_` before importing the application,
  alongside its existing SDK environment cleanup; a dedicated counterexample preserves
  that synthetic-only boundary. This does not change real application configuration.
- PASS: historical C24 runner/manifest, C17 corpus/evaluator, dependencies, Docker/CI
  recipes and old interview/speech/media remain unchanged. Only reviewed current-source
  and pending-provenance hashes/counts are maintained; no automatic historical refresh.
- Manual source/diff/link/OpenSpec structure review is recorded with local evidence;
  388 local links and manual delta structure (23 files, 125 requirements, 198 scenarios)
  PASS; OpenSpec YAML parses. Strict OpenSpec CLI remains unavailable/BLOCKED. Actual current remote CI, Linux,
  browser, telemetry/provider/privacy, two-process/runtime/full RAG and prior matrices
  remain BLOCKED. F2-05/C21 and C10 remain OPEN; F2-09 rights pending.

Precommit evidence: `enterprise-agent/eval/results/offline/f205-telemetry-startup-reviewed-20261021.json`;
full receipt/log/coverage under
`enterprise-agent/eval/results/offline-pytest-1693aaa51c8347f388c60dab47ccc8fe/`.
The dirty precommit candidate has binding BLOCKED; a final clean candidate receipt is
retained under ignored `eval/results/offline/` after local commit. Scoped CI-mode exit
success is offline execution only; overall acceptance and all release/UAT flags remain
blocked/false. Local review/commit only, then wait; no push/upload, deployment, merge,
publication, main-spec sync or archive.
