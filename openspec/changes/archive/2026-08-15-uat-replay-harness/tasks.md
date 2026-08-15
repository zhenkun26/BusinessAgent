## 1. Fixture 回放契约

- [x] 1.1 为 12 个 UAT 场景补充结构化 `replay_contract`，明确命名空间允许/拒绝、审批状态与无外部副作用预期 <!-- evidence: enterprise-agent/eval/generate_uat_simulation.py -->
- [x] 1.2 重新生成 fixture，并在生成器中校验回放契约、实体引用、角色/部门覆盖和安全标记 <!-- evidence: enterprise-agent/eval/uat_simulation/fixture.json; generate_uat_simulation.py --check -->

## 2. 回放器实现

- [x] 2.1 新增标准库 CLI 回放器，读取 fixture 并拒绝缺失或不安全的 UAT/副作用标记 <!-- evidence: enterprise-agent/eval/run_uat_replay.py -->
- [x] 2.2 实现实体引用、角色/命名空间、场景 ID、审批状态和场景级安全断言检查 <!-- evidence: run_uat_replay.py; tests/test_uat_replay.py -->
- [x] 2.3 实现 JSON/Markdown 双格式报告、失败详情、非正式 UAT 声明和正确退出码 <!-- evidence: eval/results/uat_replay_report.* (ignored runtime evidence) -->

## 3. 测试与故障证据

- [x] 3.1 为通过场景、未知引用、危险标记和负向命名空间场景增加聚焦单元测试 <!-- evidence: enterprise-agent/tests/test_uat_replay.py (5 passed) -->
- [x] 3.2 执行成功/失败回放，确认报告内容、退出码和输出目录边界符合规格 <!-- evidence: normal replay exit 0; unsafe marker replay exit 1 with dual reports -->

## 4. 文档与 OpenSpec 收口

- [x] 4.1 更新 UAT 手册和模拟数据 README，补充回放命令、报告路径和“不可作为正式 UAT 证据”说明 <!-- evidence: docs/30-guides/UAT验收计划.md; enterprise-agent/eval/uat_simulation/README.md -->
- [x] 4.2 运行 OpenSpec 严格校验、代码质量检查和相关测试，记录证据并准备归档 <!-- evidence: openspec validate --strict; ruff; targeted pytest; full suite requires missing project dependencies -->
