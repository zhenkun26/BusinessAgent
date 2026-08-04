## Purpose

让 openspec 成为项目需求与文档演进的规范载体：配置完备、能力规格沉淀为主规格、一切变更走 openspec 生命周期，使「需求—设计—任务—实现—归档」全链路可追溯。

## ADDED Requirements

### Requirement: openspec 配置必须包含项目 context

系统 SHALL 在 `openspec/config.yaml` 中维护项目 context，内容包括技术栈、工程约定、文档规范与领域背景；新建或修改 openspec artifact 时 SHALL 以该 context 为约束。

#### Scenario: 配置可读且完整
- **WHEN** 打开 `openspec/config.yaml`
- **THEN** 能读到项目技术栈、工程约定与文档分类规范等背景信息

### Requirement: 能力规格必须沉淀为主规格

系统 SHALL 将已实现或已定稿的能力规格沉淀到 `openspec/specs/<capability>/spec.md` 主规格目录；change 中的 delta specs SHALL 在实现完成后通过 sync 流程并入主规格，主规格中不得残留 ADDED/MODIFIED 等 delta 标记。

#### Scenario: 主规格目录非空且格式规范
- **WHEN** 检查 `openspec/specs/`
- **THEN** 文档类能力（documentation-layout、version-control、progress-issue-records、openspec-normalization）均以标准主规格格式存在，无 delta 操作头

### Requirement: 变更必须走 openspec 生命周期

系统 SHALL 要求一切新的功能或文档变更先创建 openspec change（propose），完成设计、规格与任务后再实施（apply），实施完成后同步主规格并归档（archive）；任何变更不得绕过该流程直接修改主规格或代码。

#### Scenario: 新需求进入流程
- **WHEN** 提出一个新需求或文档改动
- **THEN** 先创建 change 与 proposal，再进入设计与任务阶段，实施完成后归档
