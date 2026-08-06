## Why

工单工具（`enterprise-agent/app/tools/ticket.py`）仍是内存 Mock（预置 6 个历史工单，进程重启即丢），但 v1.1.0 已建好双通道契约：`BaseTool._call_external` 抽象 + `http_adapter.py`（httpx 超时/指数退避/凭证不入日志）+ `tool_provider` 开关（mock/http）。按 `docs/40-process/优化方向分析-生产上线-2026-08-05.md` 阶段二规划（建议顺序：工单 → CRM → 邮件 → SSO），工单是首个真实外部系统接入试点：缺的不是通道，而是真实接入所需的幂等、补偿、审计回写与联调验收全链路——这些模式必须在工单上验证通过后，后续系统才能照抄。

## What Changes

- 真实工单系统接入试点落地，补齐当前契约之外的接入要素：
  - **幂等键**：`create_ticket` 真实调用必须携带幂等键，重试与 Saga 补偿不得产生重复工单。
  - **重试策略**：复用 `http_adapter.py` 的超时/指数退避（`external_timeout_seconds`/`external_max_retries`），明确工单场景的重试边界（仅 5xx/网络类错误重试，4xx 立即失败）。
  - **Saga 补偿真实化**：`CreateTicketTool.compensate`（关闭工单）与 `UpdateTicketTool.compensate`（恢复旧值）在 http 提供方下真正触达外部系统，补偿失败交由 worker 按退避策略重试。
  - **审计回写**：真实外部调用的结果（成功/失败/重试次数/补偿动作）写入审计日志，数据库不可用时经 worker 本地缓存回写。
  - **联调验收用例**：定义联调环境依赖（工单系统 base URL、凭证、网络可达性）与验收用例集，作为真实接入是否成立的判定标准。
- Mock 提供方保留为降级回退通道：真实系统不可用或凭证缺失时可切回 `tool_provider=mock`，不影响演示与回归测试。
- 本 change 产出规格 delta 与联调验收方案；实现与联调执行在 apply 阶段完成。

## Capabilities

### New Capabilities

<!-- 无新增能力：真实工单接入属于既有 external-system-integration 能力的需求扩展。 -->

### Modified Capabilities

- `external-system-integration`: 增加真实工单系统接入的需求——幂等键防重复建单、重试策略边界、Saga 补偿真实触达与失败重试、审计回写、联调环境依赖与验收用例，以及 Mock 降级回退通道的切换语义。

## Impact

- 规格：`openspec/specs/external-system-integration/` 经归档后新增真实工单接入相关需求。
- 代码（apply 阶段）：`app/tools/ticket.py`（幂等键、补偿真实化）、`app/tools/http_adapter.py`（幂等键头透传，如需）、`app/config.py`（联调环境配置项）。
- 依赖：联调环境需提供可访问的工单系统实例（`ticket_api_base` 指向真实地址、`ticket_api_token` 注入有效凭证）；沿用既有 `httpx`，无新增第三方依赖。
- 后续 change 的依赖：`crm-mail-sso-integration` 将以本 change 验证的幂等/补偿/审计模式为模板。
