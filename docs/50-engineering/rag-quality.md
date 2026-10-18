# RAG quality evidence contract (C17)

Status: offline implementation only. C17, real runtime and full RAG acceptance remain
**BLOCKED**. This document defines `rag-quality-v2`; it does not report a measured quality
score. C02 must be accepted in the isolated Linux candidate before formal quality review.
C10 lease-expiry writes remain open; non-deleting audit replay remains C21.

## Frozen inputs and provenance

- `enterprise-agent/eval/eval_set.json`: preserve all 122 existing cases byte-for-byte:
  115 normal-answer cases, five refusal cases and two clarification cases. Existing
  query IDs, expected keywords and source annotations are not relaxed or normalized.
- `eval/sample_docs/`: preserve all nine Markdown sources. Their exact paths, byte SHA-256,
  document IDs, titles, namespaces and ACLs are frozen in `eval/rag_quality_manifest.json`.
- `eval/permission_eval_set.json`: six **separate** controls: sales/finance own-department
  positive cases and four cross-department negatives, with source path/hash and forbidden
  document IDs/fact strings. They supplement rather than replace the original 122 cases.
- Primary and supplemental metrics remain separate. A good synthetic control score cannot
  raise the primary score. Roles are component inputs, not proof of actual JWT/API authority.
- Reports retain the full manifest, input hashes, code-file hashes, timestamps, effective
  model names/dimension/collection, pinned prompt versions/hashes and publication generations.
  Credentials and endpoint configuration are not serialized. Evidence contains synthetic
  source text and generated answers; do not substitute private enterprise data without review.

## Metric definitions

| Metric | Denominator / interpretation |
| --- | --- |
| Primary answer coverage | Sum of per-case keyword fractions / **115**, including failed, empty, skipped and missing cases as zero |
| Supplemental answer coverage | Same rule / **2** positive controls, independently reported |
| Keyword fraction | Case-insensitive literal substring hits / that case's frozen keyword count; preserve spaces and wording |
| Top-1/3/5 and MRR | All normal-answer cases in that suite; exact document ID **and** exact title; empty/failure/missing retrieval contributes zero |
| Refusal/clarification proxy | Marker hits / all behavioral cases: **7** primary, **4** supplemental; failed/unexecuted calls get zero |
| Citation reference check | All normal-answer cases; at least one valid `[来源N]`, every reference within the actual retrieved list and present in emitted source IDs/chunk IDs |
| Permission control | Check retrieved chunks, returned sources and answer text for forbidden IDs/fact strings; failed/unexecuted cases are BLOCKED |
| Successful-answer diagnostic | Optional success-only mean is explicitly secondary; never used as acceptance coverage |
| Facts / semantic citations | **NOT_MEASURED / PENDING** until human review; neither keyword presence nor valid indexes proves support |

Scene and difficulty breakdowns follow the same fixed-denominator rule. Every expected ID
has a report row; missing observations become `not_run/skipped`, and duplicate/unknown IDs
are rejected. No partial report is silently promoted to a complete evaluation.

`mechanical_gate=PASS` requires both suites' Top-5 and answer coverage >=0.85, all normal
citation references valid, all behavioral markers present, no permission failure/blocked
control and no failed/empty answers. Skipped or missing cases block that gate. A runtime
preflight or corpus-change failure also blocks it. **Mechanical PASS is not quality PASS.**
`quality_acceptance` remains BLOCKED pending accepted C02 profile, full runtime evidence and
semantic review. The CLI returns exit 2 and never enables UAT or release flags.

## Actual pipeline and attribution

The runner captures the exact degradation invocation inside `KnowledgeAgent.run`, then
scores its final confidence decision and emitted sources. It does not retrieve twice or
maintain a simplified generation prompt. Retrieval-only mode never manufactures a refusal.
Prompts are pinned for the run with a fixed evaluation identity for A/B selection.

Per-case evidence separates retrieval `ok/empty/failed/not_run` from answer
`ok/empty/failed/skipped/blocked`, with a fixed safe error code and latency. Attribution
includes `retrieval_failed`, `retrieval_not_run`, `retrieval_miss`, `answer_failed`,
`answer_skipped`, `retrieved_context_keyword_gap`, `generation_keyword_gap`, citation,
permission and behavior-marker failures. A missing keyword in retrieved text alone does
not prove an assembly bug. Inspect retrieved chunks, final answer, sources and prompt
identity before assigning a root cause or changing prompts/chunking/thresholds.

Actual retrieval stages are `vector`, `keyword_scan` (term-match ratio over at most 500
eligible Milvus rows), `pg_fulltext_like` (PostgreSQL tsvector rank with escaped ILIKE),
`none` (valid empty result) and `failed`. None of these fallback implementations is BM25.
PostgreSQL failure raises a fixed error; it cannot become a successful no-answer response.
The C02 remote-model failure and C07/C15 authorization/publication guards remain fail closed.
No retrieval algorithm, prompt or confidence threshold has been tuned without real evidence.

## Reviewed offline entry

From the repository root:

```bash
python3.13 -I -B enterprise-agent/eval/run_c17_rag_quality.py
```

This uses the standard library, actual metric/degradation/agent orchestration source and
injected stores/models. Its audit guard denies network, filesystem writes/deletion and
subprocesses. It validates accounting and contracts, not RAG quality, throughput or runtime
integration. It is a separate reviewed entry, not an expansion of safe_validate's whitelist.

## Isolated runtime procedure (not executed or authorized by this increment)

1. Obtain separate runtime authorization and isolated Linux/dependency/credential resources.
   Complete C02 profile acceptance using Beijing Bailian embedding/reranker and the approved
   DeepSeek configuration. Use a dedicated database/collection, never current user stores.
2. Provision schema and publish the nine sources using the reviewed C03/C15 lifecycle. Set
   document IDs/titles/content bytes, namespace and ACL exactly as the manifest specifies.
   Shared documents admit all five roles; sales/finance internal documents admit their own
   role plus manager/admin. Keep source URLs consistent with the frozen publication snapshot.
   The evaluator does not prepare data, migrate, reset, ingest, recreate or repair anything.
3. Confirm all and only these nine documents are active, fully published, have no pending
   generation and match the published snapshots. Stop publishers during evaluation. Preflight
   checks exact source hashes, memberships/ACL and generations before/after execution; it is
   **not** a database snapshot or proof against every transient concurrent source change.
4. In `enterprise-agent`, run `python -B -m eval.run_eval` for the offline plan. Only after
   authorization, run `python -B -m eval.run_eval --execute --output eval/results/UNIQUE.json`.
   Choose a fresh name in an existing non-symlink directory. `--no-answer` is retrieval-only
   and cannot complete quality acceptance. All inputs are fixed; no sample-limit switch.
5. Runtime imports are deferred until opt-in. C03 schema verification performs no migration;
   Milvus must already exist (`require_existing=True` forbids creation/recreation). Preflight
   errors retain all 128 rows with explicit missing/blocked evidence. Per-case failures stay
   in the run and its denominator. Reports are exclusive-created; historical reports remain.
6. Review every normal answer's cited chunk for support and counterexamples; every refusal
   and clarification for appropriateness; all six role controls for data and citation leaks.
   Record query ID, observed answer, source/chunk, PASS/FAIL, rationale, reviewer and timestamp
   in a separate signed review linked to the exact report SHA-256. Never auto-fill reviewers
   or accept marker-only checks. Include all 122 cases, not just low-score examples.
7. Diagnose misses, keep immutable before/after reports, and authorize targeted corrections
   without changing expected results to make them pass. Rerun the complete corpus after any
   RAG change. Full API/JWT/SSE/graph and C15 runtime tests remain separate required evidence.

Compatibility: the old `--ingest`, `--recreate`, local `--no-rerank` and alternate-dataset
options are no longer evaluation features. `latest.json` is never overwritten. Report v1's
success-only coverage and simplified generation results are historical and not comparable
to v2's full-denominator, actual-agent measurements. Existing reports and sources stay intact.
