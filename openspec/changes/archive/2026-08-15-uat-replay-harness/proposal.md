## Why

当前已经有一批确定性的 G0 模拟数据，但只能做静态查看，无法稳定地逐场景检查引用完整性、角色/命名空间边界、审批前后状态和外部副作用开关。真实 UAT 用户、环境和排期尚未确认，因此需要先建立一个不接触真实系统的技术彩排回放能力，把可执行的前置验证与正式 UAT 明确分层。

## What Changes

- 增加一个基于现有 `uat_simulation/fixture.json` 的本地回放器。
- 为 12 个 UAT 场景执行确定性的结构与安全断言，输出机器可读结果和人类可读汇总报告。
- 回放器只读 fixture，不连接 PostgreSQL、Milvus、Redis、CRM、邮件或工单系统。
- 报告明确标记为 G0 技术彩排，不得被解释为正式 UAT、真实外部系统联调或上线放行证据。
- 将回放命令、报告位置和 OpenSpec/UAT 证据关系写入操作手册。

## Capabilities

### New Capabilities

- `uat-replay`: 对合成 UAT fixture 执行可复现的本地技术彩排，校验数据引用、权限边界、审批状态和副作用安全标记，并生成结果报告。

### Modified Capabilities

- 无。现有正式 UAT、真实外部系统接入和灰度放行要求不变。

## Impact

- 新增 `enterprise-agent/eval/run_uat_replay.py` 及其聚焦测试。
- 复用 `enterprise-agent/eval/uat_simulation/fixture.json`，默认报告写入 `enterprise-agent/eval/results/`。
- 更新 `enterprise-agent/eval/uat_simulation/README.md` 与 `docs/30-guides/UAT验收计划.md` 的 G0 执行说明。
- 不新增运行时依赖、不修改 API、数据库 schema、真实连接器或生产配置。
