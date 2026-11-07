## ADDED Requirements

### Requirement: Analysis extension preserves query-source identity
The reference CRM SHALL provide the separately versioned crm-analysis-v1 read schema
over the same customer/order records as B01/B02. Pages SHALL bind run, immutable snapshot,
UTC as-of, date range and complete counts. Expired or invalid snapshots SHALL fail rather
than silently restart. Service implementation and full application acceptance remain C18.

#### Scenario: Analytics adapter passes injected transport checks
- **WHEN** C16 tests validate complete pages and matching query aggregates offline
- **THEN** only the adapter candidate has evidence; independent service and enterprise acceptance remain BLOCKED

### Requirement: Reference contract is versioned and separate from vendor acceptance
The project SHALL freeze a named CRM/ticket/mail reference profile with explicit routes, fields, authorization, receipts and isolated service addresses before C12 implementation. It SHALL label target behavior separately from current adapters and retain real-provider confirmation tasks.

#### Scenario: Contract prework is delivered
- **WHEN** the document and static checks are complete
- **THEN** only task 4.1 is complete, C18 full acceptance remains open, and no runtime support or enterprise confirmation is claimed

### Requirement: Logical operations survive retry and recovery
The reference profile SHALL require durable unique operation IDs, same-key/same-request replay, different-payload conflict, atomic effect/receipt persistence and an authenticated outcome-query route. Compensation SHALL have its own stable ID linked to the forward operation.

#### Scenario: Response is lost after commit
- **WHEN** the same operation is queried or replayed after a timeout or process restart
- **THEN** it resolves to the original retained receipt and cannot create a second effect; unknown outcomes cannot be reported as rollback or assigned a new identity

### Requirement: Compensation is conditional and truthful
The reference profile SHALL define retained CRM tombstones, version-checked ticket closure/restoration and explicit mail recall states. Later unrelated updates SHALL NOT be silently overwritten by compensation.

#### Scenario: A compensation conflicts with later business activity
- **WHEN** the recorded post-operation version no longer matches
- **THEN** the service rejects the compensation, retains evidence and requires reconciliation rather than claiming restoration

#### Scenario: Mail recall is merely requested or unsupported
- **WHEN** a provider returns requested or unsupported instead of terminal recalled
- **THEN** the application must not label the mail recalled or the Saga fully compensated

### Requirement: Fault evidence must traverse the complete application
The project SHALL define future cases linking authorization, planning, approval where required, external operation, service ledger and application audit under independent service restart/network faults. The reference mail profile SHALL capture only synthetic allowlisted recipients and have no external delivery.

#### Scenario: Only the legacy stub or MockTransport passes
- **WHEN** evidence lacks independent persistent services or the complete application path
- **THEN** C18 runtime acceptance remains BLOCKED and formal_uat, release_evidence and release_allowed remain false

### Requirement: Prework does not authorize dependent work
The project SHALL retain C10's lease-expiry write race and real-runtime blockers, and SHALL pause after the C18 prework increment before C12 or other stages.

#### Scenario: Reference prework is committed locally
- **WHEN** the prework increment is ready for review
- **THEN** further push, implementation, deployment and any live business call require their own user authorization

### Requirement: Independent reference services retain transactional effects
The reference implementation SHALL expose B01-B13 and crm-analysis-v1 from separate
CRM, ticket and mail processes with persistent per-service storage, strict requests,
run/principal grants, atomic effects and terminal receipts, retained rejections and
version-checked compensation. It SHALL have no SMTP or automatic data reset/deletion.

#### Scenario: Same operation recurs after an uncertain response
- **WHEN** a matching key/fingerprint is retried or queried under the same store identity
- **THEN** the original receipt is returned or an uncommitted pending transaction is safely completed without duplicating a committed effect

#### Scenario: Incompatible ledger identity
- **WHEN** startup sees a mismatched store identity, service or schema
- **THEN** startup fails without overwriting records or claiming safe recovery

### Requirement: Reference controls are isolated and explicit
The service SHALL provide authenticated control-v1 on a separate listener for fresh-run
provisioning, retained evidence and operation/attempt/phase-scoped faults. Business tokens,
user headers and natural-language payloads SHALL NOT grant operator controls.

#### Scenario: Unauthorized reset or fault installation
- **WHEN** a business caller attempts operator actions or a reset
- **THEN** the request is denied without disclosing records or changing business state

### Requirement: C18 evidence distinguishes implementation from full-path acceptance
The project SHALL provide an opt-in login/chat/approval/resume transcript runner and
reference-ledger evidence capture. It SHALL retain all R01-R20 statuses and require
independent process, persistence, transport fault and application audit/Saga/queue evidence
before closing C18. No offline test or transcript-only observation SHALL grant full PASS.

#### Scenario: Local implementation passes injected tests
- **WHEN** service/client contracts pass against in-memory SQLite and transport doubles
- **THEN** only the implementation subtask is complete, runtime/full RAG stay BLOCKED, C10 stays open and audit replay remains C21

### Requirement: Reference observation is bounded and does not grant execution authority
The application SHALL restrict reference configuration and per-session correlation endpoints
to current administrators, omit credentials and business/audit payloads, parameterize queries,
and enforce row/time bounds. The collector SHALL verify expected store/run identities and
stable fixture hashes before further business messages and preserve missing evidence.

#### Scenario: Evidence identity changes or an approval is ambiguous
- **WHEN** a store identity or fixture hash differs, or more than one approval matches
- **THEN** the collector stops without choosing another ledger or arbitrary approval, retains BLOCKED cases, and never repairs audit records or grants execution authority
