# Data flow and privacy boundaries

## F2-05 plan — authorized 2026-10-20

Baseline: `39ea39c`. Record the plan before implementation. This is a bounded synthetic-data
increment, not private-data admission, a provider-contract review or a claim of compliance.

1. Map queries/history, retrieval text, model answers, tool inputs/results, identity,
   credentials and operational metadata to storage, diagnostics and external recipients.
   Separate current implementation from required access/retention/disposal decisions.
2. Remove raw query/history/username/subtask/model-response/reasoning and exception text
   from the covered graph, knowledge/execution agent and RAG diagnostics. Preserve fixed
   events and useful counts/timings, without changing routing, prompts, ACLs or business
   audit payloads. Scope includes graph/planner/history/executor/aggregator/dispatcher,
   agents/knowledge/execution, rag/degradation/retriever/llm/reranker. Document unreviewed
   sinks rather than claiming repository-wide PII filtering.
3. Restrict application-owned manual tracing helpers to fixed names and a small typed
   metadata allowlist. Drop free text, unknown keys, nested data, identifiers and exception
   details. Preserve operation failures and counts. This does not certify automatic SDK,
   HTTP, database instrumentation, LangSmith, proxy or third-party logging.
4. Use only synthetic markers and in-process doubles to verify diagnostic boundaries,
   unchanged query/document delivery to the intended model adapters, fixed provider errors,
   TLS/host/redirect configuration and existing authorization/citation behavior. No real
   endpoint, model, database, telemetry exporter or browser is invoked.
5. Define synthetic-only use and a private-data admission checklist: data owner/class,
   allowed purpose/recipient/region, provider terms, access/retention, removal from active
   stores/backups/replay, and measured egress evidence. No automatic deletion or guessed
   retention SLA. Refresh only affected F2-09 source hashes, synchronize trackers/OpenSpec,
   review and commit locally; stop without push/upload or starting the next item.

### Acceptance / exclusions

- Synthetic business text and identities do not occur in covered operational log calls
  or manual tracing-helper payloads, including exception, DEBUG and fallback paths.
- Approved numeric/boolean/enumerated manual trace metadata survives; unknown or malformed
  metadata is omitted without stringifying opaque objects. No raw exception capture.
- Provider contract tests explicitly show that embeddings receive text, rerankers receive
  queries/documents, and generation receives query/history/context. Credential redaction
  is not anonymization; payload stripping that changes the requested answer is not a fix.
- Persistent business records (checkpoints, approvals, tool operation/Saga records, audits,
  retained replay and backups) retain existing behavior. Their private-data controls remain
  an admission blocker; this change does not certify or rewrite them.
- No new dependency, migration, real service call, data deletion, push/upload, deployment,
  release, spec sync or archive. Real runtime/full RAG and strict OpenSpec CLI stay BLOCKED;
  F2-09 source rights pending, C10 OPEN. F2-05 remains open for the remaining privacy gates.

## Data categories and current flow

All implementation paths below are under `enterprise-agent/`. This is a source-level map,
not an observed network trace or a complete deployment data inventory.

| Category | Current path / recipient | Boundary and remaining gap |
| --- | --- | --- |
| Query and conversational history | API → graph state/history → planner, knowledge answer and possible aggregation prompts; current model profile uses DeepSeek Flash/Pro | History includes prior user/assistant text. Query expansion also puts previous user text into the embedding query. Identity-bound history and resource limits do not anonymize content |
| Knowledge documents/chunks | Ingest → immutable PostgreSQL publication data → Bailian embedding → Milvus vectors and chunk text/metadata | Index authorization filters reading; embedding is external processing during publication, before a user retrieves a chunk. Vectors are derived data, not proven anonymous |
| Retrieval query and candidates | Authorized/visible retrieval → Bailian reranker → selected chunks → answer prompt | Reranker input contains query and candidate document text; `return_documents=false` limits response duplication, not outgoing content. The generated answer prompt includes titles and selected text |
| Model answers and self-evaluation | DeepSeek → response/SSE and checkpoint state; gray-zone self-evaluation sends query and up to 500 answer characters | The selected remote profile routes nominally local helper calls to Flash; a function named `get_local_llm` does not establish local-only processing. C16 analysis itself uses deterministic Python |
| Tool parameters/results | Execution agent → authorized tool gateway → configured reference/HTTP service, operation receipts/Saga/approval records and business audit | Customer/mail/ticket fields and business outcomes can be sensitive. This increment does not change HTTP contracts, persistence or audit evidence |
| Identity and credentials | JWT/SSO/RBAC/session ownership, database accounts, HTTP Authorization | Credentials use C06 redaction/transient token rules. Identity IDs remain in authorized business records; classification/retention is separate from authentication |
| Operational diagnostics | Covered Loguru calls and manual tracing helpers | This increment omits content/identity text from covered diagnostics. Operational counts, durations and fixed events remain; not a PII detection engine |
| Business audit/replay | `observability/audit.py` → PostgreSQL and local retained SQLite | Input/output summaries (up to 500 characters) and payloads remain business content. Credential redaction is not anonymization. Non-deleting acknowledgements and retries preserve the original event |
| Recovery/evaluation artifacts | Checkpoint stores, physical-volume backups, logs and evaluation receipts | Copies inherit the source classification. A backup restore or retained-event replay can reintroduce data; no end-to-end deletion mechanism is established |

Source anchors: `graph/history.py`, `agents/knowledge.py`, `graph/planner.py`,
`graph/aggregator.py`, `rag/ingest.py`, `rag/retriever.py`, `rag/remote_models.py`,
`rag/llm.py`, `tools/base.py`, `observability/audit.py`, `observability/retained.py`.
Existing [credential controls](credential-safety.md), [retrieval authorization](retrieval-authorization.md),
[request budgets](request-context.md) and [recovery contract](retained-recovery.md) remain in force.

## External processing boundary

The subsequent [read-only RAG boundary](rag-trust-boundary.md) separates policy and JSON
data but still sends selected source title/body, query/history and optional answer text
to the configured models. Source document/chunk identities stay server-side; model call
metadata contains only the boundary version and selected prompt version/hash. This does
not approve private data or change provider/SDK/actual-egress acceptance requirements.

The current `bailian-deepseek-v1` profile validates HTTPS hosts/paths for Beijing Bailian
embedding/reranker and official DeepSeek. Bailian HTTP calls disable redirect following
and use fixed error codes. These are configuration/transport controls, **not** evidence of
provider retention, training use, subprocessors, residency, deletion, contract compliance
or absence of an operator-configured proxy. No such provider promises are made here.

| Route | Necessary outgoing content | Evidence still required before private data |
| --- | --- | --- |
| Bailian `text-embedding-v4` | Text batches from document chunks or expanded retrieval query | Account/workspace/region authorization, applicable dated terms, retention/training/deletion policy, allowed data classes, actual egress |
| Bailian `qwen3-rerank` | Query plus candidate text; no source/user metadata fields added by this adapter | Same account/terms checks; independently confirm reranker processing policy rather than inferring from embedding |
| DeepSeek Flash/Pro | Prompt, query/history, selected context, generated intermediate content or tool schemas/plans as required by the route | Model/account terms, actual processing location, prompt/response retention and training settings, SDK retries/telemetry and permitted purposes |
| Reference business HTTP/IdP/alerts | Structured tool business fields, identity assertions or controlled alerts | Separate recipient/authority and payload review. Reference contracts do not authorize real customer/SSO/messaging use |
| OTLP/LangSmith/automatic SDK instrumentation | Potential URLs, identity, exception, prompt/response or database metadata depending on instrumentor | Keep export disabled for this synthetic offline increment. Review exporter, headers/query capture, model callbacks, proxy/access logs and effective environment before any real run |

The subsequent [telemetry admission increment](telemetry-admission.md) adds a default-disabled
startup gate and explicit synthetic OTEL intent. It rejects covered inherited/effective
SDK enablement before covered imports/clients. This is configuration admission only;
the actual exporter/proxy capture and private-data evidence requirements below remain.

`OTEL_ENABLED=false` and `LANGCHAIN_TRACING_V2=false` are sample defaults. Verify that
`LANGSMITH_TRACING` and inherited SDK/auto-instrumentation settings do not independently
enable export. A disabled application helper or no configured OTLP exporter is not a
proof that all third-party telemetry is disabled. Real service startup is outside this
increment: production model startup checks themselves make model calls.

Legacy local/mock/Cohere profiles are development alternatives and require their own
recipient review; they are not covered by the selected production profile. A local model
fallback can select a remote client. Do not infer no egress from a provider label.

## Covered diagnostic behavior

The twelve source modules listed in the plan now use fixed events instead of raw content
or exception bodies at 53 reviewed call sites. Other safe operational messages/counts are
retained. No prompt, result, ACL, workflow decision or business audit payload is changed.
DEBUG is subject to the same source-side rule. Credentials still use the existing patcher.

Manual tracing helpers accept only:

- Fixed RAG/worker operation names; all `tool.*` operations become `tool.invoke`, and
  unknown operation/event names become fixed generic names. Free-form names are not exported.
- Enumerated retrieval scene/stage, booleans for tool success/RBAC mode, and bounded finite
  numeric retrieval counts/scores/latencies. Unknown keys, IDs, roles, scope, content,
  nested values and malformed types are dropped without calling their `str`/`repr`.
- A fixed failure event without exception text or a dynamic exception class name. The
  context manager disables automatic exception recording and does not swallow failures.

This sacrifices per-tool/per-user/per-task identity in manual spans; authorized business
audit retains those associations. It does not alter metrics label/cardinality contracts.
Automatic FastAPI/HTTP/Redis instrumentors and spans written directly by external code
can bypass these helpers and are **not privacy accepted**. Unreviewed diagnostics include
file-loader paths, embedding initialization, startup/infrastructure messages, tool/plugin
logging, SDK HTTP logs, process stdout/stderr and reverse-proxy access logs. Audit bodies,
provider prompts and database rows are not protected by the manual metadata allowlist.
A later review must enumerate and test those sinks before private-data admission.

## Access, retention and disposal requirements

Current allowed material for this increment is synthetic fixture content only. This is an
operator/use boundary, **not an implemented automatic content classifier**. Never paste
credentials or private business/personal content into model queries to test these controls.
Existing samples keep their F2-09 pending provenance; synthetic labels do not grant rights.

| Store / sink | Current implementation | Required owner decision and evidence |
| --- | --- | --- |
| Runtime prompt/response/history | Bounded in memory; some content persists in checkpoints | Limit access to authorized session roles; review model/trace callbacks and error paths; process lifetime is not a deletion certificate |
| Redis checkpoint | Configured default 7 days with refresh-on-read; zero disables TTL | Sliding backend TTL is not an absolute retention deadline or global deletion. Set approved purpose/period and verify every key/index/replica plus accepted publication history |
| PostgreSQL/Milvus business and knowledge state | Immutable versions, session/approval/action/Saga/audit records and index copies | Define data-owner access, least-privilege service identities and permitted operator access; approve record-specific retention and cross-store disposal before private use |
| Local retained audit/replay | Acknowledgements mark records; original events are not deleted | Restricted volume access and a capacity/retention decision required. Acknowledged is not erased. Replay must not restore content already approved for removal |
| Diagnostic/SDK/proxy logs | This patch reduces covered content; no project-wide retention SLA established | Identify every sink/exporter, set shortest justified retention and access policy, verify actual logging configuration and capture tests |
| Physical backups/exports/eval artifacts | Copies can survive live-store changes; local test evidence is retained and ignored | Inventory copies and access, approve expiry/restore exclusions, and test that restore/replay cannot silently resurrect removed records |
| Provider-side copies | Not observable or confirmed in this increment | Obtain account-specific dated evidence for retention, training, support access, deletion and any exceptions; do not invent a zero-retention guarantee |

No universal retention number is assigned without a purpose/owner decision. There is no
automated purge, cryptographic erasure or historical remediation claim. Existing protected
records and backups are not edited, deleted or migrated by this work.

If private-data use is later proposed, the repository owner/data owner must first approve
classification and purpose, recipients/regions, access and retention; collect dated provider
terms/effective settings; verify synthetic egress captures and outage/error/replay/restore
paths; then authorize a bounded admission. Disposal requires an inventory of active copies,
indexes, audit/replay, exports and backups, legal/hold decisions where applicable, a scoped
operator-reviewed procedure, and post-disposal/restore verification. This repository task
performs no deletion; any future filesystem deletion remains the user's operation under
current workspace instructions. Until these decisions/evidence exist, private-data admission
is **BLOCKED**, not waived because the project is a portfolio.

## Offline evidence — 2026-10-20

| Verification | Result / boundary |
| --- | --- |
| New synthetic regressions | **17 tests**, including every covered diagnostic expression, actual replan/history/executor behavior, manual-trace types/names/failures and model payload captures |
| Focused selection | **75 tests + 164 subtests PASS** (`data_privacy`, `credential_safety`, `request_context`, `remote_models`, `citation_time`) |
| Full local pytest | **1156 tests + 391 subtests PASS**, zero skips/xfails/guard denials; Python 3.13.15/macOS arm64, 45 dependency deprecation warnings |
| C06 / C08 / C17 / C21 reviewed eval entries | **20 / 23 / 29 / 45 tests PASS**; no real storage, provider or exporter |
| License/source integrity | **PASS:** 432 pending sources, 98 production packages, 3 browser packages, 32 declaration inputs; no existing source/declaration rights changed |
| Safe validation | Execution **PASS**, overall **BLOCKED**, expected exit 2; no UAT/release acceptance |
| Review | Production/test diff, unchanged business AST outside diagnostics, original modes/unrelated bytes, source binding, local links and manual OpenSpec structure checked |

HTTP tests use real httpx requests with an in-process MockTransport. LLM tests capture the
actual knowledge-generation method's prompt inputs with a model double, not a provider SDK
network request. The isolated pytest runner denies network/deletion, disables dotenv and
implicit pytest plugins/cache cleanup, and retains output only under ignored `eval/results/`.
It verifies unchanged inputs during the run. The initial generation fixture used the wrong
prompt-factory method; it was corrected to the actual `from_template` interface and the
complete suite then passed without skipping or weakening assertions.

Local receipts, coverage, source hashes, runner, validation logs and final commit binding
are retained under `enterprise-agent/eval/results/ci-pytest-a175554f9fc448eb9cd6fdecd16366a9/`.
The test receipt identifies `39ea39c` plus tested worktree hashes; subsequent prose updates
are separately reviewed. These host-specific artifacts are ignored, not uploaded and not
portable release attestations. The runner reuses already-declared dependencies; no install.

Strict OpenSpec CLI is unavailable/**BLOCKED**; manual structure checks do not replace it.
No current remote CI, real browser/service/two-process/full RAG, provider terms, processing
region, automatic telemetry or private-data acceptance is claimed. F2-05 remains **OPEN**
for those gaps, F2-09 sources **PENDING**, C10 **OPEN**. Review and local commit only, then
wait for confirmation; no automatic next increment, push/upload, merge, release or archive.

## Planner/tool selection payload clarification — 2026-10-22

The F2-06 [Planner/tool boundary](planner-tool-trust-boundary.md) changes covered prompt
assembly to separate System policy and human JSON; it does not anonymize payloads.
Classification receives the current message and authorized history. Chitchat/decomposition
receive the current message. Tool selection receives the original current request, its
literal task excerpt and role-filtered catalog/schema descriptions; it receives no history
or model-supplied permission context. These fields may contain business or personal data.
Only synthetic doubles were used this round. DeepSeek/provider retention, consent,
regional processing and actual telemetry/privacy acceptance remain BLOCKED; code-owned
metadata contains only boundary/template version/hash. C21 audit/metrics remain intact.

## Non-knowledge composition clarification — 2026-10-22

F2-06 [non-knowledge composition](nonknowledge-result-boundary.md) no longer sends the
current question or action result prose to a summary model. It displays literal quoted
data and structured snapshot status locally. Chitchat and other provider payloads remain
unchanged and privacy-unaccepted. The scoped diagnostic expression inventory is now 80
(previous candidate 82): removing the two obsolete summary log calls also removes their
automatic subtests, not the remaining diagnostic checks. This is not global log coverage
or secret removal. C21 audit/metrics retained; real privacy/provider/retention BLOCKED.

## Chitchat payload clarification — 2026-10-22

The F2-06 [chitchat boundary](chitchat-trust-boundary.md) sends only a message JSON object
under fixed System instructions. Username, history, identity, credentials and tool catalogs
are omitted; local canned replies also omit display names. Messages may still contain
private content: this is not anonymization, DLP or provider/privacy acceptance. Only fixed
boundary/policy hash metadata is added. Model drafts stay hidden and admitted text is
literal chat, not execution evidence. The scoped diagnostic expression count changes
80 to 79 with removal of the old response-length warning; no raw content log is added.
C21 audit/metrics and privacy/provider/retention gates remain intact/BLOCKED.

## Optional LLM rerank clarification — 2026-10-22

The F2-06 [optional LLM rerank boundary](llm-rerank-trust-boundary.md) sends only query and
the existing first-1000-character candidate prefix as human JSON under fixed read-only
policy/selected task references. Version IDs/template hashes are metadata; source IDs,
identity and tool catalogs are omitted. Query/chunk text can still contain private data;
this is not DLP, anonymization or supplier acceptance. Raw score events stay hidden;
ordinary errors are fixed and whole-batch, with no raw diagnostics. Covered diagnostic
expressions remain 79; C21 audit/metrics retained. Bailian/Cohere/BGE payloads and existing
provider/retention gates are unchanged/BLOCKED. No real provider was called.

## Optional Cohere/BGE result clarification — 2026-10-22

The F2-06 [result/numerical boundary](optional-rerank-result-boundary.md) preserves existing
payloads: Cohere receives query plus full candidate text; BGE receives query and each
first-1000-character prefix. Source/ACL fields are copied server-side, not accepted from
provider rows. Validation and fixed batch errors add no raw content diagnostics; the
covered expression count remains 79. This is not DLP/anonymization/provider admission.
No real SDK/model was used, installed or downloaded. C21 audit/metrics and all existing
provider/retention/disposal/privacy gates remain unchanged/BLOCKED.
