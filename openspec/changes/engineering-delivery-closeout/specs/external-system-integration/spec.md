## MODIFIED Requirements

### Requirement: 后台 worker 必须执行异步任务
The independent worker SHALL consume retained PostgreSQL jobs after initializing required dependencies. Pre-dispatch lease expiry SHALL permit bounded delayed recovery. Once dispatch may have occurred, knowledge-task failure SHALL retain a queryable dead task without automatic repeat. Saga recovery MAY retry within four attempts only through its durable per-operation dispatch guards. Full delivery SHALL additionally require C13 durable Saga recovery and C21 non-deleting audit replay; C14 alone SHALL NOT claim those capabilities.

#### Scenario: 文档入库任务被消费
- **WHEN** approval creates a knowledge job
- **THEN** the worker executes frozen input or records a fixed failure reason; queue acknowledgment does not remove evidence

#### Scenario: Saga 失败补偿重试
- **WHEN** a retained Saga recovery job is claimed
- **THEN** the worker verifies the journal, cancels undispatched forward actions, reconciles uncertain operations by original ID and compensates known effects in reverse order; legacy or missing journals fail closed

#### Scenario: 审计缓存回写
- **WHEN** only the legacy deleting cache replay path exists
- **THEN** the worker preserves cache files and defers replay to C21, rather than silently deleting files or claiming synchronization

#### Scenario: 消费者失活
- **WHEN** a consumer stops unexpectedly or its progress heartbeat becomes stale
- **THEN** process supervision exits on termination and the admin consumer query exposes stale progress; this is not complete C21 readiness

### Requirement: Durable Saga and linked HTTP compensation
The system SHALL persist an exact ordered plan and atomic recovery job before side effects.
It SHALL guard journal ownership and dispatch, retain separate forward/inverse identities,
and revalidate current authorization and target before inverse I/O. It SHALL NOT resume
new forward actions after restart, repeat a claimed inverse write, or treat unknown/recall
pending outcomes as compensated. All records SHALL be retained without destructive ack.

#### Scenario: Lost inverse response
- **WHEN** a compensation response is lost after dispatch
- **THEN** recovery queries the original inverse UUID and requires a matching complete receipt; it never changes the key or refreshes the original version

#### Scenario: Uncertain forward effect
- **WHEN** an original operation has no provable terminal result
- **THEN** all inverse writes stop and the Saga remains unresolved with retained evidence

#### Scenario: External mail recall request
- **WHEN** the provider accepts a recall request with 202
- **THEN** its linked receipt is persisted but Saga compensation remains incomplete and requires intervention

#### Scenario: Stale owner or changed authority
- **WHEN** ownership expires or current actor/provider configuration no longer matches
- **THEN** no new write is dispatched by that owner and no success is inferred from lease expiry
