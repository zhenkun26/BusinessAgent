## Context

现状见 proposal.md 的 Why。关键约束：`BaseTool.invoke`（`app/tools/base.py:147-295`）已统一权限/参数校验/执行/审计/tracing，`tool_provider=http` 时走 `_call_external`；`http_adapter.py` 已实现超时（`external_timeout_seconds`，默认 10s）、指数退避重试（`external_max_retries`，默认 2 次）、401/403/4xx 立即失败、凭证仅入请求头；`ticket.py` 的 `_call_external` 已按 `POST /api/v1/tickets`、`PATCH /api/v1/tickets/{ticket_id}` 契约写好，但缺幂等键，补偿只操作内存 Mock；Saga 补偿失败重试与审计本地缓存回写已由 worker 承担（既有 external-system-integration 规格）。联调环境是最大不确定项：当前 `ticket_api_base` 仅为占位地址（`app/config.py:106`）。

## Goals / Non-Goals

**Goals:**
- 工单真实接入的幂等、重试、补偿、审计、降级、联调验收六要素形成可验证的契约与实现方案。
- 方案不破坏既有双通道架构与 `ToolResult` 契约，Mock 通道行为不变。
- 联调验收用例集可机械执行，作为 `crm-mail-sso-integration` 的模板。

**Non-Goals:**
- 不接入 CRM/邮件/SSO（后续 change 承接）。
- 不改 `tool_provider` 全局开关语义，不引入新的配置框架。
- 不在本 change 中自建 Mock 服务器产品化——联调环境依赖由外部工单系统或临时 stub 满足，方案见 Decisions 3。

## Decisions

### 1. 幂等键由工具层生成，经 `extra_headers` 透传，不改 http_adapter 签名

`create_ticket._call_external` 生成幂等键（建议 `ticket-{request_id}-{uuid}`，优先复用 `context["request_id"]` 保证同一次对话请求内重试键不变），通过 `call_external_api` 已有的 `extra_headers` 参数以 `Idempotency-Key` 头发送，并记入 `side_effects` 供审计关联。

备选：给 `call_external_api` 增加 `idempotency_key` 专用参数。否决：现有 `extra_headers` 已够用，改签名会波及 CRM/邮件工具调用点，违反最小改动。

### 2. 补偿真实化走同一条 `_call_external` 通道，不复用 invoke 的 RBAC

`compensate` 在 http 提供方下直接调用 `call_external_api`：创建补偿 → PATCH 状态为 closed 并附 `closure_reason=saga_compensation`；更新补偿 → PATCH 恢复 `old_values`。补偿属内部系统行为，沿用既有 `skip_rbac=True` 语义（Saga 补偿本就跳过 RBAC），不新建权限通道。补偿失败按既有规格交 worker 退避重试。

备选：补偿走 `invoke(skip_rbac=True)`。否决：`compensate` 拿到的入参是 `compensation_data` 而非工具入参 schema，走 invoke 会把两套参数模型搅在一起；直接调用适配器更直白。

### 3. 联调环境依赖外部工单系统或临时 stub，验收用例集落成可执行清单

联调环境依赖：`ticket_api_base` 指向可达实例、`ticket_api_token` 注入有效凭证、网络连通（容器内可解析）。若真实工单系统未就绪，允许用临时 HTTP stub（返回契约一致的 JSON）先行验收，但验收记录必须标注 stub/真实实例。验收用例集覆盖规格中的全部 Scenario：正常创建/更新、幂等重试（同键重复提交只产生一张工单）、4xx/5xx 错误路径、补偿触发与 worker 重试、审计回写、mock 降级切换。

备选：等真实工单系统采购到位再联调。否决：评审已明确阶段二工作量最大且最不确定，用 stub 先行可提前锁定契约，真实系统到位后只重跑用例集。

### 4. 重试边界不新造逻辑，规格只冻结 http_adapter 既有行为

重试语义（5xx/网络错误退避重试、4xx 立即失败、耗尽返回 `success=false`）已在 `http_adapter.py` 实现并有测试覆盖，本 change 只把它冻结为工单场景的规格要求，不新增重试参数或熔断器。

备选：为工单单独加熔断/限流。否决：单系统试点阶段过度设计，待 `crm-mail-sso-integration` 多系统接入后再评估。

## Risks / Trade-offs

- 外部工单系统不支持幂等键头 → 规格要求"同一请求重试不产生重复工单"，若对方不支持 `Idempotency-Key`，降级方案为工具层在重试前查询是否已建单；联调验收时优先验证对方能力，结论记入 DECISIONS。
- 用 stub 验收可能掩盖真实系统的契约偏差（字段命名、错误码体系）→ 验收记录强制标注 stub/真实实例，真实系统到位后必须重跑全量用例。
- 补偿真实化后 Saga 回滚也依赖外部系统可用性 → 补偿失败交 worker 退避重试并留可查询记录，与既有规格一致；工单已关闭的补偿（close）天然幂等，风险可控。

## Migration Plan

无数据迁移。apply 阶段顺序：幂等键与补偿真实化实现 → 单元测试（Mock http 层）→ 配置联调环境（base URL/凭证/stub）→ 执行联调验收用例集并记录 → 归档。回滚策略：`tool_provider` 切回 mock 即恢复演示态，代码改动向后兼容（Mock 通道行为不变）。

## Open Questions

- 联调所用的工单系统最终选型（自研/Jira/Zendesk/临时 stub）未定；不影响规格与任务拆分，apply 阶段开工前确认即可。
- `update_ticket` 补偿恢复旧值前是否需要先读当前值做冲突检测（联调期间工单可能被人工改动）？倾向不做，补偿语义是"Saga 回滚"而非"并发控制"，评审确认。
