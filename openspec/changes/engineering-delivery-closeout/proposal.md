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
- `deployment-artifacts`: C01 的同摘要镜像部署、生产入口路由、流式透传与内部指标边界。

- `model-profile`: C02 生产模型方案、依赖契约、启动推理探针与失败闭合。

### Modified Capabilities

无现有能力主规格修改。当前增加交付治理与 C01 部署产物契约；后续 C 项若改变既有能力要求，必须先补充对应 delta 与设计再实现。

## Impact

- S0 仅修改项目文档、OpenSpec context 与本 change。2026-10-17 用户进一步授权 C24 前置：新增离线安全验证入口、针对入口的回归测试及证据模板；不改应用业务行为、依赖、部署配置或版本号。
- 当前代码基线：`153f78651217eec7544b064446344d27b36085f1`。
- 差距事实源：[ISSUES](../../../docs/40-process/ISSUES.md#engineering-closeout)。
- 排期事实源：[ROADMAP](../../../docs/40-process/ROADMAP.md#engineering-closeout-stages)。
- 交付契约：[工程交付基线](../../../docs/50-engineering/engineering-delivery-baseline.md)。
- S0 文档提交 `05d8d0c` 已按用户单独授权推送到同名远端分支；该授权不延伸为 C24 新提交的推送。合并、发布、部署或外部消息/业务写入不在本轮范围；不新增依赖、不执行删除。

2026-10-17 后续授权：C24 提交 `a329603` 已推送到同名远端；本轮推进 C01，修改生产 Compose、Nginx、部署契约检查及文档，不扩展到 C02 模型、C03 迁移或 C09 多进程一致性。用户随后授权 C01 配置修复独立提交并推送到同名远端分支，再推进 C02；C03 仍未授权。真实运行验收缺少 Docker/Nginx 时保留 BLOCKED，不提前勾选整项。

C02 scope (confirmed 2026-10-17): replace the provisional local candidate with Beijing Bailian embedding/reranking and official DeepSeek Flash/Pro services. Implement separate credentials, bounded remote adapters, profile/startup validation, isolated vector collection configuration and slim-image alignment; retain approved libpq5/checkpoint checks. This increment includes documentation and offline verification only. Real API calls and isolated Linux acceptance remain BLOCKED; C02 remains open and C03 is not authorized.
