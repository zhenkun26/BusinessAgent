# Knowledge publication and index consistency

C15 offline candidate, 2026-10-17. Real PostgreSQL/Milvus/Linux acceptance and full
RAG quality regression remain **BLOCKED**. No enterprise production claim is made.

## Publication boundary

The PostgreSQL document ledger is the visibility authority. Migration 006 adds retained
`knowledge_publications` and active/pending generation pointers on `documents`. API and
worker require manifest v6; v1–v5 bytes are unchanged. No migration ran this round.

1. Validate explicit ACL, namespace, document metadata and nonempty chunks. Freeze the
   content, metadata, chunk plan, embedding provider/model/dimension and splitter recipe.
2. In one transaction, lock the source document, create a staging generation, and mark
   it `indexing` with a pending pointer. The generation has a UUID; chunk keys combine
   that UUID and an ordinal. An uncertain commit acknowledgment stops before indexing.
3. Embed the frozen chunks and upsert their exact keys into the selected namespace.
   Require the complete count and matching primary keys, then flush. Missing partitions
   fail closed; there is no shared-company fallback. In-memory storage also replaces
   identical keys instead of appending duplicates, but remains development-only.
4. Lock and recheck the source snapshot, pending pointer and current reviewer. Only
   then atomically publish the generation, replace document metadata/current pointer,
   refresh PostgreSQL search text and insert a transition audit event. Failures propagate
   as fixed safe codes and preserve a staging record/error for reconciliation.

This is a visibility protocol, not a distributed transaction or proof that PostgreSQL
and Milvus commit together. Partial/unconfirmed writes may remain physically stored;
application retrieval cannot admit them without the active ledger generation. Milvus
upsert uses the existing ORM API and its mutation receipt; actual installed-version
behavior still needs isolated validation. [Milvus 2.4 ORM upsert reference](https://milvus.io/api-reference/pymilvus/v2.4.x/ORM/Collection/upsert.md).

## Updates, retries and deactivation

- Identical published input returns the retained count without embedding or indexing.
  Identical staging input retries the same generation/chunk keys. A changed input while
  indexing conflicts; it cannot replace an in-progress plan.
- A new version hides the old version while indexing. On activation only the new
  generation is eligible. Old vectors and publication records remain retained. An
  old version cannot be republished merely by replaying its old input.
- Feedback approval still queues a C14 task and returns 202. The worker binds the exact
  source hash, original reviewer and publication options; it rechecks authority before
  activation. Direct trusted CLI imports cannot bypass draft/rejected/queued/inactive
  states. CLI imports require explicit `--roles`; missing/empty ACL never means all roles.
- A knowledge task that may have executed still becomes retained `dead` under C14.
  There is no automatic queue replay/reset. An admin can explicitly retry a dead
  knowledge job; this creates a distinct retained task referencing the identical
  payload, and repeated retry of that parent returns the same child task. The original
  reviewer is not replaced by the retrying admin. Changed source/revoked reviewer blocks
  publication. Concurrent old/retry handlers may upsert the same immutable keys, but
  cannot activate a superseded/disabled generation. This is not C10 write fencing.
- Deactivation commits `inactive` and clears only the pending pointer, retaining data
  and the prior active pointer for history. Late activation then fails. Repeated
  deactivation is idempotent. No reactivation, destructive cleanup or generic task reset
  endpoint is introduced. A rejected candidate cannot be directly imported or approved.
- Rejection remains draft-only and now commits its conditional transition and audit
  together. Queued/indexing/active documents cannot be rejected as drafts.

## Retrieval and legacy compatibility

Every application degradation-chain request obtains a fresh PostgreSQL snapshot of
active published generations, scoped by role, namespace and document type. Vector
candidates must match an eligible chunk ID and its canonical document, text, title,
source URL, type and ACL **before reranking**. The same gate applies to returned results,
keyword scans and PostgreSQL fallback. No cached BM25 corpus bypasses this check.
PostgreSQL fallback searches chunks from the active generation instead of raw legacy
`documents.content`; an empty vector/keyword scan now also reaches that fallback.

There is no visibility cache. Missing database/schema, timeout, invalid snapshot or
capacity overflow fails closed before model calls. Direct synchronous retriever calls
outside a publication scope are rejected; production callers use the async degradation
chain. Low-level vector adapters are index primitives, not independent authorized APIs.
C07 ACL regression uses a visibility fixture to isolate ACL checks; C15 tests exercise
the actual visibility module and complete retrieval chain with injected stores/models.

Visibility is admitted at snapshot time. A request already admitted before deactivation
may finish; this does not retract prior answers or cancel in-flight requests. New requests
must reload the ledger. Post-filtering may reduce vector recall when old versions crowd
top-K; the fallback mitigates empty results but is not a quality guarantee.

Limits: at most 1,000 eligible documents and 10,000 chunks per request; at most 1,000
chunks per publication. Metadata respects vector-field UTF-8 byte limits. The existing
safe-payload guard also caps serialized document input at 64 KiB and rejects credentials.
These are bounded reference-profile limits, not measured enterprise capacity claims.
Embedding recipe changes while staging conflict rather than silently changing versions.

Historical documents without an active publication pointer are **not searchable** under
this contract, even if their old status says active. Rows/vectors are not deleted or
silently certified. Before isolated rollout, inventory legacy rows and explicitly
reimport/review intended active content with ACLs. Review legacy eval import commands
that omit `access_roles`; they now fail closed. A historical active row can be reimported
through trusted CLI; rejected/inactive rows require a separately approved lifecycle plan.

Inventory retained tasks before an upgrade as well. C15 normalizes a title-only candidate's
empty content to its title before hashing, keeping new publication retries stable after
activation. Pre-C15 queued title-only jobs retain their old hash and fail closed under
the new comparison; this increment does not rewrite or automatically replay them. Resolve
such legacy jobs through a separately reviewed reconciliation plan in the isolated rollout.

## Administrative API and operator workflow

All routes require the current admin role; credentials stay in the Authorization header.
These are documented operations for a separately authorized environment, not commands
executed during this offline increment.

| Route under `/api/v1/admin` | Meaning |
| --- | --- |
| `GET /documents?status=indexing` | Locate unfinished ledger entries |
| `GET /documents/{document_id}/publications` | Up to 50 newest generation IDs, state, error, count, timestamps and current-pointer flag; no content/ACL payload |
| `GET /task-jobs?state=dead` | Retained failed task metadata |
| `POST /task-jobs/{task_id}/retry-knowledge` | 202 with stable child task; only dead knowledge jobs with unchanged source |
| `POST /documents/{document_id}/deactivate` | Atomically hide queued/indexing/active document; retain all data |

Check both task and document/publication state. `done` is not independent Milvus readback
proof; `published` is application-acknowledged activation. A stale worker may have written
physical index rows after a job died; do not infer rollback or delete them. Retry only
this versioned path, never old unversioned import routines or new arbitrary document IDs.

## Runtime acceptance matrix

Every row remains BLOCKED until isolated Linux/real-store evidence is recorded.

| Scenario | Required evidence |
| --- | --- |
| Empty/v5→v6 bootstrap, repeat, rollback, missing-schema startup | Actual catalog/history/hash checks; legacy rows unchanged |
| Two publishers, same input and conflicting updates | One retained generation per input, stable keys, one current pointer |
| Partial upsert, flush timeout, response loss, PG failure | No half-published result through vector/keyword/PG/RAG; retained failure |
| Kill before/after stage/index/activation commits | Same generation retry; no duplicate eligible content; safe uncertain acknowledgment |
| Update with old vectors retained; stop/restart API and worker | Only current generation in new requests; no stale cache exposure |
| Reject/deactivate/reviewer revocation versus slow worker | No late activation; atomic audit; original reviewer remains binding |
| Dead job retry twice and concurrent old worker | Retained parent/child tasks; same generation keys; no arbitrary queue reset |
| Independent Milvus readback and ACL/type matrix | Exact current keys/text/metadata, no missing chunks or cross-namespace fallback |
| Database outage and capacity bounds | No model/reranker/generation using stale visibility |
| Full RAG dataset, answer and retrieval metrics | No promotion of mock tests into answer-quality acceptance; review C17/C23 recall/latency |

No filesystem/data-volume deletion, existing migration rewrite, dependency installation,
service startup or live model calls were performed. C10 checkpoint race remains open;
C21 retains audit replay. C15 5.1.2 and the whole item remain open. Stop before C16.
