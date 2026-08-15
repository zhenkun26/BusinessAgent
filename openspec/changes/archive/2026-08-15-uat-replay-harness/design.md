## Context

当前已有 `enterprise-agent/eval/uat_simulation/fixture.json`，但它只能被静态查看；正式 UAT 的真实用户、独立环境和排期仍未确认。回放器属于评测工具，不应进入 FastAPI 运行时，也不应依赖 PostgreSQL、Milvus、Redis 或任何外部连接器。

实现需要同时满足 `uat-replay` 规格的两类边界：一方面把引用、角色、命名空间、审批状态和场景覆盖检查做成可重复执行的证据；另一方面，无论通过还是失败，都必须明确它是 G0 技术彩排，不是正式 UAT、真实外部系统联调或上线放行证据。

## Goals / Non-Goals

**Goals:**

- 提供一个仅依赖 Python 标准库的命令行回放器，默认读取现有合成 fixture。
- 对全局安全标记、实体引用、角色/命名空间/场景/审批状态覆盖，以及每个场景的结构化回放契约执行独立检查。
- 同时生成机器可读 JSON 和人类可读 Markdown 报告；失败时仍保留完整失败证据并返回非零退出码。
- 让 fixture 中的负向权限场景以显式 `replay_contract` 表达“应拒绝”，不通过场景编号或中文断言文本推断预期。

**Non-Goals:**

- 不启动应用服务，不写入数据库，不调用 CRM、邮件、工单、SSO 或其他外部系统。
- 不模拟真实 LLM 输出质量，不判定知识答案的业务正确性，不替代真实员工 UAT。
- 不把回放报告写入正式发布决策或关闭 `ISSUES.md` 的 I-02。

## Decisions

### 1. 使用独立标准库脚本，不复用应用运行时

新增 `enterprise-agent/eval/run_uat_replay.py`，只使用 `argparse`、`json`、`datetime`、`pathlib` 等标准库。这样回放可以在依赖未安装、外部服务未启动的环境中运行，也避免评测脚本意外初始化应用连接。

备选方案：通过 FastAPI API 回放。否决：会把 G0 变成服务级测试，产生数据库/连接器状态依赖，且无法保证“只读 fixture、无外部副作用”。

### 2. 把场景预期写成结构化 `replay_contract`

每个场景补充结构化契约，例如允许/拒绝的文档命名空间、预期审批状态、审批人权限和“禁止外部副作用”要求。回放器只依据契约和实体索引判断结果，不解析自然语言 `expected_assertions`。

备选方案：按 `UAT-K02` 等场景编号硬编码规则。否决：新增或调整场景时容易产生隐藏分支，且无法复用回放器。

### 3. 通过/失败都生成双格式报告

报告固定包含 `fixture_id`、执行时间、执行模式、正式 UAT 状态、每个检查项、失败详情和场景引用。`overall_status` 只有 `passed` 或 `failed`；报告额外写死 `formal_uat=false` 和 `release_evidence=false`，避免被误作为上线证据。

备选方案：只在成功时输出报告。否决：失败回放是发现数据或权限回归的关键证据，必须可留痕。

## Risks / Trade-offs

- [fixture 契约与生成器漂移] → 生成器和回放器各自做严格校验；每次生成后执行 `--check` 与回放测试。
- [报告时间导致内容不完全可复现] → fixture 内容和 seed 保持确定性；执行时间只作为证据元数据，并允许测试注入固定时间。
- [结构校验通过但业务答案仍错误] → 报告明确仅为 G0 技术彩排，知识答案、真实业务语义和外部系统返回必须由正式 UAT 另行确认。
- [误用报告进行上线放行] → JSON/Markdown 均显式标记非正式 UAT、非发布证据，操作手册同步写明边界。

## Migration Plan

1. 扩展现有 fixture 生成器，为 12 个场景写入 `replay_contract`。
2. 新增回放脚本和聚焦测试；默认报告写入已被忽略的 `enterprise-agent/eval/results/`。
3. 本地执行成功和失败 fixture 两类回放，确认退出码、报告和安全标记符合规格。
4. 回滚时删除回放脚本、测试、fixture 契约字段和文档引用即可；不涉及数据库迁移、服务重启或生产状态。

## Open Questions

无。真实用户、UAT 环境和灰度排期属于 `uat-and-ga-rollout` 的后续工作，不影响本 change 的技术方案。
