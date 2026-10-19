# Frozen capacity evidence

C23 offline candidate, 2026-10-19. **L01–L16 runtime acceptance: BLOCKED.**
C22 `d70c1b4` is pushed and verified. This increment does not execute load, services,
paid models, Docker or current databases. C23 remains open; C10 fencing stays open.
D/O/B/S/R, complete runtime/RAG, enterprise UAT and release gates remain unchanged.

## Candidate and execution boundary

`capacity/contract.py` validates frozen plans and computes conservative reports.
`capacity/runner.py` supplies an opt-in standard-library workload through the application
HTTPS entry and the independent reference mail ledger. `eval/run_capacity.py` is the
local CLI; `eval/run_load_test.sh` now delegates to it, with no defaults, Docker fallback,
mutable image pull or automatic cleanup. `deploy/Dockerfile.capacity` packages the runner
on an explicitly supplied application image; no new dependency is introduced.

The old k6 script and renderer remain historical artifacts. k6 now requires explicit
historical acknowledgment, target, credentials and users; it is not C23 acceptance.
The legacy renderer rejects missing/non-boolean threshold evidence and writes a fresh
report exclusively. Historical health-heavy throughput and old passes are not current
business capacity. No historical acceptance record is rewritten.

The runtime candidate uses only `https://nginx:443` for application calls and
`http://reference-mail:8081` for private operator evidence. The certificate must include
`nginx` in its SAN; mount the reviewed CA read-only and set `CAPACITY_CA_FILE`. Normal
TLS/hostname verification stays enabled. No insecure flag, public target, redirect,
proxy forwarding, direct tool invocation or application bypass is supported. Fixed DNS
names and operator-controlled network isolation remain trust boundaries.

A valid plan plus `--execute --approved-plan-sha256 <exact digest>` is necessary. The
hash is an operator assertion of prior review, not a signature or authorization system.
A new output directory in an existing non-symlink parent is mandatory; reports/slots
use exclusive creation and file fsync. Keep manifests, interrupted slots, completed
containers, source plans and all service records. No reset, overwrite or deletion path
exists. Do not run this candidate against current or enterprise state.

## Proposed first load point, not confirmed runtime parameters

The [draft plan](../../enterprise-agent/eval/capacity-plan.example.json) intentionally
contains null environment/image/data fields and unresolved knowledge oracles. It rejects
execution as-is. Replace them in a separately retained private plan after inspecting the
actual isolated candidate. Never put passwords, tokens or real customer text in a plan.

| Frozen dimension | Initial proposal / required actual evidence |
| --- | --- |
| Candidate | Exact 40-character Git commit; application, reference and capacity image digests; schema-manifest SHA-256 |
| Hardware/processes | Actual Linux platform/CPU/core count/RAM/storage, API and worker processes; SHA-256 of reviewed topology/resource-limit inventory |
| Models | Beijing `text-embedding-v4`/`qwen3-rerank`, DeepSeek `deepseek-flash` and `deepseek-v4-pro`; actual versions, quotas and spend authorization in hashed review |
| Data | Published corpus manifest, document/chunk counts, CRM order count, fresh provisioned reference run, mail store UUID/fixture hash and principal |
| Roles | Three distinct manager requesters, another manager approver and an administrator observer; no role grants by runner |
| Duration/rate | 1800 seconds, one arrival every 5 seconds, three fixed requester lanes, no automatic warm-up |
| Mix | Deterministic cycle Q&A, Q&A, analysis, Q&A, approved mail: 216 / 72 / 72 scheduled flows |
| Minimum | At least 60 scheduled observations per type in this proposed point; actual recorded and failed/missing counts reported separately |
| Timing bounds | 120-second socket/read budget per HTTP phase, <=250 ms launch lag, 720-second drain after the steady window |
| Baseline | Per type/HTTP phase p95 <=2000 ms, p99 <=5000 ms, error rate strictly <0.005; no post-run relaxation |

This is a small **initial load point**, not a maximum capacity claim or a simulated
enterprise traffic model. A 72-sample p99 is effectively its largest observed sample;
zero errors at this count does not establish a high-confidence long-term error bound.
Select larger populations/longer windows/other load points before execution if needed;
retain every point, including failures. Preflight login/identity/reference checks are
outside the measurement window; application caches are not reset or warmed automatically.
Record pre-existing cache/index state with the environment evidence.

The existing limiter shares user keys across routes. Chat uses 30/min, login uses 10/min;
admin/approval/default routes can have other limits. Account/IP, Nginx 30r/s and provider
quota effects must all be frozen and verified. This runner does not disable or tune them.
Preflight performs five logins for the default three lanes. Tokens must outlive the run
and drain; expired identity becomes a measured failure, never a hidden refresh/retry.
Provider billing includes all planner/generator/embedding/rerank/retry calls inside the
application. Set account spend limits and stop criteria externally before any paid run;
this collector has no billing API or automatic cost cutoff.

## Business oracles and timing

Every flow omits `session_id`, asking the application for a fresh session. A fixed lane
uses one requester; if its previous request is still active, the new arrival is recorded
DROPPED, without queuing it into an easier closed-loop load. Late launches are also dropped.
No health requests enter business throughput, and no business request is retried by the
collector. The application's own retry policy remains part of the measured candidate.

- Q&A requires `knowledge_qa`, a nonempty answer, no replan, expected text markers and
  exclusively allowed published document IDs. These are mechanical checks, not semantic
  correctness or C17 permission/quality acceptance. Bind prompts/oracles to actual corpus.
- Analysis requires `data_analysis`, no replan and frozen expected markers. The draft
  baseline reference fixture has two orders totaling CNY 1,300.49; independently verify
  exact per-customer/currency/date values and snapshot identity. A variant or larger fixture
  requires different oracles **before** the run. Text markers cannot prove full correctness.
- Approved business uses a fixed synthetic external message to `customer@reference.invalid`.
  It observes exactly one pending external-mail approval, uses the distinct approver to
  decide, then the requester to resume once. Require `executed`, exactly one committed
  application operation, matching independent run/store/hash/receipt, one committed attempt,
  a captured external resource with the exact recipient and no cc/attachments, and successful
  tool audit. Missing/delayed evidence is failure; HTTP 200 alone never satisfies the oracle.
  This fixture is synchronous: extra queued/Saga steps reject this specific oracle rather
  than silently accepting a different business flow. The sink has no SMTP delivery.

Client monotonic timing records first nonempty user-facing SSE **token event**, complete
HTTP body, each HTTP phase and the full workflow including observation overhead. Headers,
progress and a final-only event do not establish TTFT. Parser errors, duplicate final events,
invalid UTF-8/JSON, unfinished events and stream error/cancel events fail. SSE parsing and
8 MiB total-body limits apply before any content is retained; event size is limited to 1 MiB.

Application phases are `/chat/stream`, admin evidence, decision and resume; independent
mail ledger reads are explicitly labelled `mail_ledger`. IDs never enter metric labels.
A non-200 response is counted immediately at headers, with its full-body duration **censored**;
the body is neither drained nor logged. Timeouts/disconnects are likewise censored at the
phase level. The workflow still records elapsed time to failure. DNS resolution and host
scheduling can exceed Python socket budgets; real bounded-stop behavior is L14, not an
OS-level real-time guarantee. There is no automatic mutation cancellation/replay after an
uncertain response. Reconcile retained approval/provider state before any later workload.

Percentiles use nearest rank, exposing sample counts and missing/censored observations.
Failures and unrecorded/dropped slots stay in the **scheduled flow denominator**. HTTP
phase failure rates have their own attempted-request denominator, not the flow denominator.
429s are reported separately and count as failures. TTFT and full durations cannot substitute
for each other. `business_per_second` counts only successful flows completed within the
steady 1800-second window; later successes are reported as drain completions separately.
All-success within the historical baseline yields OBSERVED, never complete acceptance.
Runtime breaches yield FAIL; synthetic fixtures can only yield offline observations.
Preflight failure before a `started.json` marker is NOT_STARTED/BLOCKED, not measured capacity.

The report deliberately says `queue_latency=NOT_OBSERVED` and
`execution_latency=NOT_OBSERVED`. HTTP resume duration is not a server execution-only timer.
The synchronous mail workload cannot measure worker throughput. L11 requires separately
reviewed async-job timestamps under mixed load (enqueue/claim/start/finish with a defined
clock and retry semantics); missing timestamps cannot become zero. C21 exposes dependency/
backlog gauges but no per-job timing series or CPU/RSS exporter. Resource and async timing
collection remain explicit runtime prerequisites, not features claimed by this collector.

## Future isolated execution procedure (not authorized or run here)

1. Resolve relevant C01–C22 runtime prerequisites, including C10 risk review; retain the actual
   image/schema/corpus/topology identities and model funding/quota approval. Provision a fresh
   synthetic reference run through C18's separate procedure; do not reuse/erase an old run.
   All requester/approver IDs must belong to its allowlist. Ready/CONFIGURED is not acceptance.
2. Prepare the private plan and review the workload/thresholds with the user. Run plan-only:

   ```bash
   python3 -I -B enterprise-agent/eval/run_capacity.py --plan /reviewed/capacity-plan.json
   ```

   It returns the canonical digest, scheduled count and BLOCKED/NOT_RUN (exit 2), without
   constructing a client or writing files. Invalid/unresolved plans return a fixed error.
3. Build `Dockerfile.capacity` only in the isolated build context with the exact application
   digest as `BUSINESSAGENT_IMAGE`. Record the resulting capacity image digest in the plan.
   Run its image on reviewed production+reference networks with non-root UID, read-only root,
   dropped capabilities, no-new-privileges, no exposed port, a writable private retained output
   mount and read-only plan/CA mounts. Do not start the application through this image.
4. Supply only private environment values: `CAPACITY_OPERATOR_TOKEN`,
   `CAPACITY_ADMIN_USERNAME/PASSWORD`, `CAPACITY_APPROVER_USERNAME/PASSWORD`, and
   `CAPACITY_REQUESTER_0_USERNAME/PASSWORD` through `CAPACITY_REQUESTER_2_USERNAME/PASSWORD`
   for the default lanes. For a confirmed larger concurrency, supply matching extra lanes.
   Do not put credentials in arguments, plans or reports. A separate env file may be mounted
   via the operator's reviewed container command; never print its content.
5. Inside that already reviewed runtime, the image entrypoint accepts:

   ```text
   --plan /reviewed/capacity-plan.json --execute
   --approved-plan-sha256 <confirmed-canonical-digest> --output /data/new-capacity-run
   ```

   Explicit execution creates a fresh directory before preflight. It may write persistent
   sessions/checkpoints/audit/approvals/reference mail and call paid providers. It provisions
   nothing, cannot roll back uncertain business effects and keeps all outputs. Host/process
   kill can leave only partial slot files; no success receipt is synthesized.
6. Independently retain per-process resource time series (CPU, RSS, disk I/O/free space,
   network), PG connections/locks, Redis/Milvus observations, queue depth/oldest age and audit
   backlog at a frozen cadence (proposed <=5 s), covering baseline, full run and drain.
   Observe provider quotas/billing and all API/worker scrapes, with clock synchronization and
   source hashes. Record recovery to the pre-run backlog/resource baseline and time to drain;
   end-of-load is not proof of recovery. The collector does not deploy resource exporters.
7. Rebuild a report from retained files without HTTP:

   ```bash
   python3 -I -B enterprise-agent/eval/run_capacity.py \
     --plan /reviewed/capacity-plan.json --summarize /retained/capacity-run
   ```

   It verifies plan identity, rejects duplicate/out-of-range slots and prints JSON only.
   Preserve the original report; a missing finished marker is incomplete. Offline reports
   are unsigned observations, not proof of live execution or independent review.

Output contains hashes/allowlisted status and timing fields, not answer bodies, prompts,
service resource text, passwords, JWTs or exception messages. Operators must separately
retain private semantic evidence under approved custody and attach only sanitized references.

## L01–L16 runtime matrix

Every row is **BLOCKED** for this increment. Record expected/actual results, timestamps,
source hashes and candidate identity for every subcase; do not promote code/tests to PASS.

| Case | Required evidence and acceptance |
| --- | --- |
| L01 | Actual immutable application/reference/collector images, schema, hardware/process/storage/network inventory match the pre-approved plan |
| L02 | Actual model endpoints/versions, account quotas, spend cap, token TTL and limiter policies match the frozen review; no hidden bypass |
| L03 | Published corpus/ACL/fixture identity and document/chunk/order counts; nontrivial reviewed Q&A and exact analysis oracles |
| L04 | Distinct current requester/approver/admin identities, private TLS, isolated sink/no egress, fresh run and retained asset policy |
| L05 | >=1800 s steady open-loop mixed run; exact scheduled mix/minimums/concurrency; all launched/dropped/missing slots retained |
| L06 | Q&A factual/citation/ACL review bound to observation hashes, no refusal/fallback disguised as an answer |
| L07 | Analysis exact numbers, currency/date/snapshot and source agreement; no mock fallback or answer-marker-only acceptance |
| L08 | Approved mail through real planning/decision/fresh resume, one effect and matching durable audit/independent receipt per successful flow |
| L09 | Raw HTTP/SSE/client/server timing comparison; real TTFT separate from headers/full response and observer overhead |
| L10 | Per-type and per-phase p95/p99/error/429/censor counts against frozen baseline; every breach FAIL, no post-hoc tuning |
| L11 | Reviewed asynchronous jobs during mixed load, actual queue and execution timestamps/retries; no HTTP-latency proxy for worker capacity |
| L12 | Full time series for every API/worker, CPU/RSS/disk/connections/locks/store health; distinguish bottlenecks from observer/load-generator saturation |
| L13 | Post-load queue/audit/resource recovery to baseline within the frozen drain window; unresolved/unknown actions independently reconciled |
| L14 | Real deadline/launch-lag/overload/429/token expiry/disconnect/interruption behavior; no runaway load/retries and retained partial evidence |
| L15 | Actual provider usage/cost/rate limits with complete scheduled denominator and attribution; no free/mock run presented as target-model capacity |
| L16 | Reviewed bound report with sample limitations, failed points, sustainable tested load and headroom; no maximum capacity/monthly SLA/UAT/release inference |

Full acceptance requires all applicable runtime rows and engineering baseline §5, not just
an OBSERVED report. No performance tuning or threshold relaxation has been justified by
measurements this turn. C23 is still open; await confirmation before C24 final work.
