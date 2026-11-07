# Analysis data adapter contract

C16 offline candidate, 2026-10-17. Actual CRM/PostgreSQL/JWT/API/SSE/Linux
acceptance remains **BLOCKED**. This is not enterprise-source or report-quality evidence.

C18 now supplies an [independent CRM service candidate](reference-integration.md);
its in-memory contract checks do not close the real snapshot or application acceptance gate.

## Application behavior

Analysis uses QueryOrderTool's effective provider: CRM_TOOL_PROVIDER when set,
otherwise TOOL_PROVIDER. Mock reads the same built-in order/customer fixtures as query
tools and labels every report as synthetic. HTTP uses the same CRM base, service token,
reference profile and run as query tools. Unknown providers, missing configuration,
transport errors and invalid records never fall back to Mock or partial totals.

The executor passes the authenticated user's ID and original message to AnalysisAgent;
a model-generated subtask cannot silently replace the requested dates or customer IDs.
Current database identity is checked before loading, before each page, after loading and
before report delivery. A missing, disabled, changed-role/department or unavailable identity
fails closed, including in development. Order permission is required. Customer permission
controls the separate customer read; finance derives grouping IDs only from authorized
orders and never loads the customer directory or lifetime sales.

The reference profile is single-organization and retains the existing tool-level
permission model: order permission allows the run's orders. This is not department,
sales-owner or tenant row-level isolation. Service credentials do not substitute for
application authorization. No role or JWT is sent as a service credential. A completed
authorization check cannot retroactively revoke already-delivered output.

## Supported query and arithmetic scope

- Deterministic customer grouping, order count and original order amount; comparisons
  are side-by-side rows, not generated prose or inferred causal conclusions.
- Select C-prefixed numeric IDs such as C001, or use `customer:opaque-id` /
  `客户=opaque-id`. Known order customer IDs are also recognized literally.
  Unknown explicit IDs fail rather than broadening to all customers. Name-only entity
  resolution is unsupported; use IDs. No ID means all available orders.
- An explicit pair of ISO dates (for example `2026-01-01 至 2026-06-30`) means an
  inclusive UTC calendar-date interval on order creation. No period means all available
  dates, explicitly labeled in the report. Relative periods, partial dates, year-only
  requests and time comparisons are rejected. The parser is intentionally bounded,
  not a general natural-language date interpreter.
- By default all pending/completed/cancelled/refunded orders are included. Explicit
  `pending` / `待处理`, `completed` / `已完成`, `cancelled` / `已取消`,
  `refunded` / `已退款` select those statuses. Exclusion syntax is rejected.
- Money is nonnegative integer minor units, bounded to 100,000,000,000,000 per order.
  Sum integers; format using Decimal only at presentation. The reference schema fixes
  two decimal places for every supported currency; different currency codes never sum
  together. This is a reference convention, not a general ISO currency-exponent adapter.
- Cancelled/refunded original amounts are not automatically negated. Amount is **not net
  revenue**. Lifetime revenue is unavailable, not approximated from orders. Revenue,
  rankings, industry/distribution, averages, ratios and trend requests return
  ANALYSIS_METRIC_UNSUPPORTED; no fabricated or silent alternative statistic.
- Empty complete results return success with stage analysis_empty, coverage none and no
  replan. Data/authority failures return analysis_blocked, fixed code and no data field.
  Deterministic reports include requested/observed dates, included statuses, provider,
  snapshot/as-of/fetch timestamps and currency semantics.
- Neither parsing nor report generation calls a model. Multi-agent aggregation containing
  an analysis result concatenates original answers, preserving facts and failures rather
  than rewriting them. General planner/model routing still exists; actual end-to-end
  routing/SSE acceptance is not proven by these unit checks.

Old LLM report/multi-hop behavior and lifetime-sales examples no longer describe this
candidate. The legacy standalone analysis eval lacks authenticated identity and is not
an acceptance entry. This increment does not run or rewrite historical evaluation data.

## Reference HTTP extension: crm-analysis-v1

This is an additive, separately versioned extension to
[business-reference-v1](reference-business-contract.md). Existing mutation receipts and
C12/C13 semantics remain unchanged. The independent service is **not implemented or
deployed in this increment**. C18 must implement and verify these routes.

Routes relative to CRM_API_BASE:

| Route | Contract |
| --- | --- |
| GET /analysis/orders | First request creates/adopts an immutable read snapshot; returns order pages |
| GET /analysis/customers | Requires that order snapshot ID; returns customer projection from the same snapshot |

All existing service-authentication, isolated run/principal binding, no redirects,
64 KiB strict JSON, X-Reference-Run-Id and X-Reference-Profile rules apply. Request
query: limit=100, optional cursor, optional snapshot_id, and either both start_date and
end_date or neither. Cursors and snapshot IDs use ASCII letters/digits/underscore/hyphen,
1–64 characters; they are encoded as query values, never followed as URLs.
The initial orders request has no snapshot ID; every subsequent page/resource binds
the accepted snapshot. Subsequent retries must not move to a new snapshot.

Each successful response is HTTP 200 with exactly:

```json
{
  "schema": "crm-analysis-v1",
  "run_id": "<configured-run-uuid>",
  "snapshot_id": "<opaque-id>",
  "as_of": "2026-10-17T12:00:00Z",
  "range": {"start_date": null, "end_date": null},
  "items": [],
  "total": 0,
  "next_cursor": null
}
```

The timestamp is a synthetic shape example, not an actual observation. as_of is UTC,
immutable across both resources/pages. range echoes the exact requested interval.
total is the total count for that resource, constant on every page. Orders must lie
within the interval; customers may include the full run directory so every selected
order can be joined when authorized. Snapshot identity, as-of and run are common to
both resources; total is per resource. Orders and customers are unique by primary ID.
An empty page cannot have a next cursor. The final accumulated count must equal total.

Order item fields are exactly order_id, customer_id, amount_minor, currency, status,
version and created_at. IDs follow the reference resource grammar; version is integer
>=1; amount_minor is integer (not bool/float/string); currency is three uppercase ASCII
letters; status uses the four values above; created_at is canonical YYYY-MM-DD.
The snapshot reads the same records and versions as B02; B02 may expose created_at as
an additional field without changing its existing required fields.

Customer item fields are exactly customer_id, name, level, version. Name/level are
nonempty strings <=200 characters without control characters. No contact details,
email, lifetime revenue or additional payload is returned. When customer reading is
allowed, every order customer must exist in that snapshot. Finance needs no such
directory read. Customer names are escaped for Markdown/HTML presentation.

At most 100 records per page, 50 pages and 5,000 rows per resource; a 30-second deadline
covers authorization and loading. Existing HTTP transport uses <=5 seconds per attempt,
at most two retries for GET and a 64 KiB response bound. Count/cursor loops, duplicate
IDs, mismatched schema/run/range/snapshot/time, malformed fields, missing customer joins
and bounds reject the entire report. An expired snapshot returns 409/410; auth failures
401/403; none can cause an automatic new snapshot after partial acceptance.
No cache or durable analytics snapshot is stored in BusinessAgent.

## Isolated acceptance still required

| Scenario | Required runtime evidence |
| --- | --- |
| Same run query and analysis | Change seeded records; B01/B02 versions and aggregate amounts follow the same source |
| Multiple pages and concurrent service updates | Frozen snapshot consistency across both resources; no missing or duplicated rows |
| Expiry, partial response, timeout, restart, 401/403/5xx | Fixed error, no partial report or Mock fallback |
| JWT role/department change, disabled user, PG outage | No unauthorized source access or delivery; finance never calls customer route |
| Empty/date/status/multiple-currency data | Exact integer totals and clear scope; no revenue approximation |
| Application chat, multi-agent, SSE and browser | Original scoped request and deterministic report survive the complete path |
| Limits and load | Measure deadlines/memory/latency; no unmeasured enterprise capacity claim |

C16 remains open. Full pytest and strict OpenSpec CLI remain BLOCKED locally. C15 full
RAG/runtime blockers remain, C10 write race remains open, and audit replay remains C21.
No live calls, dependencies, migrations, deletion, deployment or release were performed.
