# Runtime observability candidate (C21)

Status: offline implementation only; **C21 remains open**. O01–O16 below are all
**BLOCKED**. This contract does not close B01–B16, S01–S16, R01–R20, full RAG,
historical credential handling, C10 lease-expiry writing races or enterprise acceptance.
See the [delivery baseline](engineering-delivery-baseline.md),
[issue oracle](../40-process/ISSUES.md#c21) and
[delivery record](../40-process/阶段性总结_C21就绪审计指标与告警.md).

## Readiness and process boundaries

`/health` observes process liveness. API `/ready` returns 200 with `status=ready`
only when every required component is healthy; otherwise 503/unavailable. Its
`components` contain bounded status fields, never connection strings or exception text:

| Component | Observation | Limit |
| --- | --- | --- |
| db | Existing connection and schema-manifest health check | Requires migration 7; not a business write transaction |
| redis | Shared runtime client PING | Does not certify Lua, cancellation, TTL or failover |
| milvus | Initialized collection exists | Not retrieval quality, indexing or full RAG; explicit dev memory is labelled |
| checkpointer | Read through the already initialized saver | API only; no automatic setup/backend substitution |
| tools | All eight required tools are registered | No external business/model call |
| workers | Both queue names have heartbeats within 75 seconds | API checks shared consumers; worker checks its own worker UUID |
| audit | Retained store writable and no process-observed unretained event | Includes pending count/oldest age; does not certify delivery |

Each asynchronous probe has a four-second deadline. Blocking Milvus work runs in a
thread with its own two-second RPC timeout; cancellation cannot kill a blocked thread.
Slow native calls and connection pressure must be tested. Readiness and scrapes perform
real dependency observations, including a retained-store write probe. They are not free
or zero-side-effect pings. An old pending audit backlog can coexist with ready=200;
the monitor and audit-age rule independently treat age over 60 seconds as a fault.

The worker has an internal-only ASGI listener on 8001 (`/health`, `/ready`, `/metrics`).
Its container check uses its own `/ready`, not the API's probe. The supervisor owns
signals and cancels its observation/replay/consumer children together. The older admin
consumer inventory's 45-second `fresh` indicator remains a stricter progress indicator;
75 seconds here allows the existing heartbeat schedule before declaring unavailable.
Neither threshold proves an external write has stopped after a lease expires.

No billable LLM, embedding or reranker call occurs in these probes. Ready=200 cannot
certify provider credentials, semantic quality, real authorization, or business capacity.

## Retained audit and migration

Migration `deploy/007_audit_identity.sql` adds nullable event/correlation fields to audit
rows, a unique event-ID index, and originating request/trace IDs to task jobs. Existing
rows retain their original identity and contents. Migrations 1–6 are unchanged. Apply
only through the approved [C03 workflow](../../enterprise-agent/deploy/DATABASE_BOOTSTRAP.md)
on an isolated target. The image recipe now copies every manifest SQL file; previously
root-level migrations after the initial schema were missing from that recipe. No image
build or database migration has run for C21.

API and worker share a **single-host local named volume** `audit_state` at
`/data/observability`, with `OBSERVABILITY_STORE_PATH=/data/observability/state.sqlite3`.
An optional second API uses the same volume. This is not NFS, multi-host HA or a global
exactly-once transaction. Ensure the image's non-root UID 65534 can write this volume;
never repair an existing user volume automatically. Outside this recipe the default is
`logs/audit/retained.sqlite3`; separate working directories do not share recovery state.

For each new audit event the logger generates a UUID and original UTC occurrence time,
redacts before truncating summaries, retains the event, then attempts PostgreSQL. A PG
commit is followed by a local acknowledgement update. Replay uses the same event UUID
with `ON CONFLICT(event_id) DO NOTHING`; unknown commit/ack results can be retried without
creating a second PG event with that identity. Acknowledged events and their bodies remain.
Concurrent replay workers may send the same event; the PG unique index is the arbiter.
An event-ID collision with different local contents is rejected rather than overwritten.

SQLite uses PERSIST journaling, FULL synchronization and memory temporary storage;
there is no row/file deletion, WAL lifecycle, vacuum, rotation or garbage collection in
this path. These are code/configuration intentions, not evidence about physical durability
or every SQLite/OS error path. Real filesystem traces and crash/restart evidence are O06/O16.
Disk growth is unbounded over time: operators must provision/observe capacity and retain
assets; any eventual cleanup requires a separate user decision.

Limits: 256 KiB per retained body, SQLite lock wait two seconds, PG write timeout five
seconds, at most 100 events per replay batch, a ten-second interval after each batch.
Failed events defer for 30 seconds so one poison record does not permanently starve later
records. Oldest age includes deferred records. A batch of failures can therefore take
minutes; the interval is not a ten-second recovery SLA. Pending records remain inspectable.

If local retention fails but PG succeeds, PG remains the durable copy. If both fail, the
business path logs a fixed failure code and increments a process-local `unretained` count;
readiness becomes unhealthy. This is an observed possible loss, **not a zero-loss claim**.
The counter resets on process restart and cannot restore a lost event; operators must retain
incident evidence and reconcile it. Application business operations are not rolled back
solely because best-effort audit storage fails. Readiness is an observation, not admission
control. Transactional approval-transition audit stays in the approval transaction.

### Historical JSON caches

Startup never scans/imports/deletes old JSON caches. They may contain historical credentials
and unkeyed records already written to PG. Keep their handling BLOCKED until a separately
reviewed copy and per-file reconciliation are available. A review manifest is a JSON list:

```json
[{"file":"reviewed-event.json","sha256":"REVIEWED_SHA256","decision":"import_new"}]
```

Use `already_in_database` for reconciled records that must not be imported. Hash, filename,
record shape and all decisions are validated before any new writes. Review at most 1,000
files per manifest; each file/manifest is at most 256 KiB. No contents are printed. From the
application directory, after authorization for the reviewed copy:

```bash
python -B -m app.observability.legacy_audit --source /reviewed/copy --review /reviewed/manifest.json
# Only after reviewing PLAN_ONLY and the exact target:
python -B -m app.observability.legacy_audit --source /reviewed/copy --review /reviewed/manifest.json --apply-to-retained-store /isolated/audit/state.sqlite3
```

These commands were not executed. Repeated imports of the same filename/hash use a stable
UUID5. Renaming/changing the source changes that identity; reconcile such copies manually.
This cannot retroactively deduplicate old PG records without event IDs. Import retains a
redacted new event; it does not sanitize, remove or alter the historical original.

## Correlation and metric semantics

For responses sent through it, the ASGI boundary creates a server-owned request ID and
returns `X-Request-ID`; supplied
client IDs do not become the identity. Context variables reset after each request/task.
New audit rows carry request ID, current valid trace ID and task ID where available.
Approval-transition payloads include correlation alongside approval/execution IDs; those
legacy transactional rows do not use the new outbox or backfill dedicated ID columns.
Tool payload `workflow_request_id` preserves the graph's distinct operation identity.
Enqueued jobs store originating request/trace IDs. Worker spans include task ID, queue,
scope and originating trace as attributes, and audit start/handler-return/interruption.
`handler_returned` does not assert queue commit or external business success.

FastAPI instrumentation is registered before middleware-stack construction; the tracing
SDK starts in lifespan. Optional tracing absence yields null trace IDs; request/task
correlation still works. Worker spans have an origin attribute, not automatically propagated
parent context. Real exported traces and joins require O09; no distributed trace claim is made.

| Metric | Unit / labels | Interpretation |
| --- | --- | --- |
| `agent_http_request_latency_seconds` | Histogram, seconds; method/path/status | Through final body send (SSE included); interrupted streams end at interruption |
| `agent_http_response_start_seconds` | Histogram, seconds; method/path | Response headers, **not** LLM TTFT |
| `agent_http_outcomes_total` | Counter; method/path/outcome | complete/disconnected/aborted transport; HTTP 200 plus business error can still be complete |
| `agent_dependency_ready` | Gauge; fixed component | Latest observed readiness, 0/1 |
| `agent_audit_pending` | Gauge, events | Shared-store pending count; -1 unavailable |
| `agent_audit_oldest_seconds` | Gauge, seconds | Shared-store oldest pending age; -1 unavailable |
| `agent_llm_tokens_total` | Counter; model/token_type | Existing callback-produced token totals; do not add total to prompt+completion |

Paths are registered route templates, `/ui/{asset}`, or `__unmatched__`. Request/session/
user/task IDs and arbitrary raw paths never become metric labels. Methods outside the fixed
HTTP set map to OTHER. Latency buckets extend to 300 seconds; longer samples enter +Inf.
Full-body timing excludes background work after the final response body. An exception that
escapes user middleware records status 500/aborted at the failure boundary; a later framework
error response is outside that observation and may lack this header. A disconnected
client may be classified aborted if the framework never delivers an ASGI disconnect event.

Unproduced historical quality/session/node/error/Saga metric families were removed; zero
samples are not evidence of quality or success. C17's report is the RAG-quality oracle.
Existing HTTP 5xx ratios measure response status, not SSE business outcomes or measured SLA.
Non-SSE latency rules exclude the stream route; no throughput/load acceptance is implied.

Each API process/container and worker must be scraped separately. The candidate keeps one
Uvicorn worker per API container; use `prometheus-dual-api.yml` for api/api2/worker targets.
Do not enable extra hidden Uvicorn workers and assume one scrape aggregates them. Sum rates
of independent request/token counters; use **max**, never sum, for shared audit backlog/age.
Retain instance labels for readiness and scrape failures. Memory registries reset on restart.

## Controlled alert receipt and isolated recipe

The opt-in monitor polls fixed internal readiness targets, with five-second HTTP timeouts,
64 KiB response limits, no redirects/proxy inheritance and a ten-second interval after each
cycle. It retains each firing/resolved transition atomically with its condition state.
Initial healthy state creates no fabricated recovery. It POSTs only fixed fields (UUID,
condition, state) to the independent receiver; retries keep the same UUID. Unknown/invalid
acknowledgement stops the ordered batch so recovery cannot overtake its earlier fault.
The receiver checks the environment-supplied 32+ character token, bounds request bodies to
1 KiB, retains an idempotent receipt, then acknowledges. Authenticated GET `/receipts`
returns the latest 100 retained receipts; for a larger history inspect the retained store
through an authorized read-only session. No business payload, email or enterprise notifier.

Prometheus rules are a separate local evaluation path. No Alertmanager forwarding is
configured: a Prometheus rule firing does not prove receipt in this controlled receiver.
The monitor observes component availability and audit lag, not every Prometheus threshold.
If the monitor itself stops, it cannot report itself; inspect container/process/log evidence
and record the outage. An independent external watchdog and enterprise notification routing
are outside this candidate's claim. Neither monitor nor receiver has a Docker health probe.

Planned commands below are **not executed**. They require a reviewed immutable image,
explicit migration 7, isolated Linux/Docker, separately provisioned non-secret config and
secret environment, and a review of existing image/runtime side effects. Do not start this
on the developer machine. Do not print the environment, token, or resolved Compose secrets.
From `enterprise-agent/`, set `CONTROLLED_ALERT_TOKEN` through the approved secret facility:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml -f deploy/docker-compose.observability.yml -f deploy/docker-compose.observability-dual.yml --profile monitoring config --format json | python -B scripts/check_deployment_contract.py
docker compose --env-file .env.prod -f docker-compose.prod.yml -f deploy/docker-compose.observability.yml -f deploy/docker-compose.observability-dual.yml --profile monitoring up -d --no-build
```

A static contract PASS is not Compose rendering/build/runtime evidence. The checker also
checks api2 when present. O13 must verify actual resolved paths, mounts, identities, target
labels and all three scrapes. Nginx still routes to api; api2 is an internal acceptance target,
not load balancing or a new HA promise. Access receiver receipts from an approved internal
client that reads the token from its environment and omits it from logs/command arguments.
Retain monitoring/receiver volumes independently. No `down`, `--rm`, removal or cleanup is
part of this procedure. Other historic backup/rotation paths remain separately restricted.

## Frozen real acceptance matrix

All cases are **BLOCKED** until isolated execution with evidence. For each retain commit,
image digest, resolved non-secret configuration hashes, versions, UTC times, exact injection
and restoration steps, expected/actual counts and independent durable records. A transcript
or operator's unchecked PASS label cannot replace the oracle. No case was run here.

| ID | Required experiment and PASS oracle | Status |
| --- | --- | --- |
| O01 | Start manifest-v7 candidate; API/worker health and ready agree with initialized capabilities; no raw diagnostic/credential output | BLOCKED |
| O02 | Fail/restore PG, Redis, Milvus and checkpoint separately; each required failure yields bounded 503 and genuine recovery yields 200 | BLOCKED |
| O03 | Remove required tool registration and stop either consumer; readiness fails; worker UUID/75-second expiry is observed; clean SIGTERM closes children | BLOCKED |
| O04 | PG unavailable, new audits retained; recovery replays each accepted event ID once, with original occurrence/correlation and redacted contents | BLOCKED |
| O05 | Lose PG commit response/local acknowledgement; concurrent replay still produces one PG row per stable event; original local row retained | BLOCKED |
| O06 | Abrupt API/worker restart across shared physical volume; acknowledged/pending records survive; no missing accepted IDs or harmful lock contention | BLOCKED |
| O07 | Poison event, oversized payload, read-only/full disk and both-storage failure; later valid events progress, failures remain visible, any unretained event is an explicit FAIL for zero-loss acceptance | BLOCKED |
| O08 | Approved historical-copy reconciliation/import; hashes, decisions and repeats match expected records without duplicate old PG events or original-file mutation | BLOCKED |
| O09 | Actual HTTP/tool/approval/queue/worker operation joined by request/workflow/approval/execution/task/trace fields; exported trace origin relationship observable | BLOCKED |
| O10 | Vary arbitrary paths and IDs; metric family cardinality stays bounded and no identifiers/secrets appear; absent producers not shown as measured zero | BLOCKED |
| O11 | Timed ordinary and SSE final-body, business-error and interrupted responses; headers/full duration and transport/status semantics match external timestamps | BLOCKED |
| O12 | Real Prometheus loads rules; inject readiness/audit-lag/scrape faults; alert firing/resolution matches windows, not a fabricated SLA result | BLOCKED |
| O13 | Two independent single-worker APIs plus worker produce distinct scrapes; sum counters/max shared gauges matches independent ledger; no missing process | BLOCKED |
| O14 | Receiver outage, lost acknowledgement and monitor/receiver restart retain pending/order/identity; each repeated delivery has one independent receipt | BLOCKED |
| O15 | Actual component failure then recovery produces matching firing/resolved receiver records; invalid token rejected; monitor outage is explicitly detected by operator/external evidence | BLOCKED |
| O16 | Candidate-image filesystem/process trace confirms approved non-deleting audit/monitor/receiver behavior, permissions, PERSIST/FULL and physical durability under faults; retain all artifacts | BLOCKED |

O01–O16 are C21 evidence, not permission to run, deploy, push, archive, start C22, or close
B/S/R/full-RAG gates. A real failure remains FAIL until repaired/retested; no post-hoc threshold
change. C21 cannot close while any required case or known material gap remains unresolved.

## Design references

[SQLite atomic commit](https://www.sqlite.org/atomiccommit.html) and
[PRAGMA reference](https://www.sqlite.org/pragma.html) explain the selected journal/sync
mechanisms; they do not validate this image/filesystem. [Starlette middleware](https://www.starlette.io/middleware/)
explains ASGI ordering and context considerations. [Uvicorn 0.30 server source](https://github.com/encode/uvicorn/blob/0.30.0/uvicorn/server.py)
shows signal ownership that the embedded worker server delegates to its supervisor.
[Prometheus instrumentation](https://prometheus.io/docs/practices/instrumentation/) and
[naming guidance](https://prometheus.io/docs/practices/naming/) inform units and bounded labels.
