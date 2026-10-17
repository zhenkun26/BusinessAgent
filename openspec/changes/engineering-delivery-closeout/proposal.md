## Why

项目已有多 Agent、检索、审批、外部适配与部署资产，但代码静态复核仍发现权限、执行一致性和可复现部署缺口。历史 CI、Mock 契约和阶段归档不能证明当前完整系统可交付；项目也没有真实企业用户、业务联调与灰度证据。

用户确认以「可独立部署、完整执行、可重复验证的企业应用工程交付」为收尾目标，并授权先完成 S0 文档与规格，之后逐项确认推进。

## What Changes

- 建立工程交付基线，冻结支持范围、参考服务边界、证据等级和完成条件。
- 在 ISSUES 登记 C01–C25 的当前证据、缺口、验收标准；在 ROADMAP 维护 S0–S7 顺序与依赖。
- 本 change 的 S0 仅落盘计划；后续任务保持未执行，每项须用户确认后进入实施。
- 保留真实接入与正式 UAT 两个既有 change 的未完成任务及生产放行阻塞状态。

## Capabilities

### New Capabilities

- `engineering-delivery`: 工程交付范围、逐项验收证据、顺序推进及与企业现场生产验证的隔离规则。

### Modified Capabilities

无。本轮只增加交付治理契约，不改现有运行时主规格。后续 C 项若改变既有能力要求，必须先补充对应 delta 与设计再实现。

## Impact

- 仅修改项目文档、OpenSpec context 与本 change；不改应用、测试、依赖、部署配置或版本号。
- 当前代码基线：`153f78651217eec7544b064446344d27b36085f1`。
- 差距事实源：[ISSUES](../../../docs/40-process/ISSUES.md#engineering-closeout)。
- 排期事实源：[ROADMAP](../../../docs/40-process/ROADMAP.md#engineering-closeout-stages)。
- 交付契约：[工程交付基线](../../../docs/50-engineering/engineering-delivery-baseline.md)。
- 不包含推送、合并、发布、部署或外部消息/业务写入授权；不新增依赖、不执行删除。
