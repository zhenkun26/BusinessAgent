## Why

UAT 与安全测试至今挂起（`docs/40-process/ISSUES.md` I-02 open），项目没有任何真实用户验收记录，也没有灰度与全量放行的正式判定依据。前期评审已给出上线门槛定义：核心场景自动化回归全绿、压测达标、P0/P1 清零、权限与渗透测试通过、备份恢复演练成功、至少 2-4 周灰度稳定运行，全部满足才适合正式全量上线（见 `docs/40-process/优化方向分析-生产上线-2026-08-05.md` 阶段五）。缺少正式的发布管理规格，这些门槛只是口头约定，UAT 验收、灰度观察、全量放行都没有可引用、可复核的契约。

## What Changes

- 新增发布管理规格，冻结三类上线契约：
  - **UAT 验收计划**：真实用户验收场景集（以 `docs/30-guides/使用案例手册.md` 的业务场景为素材）、角色分工（验收用户/产品/研发/运维）与通过标准。
  - **灰度发布方案**：灰度范围与比例、观察指标与观察期、升级/回滚触发条件。
  - **上线门槛检查单**：六项门槛逐项的前置证据要求（自动化回归、压测达标、P0/P1 清零、权限与渗透测试、备份恢复演练、灰度稳定运行），逐项打勾才可全量。
- UAT 计划正文落入 `docs/30-guides/`（操作手册层），灰度与放行决策结论落入 `docs/40-process/DECISIONS.md`（单一事实源）。
- 本 change 只产出规格、计划与检查单，不改业务代码；SLA 达标线与压测/演练证据引用 `production-readiness` 规格与 `load-test-and-dr-drill` change 的概念，但不对它们写 delta。

## Capabilities

### New Capabilities
- `release-management`: UAT 验收计划（场景集、角色分工、通过标准）、灰度发布方案（灰度比例、观察指标、回滚触发条件）与上线门槛检查单（六项门槛的前置证据与放行判定），作为 UAT 执行、灰度观察与全量上线的统一判定契约。

### Modified Capabilities

<!-- 无现有规格的需求变更：SLA 与压测/演练证据由 production-readiness 规格与
     load-test-and-dr-drill change 承载，本 change 仅引用其概念，不写 delta。 -->

## Impact

- 规格：新增 `openspec/specs/release-management/`（经本 change 归档后发布）。
- 文档：`docs/30-guides/` 新增 UAT 验收计划手册；`docs/40-process/DECISIONS.md` 追加上线门槛与灰度放行决策记录；`docs/40-process/ISSUES.md` 的 I-02 在 UAT 执行完成后收口。
- 前置依赖：`production-readiness-baseline`（SLA 达标线）与 `load-test-and-dr-drill`（压测/演练证据）完成并归档后，门槛检查单对应项才可打勾。
- 代码：无（纯规格与文档 change）。
