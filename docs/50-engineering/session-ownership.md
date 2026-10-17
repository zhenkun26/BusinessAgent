# Chat session ownership contract

Date: 2026-10-17. C04 implementation and offline verification only; real
PostgreSQL, API/SSE and Linux deployment acceptance remain **BLOCKED**.
Implementation: [shared guard](../../enterprise-agent/app/security/session_access.py)
and [chat endpoints](../../enterprise-agent/app/api/chat.py).

## Access matrix

The authenticated identity comes from the existing `get_current_user` dependency.
For a supplied session ID, `sessions.user_id` is the ownership authority. A guessed
ID, matching ID prefix, same department, manager role or checkpoint presence grants
no access. IDs are opaque; existing valid owned IDs remain supported.

| Endpoint under `/api/v1/chat` | Owner | Other user / manager | Administrator targeting another user |
| --- | --- | --- | --- |
| `POST /message` with existing ID | Continue | 404 | 404 |
| `POST /stream` with existing ID | Continue with SSE | 404 before SSE response | 404 before SSE response |
| `GET /history/{session_id}` | Read checkpoint or owned status fallback | 404 | 404 |
| `POST /feedback` | Record feedback and optional draft | 404 | 404 |
| `POST /cancel` | Request cancellation | 404 | Request cancellation, preserving the existing explicit exception |

Administrators can use all five endpoints on their own sessions. Cancellation is
best-effort within the API process; `cancelled=false` means no cancellable local
task was found. It is not evidence of cross-worker cancellation or rollback of
already executed tools. This matrix does not change approval or administrative
knowledge-review permissions.

## New and existing session behavior

To start a conversation, omit `session_id` or send null. The server generates
`sess_` plus a full UUID hex string (37 characters), stores the authenticated
owner and commits before graph work. The ID contains no user identifier. Save the
returned ID for continuation; the UI already omits its empty local ID.

An explicit unknown, empty or oversized ID is rejected. Message/stream no longer
create rows for caller-chosen IDs. Feedback no longer creates placeholder rows;
it must reference a conversation already owned by the caller. These are deliberate
compatibility changes for external clients that previously supplied arbitrary IDs.
Orphan checkpoints without a session row cannot be read or adopted. No historical
rows/checkpoints are migrated, deleted or automatically repaired.

| Response | Meaning | Side effects |
| --- | --- | --- |
| 404, `detail=SESSION_NOT_AVAILABLE` | Missing, foreign, empty or oversized string ID | No graph/checkpoint access, stream producer/response, cancellation, request audit, session/feedback/draft mutation |
| 503, `detail=SESSION_ACCESS_UNAVAILABLE` | Ownership query or chat-session preparation failed | No graph/SSE or request audit; failed preparation rolls back where possible; no raw driver text |
| 409, `detail=SESSION_CREATION_CONFLICT` | Server-generated ID collided with a row | Existing row is not overwritten or adopted; no graph/SSE or request audit |

Missing and unauthorized IDs have identical status/detail for each endpoint.
This is a response-content guarantee, not a constant-time timing guarantee.
Framework-level malformed JSON/type validation remains FastAPI/Pydantic behavior
and needs real-runtime acceptance. A network failure during commit can leave the
commit outcome uncertain; C04 does not implement request idempotency or silently
retry writes. Error detail contains neither the queried ID nor its owner/status.

## Transaction and side-effect boundary

Both message paths use the same preparation helper. Existing-session lookup is
followed by an UPDATE with both session and user predicates and RETURNING; a changed
owner/missing row at update time fails instead of running the graph. New insertion
uses DO NOTHING/RETURNING on conflict, never the old unconditional upsert.
Authorization and preparation are outside broad graph exception handlers.

History authorizes before obtaining a checkpointer. On checkpoint miss, it returns
the status from that already authorized lookup, without a second unrestricted
query. Feedback and cancel use `FOR SHARE`; feedback holds the row lock in the
request transaction through its feedback/draft commit, and cancel holds it until
request-session teardown. PostgreSQL documents that this shared row lock blocks
concurrent row updates/deletes until transaction completion
([PostgreSQL 16 row locks](https://www.postgresql.org/docs/16/explicit-locking.html#LOCKING-ROWS)).
The offline tests check the requested lock clause and ordering, not real lock timing.

Application session ownership is immutable; no API here reassigns it. Direct
database ownership changes during active graph/history work are unsupported.
Operational writers must be quiesced before any separately reviewed repair.
Existing private checkpoints may already contain historical data; this increment
enforces access but does not certify or repair old contents.

## Offline verification and remaining acceptance

Run from the repository root using the existing Python 3.11+ interpreter:

```bash
python3 -I -B enterprise-agent/eval/run_c04_session_ownership.py
```

The [20-test suite](../../enterprise-agent/tests/test_session_ownership.py) loads
current source bytes, injects framework/database/graph/audit dependencies and uses
the actual cancellation registry in memory. It covers both user directions,
manager/admin policies, missing/foreign equivalence, malformed ID bounds, SQL
parameterization, orphan checkpoints, database failures, write/commit failures,
legal message/SSE/history/feedback/cancel flows, ID collisions and a simulated
lookup/update ownership change. Assertions include unchanged session/feedback/draft
snapshots and no checkpoint access or other business side effects on rejection.
There is no real HTTP server, PostgreSQL engine, identity provider, LLM or filesystem
cleanup. No new dependency is needed; the suite is also discoverable by existing CI.

Before closing C04, separately authorize an isolated candidate and verify:

1. Two synthetic accounts A/B, a manager and an administrator against all five
   real routes. Preserve before/after digests of session, checkpoint, feedback and
   draft data; cross-user rejection must change none of them. No personal data.
2. First message without ID, own continuation, actual streamed events, history hit
   and miss, positive/negative feedback, owner/admin cancellation and all other
   administrator denials. Verify HTTP errors precede SSE headers/events.
3. PostgreSQL transaction/locking behavior, lookup/update races, commit failures,
   row-lock release on exceptions and unchanged data after rejected requests.
4. Fixed error payloads for unavailable ownership storage and missing/foreign IDs;
   sanitized logs/evidence with candidate commit/image and exact configuration.

The current JWT/identity fallback and role freshness risks remain C05. Checkpoint
request scoping, concurrent runs and cross-process task cancellation remain
C08/C09/C10; general error redaction remains C06. Existing wider pytest/eval and
OpenSpec strict CLI checks are still unavailable locally. Passing this offline
suite does not close those items, formal UAT or release gates.
