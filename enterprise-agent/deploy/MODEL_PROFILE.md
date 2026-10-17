# C02 external model profile

Status (2026-10-17): selected and implemented for offline review; **real API and isolated Linux acceptance BLOCKED**. C01 runtime acceptance remains BLOCKED. Neither service startup nor a provider inference call was performed in this increment. C03 is not authorized.

## Selected contract

`MODEL_PROFILE=bailian-deepseek-v1` applies in development and production. The Mac is the development host; full deployment is an isolated Linux amd64 Compose target.

| Component | Selected contract |
| --- | --- |
| Embedding | Beijing Bailian `text-embedding-v4`, explicitly 1024 dimensions, float vectors |
| Reranking | Beijing Bailian `qwen3-rerank`, DashScope HTTP API |
| Default LLM | Official DeepSeek `deepseek-flash`: knowledge answers, classification, extraction, helper calls |
| Complex LLM | Official DeepSeek `deepseek-v4-pro`: decomposition, analytical reports and complex aggregation |
| Vector collection | `enterprise_knowledge_bailian_v4_1024_v1`, separate from all previous BGE data |
| Production image | Python 3.13, `INSTALL_ML=0`, existing HTTP/LangChain stack and approved Debian `libpq5` |
| Processes | One API process plus one worker; 2 GiB budget each, **not a measured minimum** |

Both LLM clients explicitly disable thinking mode. The current LangChain tool-message loop has not been verified to preserve DeepSeek reasoning history; enabling thinking is outside this accepted implementation. Pro remains the complex-task model. Model aliases can change provider-side; record actual returned model IDs, date and provider request IDs during future acceptance. This is not an immutable model-weight pin.

No new Python package was introduced. The optional `requirements-ml.txt` build path is retained for local development experiments; CI/default production do not use it and it is not an accepted production profile. Existing model volumes are preserved but not mounted into the API/worker. No data/model volume is removed or cleaned.

## Configuration

Copy the model settings in `.env.example` into private development/production configuration and fill the keys locally. Never put keys in source, tickets, chat or logs. `.env.prod` remains private and was not edited by this increment.

```env
MODEL_PROFILE=bailian-deepseek-v1
MODEL_STARTUP_PROBES_ENABLED=false
MODEL_HTTP_TIMEOUT_SECONDS=30
MODEL_HTTP_MAX_RETRIES=2
EMBEDDING_PROVIDER=bailian
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1024
EMBEDDING_API_KEY=<private-beijing-key>
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RERANKER_PROVIDER=bailian
RERANKER_MODEL=qwen3-rerank
RERANKER_API_KEY=<private-beijing-key>
RERANKER_BASE_URL=https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank
LLM_PROVIDER=openai_compatible
OPENAI_API_KEY=<private-deepseek-key>
OPENAI_BASE_URL=https://api.deepseek.com/v1
LITE_LLM_MODEL=deepseek-flash
PRIMARY_LLM_MODEL=deepseek-v4-pro
MILVUS_COLLECTION=enterprise_knowledge_bailian_v4_1024_v1
```

Embedding and reranker may use the same Beijing workspace key, but have independent settings and never inherit the DeepSeek key. The Beijing workspace hostname `<workspace-id>.cn-beijing.maas.aliyuncs.com` is also supported with the same API paths. Singapore/other hosts, HTTP, URL credentials, query strings and redirects are rejected by this profile. Model/key access, account quotas, billing and network reachability must be checked by the operator; configuration validation cannot verify them.

`.env.example` selects the remote profile for local development. Leaving `MODEL_PROFILE` empty permits the legacy local/mock development options; production always requires the selected remote profile. Clearing the profile does not remove the need to explicitly choose matching development providers and a separate development collection.

## Request and failure contract

- Embedding: string-only batches of at most ten; explicit `dimensions=1024` and `encoding_format=float`. Validate response count, unique indices, restored input order, numeric finite nonzero vectors and dimension. Never silently truncate text or substitute mock vectors.
- Reranker: `input.query`, `input.documents` and `parameters.top_n` using `/api/v1/services/rerank/text-rerank/text-rerank`. At most 500 candidates, positive top_n, unique valid returned indices and scores in [0,1]. Preserve original source metadata and sort by relevance. Missing/malformed results fail closed.
- Application input caps are conservative UTF-8 byte counts: 8192 per embedding text and 4000 per rerank query/document. They are intentionally stricter than provider token limits, not exact tokenization or billing estimates. Oversized input is rejected before sending; upstream chunking must respect these limits during acceptance.
- Bailian transport timeout: 30 seconds per operation by default, configurable up to 60. At most two retries for transport failures, HTTP 408/429/5xx, with 0.5/1-second backoff. Other HTTP errors and malformed results do not retry. Retries may incur extra charges. This is not a whole-task deadline or a monthly spend cap.
- Provider response bodies and raw transport exception messages never become Bailian adapter errors. Fixed codes describe configuration/input/rejection/unavailability/malformed output. Remote rerank failure propagates through retrieval and the keyword degradation chain instead of being reported as successful reranking. Existing business-layer refusals and quality thresholds still require C17 validation.
- Flash and Pro retain existing bounded SDK retries, 30/60-second request timeouts and streaming clients. Runtime streaming/tool-call correctness is not proven by fake-client tests.

## Startup and authorization boundary

API and worker validate model configuration before database/audit/queue initialization. Development performs no startup inference. Production with `MODEL_STARTUP_PROBES_ENABLED=false` stops with `MODEL_STARTUP_PROBES_NOT_AUTHORIZED` before model requests; the flag is deliberately false in the example pending real API authorization.

Only after a separately authorized acceptance session may the operator set the flag to true. Startup then probes query embedding, document embedding, one rerank, Flash and Pro using synthetic text. There are **five logical model calls per process**, up to fifteen HTTP attempts with retries. The two LLM probes request at most 32 output tokens and have 90-second outer timeouts. Blocking Bailian operations run in a thread and rely on transport timeouts; this is not a single global startup deadline. API/worker restarts repeat probes and may be billed.

Missing config or failed inference prevents startup. Offline checks do not set the flag or start services. A passed startup probe is not continuous readiness, retrieval quality, stream/tool acceptance or release approval.

## Vector data boundary

The profile rejects the historical `enterprise_knowledge` collection. Identical dimensions do not imply compatible vector spaces. No collection was created, renamed, dropped or populated during this change. Existing BGE vectors and source documents remain untouched.

Before real knowledge acceptance, create/populate the new collection from reviewed source documents using a separately reviewed non-destructive procedure; do not run existing recreate/delete-first scripts. Bind source inventory, embedding profile, dimensions and ingestion evidence to that collection. A name alone is not proof of provenance, and no reindex acceptance is claimed here. C03 database initialization and C15 indexing consistency remain separate tasks.

## Costs and account requirements

Reference prices checked 2026-10-17, CNY per million tokens, Beijing Bailian / official DeepSeek:

| Model | Input | Output |
| --- | --- | --- |
| text-embedding-v4 | 0.50 | Not applicable |
| qwen3-rerank | 0.50 | Not applicable |
| deepseek-flash | 1 off-peak / 2 peak, uncached | 4 / 8 |
| deepseek-v4-pro | 4.5 off-peak / 9 peak, uncached | 13.5 / 27 |

These are reference rates, not a billing contract or cost guarantee. Consult current provider pricing/usage before funding an acceptance session. Account charges include every agent call, full rerank input and possible retries. The suggested initial API budget is CNY 50–100; no provider balance, alert or hard monthly budget was configured. Infrastructure costs are separate. Use public/synthetic text for acceptance; external models receive the text sent to them.

## Offline verification and remaining acceptance

Run from repository root, without installing packages or invoking application startup:

```bash
python3 -I -B enterprise-agent/tests/test_model_profile.py
python3 -I -B enterprise-agent/tests/test_remote_models.py
python3 -I -B enterprise-agent/tests/test_deployment_contract.py
python3 -I -B enterprise-agent/scripts/safe_validate.py
```

Tests use fake adapters/transports and isolated source function execution; they do not prove live SDK/model compatibility. The safe validation command may return exit 2 for existing UAT/release blockers even when all allowlisted functions execute correctly. Full eval/pytest and build paths are not automatically safe to execute: review deletion/network side effects first.

Remaining **BLOCKED** acceptance: real provider authorization and keys; Linux candidate build/`pip check`/Trivy and final UID 65534 checkpoint imports; real embedding/reranking/Flash/Pro, negative cases and usage evidence; stream/tool/representative knowledge questions; memory and latency; C01 full deployment checks after initialization prerequisites. OpenSpec CLI strict validation is unavailable locally. C02 stays open; this implementation increment does not authorize C03, push, deployment or release.

## Official references

- [Bailian embedding API](https://help.aliyun.com/zh/model-studio/embedding-interfaces-compatible-with-openai)
- [Bailian rerank API](https://help.aliyun.com/zh/model-studio/text-rerank-api)
- [Regional API keys](https://help.aliyun.com/zh/model-studio/get-api-key)
- [Bailian pricing](https://help.aliyun.com/zh/model-studio/model-pricing)
- [DeepSeek pricing and model IDs](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)
- [DeepSeek thinking protocol](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)
- [Psycopg libpq requirement](https://www.psycopg.org/psycopg3/docs/basic/install.html#pure-python-installation)
