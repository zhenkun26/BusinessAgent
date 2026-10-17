## MODIFIED Requirements

### Requirement: 后台 worker 必须执行异步任务
The independent worker SHALL consume retained PostgreSQL jobs after initializing required dependencies. Pre-dispatch lease expiry SHALL permit bounded delayed recovery. Once dispatch may have occurred, failure SHALL retain a queryable dead task without automatic repeat. Full delivery SHALL additionally require C13 durable Saga recovery and C21 non-deleting audit replay; C14 alone SHALL NOT claim those capabilities.

#### Scenario: 文档入库任务被消费
- **WHEN** approval creates a knowledge job
- **THEN** the worker executes frozen input or records a fixed failure reason; queue acknowledgment does not remove evidence

#### Scenario: Saga 失败补偿重试
- **WHEN** a Saga task lacks a supported durable compensation identity
- **THEN** the C14 worker refuses with C13_REQUIRED; automatic compensation remains blocked until C13 supplies and validates that contract

#### Scenario: 审计缓存回写
- **WHEN** only the legacy deleting cache replay path exists
- **THEN** the worker preserves cache files and defers replay to C21, rather than silently deleting files or claiming synchronization

#### Scenario: 消费者失活
- **WHEN** a consumer stops unexpectedly or its progress heartbeat becomes stale
- **THEN** process supervision exits on termination and the admin consumer query exposes stale progress; this is not complete C21 readiness
