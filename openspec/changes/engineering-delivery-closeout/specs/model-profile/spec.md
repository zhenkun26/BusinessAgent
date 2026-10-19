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
