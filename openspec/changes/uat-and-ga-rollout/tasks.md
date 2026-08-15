## 1. 前置确认与素材整理

- [x] 1.1 确认前置 change 状态：`production-readiness-baseline` 已归档（SLA 达标线可用）、`load-test-and-dr-drill` 归档或给出压测/演练证据的时间点 <!-- reused: archived change tasks and loadtest/DR evidence -->
- [x] 1.2 盘点 `docs/30-guides/使用案例手册.md` 场景素材：按六类核心场景（知识问答/命名空间隔离/数据分析/工具执行/审批流/跨部门协作）建立章节引用映射 <!-- evidence: docs/30-guides/UAT验收计划.md §4 -->
- [ ] 1.3 确认 UAT 执行资源：真实验收用户人选（按 5 角色 × 部门）、执行环境与排期窗口

## 2. UAT 计划制定与执行

- [x] 2.1 起草 UAT 验收计划：角色 × 场景矩阵（每格引用手册章节号）、角色分工（验收用户/产品/研发/运维职责）、逐场景通过标准 <!-- evidence: docs/30-guides/UAT验收计划.md -->
- [x] 2.2 评审 UAT 计划：确认场景集完整性、通过标准可判定、对 Open Questions（真实用户范围）给出结论 <!-- evidence: eval/validate_uat_plan.py; docs/40-process/UAT计划评审记录-2026-08-15.md; 12/12 场景一致，真实用户/环境/排期/签署人未确认，正式 UAT 不放行 -->
- [ ] 2.3 按计划执行 UAT（允许分批，核心场景先行），逐场景记录结果与发现问题 <!-- G0 fixture 已生成，但未执行真实 UAT，不计入完成度 -->
- [ ] 2.4 问题修复与复验：UAT 发现的 P0/P1 修复后复验通过；收口 `docs/40-process/ISSUES.md` 的 I-02（UAT 部分）

## 3. 灰度方案制定与执行

- [x] 3.1 起草灰度发布方案：放量阶梯（单部门试点 → 多部门 → 全员）、每级观察期、观察指标（引用 SLA 口径）、回滚触发条件与回退操作路径 <!-- evidence: docs/30-guides/发布灰度与上线门槛检查单.md §§1-4 -->
- [ ] 3.2 评审灰度方案：确认比例、观察期（总计 2-4 周）与回滚路径可执行，结论落 `docs/40-process/DECISIONS.md`
- [ ] 3.3 按方案执行灰度：逐级放量，每级放量前确认上一级观察期指标达标并留记录
- [ ] 3.4 灰度观察期满且指标持续达标后，将灰度结论记录到 DECISIONS.md；期间触发回滚条件则执行回退并重新观察

## 4. 上线门槛核对与放行

- [x] 4.1 起草上线门槛检查单：六项门槛逐项的前置证据引用（CI/测试报告、压测报告、渗透测试报告、演练 RTO/RPO 记录、灰度结论） <!-- evidence: docs/30-guides/发布灰度与上线门槛检查单.md §5 -->
- [ ] 4.2 逐项核对检查单：证据齐备项打勾，缺口项记入 ISSUES 并阻止放行
- [ ] 4.3 全部打勾后评审签署全量放行结论，落 `docs/40-process/DECISIONS.md`；收口 ISSUES I-02 安全测试部分的遗留状态
- [ ] 4.4 运行 `openspec validate uat-and-ga-rollout --strict` 通过后归档
