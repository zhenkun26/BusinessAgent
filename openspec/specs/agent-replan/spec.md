# agent-replan Specification

## Purpose
让 Agent 在知识覆盖不足时自动重新规划检索策略或请求澄清，而不是只返回“未覆盖”后结束，并保证重规划次数有上限。
## Requirements
### Requirement: 知识覆盖不足时必须触发自动重规划

当子 Agent 返回 `needs_replan=true` 时，系统 SHALL 自动重新规划：根据重规划原因扩大检索、切换检索方式或请求用户补充信息，不得直接以“未覆盖”结束本轮对话。

#### Scenario: 知识库无结果时触发重规划
- **WHEN** 知识问答返回 `knowledge_coverage_none`
- **THEN** 系统执行至少一次重规划尝试并返回新的回答或澄清请求

#### Scenario: 部分覆盖时按提示补检
- **WHEN** 知识回答为部分覆盖且携带补检提示
- **THEN** 系统基于提示执行补充检索并生成更新后的回答

### Requirement: 重规划轮次必须有上限

系统 SHALL 将单次对话的重规划轮次限制为不超过 2 轮；达到上限后 SHALL 返回最终答复，并在响应中标记 `needs_replan` 与原因。

#### Scenario: 连续重规划失败后停止
- **WHEN** 重规划已执行 2 轮仍无法覆盖
- **THEN** 系统返回最终答复，不再继续重规划，并说明覆盖不足的原因

### Requirement: 重规划结果必须反馈给调用方

系统 SHALL 在对话响应中返回 `needs_replan`、`replan_reason` 与最终答案，使前端与调用方可区分“覆盖充分”“覆盖不足”与“重规划耗尽”。

#### Scenario: 重规划后覆盖成功
- **WHEN** 重规划补充检索后获得足够覆盖
- **THEN** 响应包含带来源的最终答案，`needs_replan=false`

#### Scenario: 重规划后仍覆盖不足
- **WHEN** 重规划耗尽且覆盖仍不足
- **THEN** 响应包含最终答案与 `needs_replan=true`，并带重规划原因

