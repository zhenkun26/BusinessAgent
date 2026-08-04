## Purpose

建立进度记录与问题留存的统一规范，让规划、阶段总结、决策与坑记录各有单一事实源，避免同类信息散落在多个文件中互相重叠、互相矛盾。

## ADDED Requirements

### Requirement: 里程碑规划必须有单一事实源

系统 SHALL 在 `docs/40-process/ROADMAP.md` 维护项目里程碑规划（已完成阶段、进行中 change、挂起事项），作为进度规划的单一事实源；其他文档 SHALL 引用而非复制规划内容。

#### Scenario: 规划信息唯一
- **WHEN** 需要确认项目当前阶段与后续规划
- **THEN** 以 `ROADMAP.md` 为准，其内容与 README 及 openspec change 状态一致

### Requirement: 阶段性总结必须按模板追加

系统 SHALL 为每轮迭代在 `docs/40-process/` 下追加阶段性总结，并沿用统一模板（进度概览、交付物、问题与修复、经验教训、下一步），命名包含阶段或周次标识。

#### Scenario: 新迭代总结落盘
- **WHEN** 完成一轮迭代
- **THEN** `docs/40-process/` 新增一份按模板编写的阶段性总结，且内容不与既有总结冲突

### Requirement: 设计决策必须记录背景与改判条件

系统 SHALL 在 `docs/40-process/DECISIONS.md` 以决策记录形式（背景、决策、放弃了什么、改判条件）沉淀重要设计与工程决策；新增决策 SHALL 追加而非改写历史条目。

#### Scenario: 新增决策留痕
- **WHEN** 做出一个影响后续演进的设计选择
- **THEN** `DECISIONS.md` 新增一条含背景、决策、放弃项与改判条件的记录

### Requirement: 问题与坑必须统一记录

系统 SHALL 在 `docs/40-process/ISSUES.md` 统一记录问题、坑与 backlog（状态、优先级、现象、根因、修复、验证、日期），并将既有分散在手册中的坑记录迁移或链接到该文件，保证问题信息单一事实源。

#### Scenario: 问题信息可检索
- **WHEN** 排查一个曾出现的问题
- **THEN** `ISSUES.md` 能查到该问题的状态、根因与修复记录，无需翻多个手册
