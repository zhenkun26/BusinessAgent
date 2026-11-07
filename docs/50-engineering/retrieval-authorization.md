# C07 retrieval authorization and expression contract

Status: offline increment implemented, 2026-10-17. **C07 remains open; real Milvus,
PostgreSQL, JWT/API/SSE and Linux acceptance is BLOCKED.** Prior browser/SSO and
historical credential remediation blockers are unchanged. No store was queried,
reindexed, migrated or deleted during this increment.

## Authorization matrix

`ROLE_NAMESPACES` in [rbac.py](../../enterprise-agent/app/security/rbac.py) remains
the single source of role grants. [retrieval_policy.py](../../enterprise-agent/app/security/retrieval_policy.py)
combines them with the authenticated current department and document ACL. Department
is identity context, not a user-selected search namespace.

| Current role | Authorized document namespaces | Missing/empty department |
| --- | --- | --- |
| salesperson | dept_sales plus shared_company, if current department is dept_sales | shared_company only |
| customer_service | dept_cs plus shared_company, if current department is dept_cs | shared_company only |
| finance | dept_finance plus shared_company, if current department is dept_finance | shared_company only |
| manager | dept_sales, dept_finance, dept_cs, dept_hr and shared_company | Same explicit cross-department grant |
| admin | Any syntactically valid namespace, including restricted_exec | Same wildcard grant |

For ordinary roles whose current department is shared_company, only shared_company
is available. A nonempty department must be in the role grant (admin has a wildcard)
and use the namespace syntax `[a-z][a-z0-9_]{0,63}`. A role/department mismatch, an
unknown role, missing role or unsupported department denies before models/stores;
it never becomes an unrestricted search. Manager access to restricted_exec is denied.

Every row must also be active and include the current role in its `access_roles`
list. **Shared does not mean public, and admin does not bypass document ACL.** Missing
or malformed ACL/namespace/type metadata is discarded. C05 supplies current identity;
this is not continuous revocation of already generated answers or in-flight requests.

`SearchFilter` without a role and direct store search without a filter now reject.
`active_only=False` is unsupported on user retrieval methods. `doc_types=None` means
no type narrowing, while `doc_types=[]` means no documents. This applies to memory,
Milvus vector search, Milvus keyword scan and PostgreSQL fallback alike.

## Encoding and output boundaries

- Milvus role, namespace, type and document ID values pass one double-quoted literal
  encoder. Quotes and backslashes are escaped; control characters, empty or oversized
  strings reject. Namespace syntax and role membership also validate independently.
  Type values are at most 32 UTF-8 bytes; document IDs at most 64 bytes. The encoder
  does not accept caller-supplied expression fragments, identifiers or operators.
- PostgreSQL uses bound values. Role/namespace/type arrays are JSON-serialized and
  cast to JSONB, never assembled with interpolated values. Each keyword uses bound
  `plainto_tsquery`; OR composition contains only generated parameter names. LIKE
  fallback escapes `!`, `%` and `_` with an explicit `!` escape character.
- Keyword fallback carries type constraints as well as identity scope. Authorization
  exceptions propagate and cannot trigger a wider fallback. Database failures return
  no documents with a fixed diagnostic code.
- Stores fetch `access_roles` and active state and recheck them before returning any
  body/title/source. Memory and keyword paths filter before text scoring. Retriever
  candidates are checked before external reranking and again after it. All five
  reranker implementations preserve ACL metadata. The degradation chain and knowledge
  agent also guard results before model context and citation construction.
- Document-ID deletion encoding is repaired, but no real delete call is authorized
  by this change. Offline tests invoke that method only against a mock collection.

Milvus's [2.4 scalar filter contract](https://milvus.io/docs/v2.4.x/get-and-scalar-query.md)
defines filters as expressions; the application now treats dynamic values as
literals. Offline round-trip checks do not establish actual server parser behavior.
The selected Milvus/PyMilvus and PostgreSQL versions must still pass live acceptance.

## Offline evidence and remaining limits

Run from the repository root:

```bash
python3 -I -B enterprise-agent/eval/run_c07_retrieval_authorization.py
```

The suite executes actual source with injected collection/session/model interfaces.
Collections and sessions deliberately return unauthorized rows so result checks
must remove bodies, titles and source metadata before reranking/generation/citations.
It exercises four paths, all roles, absent departments, explicit manager scope,
inactive/ACL-denied documents, malicious literals, type constraints and fault fallback.
The memory-path numeric double supplies scores; it does not validate NumPy math.

Real Milvus filter parsing, SQL query semantics/driver types, physical partitions,
index/PG metadata consistency, latency, recall and external model behavior remain
unverified. The policy trusts persisted ACL metadata; it cannot detect a document
whose stored classification itself is wrong. C15 owns publication/index consistency,
C17 owns retrieval quality. Existing history/checkpoints are not reclassified or
scrubbed here; historical credential remediation remains separately blocked.

Before closing C07, use a separately authorized isolated candidate and synthetic
corpus containing distinct markers in body/title/source for every matrix cell:

1. Test all roles, current departments, absent/invalid departments and role changes
   through actual authenticated API/SSE requests. Confirm stale JWT role claims do
   not override C05's current database identity.
2. Exercise vector, keyword and PG paths under forced outages with identical ACL,
   active state and type restrictions, including empty lists and manager/admin cases.
3. Verify quote/backslash/operator/control/Unicode cases in actual Milvus parsing and
   PG bound parameters; document-ID tests must target isolated synthetic data only
   under separate write authorization. No filesystem cleanup is authorized here.
4. Check provider requests, answers, citations, source URLs, SSE events and diagnostics
   for unauthorized markers. Test missing/corrupt metadata and restored availability.
5. Bind evidence to commit/image, model and store versions. Keep formal_uat,
   release_evidence and release_allowed false until their independent gates pass.
