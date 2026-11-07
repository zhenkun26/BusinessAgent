## ADDED Requirements

### Requirement: Production must select an explicit model profile
Production SHALL require `bailian-deepseek-v1`: Beijing Bailian text-embedding-v4 (1024 dimensions), qwen3-rerank, DeepSeek Flash for default tasks and Pro for complex tasks. Credentials and endpoints SHALL be independent for embedding, reranking and LLM. The selected profile SHALL use a separate named vector collection, preserving existing BGE data.

#### Scenario: Unsupported or incomplete profile
- **WHEN** production configuration selects a missing/unknown profile, incompatible providers/models, non-approved endpoints, absent credentials, an old collection or wrong dimensions
- **THEN** API and worker refuse startup before database, audit or queue initialization and emit only safe error codes

### Requirement: Model failure must not silently degrade production
Production SHALL validate configuration without network access, require explicit operator opt-in for billable startup probes, and verify embedding, reranking and LLM inference before startup succeeds. Required model failures SHALL stop startup rather than activate local, mock or passthrough fallbacks. Remote requests SHALL have bounded timeouts/retries and sanitized errors; malformed vectors or rerank indices/scores SHALL fail closed. Remote-profile rerank failures SHALL propagate out of the retriever rather than return unreranked candidates.

#### Scenario: Paid probes have not been authorized
- **WHEN** production starts with MODEL_STARTUP_PROBES_ENABLED=false
- **THEN** startup stops before any model request or business initialization

#### Scenario: Remote embedding batches
- **WHEN** a valid list of documents is embedded
- **THEN** requests contain at most ten strings each with explicit dimensions and float encoding, and validated vectors preserve input order

#### Scenario: Loading or inference fails
- **WHEN** a required package/model is absent or inference fails, produces invalid vectors, or returns empty LLM output
- **THEN** startup fails, and raw exception details or credentials are not included in the public startup error

#### Scenario: Development mode
- **WHEN** APP_ENV is dev
- **THEN** startup performs no inference; selecting the remote profile still enforces configuration and remote-only routing, while an empty profile retains legacy development providers

### Requirement: Candidate dependencies and evidence must match the profile
The CI candidate SHALL use the slim remote-service build without local ML dependencies and run package compatibility and final non-root PostgreSQL import checks. Development manifests SHALL include the already-declared PostgreSQL checkpoint dependencies. Runtime model acceptance SHALL remain separate from offline checks.

#### Scenario: Only offline evidence is available
- **WHEN** fake-adapter tests and source checks pass but no real candidate build/model/LLM run exists
- **THEN** C02 remains open with runtime acceptance BLOCKED, optional profiles remain unaccepted, and no production release is inferred


### Requirement: Reranker selection and cache admission must be explicit
The factory SHALL reject unknown or empty providers, preserve auto as Cohere-with-key or
passthrough-without-key, and validate the remote profile before cache reuse. Relevant
configuration changes SHALL require process restart instead of silent backend switching.
Selection state SHALL distinguish requested/effective providers and fixed fallback reasons
without exposing secrets. Budget/cancellation interruptions SHALL propagate and SHALL NOT
publish an interrupted construction or successful fallback into the cache.

#### Scenario: Warm cache with changed or invalid configuration
- **WHEN** a cached development backend exists and configuration becomes invalid or materially different
- **THEN** the factory rejects reuse with a fixed error before backend work; required remote-profile failures never select passthrough

#### Scenario: Passthrough versus successful scoring
- **WHEN** explicit passthrough, auto without credentials or optional initialization fallback is selected
- **THEN** retrieval reports vector stage without rerank-success telemetry; actual successful scoring reports rerank, and optional invocation failure records coarse/vector fallback

#### Scenario: Preserve evaluation route semantics
- **WHEN** retrieval stage reporting is corrected
- **THEN** DegradationResult.stage retains its primary-vector-route meaning and C17 corpus, evaluator, categories and denominators stay unchanged

#### Scenario: Interrupted initialization
- **WHEN** a budget or cancellation interrupt occurs before or during factory construction
- **THEN** it propagates without caching the interrupted backend or fallback; offline checks do not imply hard cancellation or real model acceptance


### Requirement: Retrieval and confidence scores must pass numerical admission
The system SHALL reject boolean, non-real and non-finite scores before conversion,
clipping, model use or confidence publication. Valid finite memory/Milvus handling,
confidence arithmetic, weights and thresholds SHALL remain unchanged. Invalid batches
SHALL NOT be partially salvaged by dropping rows or substituting zero; existing controlled
failure/fallback paths SHALL remain distinct from empty retrieval. Numeric admission
SHALL NOT establish semantic correctness, calibrated probability or runtime acceptance.

#### Scenario: Invalid authorized coarse score
- **WHEN** a raw or visible coarse result contains NaN, Infinity, boolean or non-numeric scores
- **THEN** reject the batch before reranking/generation, preserving controlled failure/fallback accounting instead of converting it into high confidence

#### Scenario: Invalid knowledge or confidence input
- **WHEN** any knowledge result score or used confidence operand/intermediate is invalid
- **THEN** fail safely without invalid source publication, fabricated no-answer or skip-hint success

#### Scenario: Finite compatibility and evidence
- **WHEN** admitted finite values exercise memory clipping, raw Milvus COSINE, confidence weighting and scene decisions
- **THEN** retain their previous results, weights/thresholds and C17 definitions/categories/denominators; real quality/privacy/runtime/full RAG remain BLOCKED and C10 stays OPEN
